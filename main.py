from flask import Flask, render_template, redirect, session, request, jsonify, url_for, flash
import firebase_admin
from firebase_admin import credentials, auth
import requests
from functools import wraps
import secrets
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Initialize Firebase Admin SDK
# Download your service account key from Firebase Console
# and place it in your project directory
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Firebase initialization error: {e}")

# Firebase Web API Key (get this from Firebase Console -> Project Settings -> Web API Key)
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")


def login_required(f):
    """Decorator to check if user is logged in"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('choose_login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/guest')
def guest_login():
    session['user'] = {
        'name': 'Guest',
        'auth_type': 'guest',
        'uid': f'guest_{secrets.token_hex(8)}'
    }
    flash('Logged in as Guest', 'success')
    return redirect('/')


# Generic auth callback route (NEW - this is what your frontend needs)
@app.route('/auth/callback', methods=['POST'])
def auth_callback():
    """Handle authentication callback for all providers"""
    try:
        # Get the request data
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        id_token = data.get('idToken')
        provider = data.get('provider', 'unknown')

        if not id_token:
            return jsonify({'success': False, 'error': 'No ID token provided'}), 400

        # Verify the ID token with Firebase Admin
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']

        # Get user info from Firebase
        user = auth.get_user(uid)

        # Determine auth type based on provider
        if provider == 'google.com':
            auth_type = 'google'
        elif provider == 'apple.com':
            auth_type = 'apple'
        elif provider == 'password':
            auth_type = 'email'
        else:
            auth_type = provider

        # Store user info in session
        session['user'] = {
            'uid': uid,
            'name': user.display_name or user.email or 'User',
            'email': user.email,
            'auth_type': auth_type,
            'photo_url': getattr(user, 'photo_url', None),
            'provider': provider
        }

        print(f"User authenticated: {user.email} via {auth_type}")

        return jsonify({
            'success': True,
            'redirect': url_for('dashboard'),
            'user': {
                'uid': uid,
                'email': user.email,
                'name': user.display_name or user.email,
                'provider': provider
            }
        })

    except auth.InvalidIdTokenError:
        print("Invalid ID token")
        return jsonify({'success': False, 'error': 'Invalid authentication token'}), 400
    except auth.ExpiredIdTokenError:
        print("Expired ID token")
        return jsonify({'success': False, 'error': 'Authentication token has expired'}), 400
    except Exception as e:
        print(f"Auth callback error: {e}")
        return jsonify({'success': False, 'error': 'Authentication failed'}), 500


# Keep your existing Google callback for backward compatibility
@app.route('/auth/google/callback', methods=['POST'])
def google_callback():
    """Handle Google OAuth callback (legacy route)"""
    try:
        # Get the Firebase ID token from the request
        id_token = request.json.get('idToken')

        if not id_token:
            return jsonify({'error': 'No ID token provided'}), 400

        # Verify the ID token with Firebase Admin
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']

        # Get user info from Firebase
        user = auth.get_user(uid)

        # Store user info in session
        session['user'] = {
            'uid': uid,
            'name': user.display_name or user.email,
            'email': user.email,
            'auth_type': 'google',
            'photo_url': user.photo_url
        }

        return jsonify({'success': True, 'redirect': url_for('home')})

    except Exception as e:
        print(f"Google auth error: {e}")
        return jsonify({'error': 'Authentication failed'}), 400


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect('/')


@app.route('/login')
def choose_login():
    """Redirect to Google OAuth - This will be handled by frontend Firebase"""
    return render_template('Login.html',
                           firebase_api_key=FIREBASE_WEB_API_KEY)


@app.route('/profile')
@login_required
def profile():
    """User profile page (example of protected route)"""
    return render_template('profile.html', user=session['user'])


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page (example of protected route)"""
    return render_template('dashboard.html', user=session['user'])


# API endpoint to get current user info
@app.route('/api/user')
def get_user():
    if 'user' in session:
        return jsonify(session['user'])
    return jsonify({'error': 'Not authenticated'}), 401


# Add error handlers for better debugging
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Route not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True)