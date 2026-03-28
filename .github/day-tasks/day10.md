# Day 10: PoC Final Validation + CI/CD Setup

## Context
Final day of the 10-day PoC. Complete validation, CI pipeline, and handover documentation.

## Task

### 1. Create `.github/workflows/ci.yml`
CI pipeline that runs on every push to main and PRs:
```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: ankane/pgvector:latest
        env:
          POSTGRES_USER: langbotuser
          POSTGRES_PASSWORD: yourpassword
          POSTGRES_DB: langbotdb
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7.2-alpine
        ports: ["6379:6379"]
        options: --health-cmd "redis-cli ping" --health-interval 5s --health-timeout 3s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=graph --cov=llm --cov-report=xml
        env:
          PG_CONNECTION_STRING: postgresql://langbotuser:yourpassword@localhost:5432/langbotdb
          REDIS_URL: redis://localhost:6379/0
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
      - uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

### 2. Create `docs/DEMO_SCRIPT.md`
PoC demo walkthrough document:
- Three demo scenarios (technical, creative, analytical tasks)
- Expected output for each phase
- Screenshots placeholders
- Talking points for each phase

### 3. Create `docs/HANDOVER.md`
Technical handover document for production phase:
- What was built (summary of Days 1-10)
- Architecture decisions and rationale
- Known limitations and technical debt
- Recommended next steps for production (Day 11-30)
- Environment variables reference
- Troubleshooting guide (top 5 common issues)

### 4. Final acceptance checklist
Verify all PoC acceptance criteria:
- [ ] Complete 5-phase flow executes (3 models: Claude + GPT + Gemini)
- [ ] Telegram: submit task, receive final report
- [ ] Web UI: real-time phase display + discussion thread
- [ ] PostgreSQL persistence working
- [ ] Cost tracking showing per-model breakdown
- [ ] docker-compose up starts cleanly
- [ ] Phase timeout protection (60s per model)
- [ ] Unit tests passing (80%+ coverage)
- [ ] CI pipeline passing

### 5. Update `docs/PROJECT_PLAN.md`
- Mark Day 10 as "Done"
- Add PoC completion date
- Add summary: "PoC COMPLETE — All 10 days implemented"
- Add "Next Phase" section pointing to production roadmap

### 6. Create git tag for PoC completion
After all changes committed:
```bash
git tag -a v0.1.0-poc -m "PoC complete: 5-phase multi-agent system operational"
git push origin v0.1.0-poc
```

## Requirements
- CI must pass on clean Ubuntu runner (no local deps)
- All Day 1-10 implementations must be importable without errors
- README Quick Start must work end-to-end
- HANDOVER.md must be comprehensive enough for a new developer to continue
