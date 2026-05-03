"""
Test 1: Verify OR-Tools Installation and Basic Functionality
Run this first to ensure OR-Tools is working correctly.
"""

from ortools.sat.python import cp_model
import sys

def test_ortools_installation():
    """Test if OR-Tools is installed and working"""
    print("=" * 60)
    print("TEST 1: OR-Tools Installation Check")
    print("=" * 60)
    
    try:
        # Simple test: Schedule 2 tasks in 3 time slots
        model = cp_model.CpModel()
        
        # Variables: Task A and Task B can be in slots 0, 1, or 2
        task_a = model.NewIntVar(0, 2, 'task_a')
        task_b = model.NewIntVar(0, 2, 'task_b')
        
        # Constraint: Tasks can't be in the same slot
        model.Add(task_a != task_b)
        
        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("✅ OR-Tools is WORKING!")
            print(f"   Task A scheduled at slot: {solver.Value(task_a)}")
            print(f"   Task B scheduled at slot: {solver.Value(task_b)}")
            print(f"   Solve time: {solver.WallTime()}s")
            return True
        else:
            print("❌ OR-Tools solver returned unexpected status")
            return False
            
    except ImportError as e:
        print("❌ OR-Tools NOT INSTALLED or import failed")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_constraint_programming():
    """Test more complex constraint programming"""
    print("\n" + "=" * 60)
    print("TEST 2: Constraint Programming with Optimization")
    print("=" * 60)
    
    try:
        # Problem: Schedule 3 courses in 5 time slots
        # Each course has 1 session
        # Maximize "preference" (later slots are better)
        
        model = cp_model.CpModel()
        
        # Variables
        course_1 = model.NewIntVar(0, 4, 'course_1')
        course_2 = model.NewIntVar(0, 4, 'course_2')
        course_3 = model.NewIntVar(0, 4, 'course_3')
        
        # Constraints: No conflicts
        model.Add(course_1 != course_2)
        model.Add(course_1 != course_3)
        model.Add(course_2 != course_3)
        
        # Objective: Maximize sum of time slots (prefer later)
        model.Maximize(course_1 + course_2 + course_3)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL:
            print("✅ Constraint optimization WORKING!")
            print(f"   Course 1 at slot: {solver.Value(course_1)}")
            print(f"   Course 2 at slot: {solver.Value(course_2)}")
            print(f"   Course 3 at slot: {solver.Value(course_3)}")
            print(f"   Total score: {solver.ObjectiveValue()}")
            return True
        else:
            print("❌ Failed to find optimal solution")
            return False
            
    except Exception as e:
        print(f"❌ Error in constraint programming test: {e}")
        return False

def test_boolean_variables():
    """Test BoolVar usage (used in actual timetable generator)"""
    print("\n" + "=" * 60)
    print("TEST 3: Boolean Variables (Actual Timetable Pattern)")
    print("=" * 60)
    
    try:
        model = cp_model.CpModel()
        
        # Create binary variables for each possible assignment
        # Format: course_slot_room
        vars = {}
        
        # 2 courses, 3 slots, 2 rooms
        for course in range(2):
            for slot in range(3):
                for room in range(2):
                    var_name = f'c{course}_t{slot}_r{room}'
                    vars[(course, slot, room)] = model.NewBoolVar(var_name)
        
        # Constraint 1: Each course assigned exactly once
        for course in range(2):
            course_vars = [vars[(course, slot, room)] 
                          for slot in range(3) 
                          for room in range(2)]
            model.Add(sum(course_vars) == 1)
        
        # Constraint 2: Room can't be double-booked
        for slot in range(3):
            for room in range(2):
                room_vars = [vars[(course, slot, room)] 
                            for course in range(2)]
                model.Add(sum(room_vars) <= 1)
        
        # Objective: Prefer room 0
        objective_terms = []
        for k, var in vars.items():
            course, slot, room = k
            if room == 0:
                objective_terms.append(var * 10)  # Bonus for room 0
        
        model.Maximize(sum(objective_terms))
        
        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL:
            print("✅ Boolean variable pattern WORKING!")
            print("   Assignments:")
            for k, var in vars.items():
                if solver.Value(var) == 1:
                    course, slot, room = k
                    print(f"     Course {course} → Slot {slot}, Room {room}")
            return True
        else:
            print("❌ Failed to solve with boolean variables")
            return False
            
    except Exception as e:
        print(f"❌ Error in boolean variable test: {e}")
        return False

if __name__ == "__main__":
    print("\n🔍 TABLESYS OR-Tools Verification Suite\n")
    
    results = []
    results.append(test_ortools_installation())
    results.append(test_constraint_programming())
    results.append(test_boolean_variables())
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if all(results):
        print("✅ ALL TESTS PASSED - OR-Tools is fully functional!")
        print("   You can proceed to test the actual timetable generator.")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("   Fix OR-Tools installation before proceeding.")
        sys.exit(1)
