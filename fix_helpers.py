import re

with open("backend/app/services/dashboard_service.py", "r") as f:
    content = f.read()

replacements = [
    (r"def _user_query\(self\):\s*query = self\._user_query\(\)", "def _user_query(self):\n        query = self.db.query(User)"),
    (r"def _course_query\(self\):\s*query = self\._course_query\(\)", "def _course_query(self):\n        query = self.db.query(Course)"),
    (r"def _lecturer_query\(self\):\s*query = self\._lecturer_query\(\)", "def _lecturer_query(self):\n        query = self.db.query(Lecturer)"),
    (r"def _room_query\(self\):\s*query = self\._room_query\(\)", "def _room_query(self):\n        query = self.db.query(Room)"),
    (r"def _group_query\(self\):\s*query = self\._group_query\(\)", "def _group_query(self):\n        query = self.db.query(StudentGroup)"),
    (r"def _timetable_query\(self\):\s*query = self\._timetable_query\(\)", "def _timetable_query(self):\n        query = self.db.query(Timetable)"),
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open("backend/app/services/dashboard_service.py", "w") as f:
    f.write(content)

