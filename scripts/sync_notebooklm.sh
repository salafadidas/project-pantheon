#!/usr/bin/env bash
# sync_notebooklm.sh
#
# 由 launchd 每 5 分鐘呼叫一次。
# 流程：git pull → 偵測 plan 版本是否變更 → 有變更則自動上傳到 NotebookLM。
#
# 一次性安裝（在 Mac 執行）：
#   cp /Users/$(whoami)/project-pantheon/scripts/com.pantheon.notebooklm-sync.plist \
#      ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.pantheon.notebooklm-sync.plist

set -euo pipefail

# ── 路徑設定 ─────────────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="$HOME/.pantheon-last-uploaded-plan"
LOG_FILE="$HOME/.pantheon-sync.log"
BRANCH="claude/remote-control-Q2YAQ"

# 確保 node 可找到（涵蓋 Intel 及 Apple Silicon homebrew 路徑）
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# ── 日誌函式 ──────────────────────────────────────────────────────────────────
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# ── 主流程 ───────────────────────────────────────────────────────────────────
cd "$PROJECT_DIR"

log "--- sync start ---"

# 1. git pull
git fetch origin "$BRANCH" >> "$LOG_FILE" 2>&1
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")
if [ "$LOCAL" != "$REMOTE" ]; then
  log "New commits detected, pulling..."
  git pull origin "$BRANCH" >> "$LOG_FILE" 2>&1
else
  log "No new commits."
fi

# 2. 找最新 plan 版本
CURRENT_PLAN=$(ls "$PROJECT_DIR/docs/PROJECT_PLAN_v"*.md 2>/dev/null \
  | sort -t v -k2 -V | tail -1)

if [ -z "$CURRENT_PLAN" ]; then
  log "No plan file found, skipping."
  exit 0
fi

PLAN_VERSION=$(basename "$CURRENT_PLAN")

# 3. 比對上次已上傳版本
LAST_UPLOADED=$(cat "$STATE_FILE" 2>/dev/null || echo "")

if [ "$PLAN_VERSION" = "$LAST_UPLOADED" ]; then
  log "Plan unchanged ($PLAN_VERSION), skipping upload."
  exit 0
fi

log "New plan detected: $PLAN_VERSION (previous: ${LAST_UPLOADED:-none})"
log "Starting NotebookLM upload..."

# 4. 上傳（headless 模式）
if node "$PROJECT_DIR/scripts/upload_notebooklm.mjs" --headless >> "$LOG_FILE" 2>&1; then
  echo "$PLAN_VERSION" > "$STATE_FILE"
  log "Upload successful: $PLAN_VERSION"
else
  log "Upload FAILED (exit $?). Will retry next cycle."
fi

log "--- sync end ---"
