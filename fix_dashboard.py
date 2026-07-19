import re

with open("backend/app/services/dashboard_service.py", "r") as f:
    content = f.read()

# 1. Add query helpers
helpers = """    def _user_query(self):
        query = self.db.query(User)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(User.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            query = query.filter((User.school_id == self.user.school_id) | (User.id == self.user.id))
        return query
        
    def _course_query(self):
        query = self.db.query(Course)
        if self.user and getattr(self.user, "university_id", None):
            query = query.join(Department, Course.department_id == Department.id)
            query = query.filter(Department.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Department.school_id == self.user.school_id)
        return query
        
    def _lecturer_query(self):
        query = self.db.query(Lecturer)
        if self.user and getattr(self.user, "university_id", None):
            query = query.join(Department, Lecturer.department_id == Department.id)
            query = query.filter(Department.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Department.school_id == self.user.school_id)
        return query
        
    def _room_query(self):
        query = self.db.query(Room)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Room.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Room.school_id == self.user.school_id)
        return query
        
    def _group_query(self):
        query = self.db.query(StudentGroup)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(StudentGroup.university_id == self.user.university_id)
            # Groups are scoped to department, which is scoped to school. For simplicity, join department if school is needed.
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.join(Department, StudentGroup.department_id == Department.id).filter(Department.school_id == self.user.school_id)
        return query
        
    def _timetable_query(self):
        query = self.db.query(Timetable)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Timetable.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Timetable.school_id == self.user.school_id)
        return query"""

# Replace the existing _user_query with our new block of helpers
content = re.sub(r'    def _user_query\(self\):.*?return query', helpers, content, flags=re.DOTALL)

# Now systematically replace db.query(func.count(Model.id)) with self._model_query().with_entities(func.count(Model.id))
# And db.query(Model) with self._model_query()

replacements = [
    (r'self\.db\.query\(func\.count\(User\.id\)\)', r'self._user_query().with_entities(func.count(User.id))'),
    (r'self\.db\.query\(func\.count\(Department\.id\)\)', r'self._department_query().with_entities(func.count(Department.id))'),
    (r'self\.db\.query\(func\.count\(Course\.id\)\)', r'self._course_query().with_entities(func.count(Course.id))'),
    (r'self\.db\.query\(func\.count\(Lecturer\.id\)\)', r'self._lecturer_query().with_entities(func.count(Lecturer.id))'),
    (r'self\.db\.query\(func\.count\(Room\.id\)\)', r'self._room_query().with_entities(func.count(Room.id))'),
    (r'self\.db\.query\(func\.count\(StudentGroup\.id\)\)', r'self._group_query().with_entities(func.count(StudentGroup.id))'),
    (r'self\.db\.query\(func\.count\(Timetable\.id\)\)', r'self._timetable_query().with_entities(func.count(Timetable.id))'),
    (r'self\.db\.query\(User\)', r'self._user_query()'),
    (r'self\.db\.query\(Department\)', r'self._department_query()'),
    (r'self\.db\.query\(Course\)', r'self._course_query()'),
    (r'self\.db\.query\(Lecturer\)', r'self._lecturer_query()'),
    (r'self\.db\.query\(Room\)', r'self._room_query()'),
    (r'self\.db\.query\(StudentGroup\)', r'self._group_query()'),
    (r'self\.db\.query\(Timetable\)', r'self._timetable_query()'),
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open("backend/app/services/dashboard_service.py", "w") as f:
    f.write(content)

print("Updated dashboard_service.py successfully!")
