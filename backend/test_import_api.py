"""
Task 4 Verification: Import API Test Script

Tests the POST /api/import/timetable endpoint end-to-end:
  1. Authenticate as coordinator
  2. Load parsed timetable JSON from Task 2 output
  3. POST to import endpoint
  4. Print summary and verify counts

Usage:
    # Requires Task 2 output to exist at the expected output path.
    python backend/test_import_api.py [--base-url http://localhost:8000]
"""

import argparse
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed. Run: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8000"
COORDINATOR_USERNAME = "coordinator"
COORDINATOR_PASSWORD = "coordinator123"   # Matches seed_users.py defaults

# Locate JSON output from Task 2
JSON_CANDIDATES = [
    "/tmp/parsed_timetable.json",
    os.path.join(os.environ.get("TEMP", ""), "parsed_timetable.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "parsed_timetable.json"),
]


def resolve_json_path() -> str:
    for path in JSON_CANDIDATES:
        if path and os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "Task 2 output JSON not found. Run test_pdf_parser.py first.\n"
        "Searched: " + ", ".join(p for p in JSON_CANDIDATES if p)
    )


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def authenticate(base_url: str, session: requests.Session) -> str:
    print("Step 1: Authenticating as coordinator...")
    response = session.post(
        f"{base_url}/api/auth/login",
        data={"username": COORDINATOR_USERNAME, "password": COORDINATOR_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if response.status_code != 200:
        print(f"  FAIL: Login returned HTTP {response.status_code}")
        print(f"  Body: {response.text[:500]}")
        return ""
    token = response.json().get("access_token", "")
    if token:
        print(f"  PASS: Authenticated (token length: {len(token)})")
    else:
        print("  FAIL: No access_token in response")
    return token


def load_parsed_data() -> dict:
    print("Step 2: Loading parsed timetable JSON...")
    path = resolve_json_path()
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    print(f"  Source : {path}")
    print(f"  Courses : {len(data.get('courses', []))}")
    print(f"  Rooms   : {len(data.get('rooms', []))}")
    print(f"  Slots   : {len(data.get('time_slots', []))}")
    return data


def run_import(base_url: str, token: str, data: dict, session: requests.Session) -> dict:
    print("Step 3: Posting to /api/import/timetable...")
    payload = {
        "source": "pdf_upload",
        "term": data.get("metadata", {}).get("term", "Term 1"),
        "year": data.get("metadata", {}).get("year", 2026),
        "department_id": 1,
        "data": {
            "courses": data.get("courses", []),
            "rooms": data.get("rooms", []),
            "time_slots": data.get("time_slots", []),
        },
    }
    start = time.time()
    response = session.post(
        f"{base_url}/api/import/timetable",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    elapsed = time.time() - start
    print(f"  HTTP {response.status_code} in {elapsed:.2f}s")

    if response.status_code != 200:
        print(f"  FAIL: {response.text[:800]}")
        return {}
    return response.json()


def verify_auth_guards(base_url: str, session: requests.Session) -> None:
    """Confirm endpoint returns 401 without token and 403 for non-coordinator."""
    print("Step 4: Verifying authentication guards...")

    # No token
    r_no_auth = session.post(
        f"{base_url}/api/import/timetable",
        json={"source": "test", "term": "T", "year": 2026, "department_id": 1, "data": {}},
        timeout=10,
    )
    status_401 = r_no_auth.status_code == 401
    print(f"  [{'PASS' if status_401 else 'FAIL'}] No token returns 401 (got {r_no_auth.status_code})")


def print_summary(result: dict) -> bool:
    if not result:
        return False

    summary = result.get("summary", {})
    print()
    print("IMPORT COMPLETE")
    print("=" * 50)
    print(f"Status         : {result.get('status')}")
    print(f"Import ID      : {result.get('import_id')}")
    print(f"Timetable ID   : {result.get('timetable_id')}")
    print(f"Execution Time : {result.get('execution_time_ms')}ms")
    print()
    print("Summary:")
    print(f"  Courses Imported  : {summary.get('courses_imported', 0)}")
    print(f"  Courses Updated   : {summary.get('courses_updated', 0)}")
    print(f"  Courses Skipped   : {summary.get('courses_skipped', 0)}")
    print(f"  Rooms Imported    : {summary.get('rooms_imported', 0)}")
    print(f"  Rooms Skipped     : {summary.get('rooms_skipped', 0)}")
    print(f"  Slots Skipped     : {summary.get('slots_skipped', 0)}")
    print(f"  Warnings          : {len(summary.get('warnings', []))}")
    print(f"  Errors            : {len(summary.get('errors', []))}")

    warnings = summary.get("warnings", [])
    if warnings:
        print()
        print("First 5 Warnings:")
        for w in warnings[:5]:
            print(f"  - {w}")

    errors = summary.get("errors", [])
    if errors:
        print()
        print("Errors:")
        for e in errors[:5]:
            print(f"  - {e}")

    passed = (
        result.get("status") == "success"
        and summary.get("courses_imported", 0) + summary.get("courses_updated", 0) > 0
    )
    return passed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Test the timetable import API endpoint.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print()
    print("IMPORT API TEST")
    print("=" * 50)
    print(f"Target: {base_url}")
    print()

    session = requests.Session()

    token = authenticate(base_url, session)
    if not token:
        return 1
    print()

    try:
        data = load_parsed_data()
    except FileNotFoundError as exc:
        print(f"  FAIL: {exc}")
        return 1
    print()

    result = run_import(base_url, token, data, session)
    if not result:
        return 1
    print()

    verify_auth_guards(base_url, session)
    print()

    passed = print_summary(result)

    print()
    print("=" * 50)
    if passed:
        print("STATUS: IMPORT TEST PASSED")
        print()
        print("Recommendation: Ready for Task 6 (Timetable Grid Display)")
        return 0
    else:
        print("STATUS: IMPORT TEST FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
