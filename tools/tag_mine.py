"""由文獻提出標籤候選：讓 Claude（只能讀檔）逐篇讀 PDF，回答「現有標籤夠不夠、該加什麼」。

用法：python3 tools/tag_mine.py PAPER-SIMBA [更多 doc_id…]，不給 doc_id 就跑所有有 PDF 的文件
輸出：schema/tag_mining/<doc_id>.json（已存在就略過；要重跑先刪檔）
彙整：python3 tools/tag_report.py
"""
import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
MODEL = os.environ.get("TAG_MODEL", "claude-opus-5-5")
OUT = ROOT / "schema/tag_mining"


def pdf_for(doc_id):
    for p in sorted((ROOT / "pdfs").glob("*.pdf")):
        if doc_id.endswith(p.stem):
            return p
    return None


def run(doc):
    out = OUT / f"{doc['doc_id']}.json"
    if out.exists():
        return f"{doc['doc_id']}: 已有結果，略過"
    pdf = pdf_for(doc["doc_id"])
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    pages = re.search(r"Pages:\s+(\d+)", info).group(1)
    prompt = (ROOT / "tools/tag_mine_prompt.md").read_text(encoding="utf-8").format(
        doc_id=doc["doc_id"], title=doc["title"], stem=pdf.stem, pages=pages)
    res = subprocess.run([CLAUDE, "-p", prompt, "--model", MODEL, "--effort", "high", "--tools", "Read",
                          "--allowedTools", "Read", "--permission-mode", "dontAsk", "--output-format", "json",
                          "--no-session-persistence"], cwd=ROOT, capture_output=True, text=True, timeout=3600)
    try:
        meta = json.loads(res.stdout)
        m = re.search(r"```json\s*(.*?)```", meta.get("result", ""), re.S)
        data = json.loads(m.group(1) if m else meta["result"])
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        return f"{doc['doc_id']}: 失敗 {e}"
    data["_meta"] = {"model": MODEL, "cost_usd": meta.get("total_cost_usd"), "turns": meta.get("num_turns")}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return (f"{doc['doc_id']}: {len(data.get('decisions', []))} 個決策、{len(data.get('proposed_tags', []))} 個新標籤提案、"
            f"${meta.get('total_cost_usd') or 0:.2f}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "catalog.csv", newline="", encoding="utf-8") as f:
        # 案例卡（type=case）沒有自己的 PDF；檔名比對會誤配到來源白皮書，所以跳過
        docs = [r for r in csv.DictReader(f) if r["type"] != "case" and pdf_for(r["doc_id"])]
    if len(sys.argv) > 1:
        docs = [d for d in docs if d["doc_id"] in sys.argv[1:]]
    with ThreadPoolExecutor(int(os.environ.get("TAG_WORKERS", "4"))) as ex:
        for msg in ex.map(run, docs):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
