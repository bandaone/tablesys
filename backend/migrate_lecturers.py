import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("Error: No DATABASE_URL found in .env")
    exit(1)

engine = create_engine(db_url)

try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE lecturers ADD COLUMN IF NOT EXISTS welcome_email_sent BOOLEAN DEFAULT FALSE;"))
        conn.commit()
    print("Successfully added welcome_email_sent column to lecturers table.")
except Exception as e:
    print(f"Migration failed or column already exists: {e}")
