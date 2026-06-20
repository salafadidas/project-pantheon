---
title: Project Pantheon — Status Summary
date: 2026-06-20
sprint: Sprint 0 → Sprint 1 transition
branch: claude/remote-control-Q2YAQ
---

# Project Pantheon — Status Summary (2026-06-20)

## 整體進度

| 階段 | 狀態 | 說明 |
|------|------|------|
| Sprint 0 — Memory Layer Assessment | ✅ 完成 | 庫存文件完成、thread_id 決策完成 |
| S1-MEM-1 — Memory tool prompt fix | ✅ 完成 | 驗證寫入 store table |
| S1-MEM-2 — Retrieval & embedding | 🔜 待開始 | Google embedding 問題待解決 |
| Sprint 1 — Auth / Multi-tenant / Hardening | 🔜 尚未開始 | 等 S1-MEM-1 merge 後展開 |

---

## Sprint 0 完成事項

### Step 1 — Current-state inventory
- 文件：`docs/MEMORY_CURRENT_STATE_2026-06-19.md`（已在上一 session commit）
- 全部 10 項關切已驗證；2 項標記為 doc-only（backup/restore → Sprint 5；auditability → Sprint 2），風險已明文記錄

### Step 1.5 — thread_id 決策
- 決定：**T1 — 保持 `thread_id == user_id`**（最低衝擊，不觸發 SPRINT1-CKPT-MIG）
- 文件：`docs/MEMORY_LAYER_DECISION_2026-06-20.md`（已在上一 session commit）

---

## Sprint 1 本日完成：S1-MEM-1

### 問題描述
LLM 收到「記住我最喜歡的顏色是綠色」時，不會主動呼叫 `manage_memory` tool。

### 根本原因
1. `MEMORY_SYSTEM_PROMPT` 未告知 LLM 何時該呼叫 tool
2. `agent_factory.py:120` 用 `.format()` 插入記憶內容，若記憶含 `{}` 會拋 KeyError
3. `AsyncPostgresStore.setup()` 在 `EMBED_MODEL=none` 時仍試圖建立 vector index，導致 `store` table 未被建立（`store_migrations` 誤判為已完成）

### 修復內容

| 檔案 | 修改 |
|------|------|
| `agent/prompts.py` | 重寫 `MEMORY_SYSTEM_PROMPT`，加入 manage_memory tool 呼叫規則與範例 |
| `agent/agent_factory.py:120` | `.format()` → `.replace()` |
| `db/postgres_utils.py` | `EMBED_MODEL=none` 時 `index_config=None`，跳過 vector index |

### 驗證結果 ✅

```sql
SELECT prefix, key, value FROM store WHERE value::text ILIKE '%green%';

 prefix     | key          | value
------------+--------------+-----------------------------------------------
 5178700920 | 7d509a25-... | {"content": "User's favorite color is green"}
```

Commit: `39f2752` — `fix(memory): S1-MEM-1 — add memory tool usage instructions to system prompt`

---

## 已知問題 / 技術債

| 項目 | 嚴重度 | 說明 |
|------|--------|------|
| `EMBED_MODEL=none` | Medium | 無向量搜尋，記憶只能精確比對；S1-MEM-2 需解決 Google embedding 配額或換用其他 provider |
| Google API Key 配額耗盡 | Medium | Free tier 配額用完（embedding + Gemini 模型全失敗）；需等重置或升級計費方案 |
| `store_migrations` 黑洞 | Low | 若 `store` table 被手動刪除，setup() 不會重建（migration 表誤判）；需加 idempotent check |
| OpenAI / claude-opus / claude-sonnet | Low | 配額或模型 ID 錯誤；只有 claude-haiku 與 gemini-2.5-flash-lite 健康 |
| `default_user` 硬編碼 | Medium | `main.py:233`；S1-BOOT-1 處理 |
| `.mcp.json` openmemory 條目 | Low | dev-only，S1-CLEAN-1 清除 |

---

## Sprint 1 任務清單（尚未開始）

依 `PROJECT_PLAN_v4.4.md` §Sprint 1：

| Task ID | Task | 狀態 |
|---------|------|------|
| S1-AUTH-1 | `users` + `api_keys` + `tenants` tables | ⬜ |
| S1-AUTH-2 | Auth middleware | ⬜ |
| S1-AUTH-3 | Per-tenant Redis namespace | ⬜ |
| S1-BOOT-1 | 移除 `default_user` 硬編碼 | ⬜ |
| S1-NS-1 | Namespace 升級為 `(tenant_id, user_id)` | ⬜ |
| S1-NS-MIG | Namespace migration plan + backfill script | ⬜ |
| S1-DEL-1 | 完成 `clear_user_data` TODO | ⬜ |
| S1-CLEAN-1 | 移除 dev-only `.mcp.json` openmemory | ⬜ |
| S1-UI-1 | NextAuth Google provider | ⬜ |
| S1-TEST-1 | Auth / tenant isolation / memory delete tests | ⬜ |
| **S1-MEM-1** | **Memory tool prompt fix** | **✅ 完成** |
| S1-MEM-2 | Retrieval quality + Google embedding | ⬜ |

> SPRINT1-CKPT-MIG 與 S1-TID-1 / S1-TEST-2 / S1-TEST-3：**不啟動**（Step 1.5 = T1）

---

## 環境狀態

```
Bot PID: 85905 (claude-haiku, running)
LLM_MODEL: claude-haiku
EMBED_MODEL: none  ← 暫時；S1-MEM-2 前不啟用 embedding
PG: pantheon DB — store table ✅, checkpoints ✅
Branch: claude/remote-control-Q2YAQ
```

---

## 下一步建議

1. **S1-MEM-2**：解決 embedding provider（等 Google 配額重置，或改用 Ollama local embedding）
2. **S1-AUTH-1**：開始資料庫 schema — `users`、`api_keys`、`tenants` tables
3. **PR review**：`claude/remote-control-Q2YAQ` → main，包含 S1-MEM-1 三個修改
