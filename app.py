#!/usr/bin/env python3
"""
Farmer Connect - E-commerce Platform
Main application entry point
"""

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime
import uuid

# Import modules
from modules.auth import auth_bp
from modules.farmer import farmer_bp
from modules.consumer import consumer_bp
from modules.admin import admin_bp
from modules.database import init_db, get_db_connection
from modules.utils import allowed_file, indian_rupee_format

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(farmer_bp, url_prefix='/farmer')
app.register_blueprint(consumer_bp, url_prefix='/consumer')
app.register_blueprint(admin_bp, url_prefix='/admin')

# Custom date formatter for SQLite string dates
def format_date(date_string, format_string='%b %d, %Y'):
    """Format date string from SQLite to readable format"""
    if not date_string:
        return 'Unknown'
    
    # If it's already a datetime object, just format it
    if hasattr(date_string, 'strftime'):
        return date_string.strftime(format_string)
    
    # Convert string to datetime
    try:
        # SQLite datetime format: 'YYYY-MM-DD HH:MM:SS'
        dt = datetime.strptime(str(date_string), '%Y-%m-%d %H:%M:%S')
        return dt.strftime(format_string)
    except (ValueError, TypeError):
        try:
            # Try with date only format: 'YYYY-MM-DD'
            dt = datetime.strptime(str(date_string), '%Y-%m-%d')
            return dt.strftime(format_string)
        except (ValueError, TypeError):
            try:
                # Try with microseconds: 'YYYY-MM-DD HH:MM:SS.ffffff'
                dt = datetime.strptime(str(date_string), '%Y-%m-%d %H:%M:%S.%f')
                return dt.strftime(format_string)
            except (ValueError, TypeError):
                # If all else fails, return the original string
                return str(date_string)

def nl2br(text):
    """Convert newlines to HTML <br> tags"""
    if not text:
        return ''
    # Import Markup to mark the HTML as safe
    from markupsafe import Markup
    # Replace newlines with <br> tags and mark as safe HTML
    return Markup(str(text).replace('\n', '<br>\n'))

# Register template filters
app.jinja_env.filters['rupee'] = indian_rupee_format
app.jinja_env.filters['date_format'] = format_date
app.jinja_env.filters['nl2br'] = nl2br

# Register template globals
from modules.utils import get_category_icon, get_status_badge_class
app.jinja_env.globals['get_category_icon'] = get_category_icon
app.jinja_env.globals['get_status_badge_class'] = get_status_badge_class

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'products'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)

# Initialize database tables on startup
with app.app_context():
    init_db()

