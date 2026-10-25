"""
Database models for the Office Document Numbering System.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    """
    Represents an authorized user of the system.
    Stores their TOTP secret for Authenticator App login.
    """
    __tablename__ = "users"

    email       = db.Column(db.String(100), primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    totp_secret = db.Column(db.String(32), nullable=True)
    is_setup    = db.Column(db.Boolean, default=False)
    role        = db.Column(db.String(20), default='user')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    # Encrypted AI provider API keys (stored via cryptography.fernet)
    gemini_api_key   = db.Column(db.Text, nullable=True)
    groq_api_key     = db.Column(db.Text, nullable=True)
    deepseek_api_key = db.Column(db.Text, nullable=True)
    allowed_offices  = db.Column(db.String(255), default='ALL', nullable=True) # e.g. 'ALL', 'ESSIC', 'HUEED', 'AIE', or 'ESSIC,AIE'

    def get_allowed_offices_list(self):
        """Returns list of office codes this user is permitted to access."""
        from offices import OFFICE_CONFIGS
        if self.role == 'admin':
            return list(OFFICE_CONFIGS.keys())
        raw = (self.allowed_offices or 'ALL').strip().upper()
        if raw == 'ALL' or not raw:
            return list(OFFICE_CONFIGS.keys())
        offices = [o.strip() for o in raw.split(',') if o.strip()]
        valid = [o for o in offices if o in OFFICE_CONFIGS]
        return valid if valid else ['ESSIC']

    def can_access_office(self, office_code):
        """Check if user can access a specific office code."""
        if self.role == 'admin':
            return True
        if not office_code:
            return False
        return office_code.upper() in self.get_allowed_offices_list()

    def __repr__(self):
        return f"<User {self.email}>"


class Document(db.Model):
    """
    Represents a processed office document record.
    Stores the generated code number and file references.
    """
    __tablename__ = "documents"

    id               = db.Column(db.Integer, primary_key=True)
    serial_number    = db.Column(db.Integer, nullable=False)          # e.g. 31
    full_code        = db.Column(db.String(100), nullable=False)      # e.g. 0031 ESSIC 05-2026
    office_code      = db.Column(db.String(20), nullable=False, default='ESSIC', index=True) # e.g. ESSIC, HUEED, AIE
    month            = db.Column(db.Integer, nullable=False)
    year             = db.Column(db.Integer, nullable=False)
    filename         = db.Column(db.String(255), nullable=False)      # original uploaded filename
    file_title       = db.Column(db.String(255), nullable=True)       # user provided title
    generated_filename = db.Column(db.String(255), nullable=True)     # filename of modified doc
    generated_pdf_filename = db.Column(db.String(255), nullable=True) # filename of generated PDF
    username         = db.Column(db.String(100), nullable=True)       # person who generated
    email            = db.Column(db.String(100), nullable=True)       # person who generated
    status           = db.Column(db.String(50), default='pending')    # pending, approved
    doc_type         = db.Column(db.String(20), nullable=True)        # "letter" or "request"
    sender           = db.Column(db.Text, nullable=True)
    sender_position  = db.Column(db.Text, nullable=True)
    recipient        = db.Column(db.Text, nullable=True)
    subject          = db.Column(db.Text, nullable=True)
    holder_name      = db.Column(db.Text, nullable=True)
    position         = db.Column(db.Text, nullable=True)
    is_internal      = db.Column(db.Boolean, default=False)
    manager_is_sender = db.Column(db.Boolean, default=False)
    raw_draft        = db.Column(db.Text, nullable=True)
    generated_body   = db.Column(db.Text, nullable=True)
    ai_model         = db.Column(db.String(100), nullable=True)
    sharepoint_url   = db.Column(db.Text, nullable=True)              # direct link to file on OneDrive/SharePoint
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    # Tracking & Response fields (Internal correspondence tracking)
    is_sent               = db.Column(db.Boolean, default=False)
    sent_date             = db.Column(db.DateTime, nullable=True)
    sent_method           = db.Column(db.String(50), nullable=True)          # e.g. internal_hand, internal_messenger, internal_email, internal_portal
    sent_by               = db.Column(db.String(100), nullable=True)         # person who dispatched/delivered
    received_by           = db.Column(db.String(100), nullable=True)         # person who received the sent document internally
    sent_notes            = db.Column(db.Text, nullable=True)                # notes/delivery details
    requires_response     = db.Column(db.Boolean, default=False)
    response_deadline     = db.Column(db.Date, nullable=True)
    response_status       = db.Column(db.String(50), default='not_sent')     # not_sent, awaiting_response, no_response_needed, received
    response_date         = db.Column(db.DateTime, nullable=True)
    response_ref          = db.Column(db.String(100), nullable=True)         # incoming letter/reply reference number
    response_summary      = db.Column(db.Text, nullable=True)                # summary of reply
    response_file         = db.Column(db.String(255), nullable=True)         # uploaded response file (PDF, docx, img)
    response_received_by  = db.Column(db.String(100), nullable=True)         # who logged the incoming response
    followup_notes        = db.Column(db.Text, nullable=True)

    @property
    def is_overdue(self):
        if self.requires_response and self.response_status == 'awaiting_response' and self.response_deadline:
            from datetime import date
            return self.response_deadline < date.today()
        return False

    @property
    def days_until_deadline(self):
        if self.response_deadline:
            from datetime import date
            delta = self.response_deadline - date.today()
            return delta.days
        return None

    def __repr__(self):
        return f"<Document id={self.id} code={self.full_code}>"


class Contact(db.Model):
    """
    Represents a contact (sender or recipient) to be used for auto-completing fields.
    """
    __tablename__ = "contacts"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(255), nullable=False)
    type        = db.Column(db.String(50), nullable=True) # e.g. 'sender', 'recipient'
    office_code = db.Column(db.String(20), nullable=True, default='ESSIC')
    holder_name = db.Column(db.String(255), nullable=True)
    position    = db.Column(db.String(255), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Contact id={self.id} name={self.name}>"


class KeepAlive(db.Model):
    """
    Heartbeat table to register regular write activity and prevent database pausing.
    """
    __tablename__ = "keep_alive"

    id         = db.Column(db.Integer, primary_key=True)
    pinged_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    note       = db.Column(db.String(100), default="automated heartbeat ping")

    def __repr__(self):
        return f"<KeepAlive pinged_at={self.pinged_at}>"
