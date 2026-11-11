# 改成 edge 版：範圍與計畫

2026-11-09 草案；**2026-11-10 已依此改版上線**（schema_version 2）。新增參數或標籤之後仍照 README 規則 4 先跟學長確認。

## 0. 範圍

- **主要對象**：嵌入式／edge AI 加速器。特徵是功耗約數 W 到數十 W、die 小、多半沒有 HBM、成本敏感。
- **對照組**：資料中心加速器（MI300X、Gaudi 3 等）。保留它們的資料，但在 catalog 標 `scenario=datacenter`，不再優先補。
- **第一階段只做四個維度**：運算 die、切分方式、記憶體（原 HBM）、D2D。

## 1. 改了什麼（草案已併入正式檔）

| 檔案 | 內容 |
|---|---|
| `schema/dse_dimensions.yaml` | 四個維度的 edge 版參數，共 40 個。每個參數標 P1／P2／P3 優先級、別名（aliases）、常見錯誤（pitfalls），以及對應的舊參數（replaces） |
| `schema/tags.yaml` | 新增 `scenario` 標籤組，以及記憶體、封裝、工作負載的新標籤 |
| `catalog_candidates.csv` | 17 份 edge 候選文件。是從網路搜尋找來的，標題、會議、數字都還要打開原文確認，才能搬進 `catalog.csv` |

四個維度的主要改動：

- **運算 die**：新增 TOPS/W、die 功耗、MAC 數、時脈、SRAM 頻寬。reticle 上限降成 P3。
- **切分方式**：新增封裝內記憶體 die 數、平台最多可外掛幾顆 chiplet、論文找到的最佳切分數。3D 堆疊快取降成 P3。
- **記憶體**：`hbm_*` 改成通用的 `mem_*`（總容量、總頻寬、匯流排寬度、pin 速率、pJ/bit），以 LPDDR 為主。新增 flash 讀取頻寬和每 GB 成本。HBM 專用參數全部降成 P3。
- **D2D**：參數大致不變，優先序改成 pJ/bit、每 mm 邊長頻寬優先，因為 edge 多用有機基板。新增 module lane 數和 PHY 面積。

## 2. 舊資料怎麼處理

- **數字不刪。** 已用 `tools/migrate_edge.py` 依 `replaces` 改名（19 列換了 id），並補上 `value_kind` 初稿（人工複核時一併確認）。
- **catalog 補 scenario 標籤，並調整優先級：**

| scenario | 文件 | 處理 |
|---|---|---|
| edge | PAPER-SIMBA、PAPER-CAMBRICON-LLM | 照用，edge 的核心參考 |
| generic | SPEC-UCIE-*、SPEC-BOW-2.0、SPEC-AIB、PAPER-CHIPLET-ACTUARY、PAPER-GEMINI、BOOK-LAU-CHIPLET、WP-TSMC-3DFABRIC | 照用。UCIe 改成優先抄 standard package 的數字；TSMC 改成優先看 InFO |
| datacenter | WP-AMD-CDNA3、WP-INTEL-GAUDI3、WP-NV-BLACKWELL、PAPER-HECATON、SPEC-JEDEC-HBM3/4、SPEC-CXL-3、PAPER-ECTC23-COWOSL、兩張案例卡 | 留作對照，不再優先收 |
| generic（P3） | PAPER-AMD-ISCA21、SPEC-BOW-MEM-1.0 | 延後 |

## 3. 優先順序怎麼定

- **參數**：P1 是 DSE 第一版一定要有的，也就是直接進效能、能耗、成本公式的數字。P2 讓模型更準。P3 只當參考。
- **文件**：先收「涵蓋最多 P1 缺口、且拿得到」的文件。同等條件下，論文實測 ＞ 規格 ＞ 論文假設 ＞ 白皮書。
- 等 DSE 有第一版結果，改用敏感度排序：哪個參數一變、最佳設計就跟著換，那個參數就優先補、優先複核。

## 4. 檢索：包成工具，讓 harness 可以呼叫

