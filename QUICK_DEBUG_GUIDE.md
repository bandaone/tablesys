# 🚀 QUICK START: DEBUGGING TABLESYS

## Run These Commands (In Order):

```powershell
# 1. Test OR-Tools
cd c:\SYSTEMS\TABLESYS\backend
python test_ortools_basic.py

# 2. Check database data
python verify_timetable_data.py

# 3. Test solver logic
python test_solver_minimal.py

# 4. Try full generation
python debug_generation.py
```

---

## Expected Outcomes:

### ✅ SUCCESS:
- All tests show "✅ PASSED"
- Data verification shows courses, lecturers, rooms, groups
- Debug generation completes with slots created

### ❌ FAILURE:
- Report exact error message to me
- Note which test failed

---

## If Data Missing:

```powershell
python seed_db.py
python seed_users.py
```

---

## Files Created for You:

1. **SYSTEM_AUDIT_REPORT.md** - Complete analysis of your system
2. **DEBUG_WORKFLOW.md** - Detailed debugging guide
3. **test_ortools_basic.py** - OR-Tools installation test
4. **verify_timetable_data.py** - Database integrity check
5. **test_solver_minimal.py** - Constraint solver unit tests
6. **debug_generation.py** - Full generation with logging
7. **THIS FILE** - Quick reference

---

## What Exists in Your System:

✅ OR-Tools installed (v9.8.3296)  
✅ Full CP-SAT solver implementation (488 lines)  
✅ Neural Brain optimization layer  
✅ WebSocket real-time updates  
✅ Level-by-level generation (5→4→3→2)  
✅ Complete database models  

---

## Current Issues to Fix:

⚠️ Room filtering logic incomplete  
⚠️ Session parsing defaults may be wrong  
⚠️ Variable explosion risk with large datasets  
⚠️ Over-constrained scenarios possible  

---

## Next Steps After Tests Pass:

1. Start backend: `uvicorn app.main:app --reload`
2. Start frontend: `npm run dev`
3. Login as "coordinator"
4. Create timetable and click "Generate"
5. Watch progress in real-time

---

**START HERE:** Run `python test_ortools_basic.py` and report results!
