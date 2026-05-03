import pandas as pd
import io

data = """Name	Building	Type	Equipment	Capacity	Availability	Priority
Agricultural Engineering Lab Room	Agricultural Engineering Building	Lab	Lab equipment	30	Mon-Fri 07:00-19:00	standard
Soil Physics Lab	Agricultural Engineering Building	Lab	Soil physics equipment	25	Mon-Fri 07:00-19:00	standard
Computer Room	Agricultural Engineering Building	Computer Lab	Computers	30	Mon-Fri 07:00-19:00	high
Conference Room	Agricultural Engineering Building	Conference Room	Whiteboard; Projector	20	Mon-Fri 07:00-19:00	standard"""

text = data
if "\t" in text and text.count("\t") > text.count(","):
    sep = "\t"
else:
    sep = ";" if text.count(";") > text.count(",") else ","

df = pd.read_csv(io.StringIO(text), sep=sep)
print("Original Columns:", df.columns.tolist())

_COL_ALIASES = {
    "code": "code", "room code": "code", "venue code": "code",
    "name": "name", "room name": "name", "venue name": "name", "venue": "name",
    "building": "building", "block": "building",
    "furniture type": "furniture_type", "furniture": "furniture_type", "room type": "room_type", "type": "furniture_type",
    "equipment": "equipment", "equipment list": "equipment",
    "capacity": "capacity", "size": "capacity", "seats": "capacity",
    "availability": "availability", "available": "availability",
    "priority": "priority_level", "priority level": "priority_level", "priority_level": "priority_level"
}

df.columns = [c.strip().lower() for c in df.columns]
rename_map = {col: _COL_ALIASES[col] for col in df.columns if col in _COL_ALIASES}
df = df.rename(columns=rename_map)

print("Renamed Columns:", df.columns.tolist())

# Needed columns check
if "name" not in df.columns and "code" not in df.columns:
    print("Error: Missing name/code")
if "capacity" not in df.columns:
    print("Error: Missing capacity")

for idx, row in df.iterrows():
    print(row.to_dict())
