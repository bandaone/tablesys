# 🎯 PHASE 2: DEBUG & FIX WORKFLOW

## Your Current Status: READY FOR TESTING ✅

I've completed the system audit. Here's what I found and what you need to do next.

---

## 📋 AUDIT FINDINGS

### ✅ WHAT'S WORKING:

1. **OR-Tools is installed** (v9.8.3296)
2. **Full CP-SAT implementation exists** (488 lines in timetable_generator.py)
3. **Neural Brain optimization layer** is integrated
4. **WebSocket real-time updates** implemented
5. **Level-by-level algorithm** (5→4→3→2) is complete
6. **Database models** are comprehensive

### ⚠️ POTENTIAL ISSUES IDENTIFIED:

1. **Variable explosion** - Could create 100k+ variables with full dataset
2. **Room filtering logic** - Incomplete for "ANY" room type
3. **Session parsing** - May default to 1-hour blocks without proper config
4. **Over-constrained scenarios** - Solver may fail if resources insufficient
5. **WebSocket async handling** - Database session management could be improved

---

## 🛠️ YOUR DEBUGGING TOOLKIT

I've created 4 test scripts for you:

### 1. `test_ortools_basic.py` - Verify OR-Tools Installation
Tests if the constraint solver works at all.

```powershell
cd c:\SYSTEMS\TABLESYS\backend
python test_ortools_basic.py
```

**Expected**: "✅ ALL TESTS PASSED"

---

### 2. `verify_timetable_data.py` - Check Database Data
Verifies you have sufficient data for generation.

```powershell
python verify_timetable_data.py
```

**Checks:**
- Courses, lecturers, rooms, groups exist
- All courses have lecturers assigned
- All courses have student groups assigned
- Room types are available
- Estimates solver complexity

**Expected**: Should show data counts and identify orphaned courses

---

### 3. `test_solver_minimal.py` - Test Constraint Logic
Tests the CP-SAT solver with simplified scenarios.

```powershell
python test_solver_minimal.py
```

**Tests:**
- Single course scheduling
- Multiple courses without conflicts
- Resource conflict detection
- Multi-session courses
- Complex 5-course scenario

**Expected**: All 5 tests should pass

---

### 4. `debug_generation.py` - Full Generation with Logging
Runs actual timetable generation with verbose output.

```powershell
python debug_generation.py
```

**Shows:**
- Data audit before generation
- Real-time progress updates
- Exact error messages if it fails
- Slot counts and samples if successful

---

## 🚦 YOUR ACTION PLAN (NEXT 2 HOURS)

### STEP 1: Run Tests in Order (30 minutes)

```powershell
# Navigate to backend
cd c:\SYSTEMS\TABLESYS\backend

# Test 1: OR-Tools
python test_ortools_basic.py
# If this fails, OR-Tools isn't installed properly

# Test 2: Database Data
python verify_timetable_data.py
# If this shows missing data, run seed_db.py

# Test 3: Solver Logic
python test_solver_minimal.py
# If this fails, there's a fundamental solver issue

# Test 4: Full Generation
python debug_generation.py
# This shows what actually happens
```

---

### STEP 2: Interpret Results (30 minutes)

#### Scenario A: All Tests Pass ✅
→ Your system is working! Try generating from the UI.

#### Scenario B: Data Issues ⚠️
→ Run database seeding:
```powershell
python seed_db.py
python seed_users.py
```

#### Scenario C: Solver Fails ❌
→ Report to me which test failed and the error message.

---

### STEP 3: Try UI Generation (30 minutes)

If tests pass:

1. **Start the backend:**
   ```powershell
   cd c:\SYSTEMS\TABLESYS\backend
   uvicorn app.main:app --reload
   ```

2. **Start the frontend:**
   ```powershell
   cd c:\SYSTEMS\TABLESYS\frontend
   npm run dev
   ```

3. **Login and generate:**
   - Go to http://localhost:3000
   - Login as "coordinator"
   - Create a new timetable
   - Click "Generate"
   - Watch the progress

---

### STEP 4: Report Back (30 minutes)

Tell me one of these:

**OPTION A: "It worked!"**
→ Great! We move to Phase 3 (enhancements)

**OPTION B: "Test X failed with error Y"**
→ I'll help you fix it

**OPTION C: "Generation started but..."**
→ Describe what you see (progress stuck? error message? timeout?)

---

## 🔍 HOW TO READ THE OUTPUT

### Good Signs:
- ✅ symbols everywhere
- "Status: OPTIMAL" or "FEASIBLE"
- Solver time < 60 seconds
- Slots created and saved

### Bad Signs:
- ❌ symbols or errors
- "Status: INFEASIBLE" → Over-constrained
- Solver runs forever (>5 min) → Too many variables
- "No variables created" → Data mismatch
- Exception traces → Code bug

---

## 💡 COMMON FIXES

### Problem: "No courses in database"
```powershell
cd c:\SYSTEMS\TABLESYS\backend
python seed_db.py
```

### Problem: "Courses have no lecturers"
Check lecturer_assignments table, or re-seed.

### Problem: "INFEASIBLE status"
- Too few rooms for courses
- Reduce number of courses being generated
- Check room type requirements

### Problem: "Takes forever"
- Variable explosion (too many courses)
- Try generating one level at a time
- Reduce time slots or days

---

## 📊 WHAT I NEED FROM YOU

Run the tests and tell me:

1. **Which tests passed/failed?**
2. **Error messages** (copy-paste exact text)
3. **Data counts** from verify_timetable_data.py
4. **What happens in the UI?** (if you get that far)

---

## 🎯 NEXT PHASE PREVIEW

Once generation works:

**Phase 3A: Bug Fixes**
- Fix room filtering logic
- Improve session parsing
- Handle edge cases

**Phase 3B: Enhancements**
- Better conflict resolution
- Lecturer unavailability checks
- Gap prevention (no free periods)

**Phase 3C: UI Improvements**
- Visual timetable calendar
- Conflict highlighting
- Export to PDF/Excel

---

## 📞 READY TO START?

Run this now:

```powershell
cd c:\SYSTEMS\TABLESYS\backend
python test_ortools_basic.py
```

Then report the output! 🚀
