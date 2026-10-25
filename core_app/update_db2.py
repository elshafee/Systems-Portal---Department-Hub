import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("SUPABASE_DB_URL")
if db_url.startswith("postgresql+psycopg://"):
    db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS holder_name TEXT;")
        cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS position TEXT;")
        cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_internal BOOLEAN DEFAULT FALSE;")
    conn.commit()
print("Migration 2 completed.")
