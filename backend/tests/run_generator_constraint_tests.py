"""
CHECKPOINT 3 – Generator Template Constraint Tests
===================================================

Tests that TimetableGenerator correctly:
1. Loads a TemplateProfile and builds the allowed_slots index.
2. Enforces slot-placement constraints via _is_slot_allowed.
3. Operates in unconstrained mode when no profile is provided.

Run directly (no DB, no pytest conftest required):
    cd backend
    python tests/run_generator_constraint_tests.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = "[PASS]"
FAIL = "[FAIL]"
results = {"passed": 0, "failed": 0}


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS} {name}")
        results["passed"] += 1
    else:
        print(f"  {FAIL} {name}" + (f"\n       detail: {detail}" if detail else ""))
        results["failed"] += 1


# ---------------------------------------------------------------------------
# We test only the helper methods in isolation — they don't need a DB.
# We create a minimal fake generator instance.
# ---------------------------------------------------------------------------

class FakeDB:
    """Minimal DB that returns a fake profile from query()."""
    def __init__(self, profile=None):
        self._profile = profile

    def query(self, model):
        return self

    def filter(self, *args):
        return self

    def first(self):
        return self._profile


class FakeProfile:
    """Minimal TemplateProfile-like object."""
    def __init__(self, containers):
        self.id = 1
        self.containers = containers


def make_generator(containers=None, with_profile=True):
    """
    Create a TimetableGenerator with a fake DB.
    Bypasses __init__ DB calls by patching after construction.
    """
    from app.services.timetable_generator import TimetableGenerator
    from datetime import time

    # Build a minimal generator without hitting DB at __init__ time
    gen = object.__new__(TimetableGenerator)
    gen.days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    gen.time_slots = [(time(7 + i, 0), time(8 + i, 0)) for i in range(12)]
    gen.all_slots = []
    gen.existing_slots = []
    gen.components = ['lecture', 'tutorial', 'practical']
    gen.allowed_slots = {}
    gen.template_profile_id = 1 if with_profile else None

    if with_profile and containers is not None:
        profile = FakeProfile(containers)
        gen.db = FakeDB(profile)
        gen._load_template_constraints(1)
    else:
        gen.db = FakeDB(None)

    return gen


# ---------------------------------------------------------------------------
# Test 1: No template -> unconstrained (all slots allowed)
# ---------------------------------------------------------------------------

def test_unconstrained():
    print("\n=== Test 1: Unconstrained mode (no template) ===")
    gen = make_generator(with_profile=False)

    check("allowed_slots is empty",      gen.allowed_slots == {})
    check("lecture allowed at any slot", gen._is_slot_allowed('lecture',   3, 0, 0))
    check("practical allowed at any",    gen._is_slot_allowed('practical', 2, 4, 8))
    check("tutorial allowed at any",     gen._is_slot_allowed('tutorial',  5, 2, 3))


# ---------------------------------------------------------------------------
# Test 2: Template loaded — correct indexing
# ---------------------------------------------------------------------------

SAMPLE_CONTAINERS = [
    # Monday 08:00-10:00 -> Lecture for Year 3 (AEN-3)
    {"session_type": "lecture",   "day": "Monday",    "start_hour": 8,  "end_hour": 10, "group_label": "AEN-3"},
    # Tuesday 14:00-17:00 -> Practical for Year 2 (GEN-2)
    {"session_type": "practical", "day": "Tuesday",   "start_hour": 14, "end_hour": 17, "group_label": "GEN-2"},
    # Wednesday 10:00-12:00 -> Tutorial for Year 5 (AEN-5)
    {"session_type": "tutorial",  "day": "Wednesday", "start_hour": 10, "end_hour": 12, "group_label": "AEN-5"},
]


def test_constraint_loading():
    print("\n=== Test 2: Template loaded — index built correctly ===")
    gen = make_generator(SAMPLE_CONTAINERS)

    check("allowed_slots has lecture",   'lecture'   in gen.allowed_slots)
    check("allowed_slots has practical", 'practical' in gen.allowed_slots)
    check("allowed_slots has tutorial",  'tutorial'  in gen.allowed_slots)

    # Level extraction
    lev = gen._extract_level_from_label("AEN-3")
    check("AEN-3 extracts level 3",      lev == 3, f"got {lev}")
    lev2 = gen._extract_level_from_label("GEN-2")
    check("GEN-2 extracts level 2",      lev2 == 2, f"got {lev2}")
    lev_none = gen._extract_level_from_label("HOURS")
    check("HOURS extracts None",         lev_none is None, f"got {lev_none}")


# ---------------------------------------------------------------------------
# Test 3: is_slot_allowed — hard constraint enforcement
# ---------------------------------------------------------------------------

def test_slot_allowed():
    print("\n=== Test 3: _is_slot_allowed enforces constraints ===")
    gen = make_generator(SAMPLE_CONTAINERS)

    # Monday 08:00-09:00 (day_idx=0, t_idx=1) Lecture Year 3 -> ALLOWED
    check("Mon 08:00 lecture Y3 is ALLOWED",
          gen._is_slot_allowed('lecture', 3, 0, 1))

    # Monday 09:00-10:00 (day_idx=0, t_idx=2) Lecture Year 3 -> ALLOWED
    check("Mon 09:00 lecture Y3 is ALLOWED",
          gen._is_slot_allowed('lecture', 3, 0, 2))

    # Monday 10:00 (day_idx=0, t_idx=3) Lecture Year 3 -> NOT in template (container ends at 10)
    check("Mon 10:00 lecture Y3 is BLOCKED",
          not gen._is_slot_allowed('lecture', 3, 0, 3))

    # Tuesday 14:00-16:00 Practical Year 2 -> ALLOWED (t_idx = 14-7=7, 15-7=8, 16-7=9)
    check("Tue 14:00 practical Y2 is ALLOWED",
          gen._is_slot_allowed('practical', 2, 1, 7))
    check("Tue 15:00 practical Y2 is ALLOWED",
          gen._is_slot_allowed('practical', 2, 1, 8))
    check("Tue 16:00 practical Y2 is ALLOWED",
          gen._is_slot_allowed('practical', 2, 1, 9))

    # Tuesday 07:00 Practical Year 2 -> BLOCKED
    check("Tue 07:00 practical Y2 is BLOCKED",
          not gen._is_slot_allowed('practical', 2, 1, 0))

    # Wednesday 10:00 Tutorial Year 5 -> ALLOWED (t_idx=3)
    check("Wed 10:00 tutorial Y5 is ALLOWED",
          gen._is_slot_allowed('tutorial', 5, 2, 3))

    # Practical for Year 3 (not in template, only Year 2 practical is defined) -> unconstrained -> ALLOWED
    check("Practical Y3 (not in template) is ALLOWED",
          gen._is_slot_allowed('practical', 3, 0, 0))

    # Lecture for Year 3 on Friday (not in template) -> BLOCKED (Friday not in lecture Y3 set)
    check("Fri lecture Y3 blocked (not in template)",
          not gen._is_slot_allowed('lecture', 3, 4, 1))


# ---------------------------------------------------------------------------
# Test 4: Empty/malformed containers
# ---------------------------------------------------------------------------

def test_edge_cases():
    print("\n=== Test 4: Edge cases ===")

    # Empty containers -> unconstrained
    gen = make_generator([])
    check("Empty containers -> unconstrained",  gen._is_slot_allowed('lecture', 3, 0, 1))

    # Container with missing keys
    gen2 = make_generator([
        {"session_type": "lecture"},  # missing day and start_hour
        {"day": "Monday", "start_hour": 8},  # missing session_type
    ])
    check("Malformed containers -> unconstrained", gen2._is_slot_allowed('lecture', 3, 0, 1))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_unconstrained()
    test_constraint_loading()
    test_slot_allowed()
    test_edge_cases()

    total = results["passed"] + results["failed"]
    bar = "=" * 55
    print(f"\n{bar}")
    print(f"CHECKPOINT 3 RESULTS: {results['passed']}/{total} passed")
    if results["failed"] > 0:
        print(f"  {results['failed']} FAILURES - review output above")
        sys.exit(1)
    else:
        print("  ALL TESTS PASSED")
        sys.exit(0)
