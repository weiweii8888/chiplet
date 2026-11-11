"""彙整「標籤該怎麼切」的三個來源，寫成 schema/TAG-REPORT.md（只提案，不改 tags.yaml）。

來源（方法見 TAGGING-METHOD.md）：
  A 由上而下：Tack 實際要做的決策變數（第 2～4、6～16 頁）與附件 A2 規定的固定標籤，每個都要有標籤可查。
  B 文獻：tools/tag_mine.py 讓 Claude 逐篇讀 PDF 的結果（schema/tag_mining/*.json）。
  C 由下而上：tools/trace_stats.py 的 workload 特徵（traces/stats/*.json），有分群能力的才收。
另外檢查現有標籤的涵蓋率：0 份文件、或超過 60% 文件都有的標籤，都要檢討。

用法：python3 tools/tag_report.py
"""
import csv
import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# A：Tack 的決策變數 → 需要的標籤（group, id, 中文, 出處）
TOP_DOWN = [
    ("kv_policy", "kv_retain", "前文保留策略", "Tack p.4 KV／context manager：保留"),
    ("kv_policy", "kv_quantize", "KV 量化", "Tack p.4；附件 A2 固定標籤"),
    ("kv_policy", "kv_evict", "KV 逐出", "Tack p.4；附件 A2 固定標籤"),
    ("kv_policy", "kv_reuse", "KV 重用（含 prefix 快取）", "Tack p.4、p.8 KV 重用 adapter；附件 A2 固定標籤"),
    ("kv_policy", "sparse_attention", "稀疏注意力", "Tack p.2、p.9 四個設定之一"),
    ("kv_policy", "context_compaction", "context 壓縮／摘要", "附件 A1：trace 要記壓縮事件"),
    ("serving", "pd_disaggregation", "prefill／decode 分離", "附件 A2 ③ Splitwise／DistServe；固定標籤 serving 架構"),
    ("serving", "multi_session", "多 session 同時服務", "Tack p.2：換 session 數，79% 任務換最佳硬體"),
    ("workload", "agent_workload", "agent 長 context（多輪、tool 呼叫）", "Tack p.1～2 研究主軸"),
    ("memory", "lpddr", "LPDDR", "附件 A2 固定標籤：記憶體種類"),
    ("memory", "hbm", "HBM", "附件 A2 固定標籤：記憶體種類"),
    ("metric", "bandwidth_capacity", "頻寬與容量", "附件 A2 固定標籤"),
    ("method", "simulator", "模擬器／評估器", "Tack p.6～7：LLMCompass、PLENA"),
    ("method", "analytical_model", "解析模型（roofline 等）", "Tack p.13：roofline × 效率 η"),
    ("method", "silicon_measured", "實機或下線晶片量測", "Tack：高保真度評估＝模擬或 H100 實機"),
]


