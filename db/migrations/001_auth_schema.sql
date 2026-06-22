-- Migration: 001_auth_schema
-- Sprint 1 task: S1-AUTH-1
-- Description: Create tenant ownership tables (minimal viable schema for S1-NS-MIG)
-- Idempotent: all statements use CREATE TABLE IF NOT EXISTS / CREATE UNIQUE INDEX IF NOT EXISTS
-- Do NOT add: created_at, updated_at, is_active, scopes, last_used_at — deferred to Sprint 2+

-- ------------------------------------------------------------------ --
-- tenants                                                              --
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS tenants (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL
);

-- ------------------------------------------------------------------ --
-- users                                                                --
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL REFERENCES tenants(id),
    telegram_user_id TEXT NOT NULL
);

-- unique: one Telegram user maps to exactly one tenant in this table
-- (migration mapping key: telegram_user_id → tenant_id)
CREATE UNIQUE INDEX IF NOT EXISTS users_telegram_user_id_uidx
    ON users (telegram_user_id);

-- ------------------------------------------------------------------ --
-- api_keys                                                             --
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS api_keys (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  UUID NOT NULL REFERENCES tenants(id),
    key_hash   TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS api_keys_key_hash_uidx
    ON api_keys (key_hash);
