"""知識庫檢索：給人、腳本與 agent（透過 tools/kb_mcp.py）共用的查詢函式。輸出一律是 JSON。

用法（在任何目錄都可以）：
  python3 tools/kb.py params [--dimension memory] [--priority P1]
  python3 tools/kb.py query mem_pin_rate [--scenario edge] [--text LPDDR] [--mode release]
  python3 tools/kb.py get N0037            （或 doc_id，例如 PAPER-SIMBA）
  python3 tools/kb.py gaps [--dimension d2d] [--priority P1] [--scenario edge]
  python3 tools/kb.py search "flash"

原則：
- 每筆數字都帶出處（doc_id、頁碼、原文）與 verified；agent 引用時要附 num_id。
- mode=draft（預設）包含未複核的數字並標示；mode=release 只回已複核的數字（論文只能用這個）。
- 只讀不寫。新增數字走 incoming batch → tools/check.py --batch → tools/add_numbers.py。
"""
import argparse
import csv
import difflib
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EDGE = {"edge_embedded", "edge_automotive", "edge_mobile"}
VALUE_KINDS = {
    "spec_limit": "規格上下限或目標",
    "measured": "實際晶片量測或下線晶片的設計值",
    "assumed": "論文假設或模擬設定",
    "derived": "換算、推算或推斷",
    "vendor_claim": "廠商宣稱（多為峰值）",
}


def _csv(name):
    p = ROOT / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _split(cell):
    return [x.strip() for x in (cell or "").split(";") if x.strip()]


