"""用 Claude Code 無頭模式（claude -p）從一份 PDF 抽數字，輸出 incoming/raw/<doc>-<run>.json。

同一份文件跑兩次（run A、B，彼此看不到對方的答案），再由 tools/reconcile.py 比對。
抽取用的指引在 tools/extract_prompt.md（等於這個專案的抽數字 skill）；Claude 只被允許用 Read，不能寫檔。

用法：python3 tools/extract.py PAPER-NN-BATON A
環境變數：CLAUDE_BIN（claude 執行檔路徑）、EXTRACT_MODEL（預設 claude-opus-5-5）
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
MODEL = os.environ.get("EXTRACT_MODEL", "claude-opus-5-5")


def pdf_for(doc_id):
    for p in sorted((ROOT / "pdfs").glob("*.pdf")):
        if doc_id.endswith(p.stem):
            return p
    sys.exit(f"找不到 {doc_id} 的 PDF")


def pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", out)
    return int(m.group(1)) if m else 0


def main():
    doc_id, run = sys.argv[1], sys.argv[2]
    pdf = pdf_for(doc_id)
    prompt = (ROOT / "tools/extract_prompt.md").read_text(encoding="utf-8").format(
        doc_id=doc_id, stem=pdf.stem, pages=pages(pdf))
    outdir = ROOT / "incoming/raw"
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    res = subprocess.run(
        [CLAUDE, "-p", prompt, "--model", MODEL, "--effort", "high",
         "--tools", "Read", "--allowedTools", "Read", "--permission-mode", "dontAsk",
         "--output-format", "json", "--no-session-persistence"],
        cwd=ROOT, capture_output=True, text=True, timeout=3600)
    (outdir / f"{doc_id}-{run}.cli.json").write_text(res.stdout or res.stderr, encoding="utf-8")
    try:
        meta = json.loads(res.stdout)
        text = meta.get("result", "")
    except json.JSONDecodeError:
        sys.exit(f"{doc_id}-{run}: claude 輸出不是 JSON：{(res.stderr or res.stdout)[:300]}")
    m = re.search(r"```json\s*(.*?)```", text, re.S)
    try:
        data = json.loads(m.group(1) if m else text)
    except (json.JSONDecodeError, AttributeError) as e:
        sys.exit(f"{doc_id}-{run}: 抽取結果解析失敗：{e}")
    data["_meta"] = {"model": MODEL, "run": run, "seconds": round(time.time() - t0),
                     "cost_usd": meta.get("total_cost_usd"), "turns": meta.get("num_turns")}
    (outdir / f"{doc_id}-{run}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{doc_id}-{run}: {len(data.get('rows', []))} rows, {len(data.get('leads', []))} leads, "
          f"{data['_meta']['seconds']}s, ${data['_meta']['cost_usd']}")


if __name__ == "__main__":
    main()
