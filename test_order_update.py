#!/usr/bin/env python3

"""
Test script to debug order confirmation functionality
"""

import sys
import requests
from modules.database import get_db_connection

def test_order_confirmation():
    """Test order confirmation process"""
    
    # Check database state before
    print("=== Database State Before ===")
    conn = get_db_connection()
    
    order = conn.execute('SELECT * FROM orders WHERE id = 1').fetchone()
    print(f"Order status: {order['status']}")
    
    tracking_entries = conn.execute('SELECT * FROM order_tracking WHERE order_id = 1').fetchall()
    print(f"Tracking entries: {len(tracking_entries)}")
    for entry in tracking_entries:
        print(f"  - {entry['status']}: {entry['message']}")
    
    conn.close()
    
    # Test the update endpoint directly
    print("\n=== Testing Order Update ===")
    
    # We need to simulate a farmer session
    # Let's check what happens when we make a direct update
    try:
        conn = get_db_connection()
        
        # Simulate the order status update
        print("Updating order status to 'confirmed'...")
        
        conn.execute('''
            UPDATE orders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', ('confirmed', 1))
        
        print("Adding tracking entry...")
        
        # Add tracking entry
        conn.execute('''
            INSERT INTO order_tracking (order_id, status, message, updated_by)
            VALUES (?, ?, ?, ?)
        ''', (1, 'confirmed', 'Order confirmed by farmer', 38))
        
        conn.commit()
        print("Update successful!")
        
    except Exception as e:
        print(f"Error during update: {e}")
        conn.rollback()
    
    finally:
        conn.close()
    
    # Check database state after
    print("\n=== Database State After ===")
    conn = get_db_connection()
    
    order = conn.execute('SELECT * FROM orders WHERE id = 1').fetchone()
    print(f"Order status: {order['status']}")
    
    tracking_entries = conn.execute('SELECT * FROM order_tracking WHERE order_id = 1').fetchall()
    print(f"Tracking entries: {len(tracking_entries)}")
    for entry in tracking_entries:
        print(f"  - {entry['status']}: {entry['message']} (by user {entry['updated_by']})")
    
    conn.close()

if __name__ == '__main__':
    test_order_confirmation()