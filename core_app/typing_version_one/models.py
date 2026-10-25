"""
Database models for the ESSIC Document Numbering + AI Generation System.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Document(db.Model):
    __tablename__ = "documents"

    id                 = db.Column(db.Integer, primary_key=True)
    serial_number      = db.Column(db.Integer, nullable=False)
    full_code          = db.Column(db.String(100), nullable=False)
    month              = db.Column(db.Integer, nullable=False)
    year               = db.Column(db.Integer, nullable=False)
    doc_type           = db.Column(db.String(20), nullable=False, default="letter")   # "letter" | "request"
    sender             = db.Column(db.Text, nullable=True)
    recipient          = db.Column(db.Text, nullable=True)
    subject            = db.Column(db.Text, nullable=True)
    raw_draft          = db.Column(db.Text, nullable=True)    # user's free-text draft
    generated_body     = db.Column(db.Text, nullable=True)    # AI-refined Arabic body
    filename           = db.Column(db.String(255), nullable=False)
    generated_filename = db.Column(db.String(255), nullable=True)
    ai_model           = db.Column(db.String(100), nullable=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Document id={self.id} code={self.full_code}>"
