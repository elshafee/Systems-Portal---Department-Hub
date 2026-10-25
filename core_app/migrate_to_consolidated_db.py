"""
migrate_to_consolidated_db.py

Migrates all records from Vice Dean and AIE databases into the primary ESSIC database,
and stamps all existing ESSIC records with office_code = 'ESSIC'.
"""
import os
import sys
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PRIMARY_URL = "postgresql+psycopg://postgres.spjivemssfkebihjfvae:mXP%248u73SQNNM6D@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"

SOURCES = [
    {
        "name": "Vice Dean",
        "office_code": "HUEED",
        "url": "postgresql+psycopg://postgres.ucxlldcmvguetxjgghfx:8wD.xVc4s%3DxdA6P@aws-1-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"
    },
    {
        "name": "AIE",
        "office_code": "AIE",
        "url": "postgresql+psycopg://postgres.vkcedjubluzooadtvtci:NxdjC2p.Z%40qR%2B76@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"
    }
]

def run_migration():
    print(f"Connecting to primary database (ESSIC)...")
    primary_eng = create_engine(PRIMARY_URL)

    with primary_eng.connect() as p_conn:
        # 1. Stamp all existing documents in ESSIC with office_code = 'ESSIC'
        res = p_conn.execute(text("UPDATE documents SET office_code = 'ESSIC' WHERE office_code IS NULL OR office_code = '';"))
        print(f"Updated existing ESSIC documents with office_code='ESSIC': {res.rowcount} rows.")
        
        # Stamp contacts in ESSIC
        res_c = p_conn.execute(text("UPDATE contacts SET office_code = 'ESSIC' WHERE office_code IS NULL OR office_code = '';"))
        print(f"Updated existing ESSIC contacts with office_code='ESSIC': {res_c.rowcount} rows.")
        p_conn.commit()

        # Existing user emails in primary
        existing_users = set(p_conn.execute(text("SELECT email FROM users")).scalars().all())
        existing_doc_codes = set(p_conn.execute(text("SELECT full_code FROM documents")).scalars().all())
        existing_contact_names = set(p_conn.execute(text("SELECT name FROM contacts")).scalars().all())

        for src in SOURCES:
            print(f"\nProcessing {src['name']} ({src['office_code']})...")
            try:
                src_eng = create_engine(src['url'])
                with src_eng.connect() as s_conn:
                    # A. Migrate Users
                    s_users = s_conn.execute(text("SELECT * FROM users")).mappings().all()
                    users_added = 0
                    for u in s_users:
                        if u['email'] not in existing_users:
                            cols = list(u.keys())
                            col_str = ", ".join(cols)
                            param_str = ", ".join([f":{c}" for c in cols])
                            p_conn.execute(text(f"INSERT INTO users ({col_str}) VALUES ({param_str})"), dict(u))
                            existing_users.add(u['email'])
                            users_added += 1
                    print(f"  -> Migrated {users_added} new users from {src['name']}.")

                    # B. Migrate Contacts
                    contacts_added = 0
                    if s_conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'contacts')")).scalar():
                        s_contacts = s_conn.execute(text("SELECT * FROM contacts")).mappings().all()
                        for c in s_contacts:
                            if c['name'] not in existing_contact_names:
                                c_dict = dict(c)
                                c_dict.pop('id', None) # allow auto-increment in primary
                                c_dict['office_code'] = src['office_code']
                                cols = list(c_dict.keys())
                                col_str = ", ".join(cols)
                                param_str = ", ".join([f":{k}" for k in cols])
                                p_conn.execute(text(f"INSERT INTO contacts ({col_str}) VALUES ({param_str})"), c_dict)
                                existing_contact_names.add(c['name'])
                                contacts_added += 1
                    print(f"  -> Migrated {contacts_added} contacts from {src['name']}.")

                    # C. Migrate Documents (if any)
                    docs_added = 0
                    if s_conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'documents')")).scalar():
                        s_docs = s_conn.execute(text("SELECT * FROM documents")).mappings().all()
                        for d in s_docs:
                            if d['full_code'] not in existing_doc_codes:
                                d_dict = dict(d)
                                d_dict.pop('id', None) # allow auto-increment in primary
                                d_dict['office_code'] = src['office_code']
                                cols = list(d_dict.keys())
                                col_str = ", ".join(cols)
                                param_str = ", ".join([f":{k}" for k in cols])
                                p_conn.execute(text(f"INSERT INTO documents ({col_str}) VALUES ({param_str})"), d_dict)
                                existing_doc_codes.add(d['full_code'])
                                docs_added += 1
                    print(f"  -> Migrated {docs_added} documents from {src['name']}.")

                    p_conn.commit()
            except Exception as e:
                print(f"  -> Warning during {src['name']} migration: {e}")

    print("\nConsolidated database migration finished successfully!")

if __name__ == "__main__":
    run_migration()
