from sqlalchemy import create_engine, text
engine = create_engine('postgresql://tablesys:J8rQ4mN2xV9pL6cT1sW7kD3hF5bZ0yUa@localhost:5432/tablesys_db')
with engine.connect() as conn:
    res = conn.execute(text("SELECT level, code FROM courses WHERE id IN (SELECT course_id FROM timetable_slots WHERE timetable_id=5)"))
    for row in res:
        print(row)
