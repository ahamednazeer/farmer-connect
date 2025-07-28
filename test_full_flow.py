#!/usr/bin/env python3

"""
Test script to simulate the complete order confirmation flow
"""

import requests
import json
from modules.database import get_db_connection

def test_ajax_request():
    """Test the actual AJAX request that would be made by the frontend"""
    
    print("=== Testing AJAX Order Update Request ===")
    
    # Reset order to pending first
    conn = get_db_connection()
    conn.execute('UPDATE orders SET status = ? WHERE id = 1', ('pending',))
    conn.execute('DELETE FROM order_tracking WHERE order_id = 1')
    conn.commit()
    
    order = conn.execute('SELECT * FROM orders WHERE id = 1').fetchone()
    print(f"Initial order status: {order['status']}")
    conn.close()
    
    # Simulate the AJAX request
    url = 'http://127.0.0.1:5001/farmer/orders/update-status/1'
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    data = {'status': 'confirmed'}
    
    try:
        print(f"Making POST request to: {url}")
        print(f"Headers: {headers}")
        print(f"Data: {data}")
        
        response = requests.post(url, headers=headers, data=data, allow_redirects=False)
        
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.headers.get('Content-Type', '').startswith('application/json'):
            try:
                response_data = response.json()
                print(f"JSON Response: {response_data}")
            except:
                print("Failed to parse JSON response")
                print(f"Raw response: {response.text}")
        else:
            print(f"Non-JSON response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    
    # Check final database state
    print("\n=== Final Database State ===")
    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE id = 1').fetchone()
    print(f"Final order status: {order['status']}")
    
    tracking_entries = conn.execute('SELECT * FROM order_tracking WHERE order_id = 1').fetchall()
    print(f"Tracking entries: {len(tracking_entries)}")
    for entry in tracking_entries:
        print(f"  - {entry['status']}: {entry['message']}")
    
    conn.close()

if __name__ == '__main__':
    test_ajax_request()