#!/usr/bin/env python3
"""
Development server runner for Farmer Connect
"""

from app import app
from modules.database import init_db

if __name__ == '__main__':
    # Initialize database
    with app.app_context():
        init_db()
    
    print("Starting Farmer Connect...")
    print("Server: http://localhost:5002")
    print("Admin Login: admin@farmerconnect.com / admin123")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5002)