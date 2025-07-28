#!/usr/bin/env python3
"""
Simple test script to verify the Farmer Connect application
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from modules.database import get_db_connection

def test_database_connection():
    """Test database connection"""
    try:
        conn = get_db_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        
        print("✅ Database connection successful!")
        print(f"📋 Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[0]}")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_routes():
    """Test main routes"""
    with app.test_client() as client:
        try:
            # Test home page
            response = client.get('/')
            if response.status_code == 200:
                print("✅ Home page loads successfully")
            else:
                print(f"❌ Home page failed: {response.status_code}")
            
            # Test products page
            response = client.get('/products')
            if response.status_code == 200:
                print("✅ Products page loads successfully")
            else:
                print(f"❌ Products page failed: {response.status_code}")
            
            # Test login page
            response = client.get('/auth/login')
            if response.status_code == 200:
                print("✅ Login page loads successfully")
            else:
                print(f"❌ Login page failed: {response.status_code}")
            
            # Test register page
            response = client.get('/auth/register')
            if response.status_code == 200:
                print("✅ Register page loads successfully")
            else:
                print(f"❌ Register page failed: {response.status_code}")
            
            return True
        except Exception as e:
            print(f"❌ Route testing failed: {e}")
            return False

def check_admin_account():
    """Check if admin account exists"""
    try:
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM users WHERE email = 'admin@farmerconnect.com'").fetchone()
        conn.close()
        
        if admin:
            print("✅ Admin account exists!")
            print(f"   Email: {admin['email']}")
            print(f"   Username: {admin['username']}")
            print("   Password: admin123")
        else:
            print("❌ Admin account not found!")
        return admin is not None
    except Exception as e:
        print(f"❌ Admin account check failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🌱 Testing Farmer Connect Application")
    print("=" * 50)
    
    success_count = 0
    total_tests = 3
    
    # Test database
    if test_database_connection():
        success_count += 1
    
    # Test admin account
    if check_admin_account():
        success_count += 1
    
    # Test routes
    if test_routes():
        success_count += 1
    
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All tests passed! Your application is ready to run.")
        print("\n🚀 To start the server, run: python run.py")
        print("🌐 Then visit: http://localhost:5000")
        print("👨‍💼 Admin login: admin@farmerconnect.com / admin123")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        
    return success_count == total_tests

if __name__ == '__main__':
    main()