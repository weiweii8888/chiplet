# 知識庫後續規劃：規則、擴充、合併，以及怎麼用現成 agent／LLM

2026-10-29 草案。凡是要改 `schema/` 或 CSV 欄位的項目，都要先跟學長確認（README 規則 4），所以在 §7 列成待決定事項。

## 0. 現況與目標

**現況**：22 份文件、87 個數字，格式是 CSV＋YAML。

- 數字目前靠 AI 抽取，再由 AI 對照頁面圖做一次檢查。
- `check.py` 只檢查格式：參數 id 存不存在、單位對不對、doc_id 有沒有登錄。

**問題**：規模一大，下面四件事會出狀況。

- 靠人和 AI「看」來把關，速度跟不上，也會漏掉。
- 多人或多個 agent 同時加資料，num_id 會撞號、CSV 會衝突。
- 同一參數從不同文件來的多個值，分不清是「互相矛盾」，還是「本來就是不同的設計選項」。
- DSE 要的是「每個參數一個可用的值或範圍」，但目前只有一筆一筆的原始紀錄。

**目標**：

- LLM 只負責「提案」，例如找文件、抽數字、建議規則。
- 規則（程式自動檢查）和人負責「把關」。
- 合併由腳本產生，不手改。

---

## 1. 整體流程：資料分四層

```
L0 原始     pdfs/*.pdf → 每頁文字（兩種抽法）＋頁面圖              不進 git
              │  LLM 抽取（提案）
              ▼
   收件匣   incoming/<誰>-<日期>.yaml                              待檢查
              │  tools/check.py：規則檢查（§2）
              │  tools/add_numbers.py：統一編號、去重（§4.1）
              ▼
L1 紀錄     numbers.csv：一列一個「某文件某頁說了某數字」           只增不改原意
              │  人工複核 → verified_by
              ▼
L2 合併     derived/dse_params.yaml：每個參數＋情境一個值或範圍     腳本產生，不手改
              │  adapter
              ▼
L3 使用     DSE／模擬器的硬體設定檔                                  腳本產生
```

設計原則：

- 每一層都可以從上一層重算。
- 人只動 L1 的 `verified_by`，以及 `schema/` 裡的規則。

---

## 2. 建立規則

規則分五類。前四類是「檢查」，第五類是「合併」（§4）。

| 類型 | 檢查什麼 | 例子 | 現況 |
|---|---|---|---|
| 格式 | 欄位、參數 id、單位、doc_id | `hbm_pin_rate` 的單位必須是 `Gb/s` | 已有（check.py） |
| 出處 | 引句是否逐字出現在標注的那一頁；數值是否出現在引句裡 | N0085 的引句和原文不符 | **已試跑**，見下 |
| 合理範圍 | 數值落在物理上合理的區間 | `hbm_pin_rate` 介於 1～15 Gb/s；`compute_die_area` ≤ 858 mm²（wafer-scale 例外） | 未做 |
| 一致性 | 同一產品的幾個參數之間要符合公式 | 總容量 = stack 數 × 每 stack 容量；總頻寬 ≈ stack 數 × 寬度 × pin 速率 ÷ 8 | 已手算驗證，見下 |
| 合併 | 多個值怎麼變成 DSE 用的一個值 | 見 §4 | 未做 |

### 2.1 試跑結果：出處規則（今天用現有 87 筆試過）

方法：

- 每份 PDF 用兩種方式轉成逐頁文字（pdftotext 版面模式與一般模式）。
- 去掉大小寫、標點和換行斷字後，檢查 `quote` 是否出現在 `location` 標的那一頁。
- 只要任一種抽法找得到，就算通過。

| 結果 | 筆數 | 說明 |
|---|---|---|
| 引句逐字出現在標注頁 | 86 | 通過 |
| 找不到 | 1 | **N0085**：資料寫 "clock frequency"，原文是 "clock speed"。數值 2 TOPS 正確，引句已修正 |
| 數值不在引句裡 | 12 | 全部是單位換算（例如 5.3 TB/s 記成 5300 GB/s）或推算（例如 2.5 mm × 2.4 mm 記成 6 mm²），不是錯誤 |

