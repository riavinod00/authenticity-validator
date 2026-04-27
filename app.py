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
from dotenv import load_dotenv
import google.generativeai as genai
import base64
from PIL import Image

load_dotenv()

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
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs"
)

# Upload configuration
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Initialization ---
with app.app_context():
    db.create_all()

    if not User.query.filter_by(username='admin').first():
        hashed_password = generate_password_hash('password', method='pbkdf2:sha256')
        new_user = User(username='admin', password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

    if not Certificate.query.first():
        cert1 = Certificate(cert_number='CERT-1CT12CS192', student_name='Ram Govind', institution='Central University', issue_date='2013-05-15')
        cert2 = Certificate(cert_number='CERT-1SP12EC134', student_name='Priya Micheal', institution='State Public University', issue_date='2014-01-20')
        cert3 = Certificate(cert_number='CERT-1DU12EEE167', student_name='Kavitha Nair', institution='Deemed University', issue_date='2023-11-10')
        cert4 = Certificate(cert_number='CERT-1RV12ISE201', student_name='Meera Iyer', institution='R V COLLEGE', issue_date='2015-02-12')
        cert5 = Certificate(cert_number='CERT-1PES12CS192', student_name='Rahul Verma', institution='PES COLLEGE', issue_date='2013-08-30')
        db.session.add_all([cert1, cert2, cert3, cert4, cert5])
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

    cert = Certificate.query.filter_by(cert_number=cert_number).first()

    if cert:
        status = 'Verified'
        message = 'Certificate is authentic and verified.'
    else:
        status = 'Not Verified'
        message = 'Certificate not found in the registry.'

    raw_data = f"{cert_number}-{status}-{datetime.datetime.utcnow().isoformat()}"
    crypto_hash = hashlib.sha256(raw_data.encode()).hexdigest()
    block_id = "BLK-" + str(uuid.uuid4())[:8].upper()

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
            'student_name': cert.student_name if cert else (student_name if student_name else 'Unknown'),
            'institution': cert.institution if cert else (institution if institution else 'Unknown'),
            'issue_date': cert.issue_date if cert else 'N/A'
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

        try:
            # --- Gemini Vision AI Scan ---
            img = Image.open(filepath)
            model = genai.GenerativeModel("gemini-1.5-flash")

            ai_response = model.generate_content([
                img,
                """You are an expert academic certificate validator.
Analyze this certificate image and check for:
1. Official seals or stamps
2. Authorized signatures
3. Consistent fonts and formatting
4. Institution name and branding
5. Issue date, course/degree name, recipient name
6. Any signs of tampering, photoshopping, or inconsistencies

Also extract the certificate number if visible (look for patterns like CERT-XXXX).

Respond in EXACTLY this format:
VERDICT: VERIFIED or NOT VERIFIED
CONFIDENCE: High / Medium / Low
CERT_NUMBER: (extracted cert number or UNKNOWN)
STUDENT_NAME: (extracted name or UNKNOWN)
INSTITUTION: (extracted institution or UNKNOWN)
REASONS:
- reason 1
- reason 2
SUSPICIOUS_ELEMENTS: (list issues or None)"""
            ])

            ai_text = ai_response.text

            # Parse AI response
            def extract_field(label, text):
                for line in text.splitlines():
                    if line.startswith(label):
                        return line.split(':', 1)[-1].strip()
                return 'UNKNOWN'

            ai_verdict    = extract_field('VERDICT', ai_text)
            ai_cert_number = extract_field('CERT_NUMBER', ai_text)
            ai_student_name = extract_field('STUDENT_NAME', ai_text)
            ai_institution  = extract_field('INSTITUTION', ai_text)
            ai_confidence   = extract_field('CONFIDENCE', ai_text)

            # Cross-check with database
            cert_check = None
            if ai_cert_number != 'UNKNOWN':
                cert_check = Certificate.query.filter_by(cert_number=ai_cert_number).first()

            # Final verdict
            if ai_verdict == 'VERIFIED' and cert_check:
                status = 'Verified'
                message = f'AI Scan passed ({ai_confidence} confidence) and certificate found in registry.'
            elif ai_verdict == 'VERIFIED' and not cert_check:
                status = 'Not Verified'
                message = 'AI Scan passed but certificate not found in registry.'
            else:
                status = 'Not Verified'
                message = f'AI Scan flagged this certificate as suspicious ({ai_confidence} confidence).'

        except Exception as e:
            status = 'Not Verified'
            message = f'AI scan failed: {str(e)}'
            ai_cert_number  = 'UNKNOWN'
            ai_student_name = 'Unknown'
            ai_institution  = 'Unknown'
            cert_check = None

        # Crypto proof
        raw_data = f"{ai_cert_number}-{status}-{datetime.datetime.utcnow().isoformat()}"
        crypto_hash = hashlib.sha256(raw_data.encode()).hexdigest()
        block_id = "BLK-" + str(uuid.uuid4())[:8].upper()

        # Save history
        new_history = VerificationHistory(
            user_id=current_user.id,
            cert_number=ai_cert_number,
            status=status,
            method='Upload & AI Scan',
            crypto_hash=crypto_hash,
            block_id=block_id
        )
        db.session.add(new_history)
        db.session.commit()

        # Cleanup
        try:
            os.remove(filepath)
        except Exception:
            pass

        return jsonify({
            'status': status,
            'message': message,
            'crypto_hash': crypto_hash,
            'block_id': block_id,
            'cert_details': {
                'student_name': cert_check.student_name if cert_check else ai_student_name,
                'institution': cert_check.institution if cert_check else ai_institution,
                'issue_date': cert_check.issue_date if cert_check else 'N/A'
            }
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
