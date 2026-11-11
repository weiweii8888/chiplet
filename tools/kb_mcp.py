"""把知識庫檢索包成 MCP server（stdio），讓 Claude Code 等 agent harness 與 Tack 外掛直接呼叫。

不需要額外套件：自己實作 MCP 的 initialize、tools/list、tools/call（JSON-RPC 2.0，一行一則訊息）。
每次呼叫都重新讀檔，所以資料更新後不用重開 server。

註冊到 Claude Code：專案根目錄的 .mcp.json（已附）。手動測試：
  printf '%s\\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 tools/kb_mcp.py
"""
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb import KB  # noqa: E402

SERVER_INFO = {"name": "chiplet-kb", "version": "0.1.0"}
INSTRUCTIONS = (
    "chiplet 硬體數字知識庫，主要對象是跑 LLM 的嵌入式／edge AI 加速器，資料中心產品只當對照。"
    "每筆數字都有出處（doc_id、頁碼、原文）；回答或做設計決策時請引用 num_id。"
    "verified=false 的數字只能用於探索，不能直接寫進論文（論文請用 mode=release）。"
    "value_kind：measured＞spec_limit＞assumed／vendor_claim／derived，比較時注意性質不同。"
    "不知道參數 id 時先用 kb_search 或 kb_list_params；查不到數字時用 kb_gaps 看缺口與建議文件。"
)

SCENARIO = {"type": "string",
            "description": "edge（edge 加上不分場景的標準與方法，預設建議）、edge_only、edge_embedded、edge_mobile、"
                           "edge_automotive、datacenter、generic；不填＝全部"}

TOOLS = [
    {
        "name": "kb_list_params",
        "description": "列出知識庫的設計維度與參數 id（含單位、優先級 P1～P3、用途、別名、目前有幾筆數字）。不確定參數 id 時先呼叫這個。",
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
            "dimension": {"type": "string", "description": "compute_die、partition、memory、d2d、workload_ref、thermal_power、package、cost、system"},
            "priority": {"type": "string", "enum": ["P1", "P2", "P3"]}}},
    },
    {
        "name": "kb_query",
        "description": "查某個參數（或某個維度）的所有數值。回傳摘要（最小、最大、來源性質分布）與每筆數字的條件、性質、是否已複核、出處頁碼與原文。舊參數 id 會自動轉成新 id。",
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
            "parameter": {"type": "string", "description": "參數 id，例如 d2d_energy_per_bit、mem_total_bandwidth"},
            "dimension": {"type": "string", "description": "改查整個維度"},
            "scenario": SCENARIO,
            "text": {"type": "string", "description": "在條件、原文、文件標題裡找的關鍵字（空白分隔＝全部都要有），例如 LPDDR5X、organic"},
            "value_kind": {"type": "string", "enum": ["spec_limit", "measured", "assumed", "derived", "vendor_claim"]},
            "mode": {"type": "string", "enum": ["draft", "release"], "description": "draft 含未複核（預設）；release 只回已複核"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200}}},
    },
    {
        "name": "kb_get",
        "description": "用 num_id（例如 N0037）取一筆數字的完整出處，或用 doc_id（例如 PAPER-SIMBA）取一份文件的資訊與它所有的數字。",
        "inputSchema": {"type": "object", "additionalProperties": False, "required": ["id"], "properties": {
            "id": {"type": "string"}}},
    },
    {
        "name": "kb_gaps",
        "description": "列出某場景下還缺數字的參數：完全沒有、只有不符場景的來源（例如只有資料中心）、有但都未複核；並依優先級建議下一步該讀的文件。",
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
            "dimension": {"type": "string"},
            "priority": {"type": "string", "enum": ["P1", "P2", "P3"], "description": "預設 P1"},
            "scenario": SCENARIO}},
    },
    {
        "name": "kb_search",
        "description": "全文搜尋：在參數（id、用途、別名）、文件（標題、摘要、標籤、候選清單）、數字（條件、原文）裡找關鍵字。",
        "inputSchema": {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {
            "text": {"type": "string"}}},
    },
]


def call_tool(name, args):
    kb = KB()
    if name == "kb_list_params":
        return kb.list_params(args.get("dimension"), args.get("priority"))
    if name == "kb_query":
        return kb.query(args.get("parameter"), args.get("dimension"), args.get("scenario"), args.get("text"),
                        args.get("value_kind"), args.get("mode", "draft"), args.get("limit", 50))
    if name == "kb_get":
        return kb.get(args["id"])
    if name == "kb_gaps":
        return kb.gaps(args.get("dimension"), args.get("priority", "P1"), args.get("scenario", "edge"))
    if name == "kb_search":
        return kb.search(args["text"])
    raise KeyError(name)


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification（例如 notifications/initialized），不用回
        return None
    if method == "initialize":
        ver = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        result = {"protocolVersion": ver, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        p = msg.get("params") or {}
        try:
            out = call_tool(p.get("name"), p.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                      "isError": "error" in out}
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"未知工具或缺參數：{e}"}}
        except Exception:
            result = {"content": [{"type": "text", "text": traceback.format_exc(limit=3)}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"不支援的方法 {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON 解析失敗"}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
