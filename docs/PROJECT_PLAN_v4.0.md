---
title: Project Pantheon — Stage 2 Sprint Plan
version: v4.0
date: 2026-05-03
status: DRAFT — awaiting kickoff approval
parent_plan: PROJECT_PLAN_v3.4.md
---

# Project Pantheon — Stage 2 Sprint Plan (Production-Grade Deployment)

> **Current file: `PROJECT_PLAN_v4.0.md`** — Sprint-level plan for Stage 2.
> Master plan continues to live in `PROJECT_PLAN_v3.4.md` (or its successor).

---

## 1. Goals & Non-Goals

### Goals
1. Run Pantheon as a **multi-tenant cloud service** with per-tenant rate limits and isolation.
2. Add **authentication** (API key for server-to-server, Google OAuth for browser users).
3. Add **observability** — Prometheus metrics, Grafana dashboards, OpenTelemetry traces.
4. **Performance test** — establish SLAs (p50 / p95 latency per phase, max concurrent sessions).
5. **Disaster recovery** — automated DB backups, runbook, restore drill.
6. **User-facing UI improvements** — accounts, session history, share-by-link.

### Non-Goals (deferred to Stage 3 or later)
- Eigent execution layer (Stage 3)
- Mobile-native app
- Offline mode
- Custom model fine-tuning
- Marketplace / plugin system

---

## 2. Decisions Locked (from v3.4 §7)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cloud target | **GCP Cloud Run + Memorystore + Cloud SQL** | LangGraph + Redis pub/sub friendly; Gemini in-network saves egress; pay-per-request matches bursty usage |
| Auth strategy | **API Key (server) + Google OAuth (browser)** | Reuses Google account already used for NotebookLM; no need to manage passwords |
| Frontend | **Keep Next.js 14**, add NextAuth | Avoid rewrite; mature WebSocket support |
| Stage 3 (Eigent) | **Deferred** to post-Stage 2 decision gate | Avoid scope creep |

---

## 3. Reference Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       USERS                                     │
│  Browser (NextAuth)   │  Telegram   │  CLI/3rd-party (API key) │
└──────┬───────────────┬───────────────┬───────────────────────────┘
       │HTTPS          │HTTPS          │HTTPS
       ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Cloud Load Balancer + Cloud Armor (rate limit, WAF)            │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Cloud Run service: pantheon-api (FastAPI)                      │
│  - Auth middleware (API key OR session cookie)                  │
│  - Tenant isolation (per-tenant Redis namespace)                │
│  - OpenTelemetry instrumentation                                │
└──────┬──────────────────────────────────────────────┬───────────┘
       │                                              │
       ▼                                              ▼
┌──────────────────┐                ┌──────────────────────────────┐
│ Memorystore      │                │ Cloud SQL (Postgres + pgvec) │
│ (Redis pub/sub)  │                │ - users, sessions, costs,    │
│ session events   │                │   reports, audit_log         │
└──────────────────┘                └──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Telegram bot worker (Cloud Run job, single replica)            │
└─────────────────────────────────────────────────────────────────┘

Observability sidecar:
  ┌─────────┐   ┌─────────┐   ┌─────────┐
  │Cloud Ops│ ← │Prometheus│ ← │OpenTel  │
  │ Logging │   │ scraper  │   │ exporter│
  └─────────┘   └─────────┘   └─────────┘
                     │
                     ▼
                ┌─────────┐
                │ Grafana │  (Cloud Monitoring or self-hosted)
                └─────────┘
