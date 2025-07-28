"""
Utility functions for Farmer Connect
"""

import os
import uuid
import re
from werkzeug.utils import secure_filename
from functools import wraps
from flask import session, redirect, url_for, flash

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, folder='products'):
    """Save uploaded file with unique name"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{uuid.uuid4()}{ext}"
        
        # Create directory if it doesn't exist
        upload_path = os.path.join('static/uploads', folder)
        os.makedirs(upload_path, exist_ok=True)
        
        # Save file
        filepath = os.path.join(upload_path, unique_filename)
        file.save(filepath)
        
        return f"uploads/{folder}/{unique_filename}"
    return None

def indian_rupee_format(amount):
    """Format amount in Indian Rupee format"""
    if amount is None:
        return "₹0"
    
    amount = float(amount)
    if amount == int(amount):
        amount = int(amount)
    
    # Convert to string and format with commas
    amount_str = f"{amount:,.2f}" if amount != int(amount) else f"{amount:,}"
    
    return f"₹{amount_str}"

def generate_order_number():
    """Generate unique order number"""
    import random
    import string
    from datetime import datetime
    
    # Format: FC + YYMMDD + 4 random digits
    date_part = datetime.now().strftime("%y%m%d")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"FC{date_part}{random_part}"

def require_login(user_types=None):
    """Decorator to require login"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page.', 'error')
                return redirect(url_for('auth.login'))
            
            if user_types and session.get('user_type') not in user_types:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_approval(f):
    """Decorator to require account approval"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_approved'):
            flash('Your account is pending approval. Please wait for admin approval.', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate Indian phone number format"""
    # Remove spaces and special characters
    phone_clean = re.sub(r'[^\d+]', '', phone)
    
    # Check various Indian phone number patterns
    patterns = [
        r'^\+91[6-9]\d{9}$',  # +91xxxxxxxxxx
        r'^91[6-9]\d{9}$',    # 91xxxxxxxxxx
        r'^[6-9]\d{9}$',      # xxxxxxxxxx
    ]
    
    return any(re.match(pattern, phone_clean) for pattern in patterns)

def format_phone(phone):
    """Format phone number for display"""
    if not phone:
        return ""
    
    # Remove all non-digits except +
    phone_clean = re.sub(r'[^\d+]', '', phone)
    
    # If it starts with +91 or 91, format accordingly
    if phone_clean.startswith('+91'):
        number = phone_clean[3:]
        return f"+91 {number[:5]} {number[5:]}"
    elif phone_clean.startswith('91') and len(phone_clean) == 12:
        number = phone_clean[2:]
        return f"+91 {number[:5]} {number[5:]}"
    elif len(phone_clean) == 10:
        return f"+91 {phone_clean[:5]} {phone_clean[5:]}"
    
    return phone

def get_file_size(filepath):
    """Get file size in human readable format"""
    if not os.path.exists(filepath):
        return "0 B"
    
    size = os.path.getsize(filepath)
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    
    return f"{size:.1f} TB"

def calculate_delivery_charge(total_amount, delivery_distance=None):
    """Calculate delivery charge based on amount and distance"""
    from modules.database import get_setting
    
    free_delivery_above = float(get_setting('free_delivery_above', 1000))
    base_delivery_charge = float(get_setting('delivery_charge', 50))
    
    if total_amount >= free_delivery_above:
        return 0
    
    # Basic delivery charge
    delivery_charge = base_delivery_charge
    
    # Add distance-based charge if provided
    if delivery_distance and delivery_distance > 10:
        extra_km = delivery_distance - 10
        delivery_charge += extra_km * 5  # ₹5 per km after 10km
    
    return delivery_charge

def truncate_text(text, length=100):
    """Truncate text to specified length"""
    if not text:
        return ""
    
    if len(text) <= length:
        return text
    
    return text[:length-3] + "..."

def get_category_icon(category):
    """Get icon class for category"""
    icons = {
        'Vegetables': 'fas fa-carrot',
        'Fruits': 'fas fa-apple-alt',
        'Dairy': 'fas fa-glass-whiskey',
        'Grains': 'fas fa-seedling',
        'Herbs': 'fas fa-leaf',
        'Pulses': 'fas fa-circle',
    }
    return icons.get(category, 'fas fa-shopping-basket')

def get_status_badge_class(status):
    """Get CSS class for status badges"""
    classes = {
        'pending': 'badge-warning',
        'confirmed': 'badge-info',
        'processing': 'badge-primary',
        'shipped': 'badge-secondary',
        'delivered': 'badge-success',
        'cancelled': 'badge-danger',
        'paid': 'badge-success',
        'failed': 'badge-danger',
        'refunded': 'badge-warning'
    }
    return classes.get(status.lower(), 'badge-secondary')

