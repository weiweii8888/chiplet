"""一次性轉換：2026-11-09 改成 edge 版 schema（schema_version 2）。

做四件事（可重複執行，結果相同）：
1. numbers.csv：依 dse_dimensions.yaml 的 replaces，把舊參數 id 改成新的。
2. numbers.csv：新增 value_kind 欄（數字的性質），依文件類型與 condition 先填初稿，人工複核時一併確認。
3. catalog.csv：tags 補 scenario 標籤；dimensions 的 hbm 改成 memory；priority 從 W1～W4 改成 P1～P3。
4. cards/*.yaml：design 底下的 hbm 改成 memory。

用法：python3 tools/migrate_edge.py
"""
import csv
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# 每份文件的場景與新優先級（理由見 EDGE-PLAN.md §2）
DOC_PLAN = {
    "PAPER-SIMBA": ("edge_embedded", "P1"),
    "PAPER-CAMBRICON-LLM": ("edge_mobile", "P1"),
    "SPEC-BOW-2.0": ("generic", "P1"),
    "SPEC-UCIE-3.0": ("generic", "P1"),
    "SPEC-UCIE-2.0": ("generic", "P2"),
    "SPEC-AIB": ("generic", "P2"),
    "SPEC-BOW-MEM-1.0": ("generic", "P3"),
    "PAPER-CHIPLET-ACTUARY": ("generic", "P2"),
    "PAPER-GEMINI": ("generic", "P2"),
    "BOOK-LAU-CHIPLET": ("generic", "P2"),
    "WP-TSMC-3DFABRIC": ("generic", "P2"),
    "PAPER-AMD-ISCA21": ("generic", "P3"),
    "SPEC-JEDEC-HBM4": ("datacenter", "P3"),
    "SPEC-JEDEC-HBM3": ("datacenter", "P3"),
    "SPEC-CXL-3": ("datacenter", "P3"),
    "WP-AMD-CDNA3": ("datacenter", "P3"),
    "WP-NV-BLACKWELL": ("datacenter", "P3"),
    "WP-INTEL-GAUDI3": ("datacenter", "P3"),
    "PAPER-HECATON": ("datacenter", "P3"),
    "PAPER-ECTC23-COWOSL": ("datacenter", "P3"),
    "CASE-MI300X": ("datacenter", "P3"),
    "CASE-GAUDI3": ("datacenter", "P3"),
}
SCENARIOS = {"edge_embedded", "edge_automotive", "edge_mobile", "datacenter", "generic"}

# value_kind 初稿：先看 condition 有沒有推斷／推算，再看文件類型
DERIVED_HINTS = ("推斷", "推算", "面積為換算", "模型推算值")
KIND_BY_TYPE = {"spec": "spec_limit", "whitepaper": "vendor_claim", "textbook": "assumed"}
MEASURED_DOCS = {"PAPER-SIMBA"}  # 實際下線晶片的量測或設計值


def guess_kind(row, doc_type):
    if any(h in row["condition"] for h in DERIVED_HINTS):
        return "derived"
    if row["doc_id"] in MEASURED_DOCS:
        return "measured"
    return KIND_BY_TYPE.get(doc_type, "assumed")


def read(name):
    with open(ROOT / name, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def write(name, fields, rows):
    with open(ROOT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


dims = yaml.safe_load((ROOT / "schema/dse_dimensions.yaml").read_text(encoding="utf-8"))["dimensions"]
rename = {}
for d in dims.values():
    for pid, spec in d["params"].items():
        old = spec.get("replaces") or []
        for o in [old] if isinstance(old, str) else old:
            if o != pid:
                rename[o] = pid

# catalog
cfields, catalog = read("catalog.csv")
doc_type = {r["doc_id"]: r["type"] for r in catalog}
for r in catalog:
    scen, prio = DOC_PLAN.get(r["doc_id"], ("generic", "P2"))
    tags = [t for t in r["tags"].split(";") if t.strip()]
    if not SCENARIOS & set(tags):
        tags.insert(0, scen)
    r["tags"] = ";".join(tags)
    r["dimensions"] = ";".join("memory" if x == "hbm" else x for x in r["dimensions"].split(";") if x)
    if r["priority"].startswith("W"):
        r["priority"] = prio
write("catalog.csv", cfields, catalog)

# numbers
nfields, numbers = read("numbers.csv")
if "value_kind" not in nfields:
    nfields.insert(nfields.index("source_grade") + 1, "value_kind")
renamed = 0
for r in numbers:
    if r["parameter"] in rename:
        r["parameter"] = rename[r["parameter"]]
        renamed += 1
    if not r.get("value_kind"):
        r["value_kind"] = guess_kind(r, doc_type.get(r["doc_id"], ""))
write("numbers.csv", nfields, numbers)

# cards
for p in (ROOT / "cards").glob("*.yaml"):
    s = p.read_text(encoding="utf-8")
    s2 = re.sub(r"(?m)^(\s+)hbm:", r"\1memory:", s)
    if s2 != s:
        p.write_text(s2, encoding="utf-8")

print(f"參數改名 {renamed} 列；catalog {len(catalog)} 列已補 scenario 與 P1～P3 優先級")
