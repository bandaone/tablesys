# 🔍 TABLESYS SYSTEM AUDIT REPORT
**Date:** February 18, 2026  
**Phase:** Week 3 - Debug & Fix Existing System

---

## ✅ WHAT EXISTS (DISCOVERY PHASE)

### **A. Backend Files - ALL PRESENT**

#### **Services:**
- ✅ `backend/app/services/timetable_generator.py` - **488 lines** - FULL CP-SAT IMPLEMENTATION
- ✅ `backend/app/services/neural_brain.py` - **110 lines** - Pattern recognition & optimization
- ✅ `backend/app/services/export_service.py` - Export functionality

#### **Routers:**
- ✅ `backend/app/routers/timetables.py` - **WebSocket generation endpoint**

#### **Models:**
- ✅ Complete database schema with all enums and relationships
- ✅ OR-Tools integration confirmed in `requirements.txt` (version 9.8.3296)

---

## 🧩 CURRENT ARCHITECTURE ANALYSIS

### **1. Timetable Generation Flow**

```
User clicks "Generate" → WebSocket Connection → TimetableGenerator
                                                        ↓
                        Level-by-Level Generation (5→4→3→2)
                                                        ↓
                        CP-SAT Solver (OR-Tools) with Constraints
                                                        ↓
                        Real-time Progress Updates → Frontend
                                                        ↓
                        Save Slots to Database
```

### **2. OR-Tools Implementation Status**

✅ **INSTALLED**: `ortools==9.8.3296` in requirements.txt  
✅ **IMPORTED**: Used in `timetable_generator.py`  
✅ **INTEGRATED**: Full CP-SAT constraint programming implementation

The solver is **FULLY IMPLEMENTED** with:
- Variable creation for valid course-room-time-lecturer combinations
- Hard constraints (no conflicts)
- Soft constraints (preferences, optimization)
- Neural Brain integration for weight scoring

### **3. The "Neural Brain" System**

**Purpose:** Add intelligent optimization on top of CP-SAT solver  
**Location:** `backend/app/services/neural_brain.py`

**Features:**
- Analyzes historical scheduling patterns
- Provides "link weight" scores for room-level-time combinations
- Integrates coordinator manual overrides
- Group-specific venue preferences

**Integration:** Objective function in CP-SAT solver uses neural weights × 1000 for integer scoring

---

## 🛠️ CONSTRAINT SOLVER BREAKDOWN

### **Current Constraints Implemented:**

#### **HARD CONSTRAINTS (Must Satisfy):**
1. ✅ **Session Coverage**: Each course session assigned exactly once per group
2. ✅ **Room Conflicts**: Room can't be used by 2+ groups at same time
3. ✅ **Lecturer Conflicts**: Lecturer can't teach 2+ classes simultaneously
4. ✅ **Group Conflicts**: Student group can't be in 2+ places at once
5. ✅ **Level Isolation**: Higher levels scheduled first, their slots block lower levels
6. ✅ **Daily Load Limit**: Max 8 contact hours per day per group
7. ✅ **Duration Fit**: Sessions must fit within time slots (07:00-19:00)

#### **SOFT CONSTRAINTS (Optimization Goals):**
1. ✅ **Neural Link Weights**: Room-level affinity scoring (scaled × 1000)
2. ✅ **Golden Hours Bonus**: +200 points for 09:00-12:00 slots
3. ✅ **Fatigue Penalty**: -300 points for slots starting after 16:00
4. ✅ **Lecturer Preferences**: -500 penalty for unwanted times
5. ✅ **Room Type Matching**: Compatible rooms filtered before variable creation

---

## 🔍 POTENTIAL ISSUES IDENTIFIED

### **Issue 1: Variable Explosion (Scaling Problem)**

**Symptom:** Solver might take forever or run out of memory

**Cause:**  
For each course with N sessions, M groups, L lecturers, R rooms:  
Variables = N × M × L × R × 5 days × 12 time slots = **MASSIVE**

**Example:**  
- 20 courses × 2 sessions each = 40 sessions
- 40 × 4 groups × 3 lecturers × 10 rooms × 5 × 12 = **288,000 variables**

**Status:** ⚠️ **HIGH RISK** - Need to verify data size

---

### **Issue 2: Over-Constrained Scenarios**

**Symptom:** Solver returns INFEASIBLE (no solution exists)

**Possible Causes:**
1. Too few rooms for number of courses
2. Lecturer unavailability too restrictive
3. Room type mismatches (lab courses but no labs)
4. Conflicting group assignments
5. Previous level slots block all remaining slots

**Status:** ⚠️ **NEEDS TESTING**

---

### **Issue 3: Room Filtering Logic**

**Location:** `timetable_generator.py` lines 155-185

**Current Issue:**  
```python
# Line 169: Incomplete logic
if course.preferred_room_type == RoomType.ANY:
    # Adds ALL rooms, including inappropriate ones
```

**Problem:** "ANY" type courses still get inappropriate rooms (e.g., lecture in drawing room)

**Status:** ⚠️ **NEEDS REFINEMENT**

---

### **Issue 4: Session Parsing Logic**

**Location:** `timetable_generator.py` lines 83-141

