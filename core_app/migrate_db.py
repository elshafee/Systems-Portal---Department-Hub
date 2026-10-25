import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.environ.get("SUPABASE_DB_URL"))
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS sender_position TEXT;"))
    conn.commit()
    print("Added sender_position column!")
