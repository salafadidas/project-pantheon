-- Migration: 002_checkpoint_migration
-- Sprint 1 task: SPRINT1-CKPT-MIG
-- Description: Rename existing checkpoints from thread_id=user_id to thread_id=user_id:legacy
--              Implements MEMORY_MIGRATION_PLAN.md §8 backfill rule.
-- Idempotent: WHERE thread_id NOT LIKE '%:%' prevents double-suffixing on rerun.
-- Row-count logging: use psql \echo or application-level wrapper for counts.

-- ------------------------------------------------------------------ --
-- Step 1: rename checkpoints                                           --
-- ------------------------------------------------------------------ --
UPDATE checkpoints
SET thread_id = thread_id || ':legacy'
WHERE thread_id NOT LIKE '%:%';

-- ------------------------------------------------------------------ --
-- Step 2: rename checkpoint_writes (must stay consistent with         --
--         checkpoints — same thread_id key space)                     --
-- ------------------------------------------------------------------ --
UPDATE checkpoint_writes
SET thread_id = thread_id || ':legacy'
WHERE thread_id NOT LIKE '%:%';
