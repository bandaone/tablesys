"""
Script to add audit logging to courses.py bulk upload endpoint.
This script adds the missing audit logging code after db.commit() and in the exception handler.
"""

import re

# Read the file
with open("c:/SYSTEMS/TABLESYS/backend/app/routers/courses.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the db.commit() line in bulk_upload_courses function and add audit logging
# Pattern: db.commit() followed by return statement
pattern1 = r"(        db\.commit\(\)\r?\n        \r?\n)(        return \{)"

replacement1 = r"""\1        # Log successful bulk upload
        AuditLogger.log_bulk_upload(
            request=request,
            user_id=current_user.id,
            username=current_user.username,
            resource_type="course",
            count=created_count,
            success=True,
            details={"filename": file.filename, "created": created_count, "skipped": skipped_count}
        )
        
\2"""

content = re.sub(pattern1, replacement1, content)

# Find the exception handler and add audit logging
pattern2 = r"(    except Exception as e:\r?\n)(        raise HTTPException\(status_code=400, detail=f\"Error processing file: \{str\(e\)\}\"\))"

replacement2 = r"""\1        # Log failed bulk upload
        AuditLogger.log_bulk_upload(
            request=request,
            user_id=current_user.id,
            username=current_user.username,
            resource_type="course",
            count=0,
            success=False,
            details={"filename": file.filename, "error": str(e)}
        )
        
        \2"""

content = re.sub(pattern2, replacement2, content)

# Write back
with open("c:/SYSTEMS/TABLESYS/backend/app/routers/courses.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Added audit logging to courses.py bulk upload endpoint")
