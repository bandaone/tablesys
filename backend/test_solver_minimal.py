"""
Minimal Solver Test - Tests CP-SAT with simplified timetable problem
This tests the core algorithm logic without full database complexity.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ortools.sat.python import cp_model
from datetime import time

def print_section(title):
    """Print section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_single_course():
    """Test 1: Can we schedule 1 course with 1 session?"""
    print_section("TEST 1: Single Course, Single Session")
    
    try:
        model = cp_model.CpModel()
        
        # Problem: 1 course, 1 session, 1 lecture, 1 room
        # 5 days, 12 time slots per day (07:00-18:00)
        # Expected: Should easily find a solution
        
        # Variables: BoolVar for each (day, time_slot)
        vars = {}
        for day in range(5):
            for time_slot in range(12):
                var_name = f'day{day}_slot{time_slot}'
                vars[(day, time_slot)] = model.NewBoolVar(var_name)
        
        # Constraint: Exactly one slot must be selected
        model.Add(sum(vars.values()) == 1)
        
        # Objective: Prefer middle of day (slot 2-5 = 09:00-12:00)
        objective_terms = []
        for (day, slot), var in vars.items():
            if 2 <= slot <= 5:
                objective_terms.append(var * 100)  # Bonus for good time
            elif slot >= 9:
                objective_terms.append(var * -50)  # Penalty for late
        
        model.Maximize(sum(objective_terms))
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL:
            print("✅ TEST PASSED")
            # Find selected slot
            for (day, slot), var in vars.items():
                if solver.Value(var) == 1:
                    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                    print(f"   Scheduled: {days[day]} at {7+slot}:00")
                    print(f"   Objective score: {solver.ObjectiveValue()}")
            return True
        else:
            print(f"❌ TEST FAILED - Status: {status}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_two_courses_no_conflict():
    """Test 2: Two courses, different lecturers, different rooms"""
    print_section("TEST 2: Two Courses, No Resource Conflicts")
    
    try:
        model = cp_model.CpModel()
        
        # 2 courses, 2 sessions total
        # Each course needs 1 session
        # Different lecturers, different rooms (no conflicts)
        
        vars_course1 = {}
        vars_course2 = {}
        
        for day in range(5):
            for slot in range(12):
                vars_course1[(day, slot)] = model.NewBoolVar(f'c1_d{day}_t{slot}')
                vars_course2[(day, slot)] = model.NewBoolVar(f'c2_d{day}_t{slot}')
        
        # Each course assigned exactly once
        model.Add(sum(vars_course1.values()) == 1)
        model.Add(sum(vars_course2.values()) == 1)
        
        # No student overlap constraint (they can be at different times)
        # This should be easy to solve
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("✅ TEST PASSED")
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            
            for (day, slot), var in vars_course1.items():
                if solver.Value(var) == 1:
                    print(f"   Course 1: {days[day]} at {7+slot}:00")
            
            for (day, slot), var in vars_course2.items():
                if solver.Value(var) == 1:
                    print(f"   Course 2: {days[day]} at {7+slot}:00")
            
            return True
        else:
            print(f"❌ TEST FAILED - Status: {status}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_resource_conflict():
    """Test 3: Two courses, same room - must detect conflict"""
    print_section("TEST 3: Resource Conflict Detection")
    
    try:
        model = cp_model.CpModel()
        
        # 2 courses, same room, same student group
        # They MUST be at different times
        
        vars_course1 = {}
        vars_course2 = {}
        
        for day in range(5):
            for slot in range(12):
                vars_course1[(day, slot)] = model.NewBoolVar(f'c1_d{day}_t{slot}')
                vars_course2[(day, slot)] = model.NewBoolVar(f'c2_d{day}_t{slot}')
        
        # Each course assigned exactly once
        model.Add(sum(vars_course1.values()) == 1)
        model.Add(sum(vars_course2.values()) == 1)
        
        # CONFLICT CONSTRAINT: Same room means only one course per slot
        for day in range(5):
            for slot in range(12):
                model.Add(vars_course1[(day, slot)] + vars_course2[(day, slot)] <= 1)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("✅ TEST PASSED - Conflict resolved")
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            
            c1_time = None
            c2_time = None
            
            for (day, slot), var in vars_course1.items():
                if solver.Value(var) == 1:
                    c1_time = (day, slot)
                    print(f"   Course 1: {days[day]} at {7+slot}:00")
            
            for (day, slot), var in vars_course2.items():
                if solver.Value(var) == 1:
                    c2_time = (day, slot)
                    print(f"   Course 2: {days[day]} at {7+slot}:00")
            
            # Verify they're at different times
            if c1_time != c2_time:
                print("   ✅ Courses scheduled at different times (no overlap)")
                return True
            else:
                print("   ❌ ERROR: Courses overlap!")
                return False
        else:
            print(f"❌ TEST FAILED - Status: {status}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multi_session_course():
    """Test 4: One course with 2 consecutive sessions"""
    print_section("TEST 4: Multi-Session Course (2-hour block)")
    
    try:
        model = cp_model.CpModel()
        
        # 1 course needs 2 consecutive hours
        # Variables: start time (day, slot) where slot+1 must also be free
        
        vars = {}
        for day in range(5):
            for slot in range(11):  # 0-10 (last valid start for 2-hour block)
                var_name = f'day{day}_slot{slot}'
                vars[(day, slot)] = model.NewBoolVar(var_name)
        
        # Exactly one start time selected
        model.Add(sum(vars.values()) == 1)
        
        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("✅ TEST PASSED")
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            
            for (day, slot), var in vars.items():
                if solver.Value(var) == 1:
                    print(f"   Scheduled: {days[day]} from {7+slot}:00 to {9+slot}:00")
            return True
        else:
            print(f"❌ TEST FAILED - Status: {status}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_complex_scenario():
    """Test 5: Realistic mini-scenario with 5 courses"""
    print_section("TEST 5: Complex Scenario (5 courses, 2 rooms, 1 lecturer)")
    
    try:
        model = cp_model.CpModel()
        
        # 5 courses, 3 rooms, 2 lecturers
        # Each course: 1 session (1 hour)
        # Constraints:
        #   - Room can't be double-booked
        #   - Lecturer can't teach 2 courses at once
        #   - Same level students (courses 0,1,2 for group A)
        
        num_courses = 5
        num_rooms = 3
        num_lecturers = 2
        
        # Lecturer assignments
        course_to_lecturer = {0: 0, 1: 0, 2: 1, 3: 1, 4: 1}
        
        # Student group assignments
        course_to_group = {0: 0, 1: 0, 2: 0, 3: 1, 4: 1}
        
        vars = {}
        
        # Create variables: course x day x slot x room
        for course in range(num_courses):
            for day in range(5):
                for slot in range(12):
                    for room in range(num_rooms):
                        var_name = f'c{course}_d{day}_t{slot}_r{room}'
                        vars[(course, day, slot, room)] = model.NewBoolVar(var_name)
        
        # Constraint 1: Each course assigned exactly once
        for course in range(num_courses):
            course_vars = [vars[(course, day, slot, room)]
                          for day in range(5)
                          for slot in range(12)
                          for room in range(num_rooms)]
            model.Add(sum(course_vars) == 1)
        
        # Constraint 2: Room conflicts
        for day in range(5):
            for slot in range(12):
                for room in range(num_rooms):
                    room_vars = [vars[(course, day, slot, room)]
                                for course in range(num_courses)]
                    model.Add(sum(room_vars) <= 1)
        
        # Constraint 3: Lecturer conflicts
        for day in range(5):
            for slot in range(12):
                for lecturer in range(num_lecturers):
                    lecturer_courses = [c for c in range(num_courses) 
                                       if course_to_lecturer[c] == lecturer]
                    lecturer_vars = [vars[(course, day, slot, room)]
                                    for course in lecturer_courses
                                    for room in range(num_rooms)]
                    model.Add(sum(lecturer_vars) <= 1)
        
        # Constraint 4: Student group conflicts
        for day in range(5):
            for slot in range(12):
                for group in range(2):
                    group_courses = [c for c in range(num_courses)
                                    if course_to_group[c] == group]
                    group_vars = [vars[(course, day, slot, room)]
                                 for course in group_courses
                                 for room in range(num_rooms)]
                    model.Add(sum(group_vars) <= 1)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("✅ TEST PASSED - Complex scenario solved!")
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            rooms = ['Lab A', 'Lab B', 'LT']
            
            print("\n   Schedule:")
            for course in range(num_courses):
                for (c, day, slot, room), var in vars.items():
                    if c == course and solver.Value(var) == 1:
                        print(f"   Course {course}: {days[day]} {7+slot}:00, "
                              f"{rooms[room]}, Lec {course_to_lecturer[course]}")
            
            print(f"\n   Solve time: {solver.WallTime()}s")
            return True
        else:
            print(f"❌ TEST FAILED - Status: {status}")
            print(f"   This might indicate an over-constrained problem")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all solver tests"""
    print("\n🧪 TABLESYS MINIMAL SOLVER TEST SUITE")
    print("=" * 70)
    print("Tests CP-SAT constraint solver with simplified scenarios")
    
    results = []
    
    results.append(test_single_course())
    results.append(test_two_courses_no_conflict())
    results.append(test_resource_conflict())
    results.append(test_multi_session_course())
    results.append(test_complex_scenario())
    
    # Summary
    print_section("📋 TEST SUMMARY")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if all(results):
        print("\n✅ ALL SOLVER TESTS PASSED!")
        print("   The CP-SAT solver is working correctly.")
        print("\n   Next steps:")
        print("   1. Run: python verify_timetable_data.py")
        print("   2. Then try generating from the UI")
        return 0
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("   This indicates a problem with the CP-SAT solver logic.")
        print("   Review the failed tests above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
