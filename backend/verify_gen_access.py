from app.database import SessionLocal
from app.models import User, Course, UserRole

def verify_gen_access():
    db = SessionLocal()
    gen_user = db.query(User).filter(User.username == 'GEN').first()
    if not gen_user:
        print("GEN user not found.")
        return

    print(f"User: {gen_user.username}, Role: {gen_user.role}, Dept: {gen_user.department_id}")
    
    # Simulate get_courses filtering logic
    db.query(Course)
    if gen_user.role == UserRole.HOD and gen_user.department_id is not None:
        # For simplicity in this script, we just check the direct department_id
        # since we haven't uploaded courses yet, let's create a dummy one
        dummy_course = Course(code="GEN101", name="General Course", department_id=0, level=1, credits=3, lecture_hours=3)
        db.add(dummy_course)
        db.flush()
        
        courses = db.query(Course).filter(Course.department_id == gen_user.department_id).all()
        print(f"Visible courses for GEN: {[c.code for c in courses]}")
    
    db.rollback()
    db.close()

if __name__ == "__main__":
    verify_gen_access()
