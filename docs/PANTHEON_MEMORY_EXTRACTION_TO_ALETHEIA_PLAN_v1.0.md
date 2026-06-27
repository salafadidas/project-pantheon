# Pantheon Memory 抽出到 Aletheia 計畫書

**版本：** v1.0  
**日期：** 2026-06-25  
**狀態：** Approved by Vernon — Ready for implementation planning  
**建議 repo：** `salafadidas/project-pantheon`  
**建議路徑：** `docs/PANTHEON_MEMORY_EXTRACTION_TO_ALETHEIA_PLAN_v1.0.md`  
**相關專案：** Project Pantheon、Project Aletheia  
**主題：** 將 Pantheon Memory System 抽出並整合到 Aletheia Memory Core

---

## 1. 核心結論

本計畫確認以下方向：

> **Pantheon 不再作為長期 memory platform 的 owner。**  
> **Pantheon Memory System 應抽出並整合到 Aletheia，形成 Aletheia Memory Core。**  
> **Pantheon 之後專注在 Council-as-a-Service，也就是高難度問題的多模型會議會。**

新的責任分工：

```text
Aletheia owns memory.
Pantheon reasons over memory.
GitHub validates memory.
Agents act on memory.
```

中文表述：

```text
Aletheia 擁有記憶。
Pantheon 審議記憶。
GitHub 驗證記憶。
Agent 執行記憶。
```

---

## 2. 背景

Project Pantheon 目前已經是 multi-engine multi-agent collaboration system，透過 Claude、GPT、Gemini 進行結構化多階段協作。現有流程包含：

1. PM Router
2. Researcher
3. Debater
4. Voter
5. Synthesizer

這表示 Pantheon 的核心價值是：

- 多模型研究
- 多角度辯論
- 共識投票
- 高品質 synthesis
- 複雜問題決策支援

但如果 Pantheon 同時負責：

- 長期記憶
- 跨專案 RAG
- 所有 agent 的 context gateway
- Notion / Obsidian sync
- GitHub docs sync
- 一般 coding task memory CRUD

系統責任會過重，也會降低未來可擴充性。

因此，應將 memory system 抽出到 Aletheia，讓 Aletheia 成為跨 project / LLM / agent 的總記憶平台。

---

## 3. 目標

本計畫目標：

1. 將 Pantheon 內與 memory、session、decision、RAG、context 有關的能力抽出。
2. 將上述能力整合到 Aletheia Memory Core。
3. 讓 Pantheon 從 memory owner 轉型為 Aletheia 可呼叫的 Council Service。
4. 讓所有 project / LLM / agent 都能透過 Aletheia 共用同一套 memory platform。
5. 降低 Pantheon 日常運行成本，讓它只在高難度、高風險、有爭議的問題中出場。

---

## 4. 新架構定位

### 4.1 Aletheia

Aletheia 定位為：

- AI Coding Operating Layer
- 第二大腦
- 記憶總平台
- RAG / hybrid search 平台
- Agent context gateway
- Cross-project knowledge OS

Aletheia 負責：

- memory schema
- memory storage
- session memory
- decision memory
- project memory
- user preference memory
- agent memory
- failure memory
- RAG index
- context pack generation
- memory promotion
- conflict detection
- freshness detection
- sensitivity filtering
- GitHub sync
- Notion / Obsidian sync
- Pantheon call-in

### 4.2 Pantheon

Pantheon 定位為：

- Council-as-a-Service
- 多模型會議會
- 高難度問題研究與辯論引擎
- 架構與策略決策輔助引擎
- Memory conflict resolution engine

Pantheon 負責：

- PM Router
- Researcher
- Debater
- Voter
- Synthesizer
- Council Resolution
- Majority / minority opinion summary
- Risk analysis
- Recommended actions
- ADR candidate generation
- Memory update candidate generation

---

## 5. 要從 Pantheon 抽出的能力

