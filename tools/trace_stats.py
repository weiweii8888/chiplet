"""統一軌跡的批次統計，以及和知識庫的對照（附件 A1 驗收：每批附統計；A 的 trace 對照 B 的參考資料）。

用法：python3 tools/trace_stats.py [traces/converted] [--out traces/stats]
輸出：<out>/<日期>.md 與 .json

三件事：
1. 每批統計：session 數、平均步數、context 長度分布、快取命中分布、tool 耗時與輸出量、壓縮次數。
2. 知識庫對照：把 trace 的 context 長度換算成 KV 大小，對照知識庫裡 edge 記憶體容量（實際發生 vs 書上怎麼說）。
3. 由下而上的 tag 候選：哪些 workload 特徵在 session 之間差異大（20%～80% 的 session 有），就值得變成 workload 標籤或 DSE 維度。
"""
import argparse
import datetime
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from kb import KB  # noqa: E402

# 以模型架構算的每 token KV（fp16，K 與 V 各一份）：2 × 層數 × KV head 數 × head 維度 × 2 bytes
REF_MODELS = {
    "Llama-3-8B（32 層、8 KV head、128 維）": 2 * 32 * 8 * 128 * 2,
    "Llama-2-70B（80 層、8 KV head、128 維）": 2 * 80 * 8 * 128 * 2,
}


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def load(src):
    sessions = []
    for f in sorted(Path(src).rglob("*.jsonl")):
        lines = [json.loads(x) for x in open(f, encoding="utf-8") if x.strip()]
        if not lines or lines[0].get("kind") != "session":
            continue
        head, ev = lines[0], lines[1:]
        llm = [e for e in ev if e["kind"] == "llm_call"]
        tools = [e for e in ev if e["kind"] == "tool_call"]
        comp = [e for e in ev if e["kind"] == "compaction"]
        if not llm:
            continue
        ctx = [e["context_len"] for e in llm if e.get("context_len")]
        tot_ctx = sum(ctx) or 1
        res_chars = sum(e.get("result_chars") or 0 for e in tools)
        sessions.append({
            "trace_id": head["trace_id"], "harness": head["harness"], "forked_from": head.get("forked_from"),
            "steps": len(llm), "tool_calls": len(tools), "active_s": head.get("active_s"),
            "ctx_p50": pct(ctx, 0.5), "ctx_max": max(ctx) if ctx else 0,
            "cache_hit": sum(e.get("cache_read") or 0 for e in llm) / tot_ctx,
            "output_tokens": sum(e.get("output") or 0 for e in llm),
            "tool_s": sum((e.get("duration_ms") or 0) for e in tools) / 1000,
            "tool_result_tokens_est": res_chars / 4,  # 粗估：4 字元約 1 token
            "compactions": len(comp),
            "subagent_share": sum(e.get("sidechain") for e in llm) / len(llm),
            "tools": Counter(e.get("tool") for e in tools),
        })
    return sessions