**Potential Issue:**  
```python
requires_consecutive = config.get('requires_consecutive', 1)
if isinstance(requires_consecutive, bool):
    requires_consecutive = 2 if requires_consecutive else 1
```

**Risk:** If courses don't have `session_configuration` JSON, defaults to 1-hour blocks. This may create too many sessions for long courses.

**Status:** ⚠️ **VERIFY DATA INTEGRITY**

---

### **Issue 5: Database Session in WebSocket**

**Location:** `timetables.py` line 91

```python
db = next(get_db())  # Gets session
# ...
finally:
    if db:
        db.close()  # Manually closed
```

**Risk:** WebSocket endpoint doesn't use proper async database handling. May cause connection pool issues.

**Status:** ⚠️ **ARCHITECTURAL CONCERN**

---

## 📊 DATA REQUIREMENTS FOR TESTING

### **Minimum Data Needed:**

1. **Departments:** At least 2 (e.g., CS, EEE)
2. **Courses:** 5-10 courses per level (levels 2-5)
3. **Lecturers:** 5-10 lecturers with assignments
4. **Rooms:** 10-15 rooms (mix of types)
5. **Student Groups:** 2-4 groups per department per level
6. **Assignments:**
   - GroupAssignment: Link groups to courses
   - LecturerAssignment: Link lecturers to courses

### **Data Integrity Checks Needed:**

```sql
-- Check if courses have lecturers
SELECT * FROM courses c 
WHERE NOT EXISTS (
    SELECT 1 FROM lecturer_assignments la 
    WHERE la.course_id = c.id
);

-- Check if courses have groups
SELECT * FROM courses c 
WHERE NOT EXISTS (
    SELECT 1 FROM group_assignments ga 
    WHERE ga.course_id = c.id
);

-- Check room type distribution
SELECT room_type, COUNT(*) FROM rooms GROUP BY room_type;
```

---

## 🎯 DEBUGGING ROADMAP

### **PHASE 1: VERIFY INSTALLATION (30 minutes)**

**Step 1:** Test OR-Tools Independently
```bash
cd backend
python -c "from ortools.sat.python import cp_model; print('✅ OR-Tools Working')"
```

**Step 2:** Check Database Connectivity
```bash
python -m pytest tests/test_api.py::test_database_connection
```

**Step 3:** Verify Data Exists
```bash
python verify_timetable_data.py
```

---

### **PHASE 2: ISOLATED SOLVER TEST (2 hours)**

**Create:** `backend/test_solver_simple.py`

**Goal:** Test CP-SAT with minimal data:
1. 1 course, 1 group, 1 lecturer, 2 rooms → Should succeed
2. 2 courses (conflict), 1 room → Should detect conflict
3. 5 courses, 3 rooms → Test constraint satisfaction

**Success Criteria:** Solver returns OPTIMAL or FEASIBLE

---

### **PHASE 3: INCREMENTAL TESTING (4-6 hours)**

1. **Test Level 5 Only** (smallest dataset)
   - Generate for 5th year only
   - Should complete in < 30 seconds
   
2. **Test Levels 5+4** (medium dataset)
   - Verify previous level blocking works
   
3. **Full Generation** (all levels)
   - Monitor solver time
   - Check for memory issues

---

### **PHASE 4: CONSTRAINT DEBUGGING (6-8 hours)**

**If solver fails:**

1. **Log Constraint Violations**
   ```python
   # Add to generator before solving
   print(f"Variables: {len(vars_store)}")
   print(f"Constraints: {model.NumConstraints()}")
   ```

2. **Relax Constraints Incrementally**
   - Remove soft constraints first
   - Increase daily load limit (8 → 10 hours)
   - Allow more overlap tolerance

3. **Check for Empty Results**
   ```python
   if not vars_store:
       print("❌ NO VARIABLES CREATED - CHECK DATA!")
   ```

---

## 🚨 IMMEDIATE ACTION ITEMS (NEXT 2 HOURS)

### ✅ **CHECKPOINT 1: Environment Verification**
- [ ] Confirm OR-Tools installed
- [ ] Verify Python version (3.10+)
- [ ] Check PostgreSQL connection

### ✅ **CHECKPOINT 2: Data Audit**
- [ ] Count courses, lecturers, rooms, groups
- [ ] Verify assignments exist
- [ ] Check for orphaned courses

### ✅ **CHECKPOINT 3: Simple Test**
- [ ] Create minimal test script
- [ ] Generate timetable for 1 level
- [ ] Inspect solver output

---

## 📝 NEXT STEPS AFTER AUDIT

**IF SOLVER WORKS:**
→ Move to UI testing and end-to-end validation

**IF SOLVER FAILS:**
→ Follow Phase 2-4 debugging steps above

**IF DATA MISSING:**
→ Run seed scripts, verify bulk upload works

---

## 🔧 TOOLS PROVIDED

I'll create the following test scripts:

1. `test_ortools_basic.py` - Verify OR-Tools installation
2. `test_solver_minimal.py` - Minimal constraint test
3. `verify_timetable_data.py` - Database data audit
4. `debug_generation.py` - Full generation with verbose logging

---

**STATUS:** Ready for hands-on debugging  
**NEXT:** Run verification scripts and report findings
