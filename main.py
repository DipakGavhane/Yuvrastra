from flask import Flask, render_template, redirect, session, request, jsonify, url_for, flash, abort

import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps
import secrets
import os
from dotenv import load_dotenv

from datetime import datetime, timezone
# Import your models and forms
from models import *
from forms import ProductForm, EditProductForm, BulkUploadForm, ProductSearchForm
from admin_routes import admin
from cart_routes import cart_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
# Register blueprints
app.register_blueprint(admin)
app.register_blueprint(cart_bp)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///yuvrastra.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)  # Bind the database with the Flask app
init_db(app)

# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Firebase initialization error: {e}")

# Firebase Web API Key
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")


def login_required(f):
    """Decorator to check if user is logged in"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('choose_login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('choose_login'))
        if not session['user'].get('is_admin'):
            return redirect(url_for('not_found_error'))
        return f(*args, **kwargs)

    return decorated_function


def get_or_create_user(firebase_user, auth_provider):
    """
    Get existing user or create new user in database

    Args:
        firebase_user: Firebase user object
        auth_provider: Authentication provider ('google', 'apple', 'email')

    Returns:
        User object and boolean indicating if user was created
    """
    try:
        # First try to find user by Firebase UID
        user = User.find_by_firebase_uid(firebase_user.uid)

        if user:
            # Existing user - update last login and any changed info
            user.update_last_login()

            # Update user info if it changed
            updated = False

            if firebase_user.display_name and firebase_user.display_name != user.display_name:
                user.display_name = firebase_user.display_name
                user.name = firebase_user.display_name
                updated = True

            if firebase_user.photo_url and firebase_user.photo_url != user.photo_url:
                user.photo_url = firebase_user.photo_url
                updated = True

            if firebase_user.email_verified != user.email_verified:
                user.email_verified = firebase_user.email_verified
                updated = True

            # Only commit if something was updated
            if updated:
                db.session.commit()

            return user, False

        else:
            # New user - create account
            # Split name into first and last name
            first_name = None
            last_name = None
            display_name = firebase_user.display_name

            if display_name:
                name_parts = display_name.strip().split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else None

            # Fallback name if display_name is None
            fallback_name = firebase_user.email.split('@')[0] if firebase_user.email else 'User'

            new_user = User(
                firebase_uid=firebase_user.uid,
                email=firebase_user.email,
                name=display_name or fallback_name,
                display_name=display_name,
                photo_url=firebase_user.photo_url,
                phone_number=firebase_user.phone_number,
                is_admin=(firebase_user.email == 'dipakgavhan@gmail.com'),
                auth_provider=auth_provider,
                email_verified=firebase_user.email_verified or False,  # Ensure boolean
                first_name=first_name,
                last_name=last_name,
                last_login=datetime.now(timezone.utc)
            )

            db.session.add(new_user)
            db.session.commit()

            return new_user, True

    except Exception as e:
        print(f"Error in get_or_create_user: {e}")
        db.session.rollback()
        raise


@app.route('/')
def home():
    """Main homepage route with featured products"""
    # Get featured products (active products with stock, limited to 6 for homepage)
    featured_products = Product.query.filter(
        Product.is_active == True
    ).order_by(
        Product.created_at.desc()
    ).limit(6).all()

    return render_template('index.html', products=featured_products)


@app.route('/guest')
def guest_login():
    # For guest users, we might want to create a temporary record or handle differently
    session['user'] = {
        'name': 'Guest',
        'auth_type': 'guest',
        'uid': f'guest_{secrets.token_hex(8)}'
    }
    flash('Logged in as Guest', 'success')
    return redirect('/')


# Simplified auth callback route
@app.route('/auth/callback', methods=['POST'])
def auth_callback():
    """Handle authentication callback for all providers"""
    try:
        data = request.get_json()
        if not data or not data.get('idToken'):
            return jsonify({'success': False, 'error': 'Missing token'}), 400

        # Verify Firebase token
        decoded_token = auth.verify_id_token(data['idToken'])
        firebase_user = auth.get_user(decoded_token['uid'])

        # Map provider to auth type
        provider_map = {
            'google.com': 'google',
            'apple.com': 'apple',
            'password': 'email'
        }
        auth_type = provider_map.get(data.get('provider'), 'email')

        # Get or create user
        db_user, is_new_user = get_or_create_user(firebase_user, auth_type)

        # Update last login
        db_user.update_last_login()

        # Set session
        session['user'] = {
            'id': db_user.id,
            'uid': decoded_token['uid'],
            'photo_url': db_user.photo_url,
            'email': db_user.email,
            'name': db_user.name,
            'auth_type': auth_type,
            'is_admin': db_user.is_admin,
            'is_new_user': is_new_user
        }

        # Redirect logic
        redirect_url = url_for('home') if is_new_user else url_for('home')

        return jsonify({
            'success': True,
            'redirect': redirect_url,
            'is_new_user': is_new_user
        })

    except (auth.InvalidIdTokenError, auth.ExpiredIdTokenError):
        return jsonify({'success': False, 'error': 'Invalid token'}), 400
    except Exception as e:
        print(f"Auth error: {e}")
        return jsonify({'success': False, 'error': 'Authentication failed'}), 500


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect('/')


@app.route('/login')
def choose_login():
    """Redirect to Google OAuth - This will be handled by frontend Firebase"""
    return render_template('Login.html', firebase_api_key=FIREBASE_WEB_API_KEY)


@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    # Get user from database
    user_id = session['user']['id']
    db_user = db.session.get(User, user_id)

    if not db_user:
        flash('User not found', 'error')
        return redirect(url_for('home'))

    return render_template('profile.html', user=db_user)


@app.route('/profile/setup')
@login_required
def profile_setup():
    """Profile setup page for new users"""
    if not session['user'].get('is_new_user'):
        return redirect(url_for('dashboard'))

    user_id = session['user']['id']
    db_user = db.session.get(User, user_id)

    # Temporary redirect to dashboard until template is created
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page"""
    user_id = session['user']['id']
    db_user = db.session.get(User, user_id)

    return render_template('dashboard.html', user=db_user)


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Main admin dashboard with overview stats"""
    return render_template('Add_Product.html')


@app.route('/checkout')
@login_required
def checkout():
    """Checkout page"""
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart.view_cart'))

    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids)).all() if product_ids else []

    cart_items = []
    total = 0

    for product in products:
        if not product.is_active:
            continue

        quantity = cart.get(str(product.id), 0)
        if quantity > 0:
            subtotal = float(product.price * quantity)
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })
            total += subtotal

    if not cart_items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart.view_cart'))

    return render_template('checkout.html', cart_items=cart_items, total=total)


@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    """Handle order placement"""
    try:
        cart = session.get('cart', {})
        if not cart:
            flash('Your cart is empty.', 'error')
            return redirect(url_for('cart.view_cart'))

        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip')

        # Validate required fields
        if not all([name, email, phone, address, city, state, zip_code]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('checkout'))

        # Create order
        order = Order(
            user_id=session['user']['id'],
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            shipping_address=address,
            shipping_city=city,
            shipping_state=state,
            shipping_zip=zip_code,
            total_amount=0  # Will be calculated below
        )

        # Add order items
        total_amount = 0
        product_ids = [int(pid) for pid in cart.keys()]
        products = Product.query.filter(Product.id.in_(product_ids)).all() if product_ids else []

        for product in products:
            quantity = cart.get(str(product.id), 0)
            if quantity > 0 and product.is_active and product.stock >= quantity:
                subtotal = float(product.price * quantity)
                total_amount += subtotal

                order_item = OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    product_price=product.price,
                    quantity=quantity,
                    subtotal=subtotal
                )
                order.order_items.append(order_item)

                # Update product stock
                product.stock -= quantity

        if not order.order_items:
            flash('No valid items in cart.', 'error')
            return redirect(url_for('cart.view_cart'))

        # Set final total and save order
        order.total_amount = total_amount
        db.session.add(order)
        db.session.commit()

        # Clear cart
        session.pop('cart', None)
        flash('Order placed successfully!', 'success')
        return redirect(url_for('order_confirmation', order_id=order.id))

    except Exception as e:
        db.session.rollback()
        print(f"Order error: {e}")  # Add logging
        flash('An error occurred while placing your order.', 'error')
        return redirect(url_for('checkout'))


@app.route('/order_confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    """Order confirmation page"""
    order = Order.query.get_or_404(order_id)
    if order.user_id != session['user']['id']:
        abort(403)
    return render_template('order_confirmation.html', order=order)


# API endpoint to get current user info
@app.route('/api/user')
def get_user():
    if 'user' in session:
        user_id = session['user']['id']
        db_user = db.session.get(User, user_id)

        if db_user:
            return jsonify(db_user.to_dict())
        else:
            return jsonify({'error': 'User not found in database'}), 404
    return jsonify({'error': 'Not authenticated'}), 401


# API endpoint to update user profile
@app.route('/api/user/update', methods=['POST'])
@login_required
def update_user():
    try:
        user_id = session['user']['id']
        db_user = db.session.get(User, user_id)

        if not db_user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()

        # Update allowed fields (removed non-existent fields)
        updateable_fields = [
            'display_name', 'first_name', 'last_name', 'address'
        ]

        for field in updateable_fields:
            if field in data:
                setattr(db_user, field, data[field])

        # Removed reference to non-existent updated_at field
        db.session.commit()

        return jsonify({'success': True, 'user': db_user.to_dict()})

    except Exception as e:
        print(f"Error updating user: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update user'}), 500


# Add error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Route not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True)