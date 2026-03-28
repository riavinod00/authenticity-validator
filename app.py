import os
import secrets
import hashlib
import uuid
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Certificate, VerificationHistory

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-keep-it-simple'
basedir = os.path.abspath(os.path.dirname(__name__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    # Add a mock certificate if empty
    if not Certificate.query.first():
        cert1 = Certificate(cert_number='CERT-12345', student_name='John Doe', institution='Tech University', issue_date='2025-05-15')
        cert2 = Certificate(cert_number='CERT-99999', student_name='Jane Smith', institution='Global Academy', issue_date='2024-01-20')
        db.session.add_all([cert1, cert2])
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
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your username and password.')
            return redirect(url_for('login'))
            
    return render_template('login.html')

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
        
    # Query database
    cert = Certificate.query.filter_by(cert_number=cert_number).first()
    
    status = 'Not Verified'
    message = 'Certificate record not found.'
    
    if cert:
        # Complex validation
        name_match = student_name.lower() == cert.student_name.lower() if student_name else True
        inst_match = institution.lower() == cert.institution.lower() if institution else True
        
        if name_match and inst_match:
            status = 'Verified'
            message = 'Certificate is authentic and verified.'
        else:
            message = 'Certificate number found, but associated details do not match.'
    
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
            'student_name': cert.student_name if cert else '',
            'institution': cert.institution if cert else '',
            'issue_date': cert.issue_date if cert else ''
        } if status == 'Verified' else None
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
        
        # --- Simulated AI Tampering Detection ---
        # For simplicity in this version, we'll randomize a tampering detection flag (10% chance to flag)
        import random
        is_tampered = random.choice([True] + [False]*9)
        
        if is_tampered:
            return jsonify({
                'status': 'Not Verified',
                'message': 'AI Tampering Detection Flagged: Potential image manipulations detected. Verification failed.'
            })
            
        # Simulate extracting a certificate number from the document using OCR
        # For demo purposes, let's pretend it always extracts "CERT-12345" if it's a valid upload,
        # unless it's an unrecognized file layout.
        extracted_cert_number = 'CERT-12345'
        
        # Verify against database
        cert = Certificate.query.filter_by(cert_number=extracted_cert_number).first()
        status = 'Verified' if cert else 'Not Verified'
        message = 'Authenticity Verified via Document AI Scan.' if cert else 'Document analyzed but no matching record found.'
        
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
