你在幫 chiplet 知識庫檢討「標籤清單該怎麼切」。這次只讀、不寫任何檔案。

文件：{doc_id}（{title}），PDF 在 `pdfs/{stem}.pdf`，共 {pages} 頁。

## 背景

知識庫是給 Tack 用的。Tack 是掛在 agent harness 上的經驗層，服務兩種決策：

1. **執行期的 KV／context 決策**：前文要保留、量化、逐出、重用，稀疏注意力，context 壓縮。
2. **設計期的硬體 DSE**：DRAM 技術（LPDDR5X、LPDDR6、HBM3E…）、KV 精度、記憶體容量與頻寬、chiplet 切分、D2D 介面、封裝。

會影響最佳硬體的工作負載條件：同時跑的 session 數、context 長度、模型大小、batch。
評估方式：LLMCompass、PLENA 模擬器、H100 實機、解析模型（roofline）。

知識庫的主要對象是跑 LLM 的嵌入式／edge AI 加速器，資料中心只當對照。

## 步驟

1. 讀 `schema/tags.yaml`（現有標籤）與 `schema/dse_dimensions.yaml` 的維度名稱。
2. 讀這份 PDF：至少讀摘要、引言、方法概要、實驗設定與結論（大約前 8 頁加最後 2 頁）。
3. 回答下面的問題。

## 要回答的事

- `existing_tags`：現有標籤裡，哪些適用於這份文件（只能用 tags.yaml 裡的 id）。
- `decisions`：這份文件實際在做或在比較哪些「設計決策」。每項寫：
  - `decision`：決策名稱
  - `options`：文件比較了哪些選項
  - `serves`：服務 Tack 的哪一種決策（`kv_runtime`／`hw_dse`／`both`／`neither`）
  - `evidence`：`"PDF p.N"`
- `proposed_tags`：現有標籤**表達不了**、但對查找這份文件或做上面那些決策有用的新標籤，最多 4 個。每個寫：
  - `group`：放在既有的哪一組，或新組名
  - `id`：小寫加底線
  - `label`：中文名稱
  - `definition`：一句話定義
  - `why`：沒有這個標籤時，agent 會查不到什麼
- `too_coarse`：現有標籤裡，用在這份文件時太粗、應該再細分的（寫出標籤 id 和建議怎麼分）。

原則：標籤要對應「決策」或「查找條件」，不要對應文章主題。寧可少提，不要提同義詞。

## 輸出

只輸出一個 ```json 區塊：

```json
{{"doc_id": "{doc_id}", "existing_tags": [], "decisions": [], "proposed_tags": [], "too_coarse": []}}
```