def features(s):
    """由下而上的 workload 特徵（布林），用來找值得變成標籤的特徵。"""
    return {
        "長 context（最大 > 100k token）": s["ctx_max"] > 100_000,
        "觸發過 context 壓縮": s["compactions"] > 0,
        "tool 輸出量 > 最大 context 的一半": s["tool_result_tokens_est"] > 0.5 * max(s["ctx_max"], 1),
        "快取命中 > 90%": s["cache_hit"] > 0.9,
        "用了 subagent": s["subagent_share"] > 0,
        "長任務（> 50 步）": s["steps"] > 50,
        "tool 時間 > 工作時間 30%": bool(s["active_s"]) and s["tool_s"] > 0.3 * s["active_s"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=str(ROOT / "traces/converted"))
    ap.add_argument("--out", default=str(ROOT / "traces/stats"))
    a = ap.parse_args()
    all_s = load(a.src)
    # fork 出來的 session 共用前段歷史，統計時只留原始的
    ids = {s["trace_id"] for s in all_s}
    S = [s for s in all_s if not (s["forked_from"] and s["forked_from"] in ids)]
    if not S:
        sys.exit("沒有可統計的 session")
    by_h = Counter(s["harness"] for s in S)
    L = [f"# 軌跡批次統計 {datetime.date.today()}", "",
         f"- 來源：`{a.src}`；session {len(S)} 個（{dict(by_h)}；排除 {len(all_s) - len(S)} 個 fork）",
         f"- 平均步數（LLM 呼叫）{statistics.mean(s['steps'] for s in S):.1f}；中位數 {pct([s['steps'] for s in S], .5)}",
         f"- 每 session 最大 context：p50 {pct([s['ctx_max'] for s in S], .5):,}、p90 {pct([s['ctx_max'] for s in S], .9):,}、"
         f"最大 {max(s['ctx_max'] for s in S):,} token",
         f"- 快取命中（cache_read ÷ context）：p50 {pct([s['cache_hit'] for s in S], .5):.0%}、p10 {pct([s['cache_hit'] for s in S], .1):.0%}",
         f"- 觸發壓縮的 session：{sum(s['compactions'] > 0 for s in S)}/{len(S)}",
         f"- 最常用的 tool：{', '.join(f'{k} {v}' for k, v in sum((s['tools'] for s in S), Counter()).most_common(6))}",
         "", "## 每個 session", "",
         "| trace | 步數 | tool 次數 | 工作時間 | context p50 | context 最大 | 快取命中 | tool 輸出（估 token） | 壓縮 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in sorted(S, key=lambda x: -x["ctx_max"]):
        L.append(f"| {s['trace_id'][:24]} | {s['steps']} | {s['tool_calls']} | {(s['active_s'] or 0) / 60:.0f} 分 | "
                 f"{s['ctx_p50']:,} | {s['ctx_max']:,} | {s['cache_hit']:.0%} | {s['tool_result_tokens_est']:,.0f} | {s['compactions']} |")

    # 知識庫對照
    kb = KB()
    kv_doc = kb.query(parameter="kv_cache_size").get("rows", [])
    mem = kb.query(parameter="mem_total_capacity", scenario="edge").get("rows", [])
    mem_all = kb.query(parameter="mem_total_capacity").get("rows", [])
    est = dict(REF_MODELS)
    # 文件給的 KV 大小：只有 N0087 這種「batch 1、序列長度 1000」寫明的才能除以 1000 換成每 token
    # （2026-11-11 修：原本用 "1000" in condition 判斷，會誤抓「1 GB=1000 MB」，把 batch 128 或 8 萬 token 的總量也除以 1000）
    for r in kv_doc:
        if "序列長度 1000" in r["condition"] and "batch 1" in r["condition"]:
            est[f"{r['num_id']}（{r['doc_id']}，{r['value_kind']}）70B、照比例外推"] = r["value"] * 1e6 / 1000
    # 文件直接給的每 token KV（條件欄有模型與算法）
    for r in kb.query(parameter="kv_bytes_per_token").get("rows", []):
        model = next((p.split("=", 1)[1] for p in r["condition"].split(";") if p.strip().startswith("model=")), "")
        est[f"{r['num_id']}（{r['doc_id']}，{model.strip() or '模型見條件'}）"] = r["value"] * 1e6
    L += ["", "## 和知識庫對照：實際的 context 換成 KV 要多大", "",
          "context 長度取上面的 p50、p90 與最大值；KV 只算一個 session、batch 1、不壓縮。", "",
          "| 估法（每 token KV） | p50 | p90 | 最大 |", "|---|---|---|---|"]
    qs = [pct([s["ctx_max"] for s in S], .5), pct([s["ctx_max"] for s in S], .9), max(s["ctx_max"] for s in S)]
    for name, b in est.items():
        L.append(f"| {name}：{b / 1e6:.3f} MB | " + " | ".join(f"{q * b / 1e9:.1f} GB" for q in qs) + " |")
    L += ["", "知識庫裡的記憶體總容量（edge 場景優先；沒有就列全部當對照）：", ""]
    for r in (mem or mem_all)[:10]:
        L.append(f"- {r['value']:g} GB：{r['condition'][:60]}（{r['num_id']}，{r['doc_id']}，{r['value_kind']}，"
                 f"{'已複核' if r['verified'] else '未複核'}）")
    if not mem:
        L.append("- ⚠ 知識庫還沒有 edge 場景的記憶體總容量（kb_gaps 會列為缺口）；上面全是資料中心對照")

    # 由下而上的 tag 候選
    feats = [features(s) for s in S]
    L += ["", "## 由下而上的 workload 標籤候選", "",
          "特徵在 20%～80% 的 session 出現，代表它能把 session 分成兩群，值得變成 workload 標籤或 DSE 維度；"
          "接近 0% 或 100% 的特徵分不出差別，先不收。", "",
          "| 特徵 | 有的 session | 建議 |", "|---|---|---|"]
    for k in feats[0]:
        frac = sum(f[k] for f in feats) / len(feats)
        L.append(f"| {k} | {frac:.0%} | {'候選' if 0.2 <= frac <= 0.8 else '先不收'} |")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = datetime.date.today().isoformat()
    (out / f"{stem}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / f"{stem}.json").write_text(json.dumps(
        [{k: (dict(v) if isinstance(v, Counter) else v) for k, v in s.items()} for s in S],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L[:8]))
    print(f"報告：{out / (stem + '.md')}")


if __name__ == "__main__":
    main()
