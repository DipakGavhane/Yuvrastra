from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone


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