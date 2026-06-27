# Pantheon Council Context Pack Spec

**Phase:** 1 — schema draft  
**Status:** Draft for review

## Purpose

A Council Context Pack is the memory/context payload Aletheia prepares for Pantheon when a task is complex, risky, architectural, conflict-heavy, or strategy-related.

Pantheon should reason over this pack but should not own or mutate long-term memory directly.

## Call-in threshold

Aletheia may call Pantheon when any of the following is true:

```text
complexity_score >= 7
risk_score >= 7
memory_conflict = true
architecture_change = true
security_sensitive = true
multi_agent_disagreement = true
```

## Council Context Pack schema

```json
{
  "context_pack_id": "string",
  "generated_at": "ISO-8601 string",
  "target_agent": "pantheon",
  "task": "string",
  "project": "string",
  "repo": "string|null",
  "complexity": "low|medium|high",
  "complexity_score": 0,
  "risk": "low|medium|high",
  "risk_score": 0,
  "requested_output": "council_resolution|adr_candidate|memory_review",
  "relevant_memories": [],
  "active_decisions": [],
  "related_files": [],
  "related_symbols": [],
  "conflicting_evidence": [],
  "constraints": [],
  "required_checks": [],
  "source_priorities": [],
  "freshness_warnings": [],
  "sensitivity_warnings": [],
  "metadata": {}
}
```

## Field notes

| Field | Owner | Notes |
|---|---|---|
| `context_pack_id` | Aletheia | Stable ID for audit/replay. |
| `task` | Agent/User → Aletheia | Original task. Pantheon should preserve this in output. |
| `project` / `repo` | Aletheia | Used for memory filtering and GitHub validation. |
| `complexity_score` / `risk_score` | Aletheia | Numeric trigger signals; keep raw values for audit. |
| `relevant_memories` | Aletheia | Approved or candidate memories with status labels. |
| `active_decisions` | Aletheia + GitHub | ADRs, accepted decisions, active constraints. |
| `related_files` | Aletheia/GitHub/GitNexus | File references only; Pantheon should not infer unstated code changes. |
| `related_symbols` | Aletheia/GitNexus | Symbol references only. Impact analysis remains required before symbol edits. |
| `conflicting_evidence` | Aletheia | Use for council disagreement and memory conflict resolution. |
| `required_checks` | Aletheia/GitHub | Tests, review gates, GitNexus checks, security checks. |
| `freshness_warnings` | Aletheia | Warns Pantheon about possibly stale memories. |
| `sensitivity_warnings` | Aletheia | Prevents leaking sensitive context into outputs. |

## Relevant memory item schema

```json
{
  "id": "string",
  "title": "string",
  "memory_type": "project_memory|session_memory|decision_memory|code_memory|agent_memory|user_preference|failure_memory|tool_memory|evaluation_memory|context_pack|adr",
  "status": "candidate|approved|active|deprecated|superseded|conflict|archived",
  "content": "string",
  "confidence": 0.0,
  "sensitivity": "public|internal|confidential|sensitive",
  "source_type": "notion|obsidian|github|pantheon_council|agent|manual",
  "source_url": "string|null",
  "source_path": "string|null",
  "last_reviewed": "ISO-8601 string|null",
  "related_files": [],
  "related_symbols": [],
  "tags": []
}
```

## Council Resolution schema

Pantheon submits this back to Aletheia after reasoning.

```json
{
  "session_id": "string",
  "context_pack_id": "string|null",
  "project": "string",
  "repo": "string|null",
  "task": "string",
  "resolution": "string",
  "confidence": 0.0,
  "majority_view": "string",
  "minority_view": "string|null",
  "risks": [],
  "recommended_actions": [],
  "adr_candidate": {},
  "memory_update_candidates": [],
  "agent_task_candidates": [],
  "evidence": [],
  "cost_summary": {},
  "created_by": "pantheon",
  "created_at": "ISO-8601 string"
}
```

## Memory update candidate schema

```json
{
  "title": "string",
  "memory_type": "decision_memory|project_memory|failure_memory|evaluation_memory|code_memory|agent_memory",
  "content": "string",
  "confidence": 0.0,
  "sensitivity": "public|internal|confidential|sensitive",
  "source_type": "pantheon_council",
  "source_path": "string|null",
  "related_files": [],
  "related_symbols": [],
  "tags": [],
  "promotion_reason": "string"
}
```

## ADR candidate schema

```json
{
  "title": "string",
  "status": "proposed",
  "context": "string",
  "decision": "string",
  "consequences": [],
  "alternatives": [],
  "related_files": [],
  "tags": []
}
```

## Compatibility with current Pantheon state

| Current Pantheon state field | Context / output mapping |
|---|---|
| `task` | Context Pack `task`; Council Resolution `task`. |
| `session_id` | Council Resolution `session_id`. |
| `research_results` | Council Resolution `evidence` or detail attachment. |
| `debate_history` | Council Resolution evidence/audit detail. |
| `votes` | Council Resolution majority/minority analysis input. |
| `consensus` | Council Resolution `resolution` candidate. |
| `final_report` | Human-readable rendering of Council Resolution. |
| `cost_summary` | Optional `cost_summary`; possibly future `evaluation_memory`. |

## Phase 1 non-goals

- No automatic promotion to approved memory.
- No production requirement for live Aletheia service.
- No change to existing Pantheon graph execution path.
- No direct write to Notion, Obsidian, Vector DB, or GitHub ADR from Pantheon.
