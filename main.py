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


@app.route('/login/google')
def google_login():
    """Redirect to Google OAuth - This will be handled by frontend Firebase"""
    return render_template('google_auth.html',
                           firebase_api_key=FIREBASE_WEB_API_KEY)


@app.route('/auth/google/callback', methods=['POST'])
def google_callback():
    """Handle Google OAuth callback"""
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


@app.route('/login/phone', methods=['GET', 'POST'])
def phone_login():
    """Handle phone number login"""
    if request.method == 'GET':
        return render_template('phone_auth.html',
                               firebase_api_key=FIREBASE_WEB_API_KEY)

    # This will be handled by frontend Firebase for phone auth
    return render_template('phone_auth.html',
                           firebase_api_key=FIREBASE_WEB_API_KEY)


@app.route('/auth/phone/callback', methods=['POST'])
def phone_callback():
    """Handle phone auth callback"""
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
            'name': user.phone_number,
            'phone': user.phone_number,
            'auth_type': 'phone'
        }

        return jsonify({'success': True, 'redirect': url_for('home')})

    except Exception as e:
        print(f"Phone auth error: {e}")
        return jsonify({'error': 'Authentication failed'}), 400


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect('/')


@app.route('/login')
def choose_login():
    return render_template('login.html')


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


if __name__ == '__main__':
    app.run(debug=True)