# ADR-0001: 將 Pantheon Memory System 抽出到 Aletheia

**狀態：** Accepted  
**日期：** 2026-06-25  
**決策者：** Vernon  
**相關 repo：** `salafadidas/project-pantheon`, `salafadidas/Aletheia`  
**相關計畫書：** `docs/PANTHEON_MEMORY_EXTRACTION_TO_ALETHEIA_PLAN_v1.0.md`

---

## 1. 背景

Project Pantheon 目前定位為 multi-engine multi-agent collaboration system，透過 PM Router、Researcher、Debater、Voter、Synthesizer 進行多模型協作、辯論與共識輸出。

Pantheon 的核心優勢是：

- 多模型研究
- 多角度辯論
- 共識投票
- 複雜問題 synthesis
- 高難度技術與策略問題審議

但 Pantheon 不應同時承擔所有長期記憶、跨專案 RAG、Notion / Obsidian 同步、GitHub docs sync、agent context gateway 等平台責任。這些責任更適合由 Aletheia 這個跨 project / LLM / agent 的總平台負責。

---

## 2. 決策

將 Pantheon Memory System 抽出，整合到 Aletheia，成為 **Aletheia Memory Core**。

Pantheon 之後不再作為 long-term memory owner，而是轉型為：

> **Council-as-a-Service：高難度、高風險、有衝突問題的多模型會議會。**

核心分工：

```text
Aletheia owns memory.
Pantheon reasons over memory.
GitHub validates memory.
Agents act on memory.
```

中文：

```text
Aletheia 擁有記憶。
Pantheon 審議記憶。
GitHub 驗證記憶。
Agent 執行記憶。
```

---

## 3. 抽出範圍

以下能力應移至 Aletheia：

| 能力 | 新 owner |
|---|---|
| session memory | Aletheia |
| decision memory | Aletheia |
| project context | Aletheia |
| user preference memory | Aletheia |
| agent memory | Aletheia |
| failure memory | Aletheia |
| vector memory / RAG index | Aletheia |
| context pack generation | Aletheia |
| memory promotion / governance | Aletheia |
| Notion / Obsidian sync | Aletheia |
| GitHub docs sync | Aletheia |

Pantheon 應保留：

- PM Router
- Researcher
- Debater
- Voter
- Synthesizer
- Council Resolution output
- ADR candidate output
- Memory update candidate output
- Aletheia client adapter

---

## 4. Pantheon Call-in 條件

Aletheia 只在以下情況呼叫 Pantheon：

- 架構決策
- 高風險 refactor
- 多方案技術選型
- agent 結論互相衝突
- RAG memory 互相衝突
- PR merge 前重大風險審查
- 產品策略 / roadmap
- memory promotion 有爭議

建議 threshold：

```text
complexity_score >= 7
risk_score >= 7
memory_conflict = true
architecture_change = true
security_sensitive = true
multi_agent_disagreement = true
```

---

## 5. 替代方案

### 方案 A：Pantheon 繼續擁有 memory

優點：

- 短期改動較少
- Pantheon 自給自足

缺點：

- 難以服務其他 project
- memory platform 與 council engine 耦合過深
- 日常查詢也要經過 Pantheon，成本與延遲較高
- 不利於 Aletheia 成為總平台

### 方案 B：每個 project 各自維護 memory

優點：

- 每個 project 獨立
- 實作簡單

缺點：

- 重複建置
- knowledge silo
- agent 無法共享跨 project context
- 記憶治理混亂

### 方案 C：Aletheia 統一擁有 memory，Pantheon 作為 Council Service

優點：

- 分工清楚
- 跨 project 可重用
- Pantheon 專注高價值 reasoning
- 適合 Notion / Obsidian / GitHub / Vector DB / MCP 架構

缺點：

- 需要新增 Aletheia integration
- 需要定義 API contract
- 短期架構多一層

採用方案 C。

---

## 6. 後果

### 正面後果

- Aletheia 成為所有 project / LLM / agent 的 memory source。
- Pantheon 成本可控，只在複雜任務出場。
- Codex、Claude Code、ChatGPT、Copilot 可共用同一份 context。
- GitHub 可作為 ADR、docs、agent instructions 的 source of truth。

### 負面後果 / 風險

- 需要建立 Aletheia Memory Core API。
- 需要處理 transition period。
- Pantheon 需新增 Aletheia client adapter。
- 若 Aletheia 不穩定，Pantheon context retrieval 會受影響。

---

## 7. 實作後續

後續文件：

- `docs/implementation/PANTHEON_MEMORY_EXTRACTION_PHASE1_IMPLEMENTATION_PLAN.md`
- `docs/integration/PANTHEON_ALETHEIA_API_CONTRACT.md`
- `docs/integration/PANTHEON_COUNCIL_CONTEXT_PACK_SPEC.md`

Phase 1 先做：

1. 盤點 Pantheon memory / session / report / context 相關 code。
2. 定義 Aletheia memory API contract。
3. 新增 Pantheon Aletheia client adapter。
4. 將 Council input/output 改為可與 Aletheia 串接。