```

---

## 4. Sprint Breakdown (6 weeks, 1-week sprints)

### Sprint 1 — Auth & Multi-tenant Isolation (Week 1)

| Task | Files | Owner Model |
|------|-------|------------|
| Add `users` + `api_keys` + `tenants` tables | new Alembic migration in `db/migrations/` | Sonnet 4.6 |
| Auth middleware (API key OR session cookie) | `api/middleware/auth.py` | Sonnet 4.6 |
| Per-tenant Redis namespace (`tenant:{id}:session:{sid}`) | `api/v1/sessions.py`, `core/redis_utils.py` | Sonnet 4.6 |
| NextAuth Google provider integration | `frontend/pages/api/auth/[...nextauth].ts` | Sonnet 4.6 |
| Tests | `tests/test_auth.py`, `tests/test_tenant_isolation.py` | Haiku 4.5 |

**Exit:** A second Google account cannot see the first account's sessions; API key requests are tenant-scoped.

---

### Sprint 2 — Observability (Week 2)

| Task | Files | Owner Model |
|------|-------|------------|
| OpenTelemetry instrumentation (FastAPI + LangGraph spans) | `utils/telemetry.py`, `main.py`, all node files | Sonnet 4.6 |
| Prometheus metrics endpoint `/metrics` | `api/v1/metrics.py` | Haiku 4.5 |
| Per-phase histograms (latency, tokens, cost) | wired into `graph/nodes/*.py` | Haiku 4.5 |
| Grafana dashboard JSON (5 panels: latency, errors, cost, concurrency, model health) | `infra/grafana/pantheon.json` | Sonnet 4.6 |
| Structured error budget alerts (>5% 5xx → page) | `infra/alerts/error_budget.yaml` | Sonnet 4.6 |

**Exit:** Grafana shows per-phase p50/p95 in real time; an injected 500 fires the alert within 2 min.

---

### Sprint 3 — GCP Deployment (Week 3)

| Task | Files | Owner Model |
|------|-------|------------|
| `Dockerfile.prod` (multi-stage, distroless) | `Dockerfile.prod` | Sonnet 4.6 |
| Terraform: Cloud Run + Memorystore + Cloud SQL | `infra/terraform/*.tf` | Sonnet 4.6 |
| Cloud Build CI → push to Artifact Registry → deploy | `cloudbuild.yaml` | Sonnet 4.6 |
| Secrets in Secret Manager (API keys for LLMs, OAuth client) | `infra/secrets.tf` | Haiku 4.5 |
| DNS + TLS (managed cert) | `infra/dns.tf` | Haiku 4.5 |
| Smoke test against deployed URL | `scripts/smoke_prod.sh` | Haiku 4.5 |

**Exit:** `https://pantheon.example.com/health` returns ok; full session runs end-to-end in prod.

---

### Sprint 4 — Rate Limiting & SLA (Week 4)

| Task | Files | Owner Model |
|------|-------|------------|
| Tenant-level rate limiter (sliding-window, Redis-backed) | `api/middleware/rate_limit.py` | Sonnet 4.6 |
| Per-tenant model spending cap (daily $ ceiling) | `llm/spend_guard.py` | Sonnet 4.6 |
| 429 responses with `Retry-After` header + UI banner | `api/middleware/rate_limit.py`, `frontend/components/RateLimitBanner.tsx` | Haiku 4.5 |
| SLA documentation (p50 < 2 min/phase, 99% uptime) | `docs/SLA.md` | Haiku 4.5 |
| Locust load test scenario (10 concurrent sessions) | `scripts/loadtest.py` | Sonnet 4.6 |

**Exit:** Load test hits stated SLA; rate limiter blocks runaway tenant within one window.

---

### Sprint 5 — Disaster Recovery (Week 5)

| Task | Files | Owner Model |
|------|-------|------------|
| Automated daily Cloud SQL backups + 7-day retention | Terraform tweak | Haiku 4.5 |
| Restore drill script (clone DB to staging, validate) | `scripts/dr_restore.sh` | Sonnet 4.6 |
| Runbook: rollback to previous Cloud Run revision | `docs/RUNBOOK.md` | Sonnet 4.6 |
| Chaos test: kill API pod mid-session → orphan recovery proves itself in prod | `scripts/chaos_kill.sh` | Sonnet 4.6 |
| Backup encryption with CMEK (Cloud KMS) | Terraform tweak | Haiku 4.5 |

**Exit:** Documented restore completes < 30 min; orphan recovery survives prod kill.

---

### Sprint 6 — UI Polish & Beta Launch (Week 6)

| Task | Files | Owner Model |
|------|-------|------------|
| User account page (history, API key mgmt, spend) | `frontend/pages/account.tsx` | Sonnet 4.6 |
| Session history list (paginated, filterable) | `frontend/pages/sessions.tsx`, `api/v1/sessions.py` GET list endpoint | Sonnet 4.6 |
| Share-by-link (read-only public report URL with expiry) | `api/v1/sessions.py` share endpoint, `frontend/pages/r/[token].tsx` | Sonnet 4.6 |
| Onboarding flow (first-login walkthrough) | `frontend/components/Onboarding.tsx` | Haiku 4.5 |
| Beta invite system (email allowlist) | `db/migrations/`, `api/middleware/auth.py` | Haiku 4.5 |
| Public landing page + pricing | `frontend/pages/index.tsx` (refresh) | Haiku 4.5 |

**Exit:** 10 closed-beta users complete a session and see history; tag `v1.0.0-beta`.

---

## 5. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| LLM cost overrun (single tenant runs 1000 sessions/day) | Medium | High | Spend cap (Sprint 4) + Stripe-style usage alerts |
| GCP region outage during a session | Low | Medium | Multi-zone Cloud Run; orphan recovery already handles partial failure |
| Memorystore eviction during long debate | Low | Medium | Configure Redis with `maxmemory-policy noeviction` for session keys |
| OAuth refresh token rot for NotebookLM upload | Medium | Low | Service account + scheduled refresh script |
| Quota exhaustion across all 3 providers | Low | Critical | Already mitigated by `quota_fallback.py` + NVIDIA NIM free tier |
| 1M-context request blowing up cost | Medium | Medium | Pre-call token estimator + warn-then-block above tenant cap |

---

## 6. Open Questions for Stage 2

| Question | Owner | Decide By |
|----------|-------|-----------|
| Free tier vs. paid-only at beta launch | Vernon | Sprint 6 start |
| Domain name for production (`pantheon.app`? `pantheon.ai`?) | Vernon | Sprint 3 start |
| Pricing model: per-session, per-token, monthly subscription? | Vernon | Sprint 6 start |
| Self-host Grafana vs. use GCP Cloud Monitoring | Vernon | Sprint 2 start |
| Telegram bot in prod: shared tenant or per-user webhook? | Vernon | Sprint 1 end |

---

## 7. Definition of Done (Stage 2)

- [ ] All 6 sprints exit-criteria met
- [ ] `v1.0.0-beta` tag pushed
- [ ] 10 closed-beta users active
- [ ] SLA dashboard green for 7 consecutive days
- [ ] DR restore drill documented and re-tested
- [ ] Stage 3 (Eigent) decision gate held — proceed / skip / defer

---

## 8. Version History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| v4.0 | 2026-05-03 | Sonnet 4.6 | Initial Stage 2 sprint plan — 6 weeks, GCP Cloud Run target, OAuth+API key auth, NextAuth frontend |
