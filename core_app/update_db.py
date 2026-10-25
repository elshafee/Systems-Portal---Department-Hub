import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("SUPABASE_DB_URL")
# Replace psycopg schemes if needed for standard psycopg
if db_url.startswith("postgresql+psycopg://"):
    db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS generated_pdf_filename VARCHAR(255);")
    conn.commit()
print("Migration completed.")
