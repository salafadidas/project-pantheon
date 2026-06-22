---
title: Project Pantheon — Status Summary
date: 2026-06-22
sprint: Sprint 1 in progress — S1-DEL-1 fix on review
branch: fix/s1-del-1-clear-user-data (PR pending)
---

# Project Pantheon — Status Summary (2026-06-22)

## 整體進度

| 階段 | 狀態 | 說明 |
|------|------|------|
| Sprint 0 | ✅ Closed | Issue #23; 5 docs committed; 4 baseline corrections |
| Sprint 1 capacity (#22) | ✅ Resolved | T2 locked, OAuth → Sprint 6, 1 週時程 |
| S1-MEM-1 | ✅ Done | PR #24 merged (`f3a8d29`) |
| **S1-DEL-1** | 🟡 **PR ready — awaiting review** | Branch `fix/s1-del-1-clear-user-data` |
| S1-NS-MIG → S1-NS-1 | 🔴 Blocked | 等 S1-DEL-1 merge |
| S1-BOOT-1, S1-AUTH-1, #21 | 🔜 Queued | 可並行，尚未啟動 |

---

## 今日工作：S1-DEL-1 三個 bug 修復

### 修復摘要

| Bug | 位置 | 問題 | 修法 |
|-----|------|------|------|
| 1 | `db/user_data.py:60-83` | `store` + `store_vectors` 共用同一個 connection context；`EMBED_MODEL=none` 時 `store_vectors` 不存在，psycopg3 rollback 整個 transaction，`store` DELETE 被靜默還原 | 拆成獨立 connection context；`vectors_enabled` flag 控制是否執行 3b 段 |
| 2 | `db/user_data.py:43-48` | `checkpoint_writes` 完全沒刪；殘留 rows 導致下次對話 `INVALID_CHAT_HISTORY` 永久壞掉該 user | 在同一 transaction 內先刪 `checkpoint_writes` 再刪 `checkpoints`（FK 順序） |
| 3 | `db/user_data.py:33-97` | 三段 try/except 各自獨立，部分失敗無補償 | 採 accepted-risk 方案：各段保持獨立 + 每段失敗都記 ERROR log 含足夠 context 可手動 reconcile；saga 補償延後 |

### 架構變化（新 `clear_user_data` 四段結構）

```
Section 1 — Redis         (獨立 try/except)
Section 2 — Checkpoints   (checkpoint_writes + checkpoints 同一 transaction)
Section 3a — store        (獨立 connection context)
Section 3b — store_vectors (獨立 connection context，EMBED_MODEL=none 時跳過)
Section 3c — legacy store.adelete (backward compat)
```

### TYPE_CHECKING 保護

`db/user_data.py` 的 `psycopg_pool` / `redis` / `langgraph` import 移至 `TYPE_CHECKING` guard，避免在無 libpq 環境（CI sandbox）下 import 爆炸。生產環境不受影響（型別仍正確）。

### Regression tests — `tests/test_memory_delete.py`

| 測試名稱 | 對應 Bug | 驗證內容 |
|---------|---------|---------|
| `test_checkpoint_writes_deleted` | Bug 2 | `checkpoint_writes` DELETE 先於 `checkpoints` DELETE 執行 |
| `test_store_delete_succeeds_when_store_vectors_missing` | Bug 1 | `store_vectors` 不存在時 `store` DELETE 仍 commit |
| `test_store_delete_skips_vectors_when_embed_model_none` | Bug 1 | `EMBED_MODEL=none` 時 `pool.connection()` 只呼叫 2 次（無 vectors 段） |
| `test_redis_failure_does_not_abort_checkpoints_section` | Bug 3 | Redis 失敗後 checkpoints 段仍執行 |
| `test_checkpoints_failure_does_not_abort_store_section` | Bug 3 | checkpoints 失敗後 store 段仍執行 |
| `test_full_delete_embed_model_none` | Happy path | 全流程 EMBED_MODEL=none 驗證 |
| `test_full_delete_with_vectors` | Happy path | 全流程含 store_vectors 驗證 |

**本機 mock 測試結果：7/7 passed**（無 live DB/Redis 需求）

---

## 本機 Row 7 Re-verification Checklist（需要你在本機跑）

PR merge 前，請在本機執行以下步驟確認三表歸零：

### 前置：切到 feature branch
```bash
git fetch origin
git checkout fix/s1-del-1-clear-user-data
```

### Step 1 — 確認環境
```bash
# EMBED_MODEL 應為 none（目前 dev env）
grep EMBED_MODEL .env

# Bot 應能正常啟動
python main.py &
```

### Step 2 — 製造資料（填三個表）
對 Telegram bot 發幾條訊息，說一些讓 bot 記住的事：
```
User: 我的最愛顏色是藍色，請記住這件事。
User: 幫我記住我住在新竹。
```

### Step 3 — 確認三表都有資料
```sql
-- 連到 pantheon DB
psql -U vernon -d pantheon

SELECT COUNT(*) FROM store WHERE prefix = '<your_user_id>';
-- 預期 > 0

SELECT COUNT(*) FROM checkpoints WHERE thread_id = '<your_user_id>';
-- 預期 > 0

SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = '<your_user_id>';
-- 預期 > 0
```

### Step 4 — 執行 /reset
```
User: /reset
Bot: ✅ 已清除所有對話記錄和記憶
```

### Step 5 — 驗證三表歸零（Row 7 Pass 條件）
```sql
SELECT COUNT(*) FROM store WHERE prefix = '<your_user_id>';
-- 預期：0  ✅

SELECT COUNT(*) FROM checkpoints WHERE thread_id = '<your_user_id>';
-- 預期：0  ✅

SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = '<your_user_id>';
-- 預期：0  ✅
```

### Step 6 — 驗證下一輪對話正常（Bug 2 直接驗收）
```
User: 你好，我叫 Vernon。
-- 預期：正常回應，沒有 INVALID_CHAT_HISTORY 錯誤
```

### Step 7 — 跑 regression tests
```bash
pytest tests/test_memory_delete.py -v
# 預期：7/7 passed
```

**全部 Pass → PR 可以 merge，issue #25 關閉，S1-NS-1 阻擋解除。**

---

## Issue #25 Fix Checklist 對照

| Checklist 項目 | 狀態 |
|---------------|------|
| Bug 1 fix — store DELETE 不再被 rollback | ✅ 已修復（commit `a19ad57`） |
| Bug 2 fix — checkpoint_writes 隨 checkpoints 一起刪 | ✅ 已修復（commit `a19ad57`） |
| Bug 3 — 決策已記錄（accepted-risk + 各段獨立 + ERROR log） | ✅ 已記錄（commit `a19ad57`） |
| `tests/test_memory_delete.py` 七個 regression tests | ✅ 已寫（commit `a5c0dfa`），7/7 mock 通過 |
| Row 7 本機 re-verify（三表→0） | ⬜ 等你本機跑 |
| `MEMORY_CURRENT_STATE_2026-06-19.md` Row 7 → ✅ | ⬜ 本機驗收後更新 |
| `MEMORY_LAYER_DECISION_2026-06-19.md` Candidate A C2 → ✅ | ⬜ 本機驗收後更新 |

---

## 下一步

**你需要做的：**
1. 本機跑上面 Row 7 Re-verification Checklist
2. 確認 7/7 通過後，在 GitHub 開 PR（base: main，head: fix/s1-del-1-clear-user-data）
3. Merge 後告訴我 → 我更新 `MEMORY_CURRENT_STATE` + `MEMORY_LAYER_DECISION` 兩份 doc，並關閉 issue #25

**PR merge 後，S1-NS-1 阻擋解除，可接著動的任務：**
- 等 review 時：可切 `S1-BOOT-1`（移除 `default_user` hardcoding，`telegram_bot.py:191-195`）
- S1-NS-1 阻擋解除後：S1-NS-MIG 執行細節文件 → S1-NS-1 code change

---

## Cross-references

- Issue #25 (blocker): `S1-DEL-1 fix — 3 bugs in clear_user_data`
- PR branch: `fix/s1-del-1-clear-user-data`
- Commits: `a19ad57` (fix) · `a5c0dfa` (tests)
- Sprint 0 closure: issue #23
- Sprint 1 capacity: issue #22
- S1-MEM-1 (done): PR #24, commit `f3a8d29`
- Stage 2 plan: `docs/PROJECT_PLAN_v4.4.md`
