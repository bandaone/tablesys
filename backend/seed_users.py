import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import Base, engine
from app.seeding_utils import seed_database_at_startup

def seed_users():
    print("[*] Ensuring database tables exist based on current models...")
    Base.metadata.create_all(bind=engine)
    
    print("[*] Beginning user and institution seeding...")
    seed_database_at_startup()

if __name__ == "__main__":
    seed_users()
