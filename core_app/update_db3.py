import os, psycopg
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get("SUPABASE_DB_URL")
if db_url.startswith("postgresql+psycopg://"):
    db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS manager_is_sender BOOLEAN DEFAULT FALSE;")
    conn.commit()
print("Migration 3 completed.")
