"""跑知識庫評測（eval/questions.yaml），結果寫到 eval/results/<時間>.md 與 .json。

  python3 eval/run_eval.py              retrieval＋agent 兩種都跑
  python3 eval/run_eval.py --no-agent   只跑 retrieval（免費、幾秒）

agent 測試：用 Claude Code 無頭模式，只開放 chiplet-kb 的 MCP 工具（不能讀檔、不能上網），
問題原樣丟進去，檢查答案引用的 num_id 與關鍵字。這等於測「接上 harness 之後 agent 查得到、查得對」。
環境變數：CLAUDE_BIN、EVAL_MODEL（預設 claude-opus-5-5）、EVAL_EFFORT（預設 medium）、EVAL_WORKERS（預設 4）
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from kb import KB  # noqa: E402

CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
MODEL = os.environ.get("EVAL_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("EVAL_EFFORT", "medium")
SUFFIX = "\n\n只能用 chiplet-kb 工具查資料。回答時每個數字都要附 num_id（例如 N0012）；知識庫沒有的就直接說沒有，不要用自己的知識補。回答簡短。"


def retrieval(q, kb):
    specs = q.get("retrieval") or {}
    got = set()
    for args in specs if isinstance(specs, list) else [specs]:  # 比較題可以寫多個查詢
        got |= {r["num_id"] for r in kb.query(limit=500, **args).get("rows", [])}
    if q.get("expect_empty"):
        return not got, f"結果 {len(got)} 筆（應為 0）"
    need_all = set(q.get("expect_all", []))
    need_any = set(q.get("expect_any", []))
    ok = need_all <= got and (not need_any or bool(need_any & got))
    miss = sorted(need_all - got)
    why = (f"缺 {miss}" if miss else "") + ("" if not need_any or need_any & got else f" {sorted(need_any)} 都沒查到")
    return ok, why.strip()


def agent(q):
    try:
        res = subprocess.run(
            [CLAUDE, "-p", q["question"] + SUFFIX, "--model", MODEL, "--effort", EFFORT,
             "--mcp-config", str(ROOT / ".mcp.json"), "--strict-mcp-config", "--tools", "",
             "--allowedTools", "mcp__chiplet-kb", "--permission-mode", "dontAsk",
             "--output-format", "json", "--no-session-persistence"],
            cwd=ROOT, capture_output=True, text=True, timeout=600)
        meta = json.loads(res.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"ok": False, "why": f"執行失敗：{e}", "answer": "", "cost": 0, "turns": 0}
    ans = meta.get("result", "") or ""
    cited = set(re.findall(r"N\d{4}", ans))
    why = []
    miss = sorted(set(q.get("expect_all", [])) - cited)
    if miss:
        why.append(f"沒引用 {miss}")
    if q.get("expect_any") and not (set(q["expect_any"]) & cited):
        why.append(f"{q['expect_any']} 一個都沒引用")
    if q.get("mention_any") and not any(k.lower() in ans.lower() for k in q["mention_any"]):
        why.append(f"沒提到 {q['mention_any']} 任何一個")
    return {"ok": not why, "why": "；".join(why), "answer": ans, "cited": sorted(cited),
            "cost": meta.get("total_cost_usd") or 0, "turns": meta.get("num_turns") or 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-agent", action="store_true")
    a = ap.parse_args()
    qs = yaml.safe_load((ROOT / "eval/questions.yaml").read_text(encoding="utf-8"))["questions"]
    kb = KB()
    results = []
    for q in qs:
        ok, why = retrieval(q, kb)
        results.append({"id": q["id"], "type": q["type"], "question": q["question"], "retrieval_ok": ok, "retrieval_why": why})
    if not a.no_agent:
        with ThreadPoolExecutor(int(os.environ.get("EVAL_WORKERS", "4"))) as ex:
            for r, out in zip(results, ex.map(agent, qs)):
                r["agent"] = out
                print(f"{r['id']} agent {'✓' if out['ok'] else '✗'} {out['why']}", flush=True)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    outdir = ROOT / "eval/results"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{ts}.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(results)
    r_ok = sum(r["retrieval_ok"] for r in results)
    lines = [f"# 知識庫評測 {ts}", "", f"- 題數 {n}", f"- retrieval：{r_ok}/{n}"]
    if not a.no_agent:
        g_ok = sum(r["agent"]["ok"] for r in results)
        cost = sum(r["agent"]["cost"] for r in results)
        turns = sum(r["agent"]["turns"] for r in results) / n
        lines += [f"- agent（{MODEL}，effort {EFFORT}）：{g_ok}/{n}；平均 {turns:.1f} 輪；費用約 ${cost:.2f}"]
        by_type = {}
        for r in results:
            t = by_type.setdefault(r["type"], [0, 0])
            t[0] += r["agent"]["ok"]
            t[1] += 1
        lines += ["- 依題型：" + "、".join(f"{k} {v[0]}/{v[1]}" for k, v in by_type.items())]
    lines += ["", "| 題 | 題型 | retrieval | agent | 說明 |", "|---|---|---|---|---|"]
    for r in results:
        ag = r.get("agent", {})
        why = "；".join(x for x in [r["retrieval_why"], ag.get("why", "")] if x)
        lines.append(f"| {r['id']} | {r['type']} | {'✓' if r['retrieval_ok'] else '✗'} | "
                     f"{('✓' if ag.get('ok') else '✗') if ag else '-'} | {why} |")
    if not a.no_agent:
        lines += ["", "## 答錯的題目（agent 原始回答）", ""]
        for r in results:
            if not r["agent"]["ok"]:
                lines += [f"### {r['id']} {r['question']}", "", r["agent"]["answer"].strip(), ""]
    (outdir / f"{ts}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    print(f"報告：eval/results/{ts}.md")


if __name__ == "__main__":
    main()
