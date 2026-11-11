"""把 followup.sh 各步驟的結果整理成一份 FOLLOWUP-<日期>.md（給下次開機時看）。

用法：python3 tools/followup_summary.py <followup 日誌路徑>
"""
import csv
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def latest(pattern):
    xs = sorted(ROOT.glob(pattern))
    return xs[-1] if xs else None


def section(path, start, stop=None, limit=40):
    if not path or not path.exists():
        return ["（沒有產出）"]
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        i = next(k for k, x in enumerate(lines) if x.startswith(start))
    except StopIteration:
        return lines[:limit]
    out = []
    for x in lines[i + 1:]:
        if stop and x.startswith(stop):
            break
        out.append(x)
    return out[:limit]


def main():
    log = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    added = (ROOT / "incoming/added_docs.txt").read_text(encoding="utf-8").split() if (ROOT / "incoming/added_docs.txt").exists() else []
    with open(ROOT / "catalog.csv", newline="", encoding="utf-8") as f:
        cat = {r["doc_id"]: r for r in csv.DictReader(f)}
    cost = 0.0
    for d in added:
        for run in "AB":
            p = ROOT / f"incoming/raw/{d}-{run}.json"
            if p.exists():
                cost += json.loads(p.read_text(encoding="utf-8")).get("_meta", {}).get("cost_usd") or 0
        p = ROOT / f"schema/tag_mining/{d}.json"
        if p.exists():
            cost += json.loads(p.read_text(encoding="utf-8")).get("_meta", {}).get("cost_usd") or 0
    ev = latest("eval/results/*.md")
    ev_lines = ev.read_text(encoding="utf-8").splitlines()[:6] if ev else []
    m = re.search(r"\$([\d.]+)", " ".join(ev_lines))
    cost += float(m.group(1)) if m else 0
    chk = subprocess.run([sys.executable, str(ROOT / "tools/check.py")], capture_output=True, text=True).stdout.splitlines()

    L = [f"# 後續實驗總結 {datetime.date.today()}", "",
         "由 `tools/followup.sh` 在 tmux 自動跑完。完整日誌：" + (f"`{log.resolve().relative_to(ROOT)}`" if log else "—"), "",
         f"本批費用約 ${cost:.2f}（抽取 A/B、逐篇讀標籤、agent 評測）。", "",
         "## 1. 學弟 A：trace 轉檔與統計", ""]
    st = latest("traces/stats/*.md")
    L += (st.read_text(encoding="utf-8").splitlines()[2:8] if st else ["（沒有產出）"]) + [""]
    L += ["### 和知識庫對照", ""] + section(st, "## 和知識庫對照", "## 由下而上") + [""]
    L += ["## 2. catalog 補標（只用現有標籤）", ""]
    fl = ROOT / "schema/tag_mining/fill-log.md"
    L += (fl.read_text(encoding="utf-8").splitlines()[-40:] if fl.exists() else ["（沒有產出）"]) + [""]
    L += ["## 3. 新收的 KV 管理論文", ""]
    for d in added:
        r = cat.get(d, {})
        L.append(f"- `{d}` [{r.get('status', '')}]：{r.get('title', '')}（{r.get('year', '')}）— {r.get('summary', '')}")
    if not added:
        L.append("- 沒有加入（看日誌的 arXiv 錯誤訊息）")
    L += ["", "### 抽數字結果（A/B 兩次獨立抽取）", "",
          "| 文件 | A | B | 一致 | 入庫 | 待人看 | 線索 | 費用 |", "|---|---|---|---|---|---|---|---|"]
    sm = ROOT / "incoming/summary.md"
    if sm.exists():
        L += [x for x in sm.read_text(encoding="utf-8").splitlines() if any(f"| {d} " in x for d in added)]
    L += ["", "## 4. 知識庫驗證與缺口", ""] + [x for x in chk if x.strip()][:20] + [""]
    L += ["## 5. 評測", ""] + ev_lines[2:] + [f"", f"報告：`{ev.relative_to(ROOT)}`" if ev else ""] + [""]
    L += ["## 6. 標籤檢討（三個來源都有了）", "", "完整報告：`schema/TAG-REPORT.md`。重點：", ""]
    tr = ROOT / "schema/TAG-REPORT.md"
    L += [x for x in section(tr, "## A.", "## B.") if x.startswith("→")]
    L += section(tr, "### B4", "## C.", 4)
    L += ["", "### C. trace 的 workload 特徵", ""] + section(tr, "## C.", "## D.")
    L += ["", "## 7. 要人做的事", "",
          "- 看 `incoming/*-review.yaml`：A/B 不一致或驗證沒過的數字",
          "- 看 `schema/tag_mining/fill-log.md` 裡「閱讀建議場景」：scenario 標籤沒有自動改",
          "- 和學長確認 `schema/TAG-REPORT.md` 的 A 組（11 個必要標籤）與 B3 細分建議；確認後改 tags.yaml，再跑 `bash tools/tag_pipeline.sh` 重標",
          "- 人工複核：0 筆；論文用的數字要先複核",
          ""]
    out = ROOT / f"FOLLOWUP-{datetime.date.today()}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"寫入 {out.name}")


if __name__ == "__main__":
    main()