從試跑看出三件事：

1. **規則抓得到 AI 看圖漏掉的錯。** N0085 在昨天的頁面圖檢查被標 `ok`。AI 看圖比較會核對數值，不太會逐字核對引句，所以這條規則值得變成正式檢查。
2. **只用一種抽法誤報很多。** 單用版面模式時有 10 筆誤報，因為雙欄論文的左右欄會交錯；兩種抽法合用後只剩 1 筆。
3. **「數值在引句裡」這條規則需要新欄位。** 要記原文數值和原文單位（`raw_value`、`raw_unit`），程式才能自動驗證換算，不必靠人讀 `condition` 欄的備註。

### 2.2 試跑結果：一致性規則（手算）

| 產品 | 容量：stack 數 × 每 stack | 頻寬：stack 數 × 1024 bit × pin 速率 ÷ 8 | 與原文差距 |
|---|---|---|---|
| MI300X | 8 × 24 = 192 GB ✓（N0008、N0012、N0014） | 5325 GB/s，原文 5300（N0016） | 0.5% |
| MI325X | 8 × 32 = 256 GB ✓（N0013、N0015） | 6144 GB/s，原文 6000（N0017） | 2.4% |
| MI300A | 8 × 16 = 128 GB ✓（N0054、N0055） | — | — |
| Gaudi 3 | 8 × 16 = 128 GB ✓（N0064、N0066、N0068） | 3686 GB/s，原文 3700（N0070） | 0.4% |

說明：

- Gaudi 3 那一列，也間接支持了 N0067「原文 3.6GHz 應為 3.6 Gb/s」的推斷。HBM2E 的 1024 bit 寬度還沒入庫，要等 JEDEC 規格確認。
- 這條規則現在只能手算。原因是同一份白皮書裡有 MI300X、MI325X、MI300A 三款產品，程式要先知道哪幾列屬於同一款。目前產品名寫在自由文字的 `condition` 欄，程式無法可靠分組，所以需要 §4.3 的結構化情境欄位。

### 2.3 規則寫成資料，不寫死在程式裡

新增 `schema/rules.yaml`。`check.py` 只實作幾種「規則類型」的檢查器，個別規則都放在 YAML：

```yaml
rules:
  - id: R-RANGE-HBM-PIN
    type: range
    param: hbm_pin_rate
    min: 1
    max: 15
    severity: error              # error 擋 commit；warn 只提醒
    why: HBM2 到 HBM4 的 pin 速率都在這區間；超出多半是 GB/Gb 或 GHz 混用
    test:                        # 每條規則附一個該過、一個該擋的例子
      pass: {value: 6.4}
      fail: {value: 6400}
    status: active               # proposed → warn → active
    added_by: 學弟B
    approved_by: 學長

  - id: R-CONS-HBM-CAP
    type: consistency
    group_by: [doc_id, context.product]
    expr: total_hbm_capacity == hbm_stack_count * hbm_stack_capacity
    tolerance: 0.01
    severity: warn
    why: 容量對不上，通常是抄錯產品型號或 stack 數

  - id: R-PROV-QUOTE
    type: provenance
    check: quote_on_page         # 兩種文字抽法任一找得到即通過
    severity: error
```

檢查器只需要四種：`range`、`consistency`、`provenance`、`duplicate`。之後加規則就是加 YAML，不用改程式。

---

## 3. 怎麼擴充新規則

### 3.1 新規則從哪裡來

每抓到一個錯，就問一次：「能不能寫成規則，下次自動抓？」目前抓過的錯：

