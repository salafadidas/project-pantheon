# Day 7: Error Handling, Timeouts, and Logging

## Context
Building on Day 6's complete UI. Making the system production-resilient.

## Task

### 1. Create `utils/timeout.py`
Timeout utilities for LLM calls:
```python
PHASE_TIMEOUT_SECONDS = int(os.getenv("PHASE_TIMEOUT_SECONDS", "60"))

async def with_timeout(coro, timeout_seconds=PHASE_TIMEOUT_SECONDS, fallback=None):
    """Run coroutine with timeout, return fallback on timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds}s")
        return fallback
```

### 2. Update all graph nodes to use timeout
- `graph/nodes/researcher.py`: wrap each model call in `with_timeout()`
- `graph/nodes/debater.py`: wrap each model call in `with_timeout()`
- `graph/nodes/voter.py`: wrap each model call in `with_timeout()`
- `graph/nodes/synthesizer.py`: wrap synthesizer call in `with_timeout()`
- On timeout: use placeholder `"[Model timed out after 60s]"` as the response

### 3. Create `utils/logging_config.py`
Structured logging setup using structlog:
```python
import structlog

def configure_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

### 4. Add structured logging to all nodes
Each node should log:
- Phase start: `log.info("phase_start", phase=..., session_id=..., models=[...])`
- Model response: `log.info("model_response", phase=..., model=..., tokens=..., latency_ms=...)`
- Phase complete: `log.info("phase_complete", phase=..., session_id=..., duration_ms=...)`
- Errors: `log.error("model_error", phase=..., model=..., error=str(e))`

### 5. Create `utils/retry.py`
Retry logic for LLM API failures:
```python
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
RETRY_DELAY_SECONDS = float(os.getenv("LLM_RETRY_DELAY", "1.0"))

async def with_retry(coro_factory, max_retries=MAX_RETRIES, delay=RETRY_DELAY_SECONDS):
    """Retry a coroutine factory up to max_retries times on exception."""
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            if attempt == max_retries:
                raise
            logger.warning(f"Retry {attempt + 1}/{max_retries}: {e}")
            await asyncio.sleep(delay * (attempt + 1))
```

### 6. Create `utils/__init__.py` (empty)

### 7. Update `docs/PROJECT_PLAN.md` Day 7 status to "Done"

## Requirements
- Add `structlog` to requirements.txt
- All async
- Timeouts and retries should compose: `with_timeout(with_retry(...))`
- Log all LLM latencies for cost/performance analysis
- Never let a single model failure crash the entire phase
