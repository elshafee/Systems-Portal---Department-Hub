import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

load_dotenv()

supabase_url = os.environ.get("SUPABASE_DB_URL", "")
# if it is commented out in .env, let's just use the string directly:
if not supabase_url:
    supabase_url = "postgresql://postgres.spjivemssfkebihjfvae:mXP$8u73SQNNM6D@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

supabase_url = supabase_url.replace("postgresql://", "postgresql+psycopg://", 1)

print(f"Connecting to: {supabase_url}")
engine = create_engine(supabase_url)
try:
    with engine.connect() as conn:
        print("Connected successfully!")
except Exception as e:
    print(f"Error: {e}")
