from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    email       = db.Column(db.String(100), primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    totp_secret = db.Column(db.String(32), nullable=True)
    is_setup    = db.Column(db.Boolean, default=False)
    role        = db.Column(db.String(20), default='user')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Access control fields
    access_essic      = db.Column(db.Boolean, default=False)
    access_faculty    = db.Column(db.Boolean, default=False)
    access_biomedical = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<User {self.email}>"
