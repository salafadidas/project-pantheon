# Day 6: React Frontend - Phase Timeline + Discussion Thread

## Context
Building on Day 5's API/WebSocket endpoints and Telegram integration.
The existing `frontend/` directory has a React app with WebSocket support.

## Task

### 1. Create `frontend/src/components/PhaseTimeline.tsx`
5-phase progress bar component:
- Shows phases: Routing → Research → Debate → Voting → Synthesis
- Highlights current active phase with animation
- Marks completed phases with a checkmark
- Shows elapsed time per phase
- Props: `currentPhase: string`, `completedPhases: string[]`, `phaseTimes: Record<string, number>`

### 2. Create `frontend/src/components/DiscussionThread.tsx`
Multi-agent conversation display:
- Each message bubble shows: model name badge (Claude/GPT/Gemini), content, timestamp, phase label
- Color-code by model: Claude = purple, GPT = green, Gemini = blue
- Support debate round indicators (Round 1, Round 2, etc.)
- Show research results section before debate begins
- Show voting summary after debate completes
- Props: `debateHistory: DebateEntry[]`, `researchResults: Record<string, string>`, `votes: Record<string, string>`

### 3. Create `frontend/src/components/CostMonitor.tsx`
Real-time cost display panel:
- Shows total tokens used and estimated cost per model
- Updates live via WebSocket events
- Shows cost breakdown table: Model | Input Tokens | Output Tokens | Cost ($)
- Shows total session cost
- Props: `costSummary: CostSummary`

### 4. Create `frontend/src/components/TaskSubmit.tsx`
Task submission form:
- Textarea for task description
- Submit button that calls `POST /api/v1/sessions` then `POST /api/v1/sessions/{id}/start`
- Shows session_id after submission
- Redirects to session view on success

### 5. Update `frontend/src/App.tsx`
Add routing for:
- `/` — TaskSubmit form
- `/session/:id` — PhaseTimeline + DiscussionThread + CostMonitor (connected via WebSocket)

### 6. Create `frontend/src/hooks/useSession.ts`
Custom hook for session WebSocket management:
- Connects to `WS /api/v1/sessions/{id}/stream`
- Maintains state: `phase`, `debateHistory`, `researchResults`, `votes`, `finalReport`, `costSummary`
- Auto-reconnect on disconnect
- Returns: `{ phase, debateHistory, researchResults, votes, finalReport, costSummary, isConnected }`

### 7. Update `docs/PROJECT_PLAN.md` Day 6 status to "Done"

## Requirements
- TypeScript strict mode
- Use existing WebSocket hook pattern from the codebase
- Tailwind CSS for styling (if already configured, otherwise use plain CSS modules)
- Mobile-responsive layout
- Loading states and error boundaries
