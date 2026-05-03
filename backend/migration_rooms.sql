-- ============================================================
-- TABLESYS — Room Equipment Migration
-- Safe, idempotent. Run via:
--   docker exec -i tablesys-db psql -U tablesys -d tablesys_db < migration_rooms.sql
-- ============================================================

BEGIN;

-- ── 1. Add has_whiteboard ──────────────────────────────────────────────────
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS
    has_whiteboard BOOLEAN NOT NULL DEFAULT TRUE;

-- ── 2. Add has_chalkboard ──────────────────────────────────────────────────
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS
    has_chalkboard BOOLEAN NOT NULL DEFAULT FALSE;

-- ── 3. Backfill has_projector from equipment JSON (if still present) ───────
-- Marks rooms as has_projector=TRUE if old equipment list mentioned 'projector'
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rooms' AND column_name = 'equipment'
    ) THEN
        UPDATE rooms
        SET has_projector = TRUE
        WHERE equipment::text ILIKE '%projector%'
          AND has_projector = FALSE;
    END IF;
END $$;

-- ── 4. Drop has_computers ──────────────────────────────────────────────────
ALTER TABLE rooms DROP COLUMN IF EXISTS has_computers;

-- ── 5. Drop equipment (JSON list) ─────────────────────────────────────────
ALTER TABLE rooms DROP COLUMN IF EXISTS equipment;

-- ── 6. Drop furniture_type ────────────────────────────────────────────────
ALTER TABLE rooms DROP COLUMN IF EXISTS furniture_type;

-- ── 7. Drop priority (legacy string, superseded by priority_level) ─────────
ALTER TABLE rooms DROP COLUMN IF EXISTS priority;

-- ── 8. Add index on name for faster lookups ───────────────────────────────
CREATE INDEX IF NOT EXISTS ix_rooms_name ON rooms (name);

COMMIT;

-- Verify final schema
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'rooms'
ORDER BY ordinal_position;
