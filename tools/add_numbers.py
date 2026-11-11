"""把一批數字從 YAML 檔附加到 numbers.csv，num_id 自動接續。

用法：python3 tools/add_numbers.py batch.yaml

batch.yaml 格式：
  defaults: {doc_id: PAPER-XXX, source_grade: paper, extracted_by: 名字, extracted_date: 2026-10-28}
  rows:
    - {parameter: d2d_latency, value: 20, unit: ns, condition: ..., location: PDF p.5 Table 2, quote: ...}

每列的欄位會蓋過 defaults。value_kind 必填（spec_limit／measured／assumed／derived／vendor_claim）。
入庫前會先跑 tools/check.py 的驗證（格式、單位、範圍規則、重複），有錯誤就整批不寫入。
"""
import csv
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "numbers.csv"

batch = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
defaults = batch.get("defaults") or {}

with open(path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    existing = list(reader)
last = max((int(r["num_id"][1:]) for r in existing if r["num_id"][1:].isdigit()), default=0)

# 入庫前驗證：任何錯誤就整批不寫
tags_y, dims_y, rules_y = check.load_schema()
doc_ids = {r["doc_id"] for r in check.read_csv("catalog.csv")}
candidate = [{k: str(v) for k, v in {**defaults, **e}.items()} for e in batch["rows"]]
for i, c in enumerate(candidate, 1):
    c.setdefault("condition", "")
    c["num_id"] = f"batch第{i}列"
errs, warns = check.validate_rows(candidate, existing, doc_ids, dims_y, rules_y)
for w in warns:
    print("警告：", w)
if errs:
    for e in errs:
        print("錯誤：", e)
    sys.exit(f"驗證失敗 {len(errs)} 個錯誤，整批未寫入")

new_rows = []
for i, entry in enumerate(batch["rows"], start=last + 1):
    row = {k: "" for k in fields}
    row.update({k: str(v) for k, v in {**defaults, **entry}.items()})
    unknown = set(row) - set(fields)
    if unknown:
        sys.exit(f"未知欄位 {sorted(unknown)}（第 {i - last} 列）")
    row["num_id"] = f"N{i:04d}"
    new_rows.append(row)

with open(path, "a", newline="", encoding="utf-8") as f:
    csv.DictWriter(f, fieldnames=fields, lineterminator="\n").writerows(new_rows)
print(f"附加 {len(new_rows)} 列：{new_rows[0]['num_id']}～{new_rows[-1]['num_id']}")
