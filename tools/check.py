"""知識庫驗證器：格式、單位、範圍規則、重複與衝突，選用時再查出處（引句是否真的在標注的那一頁）。

用法（在知識庫根目錄執行）：
  python3 tools/check.py                    檢查全部資料，印出統計與缺口
  python3 tools/check.py --provenance       另外檢查每筆引句是否逐字出現在 PDF 標注頁（需要 pdftotext 與 pdfs/）
  python3 tools/check.py --batch b.yaml     只檢查一批待入庫的數字（不寫入）；add_numbers.py 入庫前也會跑這個

有錯誤時 exit code 為 1。其他程式可以 import 這個模組的 validate_rows()、provenance()。
"""
import argparse
import csv
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {"待查連結", "待收", "已收", "已抽數字", "已複核"}
SOURCE_GRADES = {"spec", "paper", "whitepaper", "textbook", "vendor_web", "secondary"}
VALUE_KINDS = {
    "spec_limit": "規格上下限或目標",
    "measured": "實際晶片量測或下線晶片的設計值",
    "assumed": "論文假設或模擬設定",
    "derived": "換算、推算或推斷（condition 要寫怎麼來的）",
    "vendor_claim": "廠商宣稱（多為峰值）",
}
PRIORITIES = {"P1", "P2", "P3"}
CATALOG_REQUIRED = ["doc_id", "type", "title", "url", "access", "tags", "dimensions", "priority", "status"]
NUMBERS_REQUIRED = ["num_id", "doc_id", "parameter", "value", "unit", "location", "source_grade", "value_kind", "extracted_by"]


def split_list(cell):
    return [x.strip() for x in (cell or "").split(";") if x.strip()]


