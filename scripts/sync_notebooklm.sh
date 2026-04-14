#!/usr/bin/env bash
# sync_notebooklm.sh
#
# 由 launchd WatchPaths 觸發（flag 檔變動時執行）。
# 流程：git pull → 偵測 plan 版本是否變更 → 有變更則自動上傳到 NotebookLM。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="$HOME/.pantheon-last-uploaded-plan"
LOG_FILE="$HOME/.pantheon-sync.log"
BRANCH="claude/remote-control-Q2YAQ"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

cd "$PROJECT_DIR"

log "--- sync triggered ---"

# 1. git pull
log "Pulling latest commits..."
git pull origin "$BRANCH" >> "$LOG_FILE" 2>&1

# 2. 找最新 plan 版本
CURRENT_PLAN=$(ls "$PROJECT_DIR/docs/PROJECT_PLAN_v"*.md 2>/dev/null \
  | sort -t v -k2 -V | tail -1)

if [ -z "$CURRENT_PLAN" ]; then
  log "No plan file found, skipping."
  exit 0
fi

PLAN_VERSION=$(basename "$CURRENT_PLAN")

# 3. 比對上次已上傳版本（即 NotebookLM 上的現有版本）
LAST_UPLOADED=$(cat "$STATE_FILE" 2>/dev/null || echo "")
OLD_LABEL="${LAST_UPLOADED:-（無）}"

if [ "$PLAN_VERSION" = "$LAST_UPLOADED" ]; then
  log "Plan unchanged ($PLAN_VERSION), skipping upload."
  exit 0
fi

# ── 版本比較報告 ──────────────────────────────────────────────────────────────
OLD_VER=$(echo "$OLD_LABEL"    | grep -oE 'v[0-9]+\.[0-9]+' || echo "$OLD_LABEL")
NEW_VER=$(echo "$PLAN_VERSION" | grep -oE 'v[0-9]+\.[0-9]+' || echo "$PLAN_VERSION")

log "版本變更偵測："
log "  NotebookLM 現有版本：$OLD_VER  ($OLD_LABEL)"
log "  本地最新版本　　　：$NEW_VER  ($PLAN_VERSION)"
log "  → 開始上傳..."

# 4. 上傳（headless 模式）
UPLOAD_LOG=$(node "$PROJECT_DIR/scripts/upload_notebooklm.mjs" --headless 2>&1)
UPLOAD_EXIT=$?
echo "$UPLOAD_LOG" >> "$LOG_FILE"

if [ $UPLOAD_EXIT -eq 0 ]; then
  echo "$PLAN_VERSION" > "$STATE_FILE"

  REPORT="NotebookLM 已更新：$OLD_VER → $NEW_VER"
  log "✅ $REPORT"
  log "   上傳檔案：$PLAN_VERSION"
  log "   帳號：salafadidas@gmail.com"

  osascript -e "display notification \"$OLD_VER → $NEW_VER\" with title \"Project Pantheon — NotebookLM 已更新\" sound name \"Glass\"" 2>/dev/null || true
else
  log "❌ 上傳失敗（exit $UPLOAD_EXIT）。下次偵測到新 commit 時將重試。"
  osascript -e "display notification \"上傳失敗，請查看 ~/.pantheon-sync.log\" with title \"Project Pantheon — NotebookLM 同步錯誤\" sound name \"Basso\"" 2>/dev/null || true
fi

log "--- sync end ---"
