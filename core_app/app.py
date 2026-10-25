import base64
import io
import os
import jwt
import sys
from datetime import datetime
from functools import wraps

import pyotp
import qrcode
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, abort, session, \
    jsonify
from sqlalchemy import true
from werkzeug.utils import secure_filename

# Allow imports from project root and current dir
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Document, User, Contact, KeepAlive
from services.numbering import get_next_serial, build_full_code
from services.word_editor import replace_placeholder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
load_dotenv()

# ─── App Configuration ────────────────────────────────────────────────────────
import tempfile
if os.environ.get("VERCEL") == "1":
    DATA_DIR = os.environ.get("DATA_DIR") or tempfile.gettempdir()
else:
    DATA_DIR = os.environ.get("DATA_DIR") or BASE_DIR
DATA_DIR = os.path.abspath(DATA_DIR)
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
GENERATED_FOLDER = os.path.join(DATA_DIR, "generated")
RESPONSES_FOLDER = os.path.join(DATA_DIR, "uploads", "responses")
PREVIEWS_FOLDER = os.path.join(DATA_DIR, "generated", "previews")
os.makedirs(PREVIEWS_FOLDER, exist_ok=True)
ALLOWED_EXT = {"docx"}
ALLOWED_RESPONSE_EXT = {"pdf", "docx", "doc", "jpg", "jpeg", "png"}

def cleanup_old_previews():
    """
    Deletes preview files from PREVIEWS_FOLDER that were created on previous days
    or are older than 18 hours. Also cleans up on OneDrive.
    """
    now = datetime.now()
    if os.path.exists(PREVIEWS_FOLDER):
        for fname in os.listdir(PREVIEWS_FOLDER):
            fpath = os.path.join(PREVIEWS_FOLDER, fname)
            if os.path.isfile(fpath):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime.date() < now.date() or (now - mtime).total_seconds() > 18 * 3600:
                        os.remove(fpath)
                        try:
                            from services.onedrive import delete_file_from_share
                            delete_file_from_share(fname, is_preview=True)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[Cleanup Previews Error] {e}")

app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'essic_session'
app.secret_key = "essic-doc-numbering-secret-2026"
supabase_url = os.environ.get("SUPABASE_DB_URL")
if not supabase_url:
    raise RuntimeError("SUPABASE_DB_URL environment variable is required and not set.")

if supabase_url.startswith("postgres://"):
    supabase_url = supabase_url.replace("postgres://", "postgresql+psycopg://", 1)
elif supabase_url.startswith("postgresql://"):
    supabase_url = supabase_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = supabase_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["GENERATED_FOLDER"] = GENERATED_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB limit

# Ensure folders exist
RESPONSES_FOLDER = os.path.join(DATA_DIR, "uploads", "responses")
ALLOWED_RESPONSE_EXT = {"pdf", "docx", "doc", "jpg", "jpeg", "png"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(RESPONSES_FOLDER, exist_ok=True)

def allowed_response_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_RESPONSE_EXT

_admin_raw = os.environ.get("ADMIN_EMAILS", "mkhassan@horus.edu.eg,aelshafee@horus.edu.eg")
ADMIN_EMAILS = {e.strip().lower() for e in _admin_raw.split(",") if e.strip()}

# Allowed users — comma-separated emails in .env
_allowed_raw = os.environ.get("ALLOWED_EMAILS", "mkhassan@horus.edu.eg,aelshafee@horus.edu.eg")
ALLOWED_EMAILS = {e.strip().lower() for e in _allowed_raw.split(",") if e.strip()}


GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:5000")
SSO_SECRET = os.environ.get("SSO_SECRET", "shared_sso_secret_key_12345_32bytes_long")
SYSTEM_TEMPLATE_FILENAME = os.environ.get("SYSTEM_TEMPLATE_FILENAME", "template_essic.docx")
SYSTEM_TEMPLATE_STEM = SYSTEM_TEMPLATE_FILENAME.rsplit(".", 1)[0]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def is_current_user_admin(user_email=None):
    if not user_email:
        user_email = session.get('user', {}).get('email', '')
    if not user_email:
        return False
    if user_email in ADMIN_EMAILS:
        return True
    user = User.query.filter_by(email=user_email).first()
    return user is not None and user.role == 'admin'


_last_preview_cleanup_date = None

@app.before_request
def check_daily_preview_cleanup():
    global _last_preview_cleanup_date
    today = datetime.now().date()
    if _last_preview_cleanup_date != today:
        _last_preview_cleanup_date = today
        cleanup_old_previews()


def get_user_allowed_offices(user_email=None):
    """Returns list of office codes allowed for the current or specified user."""
    from offices import OFFICE_CONFIGS
    if not user_email:
        user_email = session.get('user', {}).get('email', '')
    if not user_email:
        return list(OFFICE_CONFIGS.keys())
    if is_current_user_admin(user_email):
        return list(OFFICE_CONFIGS.keys())
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return list(OFFICE_CONFIGS.keys())
    return user.get_allowed_offices_list()


def user_can_access_office(office_code, user_email=None):
    """Check if user is authorized to access a given department."""
    if is_current_user_admin(user_email):
        return True
    if not office_code:
        return False
    allowed = get_user_allowed_offices(user_email)
    return office_code.upper() in allowed


@app.context_processor
def inject_globals():
    is_admin = is_current_user_admin()
    from offices import get_current_office, set_current_office, OFFICE_CONFIGS

    user_email = session.get('user', {}).get('email', '')
    if user_email:
        allowed_offices_list = get_user_allowed_offices(user_email)
    else:
        allowed_offices_list = list(OFFICE_CONFIGS.keys())

    # Enforce active office strictly within user's allowed offices
    curr_office = get_current_office()
    if allowed_offices_list and curr_office['code'] not in allowed_offices_list:
        set_current_office(allowed_offices_list[0])
        curr_office = get_current_office()

    # Filtered office configs mapping for this user
    user_offices_dict = {
        code: conf for code, conf in OFFICE_CONFIGS.items()
        if code in allowed_offices_list
    }

    from services.onedrive import get_word_online_url
    return dict(
        is_admin=is_admin,
        get_word_online_url=get_word_online_url,
        GATEWAY_URL=GATEWAY_URL,
        SYSTEM_OFFICE_CODE=curr_office['code'],
        SYSTEM_ORG_NAME=curr_office['org_name'],
        SYSTEM_PREVIEW_BG=curr_office['preview_bg'],
        SYSTEM_PREVIEW_FOOTER=curr_office['preview_footer'],
        SYSTEM_PREVIEW_PT=curr_office['preview_pt'],
        CURRENT_OFFICE=curr_office,
        ALL_OFFICES=OFFICE_CONFIGS,
        USER_ALLOWED_OFFICES=allowed_offices_list,
        USER_OFFICES=user_offices_dict
    )


@app.route('/switch_office/<office_code>')
def switch_office(office_code):
    office_code = office_code.upper()
    if not user_can_access_office(office_code):
        flash(f"ليس لديك صلاحية للدخول إلى قسم {office_code} (Permission Denied).", "danger")
        return redirect(url_for('portal'))

    from offices import set_current_office
    set_current_office(office_code)
    flash(f"Switched active department to {office_code}", "info")
    next_url = request.args.get('next')
    if next_url:
        return redirect(next_url)
    ref = request.referrer
    if ref and '/switch_office/' not in ref and '/portal' not in ref:
        return redirect(ref)
    return redirect(url_for('index'))


@app.route('/portal')
@app.route('/hub')
@login_required
def portal():
    """Systems Portal / Home Page for selecting and managing departments."""
    from offices import OFFICE_CONFIGS, get_current_office
    curr_office = get_current_office()

    office_stats = {}
    for code in OFFICE_CONFIGS:
        total_docs = Document.query.filter_by(office_code=code).count()
        total_sent = Document.query.filter_by(office_code=code, is_sent=True).count()
        awaiting = Document.query.filter_by(office_code=code, is_sent=True, response_status='awaiting_response').count()
        received = Document.query.filter_by(office_code=code, response_status='received').count()
        office_stats[code] = {
            'total_docs': total_docs,
            'total_sent': total_sent,
            'awaiting': awaiting,
            'received': received
        }

    global_total = Document.query.count()
    global_awaiting = Document.query.filter_by(is_sent=True, response_status='awaiting_response').count()
    global_received = Document.query.filter_by(response_status='received').count()

    return render_template(
        "portal.html",
        office_stats=office_stats,
        global_total=global_total,
        global_awaiting=global_awaiting,
        global_received=global_received,
        CURRENT_OFFICE=curr_office,
        ALL_OFFICES=OFFICE_CONFIGS
    )



def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_current_user_admin():
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('documents'))
        return f(*args, **kwargs)

    return decorated_function


db.init_app(app)

with app.app_context():
    db.create_all()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/api/keep-alive', methods=['GET', 'POST'])