class KB:
    def __init__(self):
        tags = yaml.safe_load((ROOT / "schema/tags.yaml").read_text(encoding="utf-8"))
        schema = yaml.safe_load((ROOT / "schema/dse_dimensions.yaml").read_text(encoding="utf-8"))
        self.scenarios = set(tags["scenario"])
        self.dims = schema["dimensions"]
        self.scope = schema.get("scope", {})
        self.params = {}
        self.renamed = {}  # 舊參數 id → 新 id（2026-11-09 改 edge 版）
        for dname, d in self.dims.items():
            for pid, s in d["params"].items():
                self.params[pid] = {"parameter": pid, "dimension": dname, **s}
                old = s.get("replaces") or []
                for o in [old] if isinstance(old, str) else old:
                    if o != pid:
                        self.renamed[o] = pid
        self.catalog = {r["doc_id"]: r for r in _csv("catalog.csv")}
        self.numbers = _csv("numbers.csv")
        self.by_id = {r["num_id"]: r for r in self.numbers}
        self.candidates = _csv("catalog_candidates.csv")

    # ---------- 小工具 ----------

    def doc_scenarios(self, doc_id):
        return sorted(set(_split(self.catalog.get(doc_id, {}).get("tags"))) & self.scenarios)

    def _scenario_ok(self, doc_id, scenario):
        if not scenario:
            return True
        s = set(self.doc_scenarios(doc_id))
        if scenario == "edge":  # edge 加上不分場景的標準與方法
            return bool(s & (EDGE | {"generic"}))
        if scenario == "edge_only":
            return bool(s & EDGE)
        return scenario in s

    def _row(self, r):
        doc = self.catalog.get(r["doc_id"], {})
        return {
            "num_id": r["num_id"],
            "parameter": r["parameter"],
            "value": float(r["value"]),
            "unit": r["unit"],
            "condition": r["condition"],
            "value_kind": r.get("value_kind", ""),
            "verified": bool(r.get("verified_by", "").strip()),
            "doc_id": r["doc_id"],
            "doc_title": doc.get("title", ""),
            "doc_year": doc.get("year", ""),
            "scenario": self.doc_scenarios(r["doc_id"]),
            "source_grade": r["source_grade"],
            "location": r["location"],
            "quote": r["quote"],
        }

    def _suggest(self, word):
        word_l = word.lower()
        hits = [p for p, s in self.params.items()
                if word_l in p or any(word_l in str(a).lower() for a in s.get("aliases", []))]
        return hits or difflib.get_close_matches(word, list(self.params), n=5, cutoff=0.4)

    # ---------- 對外的查詢 ----------

    def list_params(self, dimension=None, priority=None):
        count = Counter(r["parameter"] for r in self.numbers)
        out = []
        for pid, s in self.params.items():
            if dimension and s["dimension"] != dimension:
                continue
            if priority and s["priority"] != priority:
                continue
            out.append({k: s.get(k) for k in ("parameter", "dimension", "unit", "priority", "why", "aliases")}
                       | {"n_numbers": count[pid]})
        return {"scope": self.scope, "dimensions": {k: v["name"] for k, v in self.dims.items()}, "params": out}

    def query(self, parameter=None, dimension=None, scenario=None, text=None, value_kind=None,
              mode="draft", limit=50):
        redirected = None
        if parameter in self.renamed:
            redirected, parameter = parameter, self.renamed[parameter]
        if parameter and parameter not in self.params:
            return {"error": f"沒有參數 '{parameter}'", "did_you_mean": self._suggest(parameter)}
        if dimension and dimension not in self.dims:
            return {"error": f"沒有維度 '{dimension}'", "dimensions": list(self.dims)}
        rows = []
        for r in self.numbers:
            if parameter and r["parameter"] != parameter:
                continue
            if dimension and self.params.get(r["parameter"], {}).get("dimension") != dimension:
                continue
            if value_kind and r.get("value_kind") != value_kind:
                continue
            if not self._scenario_ok(r["doc_id"], scenario):
                continue
            if mode == "release" and not r.get("verified_by", "").strip():
                continue
            if text:
                hay = " ".join([r["condition"], r["quote"], r["doc_id"],
                                self.catalog.get(r["doc_id"], {}).get("title", "")]).lower()
                if not all(t in hay for t in text.lower().split()):
                    continue
            rows.append(self._row(r))
        out = {"mode": mode, "count": len(rows)}
        if parameter:
            p = self.params[parameter]
            out["parameter"] = {k: p.get(k) for k in ("parameter", "dimension", "unit", "priority", "why", "pitfalls")}
        if rows and parameter:
            vals = [x["value"] for x in rows]
            out["summary"] = {
                "min": min(vals), "max": max(vals), "n_docs": len({x["doc_id"] for x in rows}),
                "by_value_kind": dict(Counter(x["value_kind"] for x in rows)),
                "by_scenario": dict(Counter(s for x in rows for s in x["scenario"])),
            }
        notes = []
        if redirected:
            notes.append(f"'{redirected}' 是舊參數 id，已改名為 '{parameter}'")
        if mode == "draft" and any(not x["verified"] for x in rows):
            notes.append("含未人工複核的數字（verified=false）：可用於探索，不可直接寫進論文；論文請用 mode=release")
        if rows and all(x["scenario"] == ["datacenter"] for x in rows):
            notes.append("全部來自資料中心產品，edge 場景要另找數字或註明是外推")
        if any(x["value_kind"] in ("assumed", "vendor_claim") for x in rows):
            notes.append("assumed＝論文假設、vendor_claim＝廠商峰值；比較時優先 measured 與 spec_limit")
        if not rows:
            notes.append("沒有符合的數字；可用 kb_gaps 看缺口與建議文件")
        out["notes"] = notes
        out["rows"] = rows[:limit]
        if len(rows) > limit:
            out["truncated"] = len(rows) - limit
        return out

    def get(self, id_):
        if id_ in self.by_id:
            return self._row(self.by_id[id_]) | {"value_kind_meaning": VALUE_KINDS.get(self.by_id[id_].get("value_kind"), "")}
        if id_ in self.catalog:
            d = dict(self.catalog[id_])
            nums = [r for r in self.numbers if r["doc_id"] == id_]
            d["scenario"] = self.doc_scenarios(id_)
            d["numbers"] = [{"num_id": r["num_id"], "parameter": r["parameter"], "value": float(r["value"]),
                             "unit": r["unit"], "condition": r["condition"]} for r in nums]
            return d
        for c in self.candidates:
            if c["doc_id"] == id_:
                return dict(c) | {"note": "這是候選文件，還沒確認原文、還沒入 catalog"}
        return {"error": f"找不到 '{id_}'（num_id 例如 N0012；doc_id 例如 PAPER-SIMBA）"}

    def gaps(self, dimension=None, priority="P1", scenario="edge"):
        by_param = defaultdict(list)
        for r in self.numbers:
            by_param[r["parameter"]].append(r)
        missing, reference_only, unverified_only = [], [], []
        gap_dims = set()
        for pid, s in self.params.items():
            if dimension and s["dimension"] != dimension:
                continue
            if priority and s["priority"] != priority:
                continue
            rows = [r for r in by_param[pid] if self._scenario_ok(r["doc_id"], scenario)]
            if not by_param[pid]:
                missing.append(pid)
                gap_dims.add(s["dimension"])
            elif not rows:
                reference_only.append(pid)
                gap_dims.add(s["dimension"])
            elif not any(r.get("verified_by", "").strip() for r in rows):
                unverified_only.append(pid)
        # 建議下一步讀哪些文件：catalog 裡還沒抽的、候選清單，依優先級與能補幾個缺口的維度排序
        rank = {"P1": 0, "P2": 1, "P3": 2}
        sugg = []
        for d in list(self.catalog.values()) + self.candidates:
            if d.get("status") in ("已抽數字", "已複核"):
                continue
            dims = set(_split(d.get("dimensions"))) & gap_dims
            scen = set(_split(d.get("tags")) + _split(d.get("scenario"))) & self.scenarios
            if not dims or (scenario in ("edge", "edge_only") and scen == {"datacenter"}):
                continue
            sugg.append({"doc_id": d["doc_id"], "title": d.get("title", ""), "priority": d.get("priority", ""),
                         "covers": sorted(dims), "access": d.get("access") or d.get("link_status", ""),
                         "in_catalog": d["doc_id"] in self.catalog})
        sugg.sort(key=lambda x: (rank.get(x["priority"], 9), -len(x["covers"])))
        return {"scenario": scenario, "priority": priority,
                "missing": missing,
                "reference_only": reference_only,
                "unverified_only": unverified_only,
                "suggested_docs": sugg[:10],
                "legend": {"missing": "完全沒有數字", "reference_only": "只有不符合此場景的來源（例如只有資料中心）",
                           "unverified_only": "有數字但都還沒人工複核"}}

    def search(self, text, limit=20):
        t = text.lower()
        params = [pid for pid, s in self.params.items()
                  if t in pid or t in s.get("why", "").lower() or any(t in str(a).lower() for a in s.get("aliases", []))]
        docs = [{"doc_id": d["doc_id"], "title": d["title"], "status": d["status"]}
                for d in self.catalog.values() if t in (d["title"] + d.get("summary", "") + d["tags"]).lower()]
        docs += [{"doc_id": c["doc_id"], "title": c["title"], "status": "候選"}
                 for c in self.candidates if t in (c["title"] + c.get("why_edge", "")).lower()]
        nums = [{"num_id": r["num_id"], "parameter": r["parameter"], "value": float(r["value"]), "unit": r["unit"],
                 "condition": r["condition"]}
                for r in self.numbers if t in (r["condition"] + " " + r["quote"]).lower()]
        return {"params": params, "docs": docs[:limit], "numbers": nums[:limit]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("params"); p.add_argument("--dimension"); p.add_argument("--priority")
    q = sub.add_parser("query"); q.add_argument("parameter", nargs="?"); q.add_argument("--dimension")
    q.add_argument("--scenario"); q.add_argument("--text"); q.add_argument("--value-kind")
    q.add_argument("--mode", default="draft", choices=["draft", "release"]); q.add_argument("--limit", type=int, default=50)
    g = sub.add_parser("get"); g.add_argument("id")
    gp = sub.add_parser("gaps"); gp.add_argument("--dimension"); gp.add_argument("--priority", default="P1")
    gp.add_argument("--scenario", default="edge")
    s = sub.add_parser("search"); s.add_argument("text")
    a = ap.parse_args()
    kb = KB()
    if a.cmd == "params":
        out = kb.list_params(a.dimension, a.priority)
    elif a.cmd == "query":
        out = kb.query(a.parameter, a.dimension, a.scenario, a.text, a.value_kind, a.mode, a.limit)
    elif a.cmd == "get":
        out = kb.get(a.id)
    elif a.cmd == "gaps":
        out = kb.gaps(a.dimension, a.priority or None, a.scenario or None)
    else:
        out = kb.search(a.text)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