| Pantheon 原能力 | 抽出後放到 Aletheia 的角色 |
|---|---|
| session memory | 所有 agent / project 的跨 session 工作紀錄 |
| decision memory | 架構決策、技術選型、產品決策 |
| vector memory / pgvector | 跨專案 RAG 與 semantic search |
| user preference | Vernon 的長期偏好與工作風格 |
| project context | 各專案背景、限制、roadmap、狀態 |
| agent memory | Codex、Claude Code、ChatGPT、Pantheon 的角色與偏好 |
| failure memory | 錯誤紀錄、踩坑、lesson learned |
| final report summary | 可查詢、可審核、可版本化的 knowledge artifact |
| cost / model performance log | 模型成本、品質、延遲與可靠度紀錄 |
| context pack generator | 給不同 agent 使用的任務上下文包 |

---

## 6. Pantheon 應保留的能力

Pantheon 保留：

```text
pantheon/
  council/
    router.py
    researcher.py
    debater.py
    voter.py
    synthesizer.py
  adapters/
    aletheia_client.py
  outputs/
    council_resolution.py
    adr_candidate.py
    memory_update_candidate.py
```

Pantheon 不再直接擁有 memory database。Pantheon 應透過 Aletheia API 取得 context，完成 council reasoning 後回傳 structured output。

---

## 7. Pantheon 不應再負責的事情

Pantheon 不應再作為：

- 所有 project 的主要 memory database
- 跨 agent 的主要 RAG platform
- Notion / Obsidian sync manager
- GitHub docs sync owner
- 一般日常 coding task 的必要流程
- 所有 agent 的主要 context gateway
- 長期記憶治理 owner

這些責任應由 Aletheia 負責。

---

## 8. Pantheon Council Call-in 條件

Pantheon 不需要處理所有小任務。Aletheia 只在以下情境 call Pantheon：

| 情況 | 是否 call Pantheon |
|---|---|
| 一般小 code 修改 | 否 |
| 一般 bug fix | 否 |
| 文件整理 | 否 |
| 高風險 refactor | 是 |
| 架構決策 | 是 |
| 多方案技術選型 | 是 |
| AI agent 結論互相衝突 | 是 |
| RAG memory 互相衝突 | 是 |
| PR merge 前重大風險審查 | 是 |
| 產品策略 / roadmap | 是 |
| memory promotion 有爭議 | 是 |

建議 call-in threshold：

```text
complexity_score >= 7
risk_score >= 7
memory_conflict = true
architecture_change = true
security_sensitive = true
multi_agent_disagreement = true
```

---

## 9. Pantheon Council Input

Aletheia 呼叫 Pantheon 時，應傳入完整 Council Context Pack。

範例：

```json
{
  "task": "Evaluate whether to extract Pantheon memory into Aletheia",
  "project": "project-pantheon",
  "complexity": "high",
  "risk": "medium",
  "relevant_memories": [],
  "active_decisions": [],
  "related_files": [],
  "conflicting_evidence": [],
  "requested_output": "council_resolution"
}
```

---

## 10. Pantheon Council Output

Pantheon 回傳 structured result 給 Aletheia。

範例：

```json
{
  "resolution": "Extract Pantheon memory system into Aletheia Memory Core",
  "confidence": 0.88,
  "majority_view": "...",
  "minority_view": "...",
  "risks": [],
  "recommended_actions": [],
  "adr_candidate": {},
  "memory_update_candidates": [],
  "agent_task_candidates": []
}
```

---

## 11. 優點

### 11.1 架構責任更清楚

Aletheia 負責 memory，Pantheon 負責 council reasoning。兩者分工明確。

### 11.2 Aletheia 可服務所有 project

抽出後的 memory core 不再只屬於 Pantheon，而可支援：

- Project Pantheon
- Project Aletheia
- Transparent Micro LED projects
- AI coding workflow projects
- Future GitHub repos
- ChatGPT / Codex / Claude Code / Copilot / Other Agents

### 11.3 Pantheon 成本更可控

Pantheon 是多模型會議系統，成本與延遲較高。只在高風險、高複雜度情境呼叫，可以提升整體效率。

### 11.4 減少 memory lock-in

Memory 由 Aletheia 統一管理後，未來可接不同 agent，不會被 Pantheon workflow 綁死。

