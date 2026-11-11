# 附件 A1：收集 agent 軌跡（trace）

目標（投影片附件 A1）：把 agent 在 harness 裡每一步做了什麼、用了多少 context、花多少時間完整收下來，轉成同一種軌跡格式，讓重放器或 DSE 世界跑得動，並和學弟 B 的參考資料（這個知識庫）對照。

## 四種收法與現況

| 收法 | 拿得到什麼 | 現況 |
|---|---|---|
| ① 模型端點代理（gateway） | 每次請求的 token、首字延遲、完整請求；每個 harness 都能用 | ⬜ 未做；Tack 的 gateway 進行中，接上後補 `ttft_ms` |
| ② harness 自己的 session 紀錄 | token 用量、tool 呼叫與耗時、壓縮事件 | ✅ `tools/trace_convert.py`：Claude Code、Codex 兩種格式 |
| ③ plugin／hook | 即時記錄，可補自訂欄位（tool 耗時、DSE 提案與換方向的理由） | ⬜ 規劃：用 Claude Code hooks（PreToolUse、PostToolUse、SessionEnd）寫 JSONL |
| ④ 自架伺服器指標 | GPU 上的 KV 快取命中、排隊時間 | ⬜ 要在 H100 上跑 vLLM／SGLang 才有 |

## 檔案

| 檔案 | 內容 |
|---|---|
| `traces/SCHEMA.md` | 統一軌跡格式 v0（拿到學長的 Unified Trace schema 後對齊） |
| `tools/trace_convert.py` | 收法 ②：session 紀錄轉統一格式；遮蔽個資與金鑰，只留數字與長度 |
| `tools/trace_stats.py` | 每批統計、和知識庫對照（context 換成 KV 大小、對照記憶體容量）、workload 標籤候選 |
| `traces/converted/` | 轉出的軌跡（不進 git） |
| `traces/stats/` | 每批統計報告 |

## 用法

```bash
python3 tools/trace_convert.py claude-code     # 讀 ~/.claude/projects
python3 tools/trace_convert.py codex           # 讀 ~/.codex/sessions
python3 tools/trace_stats.py                   # 統計＋知識庫對照，寫到 traces/stats/
python3 tools/tag_report.py                    # 把 workload 特徵併進標籤檢討
```

## 驗收（A1 投影片）

- [ ] 轉成統一格式後，重放器或 DSE 世界跑得動：要等學長的重放器輸入格式
- [ ] 抽 10 個任務，代理和紀錄檔的 token 數對得上：要先有 ① 代理
- [x] 寫清來源、授權、版本；濾掉個資與金鑰；原始檔不進 git：轉檔器已做
- [x] 每批附統計：任務數、平均步數、context 與快取命中分布：`trace_stats.py`

## 還沒有的資料

- **成敗（outcome）**：session 紀錄沒有。SWE 類任務要跑測試判斷；DSE 任務要記錄最後選的設計，以及它是不是最佳。
- **DSE 任務的提案與換方向理由**：要靠 ③ hook，或讓 Tack 的 MCP 工具自己記錄。
- **公開 trace**：FreeInference（CC BY 4.0）可以先用；Azure、Mooncake、BurstGPT、SWE-bench 的授權待查。

## 隱私

本機的 `~/.claude/projects`、`~/.codex/sessions` 是個人所有對話的原始紀錄，裡面有其他專案的內容。要轉檔或統計前，要先由紀錄的主人同意。
轉檔器只保留數字、長度、工具名稱，以及遮蔽過的前 120 字摘要；不保存內文。
