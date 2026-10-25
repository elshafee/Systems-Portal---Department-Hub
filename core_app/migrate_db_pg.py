from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN gemini_api_key TEXT;"))
        db.session.commit()
        print("Added gemini_api_key")
    except Exception as e:
        db.session.rollback()
        print(f"gemini_api_key error: {e}")

    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN groq_api_key TEXT;"))
        db.session.commit()
        print("Added groq_api_key")
    except Exception as e:
        db.session.rollback()
        print(f"groq_api_key error: {e}")

    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN deepseek_api_key TEXT;"))
        db.session.commit()
        print("Added deepseek_api_key")
    except Exception as e:
        db.session.rollback()
        print(f"deepseek_api_key error: {e}")

print("Migration complete")
