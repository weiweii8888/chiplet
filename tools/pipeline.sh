#!/usr/bin/env bash
# 一次跑完：抽取（每篇 A、B 兩次獨立）→ 比對與驗證後入庫 → 全庫驗證 → 評測
# 用法：tmux new -s chiplet 'bash tools/pipeline.sh PAPER-NN-BATON PAPER-MONAD ...'
set -u
cd "$(dirname "$0")/.."
export CLAUDE_BIN="${CLAUDE_BIN:-$(ls -d ~/.vscode-server/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)}"
DOCS="${*:-PAPER-NN-BATON PAPER-MONAD PAPER-EXPERT-STREAMING}"
mkdir -p incoming
LOG="incoming/pipeline-$(date +%Y%m%d-%H%M).log"
exec > >(tee -a "$LOG") 2>&1
echo "== $(date '+%F %T') 開始；文件：$DOCS；claude=$CLAUDE_BIN"

for RUN in A B; do
  echo "== $(date '+%T') 抽取 run $RUN（三篇平行）"
  PIDS=()
  for D in $DOCS; do
    if [ -s "incoming/raw/$D-$RUN.json" ]; then echo "$D-$RUN: 已有結果，略過"; continue; fi
    # 最多同時跑 MAXJ 篇（預設 4），避免撞到速率限制
    if [ ${#PIDS[@]} -ge "${MAXJ:-4}" ]; then wait "${PIDS[0]}"; PIDS=("${PIDS[@]:1}"); fi
    python3 tools/extract.py "$D" "$RUN" & PIDS+=($!)
  done
  # 只等抽取程序；不帶參數的 wait 會連 tee（日誌）一起等而卡住
  for P in "${PIDS[@]}"; do wait "$P"; done
done

echo "== $(date '+%T') 比對、驗證、入庫"
for D in $DOCS; do python3 tools/reconcile.py "$D"; done

echo "== $(date '+%T') 全庫驗證（含出處）"
python3 tools/check.py --provenance | tail -20

echo "== $(date '+%T') 評測（retrieval＋agent）"
python3 eval/run_eval.py

echo "== $(date '+%F %T') PIPELINE DONE"