def api_keep_alive():
    """
    Automated keep-alive endpoint.
    Performs a write operation into the database to generate active SQL traffic
    and prevent Supabase from pausing the project due to inactivity.
    """
    results = {}
    try:
        ping = KeepAlive.query.filter_by(id=1).first()
        now = datetime.utcnow()
        if not ping:
            ping = KeepAlive(id=1, pinged_at=now, note=f"Automated keep-alive ping at {now.isoformat()}")
            db.session.add(ping)
        else:
            ping.pinged_at = now
            ping.note = f"Automated keep-alive ping at {now.isoformat()}"
        db.session.commit()
        results["primary_db"] = {"status": "success", "pinged_at": now.isoformat()}
    except Exception as e:
        db.session.rollback()
        results["primary_db"] = {"status": "error", "error": str(e)}

    from sqlalchemy import create_engine, text
    extra_env_keys = ["SUPABASE_DB_URL_ESSIC", "SUPABASE_DB_URL_VICE_DEAN", "SUPABASE_DB_URL_AIE"]
    for key in extra_env_keys:
        val = os.environ.get(key)
        if val and val != os.environ.get("SUPABASE_DB_URL"):
            if val.startswith("postgres://"):
                val = val.replace("postgres://", "postgresql+psycopg://", 1)
            elif val.startswith("postgresql://"):
                val = val.replace("postgresql://", "postgresql+psycopg://", 1)
            try:
                eng = create_engine(val, connect_args={"connect_timeout": 10})
                with eng.connect() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS keep_alive (id INT PRIMARY KEY, pinged_at TIMESTAMP, note TEXT);"))
                    conn.execute(text("INSERT INTO keep_alive (id, pinged_at, note) VALUES (1, NOW(), 'keep-alive') ON CONFLICT (id) DO UPDATE SET pinged_at = NOW();"))
                    conn.commit()
                results[key] = "success"
            except Exception as ex:
                results[key] = f"error: {ex}"

    return jsonify({"status": "completed", "results": results}), 200


