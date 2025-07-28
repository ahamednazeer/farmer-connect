# Farmer Connect - E-commerce Platform

A comprehensive web-based e-commerce platform designed to connect local farmers directly with consumers, eliminating middlemen and enhancing farmer profitability.

## 🌟 Features

### For Farmers
- **Account Registration & Login**: Secure farmer account management with admin approval
- **Product Management**: List products with descriptions, prices, images, and inventory tracking
- **Order Management**: View and manage customer orders
- **Earnings Dashboard**: Track sales and revenue analytics
- **Inventory Control**: Real-time stock management

### For Consumers
- **User Registration & Login**: Quick consumer account setup
- **Product Browsing**: Browse/search/filter produce by category, location, or freshness
- **Shopping Cart**: Add items to cart with quantity management
- **Secure Checkout**: Multiple payment options with order tracking
- **Order History**: Track current and past orders

### Admin Panel
- **User Management**: Approve farmer accounts and manage all users
- **Product Approval**: Review and approve product listings
- **Order Monitoring**: Track all platform transactions
- **Analytics Dashboard**: Platform usage and revenue analytics
- **Category Management**: Manage product categories
- **Site Settings**: Configure platform settings

## 🛠 Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: Bootstrap 5, HTML5, CSS3, JavaScript
- **Icons**: Font Awesome
- **Charts**: Chart.js
- **Currency**: Indian Rupee (₹) system

## 📁 Project Structure

```
Farmer/
├── app.py                 # Main Flask application
├── run.py                # Development server runner
├── requirements.txt      # Python dependencies
├── README.md            # Project documentation
├── modules/             # Application modules
│   ├── __init__.py
│   ├── database.py      # Database operations
│   ├── utils.py         # Utility functions
│   ├── auth.py          # Authentication module
│   ├── farmer.py        # Farmer functionality
│   ├── consumer.py      # Consumer functionality
│   └── admin.py         # Admin functionality
├── templates/           # HTML templates
│   ├── base.html        # Base template
│   ├── index.html       # Home page
│   ├── auth/           # Authentication templates
│   ├── farmer/         # Farmer templates
│   ├── consumer/       # Consumer templates
│   └── admin/          # Admin templates
├── static/             # Static files
│   ├── css/           # Stylesheets
│   ├── js/            # JavaScript files
│   └── uploads/       # User uploaded files
└── farmer_connect.db   # SQLite database (auto-created)
```

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Clone/Download the Project
```bash
# If using git
git clone <repository-url>
cd Farmer

# Or download and extract the ZIP file to "Farmer" directory
```

### Step 2: Install Dependencies
```bash
# Create virtual environment (recommended)
python -m venv farmer_env

# Activate virtual environment
# On Windows:
farmer_env\Scripts\activate
# On macOS/Linux:
source farmer_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Test the Application
```bash
# Run the test script to verify everything is working
python test_app.py
```

### Step 4: Run the Application
```bash
# Using the run script (recommended)
python run.py

