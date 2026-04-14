#!/usr/bin/env bash
# install_sync.sh
# 一次性安裝：兩個 launchd agent（git-fetch + notebooklm-sync）。
# 用法：bash scripts/install_sync.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
FLAG_FILE="$HOME/.pantheon-new-commit-flag"

install_agent() {
  local NAME="$1"
  local SRC="$SCRIPT_DIR/${NAME}.plist"
  local DST="$AGENTS_DIR/${NAME}.plist"

  sed "s|PLACEHOLDER_HOME|$HOME|g" "$SRC" > "$DST"

  # 若已載入先卸載
  launchctl list | grep -q "$NAME" 2>/dev/null && \
    launchctl unload "$DST" 2>/dev/null || true

  launchctl load "$DST"
  echo "  ✅ $NAME 已啟動"
}

echo "=== Pantheon NotebookLM 自動同步安裝 ==="
echo "主目錄：$HOME"
echo "腳本路徑：$SCRIPT_DIR"
echo ""

# 建立 flag 檔（WatchPaths 需要路徑存在）
touch "$FLAG_FILE"

echo "安裝 agent..."
install_agent "com.pantheon.git-fetch"
install_agent "com.pantheon.notebooklm-sync"

echo ""
echo "完成！架構："
echo "  com.pantheon.git-fetch       — 每 60 秒 git fetch，偵測新 commit"
echo "  com.pantheon.notebooklm-sync — 有新 commit 時自動 pull + 上傳"
echo ""
echo "查看執行日誌："
echo "  tail -f ~/.pantheon-sync.log"
echo ""
echo "停用："
echo "  launchctl unload ~/Library/LaunchAgents/com.pantheon.git-fetch.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.pantheon.notebooklm-sync.plist"
