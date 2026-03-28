# Day 5: Telegram Bot Integration + FastAPI Endpoints

## Context
Building on Day 4's complete LangGraph (pm_router → researcher → debater → voter → synthesizer).

## Task

### 1. Update `bot/telegram_handler.py`
Extend the existing Telegram handler to support the 5-phase Pantheon flow:
- `/submit <task>` — Start a new Pantheon session, returns session_id
- `/status <session_id>` — Check current phase of a running session
- `/report <session_id>` — Get the final_report for a completed session
- `/cancel <session_id>` — Cancel a running session
- Phase progress updates: send Telegram message when each phase starts/completes
- Use PantheonState.session_id and PantheonState.phase for status tracking

### 2. Create `api/v1/sessions.py`
FastAPI router for session management:
```python
POST   /api/v1/sessions              # Create new session, return session_id
POST   /api/v1/sessions/{id}/start   # Start execution with task payload
GET    /api/v1/sessions/{id}/status  # Get current phase + progress
GET    /api/v1/sessions/{id}/report  # Get final_report (404 if not complete)
DELETE /api/v1/sessions/{id}         # Cancel session
```

### 3. Create `api/v1/websocket.py`
WebSocket endpoint for real-time phase streaming:
- `WS /api/v1/sessions/{id}/stream`
- Emit events: `{"event": "phase_start", "phase": "research", "timestamp": "..."}`
- Emit events: `{"event": "phase_complete", "phase": "research", "data": {...}}`
- Emit events: `{"event": "model_response", "model": "gpt-4o", "content": "..."}`
- Emit events: `{"event": "session_complete", "final_report": "..."}`
- Disconnect on session completion or cancellation

### 4. Create `api/__init__.py` and `api/v1/__init__.py` (empty)

### 5. Update `main.py`
Register the new API routers:
```python
from api.v1.sessions import router as sessions_router
from api.v1.websocket import router as ws_router
app.include_router(sessions_router)
app.include_router(ws_router)
```

### 6. Update `docs/PROJECT_PLAN.md` Day 5 status to "Done"

## Requirements
- All async
- Session state stored in Redis (key: `session:{id}`, TTL: 24 hours)
- Phase events published to Redis pub/sub channel: `session:{id}:events`
- WebSocket subscribes to Redis pub/sub for real-time streaming
- Telegram handler subscribes to Redis pub/sub to send phase notifications
- Error handling: return 404 if session not found, 409 if session already running