| 抓到的錯 | 對應規則 |
|---|---|
| N0039 表號記錯（Table 1 → 2） | 出處規則：引句要出現在標注頁；表號可另外比對頁面文字裡的 "Table N" |
| N0085 引句不是逐字 | 出處規則：`quote_on_page`（已試跑） |
| Gaudi 3 SRAM 頻寬前後矛盾（N0073、N0074） | 重複規則：同 doc、同參數、同情境、數值差 > 5% → 列為衝突 |
| 原文寫 3.6GHz 實為 Gb/s（N0067） | 範圍規則，加一致性規則：頻寬公式反推 pin 速率 |
| 卡片寫 Gaudi 2 是單 die，沒有出處 | 卡片規則：`choice` 裡的數字都要能對到某個 num_id |

### 3.2 新規則的生命週期

1. **提案**（`status: proposed`）：任何人都能提，LLM 也能。例如讓 agent 掃整個 numbers.csv，找「看起來可以寫成公式」的參數組合。
2. **試跑**（`status: warn`）：對現有全部資料跑一次，看誤報幾筆。誤報多就調整規則或容差。
3. **生效**（`status: active`、`severity: error`）：學長同意後才能擋 commit。

一條規則同時要附 `why` 和 `test`。`why` 讓之後的人知道它為什麼存在；`test` 防止有人改壞了沒發現。

### 3.3 抽取指引：給 LLM 的「規則」

除了檢查規則，還要有「抽的時候怎麼抽」的指引。這些指引直接寫進 `schema/dse_dimensions.yaml` 的每個參數底下，變成 LLM 的提示：

```yaml
hbm_pin_rate:
  unit: Gb/s
  why: 每 pin 速率（規格值與產品值分開記）
  aliases: [data rate, Gbps/pin, GT/s, "speed bin"]
  pitfalls:
    - 廠商常把 Gb/s 寫成 GHz（Gaudi 3 白皮書即是）
    - 不要和整個 stack 的 GB/s 搞混
```

說明：

- `aliases` 有兩個用途：用 grep 找候選頁（不需要向量資料庫），以及告訴 LLM 這些說法都算同一個參數。
- `pitfalls` 每踩到一次坑就加一條。抽取品質會隨時間變好，而且改的是資料，不是 prompt 散落在各處。

### 3.4 加新參數或新標籤

- 仍照 README 規則 4，先跟學長確認。
- 參數 id 一旦用過就不刪，只標 `deprecated: true` 和 `replaced_by:`，舊資料才不會失效。
- `schema/` 加 `schema_version`，改名時附一支一次性的轉換腳本。

---

## 4. 怎麼合併資料

### 4.1 多人／多 agent 同時新增：收件匣

- 不直接改 `numbers.csv`。每個人或每個 agent 把新數字寫到 `incoming/<誰>-<日期>.yaml`，格式就是現在 `add_numbers.py` 吃的 batch 格式。
- 由一個人（或之後的 CI）定期跑 `check.py incoming/*.yaml`，通過後再跑 `add_numbers.py`。由它統一給 num_id，所以不會撞號，git 也不會在 CSV 上衝突。
- 合併完的 batch 檔移到 `incoming/merged/`，留著當紀錄。

### 4.2 去重與衝突

判斷的 key 是 `(doc_id, parameter, 情境)`。

| 情況 | 處理 |
|---|---|
| key 相同、數值相同 | 重複，拒收（同一個數字在同一份文件出現兩次，只留頁碼較前或表格那一筆） |
| key 相同、數值不同 | **衝突**：兩筆都留，互相在 `ai_check` 註明，進人工複核隊列。Gaudi 3 SRAM 頻寬就是這種 |
| 不同文件、同參數、同情境 | 交叉核對：例如規格書和白皮書都給 MI300X 的頻寬，合併時依來源等級挑（§4.4） |
| 同參數、不同情境 | **不是衝突**，是設計空間。例如 BoW 在有機基板上 25 mm、在矽中介層上 2 mm |

### 4.3 前提：情境要結構化（需學長確認）

現在的 `condition` 是自由文字，人讀得懂，程式讀不懂，所以 §2.2 的一致性規則和 §4.2 的去重都做不了。建議新增欄位：