def load_yaml(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


def norm_id(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def main():
    tags = load_yaml("schema/tags.yaml")
    have = {t: g for g, items in tags.items() if g != "doc_type" for t in items}
    with open(ROOT / "catalog.csv", newline="", encoding="utf-8") as f:
        catalog = list(csv.DictReader(f))
    cat_tags = {r["doc_id"]: set(x for x in r["tags"].split(";") if x) for r in catalog}
    L = [f"# 標籤檢討報告 {datetime.date.today()}", "",
         "這份是提案，還沒改 `schema/tags.yaml`。依 README 規則 4，新增標籤要先跟學長確認。方法見 [TAGGING-METHOD.md](../TAGGING-METHOD.md)。", ""]

    # A 由上而下
    L += ["## A. 由上而下：Tack 的決策變數有沒有標籤可查", "", "| 標籤 | 組 | 中文 | 出處 | 現況 |", "|---|---|---|---|---|"]
    missing_td = []
    for g, tid, label, src in TOP_DOWN:
        ok = tid in have
        if not ok:
            missing_td.append(tid)
        L.append(f"| `{tid}` | {g} | {label} | {src} | {'✅ 已有' if ok else '❌ 缺'} |")
    L += ["", f"→ 缺 {len(missing_td)} 個：{', '.join(missing_td) or '無'}。這些是 Tack 一定會查的決策，**建議全數新增**。", ""]

    # B 文獻
    mined = {}
    for p in sorted((ROOT / "schema/tag_mining").glob("*.json")):
        mined[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    L += ["## B. 文獻：逐篇讀 PDF 的提案", "", f"已讀 {len(mined)} 份（`schema/tag_mining/`）。", ""]
    if mined:
        add_existing = []
        for doc, d in mined.items():
            extra = set(d.get("existing_tags", [])) - cat_tags.get(doc, set())
            extra = {t for t in extra if t in have}
            if extra:
                add_existing.append(f"- `{doc}`：catalog 建議補 {', '.join(sorted(extra))}")
        L += ["### B1. catalog 漏標（現有標籤適用但沒標）", ""] + (add_existing or ["- 無"]) + [""]

        props = defaultdict(list)
        for doc, d in mined.items():
            for t in d.get("proposed_tags", []):
                props[norm_id(t.get("id"))].append((doc, t))
        L += ["### B2. 新標籤提案（依提案文件數排序；≥2 份＝候選，1 份＝觀察）", "",
              "| 標籤 | 組 | 中文 | 定義 | 提案文件 | 和 A 重疊 | 建議 |", "|---|---|---|---|---|---|---|"]
        td_ids = {t[1] for t in TOP_DOWN}
        for tid, lst in sorted(props.items(), key=lambda kv: -len(kv[1])):
            t0 = lst[0][1]
            docs = sorted({d for d, _ in lst})
            overlap = "是" if tid in td_ids else ""
            rec = "已在 A" if overlap else ("已存在" if tid in have else ("候選" if len(docs) >= 2 else "觀察"))
            L.append(f"| `{tid}` | {t0.get('group', '')} | {t0.get('label', '')} | {str(t0.get('definition', ''))[:60]} | "
                     f"{', '.join(docs)} | {overlap} | {rec} |")
        L += [""]

        coarse, by_tag = [], defaultdict(list)
        for doc, d in mined.items():
            for c in d.get("too_coarse", []):
                tag = c.get("tag") if isinstance(c, dict) else str(c).split()[0].strip("`")
                by_tag[tag].append(doc)
                txt = c.get("suggestion", "") if isinstance(c, dict) else str(c)
                coarse.append(f"- `{tag}`（{doc}）：{txt}")
        L += ["### B3. 太粗、該細分的現有標籤", "",
              "多份文件各自讀、卻指出同一個標籤太粗，是最強的訊號（≥3 份＝建議細分）。", "",
              "| 標籤 | 幾份文件說太粗 | 文件 | 建議 |", "|---|---|---|---|"]
        for tag, docs in sorted(by_tag.items(), key=lambda kv: -len(kv[1])):
            L.append(f"| `{tag}` | {len(docs)} | {', '.join(sorted(set(docs)))} | "
                     f"{'建議細分' if len(set(docs)) >= 3 else '觀察'} |")
        L += ["", "<details><summary>各文件的細分建議原文</summary>", ""] + (coarse or ["- 無"]) + ["", "</details>", ""]

        serves = Counter()
        for d in mined.values():
            for x in d.get("decisions", []):
                serves[x.get("serves", "?")] += 1
        L += ["### B4. 文件裡的決策服務哪一種 Tack 決策", "",
              "、".join(f"{k} {v}" for k, v in serves.most_common()) or "無", "",
              "kv_runtime 很少代表收的文件偏硬體；A 組的 KV 標籤新增後要補 KV 管理論文（附件 A2 ③）。", ""]

    # C 由下而上
    stats = sorted((ROOT / "traces/stats").glob("*.json"))
    L += ["## C. 由下而上：trace 的 workload 特徵", ""]
    if stats:
        sys.path.insert(0, str(ROOT / "tools"))
        from trace_stats import features  # noqa: E402
        S = json.loads(stats[-1].read_text(encoding="utf-8"))
        feats = [features(s) for s in S]
        L += [f"來源 `{stats[-1].relative_to(ROOT)}`，{len(S)} 個 session。", "",
              "| 特徵 | 有的 session | 建議 |", "|---|---|---|"]
        for k in feats[0]:
            frac = sum(f[k] for f in feats) / len(feats)
            L.append(f"| {k} | {frac:.0%} | {'候選 workload 標籤或 DSE 維度' if 0.2 <= frac <= 0.8 else '分不出差別，先不收'} |")
        L += [""]
    else:
        L += ["還沒有 trace 統計（`traces/stats/`）。轉檔與統計要先取得授權處理本機 session 紀錄，見 traces/README.md。", ""]

    # 涵蓋率
    cnt = Counter(t for ts in cat_tags.values() for t in ts)
    n = len(catalog)
    L += ["## D. 現有標籤的涵蓋率", "", f"catalog {n} 份文件。", "",
          "| 標籤 | 組 | 文件數 | 檢討 |", "|---|---|---|---|"]
    for t, g in have.items():
        c = cnt[t]
        note = "0 份：預留中，或刪除" if c == 0 else ("超過 60%：太粗，分不出文件" if c > 0.6 * n and g != "scenario" else "")
        if note:
            L.append(f"| `{t}` | {g} | {c} | {note} |")
    L += ["", "（只列需要檢討的；其他標籤涵蓋率正常。）", ""]
    (ROOT / "schema/TAG-REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"寫入 schema/TAG-REPORT.md；A 缺 {len(missing_td)}、B 讀 {len(mined)} 份、C {'有' if stats else '無'} trace 統計")


if __name__ == "__main__":
    main()
