"""
migrate_db_ai_keys.py
One-shot migration: add gemini_api_key, groq_api_key, deepseek_api_key columns to users table.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "documents.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

columns_to_add = [
    ("gemini_api_key",   "TEXT"),
    ("groq_api_key",     "TEXT"),
    ("deepseek_api_key", "TEXT"),
]

for col_name, col_type in columns_to_add:
    try:
        cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        print(f"Added column: {col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"Column already exists: {col_name}")
        else:
            raise

conn.commit()
conn.close()
print("Migration complete.")
