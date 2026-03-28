# Day 8: Unit Tests + Integration Tests

## Context
Building on Day 7's resilient system. Adding comprehensive test coverage (target: 80%+).

## Task

### 1. Create `tests/unit/test_state.py`
Test PantheonState:
- Test all fields are present and have correct types
- Test phase transitions are valid Literal values
- Test immutable state update pattern (return new dict, don't mutate)

### 2. Create `tests/unit/test_pm_router.py`
Test pm_router node:
- Mock LLMProvider, test task classification (technical/creative/analytical/factual)
- Test that pm_model is set in returned state
- Test that phase transitions to "research"
- Test error handling when LLM fails

### 3. Create `tests/unit/test_researcher.py`
Test researcher node:
- Mock LLMProvider, test concurrent research with asyncio.gather
- Test that research_results contains entry for each debate_model
- Test timeout handling: verify placeholder used when model times out
- Test that failed models don't crash other models

### 4. Create `tests/unit/test_debater.py`
Test debater node:
- Mock LLMProvider
- Test that debate_history is appended (not mutated)
- Test debate_round increments
- Test each model gets previous debate history as context
- Test max debate rounds respected

### 5. Create `tests/unit/test_voter.py`
Test voter node:
- Mock LLMProvider
- Test votes dict populated for each model
- Test consensus calculation (majority vote logic)
- Test tie-breaking behavior

### 6. Create `tests/unit/test_synthesizer.py`
Test synthesizer node:
- Mock LLMProvider
- Test final_report is set
- Test phase transitions to "complete"
- Test report contains required sections (summary, insights, consensus, dissenting views, cost breakdown)

### 7. Create `tests/unit/test_cost_tracker.py`
Test CostTracker:
- Test token counting
- Test cost calculation per model
- Test total cost aggregation
- Test cost_summary format

### 8. Create `tests/integration/test_graph_flow.py`
Integration test for the full LangGraph flow:
- Mock all LLM calls
- Submit a task and run the full graph
- Verify state transitions: routing → research → debate → voting → synthesis → complete
- Verify final_report is populated
- Verify cost_summary is populated

### 9. Create `tests/conftest.py`
Shared pytest fixtures:
- `mock_llm_provider`: LLMProvider with mocked responses
- `sample_pantheon_state`: Valid initial PantheonState
- `sample_debate_history`: Pre-populated debate entries

### 10. Update `docs/PROJECT_PLAN.md` Day 8 status to "Done"

## Requirements
- pytest + pytest-asyncio for async tests
- Use `unittest.mock.AsyncMock` for async LLM calls
- Run: `pytest tests/ -v --cov=graph --cov=llm --cov-report=term-missing`
- Target: 80%+ coverage on graph/nodes/ and llm/
- Add `pytest`, `pytest-asyncio`, `pytest-cov` to requirements.txt
