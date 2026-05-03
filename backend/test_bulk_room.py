import pandas as pd
from app.database import SessionLocal
from app.models import Room
from sqlalchemy.exc import IntegrityError

db = SessionLocal()
df = pd.read_excel("venues_register.xlsx")

from app.routers.rooms import _COL_ALIASES
df.columns = [c.strip().lower() for c in df.columns]
rename_map = {col: _COL_ALIASES[col] for col in df.columns if col in _COL_ALIASES}
df = df.rename(columns=rename_map)
df = df.loc[:, ~df.columns.duplicated()]

for idx, row in df.iterrows():
    row_name = str(row.get("name", ""))
    room_data = {
        "name": row_name,
        "capacity": 30,
        "room_type": "lecture_hall",
        "priority_level": 5,
        "is_blocked": False
    }
    
    existing = db.query(Room).filter(Room.name == row_name).first()
    if existing:
        pass
    else:
        db.add(Room(**room_data))

try:
    db.commit()
    print("COMMIT SUCCESS")
except Exception as e:
    print(f"COMMIT FAILED WITH: {e}")

db.close()
