import re

with open("backend/app/services/dashboard_service.py", "r") as f:
    content = f.read()

replacements = [
    (
        r"self\.db\.query\(\s*Department\.name,\s*func\.count\(Timetable\.id\)\.label\('count'\)\s*\)\.join\(Timetable\)\.group_by\(Department\.name\)",
        r"self._department_query().with_entities(Department.name, func.count(Timetable.id).label('count')).join(Timetable).group_by(Department.name)"
    ),
    (
        r"self\.db\.query\(func\.count\(TimetableSlot\.id\)\)",
        r"self._timetable_query().join(TimetableSlot).with_entities(func.count(TimetableSlot.id))"
    ),
    (
        r"self\.db\.query\(func\.count\(TimetableVersion\.id\)\)",
        r"self._timetable_query().join(TimetableVersion).with_entities(func.count(TimetableVersion.id))"
    ),
    (
        r"self\.db\.query\(func\.count\(distinct\(TimetableSlot\.room_id\)\)\)",
        r"self._timetable_query().join(TimetableSlot).with_entities(func.count(distinct(TimetableSlot.room_id)))"
    ),
    (
        r"self\.db\.query\(func\.count\(distinct\(TimetableSlot\.lecturer_id\)\)\)",
        r"self._timetable_query().join(TimetableSlot).with_entities(func.count(distinct(TimetableSlot.lecturer_id)))"
    ),
    (
        r"self\.db\.query\(\s*func\.sum\(Course\.credit_hours\)\s*\)\.join\(TimetableSlot\)",
        r"self._course_query().join(TimetableSlot, TimetableSlot.course_id == Course.id).with_entities(func.sum(Course.credit_hours))"
    ),
    (
        r"self\.db\.query\(\s*func\.avg\(\s*case\(\s*\(\(Room\.capacity > 0,\s*\(StudentGroup\.size \* 100\.0\) / Room\.capacity\)\),\s*else_=0\s*\)\s*\)\s*\)\.join\(TimetableSlot,\s*TimetableSlot\.room_id == Room\.id\)",
        r"self._room_query().with_entities(func.avg(case(((Room.capacity > 0, (StudentGroup.size * 100.0) / Room.capacity)), else_=0))).join(TimetableSlot, TimetableSlot.room_id == Room.id)"
    ),
    (
        r"self\.db\.query\(Notification\)\.order_by",
        r"self.db.query(Notification).filter(Notification.university_id == self.user.university_id if getattr(self.user, 'university_id', None) else True).order_by"
    ),
    (
        r"self\.db\.query\(\s*Lecturer\.id,\s*Lecturer\.name,\s*func\.sum\(Course\.credit_hours\)\.label\('total_hours'\)\s*\)\.join\(TimetableSlot,\s*TimetableSlot\.lecturer_id == Lecturer\.id\)",
        r"self._lecturer_query().with_entities(Lecturer.id, Lecturer.name, func.sum(Course.credit_hours).label('total_hours')).join(TimetableSlot, TimetableSlot.lecturer_id == Lecturer.id)"
    ),
    (
        r"self\.db\.query\(func\.count\(TimetableSlot\.id\)\)\.join\(\s*Room\s*\)\.join\(StudentGroup\)",
        r"self._timetable_query().with_entities(func.count(TimetableSlot.id)).join(TimetableSlot).join(Room, TimetableSlot.room_id == Room.id).join(StudentGroup, TimetableSlot.group_id == StudentGroup.id)"
    ),
    (
        r"self\.db\.query\(func\.count\(Notification\.id\)\)\.filter",
        r"self.db.query(func.count(Notification.id)).filter(Notification.university_id == self.user.university_id if getattr(self.user, 'university_id', None) else True).filter"
    ),
    (
        r"self\.db\.query\(func\.count\(distinct\(LecturerAssignment\.course_id\)\)\)",
        r"self._course_query().join(LecturerAssignment).with_entities(func.count(distinct(LecturerAssignment.course_id)))"
    ),
    (
        r"self\.db\.query\(func\.count\(distinct\(GroupAssignment\.course_id\)\)\)",
        r"self._course_query().join(GroupAssignment).with_entities(func.count(distinct(GroupAssignment.course_id)))"
    ),
    (
        r"self\.db\.query\(func\.count\(distinct\(CourseGroupLink\.course_id\)\)\)",
        r"self._course_query().join(CourseGroupLink).with_entities(func.count(distinct(CourseGroupLink.course_id)))"
    ),
    (
        r"self\.db\.query\(Timetable\)\.filter",
        r"self._timetable_query().filter"
    )
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open("backend/app/services/dashboard_service.py", "w") as f:
    f.write(content)

print("Second pass done!")
