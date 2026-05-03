#!/usr/bin/env python
"""
migrate_rooms.py
================
Safe, idempotent migration script for the Room model equipment overhaul.

Changes applied to the `rooms` table
-------------------------------------
ADD    has_whiteboard   BOOLEAN  NOT NULL DEFAULT TRUE
ADD    has_chalkboard   BOOLEAN  NOT NULL DEFAULT FALSE
DROP   has_computers
DROP   equipment        (JSON column — formerly a list of strings)
DROP   furniture_type
DROP   priority         (legacy string field superseded by priority_level)

Existing data is preserved:
  - has_projector  already exists and is kept as-is
  - All other columns (name, building, capacity, room_type, etc.) are untouched

Safety features
---------------
* Wrapped in a single transaction — any error triggers a full ROLLBACK.
* Each ADD/DROP is guarded by an IF EXISTS / column-exists check → idempotent.
* Run with  --dry-run  to see what SQL would execute without touching the DB.
* Prints a clear before/after column summary.

Usage
-----
  # Preview only (no changes):
  python migrate_rooms.py --dry-run

  # Apply for real:
  python migrate_rooms.py
"""

import sys
import os
import argparse

# ── Make app importable from backend root ────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from app.config import settings  # loads DATABASE_URL from .env

import psycopg2
from psycopg2.extras import RealDictCursor


# ────────────────────────────────────────────────────────────────────────────
# Migration steps — each is (description, sql)
# The SQL uses DO $$ BEGIN ... EXCEPTION WHEN duplicate_column THEN ... END $$
# so each step is safe to run again if the column already exists / is gone.
# ────────────────────────────────────────────────────────────────────────────

MIGRATION_STEPS = [
    # ── ADD new equipment booleans ─────────────────────────────────────────
    (
        "ADD has_whiteboard (default TRUE)",
        """
        DO $$ BEGIN
            ALTER TABLE rooms ADD COLUMN has_whiteboard BOOLEAN NOT NULL DEFAULT TRUE;
        EXCEPTION WHEN duplicate_column THEN
            RAISE NOTICE 'Column has_whiteboard already exists, skipping.';
        END $$;
        """,
    ),
    (
        "ADD has_chalkboard (default FALSE)",
        """
        DO $$ BEGIN
            ALTER TABLE rooms ADD COLUMN has_chalkboard BOOLEAN NOT NULL DEFAULT FALSE;
        EXCEPTION WHEN duplicate_column THEN
            RAISE NOTICE 'Column has_chalkboard already exists, skipping.';
        END $$;
        """,
    ),
    # ── Migrate projector data from equipment JSON if present ──────────────
    # If the old `equipment` column still exists, scan it to set has_projector
    # for any room that listed "projector" in its equipment array.
    (
        "Backfill has_projector from equipment JSON (if equipment column exists)",
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'rooms' AND column_name = 'equipment'
            ) THEN
                UPDATE rooms
                SET has_projector = TRUE
                WHERE equipment::text ILIKE '%projector%'
                  AND has_projector = FALSE;
                RAISE NOTICE 'Backfilled has_projector from equipment JSON.';
            ELSE
                RAISE NOTICE 'equipment column not present, skipping backfill.';
            END IF;
        END $$;
        """,
    ),
    # ── DROP obsolete columns ──────────────────────────────────────────────
    (
        "DROP has_computers",
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'rooms' AND column_name = 'has_computers'
            ) THEN
                ALTER TABLE rooms DROP COLUMN has_computers;
                RAISE NOTICE 'Dropped has_computers.';
            ELSE
                RAISE NOTICE 'has_computers already removed, skipping.';
            END IF;
        END $$;
        """,
    ),
    (
        "DROP equipment (JSON list)",
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'rooms' AND column_name = 'equipment'
            ) THEN
                ALTER TABLE rooms DROP COLUMN equipment;
                RAISE NOTICE 'Dropped equipment.';
            ELSE
                RAISE NOTICE 'equipment already removed, skipping.';
            END IF;
        END $$;
        """,
    ),
    (
        "DROP furniture_type",
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'rooms' AND column_name = 'furniture_type'
            ) THEN
                ALTER TABLE rooms DROP COLUMN furniture_type;
                RAISE NOTICE 'Dropped furniture_type.';
            ELSE
                RAISE NOTICE 'furniture_type already removed, skipping.';
            END IF;
        END $$;
        """,
    ),
    (
        "DROP priority (legacy string field)",
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'rooms' AND column_name = 'priority'
            ) THEN
                ALTER TABLE rooms DROP COLUMN priority;
                RAISE NOTICE 'Dropped legacy priority string column.';
            ELSE
                RAISE NOTICE 'priority already removed, skipping.';
            END IF;
        END $$;
        """,
    ),
]


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def get_room_columns(cursor) -> list[str]:
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'rooms'
        ORDER BY ordinal_position;
    """)
    return [row["column_name"] for row in cursor.fetchall()]


def get_room_count(cursor) -> int:
    cursor.execute("SELECT COUNT(*) AS n FROM rooms;")
    return cursor.fetchone()["n"]


def run_migration(dry_run: bool = False):
    print()
    print("=" * 60)
    print("  TABLESYS – Room Equipment Migration")
    print("  Mode:", "DRY-RUN (no changes will be made)" if dry_run else "LIVE")
    print("=" * 60)
    print()

    # Parse DATABASE_URL for psycopg2 (strip +asyncpg or +psycopg2 suffix if present)
    db_url = settings.DATABASE_URL
    if "+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")
    elif "+psycopg2" in db_url:
        db_url = db_url.replace("postgresql+psycopg2", "postgresql")

    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    conn.autocommit = False  # explicit transaction control

    try:
        with conn.cursor() as cur:
            # ── Pre-migration snapshot ───────────────────────────────────
            before_cols = get_room_columns(cur)
            room_count  = get_room_count(cur)

            print(f"  Rooms in database : {room_count}")
            print(f"  Columns BEFORE    : {', '.join(before_cols)}")
            print()

            if dry_run:
                print("  Steps that WOULD run:")
                for i, (desc, sql) in enumerate(MIGRATION_STEPS, 1):
                    print(f"    {i}. {desc}")
                print()
                print("  [OK] Dry-run complete. No changes made.")
                print()
                conn.rollback()
                return

            # ── Execute each step inside one transaction ─────────────────
            for i, (desc, sql) in enumerate(MIGRATION_STEPS, 1):
                print(f"  [{i}/{len(MIGRATION_STEPS)}] {desc} ...", end=" ", flush=True)
                cur.execute(sql)
                print("done")

            # ── Post-migration snapshot ──────────────────────────────────
            after_cols = get_room_columns(cur)
            added      = sorted(set(after_cols) - set(before_cols))
            removed    = sorted(set(before_cols) - set(after_cols))

            print()
            print("  ── Summary ──────────────────────────────────────────")
            if added:
                print(f"  [+] Added   : {', '.join(added)}")
            if removed:
                print(f"  [-] Removed : {', '.join(removed)}")
            if not added and not removed:
                print("  [=] No column changes (migration already applied).")

            print(f"  Rooms preserved   : {get_room_count(cur)} / {room_count}")
            print()

            conn.commit()
            print("  [OK] Migration committed successfully. Database is safe.")
            print()

    except Exception as exc:
        conn.rollback()
        print()
        print("  [FAIL] MIGRATION FAILED -- rolled back. No data was changed.")
        print(f"         Error: {exc}")
        print()
        raise
    finally:
        conn.close()


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Room equipment schema migration")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would happen without making any changes",
    )
    args = parser.parse_args()
    run_migration(dry_run=args.dry_run)
