-- Migration: 003_namespace_migration
-- Sprint 1 task: S1-NS-1 (backfill phase)
-- Description: Copy existing store rows from namespace (user_id,) to (tenant_id, user_id).
--              Uses 1-user-1-tenant synthesized mapping (MEMORY_MIGRATION_PLAN.md §2).
--              Old rows are NOT deleted — they remain for dual-read fallback window.
-- Idempotent: INSERT ... WHERE NOT EXISTS guard prevents duplicate rows on rerun.
-- Run AFTER 002_checkpoint_migration.sql.

-- ------------------------------------------------------------------ --
-- Backfill store rows                                                  --
-- Each existing (user_id,) prefix row gets a copy under               --
-- (user_id, user_id) — i.e. tenant_id synthesized = user_id.         --
-- When real tenant_id lookup is in place (post S1-AUTH-2), re-run    --
-- this migration with the actual tenant mapping.                      --
-- ------------------------------------------------------------------ --
INSERT INTO store (prefix, key, value, created_at, updated_at)
SELECT
    user_id || '/' || user_id  AS prefix,   -- new: (tenant_id=user_id, user_id)
    key,
    value,
    created_at,
    updated_at
FROM (
    SELECT
        prefix                         AS user_id,
        key,
        value,
        created_at,
        updated_at
    FROM store
    WHERE prefix NOT LIKE '%/%'         -- old-shape rows only: single user_id prefix
) old_rows
WHERE NOT EXISTS (
    SELECT 1 FROM store s2
    WHERE s2.prefix = old_rows.user_id || '/' || old_rows.user_id
      AND s2.key    = old_rows.key
);