def send_notification(user_id, title, message, notification_type='info', link=None, conn=None):
    """Send notification to user"""
    from modules.database import get_db_connection
    
    # Use provided connection or create a new one
    should_close_conn = conn is None
    if conn is None:
        conn = get_db_connection()
    
    conn.execute('''
        INSERT INTO notifications (user_id, title, message, type, link)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, title, message, notification_type, link))
    
    # Only commit and close if we created the connection
    if should_close_conn:
        conn.commit()
        conn.close()

def get_user_notifications(user_id, limit=10, unread_only=False):
    """Get user notifications"""
    from modules.database import get_db_connection
    
    conn = get_db_connection()
    
    query = '''
        SELECT * FROM notifications 
        WHERE user_id = ?
    '''
    
    if unread_only:
        query += ' AND is_read = 0'
    
    query += ' ORDER BY created_at DESC'
    
    if limit:
        query += f' LIMIT {limit}'
    
    notifications = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    
    return notifications

def mark_notification_read(notification_id):
    """Mark notification as read"""
    from modules.database import get_db_connection
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE notifications 
        SET is_read = 1 
        WHERE id = ?
    ''', (notification_id,))
    conn.commit()
    conn.close()

def track_user_activity(user_id, activity_type, activity_data=None):
    """Track user activity for analytics"""
    from modules.database import get_db_connection
    from flask import request
    import json
    
    conn = get_db_connection()
    
    # Get user's IP and user agent
    ip_address = request.remote_addr if request else None
    user_agent = request.headers.get('User-Agent') if request else None
    
    # Convert activity data to JSON string
    data_json = json.dumps(activity_data) if activity_data else None
    
    try:
        conn.execute('''
            INSERT INTO analytics_events (user_id, event_type, event_data, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, activity_type, data_json, ip_address, user_agent))
        
        conn.commit()
    except Exception as e:
        print(f"Activity tracking error: {e}")
    finally:
        conn.close()

def get_product_rating(product_id):
    """Get average rating for a product"""
    from modules.database import get_db_connection
    
    conn = get_db_connection()
    
    try:
        result = conn.execute('''
            SELECT AVG(rating) as avg_rating, COUNT(*) as review_count
            FROM reviews 
            WHERE product_id = ? AND is_approved = 1
        ''', (product_id,)).fetchone()
        
        avg_rating = round(result['avg_rating'], 1) if result['avg_rating'] else 0
        review_count = result['review_count'] if result['review_count'] else 0
        
        return avg_rating, review_count
    
    except Exception as e:
        print(f"Get product rating error: {e}")
        return 0, 0
    
    finally:
        conn.close()

def get_farmer_rating(farmer_id):
    """Get average rating for a farmer"""
    from modules.database import get_db_connection
    
    conn = get_db_connection()
    
    try:
        result = conn.execute('''
            SELECT AVG(rating) as avg_rating, COUNT(*) as rating_count
            FROM farmer_ratings 
            WHERE farmer_id = ? AND is_approved = 1
        ''', (farmer_id,)).fetchone()
        
        avg_rating = round(result['avg_rating'], 1) if result['avg_rating'] else 0
        rating_count = result['rating_count'] if result['rating_count'] else 0
        
        return avg_rating, rating_count
    
    except Exception as e:
        print(f"Get farmer rating error: {e}")
        return 0, 0
    
    finally:
        conn.close()

def calculate_discount(original_amount, promo_code=None):
    """Calculate discount based on promo code or active promotions"""
    from modules.database import get_db_connection
    from datetime import date
    
    if not promo_code:
        return 0, None
    
    conn = get_db_connection()
    
    try:
        # Check if promo code exists and is active
        promotion = conn.execute('''
            SELECT * FROM promotions 
            WHERE promo_code = ? AND is_active = 1 
            AND start_date <= ? AND end_date >= ?
            AND (usage_limit IS NULL OR usage_count < usage_limit)
        ''', (promo_code.upper(), date.today(), date.today())).fetchone()
        
        if not promotion:
            return 0, "Invalid or expired promo code"
        
        # Check minimum order amount
        if original_amount < promotion['min_order_amount']:
            min_amount = indian_rupee_format(promotion['min_order_amount'])
            return 0, f"Minimum order amount is {min_amount} for this promotion"
        
        # Calculate discount
        if promotion['discount_type'] == 'percentage':
            discount = (original_amount * promotion['discount_value']) / 100
        else:  # fixed_amount
            discount = promotion['discount_value']
        
        # Ensure discount doesn't exceed order amount
        discount = min(discount, original_amount)
        
        return discount, None
    
    except Exception as e:
        print(f"Calculate discount error: {e}")
        return 0, "Error applying discount"
    
    finally:
        conn.close()

def apply_promotion_usage(promo_code):
    """Increment usage count for a promotion"""
    from modules.database import get_db_connection
    
    conn = get_db_connection()
    
    try:
        conn.execute('''
            UPDATE promotions 
            SET usage_count = usage_count + 1
            WHERE promo_code = ?
        ''', (promo_code.upper(),))
        
        conn.commit()
    
    except Exception as e:
        print(f"Apply promotion usage error: {e}")
    
    finally:
        conn.close()

def check_stock_alerts():
    """Check and send inventory alerts to farmers"""
    from modules.database import get_db_connection
    from datetime import datetime, timedelta
    
    conn = get_db_connection()
    
    try:
        # Get active alert settings
        alerts = conn.execute('''
            SELECT ia.*, p.name as product_name, p.quantity, p.expiry_date,
                   u.full_name as farmer_name
            FROM inventory_alerts ia
            JOIN products p ON ia.product_id = p.id
            JOIN users u ON ia.farmer_id = u.id
            WHERE ia.is_active = 1
        ''').fetchall()
        
        for alert in alerts:
            should_alert = False
            alert_message = ""
            
            if alert['alert_type'] == 'low_stock' and alert['quantity'] <= alert['threshold_value']:
                should_alert = True
                alert_message = f"Low stock alert: {alert['product_name']} has only {alert['quantity']} units left."
            
            elif alert['alert_type'] == 'out_of_stock' and alert['quantity'] == 0:
                should_alert = True
                alert_message = f"Out of stock alert: {alert['product_name']} is out of stock."
            
            elif alert['alert_type'] == 'expiring_soon' and alert['expiry_date']:
                try:
                    expiry = datetime.strptime(alert['expiry_date'], '%Y-%m-%d').date()
                    days_to_expiry = (expiry - datetime.now().date()).days
                    
                    if days_to_expiry <= alert['threshold_value']:
                        should_alert = True
                        alert_message = f"Expiry alert: {alert['product_name']} will expire in {days_to_expiry} days."
                except ValueError:
                    pass
            
            # Send alert if needed and not recently alerted
            if should_alert:
                last_alerted = alert['last_alerted']
                if not last_alerted or datetime.now() - datetime.fromisoformat(last_alerted) > timedelta(hours=24):
                    send_notification(
                        alert['farmer_id'],
                        'Inventory Alert',
                        alert_message,
                        'warning',
                        '/farmer/inventory'
                    )
                    
                    # Update last alerted timestamp
                    conn.execute('''
                        UPDATE inventory_alerts 
                        SET last_alerted = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (alert['id'],))
        
        conn.commit()
    
    except Exception as e:
        print(f"Stock alerts error: {e}")
    
    finally:
        conn.close()

