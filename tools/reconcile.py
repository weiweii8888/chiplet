"""比對同一份文件的兩次獨立抽取（A、B），通過驗證的才入庫。

流程：
1. A、B 配對：同參數、同單位、數值差 ≤ 0.5% 算一致。
2. 一致的列做出處檢查（引句是否在標注頁）；不在標注頁但在別頁找到，就改頁碼並記在 ai_check。
3. 跑 check.py 的驗證（單位、範圍、重複與衝突）。
4. 全部通過的寫成 incoming/<doc>-agreed.yaml，交給 add_numbers.py 入庫（verified_by 留空，等人工複核）。
   其他的寫成 incoming/<doc>-review.yaml，附原因，等人看。被引用的數字寫成 incoming/<doc>-leads.yaml，當找原始文件的線索。

用法：python3 tools/reconcile.py PAPER-NN-BATON
"""
import csv
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "incoming"
TODAY = datetime.date.today().isoformat()


def load(doc, run):
    p = INC / "raw" / f"{doc}-{run}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = []
    for r in d.get("rows", []):
        try:
            r["value"] = float(r["value"])
        except (TypeError, ValueError, KeyError):
            continue
        rows.append({k: r.get(k, "") for k in ("parameter", "value", "unit", "condition", "location", "quote", "value_kind")})
    return rows, d.get("leads", []), d.get("_meta", {})


def same(a, b):
    if a["parameter"] != b["parameter"] or a["unit"] != b["unit"]:
        return False
    return abs(a["value"] - b["value"]) <= 1e-9 + 0.005 * abs(a["value"])


def relocate(doc, row):
    """引句不在標注頁時，掃整份 PDF 找它在哪一頁。"""
    pdf = check.pdf_for(doc)
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    n = int(re.search(r"Pages:\s+(\d+)", out).group(1))
    for page in range(1, n + 1):
        trial = dict(row, doc_id=doc, location=f"PDF p.{page}")
        if check.provenance(trial)[0] == "ok":
            return page
    return None


def main():
    doc = sys.argv[1]
    A, B = load(doc, "A"), load(doc, "B")
    if not A or not B:
        sys.exit(f"{doc}: 缺 A 或 B 的抽取結果")
    rows_a, leads_a, meta_a = A
    rows_b, leads_b, meta_b = B

    agreed, review, used = [], [], set()
    for a in rows_a:
        j = next((j for j, b in enumerate(rows_b) if j not in used and same(a, b)), None)
        if j is None:
            review.append(dict(a, reason="只有 A 抽到（B 沒有同參數同值）"))
        else:
            used.add(j)
            agreed.append(dict(a, ai_check="A/B 一致"))
    review += [dict(b, reason="只有 B 抽到（A 沒有同參數同值）") for j, b in enumerate(rows_b) if j not in used]

    # 出處
    passed = []
    for r in agreed:
        st, why = check.provenance(dict(r, doc_id=doc))
        if st == "ok":
            passed.append(dict(r, ai_check=r["ai_check"] + "；出處 ok"))
            continue
        page = relocate(doc, r) if st == "fail" else None
        if page:
            old = r["location"]
            r["location"] = re.sub(r"p\.\s*\d+", f"p.{page}", old) if re.search(r"p\.\s*\d+", old) else f"PDF p.{page}"
            passed.append(dict(r, ai_check=r["ai_check"] + f"；頁碼由「{old}」改為 p.{page}（引句在該頁）"))
        else:
            review.append(dict(r, reason=f"A/B 一致但出處檢查失敗：{why}"))

    # 驗證（單位、範圍、重複、衝突）
    tags, dims, rules = check.load_schema()
    doc_ids = {r["doc_id"] for r in check.read_csv("catalog.csv")}
    existing = check.read_csv("numbers.csv")
    cands = []
    for i, r in enumerate(passed, 1):
        c = {k: str(v) for k, v in r.items()}
        c.update(num_id=f"cand{i}", doc_id=doc, source_grade="paper", extracted_by="claude")
        cands.append(c)
    errs, warns = check.validate_rows(cands, existing, doc_ids, dims, rules)
    bad = {}
    for e in errs:
        bad.setdefault(e.split(":")[0], []).append(e)
    note = {}
    for w in warns:
        note.setdefault(w.split(":")[0], []).append(w.split(":", 1)[1].strip())
    final = []
    for c, r in zip(cands, passed):
        if c["num_id"] in bad:
            review.append(dict(r, reason="驗證失敗：" + "；".join(x.split(":", 1)[1].strip() for x in bad[c["num_id"]])))
        else:
            extra = "；".join(note.get(c["num_id"], []))
            final.append(dict(r, ai_check=r["ai_check"] + (f"；警告：{extra}" if extra else "")))

    def dump(path, obj):
        path.write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")

    model = meta_a.get("model", "claude")
    if final:
        batch = {"defaults": {"doc_id": doc, "source_grade": "paper", "extracted_by": f"{model}（Claude Code，A/B 兩次獨立抽取）",
                              "extracted_date": TODAY},
                 "rows": [{k: (v if k != "value" else (int(v) if float(v).is_integer() else v)) for k, v in r.items()} for r in final]}
        dump(INC / f"{doc}-agreed.yaml", batch)
        res = subprocess.run([sys.executable, str(ROOT / "tools/add_numbers.py"), str(INC / f"{doc}-agreed.yaml")],
                             capture_output=True, text=True)
        print(res.stdout.strip() or res.stderr.strip())
        if res.returncode == 0:
            (INC / "merged").mkdir(exist_ok=True)
            (INC / f"{doc}-agreed.yaml").rename(INC / "merged" / f"{doc}-agreed-{TODAY}.yaml")
            # catalog 狀態改為已抽數字
            with open(ROOT / "catalog.csv", newline="", encoding="utf-8") as f:
                rd = csv.DictReader(f)
                fields, cat = rd.fieldnames, list(rd)
            for r in cat:
                if r["doc_id"] == doc and r["status"] in ("待收", "已收"):
                    r["status"] = "已抽數字"
            with open(ROOT / "catalog.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
                w.writeheader()
                w.writerows(cat)
    if review:
        dump(INC / f"{doc}-review.yaml", {"doc_id": doc, "rows": review})
    leads = {(str(x.get("parameter")), str(x.get("value")), str(x.get("cited_ref"))): x for x in leads_a + leads_b}
    if leads:
        dump(INC / f"{doc}-leads.yaml", {"doc_id": doc, "leads": list(leads.values())})

    summary = (f"| {doc} | A {len(rows_a)} | B {len(rows_b)} | 一致 {len(agreed)} | 入庫 {len(final)} | "
               f"待人看 {len(review)} | 線索 {len(leads)} | ${(meta_a.get('cost_usd') or 0) + (meta_b.get('cost_usd') or 0):.2f} |")
    with open(INC / "summary.md", "a", encoding="utf-8") as f:
        f.write(summary + "\n")
    print(summary)


if __name__ == "__main__":
    main()
