#!/usr/bin/env python3
"""
Setup script for Farmer Connect Application
This script handles the initial setup and configuration
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

def print_header():
    """Print setup header"""
    print("🌱 Farmer Connect - Setup Script")
    print("=" * 50)

def check_python_version():
    """Check Python version"""
    print("📋 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Need Python 3.8+")
        return False

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    directories = [
        "static/uploads",
        "static/uploads/products",
        "static/uploads/profiles",
        "templates/farmer",
        "templates/consumer", 
        "templates/admin"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {directory}")
    
    return True

def check_database():
    """Check database setup"""
    print("\n🗄️ Checking database...")
    try:
        if os.path.exists("farmer_connect.db"):
            print("✅ Database file exists")
            
            # Check tables
            conn = sqlite3.connect("farmer_connect.db")
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            if len(tables) >= 8:
                print(f"✅ Database has {len(tables)} tables")
                return True
            else:
                print(f"⚠️  Database has only {len(tables)} tables, may need initialization")
                return False
        else:
            print("⚠️  Database file doesn't exist, will be created on first run")
            return True
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def test_import():
    """Test if the application can be imported"""
    print("\n🧪 Testing application import...")
    try:
        from app import app
        print("✅ Application imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def create_env_file():
    """Create environment file with default settings"""
    print("\n⚙️  Creating environment configuration...")
    
    env_content = """# Farmer Connect Environment Configuration
# Copy this file to .env and modify as needed

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-this-in-production

# Database Configuration
DATABASE_URL=sqlite:///farmer_connect.db

# Upload Configuration
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=16777216  # 16MB

# Email Configuration (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Payment Gateway (Future Integration)
RAZORPAY_KEY_ID=your-razorpay-key
RAZORPAY_KEY_SECRET=your-razorpay-secret
"""
    
    try:
        with open("config.env", "w") as f:
            f.write(env_content)
        print("✅ Environment file created: config.env")
        return True
    except Exception as e:
        print(f"❌ Failed to create environment file: {e}")
        return False

def run_test_suite():
    """Run the test suite"""
    print("\n🧪 Running test suite...")
    try:
        result = subprocess.run([sys.executable, "test_app.py"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ All tests passed")
            return True
        else:
            print("❌ Some tests failed")
            print(result.stdout)
            return False
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")
        return False

def print_final_instructions():
    """Print final setup instructions"""
    print("\n" + "=" * 50)
    print("🎉 Setup Complete!")
    print("\n🚀 Next Steps:")
    print("1. Run the application:")
    print("   python run.py")
    print("\n2. Open your browser and visit:")
    print("   http://localhost:5000")
    print("\n3. Login as admin:")
    print("   Email: admin@farmerconnect.com")
    print("   Password: admin123")
    print("\n4. Start by:")
    print("   - Registering as a farmer or consumer")
    print("   - Exploring the admin panel")
    print("   - Adding products (as farmer)")
    print("   - Browsing products (as consumer)")
    print("\n📚 Documentation:")
    print("   Check README.md for detailed information")
    print("\n🛠️  Development:")
    print("   - Modify config.env for custom settings")
    print("   - Check modules/ for backend code")
    print("   - Check templates/ for frontend code")
    print("   - Check static/ for assets")

def main():
    """Main setup function"""
    print_header()
    
    success_count = 0
    total_steps = 6
    
    # Step 1: Check Python version
    if check_python_version():
        success_count += 1
    
    # Step 2: Install dependencies
    if install_dependencies():
        success_count += 1
    
    # Step 3: Create directories
    if create_directories():
        success_count += 1
    
    # Step 4: Test imports
    if test_import():
        success_count += 1
    
    # Step 5: Check database
    if check_database():
        success_count += 1
    
    # Step 6: Create env file
    if create_env_file():
        success_count += 1
    
    print(f"\n🎯 Setup Results: {success_count}/{total_steps} steps completed")
    
    if success_count == total_steps:
        # Run test suite if setup is successful
        run_test_suite()
        print_final_instructions()
        return True
    else:
        print("\n⚠️  Setup incomplete. Please fix the errors above and run setup again.")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed with error: {e}")
        sys.exit(1)