def get_product_availability_status(product):
    """Get product availability status with appropriate styling"""
    if not product:
        return {'status': 'unavailable', 'text': 'Not Available', 'class': 'badge-danger'}
    
    quantity = product['quantity'] if hasattr(product, '__getitem__') else product.quantity
    
    if quantity == 0:
        return {'status': 'out_of_stock', 'text': 'Out of Stock', 'class': 'badge-danger'}
    elif quantity <= 5:
        return {'status': 'low_stock', 'text': f'Low Stock ({quantity} left)', 'class': 'badge-warning'}
    else:
        return {'status': 'in_stock', 'text': 'In Stock', 'class': 'badge-success'}

def format_time_ago(datetime_str):
    """Format datetime as time ago (e.g., '2 hours ago')"""
    if not datetime_str:
        return "Unknown"
    
    try:
        from datetime import datetime
        
        # Parse the datetime string
        if isinstance(datetime_str, str):
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        else:
            dt = datetime_str
        
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 2592000:  # 30 days
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            return dt.strftime("%b %d, %Y")
    
    except Exception as e:
        print(f"Format time ago error: {e}")
        return str(datetime_str)

def generate_slug(text):
    """Generate URL-friendly slug from text"""
    import re
    
    if not text:
        return ""
    
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    
    return slug

def validate_image_file(file):
    """Validate uploaded image file"""
    if not file or not file.filename:
        return False, "No file selected"
    
    if not allowed_file(file.filename):
        return False, f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size (5MB limit)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)     # Reset position
    
    if size > 5 * 1024 * 1024:  # 5MB
        return False, "File size too large. Maximum 5MB allowed."
    
    return True, None

def sanitize_search_query(query):
    """Sanitize search query to prevent SQL injection"""
    if not query:
        return ""
    
    # Remove special SQL characters but keep spaces and basic punctuation
    import re
    sanitized = re.sub(r'[;\'"\\%_]', '', query.strip())
    
    # Limit length
    return sanitized[:100]

def get_pagination_data(total_items, page=1, per_page=20):
    """Calculate pagination data"""
    try:
        page = int(page) if page else 1
        per_page = int(per_page) if per_page else 20
    except (ValueError, TypeError):
        page = 1
        per_page = 20
    
    if page < 1:
        page = 1
    
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    
    has_prev = page > 1
    has_next = page < total_pages
    
    return {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'offset': offset,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': page - 1 if has_prev else None,
        'next_num': page + 1 if has_next else None
    }