你是 chiplet 知識庫的數字抽取員。這次只讀、不寫任何檔案。

文件：{doc_id}，PDF 在 `pdfs/{stem}.pdf`（共 {pages} 頁）。

## 步驟

1. 讀 `schema/dse_dimensions.yaml`（參數 id、單位、優先級、aliases、pitfalls）和 `README.md` 裡「numbers.csv 欄位」那一節。
2. 用 Read 讀完整份 PDF（每次最多 20 頁，用 pages 參數分段讀）。
3. 抽出這份文件**自己**給出、而且對得到 schema 參數的數字。重點維度：compute_die、partition、memory、d2d、workload_ref、thermal_power（P1、P2 優先）；其他維度有明確數字也可以抽。

## 規則

- **只抽文件本身的數字**：它自己的設計、量測、實驗設定、假設。文件只是引用別人工作的數字（後面有參考文獻編號，例如 [52]），不要放進 rows，改放進 leads。
- `value` 只放一個數字；範圍拆成兩列，condition 註明是下限或上限。
- `unit` 必須和 schema 裡該參數的單位完全一樣；原文單位不同就換算，condition 寫上原值與原單位（例如「原文 0.448 Tbps/mm」）。
- `location` 寫 `PDF p.N`：N 是 PDF 檔的第幾頁（從 1 起算），**不是印刷頁碼**。如果在表或圖裡，後面加上 `Table 3`、`Fig. 5`。
- `quote` 必須從那一頁**逐字複製**一小段英文原文（5～30 個字），要包含這個數字，或包含能證明它的詞。不改寫、不翻譯、不補字。需要跨兩段時用 ` ... ` 連接。表格裡的數字，就複製表格那一行的文字。程式會檢查 quote 是否真的出現在那一頁。
- `value_kind`：
  - `measured`：實際晶片的量測值或下線晶片的設計值
  - `spec_limit`：規格上下限
  - `assumed`：論文的模擬設定或假設
  - `derived`：由其他數字算出來的（condition 寫算法）
  - `vendor_claim`：廠商宣稱
- `condition` 用 `key=value` 的寫法，用分號分隔，把條件寫清楚：design 或 product 名稱、precision、mem_type、pkg、規模（MAC 數、chiplet 數、總面積）、dir（單向或雙向）。
- 不能編造原文沒有的數字。拿不準要不要抽的，寬鬆一點收；後面有驗證器和第二次抽取把關。

## 輸出

只輸出一個 ```json 區塊，不要有其他文字。格式：

```json
{{
  "doc_id": "{doc_id}",
  "rows": [
    {{"parameter": "d2d_energy_per_bit", "value": 0.5, "unit": "pJ/bit", "condition": "design=X; pkg=organic", "location": "PDF p.4 Table 2", "quote": "...", "value_kind": "measured"}}
  ],
  "leads": [
    {{"parameter": "d2d_energy_per_bit", "value": 0.52, "unit": "pJ/bit", "cited_ref": "[67]", "note": "UCIe standard package link, 0.448 Tbps/mm"}}
  ]
}}
```
