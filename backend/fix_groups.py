import re

# Read groups.py
with open('app/routers/groups.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Normal create_group
content = content.replace(
    "group_data['level'] = resolved_level",
    "group_data['level'] = resolved_level\n\n    # Inject university_id to satisfy not-null constraint\n    group_data['university_id'] = getattr(current_user, 'university_id', None) or 1\n"
)

# 2. Bulk upload
content = re.sub(
    r"(size=int\([^)]+\))\n",
    r"\1,\n                    university_id=getattr(current_user, 'university_id', None) or 1\n",
    content
)

# 3. Subgroup auto-generation
content = content.replace(
    '"display_code": suffix',
    '"display_code": suffix,\n            "university_id": getattr(current_user, "university_id", None) or 1'
)

# Write back
with open('app/routers/groups.py', 'w', encoding='utf-8') as f:
    f.write(content)
