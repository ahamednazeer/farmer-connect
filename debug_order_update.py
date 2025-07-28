#!/usr/bin/env python3

"""
Debug script to test order update with proper session simulation
"""

from modules.database import get_db_connection
from modules.farmer import farmer_bp
from flask import Flask, session, request, g
from werkzeug.test import Client
from werkzeug.wrappers import Response
import json

app = Flask(__name__)
app.secret_key = 'test-secret-key'
app.register_blueprint(farmer_bp, url_prefix='/farmer')

def test_order_update_with_session():
    """Test order update with proper session"""
    
    print("=== Testing Order Update with Session ===")
    
    # Reset order to pending
    conn = get_db_connection()
    conn.execute('UPDATE orders SET status = ? WHERE id = 1', ('pending',))
    conn.execute('DELETE FROM order_tracking WHERE order_id = 1')
    conn.commit()
    
    order = conn.execute('SELECT * FROM orders WHERE id = 1').fetchone()
    print(f"Initial order status: {order['status']}")
    conn.close()
    
    # Test with Flask test client
    with app.test_client() as client:
        # Simulate farmer login session
        with client.session_transaction() as sess:
            sess['user_id'] = 38  # Farmer ID
            sess['user_type'] = 'farmer'
            sess['username'] = 'farmer1'
            sess['is_approved'] = True  # Add approval status
        
        # Make the request
        response = client.post('/farmer/orders/update-status/1', 
                             data={'status': 'confirmed'},
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response data: {response.get_data(as_text=True)}")
        
        # Try to parse as JSON
        try:
            if response.content_type and 'json' in response.content_type:
                response_data = response.get_json()
                print(f"JSON Response: {response_data}")
        except Exception as e:
            print(f"Could not parse JSON: {e}")
    
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
    test_order_update_with_session()