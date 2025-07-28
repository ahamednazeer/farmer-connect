"""
Consumer module for Farmer Connect
Handles consumer-specific functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from modules.database import get_db_connection
from modules.utils import require_login, generate_order_number, calculate_delivery_charge, send_notification
from datetime import datetime, date

consumer_bp = Blueprint('consumer', __name__)

@consumer_bp.route('/dashboard')
@require_login(['consumer'])
def dashboard():
    """Consumer dashboard"""
    conn = get_db_connection()
    
    # Get consumer stats
    stats = {}
    
    # Total orders
    stats['total_orders'] = conn.execute('''
        SELECT COUNT(*) FROM orders WHERE consumer_id = ?
    ''', (session['user_id'],)).fetchone()[0]
    
    # Total spent
    stats['total_spent'] = conn.execute('''
        SELECT COALESCE(SUM(total_amount), 0) FROM orders 
        WHERE consumer_id = ? AND payment_status = 'paid'
    ''', (session['user_id'],)).fetchone()[0]
    
    # Pending orders
    stats['pending_orders'] = conn.execute('''
        SELECT COUNT(*) FROM orders 
        WHERE consumer_id = ? AND status IN ('pending', 'confirmed', 'processing')
    ''', (session['user_id'],)).fetchone()[0]
    
    # Cart items
    stats['cart_items'] = conn.execute('''
        SELECT COUNT(*) FROM cart_items WHERE user_id = ?
    ''', (session['user_id'],)).fetchone()[0]
    
    # Recent orders
    recent_orders = conn.execute('''
        SELECT * FROM orders 
        WHERE consumer_id = ?
        ORDER BY created_at DESC
        LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    # Recommended products (based on previous purchases)
    recommended_products = conn.execute('''
        SELECT DISTINCT p.*, u.farm_name, u.location
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE p.is_approved = 1 AND p.quantity > 0
        AND p.category IN (
            SELECT DISTINCT p2.category FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p2 ON oi.product_id = p2.id
            WHERE o.consumer_id = ?
        )
        ORDER BY p.created_at DESC
        LIMIT 6
    ''', (session['user_id'],)).fetchall()
    
    # If no recommendations, show featured products
    if not recommended_products:
        recommended_products = conn.execute('''
            SELECT p.*, u.farm_name, u.location
            FROM products p
            JOIN users u ON p.farmer_id = u.id
            WHERE p.is_approved = 1 AND p.quantity > 0 AND p.is_featured = 1
            ORDER BY p.created_at DESC
            LIMIT 6
        ''').fetchall()
    
    conn.close()
    
    return render_template('consumer/dashboard.html',
                         stats=stats,
                         recent_orders=recent_orders,
                         recommended_products=recommended_products)

@consumer_bp.route('/cart')
@require_login(['consumer'])
def cart():
    """Shopping cart"""
    conn = get_db_connection()
    
    # Get cart items
    cart_items = conn.execute('''
        SELECT ci.*, p.name, p.price, p.unit, p.image, p.quantity as stock,
               u.farm_name, u.location, (ci.quantity * p.price) as subtotal
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        JOIN users u ON p.farmer_id = u.id
        WHERE ci.user_id = ? AND p.is_approved = 1
        ORDER BY ci.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    # Calculate totals
    subtotal = sum(float(item['subtotal']) for item in cart_items)
    delivery_charge = calculate_delivery_charge(subtotal)
    total = subtotal + delivery_charge
    
    conn.close()
    
    return render_template('consumer/cart.html',
                         cart_items=cart_items,
                         subtotal=subtotal,
                         delivery_charge=delivery_charge,
                         total=total)

@consumer_bp.route('/api/cart/update', methods=['POST'])
@require_login(['consumer'])
def update_cart():
    """Update cart item quantity (AJAX)"""
    data = request.get_json()
    cart_item_id = data.get('cart_item_id')
    quantity = int(data.get('quantity', 1))
    
    if quantity <= 0:
        return jsonify({'success': False, 'message': 'Quantity must be greater than 0'})
    
    conn = get_db_connection()
    
    # Get cart item with product stock info
    cart_item = conn.execute('''
        SELECT ci.*, p.quantity as stock
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.id = ? AND ci.user_id = ?
    ''', (cart_item_id, session['user_id'])).fetchone()
    
    if not cart_item:
        return jsonify({'success': False, 'message': 'Cart item not found'})
    
    if quantity > cart_item['stock']:
        return jsonify({'success': False, 'message': 'Not enough stock available'})
    
    try:
        conn.execute('''
            UPDATE cart_items 
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        ''', (quantity, cart_item_id, session['user_id']))
        
        conn.commit()
        
        # Get updated cart totals
        cart_items = conn.execute('''
            SELECT ci.quantity * p.price as subtotal
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = ?
        ''', (session['user_id'],)).fetchall()
        
        subtotal = sum(float(item['subtotal']) for item in cart_items)
        delivery_charge = calculate_delivery_charge(subtotal)
        total = subtotal + delivery_charge
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Cart updated successfully',
            'subtotal': subtotal,
            'delivery_charge': delivery_charge,
            'total': total
        })
    
    except Exception as e:
        print(f"Cart update error: {e}")
        return jsonify({'success': False, 'message': 'Failed to update cart'})

@consumer_bp.route('/api/cart/remove', methods=['POST'])
@require_login(['consumer'])
def remove_from_cart():
    """Remove item from cart (AJAX)"""
    data = request.get_json()
    cart_item_id = data.get('cart_item_id')
    
    conn = get_db_connection()
    
    try:
        conn.execute('''
            DELETE FROM cart_items 
            WHERE id = ? AND user_id = ?
        ''', (cart_item_id, session['user_id']))
        
        conn.commit()
        
        # Get updated cart count and totals
        cart_count = conn.execute('''
            SELECT SUM(quantity) FROM cart_items WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()[0] or 0
        
        cart_items = conn.execute('''
            SELECT ci.quantity * p.price as subtotal
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = ?
        ''', (session['user_id'],)).fetchall()
        
        subtotal = sum(float(item['subtotal']) for item in cart_items)
        delivery_charge = calculate_delivery_charge(subtotal)
        total = subtotal + delivery_charge
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Item removed from cart',
            'cart_count': cart_count,
            'subtotal': subtotal,
            'delivery_charge': delivery_charge,
            'total': total
        })
    
    except Exception as e:
        print(f"Cart remove error: {e}")
        return jsonify({'success': False, 'message': 'Failed to remove item'})

@consumer_bp.route('/checkout', methods=['GET', 'POST'])
@require_login(['consumer'])
def checkout():
    """Checkout process"""
    conn = get_db_connection()
    
    # Get cart items
    cart_items = conn.execute('''
        SELECT ci.*, p.name, p.price, p.unit, p.quantity as stock, p.farmer_id, p.image,
               u.farm_name, (ci.quantity * p.price) as subtotal
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        JOIN users u ON p.farmer_id = u.id
        WHERE ci.user_id = ? AND p.is_approved = 1
        ORDER BY ci.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    if not cart_items:
        flash('Your cart is empty!', 'error')
        return redirect(url_for('consumer.cart'))
    
    # Check stock availability
    for item in cart_items:
        if item['quantity'] > item['stock']:
            flash(f'Not enough stock for {item["name"]}. Available: {item["stock"]}', 'error')
            return redirect(url_for('consumer.cart'))
    
    # Calculate totals
    subtotal = sum(float(item['subtotal']) for item in cart_items)
    delivery_charge = calculate_delivery_charge(subtotal)
    total = subtotal + delivery_charge
    
    if request.method == 'POST':
        # Get form data
        delivery_address = request.form['delivery_address'].strip()
        delivery_phone = request.form['delivery_phone'].strip()
        delivery_type = request.form['delivery_type']
        delivery_date = request.form.get('delivery_date')
        payment_method = request.form['payment_method']
        notes = request.form.get('notes', '').strip()
        
        # Validation
        errors = []
        
        if not delivery_address:
            errors.append("Delivery address is required")
        
        if not delivery_phone:
            errors.append("Delivery phone is required")
        
        if delivery_type not in ['delivery', 'pickup']:
            errors.append("Please select a valid delivery type")
        
        if delivery_date:
            try:
                delivery_date = datetime.strptime(delivery_date, '%Y-%m-%d').date()
                if delivery_date < date.today():
                    errors.append("Delivery date cannot be in the past")
            except ValueError:
                errors.append("Invalid delivery date")
        
        if payment_method not in ['cod', 'online', 'upi']:
            errors.append("Please select a valid payment method")
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            # Create order
            order_number = generate_order_number()
            
            try:
                # Insert order
                cursor = conn.execute('''
                    INSERT INTO orders (
                        order_number, consumer_id, total_amount, delivery_address,
                        delivery_phone, delivery_type, delivery_date, payment_method, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (order_number, session['user_id'], total, delivery_address,
                      delivery_phone, delivery_type, delivery_date, payment_method, notes))
                
                order_id = cursor.lastrowid
                
                # Insert order items and update product quantities
                for item in cart_items:
                    # Insert order item
                    conn.execute('''
                        INSERT INTO order_items (
                            order_id, product_id, farmer_id, quantity, price, subtotal
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (order_id, item['product_id'], item['farmer_id'],
                          item['quantity'], item['price'], item['subtotal']))
                    
                    # Update product quantity
                    conn.execute('''
                        UPDATE products 
                        SET quantity = quantity - ?
                        WHERE id = ?
                    ''', (item['quantity'], item['product_id']))
                    
                    # Send notification to farmer
                    send_notification(
                        item['farmer_id'],
                        'New Order Received',
                        f'You have received a new order for {item["name"]}',
                        'order',
                        f'/farmer/orders/{order_id}',
                        conn
                    )
                
                # Clear cart
                conn.execute('DELETE FROM cart_items WHERE user_id = ?', (session['user_id'],))
                
                conn.commit()
                
                flash(f'Order placed successfully! Order number: {order_number}', 'success')
                return redirect(url_for('consumer.orders'))
            
            except Exception as e:
                conn.rollback()
                flash('Failed to place order. Please try again.', 'error')
                print(f"Checkout error: {e}")
                import traceback
                traceback.print_exc()
    
    # Get user info for pre-filling form
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template('consumer/checkout.html',
                         cart_items=cart_items,
                         subtotal=subtotal,
                         delivery_charge=delivery_charge,
                         total=total,
                         user=user)

@consumer_bp.route('/orders')
@require_login(['consumer'])
def orders():
    """Consumer orders list"""
    conn = get_db_connection()
    
    # Get filter parameter
    status = request.args.get('status', 'all')
    
    # Build query
    query = 'SELECT * FROM orders WHERE consumer_id = ?'
    params = [session['user_id']]
    
    if status != 'all':
        query += ' AND status = ?'
        params.append(status)
    
    query += ' ORDER BY created_at DESC'
    
    orders_list = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('consumer/orders.html',
                         orders=orders_list,
                         current_status=status)

@consumer_bp.route('/orders/<int:order_id>')
@require_login(['consumer'])
def order_detail(order_id):
    """Order detail page"""
    conn = get_db_connection()
    
    # Get order
    order = conn.execute('''
        SELECT * FROM orders WHERE id = ? AND consumer_id = ?
    ''', (order_id, session['user_id'])).fetchone()
    
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('consumer.orders'))
    
    # Get order items with product and farmer info
    order_items = conn.execute('''
        SELECT oi.*, p.name as product_name, p.unit, p.image,
               u.farm_name, u.phone as farmer_phone
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON oi.farmer_id = u.id
        WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    
    conn.close()
    
    return render_template('consumer/order_detail.html',
                         order=order,
                         order_items=order_items)



@consumer_bp.route('/reviews')
@require_login(['consumer'])
def reviews():
    """Consumer reviews"""
    conn = get_db_connection()
    
    # Get user's reviews
    reviews_list = conn.execute('''
        SELECT r.*, p.name as product_name, p.image as product_image,
               u.farm_name
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        JOIN users u ON p.farmer_id = u.id
        WHERE r.consumer_id = ?
        ORDER BY r.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('consumer/reviews.html', reviews=reviews_list)

@consumer_bp.route('/reviews/add/<int:product_id>', methods=['GET', 'POST'])
@require_login(['consumer'])
def add_review(product_id):
    """Add product review"""
    conn = get_db_connection()
    
    # Check if user has purchased this product
    has_purchased = conn.execute('''
        SELECT COUNT(*) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.consumer_id = ? AND oi.product_id = ? AND o.payment_status = 'paid'
    ''', (session['user_id'], product_id)).fetchone()[0]
    
    if not has_purchased:
        flash('You can only review products you have purchased!', 'error')
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Check if already reviewed
    existing_review = conn.execute('''
        SELECT id FROM reviews WHERE consumer_id = ? AND product_id = ?
    ''', (session['user_id'], product_id)).fetchone()
    
    if existing_review:
        flash('You have already reviewed this product!', 'info')
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Get product info
    product = conn.execute('''
        SELECT p.*, u.farm_name
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE p.id = ?
    ''', (product_id,)).fetchone()
    
    if not product:
        flash('Product not found!', 'error')
        return redirect(url_for('products'))
    
    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form.get('comment', '').strip()
        
        if rating < 1 or rating > 5:
            flash('Please select a rating between 1 and 5!', 'error')
        else:
            try:
                conn.execute('''
                    INSERT INTO reviews (product_id, consumer_id, rating, comment)
                    VALUES (?, ?, ?, ?)
                ''', (product_id, session['user_id'], rating, comment))
                
                conn.commit()
                flash('Review added successfully!', 'success')
                return redirect(url_for('product_detail', product_id=product_id))
            
            except Exception as e:
                flash('Failed to add review. Please try again.', 'error')
                print(f"Add review error: {e}")
    
    conn.close()
    return render_template('consumer/add_review.html', product=product)

# Enhanced Consumer Features

@consumer_bp.route('/api/wishlist/add', methods=['POST'])
@require_login(['consumer'])
def add_to_wishlist():
    """Add product to wishlist"""
    data = request.get_json()
    product_id = data.get('product_id')
    
    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'})
    
    conn = get_db_connection()
    
    # Check if product exists
    product = conn.execute('SELECT id FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})
    
    try:
        conn.execute('''
            INSERT OR IGNORE INTO wishlists (user_id, product_id)
            VALUES (?, ?)
        ''', (session['user_id'], product_id))
        
        conn.commit()
        
        # Get wishlist count
        wishlist_count = conn.execute('''
            SELECT COUNT(*) FROM wishlists WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Added to wishlist',
            'wishlist_count': wishlist_count
        })
    
    except Exception as e:
        print(f"Wishlist add error: {e}")
        return jsonify({'success': False, 'message': 'Failed to add to wishlist'})

@consumer_bp.route('/api/wishlist/remove', methods=['POST'])
@require_login(['consumer'])
def remove_from_wishlist():
    """Remove product from wishlist"""
    data = request.get_json()
    product_id = data.get('product_id')
    
    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'})
    
    conn = get_db_connection()
    
    try:
        conn.execute('''
            DELETE FROM wishlists WHERE user_id = ? AND product_id = ?
        ''', (session['user_id'], product_id))
        
        conn.commit()
        
        # Get wishlist count
        wishlist_count = conn.execute('''
            SELECT COUNT(*) FROM wishlists WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Removed from wishlist',
            'wishlist_count': wishlist_count
        })
    
    except Exception as e:
        print(f"Wishlist remove error: {e}")
        return jsonify({'success': False, 'message': 'Failed to remove from wishlist'})

@consumer_bp.route('/wishlist')
@require_login(['consumer'])
def wishlist():
    """Consumer wishlist page"""
    conn = get_db_connection()
    
    # Get wishlist items
    wishlist_items = conn.execute('''
        SELECT w.*, p.name, p.price, p.unit, p.image, p.quantity as stock,
               u.farm_name, u.location
        FROM wishlists w
        JOIN products p ON w.product_id = p.id
        JOIN users u ON p.farmer_id = u.id
        WHERE w.user_id = ? AND p.is_approved = 1
        ORDER BY w.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('consumer/wishlist.html', wishlist_items=wishlist_items)

@consumer_bp.route('/orders/<int:order_id>/track')
@require_login(['consumer'])
def track_order(order_id):
    """Order tracking page"""
    conn = get_db_connection()
    
    # Get order
    order = conn.execute('''
        SELECT * FROM orders WHERE id = ? AND consumer_id = ?
    ''', (order_id, session['user_id'])).fetchone()
    
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('consumer.orders'))
    
    # Get tracking history
    tracking_history = conn.execute('''
        SELECT ot.*, u.full_name as updated_by_name
        FROM order_tracking ot
        LEFT JOIN users u ON ot.updated_by = u.id
        WHERE ot.order_id = ?
        ORDER BY ot.created_at DESC
    ''', (order_id,)).fetchall()
    
    # Get order items
    order_items = conn.execute('''
        SELECT oi.*, p.name as product_name, u.farm_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON oi.farmer_id = u.id
        WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    
    conn.close()
    
    return render_template('consumer/track_order.html',
                         order=order,
                         tracking_history=tracking_history,
                         order_items=order_items)

@consumer_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@require_login(['consumer'])
def cancel_order(order_id):
    """Cancel order"""
    conn = get_db_connection()
    
    # Get order
    order = conn.execute('''
        SELECT * FROM orders WHERE id = ? AND consumer_id = ?
    ''', (order_id, session['user_id'])).fetchone()
    
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('consumer.orders'))
    
    # Check if order can be cancelled
    if order['status'] not in ['pending', 'confirmed']:
        flash('Order cannot be cancelled at this stage!', 'error')
        return redirect(url_for('consumer.order_detail', order_id=order_id))
    
    try:
        # Update order status
        conn.execute('''
            UPDATE orders 
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (order_id,))
        
        # Restore product quantities
        order_items = conn.execute('''
            SELECT product_id, quantity FROM order_items WHERE order_id = ?
        ''', (order_id,)).fetchall()
        
        for item in order_items:
            conn.execute('''
                UPDATE products 
                SET quantity = quantity + ?
                WHERE id = ?
            ''', (item['quantity'], item['product_id']))
        
        # Add tracking entry
        conn.execute('''
            INSERT INTO order_tracking (order_id, status, message, updated_by)
            VALUES (?, 'cancelled', 'Order cancelled by customer', ?)
        ''', (order_id, session['user_id']))
        
        # Notify farmers
        farmers = conn.execute('''
            SELECT DISTINCT farmer_id FROM order_items WHERE order_id = ?
        ''', (order_id,)).fetchall()
        
        for farmer in farmers:
            send_notification(
                farmer['farmer_id'],
                'Order Cancelled',
                f'Order #{order["order_number"]} has been cancelled by the customer',
                'order',
                f'/farmer/orders/{order_id}'
            )
        
        conn.commit()
        flash('Order cancelled successfully!', 'success')
    
    except Exception as e:
        flash('Failed to cancel order', 'error')
        print(f"Order cancel error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('consumer.order_detail', order_id=order_id))

@consumer_bp.route('/orders/<int:order_id>/reorder', methods=['POST'])
@require_login(['consumer'])
def reorder(order_id):
    """Reorder items from previous order"""
    conn = get_db_connection()
    
    # Get order
    order = conn.execute('''
        SELECT * FROM orders WHERE id = ? AND consumer_id = ?
    ''', (order_id, session['user_id'])).fetchone()
    
    if not order:
        flash('Order not found!', 'error')
        return redirect(url_for('consumer.orders'))
    
    # Get order items
    order_items = conn.execute('''
        SELECT oi.*, p.quantity as current_stock
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ? AND p.is_approved = 1
    ''', (order_id,)).fetchall()
    
    if not order_items:
        flash('No items available to reorder!', 'error')
        return redirect(url_for('consumer.order_detail', order_id=order_id))
    
    added_count = 0
    out_of_stock = []
    
    try:
        for item in order_items:
            # Check current stock
            if item['current_stock'] <= 0:
                out_of_stock.append(item['product_id'])
                continue
            
            # Adjust quantity if less stock available
            quantity_to_add = min(item['quantity'], item['current_stock'])
            
            # Check if already in cart
            existing_item = conn.execute('''
                SELECT * FROM cart_items 
                WHERE user_id = ? AND product_id = ?
            ''', (session['user_id'], item['product_id'])).fetchone()
            
            if existing_item:
                # Update quantity
                new_quantity = min(existing_item['quantity'] + quantity_to_add, 
                                 item['current_stock'])
                conn.execute('''
                    UPDATE cart_items 
                    SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND product_id = ?
                ''', (new_quantity, session['user_id'], item['product_id']))
            else:
                # Add new item
                conn.execute('''
                    INSERT INTO cart_items (user_id, product_id, quantity)
                    VALUES (?, ?, ?)
                ''', (session['user_id'], item['product_id'], quantity_to_add))
            
            added_count += 1
        
        conn.commit()
        
        message = f'Added {added_count} items to cart'
        if out_of_stock:
            message += f'. {len(out_of_stock)} items were out of stock.'
        
        flash(message, 'success' if added_count > 0 else 'warning')
    
    except Exception as e:
        flash('Failed to add items to cart', 'error')
        print(f"Reorder error: {e}")
    
    finally:
        conn.close()
    
    return redirect(url_for('consumer.cart'))

@consumer_bp.route('/reviews/farmer/<int:farmer_id>', methods=['GET', 'POST'])
@require_login(['consumer'])
def rate_farmer(farmer_id):
    """Rate and review farmer"""
    conn = get_db_connection()
    
    # Check if user has purchased from this farmer
    has_purchased = conn.execute('''
        SELECT COUNT(*) FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.consumer_id = ? AND oi.farmer_id = ? AND o.payment_status = 'paid'
    ''', (session['user_id'], farmer_id)).fetchone()[0]
    
    if not has_purchased:
        flash('You can only rate farmers you have purchased from!', 'error')
        return redirect(url_for('index'))
    
    # Check if already rated
    existing_rating = conn.execute('''
        SELECT id FROM farmer_ratings WHERE consumer_id = ? AND farmer_id = ?
    ''', (session['user_id'], farmer_id)).fetchone()
    
    if existing_rating:
        flash('You have already rated this farmer!', 'info')
        return redirect(url_for('index'))
    
    # Get farmer info
    farmer = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'farmer'
    ''', (farmer_id,)).fetchone()
    
    if not farmer:
        flash('Farmer not found!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        overall_rating = int(request.form['overall_rating'])
        delivery_rating = int(request.form.get('delivery_rating', 0))
        quality_rating = int(request.form.get('quality_rating', 0))
        communication_rating = int(request.form.get('communication_rating', 0))
        comment = request.form.get('comment', '').strip()
        
        # Validation
        if overall_rating < 1 or overall_rating > 5:
            flash('Please select a valid overall rating!', 'error')
        else:
            try:
                # Get a recent order for reference
                recent_order = conn.execute('''
                    SELECT o.id FROM orders o
                    JOIN order_items oi ON o.id = oi.order_id
                    WHERE o.consumer_id = ? AND oi.farmer_id = ? AND o.payment_status = 'paid'
                    ORDER BY o.created_at DESC
                    LIMIT 1
                ''', (session['user_id'], farmer_id)).fetchone()
                
                conn.execute('''
                    INSERT INTO farmer_ratings (
                        farmer_id, consumer_id, order_id, rating, 
                        delivery_rating, quality_rating, communication_rating, comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (farmer_id, session['user_id'], recent_order['id'], overall_rating,
                      delivery_rating, quality_rating, communication_rating, comment))
                
                conn.commit()
                flash('Farmer rating added successfully!', 'success')
                return redirect(url_for('index'))
            
            except Exception as e:
                flash('Failed to add rating. Please try again.', 'error')
                print(f"Farmer rating error: {e}")
    
    conn.close()
    return render_template('consumer/rate_farmer.html', farmer=farmer)

@consumer_bp.route('/profile/edit', methods=['GET', 'POST'])
@require_login(['consumer'])
def edit_profile():
    """Edit consumer profile"""
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Get form data
        full_name = request.form['full_name'].strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        
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
                        from modules.utils import save_uploaded_file
                        profile_image = save_uploaded_file(file, 'profiles')
                
                # Update user profile
                if profile_image:
                    conn.execute('''
                        UPDATE users SET
                            full_name = ?, phone = ?, location = ?, 
                            profile_image = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (full_name, phone, location, profile_image, session['user_id']))
                else:
                    conn.execute('''
                        UPDATE users SET
                            full_name = ?, phone = ?, location = ?, 
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (full_name, phone, location, session['user_id']))
                
                conn.commit()
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('consumer.dashboard'))
            
            except Exception as e:
                flash('Failed to update profile', 'error')
                print(f"Profile update error: {e}")
    
    # Get current profile data
    user = conn.execute('''
        SELECT * FROM users WHERE id = ? AND user_type = 'consumer'
    ''', (session['user_id'],)).fetchone()
    
    conn.close()
    
    return render_template('consumer/edit_profile.html', user=user)

@consumer_bp.route('/api/search/save', methods=['POST'])
@require_login(['consumer'])
def save_search():
    """Save search query for analytics"""
    data = request.get_json()
    query = data.get('query', '').strip()
    results_count = int(data.get('results_count', 0))
    
    if not query:
        return jsonify({'success': False})
    
    conn = get_db_connection()
    
    try:
        conn.execute('''
            INSERT INTO search_history (user_id, query, results_count)
            VALUES (?, ?, ?)
        ''', (session['user_id'], query, results_count))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Save search error: {e}")
        return jsonify({'success': False})

@consumer_bp.route('/notifications')
@require_login(['consumer'])
def notifications():
    """Consumer notifications"""
    conn = get_db_connection()
    
    # Get notifications
    notifications_list = conn.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    ''', (session['user_id'],)).fetchall()
    
    # Mark all as read
    conn.execute('''
        UPDATE notifications 
        SET is_read = 1 
        WHERE user_id = ? AND is_read = 0
    ''', (session['user_id'],))
    
    conn.commit()
    conn.close()
    
    return render_template('consumer/notifications.html', notifications=notifications_list)