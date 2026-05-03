"""
One-shot script to fix HTML-escaped group names in the database.
Converts names like 'Civil &amp; Environmental Engineering'
back to 'Civil & Environmental Engineering'.
"""
import html
import sys
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models import StudentGroup

db = SessionLocal()

try:
    groups = db.query(StudentGroup).all()
    fixed = 0
    for g in groups:
        unescaped = html.unescape(g.name)
        if unescaped != g.name:
            print(f"  FIX: '{g.name}'  →  '{unescaped}'")
            g.name = unescaped
            fixed += 1
    
    if fixed:
        db.commit()
        print(f"\n✅ Fixed {fixed} group name(s).")
    else:
        print("✅ No escaped names found — database is clean.")
finally:
    db.close()