@app.route('/')
def index():
    """Home page with featured products"""
    conn = get_db_connection()
    
    # Get featured products
    featured_products = conn.execute('''
        SELECT p.*, u.farm_name, u.location 
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE p.is_approved = 1 AND p.quantity > 0
        ORDER BY p.created_at DESC
        LIMIT 8
    ''').fetchall()
    
    # Get categories with product count
    categories = conn.execute('''
        SELECT category, COUNT(*) as product_count
        FROM products 
        WHERE is_approved = 1 AND quantity > 0
        GROUP BY category
        ORDER BY product_count DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('index.html', 
                         featured_products=featured_products,
                         categories=categories)

@app.route('/products')
def products():
    """Products listing page with filters"""
    conn = get_db_connection()
    
    # Get filter parameters
    category = request.args.get('category')
    location = request.args.get('location')
    search = request.args.get('search')
    sort_by = request.args.get('sort_by', 'newest')
    
    # Build query
    query = '''
        SELECT p.*, u.farm_name, u.location 
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE p.is_approved = 1 AND p.quantity > 0
    '''
    params = []
    
    if category:
        query += ' AND p.category = ?'
        params.append(category)
    
    if location:
        query += ' AND u.location LIKE ?'
        params.append(f'%{location}%')
    
    if search:
        query += ' AND (p.name LIKE ? OR p.description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    
    # Add sorting
    if sort_by == 'price_low':
        query += ' ORDER BY p.price ASC'
    elif sort_by == 'price_high':
        query += ' ORDER BY p.price DESC'
    elif sort_by == 'name':
        query += ' ORDER BY p.name ASC'
    else:  # newest
        query += ' ORDER BY p.created_at DESC'
    
    products_list = conn.execute(query, params).fetchall()
    
    # Get all categories and locations for filters
    categories = conn.execute('''
        SELECT DISTINCT category FROM products 
        WHERE is_approved = 1 AND quantity > 0
        ORDER BY category
    ''').fetchall()
    
    locations = conn.execute('''
        SELECT DISTINCT location FROM users 
        WHERE user_type = 'farmer' AND is_approved = 1
        ORDER BY location
    ''').fetchall()
    
    conn.close()
    
    return render_template('products.html',
                         products=products_list,
                         categories=categories,
                         locations=locations,
                         current_category=category,
                         current_location=location,
                         current_search=search,
                         current_sort=sort_by)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Product detail page"""
    conn = get_db_connection()
    
    product = conn.execute('''
        SELECT * FROM products
        WHERE id = ? AND is_approved = 1
    ''', (product_id,)).fetchone()
    
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('products'))
    
    # Get farmer information
    farmer = conn.execute('''
        SELECT * FROM users 
        WHERE id = ? AND user_type = 'farmer'
    ''', (product['farmer_id'],)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('products'))
    
    # Get related products from same farmer
    related_products = conn.execute('''
        SELECT * FROM products 
        WHERE farmer_id = ? AND id != ? AND is_approved = 1 AND quantity > 0
        LIMIT 4
    ''', (product['farmer_id'], product_id)).fetchall()
    
    conn.close()
    
    return render_template('product_detail.html',
                         product=product,
                         farmer=farmer,
                         related_products=related_products)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()
            
            # Validate required fields
            if not all([name, email, subject, message]):
                return jsonify({
                    'success': False, 
                    'message': 'Please fill in all required fields'
                })
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return jsonify({
                    'success': False, 
                    'message': 'Please enter a valid email address'
                })
            
            # Save to database
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO contact_messages (name, email, phone, subject, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, email, phone, subject, message))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True, 
                'message': 'Thank you for your message! We will get back to you soon.'
            })
            
        except Exception as e:
            print(f"Contact form error: {e}")
            return jsonify({
                'success': False, 
                'message': 'An error occurred while sending your message. Please try again.'
            })
    
    return render_template('contact.html')

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    """Add item to cart (AJAX)"""
    if 'user_id' not in session or session.get('user_type') != 'consumer':
        return jsonify({'success': False, 'message': 'Please login as consumer'})
    
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))
    
    conn = get_db_connection()
    
    # Check if product exists and has enough stock
    product = conn.execute(
        'SELECT * FROM products WHERE id = ? AND is_approved = 1',
        (product_id,)
    ).fetchone()
    
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})
    
    if product['quantity'] < quantity:
        return jsonify({'success': False, 'message': 'Not enough stock available'})
    
    # Check if item already in cart
    existing_item = conn.execute('''
        SELECT * FROM cart_items 
        WHERE user_id = ? AND product_id = ?
    ''', (session['user_id'], product_id)).fetchone()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item['quantity'] + quantity
        if product['quantity'] < new_quantity:
            return jsonify({'success': False, 'message': 'Not enough stock available'})
        
        conn.execute('''
            UPDATE cart_items 
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND product_id = ?
        ''', (new_quantity, session['user_id'], product_id))
    else:
        # Add new item
        conn.execute('''
            INSERT INTO cart_items (user_id, product_id, quantity)
            VALUES (?, ?, ?)
        ''', (session['user_id'], product_id, quantity))
    
    conn.commit()
    
    # Get cart count
    cart_count = conn.execute('''
        SELECT SUM(quantity) FROM cart_items WHERE user_id = ?
    ''', (session['user_id'],)).fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': 'Item added to cart',
        'cart_count': cart_count
    })

@app.context_processor
def inject_cart_count():
    """Inject cart count into all templates"""
    if 'user_id' in session and session.get('user_type') == 'consumer':
        conn = get_db_connection()
        cart_count = conn.execute('''
            SELECT SUM(quantity) FROM cart_items WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()[0] or 0
        conn.close()
        return {'cart_count': cart_count}
    return {'cart_count': 0}

@app.route('/favicon.ico')
def favicon():
    """Serve favicon to prevent 404 errors"""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)