"""把 harness 的 session 紀錄轉成統一軌跡格式（traces/SCHEMA.md）。附件 A1 的收法 ②。

用法：
  python3 tools/trace_convert.py claude-code [~/.claude/projects]
  python3 tools/trace_convert.py codex [~/.codex/sessions]
輸出：traces/converted/<harness>/<session>.jsonl（不進 git）

只保留數字與長度；訊息與 tool 輸出內文不保存，指令與參數摘要會遮蔽個資與金鑰。
"""
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "trace_convert v0 2026-11-10"
HOME = str(Path.home())
SECRET = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|sk-ant-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[bap]-[A-Za-z0-9-]{10,})"), "<secret>"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{10,}"), "Bearer <secret>"),
    (re.compile(r"(?i)(api[_-]?key|token|password|secret)(\s*[=:]\s*)\S+"), r"\1\2<secret>"),
]


def redact(s, n=120):
    s = (s or "").replace(HOME, "~")
    for pat, rep in SECRET:
        s = pat.sub(rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def text_len(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(text_len(c.get("text") or c.get("content") or "") if isinstance(c, dict) else len(str(c)) for c in content)
    return len(str(content or ""))


def first_text(content):
    if isinstance(content, str):
        return content
    for c in content or []:
        if isinstance(c, dict) and c.get("type") in ("text", "input_text") and not c.get("text", "").startswith("<"):
            return c["text"]
    return ""


def finish(harness, sid, path, events, task, models, extra=None):
    events.sort(key=lambda e: e.get("_t") or 0)
    times = [e["_t"] for e in events if e.get("_t")]
    step = 0
    for e in events:
        if e["kind"] == "llm_call":
            step += 1
        e["step"] = step
        e["t"] = datetime.fromtimestamp(e.pop("_t")).isoformat(timespec="seconds") if e.get("_t") else None
        e.pop("_t", None)
    head = {"kind": "session", "trace_id": f"{harness}:{sid}", "harness": harness, "models": dict(models),
            "task": redact(task), "task_type": "unknown", "outcome": "unknown",
            "start": datetime.fromtimestamp(min(times)).isoformat(timespec="seconds") if times else None,
            "end": datetime.fromtimestamp(max(times)).isoformat(timespec="seconds") if times else None,
            "wall_s": round(max(times) - min(times)) if times else None,
            # 實際工作時間：相鄰事件間隔超過 5 分鐘視為閒置（session 常被續用好幾天）
            "active_s": round(sum(min(b - a, 300) for a, b in zip(sorted(times), sorted(times)[1:]))) if times else None,
            **(extra or {}),
            "source": {"sha1": hashlib.sha1(str(path).encode()).hexdigest()[:12], "converter": VERSION,
                       "license": "自己的 session，僅內部使用"}}
    out = ROOT / "traces/converted" / harness / f"{sid}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for e in [head] + events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return head, sum(e["kind"] == "llm_call" for e in events)


def convert_claude_code(path):
    events, seen_req, pending, models = [], set(), {}, Counter()
    task, sid = "", path.stem
    for line in open(path, encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ts(d.get("timestamp"))
        typ = d.get("type")
        if typ == "user":
            content = d["message"].get("content")
            if not task and not d.get("isSidechain") and isinstance(content, (str, list)):
                txt = first_text(content)
                if txt and not txt.startswith("<"):
                    task = txt
            for c in content if isinstance(content, list) else []:
                if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in pending:
                    ev = pending.pop(c["tool_use_id"])
                    ev["duration_ms"] = round((t - ev["_t"]) * 1000) if t and ev["_t"] else None
                    ev["result_chars"] = text_len(c.get("content"))
                    ev["is_error"] = bool(c.get("is_error"))
        elif typ == "assistant":
            m = d.get("message", {})
            rid = d.get("requestId") or m.get("id")
            u = m.get("usage") or {}
            if rid and rid not in seen_req and u:
                seen_req.add(rid)
                models[m.get("model", "?")] += 1
                inp, cw, cr = u.get("input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("cache_read_input_tokens", 0)
                events.append({"kind": "llm_call", "_t": t, "model": m.get("model"), "input_new": inp, "cache_write": cw,
                               "cache_read": cr, "output": u.get("output_tokens", 0),
                               "thinking": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
                               "context_len": inp + cw + cr, "ttft_ms": None, "stop_reason": m.get("stop_reason"),
                               "sidechain": bool(d.get("isSidechain"))})
            for c in m.get("content") or []:
                if c.get("type") == "tool_use":
                    ev = {"kind": "tool_call", "_t": t, "tool": c.get("name"),
                          "args_summary": redact(json.dumps(c.get("input"), ensure_ascii=False)),
                          "duration_ms": None, "result_chars": None, "is_error": None}
                    pending[c.get("id")] = ev
                    events.append(ev)
        elif typ == "system" and d.get("subtype") == "compact_boundary":
            cm = d.get("compactMetadata") or {}
            events.append({"kind": "compaction", "_t": t, "pre_tokens": cm.get("preTokens"),
                           "post_tokens": cm.get("postTokens"), "trigger": cm.get("trigger")})
        sid = d.get("sessionId") or sid
    return finish("claude-code", sid, path, events, task, models)


def convert_codex(path):
    events, pending, models = [], {}, Counter()
    task, sid, model, last_ctx, forked = "", path.stem, "?", None, None
    pending_compaction = None
    for line in open(path, encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t, typ, p = ts(d.get("timestamp")), d.get("type"), d.get("payload") or {}
        if typ == "session_meta":
            sid = p.get("id") or sid
            forked = p.get("forked_from_id")
        elif typ == "turn_context":
            model = p.get("model") or model
        elif typ == "event_msg" and p.get("type") == "thread_settings_applied":
            model = (p.get("thread_settings") or {}).get("model") or model
        elif typ == "event_msg" and p.get("type") == "item_completed" and not task:
            it = p.get("item") or {}
            if it.get("type") == "UserMessage":
                task = first_text(it.get("content"))
        elif typ == "event_msg" and p.get("type") == "token_count":
            u = ((p.get("info") or {}).get("last_token_usage")) or {}
            if u and u.get("input_tokens"):  # 壓縮後第一筆可能是 0，略過
                inp, cr = u.get("input_tokens", 0), u.get("cached_input_tokens", 0)
                models[model] += 1
                ctx = inp
                events.append({"kind": "llm_call", "_t": t, "model": model, "input_new": inp - cr,
                               "cache_write": u.get("cache_write_input_tokens", 0), "cache_read": cr,
                               "output": u.get("output_tokens", 0), "thinking": u.get("reasoning_output_tokens"),
                               "context_len": ctx, "ttft_ms": None, "stop_reason": None, "sidechain": False})
                if pending_compaction is not None:
                    pending_compaction["post_tokens"] = ctx
                    pending_compaction = None
                last_ctx = ctx
        elif typ == "response_item" and p.get("type") in ("function_call", "custom_tool_call"):
            ev = {"kind": "tool_call", "_t": t, "tool": p.get("name"),
                  "args_summary": redact(p.get("arguments") or p.get("input") or ""),
                  "duration_ms": None, "result_chars": None, "is_error": None}
            pending[p.get("call_id")] = ev
            events.append(ev)
        elif typ == "response_item" and p.get("type") in ("function_call_output", "custom_tool_call_output"):
            ev = pending.pop(p.get("call_id"), None)
            if ev:
                out = p.get("output")
                txt = out if isinstance(out, str) else " ".join(x.get("text", "") for x in out or [] if isinstance(x, dict))
                m = re.search(r"Wall time:?\s*([\d.]+)\s*seconds", txt)
                ev["duration_ms"] = round(float(m.group(1)) * 1000) if m else (
                    round((t - ev["_t"]) * 1000) if t and ev["_t"] else None)
                ev["result_chars"] = len(txt)
                ev["is_error"] = bool(re.search(r"(?i)exit code:?\s*[1-9]|error", txt[:200]))
        elif typ == "compacted":
            pending_compaction = {"kind": "compaction", "_t": t, "pre_tokens": last_ctx, "post_tokens": None, "trigger": "codex"}
            events.append(pending_compaction)
    return finish("codex", sid, path, events, task, models,
                  {"forked_from": f"codex:{forked}" if forked else None})


def main():
    harness = sys.argv[1]
    if harness == "claude-code":
        src = Path(sys.argv[2] if len(sys.argv) > 2 else Path.home() / ".claude/projects").expanduser()
        files, conv = sorted(src.glob("*/*.jsonl")), convert_claude_code
    elif harness == "codex":
        src = Path(sys.argv[2] if len(sys.argv) > 2 else Path.home() / ".codex/sessions").expanduser()
        files, conv = sorted(src.rglob("rollout-*.jsonl")), convert_codex
    else:
        sys.exit("harness 只支援 claude-code、codex")
    n_ok = 0
    for f in files:
        try:
            head, n = conv(f)
        except Exception as e:  # 單檔失敗不影響其他
            print(f"略過 {f.name}：{e}")
            continue
        if n == 0:
            (ROOT / "traces/converted" / harness / f"{head['trace_id'].split(':', 1)[1]}.jsonl").unlink(missing_ok=True)
            continue
        n_ok += 1
        print(f"{head['trace_id'][:50]:50s} {n:5d} 次 LLM 呼叫  {head['wall_s'] or 0:>8}s  {head['task'][:40]}")
    print(f"{harness}：{len(files)} 個紀錄檔，轉出 {n_ok} 個 session")


if __name__ == "__main__":
    main()