| 新欄位 | 內容 | 例子 |
|---|---|---|
| `context` | 受控的 key=value，用 `;` 分隔。key 的清單寫在 schema | `product=MI300X;mem=HBM3` 或 `spec=BoW-2.0;pkg=organic;dir=uni` |
| `value_kind` | 這個數字是什麼性質 | `spec_limit`（規格上下限）／`measured`（實測）／`assumed`（論文假設）／`derived`（換算或推算）／`marketing`（廠商峰值） |
| `raw_value`、`raw_unit` | 原文數值與單位 | `5.3`、`TB/s` |

`condition` 欄保留給人讀的補充說明。

為什麼需要 `value_kind`：Hecaton 的 16 GT/s 是論文的假設，Simba 的 0.82 pJ/bit 是實測，BoW 的「< 1 pJ/bit」是規格目標。三者在 DSE 裡的分量完全不同，現在卻沒有欄位區分。

舊的 87 筆，可以讓 LLM 從 `condition` 欄轉出 `context` 和 `value_kind` 的初稿，人再快速掃過。

### 4.4 合併成 DSE 用的值

`tools/merge.py` 讀 `numbers.csv`，產生 `derived/dse_params.yaml`。這個檔案不手改，每個參數依 schema 裡指定的策略合併：

| 策略 | 用在 | 做法 |
|---|---|---|
| `by_grade` | 同一件事的多個來源（例如某產品的頻寬） | 依來源等級挑：spec > paper(measured) > paper(assumed) > whitepaper > textbook > vendor_web；同等級取版本較新的 |
| `range` | 本來就有一個分布的參數（例如 D2D 能耗、defect density） | 輸出 min、典型值、max，並列出各值的出處 |
| `latest` | 規格的版本演進（例如 UCIe 1.1 → 2.0 → 3.0） | 取最新版，舊版保留在歷史裡 |
| `keep_all` | 互相矛盾、還沒解決的 | 全部列出，標 `unresolved: true`；DSE 必須做敏感度分析 |

輸出長這樣：

```yaml
defect_density:
  strategy: range
  context: {node: 7nm}
  values:
    - {value: 0.09, from: N0043, kind: assumed}   # Chiplet Actuary 一般 7nm
    - {value: 0.13, from: N0047, kind: assumed}   # Chiplet Actuary 模擬 Zen3 立項時期
  min: 0.09
  max: 0.13
  release: false          # 有任何一筆未複核就是 false
```

分成兩種輸出：

- `release` 版只用已經填了 `verified_by` 的數字，給論文用。
- `draft` 版包含未複核的數字，給內部探索用。

這樣規則 7（論文只用已複核數字）是由程式保證，不是靠大家記得。

### 4.5 跟其他資料接

- **學弟 A 的 trace**：接點是 `workload_ref` 維度，例如模型設定和每 token 的 KV 大小。trace 那邊提供「實際 context 長度分布」，知識庫這邊提供「HBM 容量和頻寬」，兩者在 DSE 裡相乘或比較。建議兩邊約定共用的模型設定檔，例如 `models/llama2-70b.yaml`，裡面寫層數、KV head 數、精度，避免 5.1 節那種 700 MB 對 330 MB 的落差再發生。
- **模擬器**：每個模擬器寫一支小 adapter，把 `dse_params.yaml` 轉成該模擬器的硬體設定格式。知識庫本身不綁任何模擬器。

---

## 5. 用現成的 agent／LLM：哪一步用什麼