# Or directly with Flask
python app.py
```

### Step 5: Access the Application
- Open your browser and go to: http://localhost:5000
- The database will be automatically created on first run
- SQLite database file will be created as `farmer_connect.db`

## 👥 Default Accounts

### Admin Account
- **Email**: admin@farmerconnect.com
- **Password**: admin123
- **Access**: Full platform administration

### Test the Platform
1. Register as a farmer (requires admin approval)
2. Register as a consumer (automatically approved)
3. Login as admin to approve farmer accounts
4. Add products as a farmer
5. Browse and purchase as a consumer

## 💡 Key Features Explained

### Modular Architecture
The application is built with a modular structure where each user type has its dedicated module:
- `auth.py` - Handles authentication for all user types
- `farmer.py` - Farmer-specific functionality
- `consumer.py` - Consumer-specific functionality  
- `admin.py` - Admin panel features

### Database Design
- **Users Table**: Stores farmers, consumers, and admin accounts
- **Products Table**: Product listings with approval workflow
- **Orders Table**: Order management and tracking
- **Cart Items**: Shopping cart functionality
- **Reviews**: Product review system
- **Notifications**: In-app notification system

### Security Features
- Password hashing using Werkzeug security
- Session-based authentication
- Role-based access control
- Input validation and sanitization
- File upload security

### Indian Market Features
- Currency formatted in Indian Rupees (₹)
- Phone number validation for Indian numbers
- Location-based product filtering
- Cash on Delivery (COD) payment option

## 🎨 UI/UX Features

### Modern Design
- Bootstrap 5 framework for responsive design
- Google Fonts (Poppins) for modern typography
- Font Awesome icons throughout the interface
- Gradient backgrounds and smooth animations

### Mobile-First Approach
- Fully responsive design
- Mobile-optimized navigation
- Touch-friendly interface elements
- Optimized images and loading

### User Experience
- Intuitive navigation with role-based menus
- Real-time cart updates
- Toast notifications for user feedback
- Loading states and progress indicators
- Search and filter functionality

## 🔧 Configuration

### Environment Variables
You can customize the application by modifying these variables in `app.py`:
- `SECRET_KEY`: Flask secret key for sessions
- `UPLOAD_FOLDER`: Directory for uploaded files
- `MAX_CONTENT_LENGTH`: Maximum file upload size

### Database Settings
The application uses SQLite by default. To use a different database:
1. Install the appropriate database driver
2. Modify the connection string in `modules/database.py`

## 🚀 Deployment

### For Production Deployment:

1. **Set Environment Variables**:
   ```bash
   export FLASK_ENV=production
   export SECRET_KEY='your-secret-key-here'
   ```

2. **Use a Production WSGI Server**:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

3. **Database Migration**:
   - For production, consider using PostgreSQL or MySQL
   - Update connection string in database.py
   - Run migrations to create tables

4. **Static Files**:
   - Configure a web server (nginx) to serve static files
   - Set up proper file upload handling

## 🔍 API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/logout` - User logout

### Products
- `GET /products` - List all products
- `GET /product/<id>` - Product details
- `POST /api/cart/add` - Add to cart

### Farmer Dashboard
- `GET /farmer/dashboard` - Farmer dashboard
- `GET /farmer/products` - Farmer's products
- `POST /farmer/products/add` - Add new product

### Consumer Features
- `GET /consumer/cart` - Shopping cart
- `POST /consumer/checkout` - Place order
- `GET /consumer/orders` - Order history

### Admin Panel
- `GET /admin/dashboard` - Admin dashboard
- `POST /admin/farmers/approve/<id>` - Approve farmer
- `GET /admin/analytics` - Platform analytics

## 🔒 Security Considerations

### Authentication & Authorization
- Secure password hashing
- Session management
- Role-based access control
- CSRF protection (can be added)

### Data Protection
- Input validation and sanitization
- SQL injection prevention through parameterized queries
- File upload restrictions
- XSS protection through template escaping

### Recommended Additions for Production
- HTTPS/SSL implementation
- Rate limiting for API endpoints
- Database backups and recovery
- Log monitoring and alerting
- Error tracking (e.g., Sentry)

## 🧪 Testing

To test the application:

1. **Register different user types**:
   - Register as a farmer
   - Register as a consumer
   - Use admin account

2. **Test workflows**:
   - Farmer product listing workflow
   - Consumer shopping workflow
   - Admin approval workflow

3. **Test features**:
   - File uploads
   - Payment simulation
   - Order tracking
   - Notifications

## 🤝 Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For support or questions:
- Email: info@farmerconnect.com
- Phone: +91-9999999999

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Bootstrap team for the UI framework
- Font Awesome for icons
- Flask community for the web framework
- All the farmers who inspired this project

---

**Happy Farming! 🌱**# farmer-connect
