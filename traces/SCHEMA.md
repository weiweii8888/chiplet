# 統一軌跡格式（Unified Trace，暫定 v0）

附件 A1 要求「轉成同一種軌跡格式，重放器或 DSE 世界跑得動」。學長那邊已有 Unified Trace schema。
這份是在拿到它之前的暫定版，欄位照 A1 投影片「一筆 trace 長什麼樣」列。之後對齊時只要改 `tools/trace_convert.py` 的輸出，統計與知識庫對照不用動。

一個 session 一個 JSONL 檔。第一行是 `session`，之後每行是一個事件，依時間排序。

## session（第一行）

| 欄位 | 說明 |
|---|---|
| `kind` | `"session"` |
| `trace_id` | `<harness>:<原始 session id>` |
| `harness` | `claude-code`／`codex`（之後加 `pi`、`hermes`、`opencode`） |
| `models` | 這個 session 用過的模型與各自呼叫次數 |
| `task` | 第一個使用者指令的前 120 字（已遮蔽個資與金鑰）；DSE 任務另外標 `task_type: dse` |
| `outcome` | 成敗；session 紀錄裡沒有，預設 `unknown`，要由任務定義或人工標 |
| `start`、`end`、`wall_s` | 開始、結束時間與總秒數 |
| `source` | 原始檔路徑的雜湊（不放原檔路徑）、轉檔器版本、授權 |

## 事件

| `kind` | 欄位 | 從哪裡來（Claude Code／Codex） |
|---|---|---|
| `llm_call` | `step`、`model`、`input_new`（沒命中快取的輸入）、`cache_write`、`cache_read`、`output`、`thinking`、`context_len`（＝三種輸入相加）、`ttft_ms`、`stop_reason`、`sidechain`（是否為 subagent） | CC：assistant 訊息的 `usage`，同一個 requestId 只算一次；Codex：`token_count.last_token_usage` |
| `tool_call` | `step`、`tool`、`args_summary`（前 120 字，已遮蔽）、`duration_ms`、`result_chars`、`is_error` | CC：`tool_use` 與對應 `tool_result` 的時間差；Codex：`function_call`／`custom_tool_call` 與 output（優先用輸出裡的 Wall time） |
| `compaction` | `step`、`pre_tokens`、`post_tokens`、`trigger` | CC：`system/compact_boundary.compactMetadata`；Codex：`compacted`，前後長度取前後兩次 llm_call 的 context |
| `dse`（DSE 任務另加） | `proposal`、`verifier`、`result`、`pivot_reason` | 目前兩個 harness 的紀錄都沒有，要靠 ③ plugin／hook 或 MCP 工具紀錄補 |

## 已知缺口（session 紀錄這種收法拿不到的）

- `ttft_ms`（首字延遲）：要靠 ① 模型端點代理。
- KV 快取命中、排隊時間：要靠 ④ 自架伺服器的指標。這裡的 `cache_read` 是 API 的 prompt cache，不等於 GPU 上的 KV 命中。
- `outcome`：要靠任務定義（例如 SWE 任務跑測試）或人工標。

## 隱私

轉檔時會遮蔽 email、API key（`sk-…`、`ghp_…`、`AKIA…`、`Bearer …`）、家目錄路徑。不保存訊息內文、tool 輸出內文，只保存長度。
轉出的檔案放 `traces/converted/`，不進 git。
