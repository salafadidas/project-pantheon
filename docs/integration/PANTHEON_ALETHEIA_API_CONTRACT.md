# Pantheon ↔ Aletheia API Contract Draft

**Phase:** 1 — planning contract  
**Status:** Draft for review  
**Non-goal:** This document does not require Pantheon to call a live Aletheia service yet.

## Responsibility boundary

```text
Aletheia owns memory.
Pantheon reasons over memory.
GitHub validates memory.
Agents act on memory.
```

Pantheon consumes context and submits structured reasoning outputs. Aletheia owns memory schemas, storage, retrieval, review queues, conflict detection, freshness checks, GitHub sync, Notion/Obsidian sync, and context pack generation.

## Transport assumptions

Phase 1 assumes REST-compatible JSON over HTTP. A future MCP interface may wrap the same logical contract.

Base URL is configured by environment:

```text
ALETHEIA_BASE_URL=http://localhost:8080
ALETHEIA_ENABLED=false
ALETHEIA_TIMEOUT_SECONDS=10
```

If Aletheia is disabled or unavailable, Pantheon must fall back to its current 5-phase workflow.

## Endpoint: GET /context-pack

Pantheon requests task-specific context from Aletheia before council execution.

### Query parameters

| Name | Type | Required | Description |
|---|---:|---:|---|
| `task` | string | yes | User task or council question. |
| `project` | string | yes | Project key, e.g. `project-pantheon`. |
| `repo` | string | no | GitHub repository full name. |
| `target_agent` | string | no | Usually `pantheon`. |
| `requested_output` | string | no | `council_resolution`, `adr_candidate`, or `memory_review`. |

### Response

See `PANTHEON_COUNCIL_CONTEXT_PACK_SPEC.md`.

## Endpoint: POST /council/resolution

Pantheon submits final Council Resolution after synthesis.

### Request body

```json
{
  "session_id": "string",
  "project": "string",
  "repo": "string|null",
  "task": "string",
  "resolution": "string",
  "confidence": 0.0,
  "majority_view": "string",
  "minority_view": "string|null",
  "risks": [],
  "recommended_actions": [],
  "evidence": [],
  "cost_summary": {},
  "created_by": "pantheon"
}
```

### Response body

```json
{
  "accepted": true,
  "aletheia_record_id": "string|null",
  "status": "candidate|queued_for_review|rejected",
  "review_url": "string|null",
  "warnings": []
}
```

## Endpoint: POST /memory-candidates

Pantheon submits candidate memories produced during council reasoning. Aletheia must not treat these as approved memory until review/governance passes.

### Request body

```json
{
  "session_id": "string",
  "project": "string",
  "repo": "string|null",
  "candidates": [
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
      "tags": []
    }
  ]
}
```

### Response body

```json
{
  "accepted_count": 0,
  "rejected_count": 0,
  "candidate_ids": [],
  "warnings": []
}
```

## Endpoint: POST /adr-candidates

Pantheon submits ADR candidates. GitHub remains the validation surface for accepted ADRs.

### Request body

```json
{
  "session_id": "string",
  "project": "string",
  "repo": "string|null",
  "adr": {
    "title": "string",
    "status": "proposed",
    "context": "string",
    "decision": "string",
    "consequences": [],
    "alternatives": [],
    "related_files": [],
    "tags": []
  }
}
```

### Response body

```json
{
  "accepted": true,
  "candidate_id": "string|null",
  "github_pr_url": "string|null",
  "review_url": "string|null",
  "warnings": []
}
```

## Suggested Pantheon client interface

```python
class AletheiaClient:
    async def get_context_pack(self, task: str, project: str, repo: str | None = None) -> dict: ...
    async def submit_council_resolution(self, session_id: str, resolution: dict) -> dict: ...
    async def submit_memory_update_candidates(self, session_id: str, candidates: list[dict]) -> dict: ...
    async def submit_adr_candidate(self, session_id: str, adr: dict) -> dict: ...
```

## Failure and fallback rules

1. Aletheia unavailable must not block Pantheon council execution in Phase 1/2.
2. Aletheia write failures should be logged and returned as warnings, not crash synthesis.
3. Pantheon must never write directly to approved long-term memory.
4. Submitted memory items are candidates only.
5. GitHub PR/ADR remains the validation path for durable architectural decisions.

## Open questions

- Should Context Pack retrieval be synchronous before `pm_router`, or should it become a pre-node in the graph?
- Should cost summaries become `evaluation_memory` in Aletheia or remain Pantheon operational telemetry?
- Should live phase events be mirrored into Aletheia audit logs, or only final council outputs?
