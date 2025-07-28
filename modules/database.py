"""
Database module for Farmer Connect
Handles SQLite database operations
"""

import sqlite3
import os
from datetime import datetime

DATABASE = 'farmer_connect.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with all required tables"""
    conn = get_db_connection()
    
    # Users table (farmers, consumers, admin)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) UNIQUE NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(200) NOT NULL,
            user_type VARCHAR(20) NOT NULL CHECK(user_type IN ('farmer', 'consumer', 'admin')),
            full_name VARCHAR(100) NOT NULL,
            phone VARCHAR(15),
            location VARCHAR(200),
            farm_name VARCHAR(100),
            farm_description TEXT,
            profile_image VARCHAR(200),
            is_approved BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Products table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            category VARCHAR(50) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            unit VARCHAR(20) NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            image VARCHAR(200),
            is_approved BOOLEAN DEFAULT 0,
            is_featured BOOLEAN DEFAULT 0,
            harvest_date DATE,
            expiry_date DATE,
            organic BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farmer_id) REFERENCES users (id)
        )
    ''')
    
    # Categories table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(50) UNIQUE NOT NULL,
            description TEXT,
            image VARCHAR(200),
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Cart items table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            UNIQUE(user_id, product_id)
        )
    ''')
    
    # Orders table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number VARCHAR(50) UNIQUE NOT NULL,
            consumer_id INTEGER NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')),
            payment_status VARCHAR(20) DEFAULT 'pending' CHECK(payment_status IN ('pending', 'paid', 'failed', 'refunded')),
            payment_method VARCHAR(50),
            delivery_address TEXT NOT NULL,
            delivery_phone VARCHAR(15),
            delivery_type VARCHAR(20) DEFAULT 'delivery' CHECK(delivery_type IN ('delivery', 'pickup')),
            delivery_date DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (consumer_id) REFERENCES users (id)
        )
    ''')
    
    # Order items table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            farmer_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (farmer_id) REFERENCES users (id)
        )
    ''')
    
    # Reviews table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            consumer_id INTEGER NOT NULL,
            order_id INTEGER,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            is_approved BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (consumer_id) REFERENCES users (id),
            FOREIGN KEY (order_id) REFERENCES orders (id),
            UNIQUE(product_id, consumer_id, order_id)
        )
    ''')
    
    # Notifications table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            type VARCHAR(50) DEFAULT 'info',
            is_read BOOLEAN DEFAULT 0,
            link VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Farmer ratings table (separate from product reviews)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS farmer_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            consumer_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            delivery_rating INTEGER CHECK(delivery_rating >= 1 AND delivery_rating <= 5),
            quality_rating INTEGER CHECK(quality_rating >= 1 AND quality_rating <= 5),
            communication_rating INTEGER CHECK(communication_rating >= 1 AND communication_rating <= 5),
            comment TEXT,
            is_approved BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farmer_id) REFERENCES users (id),
            FOREIGN KEY (consumer_id) REFERENCES users (id),
            FOREIGN KEY (order_id) REFERENCES orders (id),
            UNIQUE(farmer_id, consumer_id, order_id)
        )
    ''')
    
    # Wishlist table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS wishlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            UNIQUE(user_id, product_id)
        )
    ''')
    
    # Search history table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query VARCHAR(200) NOT NULL,
            results_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Promotions and discounts table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            discount_type VARCHAR(20) CHECK(discount_type IN ('percentage', 'fixed_amount')),
            discount_value DECIMAL(10,2) NOT NULL,
            min_order_amount DECIMAL(10,2) DEFAULT 0,
            promo_code VARCHAR(50) UNIQUE,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            usage_limit INTEGER,
            usage_count INTEGER DEFAULT 0,
            applicable_to VARCHAR(20) DEFAULT 'all' CHECK(applicable_to IN ('all', 'farmers', 'products', 'categories')),
            applicable_ids TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Order tracking table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS order_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status VARCHAR(50) NOT NULL,
            message TEXT,
            location VARCHAR(200),
            updated_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (updated_by) REFERENCES users (id)
        )
    ''')
    
    # Communication/Messages table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            subject VARCHAR(200),
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            message_type VARCHAR(20) DEFAULT 'user' CHECK(message_type IN ('user', 'system', 'support')),
            parent_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id),
            FOREIGN KEY (parent_message_id) REFERENCES messages (id)
        )
    ''')
    
    # Analytics tracking table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type VARCHAR(50) NOT NULL,
            event_data TEXT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Farmer inventory alerts
    conn.execute('''
        CREATE TABLE IF NOT EXISTS inventory_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            alert_type VARCHAR(20) CHECK(alert_type IN ('low_stock', 'out_of_stock', 'expiring_soon')),
            threshold_value INTEGER,
            is_active BOOLEAN DEFAULT 1,
            last_alerted TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farmer_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Contact messages table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) NOT NULL,
            phone VARCHAR(15),
            subject VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'unread' CHECK(status IN ('unread', 'read', 'replied')),
            admin_reply TEXT,
            replied_by INTEGER,
            replied_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (replied_by) REFERENCES users (id)
        )
    ''')
    
    # Site settings table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS site_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key VARCHAR(100) UNIQUE NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default categories
    categories = [
        ('Vegetables', 'Fresh seasonal vegetables'),
        ('Fruits', 'Farm fresh fruits'),
        ('Dairy', 'Fresh dairy products'),
        ('Grains', 'Organic grains and cereals'),
        ('Herbs', 'Fresh herbs and spices'),
        ('Pulses', 'Various pulses and legumes')
    ]
    
    for name, desc in categories:
        conn.execute('''
            INSERT OR IGNORE INTO categories (name, description)
            VALUES (?, ?)
        ''', (name, desc))
    
    # Insert default admin user
    from werkzeug.security import generate_password_hash
    admin_password = generate_password_hash('admin123')
    
    conn.execute('''
        INSERT OR IGNORE INTO users (
            username, email, password_hash, user_type, full_name, 
            is_approved, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('admin', 'admin@farmerconnect.com', admin_password, 'admin', 
          'System Administrator', 1, 1))
    
    # Insert default site settings
    settings = [
        ('site_name', 'Farmer Connect'),
        ('site_description', 'Connecting farmers directly with consumers'),
        ('contact_email', 'info@farmerconnect.com'),
        ('contact_phone', '+91-9999999999'),
        ('delivery_charge', '50'),
        ('free_delivery_above', '1000'),
        ('commission_rate', '5')
    ]
    
    for key, value in settings:
        conn.execute('''
            INSERT OR IGNORE INTO site_settings (key, value)
            VALUES (?, ?)
        ''', (key, value))
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def get_setting(key, default=None):
    """Get site setting value"""
    conn = get_db_connection()
    result = conn.execute(
        'SELECT value FROM site_settings WHERE key = ?', (key,)
    ).fetchone()
    conn.close()
    return result['value'] if result else default

def update_setting(key, value):
    """Update site setting"""
    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO site_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (key, value))
    conn.commit()
    conn.close()