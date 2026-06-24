---
title: Project Pantheon — Status Summary
date: 2026-06-24
sprint: Sprint 1 — engineering complete, merge pending
status: Sprint 1 NOT closed — PR stack (#29 #30 #31 #32 #33) awaiting merge
---

# Project Pantheon — Status Summary (2026-06-24)

## Sprint 1 状態: Engineering Complete / Merge Pending

> **Sprint 1 is NOT closed.**
> All Sprint 1 engineering is done and PRs are open.
> Sprint 1 closes when the full PR stack lands on `main`.

---

## PR 合併順序（建議）

| 順序 | PR | Task | 說明 |
|------|-----|------|------|
| 1 | #30 | #21 session layer | `core/session.py` — sole producer of `thread_id` |
| 2 | #31 | S1-TID-1 T2 thread_id | T2 `thread_id = f"{user_id}:{session_id}"` + Redis persistence |
| 3 | #32 | S1-AUTH-3 Redis NS | `pantheon:` prefix 統一套用，15/15 tests |
| 4 | #33 | S1-AUTH-2 API-key auth | `APIKeyMiddleware` SHA-256，16/16 tests |
| 5 | #29 | S1-NS-1 + CKPT-MIG | namespace promotion + checkpoint migration（CI red 非新引入問題） |

> **#29 merge 前注意**：CI 全紅原因是 `llm/provider.py` 的 `ChatLiteLLM` import 問題（`langchain_community` sunset）。這個問題在 `main` 分支也存在，不是 PR #29 新引入的。`main` branch 先解 CI 或直接 merge（branch protection 未開）由你決定。

---

## 今日工作紀錄（2026-06-24）

### 完成項目

| Task | Branch | PR | Tests |
|------|--------|----|-------|
| Issue #21 — collapse session layer | `feat/issue-21-session-layer` | #30 | — |
| S1-TID-1 — T2 thread_id + Redis persistence | `feat/s1-tid-1-thread-id-t2` | #31 | 11/11 |
| S1-AUTH-3 — Redis `pantheon:` namespace | `feat/s1-auth-3-redis-tenant-ns` | #32 | 15/15 |
| S1-AUTH-2 — API-key middleware | `feat/s1-auth-2-api-key-middleware` | #33 | 16/16 |
| S1-MEM-2 — issue 建立 | — | issue #34 | — |

### 確認事項

- PR #29 (`feat/s1-ns-1-namespace-promotion`) 不碰 `core/session.py` 或 `telegram_bot.py`，與 #30/#31 無衝突，merge 順序可放最後
- Issue #21 保持 open，等 PR #30 + #31 實際 merge 後再關

---

## 完整 Sprint 1 任務狀態

| Task ID | 說明 | 狀態 |
|---------|------|------|
| S1-AUTH-1 | tenants/users/api_keys schema | ✅ merged (fc157e1) |
| S1-AUTH-2 | API-key middleware | 🟡 PR #33 open |
| S1-AUTH-3 | Redis per-tenant namespace | 🟡 PR #32 open |
| S1-BOOT-1 | 移除 default_user hardcoding | ✅ merged |
| S1-CLEAN-1 | 移除 openmemory MCP | ✅ merged |
| S1-DEL-1 | clear_user_data 3 bugs 修復 | ✅ merged |
| S1-MEM-1 | MEMORY_SYSTEM_PROMPT 修復 | ✅ merged (PR #24) |
| S1-NS-MIG | MEMORY_MIGRATION_PLAN | ✅ merged |
| S1-NS-1 + CKPT-MIG | namespace promotion + checkpoint migration | 🟡 PR #29 open |
| S1-TID-1 + #21 | T2 thread_id + session layer | 🟡 PR #30 #31 open |
| S1-UI-1 (NextAuth) | NextAuth Google OAuth | ⏸ deferred → Sprint 6 |
| S1-MEM-2 | embedding provider resolution | 📋 issue #34 → Sprint 2 |

---

## 下一步（你的動作）

1. 依序 merge PR #30 → #31 → #32 → #33 → #29
2. PR #30 + #31 merge 後關閉 issue #21
3. Sprint 1 正式關閉（建 Sprint 1 closure commit 或 issue comment）
4. 開始 Sprint 2 規劃（Aletheia QMD RAG、Raphael Phase 1、S1-MEM-2 embedding）

---

## Cross-references

- Sprint 0 closure: issue #23
- Sprint 1 capacity: issue #22
- S1-MEM-2 tracking: issue #34
- CI 根本問題: `llm/provider.py:13` — `ChatLiteLLM` removed from `langchain_community` (see [upstream sunset notice](https://github.com/langchain-ai/langchain-community/issues/674))
- Stage 2 plan: `docs/PROJECT_PLAN_v4.4.md`
