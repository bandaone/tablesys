import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from app.seeding_utils import seed_database_at_startup

def seed_users():
    print("[*] Beginning user and institution seeding...")
    seed_database_at_startup()

if __name__ == "__main__":
    seed_users()