@app.route('/sso_login')
def sso_login():
    token = request.args.get('token')
    next_url = request.args.get('next')
    if not token:
        return redirect(f"{GATEWAY_URL}/login")
    try:
        data = jwt.decode(token, SSO_SECRET, algorithms=["HS256"])
        session['user'] = {'name': data.get('name', ''), 'email': data['email']}
        if next_url:
            return redirect(next_url)
        return redirect(url_for('index'))
    except Exception as e:
        return f"SSO Error: {e}", 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash("Please enter your email.", "warning")
            return redirect(url_for('login'))

        # Check if user exists in DB
        user = User.query.filter_by(email=email).first()

        if not user and email not in ALLOWED_EMAILS:
            flash("This email address is not authorized to access this system. Please ask an admin to add you.",
                  "danger")
            return redirect(url_for('login'))

        if not user:
            # First time logging in: Create user and generate TOTP secret
            name = email.split('@')[0]
            totp_secret = pyotp.random_base32()
            is_admin = email in ADMIN_EMAILS
            user = User(email=email, name=name, totp_secret=totp_secret, is_setup=False,
                        role='admin' if is_admin else 'user')
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

    # Generate QR code URL
    totp_uri = pyotp.totp.TOTP(user.totp_secret).provisioning_uri(name=email, issuer_name="ESSIC Document System")

    # Generate QR code image as base64
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
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Upload page — user uploads a .docx template and gets a numbered document, or generates directly from default template."""
    from offices import get_current_office, set_current_office
    curr_office = get_current_office()
    office_code = curr_office['code']
    if not user_can_access_office(office_code):
        allowed = get_user_allowed_offices()
        if allowed:
            set_current_office(allowed[0])
            curr_office = get_current_office()
            office_code = curr_office['code']
        else:
            flash(f"You do not have access to department {office_code}.", "danger")
            return redirect(url_for('portal'))
    template_filename = curr_office['template']

    if request.method == "POST":
        action_type = request.form.get("action_type", "upload")

        if action_type == "upload":
            file = request.files.get("docx_file")

            if not file or file.filename == "":
                flash("Please select a Word document (.docx) to upload.", "warning")
                return redirect(url_for("index"))

            if not allowed_file(file.filename):
                flash("Only .docx files are accepted.", "danger")
                return redirect(url_for("index"))

            file_title = request.form.get("file_title", "").strip()

            # Save uploaded file
            original_name = secure_filename(file.filename)
            upload_path = os.path.join(UPLOAD_FOLDER, original_name)
            file.save(upload_path)

        elif action_type == "direct_template":
            file_title = request.form.get("file_title", "Direct Template Report").strip()
            upload_path = os.path.join(BASE_DIR, template_filename)
            original_name = template_filename
            
            if not os.path.exists(upload_path):
                flash(f"Default template ({template_filename}) not found.", "danger")
                return redirect(url_for("index"))
        elif action_type == "reserve":
            file_title = request.form.get("file_title", "Reserved Serial").strip()
            upload_path = os.path.join(BASE_DIR, template_filename)
            original_name = template_filename
            
            if not os.path.exists(upload_path):
                flash(f"Default template ({template_filename}) not found.", "danger")
                return redirect(url_for("index"))
        else:
            flash("Invalid action.", "danger")
            return redirect(url_for("index"))

        # Generate document number
        now = datetime.now()
        month, year = now.month, now.year
        serial = get_next_serial(month, year, office_code=office_code)
        full_code = build_full_code(serial, month, year, office_code=office_code)

        # Process Word document
        if action_type == "direct_template":
            timestamp = now.strftime("%Y%md_%H%M%S")
            generated_name = f"Direct_{timestamp}_{full_code.replace(' ', '_')}.docx"
        elif action_type == "reserve":
            timestamp = now.strftime("%Y%md_%H%M%S")
            generated_name = f"Reserved_{timestamp}_{full_code.replace(' ', '_')}.docx"
        else:
            generated_name = f"{full_code.replace(' ', '_')}.docx"
            
        generated_path = os.path.join(GENERATED_FOLDER, generated_name)

        try:
            if action_type == "upload" or action_type == "reserve":
                replace_placeholder(upload_path, generated_path, full_code)
            elif action_type == "direct_template":
                from services.word_editor import replace_placeholders
                from services.ai_generator import normalize_recipient
                
                recipient = request.form.get("recipient", "")
                subject = request.form.get("subject", "")
                holder_name = request.form.get("holder_name", "")
                position = request.form.get("position", "")
                full_body = request.form.get("full_body", "")
                sender = request.form.get("sender", "")
                is_internal = request.form.get("is_internal") == "1"
                manager_is_sender = request.form.get("manager_is_sender") == "1"

                import re
                def remove_office_code(text):
                    if not text: return ""
                    for code in ['ESSIC', 'HUEED', 'AIE']:
                        text = re.sub(rf'\(\s*{code}\s*\)', '', text, flags=re.IGNORECASE)
                        text = re.sub(rf'{code}', '', text, flags=re.IGNORECASE)
                    return text.strip()

                default_sender = curr_office.get('manager_title', '')
                
                # Unconditionally remove office text from all text fields
                recipient = remove_office_code(recipient)
                subject = remove_office_code(subject)
                holder_name = remove_office_code(holder_name)
                position = remove_office_code(position)
                full_body = remove_office_code(full_body)
                sender = remove_office_code(sender)
                default_sender = remove_office_code(default_sender)

                # Determine sender value for template
                sender_value = ""
                sender_top = f"\u202A{sender}\u202C" if sender else f"\u202A{default_sender}\u202C"
                
                # If external OR manager is sender -> sender_value stays empty (manager signature kept)
                # Only if internal AND NOT manager -> employee signature used
                if is_internal and not manager_is_sender and sender:
                    sender_value = f"\u202Bمقدمه لسيادتكم\n{sender}\u202C"

                # Parse tables_data
                import json
                raw_tables = request.form.get("tables_data") or request.form.get("table_data") or "[]"
                try:
                    tables_data = json.loads(raw_tables)
                    if tables_data and isinstance(tables_data, list):
                        if len(tables_data) > 0 and isinstance(tables_data[0], list) and len(tables_data[0]) > 0 and not isinstance(tables_data[0][0], list):
                            tables_data = [tables_data]
                except Exception:
                    tables_data = []

                # Parse and save uploaded images
                image_paths = []
                temp_image_files = []
                images = request.files.getlist("images")
                if images:
                    import uuid
                    for img in images:
                        if img and img.filename:
                            ext = img.filename.rsplit('.', 1)[-1].lower() if '.' in img.filename else 'png'
                            temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4().hex}.{ext}")
                            img.save(temp_path)
                            temp_image_files.append(temp_path)
                            image_paths.append(temp_path)
                        else:
                            image_paths.append(None)

                # Parse image_sizes (default 1x1 inch)
                image_sizes = []
                raw_sizes = request.form.get("image_sizes")
                if raw_sizes:
                    try:
                        image_sizes = json.loads(raw_sizes)
                    except Exception:
                        image_sizes = []
                if not image_sizes:
                    widths = request.form.getlist("image_widths")
                    heights = request.form.getlist("image_heights")
                    for w, h in zip(widths, heights):
                        try:
                            image_sizes.append({"width": float(w or 1.0), "height": float(h or 1.0)})
                        except Exception:
                            image_sizes.append({"width": 1.0, "height": 1.0})

                remove_manager = (is_internal and not manager_is_sender)
                replace_placeholders(upload_path, generated_path, {
                    "{{CODE_NUMBER}}": full_code,
                    "{{SEND_TO}}": ("\u202A" + normalize_recipient(recipient) + "\u202C") if recipient else "",
                    "{{SUBJECT}}": "\u202A" + subject + "\u202C",
                    "{{STACK_HOLDER}}": "\u202B" + holder_name + "\u202C",
                    "{{POSITION}}": "\u202B" + position + "\u202C",
                    "{{BODY_TEXT}}": "\u202B" + full_body + "\u202C",
                    "{{SENDER}}": sender_value,
                    "{{SENDER_TOP}}": sender_top,
                    "{{ESSIC}}": "",
                    "{{HUEED}}": "",
                    "{{AIE}}": "",
                }, remove_manager_sig=remove_manager, tables_data=tables_data, image_paths=image_paths, image_sizes=image_sizes)

                # Cleanup temp image files
                for p in temp_image_files:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                
            # Attempt PDF generation
            from services.pdf_converter import convert_docx_to_pdf
            generated_pdf_name = generated_name.replace(".docx", ".pdf")
            generated_pdf_path = os.path.join(GENERATED_FOLDER, generated_pdf_name)
            pdf_success = convert_docx_to_pdf(generated_path, generated_pdf_path)
            if not pdf_success:
                generated_pdf_name = None
        except Exception as e:
            flash(f"Error processing document: {e}", "danger")
            return redirect(url_for("index"))

        user_data = session.get('user', {})
        user_email = user_data.get('email', '')
        is_admin = is_current_user_admin()

        status = 'approved' if is_admin else 'pending'
        if action_type == "reserve":
            status = 'pending'

        if generated_name:
            # Upload to OneDrive using the onedrive service
            from services.onedrive import upload_file_to_share, LAST_ERROR
            if os.environ.get("ONEDRIVE_SHARE_URL"):
                success = upload_file_to_share(generated_path, generated_name)
                if generated_pdf_name:
                    upload_file_to_share(generated_pdf_path, generated_pdf_name)
                
                # Cleanup preview
                old_preview = session.pop('last_preview_filename', None)
                if not old_preview and user_email:
                    old_preview = f"Preview_{secure_filename(user_email.split('@')[0])}.docx"
                if old_preview:
                    local_preview = os.path.join(PREVIEWS_FOLDER, old_preview)
                    if os.path.exists(local_preview):
                        try:
                            os.remove(local_preview)
                        except Exception:
                            pass
                    from services.onedrive import delete_file_from_share
                    delete_file_from_share(old_preview, is_preview=True)
                
                if success:
                    if status == 'approved':
                        flash("Document generated and successfully uploaded to OneDrive!", "success")
                    else:
                        flash("Document generated and uploaded to OneDrive. Pending admin approval.", "info")
                else:
                    import services.onedrive as od
                    if status == 'approved':
                        flash(f"Document generated locally, but OneDrive upload failed. Error: {od.LAST_ERROR}", "danger")
                    else:
                        flash(f"Document pending, but OneDrive upload failed. Error: {od.LAST_ERROR}", "danger")
            else:
                if status == 'approved':
                    flash("Document generated locally. (OneDrive upload not configured.)", "info")
                else:
                    flash("Document uploaded successfully. It is pending admin approval.", "info")

        # Save record to database
        doc = Document(
            serial_number=serial,
            full_code=full_code,
            month=month,
            year=year,
            filename=original_name,
            file_title=file_title,
            generated_filename=generated_name,
            generated_pdf_filename=generated_pdf_name,
            username=user_data.get('name', 'Unknown'),
            email=user_email,
            status=status,
            office_code=office_code
        )
            
        if action_type == "direct_template":
            doc.doc_type = "direct"
            doc.sender = request.form.get("sender", "")
            doc.recipient = request.form.get("recipient", "")
            doc.subject = request.form.get("subject", "")
            doc.holder_name = request.form.get("holder_name", "")
            doc.position = request.form.get("position", "")
            doc.is_internal = request.form.get("is_internal") == "1"
            doc.manager_is_sender = request.form.get("manager_is_sender") == "1"
            doc.generated_body = request.form.get("full_body", "")

            # Auto-save contact info
            if doc.recipient:
                existing_rec = Contact.query.filter_by(name=doc.recipient, type="recipient", office_code=office_code).first()
                if existing_rec:
                    if doc.holder_name:
                        existing_rec.holder_name = doc.holder_name
                    if doc.position:
                        existing_rec.position = doc.position
                else:
                    new_rec = Contact(name=doc.recipient, type="recipient", holder_name=doc.holder_name, position=doc.position, office_code=office_code)
                    db.session.add(new_rec)
            
            if doc.sender:
                existing_sender = Contact.query.filter_by(name=doc.sender, type="sender", office_code=office_code).first()
                if not existing_sender:
                    new_sender = Contact(name=doc.sender, type="sender", office_code=office_code)
                    db.session.add(new_sender)
        elif action_type == "reserve":
            doc.doc_type = "reserved"

        # Store the direct SharePoint Word Online URL
        if generated_name:
            try:
                from services.onedrive import get_word_online_url
                doc.sharepoint_url = get_word_online_url(generated_name)
            except Exception:
                pass

        db.session.add(doc)
        db.session.commit()

        if status == 'approved':
            flash(f"Document number <strong>{full_code}</strong> generated successfully!", "success")
            return redirect(url_for("documents", auto_download=doc.id))
        return redirect(url_for("documents"))

    # Build preview code for the current moment
    now_preview = datetime.now()
    next_serial = get_next_serial(now_preview.month, now_preview.year, office_code=office_code)
    preview_code = build_full_code(next_serial, now_preview.month, now_preview.year, office_code=office_code)
    
    contacts = Contact.query.filter((Contact.office_code == office_code) | (Contact.office_code == None)).all()
    contacts_data = [
        {
            "name": c.name,
            "type": c.type,
            "holder_name": c.holder_name,
            "position": c.position
        } for c in contacts
    ]
    
    return render_template("index.html", preview_code=preview_code, contacts=contacts_data)


@app.route("/documents")
@login_required
def documents():
    """Documents history page — list all processed documents for permitted departments."""
    from offices import get_current_office
    curr_office = get_current_office()
    is_admin = is_current_user_admin()
    allowed_offices = get_user_allowed_offices()

    selected_office = request.args.get('office', curr_office['code'])

    # Enforce department access permissions
    if not is_admin:
        if selected_office and selected_office.upper() != 'ALL':
            if selected_office.upper() not in allowed_offices:
                selected_office = allowed_offices[0]
        else:
            if len(allowed_offices) == 1:
                selected_office = allowed_offices[0]

    query = Document.query
    if is_admin:
        if selected_office and selected_office.upper() != 'ALL':
            query = query.filter_by(office_code=selected_office.upper())
    else:
        # Permitted department users access all documents in their allowed departments
        if selected_office and selected_office.upper() != 'ALL':
            query = query.filter_by(office_code=selected_office.upper())
        else:
            query = query.filter(Document.office_code.in_(allowed_offices))

    all_docs = query.order_by(Document.created_at.desc()).all()
    return render_template(
        "documents.html",
        documents=all_docs,
        now=datetime.now(),
        is_admin=is_admin,
        selected_office=selected_office,
        allowed_offices=allowed_offices
    )


@app.route("/tracking")
@login_required
def tracking():
    """Document tracking & response follow-up page for internal correspondence."""
    from offices import get_current_office
    curr_office = get_current_office()
    is_admin = is_current_user_admin()
    allowed_offices = get_user_allowed_offices()

    selected_office = request.args.get('office', curr_office['code'])

    # Enforce department access permissions
    if not is_admin:
        if selected_office and selected_office.upper() != 'ALL':
            if selected_office.upper() not in allowed_offices:
                selected_office = allowed_offices[0]
        else:
            if len(allowed_offices) == 1:
                selected_office = allowed_offices[0]

    query = Document.query
    if is_admin:
        if selected_office and selected_office.upper() != 'ALL':
            query = query.filter_by(office_code=selected_office.upper())
    else:
        # Permitted department users access all tracking rows in their allowed departments
        if selected_office and selected_office.upper() != 'ALL':
            query = query.filter_by(office_code=selected_office.upper())
        else:
            query = query.filter(Document.office_code.in_(allowed_offices))

    all_docs = query.order_by(Document.created_at.desc()).all()

    total_sent = 0
    awaiting_response = 0
    received_count = 0
    overdue_count = 0
    no_response_count = 0
    not_sent_count = 0

    for d in all_docs:
        if d.is_sent:
            total_sent += 1
            if d.response_status == 'received':
                received_count += 1
            elif d.is_overdue:
                overdue_count += 1
            elif d.response_status == 'awaiting_response':
                awaiting_response += 1
            elif d.response_status == 'no_response_needed' or not d.requires_response:
                no_response_count += 1
        else:
            not_sent_count += 1

    stats = {
        "total_sent": total_sent,
        "awaiting_response": awaiting_response,
        "received": received_count,
        "overdue": overdue_count,
        "no_response_needed": no_response_count,
        "not_sent": not_sent_count,
        "total": len(all_docs),
    }

    return render_template("tracking.html", documents=all_docs, stats=stats, now=datetime.now(), is_admin=is_admin, selected_office=selected_office)


@app.route("/documents/<int:doc_id>/track", methods=["POST"])
@login_required
def update_document_tracking(doc_id):
    """Update tracking and response info for an internal document."""
    doc = Document.query.get_or_404(doc_id)
    user_email = session.get('user', {}).get('email', '')
    if not is_current_user_admin() and doc.email != user_email:
        flash("You do not have permission to edit this document's tracking info.", "danger")
        return redirect(request.referrer or url_for('tracking'))

    is_sent = request.form.get("is_sent") in ("1", "true", "on")
    doc.is_sent = is_sent

    sent_date_val = request.form.get("sent_date", "").strip()
    if sent_date_val:
        try:
            doc.sent_date = datetime.strptime(sent_date_val, "%Y-%m-%d")
        except ValueError:
            try:
                doc.sent_date = datetime.strptime(sent_date_val, "%Y-%m-%dT%H:%M")
            except ValueError:
                doc.sent_date = datetime.utcnow()
    elif is_sent and not doc.sent_date:
        doc.sent_date = datetime.utcnow()
    elif not is_sent:
        doc.sent_date = None

    doc.sent_method = request.form.get("sent_method", "").strip() or None
    doc.sent_by = request.form.get("sent_by", "").strip() or session.get('user', {}).get('name', '')
    doc.received_by = request.form.get("received_by", "").strip() or None
    doc.sent_notes = request.form.get("sent_notes", "").strip() or None

    requires_response = request.form.get("requires_response") in ("1", "true", "on")
    doc.requires_response = requires_response

    deadline_val = request.form.get("response_deadline", "").strip()
    if deadline_val and requires_response:
        try:
            doc.response_deadline = datetime.strptime(deadline_val, "%Y-%m-%d").date()
        except ValueError:
            pass
    elif not requires_response:
        doc.response_deadline = None

    response_status = request.form.get("response_status", "").strip()
    if not is_sent:
        response_status = "not_sent"
    elif not response_status:
        response_status = "awaiting_response" if requires_response else "no_response_needed"
    doc.response_status = response_status

    resp_date_val = request.form.get("response_date", "").strip()
    if resp_date_val and response_status == "received":
        try:
            doc.response_date = datetime.strptime(resp_date_val, "%Y-%m-%d")
        except ValueError:
            try:
                doc.response_date = datetime.strptime(resp_date_val, "%Y-%m-%dT%H:%M")
            except ValueError:
                doc.response_date = datetime.utcnow()
    elif response_status == "received" and not doc.response_date:
        doc.response_date = datetime.utcnow()
    elif response_status != "received":
        doc.response_date = None

    doc.response_ref = request.form.get("response_ref", "").strip() or None
    doc.response_summary = request.form.get("response_summary", "").strip() or None
    doc.followup_notes = request.form.get("followup_notes", "").strip() or None

    # Handle response file attachment
    if "response_file" in request.files:
        resp_file = request.files["response_file"]
        if resp_file and resp_file.filename and allowed_response_file(resp_file.filename):
            import uuid
            ext = resp_file.filename.rsplit('.', 1)[1].lower()
            safe_name = secure_filename(resp_file.filename.rsplit('.', 1)[0])
            gen_resp_filename = f"resp_{doc.id}_{uuid.uuid4().hex[:6]}_{safe_name}.{ext}"
            resp_path = os.path.join(RESPONSES_FOLDER, gen_resp_filename)
            resp_file.save(resp_path)
            doc.response_file = gen_resp_filename
            doc.response_received_by = session.get('user', {}).get('name', '')

    db.session.commit()
    flash(f"Tracking details for Code No <strong>{doc.full_code}</strong> have been updated.", "success")
    return redirect(request.referrer or url_for('tracking'))


@app.route("/download_response/<int:doc_id>")
@login_required
def download_response(doc_id):
    """Download attached response file for a document."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("Permission denied.", "danger")
        return redirect(url_for('tracking'))
    if not doc.response_file:
        flash("No response file attached to this document.", "warning")
        return redirect(request.referrer or url_for('tracking'))

    file_path = os.path.join(RESPONSES_FOLDER, doc.response_file)
    if not os.path.exists(file_path):
        alt_path = os.path.join(BASE_DIR, "uploads", "responses", doc.response_file)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            flash("Response file not found on disk.", "danger")
            return redirect(request.referrer or url_for('tracking'))
    return send_file(file_path, as_attachment=True, download_name=doc.response_file)


