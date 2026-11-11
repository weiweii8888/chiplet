# Chiplet 知識庫（edge LLM 版）

目標：把 chiplet 相關的規格書、白皮書、論文與產品案例，整理成「查得到、有出處、能抽數字」的參考資料，
當作 **跑 LLM 的嵌入式／edge AI 加速器** 在 DSE 裡的數字來源（die 數與規格、切分方式、記憶體、D2D 介面）。
資料中心加速器只當對照組。2026-11-09 從資料中心版改為 edge 版，改了什麼見 [EDGE-PLAN.md](EDGE-PLAN.md)。

- 不熟這個主題的人，先讀 [PROGRESS.md](PROGRESS.md)（白話的進度說明）。
- 規則、擴充、合併與 agent 流程規劃見 [PIPELINE-PLAN.md](PIPELINE-PLAN.md)。

## 檔案

| 檔案 | 內容 |
|---|---|
| `catalog.csv` | 文件目錄，一份文件一列 |
| `catalog_candidates.csv` | 候選文件：還沒確認原文，不算入庫 |
| `numbers.csv` | 從文件抽出的數字，一個數字一列 |
| `cards/CASE-*.yaml` | 設計案例卡，一個產品一張（模板：`cards/_template.yaml`） |
| `schema/tags.yaml` | 固定標籤清單（含 `scenario` 場景標籤） |
| `schema/dse_dimensions.yaml` | 設計維度、參數、單位、優先級 P1～P3、別名、常見錯誤 |
| `schema/rules.yaml` | 驗證規則（範圍規則），每條附自我測試 |
| `tools/check.py` | 驗證器：格式、單位、範圍、重複與衝突；`--provenance` 查引句是否在標注頁；`--batch` 檢查待入庫的一批 |
| `tools/add_numbers.py` | 批次入庫：先跑驗證，有錯誤就整批不寫 |
| `tools/kb.py` | 檢索（命令列，輸出 JSON） |
| `tools/kb_mcp.py` | 把檢索包成 MCP server，給 agent harness／Tack 用（註冊在 `.mcp.json`） |
| `tools/migrate_edge.py` | 2026-11-09 改 edge 版的一次性轉換 |
| `tools/extract_prompt.md` | 抽數字指引（給 Claude 的規則：只抽文件自己的數字、逐字引句、PDF 頁碼、value_kind） |
| `tools/extract.py` | 用 Claude Code 無頭模式抽一份 PDF（只准 Read），輸出 `incoming/raw/<doc>-<A或B>.json` |
| `tools/reconcile.py` | 比對 A、B 兩次獨立抽取 → 出處檢查（必要時自動修頁碼）→ 驗證 → 一致的入庫，其他寫 `incoming/<doc>-review.yaml` |
| `tools/pipeline.sh` | 一次跑完抽取、入庫、全庫驗證、評測（建議在 tmux 裡跑） |
| `incoming/` | 待人看的列（`*-review.yaml`）、被引用數字的線索（`*-leads.yaml`）、已入庫的 batch（`merged/`）、每次執行的紀錄 |
| `eval/questions.yaml`、`eval/run_eval.py` | 30 題標準題目；測工具（retrieval）與測 agent 透過 MCP 回答（agent），報告在 `eval/results/` |
| `pdfs/` | 原始 PDF（不進 git） |

## catalog.csv 欄位

- `doc_id`：`類型-簡稱[-版本]`，例 `SPEC-UCIE-3.0`、`PAPER-GEMINI`、`WP-AMD-CDNA3`
- `type`：`textbook`／`spec`／`whitepaper`／`paper`／`case`
- `access`：怎麼取得（公開下載、註冊後下載、填申請表、學校帳號）
- `license_archive`／`license_cite`：能不能存檔、能不能引用
- `tags`、`dimensions`：多個用 `;` 分隔，只能用 `schema/` 裡的 id；**tags 至少要有一個 scenario 標籤**（`edge_embedded`／`edge_mobile`／`edge_automotive`／`generic`／`datacenter`）
- `priority`：`P1`（先收）／`P2`／`P3`（只當對照或延後）
- `status`：`待查連結` → `待收` → `已收` → `已抽數字` → `已複核`

## numbers.csv 欄位

- `num_id`：`N0001` 起流水號（由 `add_numbers.py` 給，不要手填）
- `parameter`：只能用 `schema/dse_dimensions.yaml` 裡的參數 id
- `value`：只放一個數字；範圍或多個值就拆成多列
- `unit`：照 dse_dimensions.yaml 的單位；原文單位不同時，換算後在 `condition` 註明原值
- `condition`：這個數字成立的條件（product、precision、mem_type、pkg、spec、dir 等）
- `location`：頁碼或表號，例 `PDF p.112 Table 5-3`
- `quote`：原文那一句（短，要逐字，`--provenance` 會查）
- `source_grade`：`spec`／`paper`／`whitepaper`／`textbook`／`vendor_web`／`secondary`
- `value_kind`：數字的性質
  - `measured`：實際晶片量測或下線晶片的設計值
  - `spec_limit`：規格上下限或目標
  - `assumed`：論文假設或模擬設定
  - `derived`：換算、推算或推斷，`condition` 要寫怎麼來的
  - `vendor_claim`：廠商宣稱，多為峰值
- `verified_by`：第二個人對過原文後填
- `ai_check`：AI 對照 PDF 頁面圖的檢查結果；只是輔助，不能取代 `verified_by`

## 規則

1. 數字只從原始 PDF 抄，附頁碼或表號；不從新聞、網頁摘要或 AI 轉述抄。
2. 同一參數有規格值和產品值時，兩個都記，用 `condition` 區分。
3. 廠商行銷數字 `value_kind` 記 `vendor_claim`，盡量再找論文或規格交叉核對。
4. 不重複收；新增標籤或參數要先跟學長確認，再改 `schema/`。
5. PDF 原檔放 `pdfs/`，不進 git。
6. 新數字一律寫成 batch YAML，用 `add_numbers.py` 入庫（會先驗證）；改完跑 `python3 tools/check.py --provenance`，沒錯誤再 commit。
7. `extracted_by` 是 AI 的列，一律要有人打開 PDF 對過頁碼與原文，才能填 `verified_by`；論文只用已複核的數字（`kb.py query --mode release`）。

## 檢索

```bash
python3 tools/kb.py params --dimension memory --priority P1     # 有哪些參數
python3 tools/kb.py query d2d_energy_per_bit --scenario edge     # 查數字（附出處）
python3 tools/kb.py gaps --scenario edge                         # edge 還缺哪些 P1 數字、建議讀哪些文件
python3 tools/kb.py get N0037                                     # 單筆完整出處
python3 tools/kb.py search lpddr                                  # 全文搜尋
```

agent 透過 MCP 用同樣五個工具：`kb_list_params`、`kb_query`、`kb_get`、`kb_gaps`、`kb_search`。
