"""
app.py — ESSIC Document Numbering + AI Arabic Generation System
"""

import os, sys
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, abort, jsonify
)
from werkzeug.utils import secure_filename

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import db, Document
from services.numbering import get_next_serial, build_full_code
from services.word_editor import replace_placeholders
from services.ai_generator import (
    generate_arabic_text, build_full_document_text, get_available_models
)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER    = os.path.join(BASE_DIR, "uploads")
GENERATED_FOLDER = os.path.join(BASE_DIR, "generated")

app = Flask(__name__)
app.secret_key = "essic-ai-doc-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'documents.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER,    exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

db.init_app(app)
with app.app_context():
    db.create_all()


# ── Helpers ───────────────────────────────────────────────────────────────────

ALLOWED = {"docx"}

def allowed(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED

MODELS = [
    "openai/gpt-oss-20b",
    "google/gemma-4-12b",
    "mistralai/ministral-3-3b",
    "qwen/qwen3-coder-30b",
]
SIGNATORY = (
    ""
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("step1"))


# ── STEP 1: Choose type ───────────────────────────────────────────────────────

@app.route("/new", methods=["GET"])
def step1():
    return render_template("step1.html")


# ── STEP 2: Fill in fields + draft ───────────────────────────────────────────

@app.route("/compose/<doc_type>", methods=["GET"])
def step2(doc_type):
    if doc_type not in ("letter", "request"):
        return redirect(url_for("step1"))
    return render_template("step2.html", doc_type=doc_type, models=MODELS)


# ── STEP 3: AI generates → preview ───────────────────────────────────────────

@app.route("/generate", methods=["POST"])
def step3():
    doc_type  = request.form.get("doc_type", "letter")
    sender    = request.form.get("sender", "").strip()
    recipient = request.form.get("recipient", "").strip()
    subject   = request.form.get("subject", "").strip()
    raw_draft = request.form.get("raw_draft", "").strip()
    model     = request.form.get("model", MODELS[0])

    if not all([sender, recipient, subject, raw_draft]):
        flash("يرجى ملء جميع الحقول المطلوبة.", "warning")
        return redirect(url_for("step2", doc_type=doc_type))

    result = generate_arabic_text(
        doc_type=doc_type,
        sender=sender,
        recipient=recipient,
        subject=subject,
        raw_draft=raw_draft,
        model=model,
    )

    if not result["success"]:
        flash(f"خطأ في الاتصال بـ LM Studio: {result['error']}", "danger")
        return redirect(url_for("step2", doc_type=doc_type))

    full_body = build_full_document_text(
        doc_type=doc_type,
        sender=sender,
        recipient=recipient,
        subject=subject,
        generated_body=result["text"],
        signatory=SIGNATORY,
    )

    return render_template("step3.html",
        doc_type=doc_type,
        sender=sender,
        recipient=recipient,
        subject=subject,
        raw_draft=raw_draft,
        generated_body=result["text"],
        full_body=full_body,
        model=model,
        models=MODELS,
    )


# ── STEP 4: Upload template + finalize ───────────────────────────────────────

@app.route("/finalize", methods=["POST"])
def step4():
    doc_type      = request.form.get("doc_type", "letter")
    sender        = request.form.get("sender", "")
    recipient     = request.form.get("recipient", "")
    subject       = request.form.get("subject", "")
    raw_draft     = request.form.get("raw_draft", "")
    full_body     = request.form.get("full_body", "")
    model         = request.form.get("model", MODELS[0])

    file = request.files.get("docx_file")
    if not file or file.filename == "":
        flash("يرجى رفع ملف القالب (.docx).", "warning")
        return redirect(url_for("step1"))
    if not allowed(file.filename):
        flash("يُقبل ملفات .docx فقط.", "danger")
        return redirect(url_for("step1"))

    original_name = secure_filename(file.filename)
    upload_path   = os.path.join(UPLOAD_FOLDER, original_name)
    file.save(upload_path)

    now    = datetime.now()
    serial = get_next_serial(now.month, now.year)
    code   = build_full_code(serial, now.month, now.year)

    stem           = original_name.rsplit(".", 1)[0]
    gen_name       = f"{stem}__{code.replace(' ', '_')}.docx"
    gen_path       = os.path.join(GENERATED_FOLDER, gen_name)

    try:
        replace_placeholders(upload_path, gen_path, {
            "{{CODE_NUMBER}}": code,
            "{{BODY_TEXT}}":   full_body,
        })
    except Exception as e:
        flash(f"خطأ في معالجة المستند: {e}", "danger")
        return redirect(url_for("step1"))

    doc = Document(
        serial_number=serial,
        full_code=code,
        month=now.month,
        year=now.year,
        doc_type=doc_type,
        sender=sender,
        recipient=recipient,
        subject=subject,
        raw_draft=raw_draft,
        generated_body=full_body,
        filename=original_name,
        generated_filename=gen_name,
        ai_model=model,
    )
    db.session.add(doc)
    db.session.commit()

    flash(f"تم إنشاء المستند بنجاح — الرمز: <strong>Code No {code}</strong>", "success")
    return redirect(url_for("documents"))


# ── AJAX: regenerate body only ────────────────────────────────────────────────

@app.route("/api/regenerate", methods=["POST"])
def api_regenerate():
    data      = request.get_json()
    result    = generate_arabic_text(
        doc_type  = data.get("doc_type", "letter"),
        sender    = data.get("sender", ""),
        recipient = data.get("recipient", ""),
        subject   = data.get("subject", ""),
        raw_draft = data.get("raw_draft", ""),
        model     = data.get("model", MODELS[0]),
    )
    if result["success"]:
        full_body = build_full_document_text(
            doc_type      = data.get("doc_type", "letter"),
            sender        = data.get("sender", ""),
            recipient     = data.get("recipient", ""),
            subject       = data.get("subject", ""),
            generated_body= result["text"],
            signatory     = SIGNATORY,
        )
        return jsonify({"success": True, "body": result["text"], "full_body": full_body})
    return jsonify({"success": False, "error": result["error"]})


# ── Documents history ─────────────────────────────────────────────────────────

@app.route("/documents")
def documents():
    all_docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("documents.html", documents=all_docs, now=datetime.now())


@app.route("/download/<int:doc_id>")
def download(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if not doc.generated_filename:
        abort(404)
    return send_from_directory(GENERATED_FOLDER, doc.generated_filename,
                               as_attachment=True)


@app.route("/edit/<int:doc_id>", methods=["GET", "POST"])
def edit(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if request.method == "POST":
        try:
            new_serial = int(request.form["serial_number"])
            if new_serial < 1:
                raise ValueError
        except (ValueError, KeyError):
            flash("الرقم التسلسلي يجب أن يكون عدداً صحيحاً موجباً.", "danger")
            return redirect(url_for("edit", doc_id=doc_id))

        new_code = build_full_code(new_serial, doc.month, doc.year)
        upload_path = os.path.join(UPLOAD_FOLDER, doc.filename)
        if not os.path.exists(upload_path):
            flash("الملف الأصلي غير موجود. لا يمكن إعادة الإنشاء.", "danger")
            return redirect(url_for("documents"))

        if doc.generated_filename:
            old = os.path.join(GENERATED_FOLDER, doc.generated_filename)
            if os.path.exists(old):
                os.remove(old)

        stem     = doc.filename.rsplit(".", 1)[0]
        gen_name = f"{stem}__{new_code.replace(' ', '_')}.docx"
        gen_path = os.path.join(GENERATED_FOLDER, gen_name)

        try:
            replace_placeholders(upload_path, gen_path, {
                "{{CODE_NUMBER}}": new_code,
                "{{BODY_TEXT}}":   doc.generated_body or "",
            })
        except Exception as e:
            flash(f"خطأ: {e}", "danger")
            return redirect(url_for("documents"))

        doc.serial_number      = new_serial
        doc.full_code          = new_code
        doc.generated_filename = gen_name
        db.session.commit()

        flash(f"تم تحديث الرمز إلى <strong>Code No {new_code}</strong>", "success")
        return redirect(url_for("documents"))

    return render_template("edit.html", doc=doc)


@app.route("/delete/<int:doc_id>", methods=["POST"])
def delete(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.generated_filename:
        p = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        if os.path.exists(p):
            os.remove(p)
    db.session.delete(doc)
    db.session.commit()
    flash("تم حذف السجل.", "info")
    return redirect(url_for("documents"))


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