@app.route("/view_response/<int:doc_id>")
@login_required
def view_response(doc_id):
    """View attached response file inline in browser (for PDF and images)."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("Permission denied.", "danger")
        return redirect(url_for('tracking'))
    if not doc.response_file:
        flash("No response file attached to this document.", "warning")
        return redirect(request.referrer or url_for('tracking'))

    file_path = os.path.join(RESPONSES_FOLDER, doc.response_file)
    if not os.path.exists(file_path):
        alt_path = os.path.join(BASE_DIR, "uploads", "responses", doc.response_file)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            flash("Response file not found on disk.", "danger")
            return redirect(request.referrer or url_for('tracking'))
    return send_file(file_path, as_attachment=False)


@app.route("/documents/<int:doc_id>/delete_response_file", methods=["POST"])
@login_required
def delete_response_file(doc_id):
    """Delete attached response file."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("Permission denied.", "danger")
        return redirect(url_for('tracking'))
    if doc.response_file:
        file_path = os.path.join(RESPONSES_FOLDER, doc.response_file)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        doc.response_file = None
        db.session.commit()
        flash(f"Attached response file removed for Code No {doc.full_code}.", "info")
    return redirect(request.referrer or url_for('tracking'))


@app.route("/download/<int:doc_id>")
@login_required
def download(doc_id):
    """Download the generated (numbered) document."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("ليس لديك صلاحية للوصول إلى هذا المستند / Permission denied.", "danger")
        return redirect(url_for('documents'))

    if not doc.generated_filename:
        abort(404)
        
    local_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
    if not os.path.exists(local_path):
        from services.onedrive import download_file_from_share
        if os.environ.get("ONEDRIVE_SHARE_URL"):
            download_file_from_share(doc.generated_filename, local_path)
            
    if not os.path.exists(local_path):
        abort(404)
        
    return send_from_directory(GENERATED_FOLDER, doc.generated_filename, as_attachment=True,
        download_name=doc.generated_filename)

@app.route("/download_pdf/<int:doc_id>")
@login_required
def download_pdf(doc_id):
    """Download the generated PDF document."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("ليس لديك صلاحية للوصول إلى هذا المستند / Permission denied.", "danger")
        return redirect(url_for('documents'))

    if not doc.generated_pdf_filename:
        flash("No PDF file available for this document.", "warning")
        return redirect(url_for("documents"))
        
    local_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
    if not os.path.exists(local_path):
        from services.onedrive import download_file_from_share
        if os.environ.get("ONEDRIVE_SHARE_URL"):
            download_file_from_share(doc.generated_pdf_filename, local_path)
            
    if not os.path.exists(local_path):
        flash("File could not be found locally or on OneDrive.", "danger")
        return redirect(url_for("documents"))
        
    return send_from_directory(GENERATED_FOLDER, doc.generated_pdf_filename, as_attachment=True,
        download_name=doc.generated_pdf_filename)


@app.route("/view_pdf/<int:doc_id>")
@login_required
def view_pdf(doc_id):
    """View the generated PDF document inline."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("ليس لديك صلاحية للوصول إلى هذا المستند / Permission denied.", "danger")
        return redirect(url_for('documents'))

    if not doc.generated_pdf_filename:
        flash("No PDF file available for this document.", "warning")
        return redirect(url_for("documents"))
        
    local_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
    if not os.path.exists(local_path):
        from services.onedrive import download_file_from_share
        if os.environ.get("ONEDRIVE_SHARE_URL"):
            download_file_from_share(doc.generated_pdf_filename, local_path)
            
    if not os.path.exists(local_path):
        flash("File could not be found locally or on OneDrive.", "danger")
        return redirect(url_for("documents"))
        
    return send_from_directory(GENERATED_FOLDER, doc.generated_pdf_filename, as_attachment=False)


@app.route("/view_word/<int:doc_id>")
@login_required
def view_word_online(doc_id):
    """Redirect to Word Online to view the document."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("ليس لديك صلاحية للوصول إلى هذا المستند / Permission denied.", "danger")
        return redirect(url_for('documents'))
    if doc.sharepoint_url:
        return redirect(doc.sharepoint_url)
    if not doc.generated_filename:
        flash("No Word file available.", "warning")
        return redirect(url_for("documents"))
        
    from services.onedrive import get_word_online_url
    return redirect(get_word_online_url(doc.generated_filename))


