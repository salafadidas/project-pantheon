#!/usr/bin/env bash
# sync_catalog_to_nlm.sh
#
# 每次 llm/model_catalog.py 有定價或模型異動並更新 docs/MODEL_CATALOG_CHANGELOG.md 後執行此腳本。
# 自動刪除 NotebookLM 中的舊 changelog source，並上傳最新版本。
#
# 使用方式：
#   cd /Users/vernon/Projects/project-pantheon
#   bash scripts/sync_catalog_to_nlm.sh
#
# 前提條件：nlm CLI 已安裝並完成 `nlm login`

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CHANGELOG="$PROJECT_DIR/docs/MODEL_CATALOG_CHANGELOG.md"
NOTEBOOK_ID="d5748a18-ff1a-4eae-b8dc-f4d07028c652"   # Project Pantheon（萬神殿計畫）— owned
SOURCE_TITLE="Model Catalog Changelog"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚  Project Pantheon — NotebookLM Catalog Sync"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 0. Sanity checks ────────────────────────────────────────────────────────
if [[ ! -f "$CHANGELOG" ]]; then
  echo "❌  Changelog not found: $CHANGELOG"
  exit 1
fi

if ! command -v nlm &>/dev/null; then
  echo "❌  nlm CLI not found. Install via: pip install notebooklm-tools"
  exit 1
fi

# ── 1. Find existing changelog source(s) in the notebook ───────────────────
echo "🔍  Scanning notebook for existing changelog sources..."

EXISTING_IDS=$(nlm source list "$NOTEBOOK_ID" --json 2>/dev/null \
  | python3 -c "
import sys, json
sources = json.load(sys.stdin)
ids = [s['id'] for s in sources if 'Catalog Changelog' in s.get('title', '')]
print(' '.join(ids))
" 2>/dev/null || true)

# ── 2. Delete old source(s) if found ───────────────────────────────────────
if [[ -n "$EXISTING_IDS" ]]; then
  echo "🗑️   Deleting old source(s): $EXISTING_IDS"
  # shellcheck disable=SC2086
  nlm source delete $EXISTING_IDS --confirm
  echo "    Deleted."
else
  echo "ℹ️   No existing changelog source found — will add fresh."
fi

# ── 3. Upload updated changelog ─────────────────────────────────────────────
echo "📤  Uploading: $CHANGELOG"
nlm source add "$NOTEBOOK_ID" \
  --file "$CHANGELOG" \
  --title "$SOURCE_TITLE" \
  --wait

echo ""
echo "✅  Sync complete!"
echo "    Notebook : $NOTEBOOK_ID"
echo "    Source   : \"$SOURCE_TITLE\""
echo "    File     : $CHANGELOG"
echo "    View at  : https://notebooklm.google.com/notebook/$NOTEBOOK_ID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
