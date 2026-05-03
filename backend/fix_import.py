# Fix missing Request import in courses.py

with open("c:/SYSTEMS/TABLESYS/backend/app/routers/courses.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add Request import to line 1
content = content.replace(
    "from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File",
    "from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request"
)

with open("c:/SYSTEMS/TABLESYS/backend/app/routers/courses.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Added Request import to courses.py")
