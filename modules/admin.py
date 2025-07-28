"""
Admin module for Farmer Connect
Handles admin-specific functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from modules.database import get_db_connection, get_setting, update_setting
from modules.utils import require_login, send_notification
from datetime import datetime, date

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@require_login(['admin'])
def dashboard():
    """Admin dashboard"""
    conn = get_db_connection()
    
    # Get overall platform stats
    stats = {}
    
    # Total users by type
    stats['total_farmers'] = conn.execute('''
        SELECT COUNT(*) FROM users WHERE user_type = 'farmer'
    ''').fetchone()[0]
    
    stats['total_consumers'] = conn.execute('''
        SELECT COUNT(*) FROM users WHERE user_type = 'consumer'
    ''').fetchone()[0]
    
    stats['pending_farmers'] = conn.execute('''
        SELECT COUNT(*) FROM users WHERE user_type = 'farmer' AND is_approved = 0
    ''').fetchone()[0]
    
    # Products
    stats['total_products'] = conn.execute('''
        SELECT COUNT(*) FROM products
    ''').fetchone()[0]
    
    stats['pending_products'] = conn.execute('''
        SELECT COUNT(*) FROM products WHERE is_approved = 0
    ''').fetchone()[0]
    
    stats['active_products'] = conn.execute('''
        SELECT COUNT(*) FROM products WHERE is_approved = 1 AND quantity > 0
    ''').fetchone()[0]
    
    # Orders
    stats['total_orders'] = conn.execute('''
        SELECT COUNT(*) FROM orders
    ''').fetchone()[0]
    
    stats['today_orders'] = conn.execute('''
        SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')
    ''').fetchone()[0]
    
    # Revenue
    stats['total_revenue'] = conn.execute('''
        SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE payment_status = 'paid'
    ''').fetchone()[0]
    
    stats['month_revenue'] = conn.execute('''
        SELECT COALESCE(SUM(total_amount), 0) FROM orders 
        WHERE payment_status = 'paid' 
        AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    ''').fetchone()[0]
    
    # Contact messages
    stats['unread_messages'] = conn.execute('''
        SELECT COUNT(*) FROM contact_messages WHERE status = 'unread'
    ''').fetchone()[0]
    
    stats['total_messages'] = conn.execute('''
        SELECT COUNT(*) FROM contact_messages
    ''').fetchone()[0]
    
    # Recent activities
    recent_orders = conn.execute('''
        SELECT o.*, u.full_name as consumer_name
        FROM orders o
        JOIN users u ON o.consumer_id = u.id
        ORDER BY o.created_at DESC
        LIMIT 5
    ''').fetchall()
    
    recent_farmers = conn.execute('''
        SELECT * FROM users 
        WHERE user_type = 'farmer'
        ORDER BY created_at DESC
        LIMIT 5
    ''').fetchall()
    
    recent_products = conn.execute('''
        SELECT p.*, u.farm_name
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        ORDER BY p.created_at DESC
        LIMIT 5
    ''').fetchall()
    
    # Monthly stats for charts
    monthly_stats_raw = conn.execute('''
        SELECT strftime('%Y-%m', created_at) as month,
               COUNT(CASE WHEN user_type = 'farmer' THEN 1 END) as farmers,
               COUNT(CASE WHEN user_type = 'consumer' THEN 1 END) as consumers
        FROM users
        WHERE created_at >= DATE('now', '-6 months')
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month
    ''').fetchall()
    
    # Convert Row objects to dictionaries for JSON serialization
    monthly_stats = [dict(row) for row in monthly_stats_raw]
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_orders=recent_orders,
                         recent_farmers=recent_farmers,
                         recent_products=recent_products,
                         monthly_stats=monthly_stats)

@admin_bp.route('/farmers')
@require_login(['admin'])
def farmers():
    """Manage farmers"""
    conn = get_db_connection()
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    search = request.args.get('search')
    
    # Build query
    query = "SELECT * FROM users WHERE user_type = 'farmer'"
    params = []
    
    if status == 'approved':
        query += ' AND is_approved = 1'
    elif status == 'pending':
        query += ' AND is_approved = 0'
    elif status == 'inactive':
        query += ' AND is_active = 0'
    
    if search:
        query += ' AND (full_name LIKE ? OR farm_name LIKE ? OR location LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    query += ' ORDER BY created_at DESC'
    
    farmers_list = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('admin/farmers.html',
                         farmers=farmers_list,
                         current_status=status,
                         current_search=search)

@admin_bp.route('/farmers/<int:farmer_id>')
@require_login(['admin'])
def farmer_detail(farmer_id):
    """Farmer detail page"""
    conn = get_db_connection()
    
    # Get farmer info
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (farmer_id,)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('admin.farmers'))
    
    # Get farmer's products
    products = conn.execute('''
        SELECT * FROM products WHERE farmer_id = ? ORDER BY created_at DESC
    ''', (farmer_id,)).fetchall()
    
    # Get farmer's orders
    orders = conn.execute('''
        SELECT DISTINCT o.*, COUNT(oi.id) as item_count
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
        LIMIT 10
    ''', (farmer_id,)).fetchall()
    
    # Get earnings
    earnings = conn.execute('''
        SELECT COALESCE(SUM(oi.subtotal), 0) as total_earnings
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.farmer_id = ? AND o.payment_status = 'paid'
    ''', (farmer_id,)).fetchone()['total_earnings']
    
    # Calculate farmer stats
    farmer_stats = {
        'total_products': len(products),
        'total_orders': len(orders)
    }
    
    conn.close()
    
    return render_template('admin/farmer_detail.html',
                         farmer=farmer,
                         products=products,
                         orders=orders,
                         earnings=earnings,
                         farmer_stats=farmer_stats)

@admin_bp.route('/farmers/approve/<int:farmer_id>', methods=['POST'])
@require_login(['admin'])
def approve_farmer(farmer_id):
    """Approve farmer account"""
    conn = get_db_connection()
    
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (farmer_id,)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('admin.farmers'))
    
    try:
        conn.execute('''
            UPDATE users 
            SET is_approved = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (farmer_id,))
        
        conn.commit()
        
        # Send notification to farmer
        send_notification(
            farmer_id,
            'Account Approved',
            'Congratulations! Your farmer account has been approved. You can now start selling your products.',
            'success',
            '/farmer/dashboard'
        )
        
        flash(f'Farmer "{farmer["full_name"]}" approved successfully!', 'success')
    
    except Exception as e:
        flash('Failed to approve farmer. Please try again.', 'error')
        print(f"Approve farmer error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.farmer_detail', farmer_id=farmer_id))

@admin_bp.route('/farmers/reject/<int:farmer_id>', methods=['POST'])
@require_login(['admin'])
def reject_farmer(farmer_id):
    """Reject/deactivate farmer account"""
    conn = get_db_connection()
    
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (farmer_id,)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('admin.farmers'))
    
    reason = request.form.get('reason', '').strip()
    
    try:
        conn.execute('''
            UPDATE users 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (farmer_id,))
        
        conn.commit()
        
        # Send notification to farmer
        message = 'Your farmer account has been deactivated.'
        if reason:
            message += f' Reason: {reason}'
        
        send_notification(
            farmer_id,
            'Account Deactivated',
            message,
            'warning',
            '/auth/profile'
        )
        
        flash(f'Farmer "{farmer["full_name"]}" deactivated successfully!', 'success')
    
    except Exception as e:
        flash('Failed to deactivate farmer. Please try again.', 'error')
        print(f"Reject farmer error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.farmer_detail', farmer_id=farmer_id))

@admin_bp.route('/farmers/activate/<int:farmer_id>', methods=['POST'])
@require_login(['admin'])
def activate_farmer(farmer_id):
    """Activate farmer account"""
    conn = get_db_connection()
    
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (farmer_id,)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('admin.farmers'))
    
    try:
        conn.execute('''
            UPDATE users 
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (farmer_id,))
        
        conn.commit()
        
        # Send notification to farmer
        send_notification(
            farmer_id,
            'Account Activated',
            'Your farmer account has been activated. You can now access all features.',
            'success',
            '/farmer/dashboard'
        )
        
        flash(f'Farmer "{farmer["full_name"]}" activated successfully!', 'success')
    
    except Exception as e:
        flash('Failed to activate farmer. Please try again.', 'error')
        print(f"Activate farmer error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.farmer_detail', farmer_id=farmer_id))

@admin_bp.route('/farmers/deactivate/<int:farmer_id>', methods=['POST'])
@require_login(['admin'])
def deactivate_farmer(farmer_id):
    """Deactivate farmer account"""
    conn = get_db_connection()
    
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (farmer_id,)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('admin.farmers'))
    
    reason = request.form.get('reason', '').strip()
    
    try:
        conn.execute('''
            UPDATE users 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (farmer_id,))
        
        conn.commit()
        
        # Send notification to farmer
        message = 'Your farmer account has been deactivated.'
        if reason:
            message += f' Reason: {reason}'
        
        send_notification(
            farmer_id,
            'Account Deactivated',
            message,
            'warning',
            '/auth/profile'
        )
        
        flash(f'Farmer "{farmer["full_name"]}" deactivated successfully!', 'success')
    
    except Exception as e:
        flash('Failed to deactivate farmer. Please try again.', 'error')
        print(f"Deactivate farmer error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.farmer_detail', farmer_id=farmer_id))

@admin_bp.route('/farmers/delete/<int:farmer_id>', methods=['DELETE', 'POST'])
@require_login(['admin'])
def delete_farmer(farmer_id):
    """Delete farmer account"""
    conn = get_db_connection()
    
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (farmer_id,)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('admin.farmers'))
    
    try:
        # Delete farmer's products first
        conn.execute('DELETE FROM products WHERE farmer_id = ?', (farmer_id,))
        
        # Delete farmer's order items
        conn.execute('DELETE FROM order_items WHERE farmer_id = ?', (farmer_id,))
        
        # Delete notifications
        conn.execute('DELETE FROM notifications WHERE user_id = ?', (farmer_id,))
        
        # Delete the farmer
        conn.execute('DELETE FROM users WHERE id = ?', (farmer_id,))
        
        conn.commit()
        flash(f'Farmer "{farmer["full_name"]}" deleted successfully!', 'success')
    
    except Exception as e:
        flash('Failed to delete farmer. Please try again.', 'error')
        print(f"Delete farmer error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.farmers'))

@admin_bp.route('/farmers/approve-all', methods=['POST'])
@require_login(['admin'])
def approve_all_farmers():
    """Approve all pending farmers"""
    conn = get_db_connection()
    
    try:
        # Get all pending farmers
        pending_farmers = conn.execute('''
            SELECT id, full_name FROM users 
            WHERE user_type = 'farmer' AND is_approved = 0
        ''').fetchall()
        
        if not pending_farmers:
            return jsonify({'success': False, 'message': 'No pending farmers found'})
        
        # Approve all pending farmers
        conn.execute('''
            UPDATE users 
            SET is_approved = 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_type = 'farmer' AND is_approved = 0
        ''')
        
        conn.commit()
        
        # Send notifications to all approved farmers
        for farmer in pending_farmers:
            send_notification(
                farmer['id'],
                'Account Approved',
                'Congratulations! Your farmer account has been approved. You can now start selling your products.',
                'success',
                '/farmer/dashboard'
            )
        
        return jsonify({
            'success': True, 
            'count': len(pending_farmers),
            'message': f'{len(pending_farmers)} farmers approved successfully'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to approve farmers'})
    
    finally:
        conn.close()

@admin_bp.route('/products')
@require_login(['admin'])
def products():
    """Manage products"""
    conn = get_db_connection()
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    category = request.args.get('category')
    search = request.args.get('search')
    
    # Build query
    query = '''
        SELECT p.*, u.farm_name, u.full_name as farmer_name
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if status == 'approved':
        query += ' AND p.is_approved = 1'
    elif status == 'pending':
        query += ' AND p.is_approved = 0'
    elif status == 'out_of_stock':
        query += ' AND p.quantity = 0'
    
    if category:
        query += ' AND p.category = ?'
        params.append(category)
    
    if search:
        query += ' AND (p.name LIKE ? OR p.description LIKE ? OR u.farm_name LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    query += ' ORDER BY p.created_at DESC'
    
    products_list = conn.execute(query, params).fetchall()
    
    # Get categories for filter
    categories = conn.execute('''
        SELECT DISTINCT category FROM products ORDER BY category
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin/products.html',
                         products=products_list,
                         categories=categories,
                         current_status=status,
                         current_category=category,
                         current_search=search)

@admin_bp.route('/products/approve/<int:product_id>', methods=['POST'])
@require_login(['admin'])
def approve_product(product_id):
    """Approve product"""
    conn = get_db_connection()
    
    product = conn.execute('''
        SELECT p.*, u.full_name as farmer_name
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE p.id = ?
    ''', (product_id,)).fetchone()
    
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('admin.products'))
    
    try:
        conn.execute('''
            UPDATE products 
            SET is_approved = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (product_id,))
        
        conn.commit()
        
        # Send notification to farmer
        send_notification(
            product['farmer_id'],
            'Product Approved',
            f'Your product "{product["name"]}" has been approved and is now live on the platform.',
            'success',
            f'/farmer/products'
        )
        
        flash(f'Product "{product["name"]}" approved successfully!', 'success')
    
    except Exception as e:
        flash('Failed to approve product. Please try again.', 'error')
        print(f"Approve product error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.products'))

@admin_bp.route('/products/reject/<int:product_id>', methods=['POST'])
@require_login(['admin'])
def reject_product(product_id):
    """Reject product"""
    conn = get_db_connection()
    
    product = conn.execute('''
        SELECT p.*, u.full_name as farmer_name
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE p.id = ?
    ''', (product_id,)).fetchone()
    
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('admin.products'))
    
    reason = request.form.get('reason', '').strip()
    
    try:
        conn.execute('''
            DELETE FROM products WHERE id = ?
        ''', (product_id,))
        
        conn.commit()
        
        # Send notification to farmer
        message = f'Your product "{product["name"]}" has been rejected.'
        if reason:
            message += f' Reason: {reason}'
        
        send_notification(
            product['farmer_id'],
            'Product Rejected',
            message,
            'warning',
            '/farmer/products'
        )
        
        flash(f'Product "{product["name"]}" rejected and removed!', 'success')
    
    except Exception as e:
        flash('Failed to reject product. Please try again.', 'error')
        print(f"Reject product error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.products'))

@admin_bp.route('/products/feature/<int:product_id>', methods=['POST'])
@require_login(['admin'])
def toggle_featured_product(product_id):
    """Toggle product featured status"""
    conn = get_db_connection()
    
    product = conn.execute('''
        SELECT * FROM products WHERE id = ?
    ''', (product_id,)).fetchone()
    
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})
    
    new_status = not product['is_featured']
    
    try:
        conn.execute('''
            UPDATE products 
            SET is_featured = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_status, product_id))
        
        conn.commit()
        
        status_text = 'featured' if new_status else 'unfeatured'
        return jsonify({
            'success': True,
            'message': f'Product {status_text} successfully',
            'is_featured': new_status
        })
    
    except Exception as e:
        print(f"Toggle featured error: {e}")
        return jsonify({'success': False, 'message': 'Failed to update product'})
    
    finally:
        conn.close()

# Enhanced Admin Features for Communication and Analytics

@admin_bp.route('/analytics')
@require_login(['admin'])
def analytics():
    """Advanced Analytics Dashboard"""
    conn = get_db_connection()
    
    # Overall platform stats
    stats = {}
    
    # User growth stats
    stats['total_users'] = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    stats['total_farmers'] = conn.execute('''
        SELECT COUNT(*) FROM users WHERE user_type = 'farmer'
    ''').fetchone()[0]
    stats['total_consumers'] = conn.execute('''
        SELECT COUNT(*) FROM users WHERE user_type = 'consumer'
    ''').fetchone()[0]
    stats['monthly_user_growth'] = conn.execute('''
        SELECT COUNT(*) FROM users 
        WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    ''').fetchone()[0]
    
    # Revenue analytics
    stats['total_revenue'] = conn.execute('''
        SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE payment_status = 'paid'
    ''').fetchone()[0]
    
    stats['monthly_revenue'] = conn.execute('''
        SELECT COALESCE(SUM(total_amount), 0) FROM orders 
        WHERE payment_status = 'paid' 
        AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    ''').fetchone()[0]
    
    # Top performing farmers
    top_farmers = conn.execute('''
        SELECT u.farm_name, u.full_name, 
               COUNT(DISTINCT oi.order_id) as total_orders,
               SUM(oi.subtotal) as total_earnings,
               AVG(fr.rating) as avg_rating
        FROM users u
        LEFT JOIN order_items oi ON u.id = oi.farmer_id
        LEFT JOIN orders o ON oi.order_id = o.id AND o.payment_status = 'paid'
        LEFT JOIN farmer_ratings fr ON u.id = fr.farmer_id
        WHERE u.user_type = 'farmer' AND u.is_approved = 1
        GROUP BY u.id
        ORDER BY total_earnings DESC NULLS LAST
        LIMIT 10
    ''').fetchall()
    
    # Top selling products
    top_products = conn.execute('''
        SELECT p.name, p.category, u.farm_name,
               SUM(oi.quantity) as total_sold,
               SUM(oi.subtotal) as revenue
        FROM products p
        JOIN order_items oi ON p.id = oi.product_id
        JOIN orders o ON oi.order_id = o.id
        JOIN users u ON p.farmer_id = u.id
        WHERE o.payment_status = 'paid'
        GROUP BY p.id
        ORDER BY revenue DESC
        LIMIT 10
    ''').fetchall()
    
    # Category performance
    category_stats = conn.execute('''
        SELECT p.category,
               COUNT(DISTINCT p.id) as product_count,
               COUNT(DISTINCT oi.order_id) as order_count,
               SUM(oi.subtotal) as revenue
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id AND o.payment_status = 'paid'
        GROUP BY p.category
        ORDER BY revenue DESC NULLS LAST
    ''').fetchall()
    
    # Monthly growth data for charts (last 12 months)
    monthly_data = conn.execute('''
        SELECT strftime('%Y-%m', created_at) as month,
               strftime('%m/%Y', created_at) as month_display,
               COUNT(CASE WHEN user_type = 'farmer' THEN 1 END) as farmers,
               COUNT(CASE WHEN user_type = 'consumer' THEN 1 END) as consumers
        FROM users
        WHERE created_at >= DATE('now', '-12 months')
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month
    ''').fetchall()
    
    # Revenue by month
    revenue_data = conn.execute('''
        SELECT strftime('%Y-%m', created_at) as month,
               strftime('%m/%Y', created_at) as month_display,
               SUM(total_amount) as revenue
        FROM orders
        WHERE payment_status = 'paid' 
        AND created_at >= DATE('now', '-12 months')
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month
    ''').fetchall()
    
    # Search analytics
    popular_searches = conn.execute('''
        SELECT query, COUNT(*) as search_count, AVG(results_count) as avg_results
        FROM search_history
        WHERE created_at >= DATE('now', '-30 days')
        GROUP BY query
        ORDER BY search_count DESC
        LIMIT 20
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin/analytics.html',
                         stats=stats,
                         top_farmers=top_farmers,
                         top_products=top_products,
                         category_stats=category_stats,
                         monthly_data=monthly_data,
                         revenue_data=revenue_data,
                         popular_searches=popular_searches)

@admin_bp.route('/communications/send-announcement', methods=['GET', 'POST'])
@require_login(['admin'])
def send_announcement():
    """Send announcement to users"""
    if request.method == 'POST':
        title = request.form['title'].strip()
        message = request.form['message'].strip()
        recipient_type = request.form['recipient_type']  # all, farmers, consumers
        priority = request.form.get('priority', 'normal')
        
        if not title or not message:
            flash('Title and message are required', 'error')
            return render_template('admin/send_announcement.html')
        
        conn = get_db_connection()
        
        try:
            # Get recipient users
            if recipient_type == 'farmers':
                recipients = conn.execute('''
                    SELECT id FROM users WHERE user_type = 'farmer' AND is_active = 1
                ''').fetchall()
            elif recipient_type == 'consumers':
                recipients = conn.execute('''
                    SELECT id FROM users WHERE user_type = 'consumer' AND is_active = 1
                ''').fetchall()
            else:  # all
                recipients = conn.execute('''
                    SELECT id FROM users WHERE user_type IN ('farmer', 'consumer') AND is_active = 1
                ''').fetchall()
            
            # Send notifications to all recipients
            for recipient in recipients:
                send_notification(
                    recipient['id'],
                    title,
                    message,
                    priority,
                    None
                )
            
            flash(f'Announcement sent to {len(recipients)} users successfully!', 'success')
            return redirect(url_for('admin.dashboard'))
        
        except Exception as e:
            flash('Failed to send announcement', 'error')
            print(f"Send announcement error: {e}")
        
        finally:
            conn.close()
    
    return render_template('admin/send_announcement.html')

@admin_bp.route('/promotions')
@require_login(['admin'])
def promotions():
    """Manage promotions and discounts"""
    conn = get_db_connection()
    
    # Get all promotions
    promotions_list = conn.execute('''
        SELECT * FROM promotions 
        ORDER BY created_at DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin/promotions.html', promotions=promotions_list)

@admin_bp.route('/promotions/add', methods=['GET', 'POST'])
@require_login(['admin'])
def add_promotion():
    """Add new promotion"""
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form.get('description', '').strip()
        discount_type = request.form['discount_type']
        discount_value = float(request.form['discount_value'])
        min_order_amount = float(request.form.get('min_order_amount', 0))
        promo_code = request.form.get('promo_code', '').strip().upper()
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        usage_limit = request.form.get('usage_limit')
        
        # Validation
        errors = []
        if not title:
            errors.append("Title is required")
        if discount_value <= 0:
            errors.append("Discount value must be greater than 0")
        if discount_type == 'percentage' and discount_value > 100:
            errors.append("Percentage discount cannot exceed 100%")
        
        try:
            from datetime import datetime
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            if end <= start:
                errors.append("End date must be after start date")
        except ValueError:
            errors.append("Invalid date format")
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            conn = get_db_connection()
            try:
                conn.execute('''
                    INSERT INTO promotions (
                        title, description, discount_type, discount_value,
                        min_order_amount, promo_code, start_date, end_date, usage_limit
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (title, description, discount_type, discount_value,
                      min_order_amount, promo_code, start_date, end_date, 
                      int(usage_limit) if usage_limit else None))
                
                conn.commit()
                flash('Promotion added successfully!', 'success')
                return redirect(url_for('admin.promotions'))
            
            except Exception as e:
                flash('Failed to add promotion', 'error')
                print(f"Add promotion error: {e}")
            
            finally:
                conn.close()
    
    return render_template('admin/add_promotion.html')

@admin_bp.route('/promotions/toggle/<int:promotion_id>', methods=['POST'])
@require_login(['admin'])
def toggle_promotion(promotion_id):
    """Toggle promotion active status"""
    conn = get_db_connection()
    
    try:
        promotion = conn.execute('''
            SELECT * FROM promotions WHERE id = ?
        ''', (promotion_id,)).fetchone()
        
        if not promotion:
            return jsonify({'success': False, 'message': 'Promotion not found'})
        
        new_status = not promotion['is_active']
        
        conn.execute('''
            UPDATE promotions 
            SET is_active = ?
            WHERE id = ?
        ''', (new_status, promotion_id))
        
        conn.commit()
        
        status_text = 'activated' if new_status else 'deactivated'
        return jsonify({
            'success': True,
            'message': f'Promotion {status_text} successfully',
            'is_active': new_status
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to update promotion'})
    
    finally:
        conn.close()

@admin_bp.route('/reports')
@require_login(['admin'])
def reports():
    """Reports and data export"""
    conn = get_db_connection()
    
    # Summary stats for report generation
    report_stats = {
        'total_farmers': conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "farmer"').fetchone()[0],
        'total_consumers': conn.execute('SELECT COUNT(*) FROM users WHERE user_type = "consumer"').fetchone()[0],
        'total_products': conn.execute('SELECT COUNT(*) FROM products').fetchone()[0],
        'total_orders': conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0],
        'total_revenue': conn.execute('SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE payment_status = "paid"').fetchone()[0]
    }
    
    conn.close()
    
    return render_template('admin/reports.html', report_stats=report_stats)

@admin_bp.route('/api/reports/export/<report_type>/<format>')
@require_login(['admin'])
def export_report(report_type, format):
    """Export reports in various formats"""
    import csv
    from io import StringIO
    from flask import make_response
    
    conn = get_db_connection()
    
    try:
        if report_type == 'users':
            data = conn.execute('''
                SELECT id, username, email, user_type, full_name, phone, location,
                       farm_name, is_approved, is_active, created_at
                FROM users
                WHERE user_type IN ('farmer', 'consumer')
                ORDER BY created_at DESC
            ''').fetchall()
            
            headers = ['ID', 'Username', 'Email', 'User Type', 'Full Name', 'Phone', 
                      'Location', 'Farm Name', 'Approved', 'Active', 'Created At']
        
        elif report_type == 'orders':
            data = conn.execute('''
                SELECT o.id, o.order_number, o.total_amount, o.status, o.payment_status,
                       o.created_at, u.full_name as consumer_name, u.email as consumer_email
                FROM orders o
                JOIN users u ON o.consumer_id = u.id
                ORDER BY o.created_at DESC
            ''').fetchall()
            
            headers = ['ID', 'Order Number', 'Total Amount', 'Status', 'Payment Status',
                      'Created At', 'Consumer Name', 'Consumer Email']
        
        elif report_type == 'products':
            data = conn.execute('''
                SELECT p.id, p.name, p.category, p.price, p.unit, p.quantity,
                       p.is_approved, p.created_at, u.farm_name, u.full_name as farmer_name
                FROM products p
                JOIN users u ON p.farmer_id = u.id
                ORDER BY p.created_at DESC
            ''').fetchall()
            
            headers = ['ID', 'Name', 'Category', 'Price', 'Unit', 'Quantity',
                      'Approved', 'Created At', 'Farm Name', 'Farmer Name']
        
        elif report_type == 'revenue':
            data = conn.execute('''
                SELECT strftime('%Y-%m', o.created_at) as month,
                       COUNT(*) as order_count,
                       SUM(o.total_amount) as total_revenue,
                       AVG(o.total_amount) as avg_order_value
                FROM orders o
                WHERE o.payment_status = 'paid'
                GROUP BY strftime('%Y-%m', o.created_at)
                ORDER BY month DESC
            ''').fetchall()
            
            headers = ['Month', 'Order Count', 'Total Revenue', 'Average Order Value']
        
        else:
            return jsonify({'error': 'Invalid report type'})
        
        if format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(headers)
            
            # Write data
            for row in data:
                writer.writerow(row)
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report.csv'
            return response
        
        else:
            return jsonify({'error': 'Format not supported'})
    
    except Exception as e:
        print(f"Export report error: {e}")
        return jsonify({'error': 'Failed to generate report'})
    
    finally:
        conn.close()

@admin_bp.route('/consumers')
@require_login(['admin'])
def consumers():
    """Manage consumers"""
    conn = get_db_connection()
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    search = request.args.get('search')
    
    # Build query
    query = 'SELECT * FROM users WHERE user_type = "consumer"'
    params = []
    
    if status == 'active':
        query += ' AND is_active = 1'
    elif status == 'inactive':
        query += ' AND is_active = 0'
    
    if search:
        query += ' AND (full_name LIKE ? OR email LIKE ? OR phone LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    query += ' ORDER BY created_at DESC'
    
    consumers_list = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('admin/consumers.html',
                         consumers=consumers_list,
                         current_status=status,
                         current_search=search)

@admin_bp.route('/site-settings', methods=['GET', 'POST'])
@require_login(['admin'])
def site_settings():
    """Manage site settings"""
    if request.method == 'POST':
        settings_data = {
            'site_name': request.form.get('site_name', ''),
            'site_description': request.form.get('site_description', ''),
            'contact_email': request.form.get('contact_email', ''),
            'contact_phone': request.form.get('contact_phone', ''),
            'delivery_charge': request.form.get('delivery_charge', '0'),
            'free_delivery_above': request.form.get('free_delivery_above', '0'),
            'commission_rate': request.form.get('commission_rate', '0')
        }
        
        try:
            for key, value in settings_data.items():
                update_setting(key, value)
            
            flash('Site settings updated successfully!', 'success')
        except Exception as e:
            flash('Failed to update settings', 'error')
            print(f"Update settings error: {e}")
    
    # Get current settings
    current_settings = {}
    settings_keys = ['site_name', 'site_description', 'contact_email', 'contact_phone',
                    'delivery_charge', 'free_delivery_above', 'commission_rate']
    
    for key in settings_keys:
        current_settings[key] = get_setting(key, '')
    
    return render_template('admin/site_settings.html', settings=current_settings)

@admin_bp.route('/orders')
@require_login(['admin'])
def orders():
    """Manage orders"""
    conn = get_db_connection()
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    payment_status = request.args.get('payment_status', 'all')
    search = request.args.get('search')
    
    # Build query
    query = '''
        SELECT o.*, u.full_name as consumer_name
        FROM orders o
        JOIN users u ON o.consumer_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if status != 'all':
        query += ' AND o.status = ?'
        params.append(status)
    
    if payment_status != 'all':
        query += ' AND o.payment_status = ?'
        params.append(payment_status)
    
    if search:
        query += ' AND (o.order_number LIKE ? OR u.full_name LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += ' ORDER BY o.created_at DESC'
    
    orders_list = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('admin/orders.html',
                         orders=orders_list,
                         current_status=status,
                         current_payment_status=payment_status,
                         current_search=search)

@admin_bp.route('/orders/<int:order_id>')
@require_login(['admin'])
def order_detail(order_id):
    """Order detail page"""
    conn = get_db_connection()
    
    # Get order with consumer info
    order = conn.execute('''
        SELECT o.*, u.full_name as consumer_name, u.email as consumer_email, u.phone as consumer_phone
        FROM orders o
        JOIN users u ON o.consumer_id = u.id
        WHERE o.id = ?
    ''', (order_id,)).fetchone()
    
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('admin.orders'))
    
    # Get order items with product and farmer info
    order_items = conn.execute('''
        SELECT oi.*, p.name as product_name, p.unit, p.image,
               u.farm_name, u.full_name as farmer_name, u.phone as farmer_phone
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON oi.farmer_id = u.id
        WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    
    conn.close()
    
    return render_template('admin/order_detail.html',
                         order=order,
                         order_items=order_items)

@admin_bp.route('/categories')
@require_login(['admin'])
def categories():
    """Manage categories"""
    conn = get_db_connection()
    
    categories_list = conn.execute('''
        SELECT c.*, COUNT(p.id) as product_count
        FROM categories c
        LEFT JOIN products p ON c.name = p.category
        GROUP BY c.id
        ORDER BY c.name
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin/categories.html', categories=categories_list)

@admin_bp.route('/categories/add', methods=['POST'])
@require_login(['admin'])
def add_category():
    """Add new category"""
    name = request.form['name'].strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Category name is required!', 'error')
        return redirect(url_for('admin.categories'))
    
    conn = get_db_connection()
    
    try:
        conn.execute('''
            INSERT INTO categories (name, description)
            VALUES (?, ?)
        ''', (name, description))
        
        conn.commit()
        flash('Category added successfully!', 'success')
    
    except Exception as e:
        flash('Failed to add category. It may already exist.', 'error')
        print(f"Add category error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.categories'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@require_login(['admin'])
def settings():
    """Site settings"""
    if request.method == 'POST':
        # Update settings
        settings_to_update = [
            'site_name', 'site_description', 'contact_email', 'contact_phone',
            'delivery_charge', 'free_delivery_above', 'commission_rate'
        ]
        
        try:
            for setting in settings_to_update:
                value = request.form.get(setting, '').strip()
                if value:
                    update_setting(setting, value)
            
            flash('Settings updated successfully!', 'success')
        
        except Exception as e:
            flash('Failed to update settings. Please try again.', 'error')
            print(f"Settings update error: {e}")
        
        return redirect(url_for('admin.settings'))
    
    # Get current settings
    settings_data = {}
    settings_keys = [
        'site_name', 'site_description', 'contact_email', 'contact_phone',
        'delivery_charge', 'free_delivery_above', 'commission_rate'
    ]
    
    for key in settings_keys:
        settings_data[key] = get_setting(key, '')
    
    return render_template('admin/settings.html', settings=settings_data)

@admin_bp.route('/contact-messages')
@require_login(['admin'])
def contact_messages():
    """View and manage contact messages"""
    conn = get_db_connection()
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    
    # Build query
    query = '''
        SELECT cm.*, u.full_name as replied_by_name
        FROM contact_messages cm
        LEFT JOIN users u ON cm.replied_by = u.id
        WHERE 1=1
    '''
    params = []
    
    if status != 'all':
        query += ' AND cm.status = ?'
        params.append(status)
    
    if search:
        query += ' AND (cm.name LIKE ? OR cm.email LIKE ? OR cm.subject LIKE ? OR cm.message LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param, search_param])
    
    query += ' ORDER BY cm.created_at DESC'
    
    messages = conn.execute(query, params).fetchall()
    
    # Get message counts by status
    message_counts = {
        'total': conn.execute('SELECT COUNT(*) FROM contact_messages').fetchone()[0],
        'unread': conn.execute('SELECT COUNT(*) FROM contact_messages WHERE status = "unread"').fetchone()[0],
        'read': conn.execute('SELECT COUNT(*) FROM contact_messages WHERE status = "read"').fetchone()[0],
        'replied': conn.execute('SELECT COUNT(*) FROM contact_messages WHERE status = "replied"').fetchone()[0]
    }
    
    conn.close()
    
    return render_template('admin/contact_messages.html',
                         messages=messages,
                         message_counts=message_counts,
                         current_status=status,
                         current_search=search)

@admin_bp.route('/contact-messages/<int:message_id>')
@require_login(['admin'])
def contact_message_detail(message_id):
    """View contact message details"""
    conn = get_db_connection()
    
    message = conn.execute('''
        SELECT cm.*, u.full_name as replied_by_name
        FROM contact_messages cm
        LEFT JOIN users u ON cm.replied_by = u.id
        WHERE cm.id = ?
    ''', (message_id,)).fetchone()
    
    if not message:
        flash('Message not found!', 'error')
        return redirect(url_for('admin.contact_messages'))
    
    # Mark as read if it's unread
    if message['status'] == 'unread':
        conn.execute('''
            UPDATE contact_messages 
            SET status = 'read' 
            WHERE id = ?
        ''', (message_id,))
        conn.commit()
    
    conn.close()
    
    return render_template('admin/contact_message_detail.html', message=message)

@admin_bp.route('/contact-messages/<int:message_id>/reply', methods=['POST'])
@require_login(['admin'])
def reply_contact_message(message_id):
    """Reply to contact message"""
    reply_text = request.form.get('reply', '').strip()
    
    if not reply_text:
        flash('Reply message is required!', 'error')
        return redirect(url_for('admin.contact_message_detail', message_id=message_id))
    
    conn = get_db_connection()
    
    try:
        # Update the message with reply
        conn.execute('''
            UPDATE contact_messages 
            SET admin_reply = ?, replied_by = ?, replied_at = CURRENT_TIMESTAMP, status = 'replied'
            WHERE id = ?
        ''', (reply_text, session['user_id'], message_id))
        
        conn.commit()
        flash('Reply sent successfully!', 'success')
        
    except Exception as e:
        flash('Failed to send reply. Please try again.', 'error')
        print(f"Reply error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.contact_message_detail', message_id=message_id))

@admin_bp.route('/contact-messages/<int:message_id>/mark-read', methods=['POST'])
@require_login(['admin'])
def mark_message_read(message_id):
    """Mark message as read"""
    conn = get_db_connection()
    
    try:
        conn.execute('''
            UPDATE contact_messages 
            SET status = 'read' 
            WHERE id = ?
        ''', (message_id,))
        
        conn.commit()
        
    except Exception as e:
        print(f"Mark read error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.contact_messages'))

@admin_bp.route('/contact-messages/<int:message_id>/delete', methods=['POST'])
@require_login(['admin'])
def delete_contact_message(message_id):
    """Delete contact message"""
    conn = get_db_connection()
    
    try:
        conn.execute('DELETE FROM contact_messages WHERE id = ?', (message_id,))
        conn.commit()
        flash('Message deleted successfully!', 'success')
        
    except Exception as e:
        flash('Failed to delete message. Please try again.', 'error')
        print(f"Delete message error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('admin.contact_messages'))

