# Project Pantheon — 進度總結與下一步建議

## 1. 整體進度（截至今日 2026-05-03）

| 階段 | 狀態 | 備註 |
|------|------|------|
| **Stage 1 — PoC** | ✅ 完成 | tagged `v0.1.0-poc`（2026-04-01）|
| **PoC 後增量功能（v0.1.0 → HEAD）** | ✅ 14 commits | 已超越原 PoC 範圍 |
| **Stage 2 — Production Deployment** | ❌ 未啟動 | sprint plan 尚未撰寫 |
| **Stage 3 — Eigent 整合** | ⏸ 暫緩 | Stage 2 完成後再決議 |

---

## 2. PoC 之後額外完成的功能（plan v3.3 沒有記錄）

| Commit | 功能 | 重要性 |
|--------|------|--------|
| `64a1a30` | Model selector UI + pricing | ⭐⭐⭐ |
| `b8d748a` | Real-time streaming + debate UI dedup + quota fallback | ⭐⭐⭐⭐ |
| `78b65ce` | Markdown rendering + Gemini 503 quota handling | ⭐⭐⭐ |
| `85fb918` | Robust LLM quota fallback + startup health check | ⭐⭐⭐⭐ |
| `3e44ea1` | 504/timeout treated as transient quota error | ⭐⭐⭐ |
| `0a0fdc1` | Health-aware model selection (UI 過濾 unhealthy) | ⭐⭐⭐⭐ |
| `b3e82c2` | Telegram 回覆 parse_mode Markdown→HTML | ⭐⭐ |
| `efd6793` | Server 重啟時 orphan session recovery | ⭐⭐⭐⭐ |
| `9b0aec0` | Telegram document handler + missing selected_models | ⭐⭐⭐⭐ |
| `f980eca` 等 5 個 commit | NotebookLM 事件驅動同步 + macOS launchd 自動上傳 | ⭐⭐⭐ |

> 📌 **Plan 嚴重落後於 code**：plan 寫到 v3.3（2026-04-14），但程式碼又往前推進了 10+ 個 PR-quality 的功能。

---

## 3. ⚠️ 立即需要處理的 3 件事

### 🔴 #1 未提交的修改有「破洞」風險（最緊急）

```
M  agent/agent_factory.py     ← import sanitize_messages
M  llm/quota_fallback.py      ← import sanitize_messages
?? utils/message_utils.py     ← 未追蹤！
```

**問題**：`utils/message_utils.py` 是新增檔案（提供 `sanitize_messages` 修掉 Anthropic「empty text block」400 錯誤），但它被忘了 `git add`。如果你只 commit 那 2 個 .py 檔，**整個程式會炸 ImportError**。

**動作**：下一次 commit 時三個檔案必須一起進去。

### 🟡 #2 Plan v3.3 已過時 4 週、進度沒記錄

需要 bump 到 v3.4，把以下加入 §2「Current Progress Snapshot」：
- 健康檢查 + quota fallback
- 串流 UI + model selector UI + 健康過濾
- Orphan recovery + Telegram 修補
- NotebookLM 自動同步整條 pipeline

### 🟡 #3 Model 價格表已 3 週未驗證

依 `~/.claude/rules/model-catalog-maintenance.md`，每週一 09:00 應跑一次。**請我跑一次 diff 給你審核** — 我不會自動改 `llm/model_catalog.py`。

---

## 4. GitHub & 上游現況

| 項目 | 狀態 |
|------|------|
| `origin/main` vs `HEAD` | ✅ 已同步（無分歧）|
| `upstream/main`（langgraph-telegram-bot）| ✅ 無新 commit |
| 開啟中的 PR | 0 個 |
| 開啟中的 Issue | 1 個（#1 "Scheduling Invokations"，2025-07 開的，**過期 8 個月**，建議 close 或重寫）|
| CI（ci.yml）| 未顯示最近執行記錄，建議手動 trigger 一次驗證 |

**建議動作**：
- close issue #1（已被 v0.2 streaming 功能取代）
- 把目前 HEAD 打一個新 tag：`v0.2.0-streaming` 標記里程碑

---

## 5. 推薦下一步路線圖

### 🎯 本週（5/3 – 5/9）

```
[ ] Step 1: 完成手上未 commit 的 sanitize_messages 修補
            (3 檔一起 commit + 跑 pytest 驗證)
[ ] Step 2: bump PROJECT_PLAN_v3.3 → v3.4，補完所有缺漏的 commit
[ ] Step 3: 讓我跑一次 model catalog diff，審核後決定要不要改價格
[ ] Step 4: GitHub 整理：關 issue #1、打 v0.2.0-streaming tag
[ ] Step 5: 重新測試 Telegram /submit 上傳 Aletheia PLAN（驗證新 document handler）
```

### 🚀 本月（Stage 2 啟動）

需要先回答 plan §7「Open Questions」這 4 個 TBD 決策：

| 決策 | 我建議的方向 | 理由 |
|------|-------------|------|
| Cloud target | **GCP Cloud Run + Memorystore** | LangGraph + Redis pub/sub 友善；Gemini 走內網省錢 |
| Auth strategy | **API Key + 簡易 OAuth (Google)** | 低成本、與 Google 帳號整合 |
| Frontend | **保留 Next.js**，加 NextAuth | 已成熟，無需重寫 |
| Stage 3 Eigent | **暫緩**至 Stage 2 完成 | 避免擴張範圍 |

接著撰寫 **PROJECT_PLAN_v4.0.md**，把 Stage 2 拆成 4–6 週 sprint：

```
Week 1: 多租戶 session 隔離 + API Key auth
Week 2: Prometheus + Grafana + structured tracing
Week 3: GCP Cloud Run 部署 + Cloud SQL + Memorystore
Week 4: Rate limiting + SLA 定義
Week 5: 效能測試 + 災難復原演練
Week 6: User accounts + session history UI
```

---

## 6. 建議行動項目

```
[ ] A: 補上 utils/message_utils.py 並完成這次 commit + 跑測試
[ ] B: bump plan v3.3 → v3.4 並補完所有遺漏的進度
[ ] C: 跑 model catalog 價格 diff（不會自動改檔）
[ ] D: 開始撰寫 Stage 2 PROJECT_PLAN_v4.0.md 草稿
[ ] E: 關 GitHub issue #1 並打 v0.2.0-streaming tag
```