分兩步做。核心邏輯只寫一份。

1. **`tools/kb.py`（Python CLI，輸出 JSON）**：先讓人和腳本都能用。
2. **包成 MCP server**：Claude Code 這類 harness 和 Tack 外掛都能直接呼叫，底層呼叫同一份 `kb.py` 函式。

草擬的工具介面：

| 工具 | 輸入 | 回傳 |
|---|---|---|
| `kb_list_params` | `dimension`、`priority`（可選） | 參數 id、單位、用途、優先級 |
| `kb_query` | `parameter`，加上可選的 `scenario`、`condition` 關鍵字、`verified_only`（預設 true） | 符合的數值列表，每筆附 `num_id`、`doc_id`、頁碼、原文、是否已複核 |
| `kb_get` | `num_id` 或 `doc_id` | 單筆數字或單份文件的完整紀錄 |
| `kb_gaps` | `dimension`（可選） | 還缺數字的參數（就是現在 check.py 的統計） |

幾個原則：

- **預設只回已複核的數字**，要看草稿資料得明確指定，這樣規則 7（論文只用已複核數字）由工具保證。
- **每筆回傳都帶出處**，agent 引用時可以追回原文。
- **工具只讀不寫**。新增數字仍走 `incoming/` 加上檢查的流程（PIPELINE-PLAN §4.1）。

**要先問學長**：Tack 外掛怎麼呼叫外部工具，是 MCP、Python import，還是 HTTP？這會決定第 2 步的包法。

## 5. 時程

| 階段 | 做什麼 |
|---|---|
| 現在 | 學長確認兩份 schema 草案。確認候選文件的連結與標題，搬進 catalog |
| 第一階段 | 依新 schema 抽四個維度的 P1 數字；先拿 NN-Baton、Monad、UCIe standard package、LPDDR5X。轉換舊資料。人工複核 P1 數字 |
| 第一階段尾 | `kb.py` 第一版，先支援 `kb_query` 和 `kb_gaps` |
| 第二階段 | 改其他維度（封裝、成本、熱與功耗、產品整體、工作負載）。規則、收件匣、合併照 PIPELINE-PLAN 做 |
| 第三階段 | 包成 MCP，接上 Tack 外掛 |

## 6. 待決定

1. 學長同意這兩份 schema 草案嗎？要不要增減參數？
2. edge 的功耗範圍要不要訂一個明確的上限（例如 ≤ 75 W）？這個上限也會變成文件收不收的標準。
3. Tack 外掛呼叫工具的方式（見 §4）。

## 7. 2026-11-10 上線狀態

| 項目 | 狀態 |
|---|---|
| schema 改 edge 版（加 workload_ref 的 edge LLM 參數、device_power_budget） | ✅ |
| 舊資料轉換、補 value_kind、catalog 補 scenario 與 P1～P3 | ✅ |
| 驗證器：格式、單位、範圍規則（rules.yaml，18 條，含自我測試）、重複與衝突、出處（87/87 通過） | ✅ |
| add_numbers.py 入庫前強制驗證 | ✅ |
| 檢索 `tools/kb.py` 與 MCP server `tools/kb_mcp.py`、`.mcp.json` | ✅（stdio 實測通過；Claude Code 重新載入後要核准） |
| 一致性規則（容量＝stack 數×每 stack、頻寬公式） | ⬜ 需要結構化的 product 欄位 |
| 抽數字 pipeline（Claude Code 無頭模式、A/B 兩次獨立抽取、比對、出處、驗證後入庫） | ✅ 2026-11-10 |
| 抽 NN-Baton、Monad、Expert Streaming | ✅ 入庫 59 筆（N0088～N0146），15 筆待人看，38 條引用線索；約 $2.9 |
| 評測 30 題 | ✅ retrieval 30/30；agent 29/30（唯一失敗是評分關鍵字漏判，已修） |
| 抽 LPDDR5X 規格、UCIe standard package 論文 | ⬜ 需要 JEDEC 註冊、學校帳號 |
| 人工複核 | ⬜ 0/87 |
