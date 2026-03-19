from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    city       = db.Column(db.String(100), default='Unknown')
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    logs       = db.relationship('CarbonLog', backref='user', lazy=True)
    badges     = db.relationship('Badge', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.name}>'


class CarbonLog(db.Model):
    __tablename__ = 'carbon_logs'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date       = db.Column(db.Date, nullable=False)
    total_co2  = db.Column(db.Float, nullable=False)
    transport  = db.Column(db.Float, default=0.0)
    food       = db.Column(db.Float, default=0.0)
    energy     = db.Column(db.Float, default=0.0)
    shopping   = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CarbonLog {self.date} {self.total_co2} kg>'


class Pledge(db.Model):
    __tablename__ = 'pledges'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pledge_id   = db.Column(db.String(10), nullable=False)
    text        = db.Column(db.String(255))
    co2_saving  = db.Column(db.Float, default=0.0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Pledge {self.pledge_id} by user {self.user_id}>'


class Badge(db.Model):
    __tablename__ = 'badges'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    awarded_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Badge {self.name}>'
