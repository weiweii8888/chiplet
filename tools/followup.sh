#!/usr/bin/env bash
# 2026-11-10 後續實驗，一次跑完（使用者關機前啟動）：
# 1 trace 轉檔與統計 → 2 catalog 補標 → 3 加入 KV 管理論文 → 4 抽數字＋驗證＋評測 → 5 新文件標籤檢討 → 6 總結
set -u
cd "$(dirname "$0")/.."
export CLAUDE_BIN="${CLAUDE_BIN:-$(ls -d ~/.vscode-server/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)}"
LOG="incoming/followup-$(date +%Y%m%d-%H%M).log"
mkdir -p incoming
exec > >(tee -a "$LOG") 2>&1
echo "== $(date '+%F %T') 1 trace 轉檔與統計"
python3 tools/trace_convert.py claude-code | tail -2
python3 tools/trace_convert.py codex | tail -2
python3 tools/trace_stats.py | tail -8
echo "== $(date '+%T') 2 catalog 補標（只用現有標籤）"
python3 tools/apply_tag_fill.py
python3 tools/check.py | tail -1
echo "== $(date '+%T') 3 加入 KV 管理論文"
python3 tools/add_arxiv_docs.py kv
NEW="$(cat incoming/added_docs.txt 2>/dev/null)"
echo "== $(date '+%T') 4 抽數字（A/B）、入庫、驗證、評測：$NEW"
if [ -n "$NEW" ]; then bash tools/pipeline.sh $NEW; fi
echo "== $(date '+%T') 5 新文件逐篇讀標籤、補標、彙整"
if [ -n "$NEW" ]; then python3 tools/tag_mine.py $NEW; fi
python3 tools/apply_tag_fill.py
python3 tools/tag_report.py
python3 tools/check.py --provenance | tail -2
echo "== $(date '+%T') 6 總結"
python3 tools/followup_summary.py "$LOG"
echo "== $(date '+%F %T') FOLLOWUP DONE"
