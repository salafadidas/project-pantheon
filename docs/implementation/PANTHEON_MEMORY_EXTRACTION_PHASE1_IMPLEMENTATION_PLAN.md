# Pantheon Memory Extraction — Phase 1 Implementation Plan

**版本：** v1.0  
**日期：** 2026-06-25  
**狀態：** Ready for new execution session  
**相關 ADR：** `docs/adr/ADR-0001-extract-pantheon-memory-to-aletheia.md`  
**相關計畫書：** `docs/PANTHEON_MEMORY_EXTRACTION_TO_ALETHEIA_PLAN_v1.0.md`

---

## 1. Phase 1 目標

Phase 1 的目標不是立刻大改 Pantheon，而是完成「盤點、界面定義、低風險 adapter scaffolding」。

本階段完成後，下一個 session / Codex 應能明確知道：

1. Pantheon 目前有哪些 memory / context / report / session 相關程式碼。
2. 哪些能力要移到 Aletheia。
3. Pantheon 需要如何透過 Aletheia client 取得 context pack。
4. Pantheon council output 要如何回傳 Aletheia。
5. 下一階段該改哪些檔案、風險在哪裡。

---

## 2. Phase 1 不做什麼

Phase 1 暫時不做：

- 不移除現有 Pantheon 功能。
- 不直接重構整個 graph。
- 不改 production execution path。
- 不刪除現有 session/report 行為。
- 不實作完整 Aletheia backend。
- 不讓 Pantheon 強依賴尚未完成的 Aletheia service。

Phase 1 以 documentation、interface、adapter skeleton、inventory 為主。

---

## 3. 工作項目

### Task 1：盤點 Pantheon 相關 code

檢查以下目錄與檔案：

```text
main.py
graph/
graph/state.py
graph/pantheon_graph.py
graph/nodes/
api/v1/sessions.py
api/v1/websocket.py
telegram_adapter/telegram_bot.py
llm/provider.py
llm/cost_tracker.py
db/
core/
config/
```

輸出文件：

```text
docs/implementation/PANTHEON_MEMORY_CONTEXT_INVENTORY.md
```

內容至少包含：

| 類型 | 目前位置 | 用途 | 是否移到 Aletheia | 備註 |
|---|---|---|---|---|
| session state | | | yes/no/later | |
| final report | | | yes/no/later | |
| debate history | | | yes/no/later | |
| cost summary | | | yes/no/later | |
| user/project context | | | yes/no/later | |
| Redis state | | | yes/no/later | |
| PostgreSQL data | | | yes/no/later | |

---

### Task 2：定義 Pantheon ↔ Aletheia API contract draft

新增文件：

```text
docs/integration/PANTHEON_ALETHEIA_API_CONTRACT.md
```

至少定義：

```text
GET /context-pack
POST /council/resolution
POST /memory-candidates
POST /adr-candidates
```

建議 interface：

```python
class AletheiaClient:
    async def get_context_pack(self, task: str, project: str, repo: str | None = None) -> dict: ...
    async def submit_council_resolution(self, session_id: str, resolution: dict) -> dict: ...
    async def submit_memory_update_candidates(self, session_id: str, candidates: list[dict]) -> dict: ...
    async def submit_adr_candidate(self, session_id: str, adr: dict) -> dict: ...
```

---

### Task 3：建立 adapter skeleton

新增：

```text
integrations/aletheia_client.py
```

或若現有架構更適合：

```text
pantheon/adapters/aletheia_client.py
```

建議先用 mock / no-op 實作，避免影響現有流程。

基本需求：

- 不需要真實連 Aletheia。
- 可由 config 控制是否啟用。
- 失敗時 fallback 到現有 Pantheon 行為。
- log 清楚說明 Aletheia integration 是否 active。

---

### Task 4：新增 Council Context Pack schema draft

新增文件：

```text
docs/integration/PANTHEON_COUNCIL_CONTEXT_PACK_SPEC.md
```

Schema draft：

```json
{
  "task": "string",
  "project": "string",
  "repo": "string|null",
  "complexity": "low|medium|high",
  "risk": "low|medium|high",
  "relevant_memories": [],
  "active_decisions": [],
  "related_files": [],
  "related_symbols": [],
  "conflicting_evidence": [],
  "requested_output": "council_resolution|adr_candidate|memory_review"
}
```

---

### Task 5：新增 Council Resolution schema draft

在同一文件或獨立文件中定義：

```json
{
  "session_id": "string",
  "resolution": "string",
  "confidence": 0.0,
  "majority_view": "string",
  "minority_view": "string|null",
  "risks": [],
  "recommended_actions": [],
  "adr_candidate": {},
  "memory_update_candidates": [],
  "agent_task_candidates": []
}
```

---

### Task 6：更新 CLAUDE.md / AGENTS.md 建議，不直接修改

Phase 1 先不要直接修改 `CLAUDE.md` 或 `AGENTS.md`，只產生建議：

```text
docs/implementation/PANTHEON_AGENT_INSTRUCTION_UPDATE_PROPOSAL.md
```

內容包括：

- Pantheon memory 已決定移交 Aletheia。
- future coding agents 應避免新增新的 long-term memory owner 到 Pantheon。
- 高難度決策應透過 Aletheia call Pantheon Council。

---

## 4. 建議執行順序

```text
1. git status / branch / remote check
2. run GitNexus impact/context checks if modifying symbols
3. create inventory document
4. create API contract document
5. create context pack spec
6. add adapter skeleton only if low risk
7. run tests if code changed
8. summarize changes
9. create PR or commit directly according to user preference
```

---

## 5. 驗收標準

Phase 1 完成條件：

- [ ] 已建立 `PANTHEON_MEMORY_CONTEXT_INVENTORY.md`
- [ ] 已建立 `PANTHEON_ALETHEIA_API_CONTRACT.md`
- [ ] 已建立 `PANTHEON_COUNCIL_CONTEXT_PACK_SPEC.md`
- [ ] 已建立或規劃 Aletheia client adapter skeleton
- [ ] 沒有破壞現有 Pantheon 5-phase workflow
- [ ] 若有 code change，已執行基本測試
- [ ] 已列出 Phase 2 implementation tasks

---

## 6. 新 session / Codex 啟動提示

新 session 可直接使用以下 prompt：

```text
請根據 project-pantheon 內以下文件開始 Phase 1：

1. docs/PANTHEON_MEMORY_EXTRACTION_TO_ALETHEIA_PLAN_v1.0.md
2. docs/adr/ADR-0001-extract-pantheon-memory-to-aletheia.md
3. docs/implementation/PANTHEON_MEMORY_EXTRACTION_PHASE1_IMPLEMENTATION_PLAN.md

目標：完成 Pantheon memory/context/session/report 相關程式碼盤點，建立 Pantheon ↔ Aletheia API contract，建立 Council Context Pack spec，並視風險建立 Aletheia client adapter skeleton。

請先讀 README.md、docs/ARCHITECTURE.md、CLAUDE.md、AGENTS.md。若修改 symbol，必須遵守 AGENTS.md 中 GitNexus impact analysis 規則。不要直接重構 graph，不要刪除現有功能。Phase 1 以 documentation、interface、adapter skeleton 為主。
```
