import os
from sqlalchemy import create_engine

# URL encoded password: $ becomes %24
supabase_url = "postgresql+psycopg://postgres.spjivemssfkebihjfvae:mXP%248u73SQNNM6D@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"

print(f"Connecting to: {supabase_url}")
engine = create_engine(supabase_url)
try:
    with engine.connect() as conn:
        print("Connected successfully!")
except Exception as e:
    print(f"Error: {e}")
