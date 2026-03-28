from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cert_number = db.Column(db.String(50), unique=True, nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    institution = db.Column(db.String(150), nullable=False)
    issue_date = db.Column(db.String(20), nullable=False)

class VerificationHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cert_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)  # Verified or Not Verified
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    method = db.Column(db.String(50), default='Manual')
    crypto_hash = db.Column(db.String(64), nullable=True)
    block_id = db.Column(db.String(64), nullable=True)

    user = db.relationship('User', backref=db.backref('history', lazy=True))
