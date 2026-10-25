"""
Database migration script to add tracking and response columns to the documents table.
Compatible with Supabase PostgreSQL and local SQLite.
"""

import os
import sys
from dotenv import load_dotenv

# Load env variables from root and current directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

supabase_url = os.environ.get("SUPABASE_DB_URL")

columns_to_add = [
    ("is_sent", "BOOLEAN DEFAULT FALSE"),
    ("sent_date", "TIMESTAMP WITHOUT TIME ZONE"),
    ("sent_method", "VARCHAR(50)"),
    ("sent_by", "VARCHAR(100)"),
    ("received_by", "VARCHAR(100)"),              # Added per user requirement: who received the sent document internally
    ("sent_notes", "TEXT"),
    ("requires_response", "BOOLEAN DEFAULT FALSE"),
    ("response_deadline", "DATE"),
    ("response_status", "VARCHAR(50) DEFAULT 'not_sent'"),
    ("response_date", "TIMESTAMP WITHOUT TIME ZONE"),
    ("response_ref", "VARCHAR(100)"),
    ("response_summary", "TEXT"),
    ("response_file", "VARCHAR(255)"),
    ("response_received_by", "VARCHAR(100)"),
    ("followup_notes", "TEXT"),
]

def migrate_postgres():
    if not supabase_url:
        print("SUPABASE_DB_URL not found, skipping PostgreSQL migration.")
        return False
    
    db_url = supabase_url
    if db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
        
    import psycopg
    print("Connecting to Supabase PostgreSQL...")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for col_name, col_type in columns_to_add:
                try:
                    sql = f"ALTER TABLE documents ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
                    cur.execute(sql)
                    print(f"  + Column '{col_name}' added or already exists.")
                except Exception as e:
                    print(f"  ! Error adding '{col_name}': {e}")
        conn.commit()
    print("PostgreSQL migration completed successfully.")
    return True

def migrate_sqlite():
    sqlite_paths = [
        os.path.join(os.path.dirname(__file__), "documents.db"),
        os.path.join(os.path.dirname(__file__), "instance", "documents.db"),
    ]
    import sqlite3
    for path in sqlite_paths:
        if os.path.exists(path) and os.path.isfile(path):
            print(f"Migrating SQLite DB at {path}...")
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(documents);")
            existing = [row[1] for row in cur.fetchall()]
            for col_name, col_type in columns_to_add:
                if col_name not in existing:
                    try:
                        cur.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type};")
                        print(f"  + SQLite column '{col_name}' added.")
                    except Exception as e:
                        print(f"  ! SQLite error adding '{col_name}': {e}")
            conn.commit()
            conn.close()
            print(f"SQLite DB at {path} updated.")

if __name__ == "__main__":
    pg_success = migrate_postgres()
    migrate_sqlite()
    print("All migrations finished.")
