from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum
import uuid

# Initialize SQLAlchemy
db = SQLAlchemy()

# User Model
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    firebase_uid = db.Column(db.String(128), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=True)
    photo_url = db.Column(db.Text, nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

    # Authentication related fields
    auth_provider = db.Column(db.String(50), nullable=False)  # 'google', 'apple', 'email', 'guest'
    email_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    # Profile fields
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)

    # Single address field
    address = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
        """Convert user object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'firebase_uid': self.firebase_uid,
            'email': self.email,
            'name': self.name,
            'display_name': self.display_name,
            'photo_url': self.photo_url,
            'phone_number': self.phone_number,

            'auth_provider': self.auth_provider,
            'email_verified': self.email_verified,
            'is_active': self.is_active,

            'first_name': self.first_name,
            'last_name': self.last_name,

            'address': self.address,

            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

    @classmethod
    def find_by_firebase_uid(cls, firebase_uid):
        """Find user by Firebase UID"""
        return cls.query.filter_by(firebase_uid=firebase_uid).first()

    @classmethod
    def find_by_email(cls, email):
        """Find user by email"""
        return cls.query.filter_by(email=email).first()

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.now(timezone.utc)
        db.session.commit()



class OrderStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)

    # Image URL
    image_url = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order_items = db.relationship('OrderItem', back_populates='product', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price),
            'stock': self.stock,
            'low_stock_threshold': self.low_stock_threshold,
            'image_url': self.image_url,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def is_in_stock(self):
        return self.stock > 0

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Customer information
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20))

    # Shipping address
    shipping_address = db.Column(db.Text, nullable=False)
    shipping_city = db.Column(db.String(50), nullable=False)
    shipping_state = db.Column(db.String(50), nullable=False)
    shipping_zip = db.Column(db.String(10), nullable=False)

    # Order details
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='orders')
    order_items = db.relationship('OrderItem', back_populates='order', lazy=True, cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        if not self.order_number:
            self.order_number = self.generate_order_number()

    def generate_order_number(self):
        return f"ORD-{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'user_id': self.user_id,
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'customer_phone': self.customer_phone,
            'shipping_address': self.shipping_address,
            'shipping_city': self.shipping_city,
            'shipping_state': self.shipping_state,
            'shipping_zip': self.shipping_zip,
            'total_amount': float(self.total_amount),
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'order_items': [item.to_dict() for item in self.order_items]
        }

    def update_status(self, new_status):
        self.status = new_status
        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f'<Order {self.order_number}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    # Product details at time of order
    product_name = db.Column(db.String(100), nullable=False)
    product_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    # Relationships
    order = db.relationship('Order', back_populates='order_items')
    product = db.relationship('Product', back_populates='order_items')

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'product_price': float(self.product_price),
            'quantity': self.quantity,
            'subtotal': float(self.subtotal)
        }

    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'


def init_db(app):
    """Initialize the database with tables"""
    with app.app_context():
        db.create_all()

        # Create sample products if none exist
        if Product.query.count() == 0:
            sample_products = [
                Product(
                    name='Sample Product 1',
                    description='This is a sample product',
                    price=29.99,
                    stock=100,
                    image_url='https://via.placeholder.com/300x300'
                ),
                Product(
                    name='Sample Product 2',
                    description='Another sample product',
                    price=49.99,
                    stock=50,
                    image_url='https://via.placeholder.com/300x300'
                )
            ]

            for product in sample_products:
                db.session.add(product)

            db.session.commit()
            print("Sample products created!")

        print("Database initialized successfully!")