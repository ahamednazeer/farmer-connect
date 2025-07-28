"""
Farmer module for Farmer Connect
Handles farmer-specific functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from modules.database import get_db_connection
from modules.utils import require_login, require_approval, save_uploaded_file, send_notification
from datetime import datetime, date
import os
import csv
import io

farmer_bp = Blueprint('farmer', __name__)

@farmer_bp.route('/dashboard')
@require_login(['farmer'])
@require_approval
def dashboard():
    """Farmer dashboard"""
    conn = get_db_connection()
    
    # Get farmer information
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (session['user_id'],)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('auth.login'))
    
    # Get farmer stats
    stats = {}
    
    # Total products
    stats['total_products'] = conn.execute('''
        SELECT COUNT(*) FROM products WHERE farmer_id = ?
    ''', (session['user_id'],)).fetchone()[0]
    
    # Active products
    stats['active_products'] = conn.execute('''
        SELECT COUNT(*) FROM products 
        WHERE farmer_id = ? AND is_approved = 1 AND quantity > 0
    ''', (session['user_id'],)).fetchone()[0]
    
    # Pending products
    stats['pending_products'] = conn.execute('''
        SELECT COUNT(*) FROM products 
        WHERE farmer_id = ? AND is_approved = 0
    ''', (session['user_id'],)).fetchone()[0]
    
    # Total orders
    stats['total_orders'] = conn.execute('''
        SELECT COUNT(DISTINCT o.id) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ?
    ''', (session['user_id'],)).fetchone()[0]
    
    # Today's earnings
    stats['today_earnings'] = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND DATE(o.created_at) = DATE('now')
        AND o.payment_status = 'paid'
    ''', (session['user_id'],)).fetchone()[0]
    
    # Month's earnings
    stats['month_earnings'] = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND strftime('%Y-%m', o.created_at) = strftime('%Y-%m', 'now')
        AND o.payment_status = 'paid'
    ''', (session['user_id'],)).fetchone()[0]
    
    # Total earnings
    stats['total_earnings'] = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
    ''', (session['user_id'],)).fetchone()[0]
    
    # Pending orders
    stats['pending_orders'] = conn.execute('''
        SELECT COUNT(DISTINCT o.id) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.status = 'pending'
    ''', (session['user_id'],)).fetchone()[0]
    
    # Out of stock products
    stats['out_of_stock'] = conn.execute('''
        SELECT COUNT(*) FROM products 
        WHERE farmer_id = ? AND quantity = 0 AND is_approved = 1
    ''', (session['user_id'],)).fetchone()[0]
    
    # Average rating and total reviews
    try:
        rating_data = conn.execute('''
            SELECT AVG(rating) as avg_rating, COUNT(*) as total_reviews 
            FROM reviews r
            JOIN products p ON r.product_id = p.id
            WHERE p.farmer_id = ? AND r.is_approved = 1
        ''', (session['user_id'],)).fetchone()
        
        stats['avg_rating'] = round(rating_data[0], 1) if rating_data[0] else None
        stats['total_reviews'] = rating_data[1] if rating_data[1] else 0
    except Exception as e:
        # Handle case where reviews table might not exist or query fails
        stats['avg_rating'] = None
        stats['total_reviews'] = 0
    
    # Recent orders
    recent_orders = conn.execute('''
        SELECT o.*, u.full_name as consumer_name, 
               COALESCE(SUM(oi.subtotal), 0) as farmer_total
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN users u ON o.consumer_id = u.id
        WHERE oi.farmer_id = ?
        GROUP BY o.id, u.full_name
        ORDER BY o.created_at DESC
        LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    # Top selling products
    top_products = conn.execute('''
        SELECT p.*, COALESCE(SUM(oi.quantity), 0) as total_sold
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        WHERE p.farmer_id = ? AND p.is_approved = 1
        GROUP BY p.id
        ORDER BY total_sold DESC
        LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    # Inventory status (all products for inventory display)
    inventory_status = conn.execute('''
        SELECT * FROM products 
        WHERE farmer_id = ? AND is_approved = 1
        ORDER BY 
            CASE 
                WHEN quantity = 0 THEN 1
                WHEN quantity <= 5 THEN 2
                ELSE 3
            END,
            quantity ASC
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    
    # Low stock products
    low_stock_products = conn.execute('''
        SELECT * FROM products 
        WHERE farmer_id = ? AND quantity <= 5 AND quantity > 0 AND is_approved = 1
        ORDER BY quantity ASC
        LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    # Monthly earnings data for chart (last 12 months)
    monthly_earnings = []
    try:
        monthly_data = conn.execute('''
            SELECT strftime('%Y-%m', o.created_at) as month,
                   strftime('%m/%Y', o.created_at) as month_display,
                   COALESCE(SUM(oi.subtotal), 0) as earnings
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
            AND o.created_at >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', o.created_at)
            ORDER BY month
        ''', (session['user_id'],)).fetchall()
        
        monthly_earnings = [{'month': row[1], 'earnings': float(row[2])} for row in monthly_data]
    except Exception as e:
        # If there's an error, provide empty data
        monthly_earnings = []
    
    conn.close()
    
    return render_template('farmer/dashboard.html',
                         farmer=farmer,
                         stats=stats,
                         recent_orders=recent_orders,
                         top_products=top_products,
                         inventory_status=inventory_status,
                         low_stock_products=low_stock_products,
                         monthly_earnings=monthly_earnings)

@farmer_bp.route('/products')
@require_login(['farmer'])
@require_approval
def products():
    """Farmer products list"""
    conn = get_db_connection()
    
    # Get farmer information
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (session['user_id'],)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('auth.login'))
    
    # Get farmer stats for the navigation tabs
    stats = {}
    
    # Total products
    stats['total_products'] = conn.execute('''
        SELECT COUNT(*) FROM products WHERE farmer_id = ?
    ''', (session['user_id'],)).fetchone()[0]
    
    # Approved products (active)
    stats['approved_products'] = conn.execute('''
        SELECT COUNT(*) FROM products 
        WHERE farmer_id = ? AND is_approved = 1 AND quantity > 0
    ''', (session['user_id'],)).fetchone()[0]
    
    # Pending products
    stats['pending_products'] = conn.execute('''
        SELECT COUNT(*) FROM products 
        WHERE farmer_id = ? AND is_approved = 0
    ''', (session['user_id'],)).fetchone()[0]
    
    # Out of stock products
    stats['out_of_stock'] = conn.execute('''
        SELECT COUNT(*) FROM products 
        WHERE farmer_id = ? AND quantity = 0 AND is_approved = 1
    ''', (session['user_id'],)).fetchone()[0]
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    category = request.args.get('category')
    search = request.args.get('search')
    
    # Build query
    query = 'SELECT * FROM products WHERE farmer_id = ?'
    params = [session['user_id']]
    
    if status == 'active':
        query += ' AND is_approved = 1 AND quantity > 0'
    elif status == 'pending':
        query += ' AND is_approved = 0'
    elif status == 'out_of_stock':
        query += ' AND quantity = 0'
    
    if category:
        query += ' AND category = ?'
        params.append(category)
    
    if search:
        query += ' AND (name LIKE ? OR description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += ' ORDER BY created_at DESC'
    
    products_list = conn.execute(query, params).fetchall()
    
    # Get categories for filter
    categories = conn.execute('''
        SELECT DISTINCT category FROM products WHERE farmer_id = ?
        ORDER BY category
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('farmer/products.html',
                         farmer=farmer,
                         stats=stats,
                         products=products_list,
                         categories=categories,
                         current_status=status,
                         current_category=category,
                         current_search=search)

@farmer_bp.route('/products/add', methods=['GET', 'POST'])
@require_login(['farmer'])
@require_approval
def add_product():
    """Add new product"""
    if request.method == 'POST':
        # Get form data
        name = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        category = request.form['category']
        price = float(request.form['price'])
        unit = request.form['unit']
        quantity = int(request.form['quantity'])
        harvest_date = request.form.get('harvest_date')
        expiry_date = request.form.get('expiry_date')
        organic = 'organic' in request.form
        
        # Validation
        errors = []
        
        if not name:
            errors.append("Product name is required")
        
        if price <= 0:
            errors.append("Price must be greater than 0")
        
        if quantity < 0:
            errors.append("Quantity cannot be negative")
        
        if not category:
            errors.append("Category is required")
        
        if not unit:
            errors.append("Unit is required")
        
        # Validate dates
        if harvest_date:
            try:
                harvest_date = datetime.strptime(harvest_date, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Invalid harvest date")
                harvest_date = None
        
        if expiry_date:
            try:
                expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                if harvest_date and expiry_date <= harvest_date:
                    errors.append("Expiry date must be after harvest date")
            except ValueError:
                errors.append("Invalid expiry date")
                expiry_date = None
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            # Handle image upload
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                if file.filename:
                    image_path = save_uploaded_file(file, 'products')
            
            # Save product
            conn = get_db_connection()
            
            try:
                conn.execute('''
                    INSERT INTO products (
                        farmer_id, name, description, category, price, unit,
                        quantity, image, harvest_date, expiry_date, organic
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (session['user_id'], name, description, category, price, unit,
                      quantity, image_path, harvest_date, expiry_date, organic))
                
                conn.commit()
                flash('Product added successfully! It will be reviewed by admin.', 'success')
                return redirect(url_for('farmer.products'))
            
            except Exception as e:
                flash('Failed to add product. Please try again.', 'error')
                print(f"Add product error: {e}")
            
            finally:
                conn.close()
    
    # Get categories for form
    conn = get_db_connection()
    categories = conn.execute('SELECT name FROM categories WHERE is_active = 1').fetchall()
    conn.close()
    
    return render_template('farmer/add_product.html', categories=categories)

@farmer_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@require_login(['farmer'])
@require_approval
def edit_product(product_id):
    """Edit product"""
    conn = get_db_connection()
    
    # Get product (ensure it belongs to current farmer)
    product = conn.execute('''
        SELECT * FROM products WHERE id = ? AND farmer_id = ?
    ''', (product_id, session['user_id'])).fetchone()
    
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('farmer.products'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        category = request.form['category']
        price = float(request.form['price'])
        unit = request.form['unit']
        quantity = int(request.form['quantity'])
        harvest_date = request.form.get('harvest_date')
        expiry_date = request.form.get('expiry_date')
        organic = 'organic' in request.form
        
        # Validation (same as add_product)
        errors = []
        
        if not name:
            errors.append("Product name is required")
        
        if price <= 0:
            errors.append("Price must be greater than 0")
        
        if quantity < 0:
            errors.append("Quantity cannot be negative")
        
        # Validate dates
        if harvest_date:
            try:
                harvest_date = datetime.strptime(harvest_date, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Invalid harvest date")
                harvest_date = None
        
        if expiry_date:
            try:
                expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                if harvest_date and expiry_date <= harvest_date:
                    errors.append("Expiry date must be after harvest date")
            except ValueError:
                errors.append("Invalid expiry date")
                expiry_date = None
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            # Handle image upload
            image_path = product['image']
            if 'image' in request.files:
                file = request.files['image']
                if file.filename:
                    new_image = save_uploaded_file(file, 'products')
                    if new_image:
                        # Delete old image if exists
                        if image_path and os.path.exists(f"static/{image_path}"):
                            os.remove(f"static/{image_path}")
                        image_path = new_image
            
            # Update product
            try:
                conn.execute('''
                    UPDATE products SET
                        name = ?, description = ?, category = ?, price = ?,
                        unit = ?, quantity = ?, image = ?, harvest_date = ?,
                        expiry_date = ?, organic = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND farmer_id = ?
                ''', (name, description, category, price, unit, quantity,
                      image_path, harvest_date, expiry_date, organic,
                      product_id, session['user_id']))
                
                conn.commit()
                flash('Product updated successfully!', 'success')
                return redirect(url_for('farmer.products'))
            
            except Exception as e:
                flash('Failed to update product. Please try again.', 'error')
                print(f"Update product error: {e}")
    
    # Get categories for form
    categories = conn.execute('SELECT name FROM categories WHERE is_active = 1').fetchall()
    conn.close()
    
    return render_template('farmer/edit_product.html', product=product, categories=categories)

@farmer_bp.route('/products/delete/<int:product_id>', methods=['POST'])
@require_login(['farmer'])
@require_approval
def delete_product(product_id):
    """Delete product"""
    conn = get_db_connection()
    
    # Get product (ensure it belongs to current farmer)
    product = conn.execute('''
        SELECT * FROM products WHERE id = ? AND farmer_id = ?
    ''', (product_id, session['user_id'])).fetchone()
    
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('farmer.products'))
    
    # Check if product has orders
    has_orders = conn.execute('''
        SELECT COUNT(*) FROM order_items WHERE product_id = ?
    ''', (product_id,)).fetchone()[0]
    
    if has_orders > 0:
        flash('Cannot delete product with existing orders!', 'error')
    else:
        try:
            # Delete image if exists
            if product['image'] and os.path.exists(f"static/{product['image']}"):
                os.remove(f"static/{product['image']}")
            
            # Delete product
            conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
            conn.commit()
            flash('Product deleted successfully!', 'success')
        
        except Exception as e:
            flash('Failed to delete product. Please try again.', 'error')
            print(f"Delete product error: {e}")
    
    conn.close()
    return redirect(url_for('farmer.products'))

@farmer_bp.route('/orders')
@require_login(['farmer'])
@require_approval
def orders():
    """Farmer orders list"""
    conn = get_db_connection()
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    payment_status = request.args.get('payment_status', 'all')
    
    # Build query
    query = '''
        SELECT o.id, o.order_number, o.status, o.payment_status, o.payment_method, 
               o.total_amount, o.delivery_address, o.created_at, o.updated_at,
               u.full_name as consumer_name, u.phone as consumer_phone,
               u.location as customer_location,
               COALESCE(SUM(oi.subtotal), 0) as farmer_amount
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN users u ON o.consumer_id = u.id
        WHERE oi.farmer_id = ?
    '''
    params = [session['user_id']]
    
    if status != 'all':
        query += ' AND o.status = ?'
        params.append(status)
    
    if payment_status != 'all':
        query += ' AND o.payment_status = ?'
        params.append(payment_status)
    
    query += ' GROUP BY o.id, u.full_name, u.phone ORDER BY o.created_at DESC'
    
    orders_list = conn.execute(query, params).fetchall()
    
    # Debug: Check date values
    for order in orders_list[:3]:  # Check first 3 orders
        print(f"Order {order['id']}: created_at = '{order['created_at']}', type = {type(order['created_at'])}")
    
    # Check if export is requested
    export = request.args.get('export', '')
    if export == 'true':
        # Export orders as CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write CSV header
        writer.writerow([
            'Order Number', 'Customer Name', 'Customer Phone', 'Customer Location',
            'Status', 'Payment Status', 'Amount', 'Date', 'Items'
        ])
        
        # Write order data
        for order in orders_list:
            # Get order items for this order
            order_items = conn.execute('''
                SELECT p.name, oi.quantity, oi.price, p.unit
                FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ? AND oi.farmer_id = ?
            ''', (order['id'], session['user_id'])).fetchall()
            
            items_str = '; '.join([f"{item['name']} ({item['quantity']} {item['unit']} @ ₹{item['price']})" 
                                   for item in order_items])
            
            writer.writerow([
                order['order_number'],
                order['consumer_name'],
                order['consumer_phone'] or 'Not provided',
                order['customer_location'] or 'Not provided',
                order['status'].title(),
                order['payment_status'].title(),
                f"₹{order['farmer_amount']:.2f}",
                order['created_at'],
                items_str
            ])
        
        conn.close()
        
        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=farmer_orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response
    
    # Calculate order statistics
    stats = {}
    
    # Total orders for this farmer
    stats['total_orders'] = conn.execute('''
        SELECT COUNT(DISTINCT o.id)
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ?
    ''', (session['user_id'],)).fetchone()[0]
    
    # Pending orders
    stats['pending_orders'] = conn.execute('''
        SELECT COUNT(DISTINCT o.id)
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.status = 'pending'
    ''', (session['user_id'],)).fetchone()[0]
    
    # Completed orders (delivered)
    stats['completed_orders'] = conn.execute('''
        SELECT COUNT(DISTINCT o.id)
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.status = 'delivered'
    ''', (session['user_id'],)).fetchone()[0]
    
    # Total revenue for this farmer
    total_revenue = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0)
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
    ''', (session['user_id'],)).fetchone()[0]
    stats['total_revenue'] = float(total_revenue) if total_revenue else 0.0
    
    conn.close()
    
    return render_template('farmer/orders.html',
                         orders=orders_list,
                         current_status=status,
                         current_payment_status=payment_status,
                         stats=stats)

@farmer_bp.route('/api/orders/details')
@require_login(['farmer'])
@require_approval  
def get_order_details():
    """API endpoint to get order details for modal display"""
    order_id = request.args.get('id')
    if not order_id:
        return jsonify({'success': False, 'message': 'Order ID required'})
    
    try:
        conn = get_db_connection()
        
        # Get order with farmer's items only
        order = conn.execute('''
            SELECT DISTINCT o.*, u.full_name as consumer_name, u.email as consumer_email,
                   u.phone as consumer_phone, u.location as customer_location
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN users u ON o.consumer_id = u.id
            WHERE o.id = ? AND oi.farmer_id = ?
        ''', (order_id, session['user_id'])).fetchone()
        
        if not order:
            conn.close()
            return jsonify({'success': False, 'message': 'Order not found'})
        
        # Get order items for this farmer only
        order_items = conn.execute('''
            SELECT oi.*, p.name as product_name, p.unit, p.image as product_image
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ? AND oi.farmer_id = ?
        ''', (order_id, session['user_id'])).fetchall()
        
        # Calculate farmer's total for this order
        farmer_total = sum(float(item['subtotal']) for item in order_items)
        
        conn.close()
        
        # Format the response
        order_data = {
            'order_id': order['order_number'],
            'status': order['status'],
            'customer_name': order['consumer_name'],
            'customer_email': order['consumer_email'],
            'customer_phone': order['consumer_phone'],
            'customer_location': order['customer_location'],
            'delivery_address': order['delivery_address'],
            'created_at': order['created_at'],
            'payment_method': order['payment_method'],
            'payment_status': order['payment_status'],
            'farmer_total': farmer_total,
            'items': []
        }
        
        for item in order_items:
            order_data['items'].append({
                'product_name': item['product_name'],
                'product_image': f"/static/uploads/{item['product_image']}" if item['product_image'] else None,
                'quantity': item['quantity'],
                'unit': item['unit'],
                'price': float(item['price']),
                'total': float(item['subtotal'])
            })
        
        return jsonify({'success': True, 'order': order_data})
        
    except Exception as e:
        print(f"Error in get_order_details: {e}")
        return jsonify({'success': False, 'message': f'Error loading order details: {str(e)}'})

@farmer_bp.route('/orders/<int:order_id>')
@require_login(['farmer'])
@require_approval
def order_detail(order_id):
    """Order detail page - redirects to orders list for now"""
    # For now, redirect back to orders list as the detail template doesn't exist
    flash('Order details are available via the "View" button in the orders list', 'info')
    return redirect(url_for('farmer.orders'))

@farmer_bp.route('/earnings')
@require_login(['farmer'])
@require_approval
def earnings():
    """Farmer earnings dashboard"""
    conn = get_db_connection()
    
    # Get earnings stats
    stats = {}
    
    # Total earnings
    stats['total_earnings'] = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
    ''', (session['user_id'],)).fetchone()[0]
    
    # This month earnings
    stats['month_earnings'] = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
        AND strftime('%Y-%m', o.created_at) = strftime('%Y-%m', 'now')
    ''', (session['user_id'],)).fetchone()[0]
    
    # This week earnings
    stats['week_earnings'] = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
        AND DATE(o.created_at) >= DATE('now', '-7 days')
    ''', (session['user_id'],)).fetchone()[0]
    
    # Today's earnings
    stats['today_earnings'] = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
        AND DATE(o.created_at) = DATE('now')
    ''', (session['user_id'],)).fetchone()[0]
    
    # Recent earnings transactions
    recent_earnings = conn.execute('''
        SELECT o.order_number, o.created_at, oi.subtotal, p.name as product_name
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
        ORDER BY o.created_at DESC
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    
    # Monthly earnings for chart
    monthly_earnings = conn.execute('''
        SELECT strftime('%Y-%m', o.created_at) as month, 
               SUM(oi.subtotal) as earnings
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
        GROUP BY strftime('%Y-%m', o.created_at)
        ORDER BY month DESC
        LIMIT 12
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    # For now, redirect to dashboard as earnings template doesn't exist
    flash('Earnings details are available on your dashboard', 'info')
    return redirect(url_for('farmer.dashboard'))

@farmer_bp.route('/inventory')
@require_login(['farmer'])
@require_approval
def inventory():
    """Inventory management"""
    conn = get_db_connection()
    
    products = conn.execute('''
        SELECT * FROM products 
        WHERE farmer_id = ? AND is_approved = 1
        ORDER BY name
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    # For now, redirect to products page as inventory template doesn't exist
    flash('Inventory management is available on your products page', 'info')
    return redirect(url_for('farmer.products'))

@farmer_bp.route('/api/inventory/update', methods=['POST'])
@require_login(['farmer'])
@require_approval
def update_inventory():
    """Update product inventory (AJAX)"""
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 0))
    
    if quantity < 0:
        return jsonify({'success': False, 'message': 'Quantity cannot be negative'})
    
    conn = get_db_connection()
    
    # Verify product belongs to farmer
    product = conn.execute('''
        SELECT * FROM products WHERE id = ? AND farmer_id = ?
    ''', (product_id, session['user_id'])).fetchone()
    
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})
    
    try:
        conn.execute('''
            UPDATE products 
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND farmer_id = ?
        ''', (quantity, product_id, session['user_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Inventory updated successfully'})
    
    except Exception as e:
        print(f"Inventory update error: {e}")
        return jsonify({'success': False, 'message': 'Failed to update inventory'})

@farmer_bp.route('/api/products/<int:product_id>/restock', methods=['POST'])
@require_login(['farmer'])
@require_approval
def restock_product(product_id):
    """Restock product with optional price update (AJAX)"""
    data = request.get_json()
    quantity = int(data.get('quantity', 0))
    price = data.get('price')
    
    if quantity < 0:
        return jsonify({'success': False, 'message': 'Quantity cannot be negative'})
    
    conn = get_db_connection()
    
    # Verify product belongs to farmer
    product = conn.execute('''
        SELECT * FROM products WHERE id = ? AND farmer_id = ?
    ''', (product_id, session['user_id'])).fetchone()
    
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})
    
    try:
        # Update quantity and optionally price
        if price and float(price) > 0:
            conn.execute('''
                UPDATE products 
                SET quantity = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND farmer_id = ?
            ''', (quantity, float(price), product_id, session['user_id']))
            message = 'Product restocked and price updated successfully'
        else:
            conn.execute('''
                UPDATE products 
                SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND farmer_id = ?
            ''', (quantity, product_id, session['user_id']))
            message = 'Product restocked successfully'
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': message})
    
    except Exception as e:
        print(f"Restock error: {e}")
        return jsonify({'success': False, 'message': 'Failed to restock product'})

# Enhanced earnings and reporting endpoints

@farmer_bp.route('/earnings/report/<period>')
@require_login(['farmer'])
@require_approval
def earnings_report(period):
    """Generate earnings report for specific period"""
    conn = get_db_connection()
    
    # Define period filters
    date_filter = ""
    if period == 'today':
        date_filter = "AND DATE(o.created_at) = DATE('now')"
    elif period == 'week':
        date_filter = "AND DATE(o.created_at) >= DATE('now', '-7 days')"
    elif period == 'month':
        date_filter = "AND strftime('%Y-%m', o.created_at) = strftime('%Y-%m', 'now')"
    elif period == 'year':
        date_filter = "AND strftime('%Y', o.created_at) = strftime('%Y', 'now')"
    
    # Get detailed earnings data
    earnings_data = conn.execute(f'''
        SELECT o.order_number, o.created_at, o.payment_status, 
               p.name as product_name, p.category, p.unit,
               oi.quantity, oi.price, oi.subtotal,
               u.full_name as consumer_name
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON o.consumer_id = u.id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid' {date_filter}
        ORDER BY o.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    # Calculate summary
    total_earnings = sum(row['subtotal'] for row in earnings_data)
    total_orders = len(set(row['order_number'] for row in earnings_data))
    total_items_sold = sum(row['quantity'] for row in earnings_data)
    
    # Category-wise breakdown
    category_stats = {}
    for row in earnings_data:
        category = row['category']
        if category not in category_stats:
            category_stats[category] = {'earnings': 0, 'items_sold': 0, 'orders': 0}
        category_stats[category]['earnings'] += row['subtotal']
        category_stats[category]['items_sold'] += row['quantity']
        category_stats[category]['orders'] += 1
    
    conn.close()
    
    return render_template('farmer/earnings_report.html',
                         period=period,
                         earnings_data=earnings_data,
                         total_earnings=total_earnings,
                         total_orders=total_orders,
                         total_items_sold=total_items_sold,
                         category_stats=category_stats)

@farmer_bp.route('/api/earnings/export/<format>/<period>')
@require_login(['farmer'])
@require_approval
def export_earnings(format, period):
    """Export earnings data as CSV or PDF"""
    import csv
    import json
    from io import StringIO
    
    conn = get_db_connection()
    
    # Define period filters
    date_filter = ""
    if period == 'today':
        date_filter = "AND DATE(o.created_at) = DATE('now')"
    elif period == 'week':
        date_filter = "AND DATE(o.created_at) >= DATE('now', '-7 days')"
    elif period == 'month':
        date_filter = "AND strftime('%Y-%m', o.created_at) = strftime('%Y-%m', 'now')"
    elif period == 'year':
        date_filter = "AND strftime('%Y', o.created_at) = strftime('%Y', 'now')"
    
    # Get earnings data
    earnings_data = conn.execute(f'''
        SELECT o.order_number, o.created_at, 
               p.name as product_name, p.category, p.unit,
               oi.quantity, oi.price, oi.subtotal,
               u.full_name as consumer_name
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON o.consumer_id = u.id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid' {date_filter}
        ORDER BY o.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    if format == 'csv':
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Order Number', 'Date', 'Product', 'Category', 'Unit',
                        'Quantity', 'Price', 'Total', 'Customer'])
        
        # Write data
        for row in earnings_data:
            writer.writerow([row['order_number'], row['created_at'], 
                           row['product_name'], row['category'], row['unit'],
                           row['quantity'], row['price'], row['subtotal'], 
                           row['consumer_name']])
        
        from flask import make_response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=earnings_{period}.csv'
        return response
    
    return jsonify({'error': 'Format not supported'})

@farmer_bp.route('/inventory/alerts')
@require_login(['farmer'])
@require_approval
def inventory_alerts():
    """Inventory alerts and low stock management"""
    conn = get_db_connection()
    
    # Get low stock products (quantity <= 5)
    low_stock = conn.execute('''
        SELECT * FROM products 
        WHERE farmer_id = ? AND quantity <= 5 AND quantity > 0 AND is_approved = 1
        ORDER BY quantity ASC
    ''', (session['user_id'],)).fetchall()
    
    # Get out of stock products
    out_of_stock = conn.execute('''
        SELECT * FROM products 
        WHERE farmer_id = ? AND quantity = 0 AND is_approved = 1
        ORDER BY name
    ''', (session['user_id'],)).fetchall()
    
    # Get products expiring soon (within 7 days)
    expiring_soon = conn.execute('''
        SELECT * FROM products 
        WHERE farmer_id = ? AND expiry_date IS NOT NULL 
        AND expiry_date <= DATE('now', '+7 days')
        AND expiry_date >= DATE('now')
        AND quantity > 0 AND is_approved = 1
        ORDER BY expiry_date ASC
    ''', (session['user_id'],)).fetchall()
    
    # Get existing alert settings
    alert_settings = conn.execute('''
        SELECT * FROM inventory_alerts 
        WHERE farmer_id = ? AND is_active = 1
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('farmer/inventory_alerts.html',
                         low_stock=low_stock,
                         out_of_stock=out_of_stock,
                         expiring_soon=expiring_soon,
                         alert_settings=alert_settings)

@farmer_bp.route('/api/inventory/alert/setup', methods=['POST'])
@require_login(['farmer'])
@require_approval
def setup_inventory_alert():
    """Setup inventory alert for a product"""
    data = request.get_json()
    product_id = data.get('product_id')
    alert_type = data.get('alert_type')
    threshold_value = data.get('threshold_value', 5)
    
    conn = get_db_connection()
    
    # Verify product belongs to farmer
    product = conn.execute('''
        SELECT * FROM products WHERE id = ? AND farmer_id = ?
    ''', (product_id, session['user_id'])).fetchone()
    
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})
    
    try:
        conn.execute('''
            INSERT OR REPLACE INTO inventory_alerts 
            (farmer_id, product_id, alert_type, threshold_value, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (session['user_id'], product_id, alert_type, threshold_value))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Alert setup successfully'})
    
    except Exception as e:
        print(f"Alert setup error: {e}")
        return jsonify({'success': False, 'message': 'Failed to setup alert'})

@farmer_bp.route('/api/products/bulk-update', methods=['POST'])
@require_login(['farmer'])
@require_approval
def bulk_update_products():
    """Bulk update product quantities"""
    data = request.get_json()
    updates = data.get('updates', [])
    
    if not updates:
        return jsonify({'success': False, 'message': 'No updates provided'})
    
    conn = get_db_connection()
    updated_count = 0
    
    try:
        for update in updates:
            product_id = update.get('product_id')
            quantity = int(update.get('quantity', 0))
            
            if quantity < 0:
                continue
            
            # Verify product belongs to farmer
            product = conn.execute('''
                SELECT * FROM products WHERE id = ? AND farmer_id = ?
            ''', (product_id, session['user_id'])).fetchone()
            
            if product:
                conn.execute('''
                    UPDATE products 
                    SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND farmer_id = ?
                ''', (quantity, product_id, session['user_id']))
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully updated {updated_count} products'
        })
    
    except Exception as e:
        print(f"Bulk update error: {e}")
        return jsonify({'success': False, 'message': 'Failed to update products'})

@farmer_bp.route('/orders/update-status/<int:order_id>', methods=['POST'])
@require_login(['farmer'])
@require_approval
def update_order_status(order_id):
    """Update order status"""
    new_status = request.form.get('status')
    message = request.form.get('message', '')
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
              request.headers.get('Content-Type', '').startswith('application/')
    
    if not new_status:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Status is required'})
        flash('Status is required', 'error')
        return redirect(url_for('farmer.order_detail', order_id=order_id))
    
    valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
    if new_status not in valid_statuses:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Invalid status'})
        flash('Invalid status', 'error')
        return redirect(url_for('farmer.order_detail', order_id=order_id))
    
    conn = get_db_connection()
    
    # Verify this farmer has items in this order
    order = conn.execute('''
        SELECT DISTINCT o.id FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.id = ? AND oi.farmer_id = ?
    ''', (order_id, session['user_id'])).fetchone()
    
    if not order:
        conn.close()
        if is_ajax:
            return jsonify({'success': False, 'message': 'Order not found or access denied'})
        flash('Order not found or access denied', 'error')
        return redirect(url_for('farmer.orders'))
    
    try:
        # Update order status
        conn.execute('''
            UPDATE orders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_status, order_id))
        
        # Add tracking entry
        conn.execute('''
            INSERT INTO order_tracking (order_id, status, message, updated_by)
            VALUES (?, ?, ?, ?)
        ''', (order_id, new_status, message, session['user_id']))
        
        # Send notification to consumer
        consumer_id = conn.execute('''
            SELECT consumer_id FROM orders WHERE id = ?
        ''', (order_id,)).fetchone()[0]
        
        send_notification(
            consumer_id, 
            'Order Status Updated', 
            f'Your order status has been updated to: {new_status.title()}',
            'info',
            f'/consumer/orders/{order_id}',
            conn
        )
        
        conn.commit()
        
        if is_ajax:
            return jsonify({'success': True, 'message': 'Order status updated successfully!'})
        flash('Order status updated successfully!', 'success')
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Order status update error: {e}")
        print(f"Full traceback: {error_details}")
        if is_ajax:
            return jsonify({'success': False, 'message': f'Failed to update order status: {str(e)}'})
        flash('Failed to update order status', 'error')
    
    finally:
        conn.close()
    
    return redirect(url_for('farmer.order_detail', order_id=order_id))

@farmer_bp.route('/orders/<int:order_id>/confirm-payment', methods=['POST'])
@require_login(['farmer'])
@require_approval
def confirm_payment(order_id):
    """Confirm payment received for an order"""
    payment_method = request.form.get('payment_method', '')
    notes = request.form.get('notes', '')
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
              request.headers.get('Content-Type', '').startswith('application/')
    
    conn = get_db_connection()
    
    # Verify this farmer has items in this order and order exists
    order = conn.execute('''
        SELECT DISTINCT o.id, o.payment_status, o.consumer_id, o.order_number
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.id = ? AND oi.farmer_id = ?
    ''', (order_id, session['user_id'])).fetchone()
    
    if not order:
        conn.close()
        if is_ajax:
            return jsonify({'success': False, 'message': 'Order not found or access denied'})
        flash('Order not found or access denied', 'error')
        return redirect(url_for('farmer.orders'))
    
    # Check if payment is already confirmed
    if order['payment_status'] == 'paid':
        conn.close()
        if is_ajax:
            return jsonify({'success': False, 'message': 'Payment already confirmed for this order'})
        flash('Payment already confirmed for this order', 'warning')
        return redirect(url_for('farmer.orders'))
    
    try:
        # Update payment status to paid
        conn.execute('''
            UPDATE orders 
            SET payment_status = 'paid', 
                payment_method = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (payment_method or 'Cash/Direct', order_id))
        
        # Add tracking entry for payment confirmation
        conn.execute('''
            INSERT INTO order_tracking (order_id, status, message, updated_by)
            VALUES (?, ?, ?, ?)
        ''', (order_id, 'payment_confirmed', 
              f'Payment confirmed by farmer. Method: {payment_method or "Cash/Direct"}. Notes: {notes}', 
              session['user_id']))
        
        # Send notification to consumer
        send_notification(
            order['consumer_id'], 
            'Payment Confirmed', 
            f'Payment for order #{order["order_number"]} has been confirmed by the farmer.',
            'success',
            f'/consumer/orders/{order_id}',
            conn
        )
        
        # Send notification to admin (optional)
        admin_users = conn.execute('''
            SELECT id FROM users WHERE user_type = 'admin' AND is_active = 1
        ''').fetchall()
        
        for admin in admin_users:
            send_notification(
                admin['id'], 
                'Payment Confirmed', 
                f'Payment for order #{order["order_number"]} confirmed by farmer.',
                'info',
                f'/admin/orders/{order_id}',
                conn
            )
        
        conn.commit()
        
        if is_ajax:
            return jsonify({'success': True, 'message': 'Payment confirmed successfully!'})
        flash('Payment confirmed successfully!', 'success')
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Payment confirmation error: {e}")
        print(f"Full traceback: {error_details}")
        if is_ajax:
            return jsonify({'success': False, 'message': f'Failed to confirm payment: {str(e)}'})
        flash('Failed to confirm payment', 'error')
    
    finally:
        conn.close()
    
    return redirect(url_for('farmer.orders'))

@farmer_bp.route('/profile/edit', methods=['GET', 'POST'])
@require_login(['farmer'])
@require_approval
def edit_profile():
    """Edit farmer profile"""
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Get form data
        full_name = request.form['full_name'].strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        farm_name = request.form.get('farm_name', '').strip()
        farm_description = request.form.get('farm_description', '').strip()
        
        # Validation
        if not full_name:
            flash('Full name is required', 'error')
        else:
            try:
                # Handle profile image upload
                profile_image = None
                if 'profile_image' in request.files:
                    file = request.files['profile_image']
                    if file.filename:
                        profile_image = save_uploaded_file(file, 'profiles')
                
                # Update user profile
                if profile_image:
                    conn.execute('''
                        UPDATE users SET
                            full_name = ?, phone = ?, location = ?, 
                            farm_name = ?, farm_description = ?, profile_image = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (full_name, phone, location, farm_name, farm_description, 
                          profile_image, session['user_id']))
                else:
                    conn.execute('''
                        UPDATE users SET
                            full_name = ?, phone = ?, location = ?, 
                            farm_name = ?, farm_description = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (full_name, phone, location, farm_name, farm_description, 
                          session['user_id']))
                
                conn.commit()
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('farmer.dashboard'))
            
            except Exception as e:
                flash('Failed to update profile', 'error')
                print(f"Profile update error: {e}")
    
    # Get current profile data
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (session['user_id'],)).fetchone()
    
    conn.close()
    
    return render_template('farmer/edit_profile.html', farmer=farmer)