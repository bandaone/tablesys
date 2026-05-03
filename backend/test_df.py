import pandas as pd
import io

data = """Staff Number\tFull Name\tCourses Responsible For\tNo. of Courses
LEC001\tMr. Charles Musonda (Geomatics)\tGEE 5411\t1
LEC002\tDr. D. E. Banda\tEEE 3571, EEE 4221, EEE 4571\t3
LEC003\tDr. Faustin Banda\tGEE 4122\t1
LEC004\tMr. Daniel Brobbey\tCEE 4511\t1"""

text = data
if "\t" in text and text.count("\t") > text.count(","):
    sep = "\t"
else:
    sep = ";" if text.count(";") > text.count(",") else ","

print(f"Using separator: {repr(sep)}")
df = pd.read_csv(io.StringIO(text), sep=sep)
print("Columns:", df.columns.tolist())
df.columns = [c.strip().lower() for c in df.columns]

_COL_ALIASES = {
    "staff number": "staff_number",
    "full name": "full_name",
    "courses responsible for": "courses",
    "no. of courses": "__skip"
}
rename_map = {col: _COL_ALIASES[col] for col in df.columns if col in _COL_ALIASES}
df = df.rename(columns=rename_map)
print("Renamed:", df.columns.tolist())
for idx, row in df.iterrows():
    print(row.to_dict())
