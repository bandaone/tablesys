# Fix indentation error in courses.py line 275

with open("c:/SYSTEMS/TABLESYS/backend/app/routers/courses.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix line 275 (index 274) - remove extra indentation
if len(lines) > 274:
    lines[274] = "        raise HTTPException(status_code=400, detail=f\"Error processing file: {str(e)}\")\n"

with open("c:/SYSTEMS/TABLESYS/backend/app/routers/courses.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Fixed indentation error in courses.py")
