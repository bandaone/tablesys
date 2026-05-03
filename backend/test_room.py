import pandas as pd
from app.database import SessionLocal
from app.models import Room
import os

db = SessionLocal()
df = pd.read_excel("venues_register.xlsx")
df.columns = [c.strip().lower() for c in df.columns]
rename_map = {"type": "furniture_type"}
df = df.rename(columns=rename_map)

for idx, row in df.iterrows():
    row_name = str(row.get("name", ""))
    print(f"Row {idx+2}: {row_name}")
    room_data = {
        "name": row_name,
        "capacity": 30,
        "room_type": "lecture_hall",
        "priority_level": 5,
        "is_blocked": False
    }
    try:
        model = Room(**room_data)
        print("Model generated OK")
    except Exception as exc:
        print(f"FAILED: {exc}")
        break

db.close()