@app.route("/preview_document", methods=["POST"])
@login_required
def preview_document():
    action_type = request.form.get("action_type")
    
    import tempfile
    from services.word_editor import replace_placeholder, replace_placeholders
    from services.ai_generator import normalize_recipient
    from services.onedrive import upload_file_to_share, get_word_online_url
    from flask import jsonify
    from offices import get_current_office
    
    curr_office = get_current_office()
    office_code = curr_office['code']
    template_filename = curr_office['template']
    
    # Run cleanup of any stale preview files from prior days
    cleanup_old_previews()

    now = datetime.now()
    serial = get_next_serial(now.month, now.year, office_code=office_code)
    full_code = build_full_code(serial, now.month, now.year, office_code=office_code)
    
    user_email = session.get('user', {}).get('email', 'user')
    username = secure_filename(user_email.split('@')[0]) or 'user'
    gen_name = f"Preview_{username}.docx"
    temp_docx_path = os.path.join(PREVIEWS_FOLDER, gen_name)
    
    try:
        if action_type == "upload":
            file = request.files.get("document") or request.files.get("docx_file")
            if not file or file.filename == "":
                return jsonify({"success": False, "error": "No file uploaded"}), 400
            
            upload_path = os.path.join(PREVIEWS_FOLDER, f"upload_{gen_name}")
            file.save(upload_path)
            replace_placeholder(upload_path, temp_docx_path, full_code)
            try:
                os.remove(upload_path)
            except Exception:
                pass
            
        elif action_type == "direct_template":
            upload_path = os.path.join(BASE_DIR, template_filename)
            if not os.path.exists(upload_path):
                return jsonify({"success": False, "error": "Template not found"}), 404
                
            recipient = request.form.get("recipient", "")
            subject = request.form.get("subject", "")
            holder_name = request.form.get("holder_name", "")
            position = request.form.get("position", "")
            full_body = request.form.get("full_body", "")
            sender = request.form.get("sender", "")
            is_internal = request.form.get("is_internal") == "1"
            manager_is_sender = request.form.get("manager_is_sender") == "1"

            import re
            def remove_office_code(text):
                if not text: return ""
                for code in ['ESSIC', 'HUEED', 'AIE']:
                    text = re.sub(rf'\(\s*{code}\s*\)', '', text, flags=re.IGNORECASE)
                    text = re.sub(rf'{code}', '', text, flags=re.IGNORECASE)
                return text.strip()

            default_sender = curr_office.get('manager_title', '')
            
            # Unconditionally remove office text from all text fields
            recipient = remove_office_code(recipient)
            subject = remove_office_code(subject)
            holder_name = remove_office_code(holder_name)
            position = remove_office_code(position)
            full_body = remove_office_code(full_body)
            sender = remove_office_code(sender)
            default_sender = remove_office_code(default_sender)

            sender_value = ""
            sender_top = f"\u202A{sender}\u202C" if sender else f"\u202A{default_sender}\u202C"
            if is_internal and not manager_is_sender and sender:
                sender_value = f"\u202Bمقدمه لسيادتكم\n{sender}\u202C"

            # Parse tables_data for preview
            import json
            raw_tables = request.form.get("tables_data") or request.form.get("table_data") or "[]"
            try:
                tables_data = json.loads(raw_tables)
                if tables_data and isinstance(tables_data, list):
                    if len(tables_data) > 0 and isinstance(tables_data[0], list) and len(tables_data[0]) > 0 and not isinstance(tables_data[0][0], list):
                        tables_data = [tables_data]
            except Exception:
                tables_data = []

            # Parse and save uploaded images for preview
            image_paths = []
            temp_image_files = []
            images = request.files.getlist("images")
            if images:
                import uuid
                for img in images:
                    if img and img.filename:
                        ext = img.filename.rsplit('.', 1)[-1].lower() if '.' in img.filename else 'png'
                        temp_path = os.path.join(PREVIEWS_FOLDER, f"prev_img_{uuid.uuid4().hex}.{ext}")
                        img.save(temp_path)
                        temp_image_files.append(temp_path)
                        image_paths.append(temp_path)
                    else:
                        image_paths.append(None)

            # Parse image_sizes for preview (default 1x1 inch)
            image_sizes = []
            raw_sizes = request.form.get("image_sizes")
            if raw_sizes:
                try:
                    image_sizes = json.loads(raw_sizes)
                except Exception:
                    image_sizes = []
            if not image_sizes:
                widths = request.form.getlist("image_widths")
                heights = request.form.getlist("image_heights")
                for w, h in zip(widths, heights):
                    try:
                        image_sizes.append({"width": float(w or 1.0), "height": float(h or 1.0)})
                    except Exception:
                        image_sizes.append({"width": 1.0, "height": 1.0})

            replace_placeholders(upload_path, temp_docx_path, {
                "{{CODE_NUMBER}}": full_code,
                "{{SEND_TO}}": ("\u202A" + normalize_recipient(recipient) + "\u202C") if recipient else "",
                "{{SUBJECT}}": "\u202A" + subject + "\u202C",
                "{{STACK_HOLDER}}": "\u202B" + holder_name + "\u202C",
                "{{POSITION}}": "\u202B" + position + "\u202C",
                "{{BODY_TEXT}}": "\u202B" + full_body + "\u202C",
                "{{SENDER}}": sender_value,
                "{{SENDER_TOP}}": sender_top,
                "{{ESSIC}}": "",
                "{{HUEED}}": "",
                "{{AIE}}": "",
            }, remove_manager_sig=(is_internal and not manager_is_sender), tables_data=tables_data, image_paths=image_paths, image_sizes=image_sizes)

            # Cleanup temp image files used for preview
            for p in temp_image_files:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        else:
            return jsonify({"success": False, "error": "Invalid action type"}), 400
            
        # Upload the temporary preview doc to OneDrive previews folder
        if os.environ.get("ONEDRIVE_PREVIEW_SHARE_URL") or os.environ.get("ONEDRIVE_SHARE_URL"):
            success = upload_file_to_share(temp_docx_path, gen_name, is_preview=True)
            if success:
                from services.onedrive import delete_file_from_share
                old_preview = session.get('last_preview_filename')
                if old_preview and old_preview != gen_name:
                    delete_file_from_share(old_preview, is_preview=True)
                session['last_preview_filename'] = gen_name
                
                url = get_word_online_url(gen_name, is_preview=True)
                return jsonify({"success": True, "word_online_url": url})
            else:
                import services.onedrive as od
                return jsonify({"success": False, "error": f"Failed to upload preview to OneDrive. {od.LAST_ERROR}"})
        else:
            return jsonify({"success": False, "error": "OneDrive is not configured. Cannot preview in Word Online."})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/extract_text", methods=["POST"])
