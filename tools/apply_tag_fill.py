"""把逐篇閱讀（schema/tag_mining/*.json）認為適用、但 catalog 沒標的「現有標籤」補上。

不改 tags.yaml（不新增標籤）。scenario 組不自動改（場景判斷要人看），只列在紀錄裡。
紀錄寫到 schema/tag_mining/fill-log.md，改完要跑 check.py。

用法：python3 tools/apply_tag_fill.py
"""
import csv
import datetime
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main():
    tags = yaml.safe_load((ROOT / "schema/tags.yaml").read_text(encoding="utf-8"))
    group = {t: g for g, items in tags.items() if g != "doc_type" for t in items}
    with open(ROOT / "catalog.csv", newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        fields, cat = rd.fieldnames, list(rd)
    log = [f"## {datetime.datetime.now():%F %T} 補標", ""]
    n = 0
    for r in cat:
        p = ROOT / "schema/tag_mining" / f"{r['doc_id']}.json"
        if not p.exists():
            continue
        sugg = json.loads(p.read_text(encoding="utf-8")).get("existing_tags", [])
        cur = [t for t in r["tags"].split(";") if t]
        add = [t for t in sugg if t in group and group[t] != "scenario" and t not in cur]
        scen = [t for t in sugg if group.get(t) == "scenario" and t not in cur]
        if add:
            r["tags"] = ";".join(cur + add)
            n += len(add)
            log.append(f"- `{r['doc_id']}`：補 {', '.join(add)}")
        if scen:
            log.append(f"  - `{r['doc_id']}`：閱讀建議場景 {', '.join(scen)}（未自動改，請人判斷）")
    with open(ROOT / "catalog.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(cat)
    with open(ROOT / "schema/tag_mining/fill-log.md", "a", encoding="utf-8") as f:
        f.write("\n".join(log + [f"", f"共補 {n} 個標籤", ""]) + "\n")
    print(f"補標 {n} 個（不含 scenario）")


if __name__ == "__main__":
    main()