def read_csv(name):
    with open(ROOT / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_schema():
    tags = yaml.safe_load((ROOT / "schema/tags.yaml").read_text(encoding="utf-8"))
    dims = yaml.safe_load((ROOT / "schema/dse_dimensions.yaml").read_text(encoding="utf-8"))["dimensions"]
    rules = yaml.safe_load((ROOT / "schema/rules.yaml").read_text(encoding="utf-8"))["rules"]
    return tags, dims, rules


# ---------- 規則 ----------

def range_violation(rule, value):
    return not (float(rule["min"]) <= float(value) <= float(rule["max"]))


def self_test_rules(rules, params):
    errs = []
    for r in rules:
        if r["param"] not in params:
            errs.append(f"rules.yaml {r['id']}: 參數 {r['param']} 不在 schema")
        t = r.get("test") or {}
        if "pass" not in t or "fail" not in t:
            errs.append(f"rules.yaml {r['id']}: 缺 test.pass 或 test.fail")
        elif range_violation(r, t["pass"]) or not range_violation(r, t["fail"]):
            errs.append(f"rules.yaml {r['id']}: 規則自我測試失敗（pass={t['pass']} fail={t['fail']}）")
    return errs


# ---------- 數字列檢查（全庫與 batch 共用） ----------

def validate_rows(rows, existing, doc_ids, dims, rules):
    """檢查 rows；existing 是已入庫的數字（用來找重複與衝突）。回傳 (errors, warnings)。"""
    errors, warnings = [], []
    param_unit = {p: s["unit"] for d in dims.values() for p, s in d["params"].items()}
    active = defaultdict(list)
    for r in rules:
        if r.get("status") in ("active", "warn") and r["type"] == "range":
            active[r["param"]].append(r)

    seen = defaultdict(list)
    for r in existing:
        seen[(r["doc_id"], r["parameter"], r["condition"].strip())].append(r)

    for r in rows:
        rid = r.get("num_id") or "(batch)"
        for col in NUMBERS_REQUIRED:
            if col == "num_id" and rid == "(batch)":
                continue
            if not r.get(col):
                errors.append(f"{rid}: 缺 {col}")
        if r.get("doc_id") and r["doc_id"] not in doc_ids:
            errors.append(f"{rid}: doc_id '{r['doc_id']}' 不在 catalog.csv")
        p = r.get("parameter", "")
        if p not in param_unit:
            errors.append(f"{rid}: parameter '{p}' 不在 dse_dimensions.yaml")
        elif r.get("unit") != param_unit[p]:
            errors.append(f"{rid}: 單位 '{r.get('unit')}' 應為 '{param_unit[p]}'（換算後在 condition 記原值）")
        if r.get("value_kind") and r["value_kind"] not in VALUE_KINDS:
            errors.append(f"{rid}: value_kind '{r['value_kind']}' 不在 {sorted(VALUE_KINDS)}")
        if r.get("source_grade") and r["source_grade"] not in SOURCE_GRADES:
            errors.append(f"{rid}: source_grade '{r['source_grade']}' 不在 {sorted(SOURCE_GRADES)}")
        if r.get("location") and not re.search(r"p\.\s*\d+", r["location"]):
            warnings.append(f"{rid}: location 沒有頁碼（應寫 PDF p.N）")
        try:
            v = float(r.get("value", ""))
        except ValueError:
            errors.append(f"{rid}: value '{r.get('value')}' 不是數字（範圍請拆成兩列並在 condition 註明）")
            continue
        for rule in active.get(p, []):
            if range_violation(rule, v):
                msg = f"{rid}: {p}={v} 超出 {rule['id']} 範圍 [{rule['min']}, {rule['max']}]：{rule['why']}"
                (errors if rule["severity"] == "error" and rule["status"] == "active" else warnings).append(msg)
        # 重複與衝突：同文件、同參數、同 condition
        key = (r.get("doc_id"), p, (r.get("condition") or "").strip())
        for o in seen[key]:
            if o is r:
                continue
            try:
                ov = float(o["value"])
            except ValueError:
                continue
            if ov == v:
                errors.append(f"{rid}: 和 {o['num_id']} 重複（同文件、同參數、同 condition、同值）")
            else:
                warnings.append(f"{rid}: 和 {o['num_id']} 衝突（同文件、同參數、同 condition，值 {v} vs {ov}）；兩筆都留，進人工複核")
        seen[key].append(r)
    return errors, warnings


# ---------- 出處：引句是否在標注頁 ----------

def _norm(s):
    s = unicodedata.normalize("NFKC", s).lower().replace("-\n", "")
    return re.sub(r"[^0-9a-z]", "", s)


def pdf_for(doc_id):
    for p in sorted((ROOT / "pdfs").glob("*.pdf")):
        if doc_id.endswith(p.stem):
            return p
    return None


@lru_cache(maxsize=None)
def page_texts(pdf, page):
    out = []
    for mode in (["-layout"], []):
        try:
            res = subprocess.run(["pdftotext", *mode, "-f", str(page), "-l", str(page), str(pdf), "-"],
                                 capture_output=True, text=True, timeout=60)
            out.append(_norm(res.stdout))
        except (OSError, subprocess.TimeoutExpired):
            pass
    return tuple(out)


def provenance(row):
    """回傳 (狀態, 說明)。狀態：ok／fail／skip。"""
    pdf = pdf_for(row["doc_id"])
    m = re.search(r"p\.\s*(\d+)", row.get("location", ""))
    if not pdf or not m or not row.get("quote"):
        return "skip", "沒有 PDF、頁碼或引句"
    texts = page_texts(pdf, int(m.group(1)))
    segs = [_norm(s) for s in re.split(r"\.\.\.|…|\|", row["quote"]) if _norm(s)]
    missing = [s for s in segs if not any(s in t for t in texts)]
    if missing:
        return "fail", f"引句有 {len(missing)}/{len(segs)} 段不在 {pdf.name} p.{m.group(1)}"
    return "ok", ""


# ---------- 主程式 ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provenance", action="store_true")
    ap.add_argument("--batch")
    args = ap.parse_args()

    tags, dims, rules = load_schema()
    errors, warnings = [], []
    params = {p: s for d in dims.values() for p, s in d["params"].items()}

    # schema 本身
    for p, s in params.items():
        if s.get("priority") not in PRIORITIES:
            errors.append(f"schema {p}: priority 應為 P1/P2/P3")
        if not s.get("unit"):
            errors.append(f"schema {p}: 缺 unit")
    errors += self_test_rules(rules, params)

    catalog = read_csv("catalog.csv")
    numbers = read_csv("numbers.csv")
    doc_ids = Counter(r["doc_id"] for r in catalog)

    if args.batch:
        batch = yaml.safe_load(Path(args.batch).read_text(encoding="utf-8"))
        rows = [{k: str(v) for k, v in {**(batch.get("defaults") or {}), **e}.items()} for e in batch["rows"]]
        for i, r in enumerate(rows, 1):
            r.setdefault("condition", "")
            r["num_id"] = f"batch第{i}列"
        e, w = validate_rows(rows, numbers, doc_ids, dims, rules)
        for x in w:
            print("警告：", x)
        for x in e:
            print("錯誤：", x)
        print(f"batch {len(rows)} 列：{len(e)} 個錯誤，{len(w)} 個警告")
        sys.exit(1 if e else 0)

    # catalog
    doc_types = set(tags["doc_type"])
    all_tags = {t for g, items in tags.items() if g != "doc_type" for t in items}
    scenarios = set(tags["scenario"])
    for d, n in doc_ids.items():
        if n > 1:
            errors.append(f"catalog: doc_id 重複 {d}")
    for r in catalog:
        rid = r["doc_id"] or "(空 doc_id)"
        for col in CATALOG_REQUIRED:
            if not r.get(col) and not (col == "url" and r.get("status") == "待查連結"):
                errors.append(f"catalog {rid}: 缺 {col}")
        if r["type"] not in doc_types:
            errors.append(f"catalog {rid}: type '{r['type']}' 不在 tags.yaml doc_type")
        tl = split_list(r["tags"])
        for t in tl:
            if t not in all_tags:
                errors.append(f"catalog {rid}: 標籤 '{t}' 不在 tags.yaml")
        if not scenarios & set(tl):
            errors.append(f"catalog {rid}: tags 至少要有一個 scenario 標籤 {sorted(scenarios)}")
        for d in split_list(r["dimensions"]):
            if d not in dims:
                errors.append(f"catalog {rid}: 維度 '{d}' 不在 dse_dimensions.yaml")
        if r["priority"] not in PRIORITIES:
            errors.append(f"catalog {rid}: priority '{r['priority']}' 應為 P1/P2/P3")
        if r["status"] not in STATUSES:
            errors.append(f"catalog {rid}: status '{r['status']}' 不在 {sorted(STATUSES)}")

    # numbers
    for n, c in Counter(r["num_id"] for r in numbers).items():
        if c > 1:
            errors.append(f"numbers: num_id 重複 {n}")
    e, w = validate_rows(numbers, [], doc_ids, dims, rules)
    errors += [f"numbers {x}" for x in e]
    warnings += [f"numbers {x}" for x in w]

    if args.provenance:
        res = Counter()
        for r in numbers:
            st, why = provenance(r)
            res[st] += 1
            if st == "fail":
                errors.append(f"numbers {r['num_id']}: 出處檢查失敗：{why}")
        print(f"出處檢查：{dict(res)}")

    # cards
    num_ids = {r["num_id"] for r in numbers}
    for path in sorted((ROOT / "cards").glob("CASE-*.yaml")):
        card = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for s in card.get("sources") or []:
            if s not in doc_ids:
                errors.append(f"{path.name}: source '{s}' 不在 catalog.csv")
        for dim, entry in (card.get("design") or {}).items():
            for n in (entry or {}).get("numbers") or []:
                if n not in num_ids:
                    errors.append(f"{path.name}: {dim} 引用的 {n} 不在 numbers.csv")

    # 統計：依優先級列缺口；edge 視角另外標出「只有資料中心來源」的參數
    doc_scen = {r["doc_id"]: set(split_list(r["tags"])) & scenarios for r in catalog}
    by_param = defaultdict(list)
    for r in numbers:
        by_param[r["parameter"]].append(r)
    print(f"文件 {len(catalog)} 筆；數字 {len(numbers)} 筆（已複核 {sum(1 for r in numbers if r['verified_by'].strip())}）")
    print("  文件依場景：", dict(Counter(s for v in doc_scen.values() for s in v)))
    print("  數字依性質：", dict(Counter(r["value_kind"] for r in numbers)))
    print("\n各維度缺口（P1 優先；「僅對照」表示只有 datacenter 來源，edge 還是缺）：")
    for name, d in dims.items():
        line = []
        for prio in ("P1", "P2"):
            miss, ref_only = [], []
            for p, s in d["params"].items():
                if s["priority"] != prio:
                    continue
                rows = by_param.get(p, [])
                if not rows:
                    miss.append(p)
                elif all(doc_scen.get(r["doc_id"]) == {"datacenter"} for r in rows):
                    ref_only.append(p)
            n_prio = sum(1 for s in d["params"].values() if s["priority"] == prio)
            if n_prio:
                line.append(f"{prio} {n_prio - len(miss) - len(ref_only)}/{n_prio}"
                            + (f" 缺 {', '.join(miss)}" if miss else "")
                            + (f" 僅對照 {', '.join(ref_only)}" if ref_only else ""))
        print(f"  {name}（{d['name']}）：" + "；".join(line))

    for x in warnings:
        print("警告：", x)
    for x in errors:
        print("錯誤：", x)
    print(f"\n{len(errors)} 個錯誤，{len(warnings)} 個警告")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
