"""
Task 2 Verification: PDF Timetable Parser Test Script

Runs the TimetableParser against the UNZA timetable PDF and reports extraction
statistics. Saves output to /tmp/parsed_timetable.json (or a local equivalent).

Usage:
    # Local (Windows):
    python backend/test_pdf_parser.py

    # Docker:
    docker exec tablesys-backend python backend/test_pdf_parser.py
"""

import json
import os
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Resolve PDF path (supports both Docker mount path and local Windows path)
# ---------------------------------------------------------------------------

PDF_CANDIDATES = [
    # Docker mount path (as specified in task brief)
    "/mnt/user-data/uploads/1ST_HALF_UG_CLASS_TIMETABLE_2026_FIRST_DRAFT__1_.pdf",
    # Local Windows path – file found at project root
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "1ST HALF UG CLASS TIMETABLE 2026_FIRST DRAFT (1).pdf",
    ),
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "1ST HALF UG CLASS TIMETABLE 2026_FIRST DRAFT.pdf",
    ),
]

OUTPUT_PATH = "/tmp/parsed_timetable.json" if os.name != "nt" else os.path.join(
    os.environ.get("TEMP", os.path.dirname(os.path.abspath(__file__))),
    "parsed_timetable.json",
)


def resolve_pdf_path() -> str:
    for path in PDF_CANDIDATES:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "Cannot locate timetable PDF. Searched paths:\n"
        + "\n".join(f"  - {p}" for p in PDF_CANDIDATES)
    )


def validate_result(result: dict) -> bool:
    """Check extraction meets minimum thresholds. Returns True if OK."""
    courses = result.get("courses", [])
    slots = result.get("time_slots", [])
    rooms = result.get("rooms", [])

    passed = True

    def check(condition: bool, message: str) -> None:
        nonlocal passed
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {message}")
        if not condition:
            passed = False

    print()
    print("Validation Checks:")
    check(len(courses) >= 50, f"Courses >= 50 (got {len(courses)})")
    check(len(slots) >= 200, f"Time slots >= 200 (got {len(slots)})")
    check(len(rooms) >= 1, f"At least 1 room identified (got {len(rooms)})")
    check(
        json.dumps(result) is not None,
        "Output is valid JSON"
    )

    # Spot-check first slot structure
    if slots:
        slot = slots[0]
        required_keys = {"course_code", "day", "start_time", "end_time", "room", "groups"}
        missing = required_keys - set(slot.keys())
        check(not missing, f"Slot schema complete (missing: {missing})")

    return passed


def main() -> int:
    print()
    print("TIMETABLE PDF PARSER TEST")
    print("=" * 50)
    print()

    # Locate PDF
    try:
        pdf_path = resolve_pdf_path()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Source : {pdf_path}")
    print(f"Output : {OUTPUT_PATH}")
    print()

    # Import parser (relative import works when run from backend/ dir)
    try:
        from app.utils.pdf_timetable_parser import TimetableParser
    except ImportError:
        # Fallback: add parent dir to sys.path when running standalone
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app.utils.pdf_timetable_parser import TimetableParser

    # Parse
    print("Parsing PDF...")
    start = time.time()
    try:
        parser = TimetableParser(pdf_path)
        result = parser.parse()
    except Exception as exc:
        print(f"\nEXCEPTION during parsing: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    elapsed = time.time() - start

    # Report
    print()
    print("PARSING COMPLETE")
    print("=" * 50)
    print(f"Execution Time  : {elapsed:.2f}s")
    print(f"Courses         : {len(result['courses'])}")
    print(f"Time Slots      : {len(result['time_slots'])}")
    print(f"Rooms           : {len(result['rooms'])}")
    print()

    # Save output
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_PATH)), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(f"Output saved to : {OUTPUT_PATH}")

    # Sample
    if result["time_slots"]:
        print()
        print("Sample Time Slot (first entry):")
        print(json.dumps(result["time_slots"][0], indent=2))

    if result["courses"]:
        print()
        print("Sample Courses (first 5):")
        for c in result["courses"][:5]:
            print(f"  {c['code']} | Year {c['year']} | {c['program']}")

    # Validate
    passed = validate_result(result)

    print()
    print("=" * 50)
    if passed:
        print("STATUS: ALL CHECKS PASSED")
        print()
        print("Recommendation: Ready for Task 4 (Database Import API)")
        return 0
    else:
        print("STATUS: ONE OR MORE CHECKS FAILED")
        print()
        print("Recommendation: Review parser logic before proceeding to Task 4")
        return 1


if __name__ == "__main__":
    sys.exit(main())
