# Pantheon Memory / Context / Session Inventory

**Phase:** 1 — implementation planning  
**Status:** Draft for review  
**Scope:** Inventory only; no production behavior changes.

## Guiding principle

```text
Aletheia owns memory.
Pantheon reasons over memory.
GitHub validates memory.
Agents act on memory.
```

Pantheon should not gain new long-term memory ownership during this transition. Anything that looks like durable memory, cross-project context, RAG, memory governance, or agent context packaging should move toward Aletheia ownership.

## Inventory summary

| Type | Current location | Current use | Move to Aletheia? | Notes / Phase 2 action |
|---|---|---|---|---|
| Session state | `graph/state.py` | LangGraph runtime state: task, phase, session_id, user_id, selected models, phase outputs, cost summary, messages. | later | Keep as ephemeral council execution state. Aletheia may supply initial context pack and receive final structured output, but Pantheon still needs runtime state while executing a council. |
| Workflow graph | `graph/pantheon_graph.py` | 5-phase council orchestration: PM Router → Researcher → Debater → Voter → Synthesizer. | no | Remains Pantheon core. Do not refactor in Phase 1. |
| Session API | `api/v1/sessions.py` | Creates sessions, starts graph runs, stores transient session status/final report/cost_summary in Redis. | partial/later | Durable session summaries and final report promotion should be submitted to Aletheia later. Current Redis flow remains unchanged in Phase 1. |
| WebSocket events | `api/v1/websocket.py` | Streams phase/session events through Redis pub/sub. | no | Streaming remains Pantheon runtime behavior. Aletheia does not need to own live event transport in Phase 1. |
| Final report | `graph/state.py`, `api/v1/sessions.py` | Synthesized markdown result stored in final_state then Redis. | yes | Aletheia should eventually receive final reports as candidate memory / session summary / council resolution. Phase 1 defines contract only. |
| Research results | `graph/state.py`, `graph/nodes/researcher.py` | Per-model independent research outputs. | candidate | Useful as evidence in Aletheia, but should not be auto-promoted to approved memory. Store as candidate/evidence with review status. |
| Debate history | `graph/state.py`, `graph/nodes/debater.py` | Multi-round debate records. | candidate | Useful for audit and disagreement trace. Submit as evidence or council detail, not as approved memory. |
| Votes / consensus | `graph/state.py`, `graph/nodes/voter.py` | Model votes and winning approach. | candidate | Should map into Council Resolution schema. |
| Cost summary | `llm/cost_tracker.py`, `graph/state.py`, `api/v1/sessions.py` | Token/cost aggregation by model and phase. | later | Aletheia may store evaluation/cost memory later. Not required for Phase 1 integration. |
| PostgreSQL checkpoint/store utilities | `db/postgres_utils.py` | LangGraph checkpoint/store setup and vector-capable Postgres store helper. | yes, for memory ownership | Existing helper name and behavior suggest memory/vector storage. Future durable memory/RAG ownership should migrate to Aletheia. Pantheon should only keep runtime checkpointing if needed. |
| User data deletion | `db/user_data.py` | Deletes Redis user keys, checkpoint rows, store/store_vectors rows, legacy memory. | yes, for memory governance | This is a strong signal that Pantheon currently has legacy memory/data ownership. Move governance/deletion semantics to Aletheia in later phases. |
| Redis session cache | `api/v1/sessions.py`, `api/v1/websocket.py` | Runtime status, final report cache, pub/sub. | no/partial | Keep transient cache in Pantheon. Durable memory belongs to Aletheia. Also note current websocket uses non-namespaced `session:{id}` while sessions.py uses `pantheon:session:{id}`; this should be reviewed separately. |
| User/project context | Not yet clearly centralized | Task/user_id only; no durable project context pack integration. | yes | Aletheia should provide project memory, active decisions, related files, risks, and required checks through Context Pack API. |
| Agent instructions | `AGENTS.md`, `CLAUDE.md` if present | Coding-agent rules and GitNexus requirements. | GitHub + Aletheia | Phase 1 should not directly modify these. See `PANTHEON_AGENT_INSTRUCTION_UPDATE_PROPOSAL.md`. |

## Current Pantheon boundary after Phase 1

Pantheon remains responsible for:

- Council orchestration and 5-phase reasoning.
- Multi-model research/debate/vote/synthesis.
- Runtime session state while a council is executing.
- Returning structured council outputs.

Pantheon should not be responsible for:

- Long-term memory store.
- Cross-project RAG and hybrid search.
- Memory promotion/governance.
- Notion/Obsidian/GitHub docs sync ownership.
- Agent-wide context gateway.

## Recommended Phase 2 tasks

1. Add optional Aletheia context-pack retrieval before graph execution.
2. Extend council input to include Aletheia-provided Context Pack without replacing existing task flow.
3. Submit Council Resolution, ADR candidate, and memory update candidates to Aletheia after synthesis.
4. Keep failure fallback: if Aletheia is unavailable, Pantheon runs the existing 5-phase workflow unchanged.
5. Review Redis namespace inconsistency between `api/v1/sessions.py` and `api/v1/websocket.py` before production use.
6. Decide whether PostgreSQL checkpointing remains runtime-only in Pantheon or migrates behind Aletheia-managed persistence.
