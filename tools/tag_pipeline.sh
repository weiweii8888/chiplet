#!/usr/bin/env bash
# 標籤檢討：逐篇讀 PDF 提案（tag_mine.py）→ 彙整三個來源（tag_report.py）
set -u
cd "$(dirname "$0")/.."
export CLAUDE_BIN="${CLAUDE_BIN:-$(ls -d ~/.vscode-server/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)}"
LOG="schema/tag_mining/run-$(date +%Y%m%d-%H%M).log"
mkdir -p schema/tag_mining
{
  echo "== $(date '+%F %T') 逐篇讀 PDF 提案標籤"
  python3 tools/tag_mine.py "$@"
  echo "== $(date '+%T') 彙整"
  python3 tools/tag_report.py
  echo "== $(date '+%F %T') TAG PIPELINE DONE"
} 2>&1 | tee -a "$LOG"
