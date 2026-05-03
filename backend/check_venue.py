import pandas as pd
df = pd.read_excel("venues_register.xlsx")
cols = [c.strip().lower() for c in df.columns]
print(f"Columns: {cols}")
