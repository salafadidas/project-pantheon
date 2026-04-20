#!/usr/bin/env bash
# check_new_commits.sh
#
# 由 launchd 每 60 秒呼叫一次（輕量）。
# 只做 git fetch，發現新 commit 才寫 flag 檔觸發 upload agent。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="claude/remote-control-Q2YAQ"
FLAG_FILE="$HOME/.pantheon-new-commit-flag"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$PROJECT_DIR"

git fetch origin "$BRANCH" --quiet 2>/dev/null || exit 0

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null)

if [ "$LOCAL" != "$REMOTE" ]; then
  # 有新 commit：寫 flag 檔觸發 upload agent（WatchPaths）
  date '+%Y-%m-%dT%H:%M:%S' > "$FLAG_FILE"
fi
