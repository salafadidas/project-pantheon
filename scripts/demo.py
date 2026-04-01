#!/usr/bin/env python3
"""Project Pantheon — standalone end-to-end demo script.

Runs the full 5-phase multi-agent workflow directly (no Telegram, no HTTP server)
and prints live phase updates to the terminal.

Usage::

    # Basic (uses default task)
    python scripts/demo.py

    # Custom task
    python scripts/demo.py --task "Compare PostgreSQL and MongoDB for a social network"

    # Quiet mode (final report only)
    python scripts/demo.py --quiet

    # JSON output (for piping)
    python scripts/demo.py --json

Prerequisites:
    - .env file with OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
    - pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run from any directory
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

# ---------------------------------------------------------------------------
# Imports (after path + env setup)
# ---------------------------------------------------------------------------
from graph.pantheon_graph import pantheon_graph

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TASK = (
    "What are the key trade-offs between REST and GraphQL APIs "
    "for a high-traffic mobile application?"
)

PHASE_LABELS: dict[str, str] = {
    "routing":   "🧭  PM Router   ",
    "research":  "🔬  Researcher  ",
    "debate":    "💬  Debater     ",
    "voting":    "🗳️  Voter       ",
    "synthesis": "📝  Synthesizer ",
    "complete":  "✅  Complete    ",
}

SEPARATOR = "─" * 70


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _phase_label(phase: str) -> str:
    return PHASE_LABELS.get(phase, f"   {phase:<12}")


def _fmt_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s // 60)}m {s % 60:.0f}s"


def _print_header(task: str) -> None:
    print()
    print(SEPARATOR)
    print("  Project Pantheon — Multi-Agent Demo")
    print(SEPARATOR)
    print(f"  Task : {task[:65]}{'…' if len(task) > 65 else ''}")
    print(f"  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEPARATOR)
    print()


def _print_phase_start(phase: str) -> None:
    print(f"  {_phase_label(phase)}  ⟶  running…", flush=True)


def _print_phase_done(phase: str, elapsed: float, summary: str = "") -> None:
    suffix = f"  ({summary})" if summary else ""
    print(f"  {_phase_label(phase)}  ✓  {_fmt_seconds(elapsed)}{suffix}")


def _print_final_report(report: str) -> None:
    print()
    print(SEPARATOR)
    print("  FINAL REPORT")
    print(SEPARATOR)
    # Word-wrap at 68 chars
    words = report.split()
    line = "  "
    for word in words:
        if len(line) + len(word) + 1 > 70:
            print(line)
            line = "  " + word
        else:
            line += (" " if line.strip() else "") + word
    if line.strip():
        print(line)
    print(SEPARATOR)
    print()


def _print_cost(cost_summary: dict) -> None:
    total = cost_summary.get("total_cost_usd", 0)
    print(f"  💰  Total cost : ${total:.4f} USD")
    by_model = cost_summary.get("by_model", {})
    for model, cost in by_model.items():
        print(f"       {model:<28} ${cost:.4f}")
    print()


# ---------------------------------------------------------------------------
# Core demo runner
# ---------------------------------------------------------------------------

async def run_demo(task: str, quiet: bool, as_json: bool) -> dict:
    """Run the Pantheon graph and return the final state dict."""
    session_id = f"demo-{int(time.time())}"

    initial_state = {
        "task": task,
        "session_id": session_id,
        "user_id": "demo",
        "phase": "routing",
        "pm_model": "gpt-4o-mini",
        "debate_round": 0,
        "research_results": {},
        "debate_history": [],
        "votes": {},
        "consensus": None,
        "final_report": None,
        "cost_summary": {},
        "messages": [],
    }

    if not quiet and not as_json:
        _print_header(task)

    phase_times: dict[str, float] = {}
    final_state: dict = {}
    t_global = time.monotonic()

    async for chunk in pantheon_graph.astream(initial_state):
        for node_name, state_update in chunk.items():
            phase = state_update.get("phase", node_name)
            elapsed = time.monotonic() - t_global
            phase_times[node_name] = elapsed

            if not quiet and not as_json:
                # Build a short summary line per phase
                summary = ""
                if node_name == "researcher":
                    n = len(state_update.get("research_results", {}))
                    summary = f"{n} model(s) responded"
                elif node_name == "debater":
                    rnd = state_update.get("debate_round", "?")
                    summary = f"round {rnd}"
                elif node_name == "voter":
                    consensus = state_update.get("consensus") or "no consensus"
                    summary = f"consensus: {consensus[:40]}"
                elif node_name == "synthesizer":
                    report_len = len(state_update.get("final_report") or "")
                    summary = f"{report_len} chars"

                _print_phase_done(phase, elapsed, summary)

            final_state = state_update

    total_elapsed = time.monotonic() - t_global
    final_report = final_state.get("final_report") or "(no report generated)"
    cost_summary = final_state.get("cost_summary") or {}

    if as_json:
        output = {
            "session_id": session_id,
            "task": task,
            "phase_times": {k: round(v, 2) for k, v in phase_times.items()},
            "total_seconds": round(total_elapsed, 2),
            "final_report": final_report,
            "votes": final_state.get("votes", {}),
            "consensus": final_state.get("consensus"),
            "cost_summary": cost_summary,
        }
        print(json.dumps(output, indent=2))
        return output

    if not quiet:
        _print_final_report(final_report)
        _print_cost(cost_summary)
        print(f"  ⏱  Total time : {_fmt_seconds(total_elapsed)}")
        print()
    else:
        print(final_report)

    return final_state


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Project Pantheon — end-to-end multi-agent demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--task", "-t",
        default=DEFAULT_TASK,
        help="Task to submit to the multi-agent system (default: built-in example)",
    )
    p.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Print only the final report (no progress output)",
    )
    p.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output result as JSON (implies --quiet)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # Validate API keys
    missing = [
        k for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")
        if not os.getenv(k)
    ]
    if missing and not args.as_json:
        print(f"⚠️  Warning: missing env vars: {', '.join(missing)}", file=sys.stderr)
        print("   Some models may fail. Set keys in .env or export them.", file=sys.stderr)
        print()

    try:
        asyncio.run(run_demo(args.task, quiet=args.quiet, as_json=args.as_json))
    except KeyboardInterrupt:
        print("\n  Demo interrupted.")
        sys.exit(0)
    except Exception as exc:
        print(f"\n  ❌ Demo failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
