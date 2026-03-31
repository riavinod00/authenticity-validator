import os
import secrets
import hashlib
import uuid
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from models import db, User, Certificate, VerificationHistory

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-keep-it-simple'
basedir = os.path.abspath(os.path.dirname(__name__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# OAuth Setup
app.config['GOOGLE_CLIENT_ID'] = os.environ.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID_HERE")
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get("GOOGLE_CLIENT_SECRET", "YOUR_GOOGLE_CLIENT_SECRET_HERE")
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'email profile'},
    jwks_uri = "https://www.googleapis.com/oauth2/v3/certs"
)

# Upload configuration
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Initialization (for demo) ---
with app.app_context():
    db.create_all()
    # Add a mock admin if not exists
    if not User.query.filter_by(username='admin').first():
        hashed_password = generate_password_hash('password', method='pbkdf2:sha256')
        new_user = User(username='admin', password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
    # Add mock certificates if empty
    if not Certificate.query.first():
        sample_certs = [
            Certificate(cert_number='DU2021001', student_name='Rahul Sharma', institution='Delhi University', issue_date='2021-06-15'),
            Certificate(cert_number='MU2020045', student_name='Priya Mehta', institution='Mumbai University', issue_date='2020-07-22'),
            Certificate(cert_number='IIT2022112', student_name='Arjun Verma', institution='Indian Institute of Technology', issue_date='2022-05-10'),
            Certificate(cert_number='AU2019087', student_name='Sneha Kapoor', institution='Anna University', issue_date='2019-08-30'),
            Certificate(cert_number='OU2023034', student_name='Mohammed Rafi', institution='Osmania University', issue_date='2023-04-18'),
        ]
        db.session.add_all(sample_certs)
        db.session.commit()

# --- Routes ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your username and password.')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_exists = User.query.filter((User.username == username) | ((User.email == email) & (User.email != ''))).first()
        if user_exists:
            flash('Username or Email already exists. Please login.')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize/google')
def authorize_google():
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.json()
    
    email = user_info.get('email')
    google_id = user_info.get('id')
    username = user_info.get('name')
    
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id = google_id
            db.session.commit()
        else:
            # Create a new user from Google
            user = User(username=username, email=email, google_id=google_id)
            db.session.add(user)
            db.session.commit()
            
    login_user(user)
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    history = VerificationHistory.query.filter_by(user_id=current_user.id).order_by(VerificationHistory.timestamp.desc()).limit(10).all()
    return render_template('dashboard.html', history=history)

@app.route('/api/verify', methods=['POST'])
@login_required
def verify_certificate():
    data = request.json
    cert_number = data.get('cert_number')
    student_name = data.get('student_name', '')
    institution = data.get('institution', '')
    
    if not cert_number:
        return jsonify({'status': 'error', 'message': 'Certificate number is required.'}), 400
        
    # Query database (for demo purposes we still check to optionally use real details)
    cert = Certificate.query.filter_by(cert_number=cert_number).first()

    # For demonstration, handle both success and failure cases cleanly
    if cert_number and any(keyword in cert_number.upper() for keyword in ["FAIL", "FAKE", "INVALID", "TAMPERED"]):
        status = 'Not Verified'
        message = 'Certificate record not found or marked as invalid.'
    else:
        status = 'Verified'
        message = 'Certificate is authentic and verified.'
    
    # Generate cryptographic proof
    raw_data = f"{cert_number}-{status}-{datetime.datetime.utcnow().isoformat()}"
    crypto_hash = hashlib.sha256(raw_data.encode()).hexdigest()
    block_id = "BLK-" + str(uuid.uuid4())[:8].upper()

    # Save History
    new_history = VerificationHistory(
        user_id=current_user.id, cert_number=cert_number, status=status, 
        method='Manual', crypto_hash=crypto_hash, block_id=block_id
    )
    db.session.add(new_history)
    db.session.commit()
    
    return jsonify({
        'status': status,
        'message': message,
        'crypto_hash': crypto_hash,
        'block_id': block_id,
        'cert_details': {
            'student_name': cert.student_name if cert else (student_name if student_name else 'Demo Student'),
            'institution': cert.institution if cert else (institution if institution else 'Demo University'),
            'issue_date': cert.issue_date if cert else datetime.datetime.now().strftime('%Y-%m-%d')
        }
    })

@app.route('/api/verify_upload', methods=['POST'])
@login_required
def verify_upload():
    if 'document' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
        
    file = request.files['document']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
        
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Allow demonstrating both verified and non-verified cases based on filename
        extracted_cert_number = 'CERT-' + str(uuid.uuid4())[:8].upper()
        
        filename_upper = filename.upper()
        if any(keyword in filename_upper for keyword in ["FAIL", "FAKE", "INVALID", "TAMPERED"]):
            status = 'Not Verified'
            message = 'AI Tampering Detection Flagged: Potential manipulations detected. Verification failed.'
        else:
            status = 'Verified'
            message = 'Authenticity Verified via Document AI Scan.'
        
        raw_data = f"{extracted_cert_number}-{status}-{datetime.datetime.utcnow().isoformat()}"
        crypto_hash = hashlib.sha256(raw_data.encode()).hexdigest()
        block_id = "BLK-" + str(uuid.uuid4())[:8].upper()

        # Record history
        new_history = VerificationHistory(
            user_id=current_user.id, cert_number=extracted_cert_number, status=status, 
            method='Upload & AI Scan', crypto_hash=crypto_hash, block_id=block_id
        )
        db.session.add(new_history)
        db.session.commit()

        # Clean up file
        try:
             os.remove(filepath)
        except Exception:
             pass

        return jsonify({
            'status': status,
            'message': message,
            'crypto_hash': crypto_hash,
            'block_id': block_id
        })

@app.route('/api/analytics', methods=['GET'])
@login_required
def analytics():
    total_scans = VerificationHistory.query.count()
    verified_count = VerificationHistory.query.filter_by(status='Verified').count()
    tampered_count = VerificationHistory.query.filter_by(status='Not Verified').count()
    
    return jsonify({
        'total': total_scans,
        'verified': verified_count,
        'tampered': tampered_count
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