| 步驟 | 建議工具 | 是否現成 | 備註 |
|---|---|---|---|
| 找新文件 | Semantic Scholar、OpenAlex、arXiv 的公開 API，加 LLM 判斷相關性與建議標籤 | API 現成，要寫一支小腳本 | 輸出到 `catalog_candidates.csv`，人挑過才進 catalog。最有用的是「誰引用了 Chiplet Actuary／Simba」這種引用追蹤 |
| PDF 轉文字 | pdftotext（已裝，兩種模式合用） | 現成 | 表格很多的規格書如果效果差，再試 Docling 或 Marker 這類 PDF 轉 Markdown 工具（要另外裝） |
| 找候選頁 | grep `aliases` | 現成 | 文件少於約 200 份前不需要向量資料庫 |
| 抽數字 | Claude Code，加一個專案 skill（`.claude/skills/extract-numbers/`），把 §3.3 的指引、輸出格式、檢查步驟寫進去 | Claude Code 現成，skill 要寫 | 輸出就是 `incoming/` 的 batch YAML。誰來跑結果都一致，也不依賴我這次對話的記憶 |
| 盲抽對答案 | 另一家模型（例如 GPT 或 Gemini），只給 PDF 頁面和參數清單，不給第一次的答案 | 現成，要帳號 | 兩家一致才標 `ai_check: agree`；不一致的優先人工看。這是「雙人輸入」的老方法 |
| 自動檢查 | `check.py`，加上 §2 的規則 | 要擴充 | 純程式，不用 LLM，結果可重現 |
| 人工複核 | `tools/review_queue.py` 排優先序：衝突 > 規則警告 > DSE 第一版會用到的參數 > 其他。每筆自動切出那一頁的圖，並標出引句位置 | 要寫，用 pdftoppm | 人只要看圖、按「對」或「錯」 |
| 規則提案 | 讓 agent 讀 numbers.csv 和過去的錯誤紀錄，提出候選規則 | 現成 | 只能進 `status: proposed` |

**現在不建議用的**：

- LangChain／LlamaIndex 這類框架、向量資料庫、自己微調模型。以目前幾十份文件的規模，grep 加頁碼就夠，框架只會多一層要維護、要除錯的東西。文件超過幾百份，或要做「問答式查詢」時再考慮。

**原則**：

- LLM 的輸出一律先進 `incoming/`，過了規則才進 `numbers.csv`，填了 `verified_by` 才進 release。
- LLM 再準，也只是第一道。

---

## 6. 時程（配合 DAC：摘要 11-11、全文 11-18）

這份規劃和進度報告裡的「下週計畫」平行進行，要拿到的規格書和人工複核照原計畫做。

| 日期 | 做什麼 | 產出 |
|---|---|---|
| 10-30～10-31 | `schema/rules.yaml`；`check.py` 加 `range`、`provenance` 兩種檢查器；對現有 87 筆跑一次 | 規則檢查報告 |
| 11-01～11-04 | `incoming/` 收件匣流程；抽數字 skill；用在新拿到的 JEDEC／UCIe 文件；試一次盲抽對答案 | 新數字 batch、兩家模型一致率 |
| 11-05～11-08 | （學長同意後）加 `context`、`value_kind`、`raw_*` 欄並轉換舊資料；`consistency` 檢查器；`merge.py` 第一版 | `derived/dse_params.yaml` draft 版 |
| DAC 之後 | 自動找文件、`review_queue.py`、表格工具、模擬器 adapter | — |

如果老師決定 chiplet 要趕 DAC，11-05 之後的項目要優先做 `merge.py`。DSE 只需要 release 版的少數參數，其他可以延後。

---

## 7. 需要學長／老師決定

1. **CSV 新欄位**：`context`、`value_kind`、`raw_value`、`raw_unit`。這是 schema 變更，需要學長同意。
2. **人工複核全查或抽查**：README 規則 7 目前是全查。如果改成「兩家模型一致且通過規則的，抽查 20%；抽查錯誤率低於某門檻就整批接受」，速度會快很多，但論文用的數字是否仍要全查，需要決定。
3. **能不能用第二家模型**：需要帳號，可能有費用。
4. **DSE 先接哪個模擬器**：這決定 adapter 先寫哪一支。

---

## 附錄：試跑方法

- 試跑腳本放在 scratchpad，還沒進 repo。正式版會寫進 `check.py` 的 `provenance` 檢查器。
- 文字抽法：`pdftotext -layout` 和 `pdftotext`（一般模式），逐頁切開。
- 比對前做 NFKC 正規化，去掉換行斷字（`-\n`），只保留英數字。
- 引句含 `...` 或 `|` 時，切成多段，每段都要出現在同一頁。