@login_required
def extract_text():
    file = request.files.get("docx_file")
    if not file or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Invalid file"}), 400
        
    try:
        from docx import Document
        doc = Document(file)
        raw_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        
        from services.ai_generator import extract_document_fields
        user_email = session.get('user', {}).get('email', '')
        
        fields = extract_document_fields(raw_text, user_email)
        
        if fields:
            return jsonify({"success": True, "text": fields.get("full_body", raw_text), "fields": fields})
        else:
            return jsonify({"success": True, "text": raw_text, "fields": None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/upload_reserved/<int:doc_id>", methods=["POST"])
@login_required
def upload_reserved(doc_id):
    """Upload finalized document for a reserved serial."""
    doc = Document.query.get_or_404(doc_id)
    
    if doc.doc_type != "reserved":
        flash("This document is not eligible for this action.", "danger")
        return redirect(url_for("documents"))
        
    file = request.files.get("docx_file")
    if not file or file.filename == "":
        flash("Please select a Word document to upload.", "warning")
        return redirect(url_for("documents"))
        
    if not allowed_file(file.filename):
        flash("Only .docx files are accepted.", "danger")
        return redirect(url_for("documents"))
        
    try:
        now = datetime.now()
        timestamp = now.strftime("%Y%md_%H%M%S")
        original_name = secure_filename(file.filename)
        generated_name = f"Final_{timestamp}_{doc.full_code.replace(' ', '_')}.docx"
        
        generated_path = os.path.join(GENERATED_FOLDER, generated_name)
        file.save(generated_path)
        
        from services.pdf_converter import convert_docx_to_pdf
        generated_pdf_name = generated_name.replace(".docx", ".pdf")
        generated_pdf_path = os.path.join(GENERATED_FOLDER, generated_pdf_name)
        pdf_success = convert_docx_to_pdf(generated_path, generated_pdf_path)
        if not pdf_success:
            generated_pdf_name = None
            
        doc.filename = original_name
        doc.generated_filename = generated_name
        doc.generated_pdf_filename = generated_pdf_name
        
        is_admin = is_current_user_admin()
        status = 'approved' if is_admin else 'pending'
        
        if status == 'approved':
            from services.onedrive import upload_file_to_share
            if os.environ.get("ONEDRIVE_SHARE_URL"):
                upload_file_to_share(generated_path, generated_name)
                if generated_pdf_name:
                    upload_file_to_share(generated_pdf_path, generated_pdf_name)
                    
        doc.status = status
        db.session.commit()
        
        if status == 'approved':
            flash("Final document uploaded and approved!", "success")
        else:
            flash("Final document uploaded successfully. It is pending admin approval.", "info")
            
    except Exception as e:
        flash(f"Error processing finalized document: {e}", "danger")
        
    return redirect(url_for("documents"))

@app.route("/edit/<int:doc_id>", methods=["GET", "POST"])
@login_required
def edit(doc_id):
    """Edit a document's serial number and regenerate its full code."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("You do not have permission to modify this document.", "danger")
        return redirect(url_for("documents"))

    if request.method == "POST":
        try:
            new_serial = int(request.form["serial_number"])
            if new_serial < 1:
                raise ValueError
        except (ValueError, KeyError):
            flash("Serial number must be a positive integer.", "danger")
            return redirect(url_for("edit", doc_id=doc_id))
            
        full_body = doc.generated_body
        if doc.doc_type == "direct":
            doc.recipient = request.form.get("recipient", doc.recipient)
            doc.subject = request.form.get("subject", doc.subject)
            doc.holder_name = request.form.get("holder_name", doc.holder_name)
            doc.position = request.form.get("position", doc.position)
            doc.sender = request.form.get("sender", doc.sender)
            doc.is_internal = request.form.get("is_internal") == "1"
            doc.manager_is_sender = request.form.get("manager_is_sender") == "1"
            full_body = request.form.get("full_body", doc.generated_body)
            doc.generated_body = full_body

        doc_office = getattr(doc, 'office_code', None) or 'ESSIC'
        from offices import get_office_by_code
        office_cfg = get_office_by_code(doc_office)

        # Regenerate full code with new serial
        new_full_code = build_full_code(new_serial, doc.month, doc.year, office_code=doc_office)

        if new_serial != doc.serial_number:
            existing = Document.query.filter_by(month=doc.month, year=doc.year, serial_number=new_serial, office_code=doc_office).first()
            if existing:
                flash(f"Serial number {new_serial} is already used for this month in {doc_office}. Please choose another.", "danger")
                return redirect(url_for("edit", doc_id=doc_id))

        # Re-process the Word document with the new code
        upload_path = os.path.join(UPLOAD_FOLDER, doc.filename)
        # If it was generated via direct entry and we don't have the uploaded file, fallback to template
        fallback_template = office_cfg.get('template', SYSTEM_TEMPLATE_FILENAME)
        if doc.doc_type == "direct" and not os.path.exists(upload_path):
            upload_path = os.path.join(BASE_DIR, fallback_template)
            
        if not os.path.exists(upload_path):
            flash("Original uploaded file not found. Cannot regenerate document.", "danger")
            return redirect(url_for("documents"))

        # Remove old generated file
        if doc.generated_filename:
            old_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
                
        if doc.generated_pdf_filename:
            old_pdf_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
            if os.path.exists(old_pdf_path):
                os.remove(old_pdf_path)

        stem = doc.filename.rsplit(".", 1)[0]
        new_generated_name = f"{stem}__{new_full_code.replace(' ', '_')}.docx"
        new_generated_path = os.path.join(GENERATED_FOLDER, new_generated_name)

        try:
            if doc.doc_type == "direct":
                from services.word_editor import replace_placeholders
                from services.ai_generator import normalize_recipient
                
                import re
                def remove_office_code(text):
                    if not text: return ""
                    for code in ['ESSIC', 'HUEED', 'AIE']:
                        text = re.sub(rf'\(\s*{code}\s*\)', '', text, flags=re.IGNORECASE)
                        text = re.sub(rf'{code}', '', text, flags=re.IGNORECASE)
                    return text.strip()

                default_sender = office_cfg.get('manager_title', '')
                
                # Unconditionally remove office text from all text fields
                doc.recipient = remove_office_code(doc.recipient)
                doc.subject = remove_office_code(doc.subject)
                doc.holder_name = remove_office_code(doc.holder_name)
                doc.position = remove_office_code(doc.position)
                full_body = remove_office_code(full_body)
                doc.sender = remove_office_code(doc.sender)
                default_sender = remove_office_code(default_sender)

                body_to_use = full_body
                sender_value = ""
                sender_top = f"\u202A{doc.sender}\u202C" if doc.sender else f"\u202A{default_sender}\u202C"
                
                if doc.is_internal and not doc.manager_is_sender and doc.sender:
                    sender_value = f"\u202Bمقدمه لسيادتكم\n{doc.sender}\u202C"

                replace_placeholders(upload_path, new_generated_path, {
                    "{{CODE_NUMBER}}": new_full_code,
                    "{{SEND_TO}}": ("\u202A" + normalize_recipient(doc.recipient) + "\u202C") if doc.recipient else "",
                    "{{SUBJECT}}": "\u202A" + doc.subject + "\u202C",
                    "{{STACK_HOLDER}}": "\u202B" + (doc.holder_name or "") + "\u202C",
                    "{{POSITION}}": "\u202B" + (doc.position or "") + "\u202C",
                    "{{BODY_TEXT}}": "\u202B" + (body_to_use or "") + "\u202C",
                    "{{SENDER}}": sender_value,
                    "{{SENDER_TOP}}": sender_top,
                    "{{ESSIC}}": "",
                    "{{HUEED}}": "",
                    "{{AIE}}": "",
                }, remove_manager_sig=(doc.is_internal and not doc.manager_is_sender))
            else:
                from services.word_editor import replace_placeholder
                replace_placeholder(upload_path, new_generated_path, new_full_code)
                
            from services.pdf_converter import convert_docx_to_pdf
            new_generated_pdf_name = new_generated_name.replace(".docx", ".pdf")
            new_generated_pdf_path = os.path.join(GENERATED_FOLDER, new_generated_pdf_name)
            pdf_success = convert_docx_to_pdf(new_generated_path, new_generated_pdf_path)
            if pdf_success:
                doc.generated_pdf_filename = new_generated_pdf_name
            else:
                doc.generated_pdf_filename = None
        except Exception as e:
            flash(f"Error regenerating document: {e}", "danger")
            return redirect(url_for("documents"))

        doc.serial_number = new_serial
        doc.full_code = new_full_code
        doc.generated_filename = new_generated_name
        db.session.commit()

        flash(f"Document updated to <strong>{new_full_code}</strong>.", "success")
        return redirect(url_for("documents"))

    return render_template("edit.html", doc=doc)


@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete(doc_id):
    """Delete a document record and its generated file."""
    doc = Document.query.get_or_404(doc_id)
    if not user_can_access_office(doc.office_code):
        flash("You do not have permission to delete this document.", "danger")
        return redirect(url_for("documents"))

    # Remove generated files from disk
    if doc.generated_filename:
        gen_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        if os.path.exists(gen_path):
            os.remove(gen_path)
            
    if doc.generated_pdf_filename:
        gen_pdf_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
        if os.path.exists(gen_pdf_path):
            os.remove(gen_pdf_path)

    db.session.delete(doc)
    db.session.commit()

    flash("Document record deleted.", "info")
    return redirect(url_for("documents"))


@app.route("/approve/<int:doc_id>", methods=["POST"])
@login_required
@admin_required
def approve(doc_id):
    """Approve a pending document and upload to OneDrive."""

    doc = Document.query.get_or_404(doc_id)
    if doc.status == 'approved':
        flash("Document is already approved.", "info")
        return redirect(url_for("documents"))

    doc.status = 'approved'

    # If the document is missing a PDF, try to generate one now
    if doc.generated_filename and not doc.generated_pdf_filename:
        generated_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        if os.path.exists(generated_path):
            from services.pdf_converter import convert_docx_to_pdf
            pdf_name = doc.generated_filename.replace(".docx", ".pdf")
            pdf_path = os.path.join(GENERATED_FOLDER, pdf_name)
            if convert_docx_to_pdf(generated_path, pdf_path):
                doc.generated_pdf_filename = pdf_name

    # Trigger OneDrive upload
    if doc.generated_filename:
        generated_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        from services.onedrive import upload_file_to_share, LAST_ERROR
        if os.environ.get("ONEDRIVE_SHARE_URL") and os.path.exists(generated_path):
            success = upload_file_to_share(generated_path, doc.generated_filename)
            # Also upload the PDF if available
            if doc.generated_pdf_filename:
                pdf_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
                if os.path.exists(pdf_path):
                    upload_file_to_share(pdf_path, doc.generated_pdf_filename)
            if success:
                flash(f"Document {doc.full_code} approved and uploaded to OneDrive!", "success")
            else:
                import services.onedrive as od
                flash(f"Document {doc.full_code} approved, but OneDrive upload failed. Error: {od.LAST_ERROR}", "warning")
        else:
            flash(f"Document {doc.full_code} approved (OneDrive not configured or file missing).", "success")
    else:
        flash(f"Document {doc.full_code} approved.", "success")

    db.session.commit()
    return redirect(url_for("documents"))


@app.route("/reject/<int:doc_id>", methods=["POST"])
@login_required
@admin_required
def reject(doc_id):
    """Reject a pending document."""
    doc = Document.query.get_or_404(doc_id)
    if doc.status != 'pending':
        flash("Only pending documents can be rejected.", "warning")
        return redirect(url_for("documents"))

    doc.status = 'rejected'
    db.session.commit()
    flash(f"Document {doc.full_code} has been rejected.", "info")
    return redirect(url_for("documents"))


@app.route("/users")
@login_required
@admin_required
def users():
    """User Management Page."""
    super_admin = "aelshafee@horus.edu.eg"
    current_user_email = session.get('user', {}).get('email', '')
    
    query = User.query
    if current_user_email != super_admin:
        query = query.filter(User.email != super_admin)
        
    all_users = query.order_by(User.created_at.desc()).all()
    from offices import OFFICE_CONFIGS
    return render_template("users.html", users=all_users, ALL_OFFICES=OFFICE_CONFIGS)


@app.route("/users/role/<email>", methods=["POST"])
@login_required
@admin_required
def toggle_user_role(email):
    user = User.query.filter_by(email=email).first_or_404()
    if user.email in ADMIN_EMAILS:
        flash("Cannot change role of a root admin.", "warning")
    else:
        user.role = 'admin' if user.role == 'user' else 'user'
        db.session.commit()
        flash(f"User {email} is now {user.role}.", "success")
    return redirect(url_for("users"))


@app.route("/users/delete/<email>", methods=["POST"])
@login_required
@admin_required
def delete_user(email):
    user = User.query.filter_by(email=email).first_or_404()
    if user.email in ADMIN_EMAILS:
        flash("Cannot delete a root admin.", "warning")
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f"User {email} has been deleted.", "info")
    return redirect(url_for("users"))


@app.route("/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "user").strip()

    allowed_list = request.form.getlist("allowed_offices")
    if 'ALL' in allowed_list or not allowed_list:
        allowed_str = 'ALL'
    else:
        allowed_str = ','.join(allowed_list)

    if not name or not email:
        flash("Name and email are required.", "warning")
        return redirect(url_for("users"))

    if User.query.filter_by(email=email).first():
        flash("A user with this email already exists.", "warning")
        return redirect(url_for("users"))

    totp_secret = pyotp.random_base32()
    user = User(
        email=email,
        name=name,
        totp_secret=totp_secret,
        is_setup=False,
        role=role,
        allowed_offices=allowed_str
    )
    db.session.add(user)
    db.session.commit()
    flash(f"User {name} added successfully with access to {allowed_str}.", "success")
    return redirect(url_for("users"))


@app.route("/users/edit/<email>", methods=["POST"])
@login_required
@admin_required
def edit_user(email):
    user = User.query.filter_by(email=email).first_or_404()

    name = request.form.get("name", "").strip()
    role = request.form.get("role", user.role).strip()
    reset_otp = request.form.get("reset_otp") == "on"

    allowed_list = request.form.getlist("allowed_offices")
    if 'ALL' in allowed_list or not allowed_list:
        allowed_str = 'ALL'
    else:
        allowed_str = ','.join(allowed_list)

    if name:
        user.name = name

    if user.email not in ADMIN_EMAILS:
        user.role = role
    elif role != 'admin':
        flash("Cannot remove admin role from a root admin.", "warning")

    user.allowed_offices = allowed_str

    if reset_otp:
        user.totp_secret = pyotp.random_base32()
        user.is_setup = False
        flash(f"Authenticator reset for {user.name}.", "info")

    db.session.commit()
    flash(f"User {user.email} updated successfully.", "success")
    return redirect(url_for("users"))


# ── AI Content Generator Routes ─────────────────────────────────────────────
#
# Placeholder contract with the .docx/.pages letterhead template:
#   {{CODE_NUMBER}}  -> document code, e.g. "0031 ESSIC 05-2026"
#   {{SEND_TO}}      -> recipient office/department (normalized Arabic)
#   {{SUBJECT}}      -> subject line
#   {{STACK_HOLDER}} -> recipient's formal name/title line, e.g.
#                       "السيد الأستاذ الدكتور / محمد عبدالعال – الموقر"
#   {{POSITION}}     -> recipient's position, e.g. "نائب رئيس جامعة حورس - مصر"
#   {{BODY_TEXT}}    -> generated letter body ONLY (paragraphs, no header/signature)
#
# NOTE: these exact token names (SEND_TO / STACK_HOLDER, in this word order)
# must match whatever .docx/.pages template is actually uploaded. A previous
# version of this code used {{TO_SEND}}/{{HOLDER_STACK}} based on an older
# template file, which didn't match the token names in the template actually
# used in production — those two fields were left unreplaced as literal
# "{{TO_SEND}}"/"{{HOLDER_STACK}}" text. Always grep the real template's XML
# for `{{[A-Z_]*}}` before assuming a placeholder's exact name/order.
#
# The template already renders sender info and the closing signature as
# static content, so those are never re-embedded into {{BODY_TEXT}}.

from services.ai_generator import (generate_arabic_text, build_full_document_text,
                                     get_available_models, normalize_recipient)
from services.word_editor import replace_placeholders


@app.route("/ai/new")
@login_required
def ai_step1():
    return render_template("ai_step1.html")


@app.route("/ai/compose/<doc_type>")
@login_required
def ai_step2(doc_type):
    if doc_type not in ("letter", "request"):
        return redirect(url_for("ai_step1"))
        
    from offices import get_current_office
    curr_office = get_current_office()
    office_code = curr_office['code']
    contacts = Contact.query.filter((Contact.office_code == office_code) | (Contact.office_code == None)).all()
    contacts_data = [
        {
            "name": c.name,
            "type": c.type,
            "holder_name": c.holder_name,
            "position": c.position
        } for c in contacts
    ]
    return render_template("ai_step2.html", doc_type=doc_type, models=get_available_models(), contacts=contacts_data)


@app.route("/ai/generate", methods=["POST"])
@login_required
def ai_generate():
    doc_type = request.form.get("doc_type", "letter")
    sender = request.form.get("sender", "").strip()
    recipient = request.form.get("recipient", "").strip()
    subject = request.form.get("subject", "").strip()
    holder_name = request.form.get("holder_name", "").strip()
    position = request.form.get("position", "").strip()
    raw_draft = request.form.get("raw_draft", "").strip()
    model = request.form.get("model")

    if not all([sender, recipient, subject, holder_name, position, raw_draft]):
        flash("يرجى ملء جميع الحقول المطلوبة.", "warning")
        return redirect(url_for("ai_step2", doc_type=doc_type))

    user_email = session['user']['email']
    result = generate_arabic_text(doc_type=doc_type, sender=sender, recipient=recipient, subject=subject,
                                  raw_draft=raw_draft, user_email=user_email)

    if not result["success"]:
        flash(f"خطأ في توليد المحتوى: {result['error']}", "danger")
        return redirect(url_for("ai_step2", doc_type=doc_type))

    if result.get("warning"):
        flash(result["warning"], "warning")

    full_body = build_full_document_text(generated_body=result["text"])

    return render_template("ai_step3.html", doc_type=doc_type, sender=sender, recipient=recipient, subject=subject,
                           holder_name=holder_name, position=position, raw_draft=raw_draft,
                           generated_body=result["text"], full_body=full_body, model=model,
                           models=get_available_models(), )


@app.route("/ai/finalize", methods=["POST"])
@login_required
def ai_finalize():
    doc_type = request.form.get("doc_type", "letter")
    sender = request.form.get("sender", "")
    recipient = request.form.get("recipient", "")
    subject = request.form.get("subject", "")
    holder_name = request.form.get("holder_name", "")
    position = request.form.get("position", "")
    raw_draft = request.form.get("raw_draft", "")
    full_body = request.form.get("full_body", "")
    model = request.form.get("model")

    table_data_str = request.form.get("table_data", "[]")
    import json
    try:
        table_data = json.loads(table_data_str)
    except:
        table_data = []

    image_paths = []
    images = request.files.getlist("images")
    if images:
        import uuid
        for img in images:
            if img.filename:
                ext = img.filename.split('.')[-1]
                temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4().hex}.{ext}")
                img.save(temp_path)
                image_paths.append(temp_path)

    from offices import get_current_office
    curr_office = get_current_office()
    office_code = curr_office['code']
    template_filename = curr_office['template']

    upload_path = os.path.join(BASE_DIR, template_filename)
    if not os.path.exists(upload_path):
        flash(f"قالب النظام ({template_filename}) غير موجود.", "danger")
        return redirect(url_for("ai_step1"))
        
    original_name = template_filename

    now = datetime.utcnow()
    serial = get_next_serial(now.month, now.year, office_code=office_code)
    code = build_full_code(serial, now.month, now.year, office_code=office_code)

    stem = office_code
    gen_name = f"{stem}__{code.replace(' ', '_')}.docx"
    gen_path = os.path.join(GENERATED_FOLDER, gen_name)

    import re
    def remove_office_code(text):
        if not text: return ""
        for c in ['ESSIC', 'HUEED', 'AIE']:
            text = re.sub(rf'\(\s*{c}\s*\)', '', text, flags=re.IGNORECASE)
            text = re.sub(rf'{c}', '', text, flags=re.IGNORECASE)
        return text.strip()

    default_sender = curr_office.get('manager_title', '')
    
    # Unconditionally remove office text from all text fields
    recipient = remove_office_code(recipient)
    subject = remove_office_code(subject)
    holder_name = remove_office_code(holder_name)
    position = remove_office_code(position)
    full_body = remove_office_code(full_body)
    sender = remove_office_code(sender)
    default_sender = remove_office_code(default_sender)

    sender_top = f"\u202A{sender}\u202C" if sender else f"\u202A{default_sender}\u202C"

    try:
        replace_placeholders(upload_path, gen_path, {
            "{{CODE_NUMBER}}": code,
            "{{SEND_TO}}": "\u202A" + normalize_recipient(recipient) + "\u202C" if recipient else "",
            "{{SUBJECT}}": "\u202A" + subject + "\u202C",
            "{{STACK_HOLDER}}": "\u202B" + holder_name + "\u202C",
            "{{POSITION}}": "\u202B" + position + "\u202C",
            "{{BODY_TEXT}}": "\u202B" + full_body + "\u202C",
            "{{SENDER}}": "", # Manager signature kept
            "{{SENDER_TOP}}": sender_top,
            "{{ESSIC}}": "",
            "{{HUEED}}": "",
            "{{AIE}}": "",
        }, table_data=table_data, image_paths=image_paths)
        
        from services.pdf_converter import convert_docx_to_pdf
        gen_pdf_name = gen_name.replace(".docx", ".pdf")
        gen_pdf_path = os.path.join(GENERATED_FOLDER, gen_pdf_name)
        pdf_success = convert_docx_to_pdf(gen_path, gen_pdf_path)
        if not pdf_success:
            gen_pdf_name = None
            
    except Exception as e:
        flash(f"خطأ في معالجة المستند: {e}", "danger")
        return redirect(url_for("ai_step1"))

    user_email = session['user']['email']
    user_name = session['user']['name']
    status = 'approved' if is_current_user_admin() else 'pending'

    doc = Document(serial_number=serial, full_code=code, month=now.month, year=now.year, doc_type=doc_type,
        sender=sender, recipient=recipient, subject=subject, holder_name=holder_name, position=position, raw_draft=raw_draft, generated_body=full_body,
        filename=original_name, generated_filename=gen_name, generated_pdf_filename=gen_pdf_name, ai_model=model, username=user_name, email=user_email,
        status=status, office_code=office_code)
    
    # Auto-save contact info
    if recipient:
        existing_rec = Contact.query.filter_by(name=recipient, type="recipient", office_code=office_code).first()
        if existing_rec:
            if holder_name:
                existing_rec.holder_name = holder_name
            if position:
                existing_rec.position = position
        else:
            new_rec = Contact(name=recipient, type="recipient", holder_name=holder_name, position=position, office_code=office_code)
            db.session.add(new_rec)
    
    if sender:
        existing_sender = Contact.query.filter_by(name=sender, type="sender", office_code=office_code).first()
        if not existing_sender:
            new_sender = Contact(name=sender, type="sender", office_code=office_code)
            db.session.add(new_sender)

    db.session.add(doc)
    db.session.commit()

    if gen_name:
        from services.onedrive import upload_file_to_share
        if os.environ.get("ONEDRIVE_SHARE_URL"):
            upload_success = upload_file_to_share(gen_path, gen_name)
            try:
                from services.onedrive import get_word_online_url
                doc.sharepoint_url = get_word_online_url(gen_name)
                db.session.commit()
            except Exception:
                pass
            if not upload_success:
                from services.onedrive import LAST_ERROR
                flash(f"Error uploading to OneDrive: {LAST_ERROR}", "danger")

    flash(f"تم إنشاء المستند بنجاح — الرمز: <strong>Code No {code}</strong>", "success")
    return redirect(url_for("documents"))


@app.route("/api/ai/regenerate", methods=["POST"])
@login_required
def api_ai_regenerate():
    data = request.get_json()
    user_email = session['user']['email']
    result = generate_arabic_text(doc_type=data.get("doc_type", "letter"), sender=data.get("sender", ""),
                                  recipient=data.get("recipient", ""), subject=data.get("subject", ""),
                                  raw_draft=data.get("raw_draft", ""), user_email=user_email)
    if result["success"]:
        full_body = build_full_document_text(generated_body=result["text"])
        return jsonify({"success": True, "body": result["text"], "full_body": full_body,
                        "warning": result.get("warning")})
    return jsonify({"success": False, "error": result["error"]})

@app.route("/api/ai/format", methods=["POST"])
@login_required
def api_ai_format_document():
    data = request.get_json()
    user_email = session['user']['email']
    full_body = data.get("full_body", "")
    has_table = data.get("has_table", False)
    has_images = data.get("has_images", False)
    
    from services.ai_generator import format_document_with_ai
    result = format_document_with_ai(full_body, has_table, has_images, user_email)
    
    if result.get("success"):
        return jsonify({"success": True, "full_body": result["text"]})
    return jsonify({"success": False, "error": result.get("error", "Unknown error")})



@app.route("/api/cleanup_previews", methods=["POST", "GET"])
@login_required
@admin_required
def api_cleanup_previews():
    cleanup_old_previews()
    return jsonify({"success": True, "message": "Preview files cleaned up successfully."})


# ─── Entry Point ─────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    
    if not user:
        flash("User not found in database.", "danger")
        return redirect(url_for('documents'))

    from services.ai_generator import encrypt_api_key, get_user_keys

    if request.method == "POST":
        gemini = request.form.get("gemini_key", "").strip()
        groq = request.form.get("groq_key", "").strip()
        deepseek = request.form.get("deepseek_key", "").strip()
        
        user.gemini_api_key = encrypt_api_key(gemini) if gemini else ""
        user.groq_api_key = encrypt_api_key(groq) if groq else ""
        user.deepseek_api_key = encrypt_api_key(deepseek) if deepseek else ""
        
        db.session.commit()
        flash("API Keys saved securely.", "success")
        return redirect(url_for('settings_page'))

    user_keys = get_user_keys(user_email)
    return render_template("settings.html", user_keys=user_keys)


# ─── Contacts Management ─────────────────────────────────────────────────────

@app.route("/contacts")
@login_required
def contacts():
    all_contacts = Contact.query.order_by(Contact.name).all()
    return render_template("contacts.html", contacts=all_contacts)


@app.route("/contacts/add", methods=["POST"])
@login_required
@admin_required
def add_contact():
    name = request.form.get("name", "").strip()
    c_type = request.form.get("type", "").strip()
    holder_name = request.form.get("holder_name", "").strip()
    position = request.form.get("position", "").strip()
    
    if name:
        contact = Contact(
            name=name,
            type=c_type if c_type else None,
            holder_name=holder_name,
            position=position
        )
        db.session.add(contact)
        db.session.commit()
        flash("Contact added successfully.", "success")
    else:
        flash("Name is required.", "danger")
        
    return redirect(url_for('contacts'))


@app.route("/contacts/edit/<int:contact_id>", methods=["POST"])
@login_required
@admin_required
def edit_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    contact.name = request.form.get("name", "").strip()
    c_type = request.form.get("type", "").strip()
    contact.type = c_type if c_type else None
    contact.holder_name = request.form.get("holder_name", "").strip()
    contact.position = request.form.get("position", "").strip()
    
    db.session.commit()
    flash("Contact updated successfully.", "success")
    return redirect(url_for('contacts'))


@app.route("/contacts/delete/<int:contact_id>", methods=["POST"])
@login_required
@admin_required
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    flash("Contact deleted successfully.", "success")
    return redirect(url_for('contacts'))


@app.route("/uploads/<path:filename>")
@login_required
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", 5001)))
    app.run(debug=True, host="0.0.0.0", port=port)