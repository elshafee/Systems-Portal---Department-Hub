"""
keep_alive.py — Automated script to ping and write to Supabase databases.
Keeps Supabase projects active by performing a real write operation so they never pause.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Include project roots
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def ping_database(url: str, label: str = ""):
    if not url:
        return
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    host_info = url.split("@")[-1] if "@" in url else "database"
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 15})
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS keep_alive (id INT PRIMARY KEY, pinged_at TIMESTAMP, note TEXT);"))
            conn.execute(text("INSERT INTO keep_alive (id, pinged_at, note) VALUES (1, NOW(), 'automated heartbeat') ON CONFLICT (id) DO UPDATE SET pinged_at = NOW();"))
            conn.commit()
            print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}] SUCCESS: Wrote keep-alive heartbeat to {label or host_info}")
            return True
    except Exception as e:
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}] FAILED for {label or host_info}: {e}")
        return False

if __name__ == "__main__":
    targets = {
        "Active Database": os.environ.get("SUPABASE_DB_URL"),
        "Vice Dean": os.environ.get("SUPABASE_DB_URL_VICE_DEAN", "postgresql+psycopg://postgres.ucxlldcmvguetxjgghfx:8wD.xVc4s%3DxdA6P@aws-1-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"),
        "AIE": os.environ.get("SUPABASE_DB_URL_AIE", "postgresql+psycopg://postgres.vkcedjubluzooadtvtci:NxdjC2p.Z%40qR%2B76@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"),
        "ESSIC": os.environ.get("SUPABASE_DB_URL_ESSIC", "postgresql+psycopg://postgres.spjivemssfkebihjfvae:mXP%248u73SQNNM6D@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"),
    }

    seen = set()
    for label, url in targets.items():
        if url and url not in seen:
            seen.add(url)
            ping_database(url, label)
