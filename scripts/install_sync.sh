#!/usr/bin/env bash
# install_sync.sh
# 一次性安裝：將 launchd agent 安裝到 Mac，啟動自動同步。
# 用法：bash scripts/install_sync.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.pantheon.notebooklm-sync.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.pantheon.notebooklm-sync.plist"
LABEL="com.pantheon.notebooklm-sync"

echo "=== Pantheon NotebookLM 自動同步安裝 ==="
echo "主目錄：$HOME"
echo "腳本路徑：$SCRIPT_DIR"

# 1. 替換 placeholder
sed "s|PLACEHOLDER_HOME|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"
echo "✅ plist 已寫入：$PLIST_DST"

# 2. 若已載入先卸載（避免重複）
if launchctl list | grep -q "$LABEL" 2>/dev/null; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  echo "   （已卸載舊版）"
fi

# 3. 載入 agent
launchctl load "$PLIST_DST"
echo "✅ launchd agent 已啟動（每 5 分鐘執行一次）"
echo ""
echo "查看執行日誌："
echo "  tail -f ~/.pantheon-sync.log"
echo ""
echo "停用自動同步："
echo "  launchctl unload ~/Library/LaunchAgents/com.pantheon.notebooklm-sync.plist"