### 11.5 更適合 GitHub source of truth

Aletheia 可將 approved memory 或重要決策同步成：

```text
docs/adr/*.md
docs/session-summary/*.md
docs/project-context/*.md
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
```

---

## 12. 缺點與風險

### 12.1 系統多一層 Aletheia

原本：

```text
Pantheon → Memory → Output
```

變成：

```text
Agent → Aletheia → Memory / RAG / Context Pack → Agent
                      ↓
                 Pantheon Council
```

對策：先做 MVP，不一次做完整 OS。

### 12.2 Ownership 需要定義清楚

必須明確定義：

| 資料 | Owner |
|---|---|
| code | GitHub |
| code graph | GitNexus |
| long-term memory | Aletheia |
| council output | Pantheon |
| final decision | GitHub ADR + Aletheia |
| agent instruction | GitHub + Aletheia |
| raw chat | 短期保存或摘要化 |

### 12.3 Memory promotion 需要審核流程

不能讓所有 agent 自動寫入 long-term memory。

建議流程：

```text
Raw event
  ↓
Session summary
  ↓
Candidate memory
  ↓
Aletheia 檢查 duplicate / conflict / sensitivity / freshness
  ↓
必要時 call Pantheon Council
  ↓
Vernon 或 PR approve
  ↓
Approved memory
```

### 12.4 Pantheon call-in 成本較高

Pantheon 是多模型 research/debate/vote/synthesis，應避免被所有小任務呼叫。

---

## 13. MVP 實作順序

### Phase 1：盤點 Pantheon 現有 memory 相關能力

目標：

- 找出 session memory、decision memory、RAG、context、summary 相關程式碼。
- 判斷哪些可抽出，哪些應保留在 Pantheon。

### Phase 2：建立 Aletheia Memory Core Interface

目標：

- 定義 Aletheia memory API contract。
- Pantheon 從本地 memory owner 轉為 Aletheia memory consumer。

### Phase 3：Pantheon 改接 Aletheia Client

新增：

```text
pantheon/adapters/aletheia_client.py
```

功能：

- get_context_pack()
- submit_council_resolution()
- submit_memory_update_candidates()
- submit_adr_candidate()

### Phase 4：Council Context Pack 支援

Pantheon 不再直接處理零散資料，而是處理 Aletheia 給出的 Council Context Pack。

### Phase 5：Council Output 回寫 Aletheia

Pantheon 完成議會流程後，應把結果回傳給 Aletheia，由 Aletheia 決定是否：

- 寫入 memory
- 建立 ADR
- 建立 GitHub issue
- 建立 coding context pack
- 更新 agent instructions

---

## 14. 後續 GitHub 文件建議

後續可新增：

```text
docs/adr/ADR-0001-extract-pantheon-memory-to-aletheia.md
docs/integration/PANTHEON_ALETHEIA_API_CONTRACT.md
docs/integration/PANTHEON_COUNCIL_CONTEXT_PACK_SPEC.md
docs/implementation/PANTHEON_MEMORY_EXTRACTION_IMPLEMENTATION_PLAN.md
```

---

## 15. 已確認決策

1. Pantheon Memory System 應抽出到 Aletheia。
2. Aletheia 是 long-term memory owner。
3. Pantheon 是 Council Service，不是 memory platform。
4. Pantheon 只在高複雜度、高風險、有衝突的情境被 Aletheia call in。
5. Council output 應回傳 Aletheia，由 Aletheia 負責 memory promotion 與 GitHub sync。
6. 不應讓 Pantheon 負責 Notion / Obsidian / cross-project memory / general RAG platform。

---

## 16. 下一步

建議下一步：

1. 建立 Aletheia repo 或確認現有 Aletheia repo 名稱。
2. 將 Aletheia architecture plan 放入 Aletheia repo。
3. 在 Pantheon repo 內建立 ADR-0001。
4. 盤點 Pantheon 現有 memory 相關 code。
5. 定義 Aletheia Memory Core API。
6. 讓 Pantheon 新增 Aletheia client adapter。
