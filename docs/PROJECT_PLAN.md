# Project Pantheon PoC - 10-Day Implementation Plan

> Forked from `francescofano/langgraph-telegram-bot`
> Target: Multi-AI-Agent Collaboration System with 5-Phase Workflow

## Overview

Build a multi-AI-agent collaboration system where multiple LLM providers (Claude, GPT, Gemini) work together through a structured 5-phase workflow:

1. **PM Router** - Classify task and select lead AI model
2. **Researcher** - Independent research by each AI agent
3. **Debater** - Multi-round structured debate between agents
4. **Voter** - Consensus voting on best approach
5. **Synthesizer** - Final report combining all perspectives

## Day-by-Day Plan

| Day | Task | Model | Status |
|-----|------|-------|--------|
| 1 | Fork repo, environment setup, docs | Haiku 4.5 | In Progress |
| 2 | LiteLLM multi-model provider + cost tracking | Sonnet 4.6 | Pending |
| 3 | LangGraph state expansion + debate node migration | Sonnet 4.6 | Done |
| 4 | PM router, researcher, voter, synthesizer nodes | Sonnet 4.6 | Done |
| 5 | Telegram bot commands + FastAPI REST/WebSocket | Sonnet 4.6 | Pending |
| 6 | React frontend fork + WebSocket integration | Sonnet 4.6 | Pending |
| 7 | Phase UI components (Timeline, Discussion, Cost) | Sonnet 4.6 | Pending |
| 8 | End-to-end integration testing (3 scenarios) | Haiku 4.5 | Pending |
| 9 | Error handling, timeouts, structured logging | Haiku 4.5 | Pending |
| 10 | Final validation, Docker Compose, demo prep | Haiku 4.5 | Pending |

## What's Already Included (from fork)

- FastAPI + LangGraph agent framework
- Telegram bot with message debouncing and rate limiting
- PostgreSQL (pgvector) + Redis
- Agent factory + manager with memory
- Docker Compose (prod + dev)
- Next.js frontend (basic dashboard)

## What Needs to Be Built

- 5 new agent modules (PM Router, Researcher, Debater, Voter, Synthesizer)
- LiteLLM integration for multi-model support
- Multi-phase LangGraph orchestrator
- Phase-aware UI components
- Cost tracking system
- FastAPI REST + WebSocket endpoints

## Execution Architecture

- **Local**: Claude Code runs all implementation
- **Mobile**: GitHub App for confirmations (checkpoint mechanism)
- **Dispatch**: For triggering tasks when away from computer

## Full Plan

See: `Project Pantheon_v1.5.md` in the project root directory.
