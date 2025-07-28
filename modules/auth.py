"""
Authentication module for Farmer Connect
Handles user registration, login, and session management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from modules.database import get_db_connection
from modules.utils import validate_email, validate_phone, save_uploaded_file

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        # Get form data
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        user_type = request.form['user_type']
        full_name = request.form['full_name'].strip()
        phone = request.form['phone'].strip()
        location = request.form['location'].strip()
        
        # Validation
        errors = []
        
        if len(username) < 3:
            errors.append("Username must be at least 3 characters long")
        
        if not validate_email(email):
            errors.append("Please enter a valid email address")
        
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long")
        
        if password != confirm_password:
            errors.append("Passwords do not match")
        
        if user_type not in ['farmer', 'consumer']:
            errors.append("Please select a valid user type")
        
        if not full_name:
            errors.append("Full name is required")
        
        if phone and not validate_phone(phone):
            errors.append("Please enter a valid phone number")
        
        if not location:
            errors.append("Location is required")
        
        # Check if user already exists
        conn = get_db_connection()
        existing_user = conn.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        
        if existing_user:
            errors.append("Username or email already exists")
        
        if errors:
            for error in errors:
                flash(error, 'error')
            conn.close()
            return render_template('auth/register.html')
        
        # Additional fields for farmers
        farm_name = None
        farm_description = None
        
        if user_type == 'farmer':
            farm_name = request.form.get('farm_name', '').strip()
            farm_description = request.form.get('farm_description', '').strip()
            
            if not farm_name:
                flash("Farm name is required for farmers", 'error')
                conn.close()
                return render_template('auth/register.html')
        
        # Create user
        password_hash = generate_password_hash(password)
        is_approved = 1 if user_type == 'consumer' else 0  # Consumers auto-approved
        
        try:
            cursor = conn.execute('''
                INSERT INTO users (
                    username, email, password_hash, user_type, full_name,
                    phone, location, farm_name, farm_description, is_approved
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, email, password_hash, user_type, full_name,
                  phone, location, farm_name, farm_description, is_approved))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            if user_type == 'farmer':
                flash('Registration successful! Your account is pending admin approval.', 'info')
            else:
                # Auto-login consumers
                session['user_id'] = user_id
                session['username'] = username
                session['user_type'] = user_type
                session['full_name'] = full_name
                session['is_approved'] = is_approved
                flash('Registration successful! Welcome to Farmer Connect.', 'success')
        
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
            print(f"Registration error: {e}")
        
        finally:
            conn.close()
        
        return redirect(url_for('index'))
    
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username_or_email = request.form['username_or_email'].strip().lower()
        password = request.form['password']
        remember_me = 'remember_me' in request.form
        
        if not username_or_email or not password:
            flash('Please enter both username/email and password', 'error')
            return render_template('auth/login.html')
        
        conn = get_db_connection()
        
        # Find user by username or email
        user = conn.execute('''
            SELECT * FROM users 
            WHERE (username = ? OR email = ?) AND is_active = 1
        ''', (username_or_email, username_or_email)).fetchone()
        
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            # Set session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = user['user_type']
            session['full_name'] = user['full_name']
            session['is_approved'] = user['is_approved']
            
            # Set permanent session if remember me is checked
            if remember_me:
                session.permanent = True
            
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            
            # Redirect based on user type
            if user['user_type'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user['user_type'] == 'farmer':
                return redirect(url_for('farmer.dashboard'))
            else:
                return redirect(url_for('consumer.dashboard'))
        else:
            flash('Invalid username/email or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    """User logout"""
    username = session.get('full_name', 'User')
    session.clear()
    flash(f'Goodbye, {username}!', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """User profile management"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Get form data
        full_name = request.form['full_name'].strip()
        phone = request.form['phone'].strip()
        location = request.form['location'].strip()
        farm_name = request.form.get('farm_name', '').strip()
        farm_description = request.form.get('farm_description', '').strip()
        
        # Validation
        errors = []
        
        if not full_name:
            errors.append("Full name is required")
        
        if phone and not validate_phone(phone):
            errors.append("Please enter a valid phone number")
        
        if not location:
            errors.append("Location is required")
        
        if user['user_type'] == 'farmer' and not farm_name:
            errors.append("Farm name is required")
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            # Handle profile image upload
            profile_image = user['profile_image']
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file.filename:
                    saved_path = save_uploaded_file(file, 'profiles')
                    if saved_path:
                        profile_image = saved_path
            
            # Update user
            try:
                conn.execute('''
                    UPDATE users SET
                        full_name = ?, phone = ?, location = ?,
                        farm_name = ?, farm_description = ?, profile_image = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (full_name, phone, location, farm_name, farm_description,
                      profile_image, session['user_id']))
                
                conn.commit()
                
                # Update session
                session['full_name'] = full_name
                
                flash('Profile updated successfully!', 'success')
            
            except Exception as e:
                flash('Failed to update profile. Please try again.', 'error')
                print(f"Profile update error: {e}")
    
    # Refresh user data
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    
    # Calculate user statistics based on user type
    stats = {}
    
    if user['user_type'] == 'farmer':
        # Farmer statistics
        stats['total_products'] = conn.execute('''
            SELECT COUNT(*) FROM products WHERE farmer_id = ?
        ''', (session['user_id'],)).fetchone()[0]
        
        stats['total_orders'] = conn.execute('''
            SELECT COUNT(DISTINCT o.id) FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE oi.farmer_id = ?
        ''', (session['user_id'],)).fetchone()[0]
        
        stats['total_earnings'] = conn.execute('''
            SELECT COALESCE(SUM(oi.subtotal), 0) FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
        ''', (session['user_id'],)).fetchone()[0]
        
    elif user['user_type'] == 'consumer':
        # Consumer statistics
        stats['total_orders'] = conn.execute('''
            SELECT COUNT(*) FROM orders WHERE consumer_id = ?
        ''', (session['user_id'],)).fetchone()[0]
        
        stats['total_spent'] = conn.execute('''
            SELECT COALESCE(SUM(total_amount), 0) FROM orders 
            WHERE consumer_id = ? AND payment_status = 'paid'
        ''', (session['user_id'],)).fetchone()[0]
        
        stats['wishlist_items'] = conn.execute('''
            SELECT COUNT(*) FROM wishlists WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()[0]
        
        stats['reviews_given'] = conn.execute('''
            SELECT COUNT(*) FROM reviews WHERE consumer_id = ?
        ''', (session['user_id'],)).fetchone()[0]
    
    else:
        # Admin or other user types - set default stats
        stats['total_products'] = 0
        stats['total_orders'] = 0
        stats['total_earnings'] = 0
        stats['total_spent'] = 0
        stats['wishlist_items'] = 0
        stats['reviews_given'] = 0
    
    # Get recent activities (optional - can be implemented later)
    recent_activities = []
    
    conn.close()
    
    return render_template('auth/profile.html', user=user, stats=stats, recent_activities=recent_activities)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Change user password"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Validation
        if len(new_password) < 6:
            flash('New password must be at least 6 characters long', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('auth/change_password.html')
        
        # Verify current password
        conn = get_db_connection()
        user = conn.execute(
            'SELECT password_hash FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()
        
        if not check_password_hash(user['password_hash'], current_password):
            flash('Current password is incorrect', 'error')
            conn.close()
            return render_template('auth/change_password.html')
        
        # Update password
        new_password_hash = generate_password_hash(new_password)
        
        try:
            conn.execute('''
                UPDATE users 
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_password_hash, session['user_id']))
            
            conn.commit()
            flash('Password changed successfully!', 'success')
            
        except Exception as e:
            flash('Failed to change password. Please try again.', 'error')
            print(f"Password change error: {e}")
        
        finally:
            conn.close()
        
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password (basic implementation)"""
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        
        if not validate_email(email):
            flash('Please enter a valid email address', 'error')
            return render_template('auth/forgot_password.html')
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT id FROM users WHERE email = ? AND is_active = 1',
            (email,)
        ).fetchone()
        conn.close()
        
        if user:
            # In a real application, you would send a password reset email
            flash('Password reset instructions have been sent to your email.', 'info')
        else:
            # Don't reveal if email exists or not (security)
            flash('Password reset instructions have been sent to your email.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')