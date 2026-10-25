import os
import io
import base64
import jwt
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyotp
import qrcode
from models import db, User

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gateway_super_secret_key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gateway.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Shared secret for SSO JWT generation (must match in the child apps)
SSO_SECRET = os.environ.get("SSO_SECRET", "shared_sso_secret_key_12345_32bytes_long")

# URLs of the 3 systems
SYSTEMS = {
    'essic': {
        'name': 'Essic',
        'url': 'http://127.0.0.1:5001',
        'access_attr': 'access_essic',
        'color': 'primary',
        'icon': 'bi-building-fill-gear',
        'desc': 'Electronic Services & Science Innovation Center.',
        'image': 'assets/tech_bg.jpg'
    },
    'faculty': {
        'name': 'Vice Dean',
        'url': 'http://127.0.0.1:5002',
        'access_attr': 'access_faculty',
        'color': 'success',
        'icon': 'bi-bank2',
        'desc': 'Document numbering and tracking for the Faculty.',
        'image': 'assets/sidebar_bg.jpg'
    },
    'biomedical': {
        'name': 'AIE Department',
        'url': 'http://127.0.0.1:5003',
        'access_attr': 'access_biomedical',
        'color': 'info',
        'icon': 'bi-cpu-fill',
        'desc': 'Specialized system for the Artificial Intelligence Engineering dept.',
        'image': ''
    }
}

db.init_app(app)
with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # Save the intended destination if it came from a child app
            next_url = request.args.get('next')
            if next_url:
                session['next_url'] = next_url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    # If redirected from a child app, it passes '?next=...'
    next_url = request.args.get('next')
    if next_url:
        session['next_url'] = next_url

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash("Please enter your email.", "warning")
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()

        # For the gateway, we'll allow creation if they don't exist, but with 0 access by default.
        # Alternatively, we can restrict to admins. For now, let's create them with no access.
        if not user:
            name = email.split('@')[0]
            totp_secret = pyotp.random_base32()
            # Give first user all access, others no access (just for testing convenience, or just grant access to all for now)
            is_first = User.query.count() == 0
            user = User(
                email=email, 
                name=name, 
                totp_secret=totp_secret, 
                is_setup=False,
                role='admin' if is_first else 'user',
                access_essic=is_first,
                access_faculty=is_first,
                access_biomedical=is_first
            )
            db.session.add(user)
            db.session.commit()

        session['pending_email'] = email

        if not user.is_setup:
            return redirect(url_for('setup'))
        else:
            return redirect(url_for('verify'))

    return render_template('login.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if 'user' in session:
        return redirect(url_for('index'))

    email = session.get('pending_email')
    if not email:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if not user or user.is_setup:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code):
            user.is_setup = True
            db.session.commit()

            session.pop('pending_email', None)
            session['user'] = {'name': user.name, 'email': user.email}
            return redirect(url_for('index'))
        else:
            flash("Invalid code. Please try again.", "danger")

    totp_uri = pyotp.totp.TOTP(user.totp_secret).provisioning_uri(name=email, issuer_name="Gateway SSO")

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template('setup.html', qr_b64=qr_b64, secret=user.totp_secret, email=email)


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'user' in session:
        return redirect(url_for('index'))

    email = session.get('pending_email')
    if not email:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_setup:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code):
            session.pop('pending_email', None)
            session['user'] = {'name': user.name, 'email': user.email}
            return redirect(url_for('index'))
        else:
            flash("Invalid authenticator code. Please try again.", "danger")

    return render_template('verify.html', email=email)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    
    if not user:
        return redirect(url_for('logout'))

    # Check which systems they have access to
    accessible_systems = []
    for sys_id, sys_info in SYSTEMS.items():
        if getattr(user, sys_info['access_attr'], False):
            accessible_systems.append((sys_id, sys_info))

    if len(accessible_systems) == 0:
        return render_template('no_access.html')
    elif len(accessible_systems) == 1:
        # Redirect directly to the single accessible system
        return redirect(url_for('goto_system', sys_id=accessible_systems[0][0]))
    else:
        # Check if we were trying to access a specific system (next_url)
        next_url = session.pop('next_url', None)
        if next_url:
            for sys_id, sys_info in accessible_systems:
                if sys_info['url'] in next_url:
                    return redirect(url_for('goto_system', sys_id=sys_id, next=next_url))

        # Show choice screen
        return render_template('choose.html', systems=accessible_systems)

@app.route("/goto/<sys_id>")
@login_required
def goto_system(sys_id):
    if sys_id not in SYSTEMS:
        return "System not found", 404
        
    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    
    sys_info = SYSTEMS[sys_id]
    if not getattr(user, sys_info['access_attr'], False):
        return "Access denied to this system.", 403
        
    # Generate JWT
    from datetime import timezone
    payload = {
        'email': user.email,
        'name': user.name,
        'exp': datetime.now(timezone.utc) + timedelta(minutes=5)
    }
    token = jwt.encode(payload, SSO_SECRET, algorithm="HS256")
    
    # Destination
    next_url = request.args.get('next')
    dest = next_url if next_url else sys_info['url']
    
    sso_url = f"{sys_info['url']}/sso_login?token={token}&next={dest}"
    return redirect(sso_url)

if __name__ == "__main__":
    app.run(port=5000, debug=True)
