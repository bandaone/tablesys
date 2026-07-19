with open("backend/app/services/dashboard_service.py", "r") as f:
    content = f.read()

# Replace is_generated with is_active (the actual model field)
# A timetable is "generated" if its generation_metadata is not null
# For simplicity, use is_active as a proxy (generated timetables are made active)
content = content.replace("Timetable.is_generated == True", "Timetable.generation_metadata != None")
content = content.replace("Timetable.is_generated == False", "Timetable.generation_metadata == None")
content = content.replace('"is_generated": tt.is_generated', '"is_generated": tt.generation_metadata is not None')

# Also remove Timetable.updated_at references (doesn't exist anymore)
content = content.replace("Timetable.updated_at.desc()", "Timetable.id.desc()")
content = content.replace("Timetable.updated_at >= seven_days_ago,\n            Timetable.is_generated == True", 'Timetable.generation_metadata != None')
content = content.replace("Timetable.updated_at >= week_start,\n            Timetable.is_generated == True", 'Timetable.generation_metadata != None')
content = content.replace('"updated_at": tt.updated_at.isoformat() if tt.updated_at else None', '"updated_at": None')

# Timetable doesn't have department_id
content = content.replace("Timetable.department_id == dept.id", "False")

with open("backend/app/services/dashboard_service.py", "w") as f:
    f.write(content)

print("Done!")
