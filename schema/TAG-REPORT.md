# 標籤檢討報告 2026-11-10

這份是提案，還沒改 `schema/tags.yaml`。依 README 規則 4，新增標籤要先跟學長確認。方法見 [TAGGING-METHOD.md](../TAGGING-METHOD.md)。

## A. 由上而下：Tack 的決策變數有沒有標籤可查

| 標籤 | 組 | 中文 | 出處 | 現況 |
|---|---|---|---|---|
| `kv_retain` | kv_policy | 前文保留策略 | Tack p.4 KV／context manager：保留 | ❌ 缺 |
| `kv_quantize` | kv_policy | KV 量化 | Tack p.4；附件 A2 固定標籤 | ❌ 缺 |
| `kv_evict` | kv_policy | KV 逐出 | Tack p.4；附件 A2 固定標籤 | ❌ 缺 |
| `kv_reuse` | kv_policy | KV 重用（含 prefix 快取） | Tack p.4、p.8 KV 重用 adapter；附件 A2 固定標籤 | ❌ 缺 |
| `sparse_attention` | kv_policy | 稀疏注意力 | Tack p.2、p.9 四個設定之一 | ❌ 缺 |
| `context_compaction` | kv_policy | context 壓縮／摘要 | 附件 A1：trace 要記壓縮事件 | ❌ 缺 |
| `pd_disaggregation` | serving | prefill／decode 分離 | 附件 A2 ③ Splitwise／DistServe；固定標籤 serving 架構 | ❌ 缺 |
| `multi_session` | serving | 多 session 同時服務 | Tack p.2：換 session 數，79% 任務換最佳硬體 | ❌ 缺 |
| `agent_workload` | workload | agent 長 context（多輪、tool 呼叫） | Tack p.1～2 研究主軸 | ❌ 缺 |
| `lpddr` | memory | LPDDR | 附件 A2 固定標籤：記憶體種類 | ✅ 已有 |
| `hbm` | memory | HBM | 附件 A2 固定標籤：記憶體種類 | ✅ 已有 |
| `bandwidth_capacity` | metric | 頻寬與容量 | 附件 A2 固定標籤 | ✅ 已有 |
| `simulator` | method | 模擬器／評估器 | Tack p.6～7：LLMCompass、PLENA | ✅ 已有 |
| `analytical_model` | method | 解析模型（roofline 等） | Tack p.13：roofline × 效率 η | ❌ 缺 |
| `silicon_measured` | method | 實機或下線晶片量測 | Tack：高保真度評估＝模擬或 H100 實機 | ❌ 缺 |

→ 缺 11 個：kv_retain, kv_quantize, kv_evict, kv_reuse, sparse_attention, context_compaction, pd_disaggregation, multi_session, agent_workload, analytical_model, silicon_measured。這些是 Tack 一定會查的決策，**建議全數新增**。

## B. 文獻：逐篇讀 PDF 的提案

已讀 16 份（`schema/tag_mining/`）。

### B1. catalog 漏標（現有標籤適用但沒標）

- `PAPER-EXPERT-STREAMING`：catalog 建議補 edge_embedded
- `PAPER-GEMINI`：catalog 建議補 datacenter
- `PAPER-KIVI`：catalog 建議補 datacenter
- `PAPER-NN-BATON`：catalog 建議補 generic
- `PAPER-SIMBA`：catalog 建議補 datacenter

### B2. 新標籤提案（依提案文件數排序；≥2 份＝候選，1 份＝觀察）

| 標籤 | 組 | 中文 | 定義 | 提案文件 | 和 A 重疊 | 建議 |
|---|---|---|---|---|---|---|
| `multi_session` | workload | 多請求並行 | 同一個模型同時服務多個請求或 session（prefill 和 decode 混在一起、chunked prefill | PAPER-EXPERT-STREAMING, PAPER-VLLM, WP-AMD-CDNA3 | 是 | 已在 A |
| `chiplet_reuse` | partition | chiplet／封裝重用 | 用同一組 chiplet 或同一個封裝組出多個產品等級（例如 1X/2X/4X、中心 die 加不同延伸 die）。 | PAPER-CHIPLET-ACTUARY, PAPER-GEMINI |  | 候選 |
| `phase_disaggregation` | workload | prefill／decode 分離 | 文件把 prefill（受算力限制）和 decode（受頻寬限制）拆開，分配不同的運算資源、平行方式或硬體。 | PAPER-DISTSERVE, PAPER-MOONCAKE |  | 候選 |
| `ddr` | memory | 標準 DDR | 外部記憶體用 DDR3、DDR4 或 DDR5（不是 LPDDR，也不是 HBM）。 | PAPER-EXPERT-STREAMING, PAPER-HECATON |  | 候選 |
| `batch_sweep` | workload | 跨 batch 評估 | 文件在不同 batch（例如 1 與 64）下回報效能、能耗或最佳硬體，可以看出結論對 batch 敏不敏感。 | PAPER-GEMINI, PAPER-SIMBA |  | 候選 |
| `kv_eviction` | kv_policy（新組：執行期 KV 決策） | KV 逐出策略 | KV 快取容量不夠時，用哪種策略（LRU、LFU、依長度或依重要性）決定先丟哪些 block 或 token。 | PAPER-MOONCAKE, PAPER-SGLANG |  | 候選 |
| `cross_die_mapping` | mapping | 跨 die 工作負載切分 | 研究模型的運算或張量沿哪個維度分到多顆 die，以及這個選擇帶來的 D2D 流量與能耗。 | PAPER-NN-BATON, PAPER-SIMBA |  | 候選 |
| `tiered_weight_kv` | memory | 權重／KV 分層存放 | 權重和 KV cache 刻意放在不同種類的記憶體（例如權重放 flash 或容量層、KV 放 DRAM 或頻寬層），並 | PAPER-CAMBRICON-LLM |  | 觀察 |
| `model_accuracy` | metric | 模型精度影響 | 文件有量化硬體或演算法選擇（量化位元數、記憶體錯誤率、壓縮、逐出）對模型精度的影響。 | PAPER-CAMBRICON-LLM |  | 觀察 |
| `weight_precision` | precision | 權重精度比較 | 文件比較了不同權重量化位元數（例如 W8A8 對 W4A16），並報告效能、頻寬或容量上的差異。 | PAPER-CAMBRICON-LLM |  | 觀察 |
| `mixed_process_node` | partition | 異質製程切分 | 同一個封裝裡不同 die 用不同製程節點（例如 IO／host／中心 die 用成熟製程，運算 die 用先進製程）。 | PAPER-CHIPLET-ACTUARY |  | 觀察 |
| `monolithic_baseline` | partition | 有單晶 SoC 對照 | 文件拿單晶 SoC 當基準，量化跟多 chiplet 比起來的差異。 | PAPER-CHIPLET-ACTUARY |  | 觀察 |
| `model_parallel_mapping` | mapping | 模型平行切分（TP／PP） | 文件比較把模型用 tensor parallel、pipeline parallel 或 replication 切到多 | PAPER-DISTSERVE |  | 觀察 |
| `multi_session_serving` | workload | 多請求併發服務 | 工作負載是多個請求依某個到達率同時進來、會排隊，結論和到達率或併發數有關。 | PAPER-DISTSERVE |  | 觀察 |
| `moe_inference` | workload | MoE 模型推論 | 推論的是 Mixture-of-Experts 模型，每個 token 只啟用一部分專家的權重。 | PAPER-EXPERT-STREAMING |  | 觀察 |
| `cross_die_sram_pooling` | mapping（新組：跨 chiplet 的資料放置與搬移方式） | 跨 die 片上記憶體共享池 | 把所有 chiplet 的片上 SRAM 當成一個共享池，每份權重或資料只存一份，要用時靠 D2D 搬過去，用 D2D  | PAPER-EXPERT-STREAMING |  | 觀察 |
| `chiplet_granularity_sweep` | partition | 切分粒度掃描 | 文件在固定總算力或總面積下比較不同 chiplet 數，並給出最佳切分數。 | PAPER-GEMINI |  | 觀察 |
| `mapping_hw_codesign` | method | 映射與硬體共同探索 | 最佳硬體是在同時最佳化 dataflow／層映射（或資料放置）的前提下得到的，而不是先固定映射再比硬體。 | PAPER-GEMINI |  | 觀察 |
| `cross_die_parallelism` | mapping（新組） | 跨 die 的模型切分方式 | 文件比較了把模型的權重、activation 或 attention head 分到多顆 die 的方法（例如 1D 或 | PAPER-HECATON |  | 觀察 |
| `nop_topology` | interconnect（新組） | 封裝內網路拓樸 | 文件比較或指定多顆 die 之間的 NoP 連接拓樸（例如 ring、bypass ring、mesh、2D-torus | PAPER-HECATON |  | 觀察 |
| `kv_quantization` | kv_policy（新組：執行期 KV 決策） | KV 量化／降精度 | 文件比較 KV cache 用多少位元存、怎麼分組量化，或哪些 token 保留全精度。 | PAPER-KIVI |  | 觀察 |
| `model_quality` | metric | 模型品質（準確率／分數） | 文件報告壓縮、量化或逐出之後的任務準確率、F1、ROUGE、perplexity 或 NIAH 檢索率。 | PAPER-KIVI |  | 觀察 |
| `long_context` | workload | 長 context | 文件有在長序列上評估或分析（例如 ≥8K token、LongBench、needle-in-a-haystack）。 | PAPER-KIVI |  | 觀察 |
| `batch_scaling` | workload | batch／同時 session 數掃描 | 文件掃描 batch 大小或同時請求數，並報告記憶體用量、吞吐或延遲隨它的變化。 | PAPER-KIVI |  | 觀察 |
| `heterogeneous_chiplets` | partition | 異質特化 chiplet | 同一封裝內的運算 chiplet 依各自負責的 workload 設計不同的 PE 數、buffer 與 dataflo | PAPER-MONAD |  | 觀察 |
| `in_package_network` | interconnect（新組） | 封裝內網路拓撲 | 文件比較或設計了 chiplet 間的網路拓撲、路由、chiplet 擺放或鏈路頻寬配置（例如 mesh 和 ring） | PAPER-MONAD |  | 觀察 |
| `inter_chiplet_pipeline` | mapping（新組） | 跨 chiplet 層間管線 | 把模型的不同層或不同 workload 分給不同 chiplet，以 pipeline 方式重疊執行，而不是把單一層切到 | PAPER-MONAD |  | 觀察 |
| `kv_prefix_reuse` | kv_policy（新組：執行期 KV 決策） | 前綴 KV 重用 | 跨請求或跨 session 共用相同前綴的 KV（prefix caching），包含命中率、可重用比例，以及重用和重算 | PAPER-MOONCAKE |  | 觀察 |
| `request_trace` | method | 真實請求 trace | 文件提供或使用真實工作負載 trace（抵達時間、輸入／輸出長度、session 或前綴 hash），可以拿來重播或統計 | PAPER-MOONCAKE |  | 觀察 |
| `die_count_sweep` | partition | 固定總算力下掃描 die 數 | 總算力或總 MAC 固定，只改切成幾顆 die，並比較能耗、延遲、面積的文件。 | PAPER-NN-BATON |  | 觀察 |
| `batch_one` | workload_condition | batch=1／單 session 評估 | 評估結果建立在 batch 1 或單一請求串流的條件下。 | PAPER-NN-BATON |  | 觀察 |
| `kv_reuse` | kv_runtime（新組，執行期 KV 決策） | KV 跨請求保留與重用 | 請求結束後保留 KV，讓之後共用前綴或相同內容的請求直接拿來用，不必重做 prefill。 | PAPER-SGLANG | 是 | 已在 A |
| `cache_aware_scheduling` | kv_runtime（新組，執行期 KV 決策） | 快取感知的請求排程 | 排請求或呼叫的順序時，以提高 KV 命中率為目標（例如最長共享前綴優先），而不是 FCFS。 | PAPER-SGLANG |  | 觀察 |
| `prefix_sharing` | workload | 多請求共用前綴 | 工作負載裡有多個請求或呼叫共用相同前綴（system prompt、few-shot 範例、多輪對話歷史、fork 出來 | PAPER-SGLANG |  | 觀察 |
| `multi_hop_nop` | d2d_topology（新組） | 多跳封裝內網路 | 封裝內的 die 用 mesh 這類多跳網路互連，延遲和能耗會隨 hop 數與 die 的位置增加。 | PAPER-SIMBA |  | 觀察 |
| `kv_paging` | kv_policy | KV 分頁／區塊配置 | KV cache 用固定大小區塊按需配置、不必連續存放，並討論區塊大小與碎片。 | PAPER-VLLM |  | 觀察 |
| `kv_sharing` | kv_policy | KV 共享與前綴重用 | 多個序列或請求共用同一段 KV（共用 prefix、parallel sampling、beam search），寫入時 | PAPER-VLLM |  | 觀察 |
| `kv_evict_recover` | kv_policy | KV 逐出與取回 | 記憶體不足時逐出哪些 KV，以及之後取回的方式：offload 到下一層記憶體再搬回，或丟掉後重算。 | PAPER-VLLM |  | 觀察 |
| `d2d_asymmetric_link` | d2d_config（新組：D2D 連結的配置選項，和 d2d_interface 選哪種標準分開） | 非對稱 D2D 連結 | D2D 連結兩個方向可以配不同頻寬（TX/RX slice 數不同，或只走單向），用來對應讀多寫少的流量。 | SPEC-BOW-2.0 |  | 觀察 |
| `unified_memory` | memory | CPU／加速器統一記憶體 | CPU 與加速器共用同一個實體記憶體池，host 與 device 之間不用互相拷貝。 | WP-AMD-CDNA3 |  | 觀察 |
| `low_precision_format` | precision | 低精度數值格式（FP8／INT8／INT4 等） | 文件給出低精度格式的硬體支援、吞吐量倍數，或容量與精度之間的取捨。 | WP-AMD-CDNA3 |  | 觀察 |
| `matrix_unit_granularity` | compute_arch | 矩陣單元粒度 | 文件比較或說明矩陣運算單元的大小與數量（少數大陣列對比大量小核），以及它對輸入頻寬和小 GEMM 利用率的影響。 | WP-INTEL-GAUDI3 |  | 觀察 |
| `bottleneck_crossover` | workload | 瓶頸分界條件 | 文件寫出在什麼工作負載條件（模型大小、batch、context 長度、session 數）下，效能改由頻寬、容量或算力 | WP-INTEL-GAUDI3 |  | 觀察 |

### B3. 太粗、該細分的現有標籤

多份文件各自讀、卻指出同一個標籤太粗，是最強的訊號（≥3 份＝建議細分）。

| 標籤 | 幾份文件說太粗 | 文件 | 建議 |
|---|---|---|---|
| `bandwidth_capacity` | 10 | PAPER-DISTSERVE, PAPER-EXPERT-STREAMING, PAPER-GEMINI, PAPER-HECATON, PAPER-KIVI, PAPER-MOONCAKE, PAPER-VLLM, SPEC-BOW-2.0, WP-AMD-CDNA3, WP-INTEL-GAUDI3 | 建議細分 |
| `kv_cache` | 6 | PAPER-CAMBRICON-LLM, PAPER-DISTSERVE, PAPER-KIVI, PAPER-MOONCAKE, PAPER-SGLANG, PAPER-VLLM | 建議細分 |
| `simulator` | 6 | PAPER-CAMBRICON-LLM, PAPER-DISTSERVE, PAPER-EXPERT-STREAMING, PAPER-HECATON, PAPER-MONAD, PAPER-NN-BATON | 建議細分 |
| `latency` | 6 | PAPER-DISTSERVE, PAPER-HECATON, PAPER-MOONCAKE, PAPER-SGLANG, PAPER-SIMBA, PAPER-VLLM | 建議細分 |
| `on_chip_sram` | 4 | PAPER-EXPERT-STREAMING, PAPER-NN-BATON, PAPER-SIMBA, WP-INTEL-GAUDI3 | 建議細分 |
| `proprietary_d2d` | 4 | PAPER-GEMINI, PAPER-SIMBA, WP-AMD-CDNA3, WP-INTEL-GAUDI3 | 建議細分 |
| `compute_die` | 4 | PAPER-HECATON, PAPER-NN-BATON, PAPER-SIMBA, WP-AMD-CDNA3 | 建議細分 |
| `cost_yield` | 3 | PAPER-CHIPLET-ACTUARY, PAPER-GEMINI, PAPER-MONAD | 建議細分 |
| `dse` | 3 | PAPER-CHIPLET-ACTUARY, PAPER-DISTSERVE, PAPER-MONAD | 建議細分 |
| `dnn_inference` | 3 | PAPER-GEMINI, PAPER-MONAD, PAPER-NN-BATON | 建議細分 |
| `energy` | 2 | PAPER-SIMBA, SPEC-BOW-2.0 | 觀察 |
| `pim` | 1 | PAPER-CAMBRICON-LLM | 觀察 |
| `llm_on_device` | 1 | PAPER-CAMBRICON-LLM | 觀察 |
| `ucie` | 1 | PAPER-EXPERT-STREAMING | 觀察 |
| `llm_inference` | 1 | PAPER-KIVI | 觀察 |
| `generic` | 1 | PAPER-KIVI | 觀察 |
| `interposer_2_5d` | 1 | PAPER-MONAD | 觀察 |
| `hybrid_bonding_3d` | 1 | WP-AMD-CDNA3 | 觀察 |
| `io_die` | 1 | WP-AMD-CDNA3 | 觀察 |
| `bridge` | 1 | WP-INTEL-GAUDI3 | 觀察 |

<details><summary>各文件的細分建議原文</summary>

- `pim`（PAPER-CAMBRICON-LLM）：分成 dram_pim（在 DRAM／HBM bank 旁運算）和 in_storage_compute（在 flash 或儲存端運算）；後者可以再加條件區分 die 上運算還是 controller 端運算。兩者的頻寬來源、錯誤率和面積限制都不同，本文就特別說明自己是 die 上運算，跟 controller 端的 ISC 不一樣（p.3）。
- `kv_cache`（PAPER-CAMBRICON-LLM）：分成 kv_placement_static（設計期決定 KV 放在哪一層、要多大，屬 hw_dse）和 kv_runtime_policy（執行期的保留、量化、逐出、重用、稀疏，屬 kv_runtime）。本文只把 KV 固定放在 DRAM，所以沒標 kv_cache；如果硬標，Tack 查執行期 KV 策略時會撈到這篇。
- `llm_on_device`（PAPER-CAMBRICON-LLM）：把工作負載條件拆成可查的標籤：batch_1（單一 session、單一 batch 的 decode），對應 multi_session（多 session 同時跑）；另外加 context 長度區間（short_ctx，大約 ≤4K；long_ctx）。本文只測 batch=1、序列長度約 1000、模型 6.7B–70B。現在的定義只寫「batch 小」，無法區分 agent harness 常見的多 session 或長 context。
- `simulator`（PAPER-CAMBRICON-LLM）：分成「文件本身提供模擬器」和「文件用哪種方法評估」：eval_cycle_sim（cycle-accurate 模擬）、eval_analytical（roofline 或解析模型）、eval_silicon（實機量測）、eval_rtl_synth（RTL 合成估面積與功耗）。本文用 SSDsim 加上自寫的 NPU cycle-accurate 模擬器、用 roofline 做動機分析、用 65 nm 合成估面積，但沒有提供可重用的模擬器，所以沒標 simulator。
- `cost_yield`（PAPER-CHIPLET-ACTUARY）：拆成 cost_re_yield（製造成本：晶圓、die 良率、封裝良率、KGD 浪費，對應 p.3 式 4–5）和 cost_nre（一次性設計成本與生產量攤提，對應 p.3 式 6–8、p.5 的量產轉折點）。edge 的 die 小，良率好處有限，主要差在 NRE；現在兩種成本混在一個標籤裡，agent 挑不出要的那種。
- `dse`（PAPER-CHIPLET-ACTUARY）：依探索的目標拆開，例如 dse_cost（只看成本）和 dse_perf_energy（看效能、能耗）。這份文件明講不考慮效能與功耗（p.2 的假設），只標 dse 的話，agent 找 LLM edge 的效能 DSE 時會誤撈到它。
- `kv_cache`（PAPER-DISTSERVE）：改成依決策細分：kv_transfer（跨裝置或跨 die 搬 KV，本文的 prefill→decode 傳輸，例如 OPT-66B 在 10 rps 下約需 90 Gbps，見 p.6）、kv_capacity（KV 佔用的容量限制 batch，見 p.6）、kv_quantization、kv_eviction、kv_reuse。目前一個標籤同時涵蓋放置和搬移，Tack 在執行期要決定的「保留／量化／逐出／重用」查不到對應文件。
- `latency`（PAPER-DISTSERVE）：細分成 ttft（首 token 延遲）、tpot（每個輸出 token 的延遲）、slo_goodput（滿足 SLO 前提下的最大請求率）。本文的結論全建立在 TTFT 和 TPOT 分開設 SLO 上；只標 latency 的話，查不到「decode 受頻寬限制，所以 TPOT 由記憶體頻寬決定」這類能直接轉成硬體需求的證據。
- `bandwidth_capacity`（PAPER-DISTSERVE）：拆成 mem_bandwidth、mem_capacity、interconnect_bandwidth。本文講的頻寬是 GPU 之間的互連（NVLink 600 GB/s 對比跨節點 25 Gbps），容量指的是 GPU 記憶體能不能放下權重和 KV。混在一起時，agent 會把互連的數字誤當成 DRAM 頻寬。
- `simulator`（PAPER-DISTSERVE）：拆成 analytical_model（roofline 或排隊論，例如本文的 M/D/1 和附錄 A 的 GEMM 延遲模型）、simulator（例如 LLMCompass、PLENA，或本文的離散事件模擬器）、real_hw_measurement（例如 H100、A100 實機）。本文三種都有，而且附錄 Table 2 驗證模擬器和實機誤差小於 2%（p.12）；Tack 需要依評估方式篩選文件。
- `dse`（PAPER-DISTSERVE）：拆成 hw_dse（硬體設計空間）和 deployment_search（固定硬體下搜尋平行度與擺放）。本文的 Algorithm 1 和 2 屬於後者，所以這次沒有標 dse；如果不拆，查硬體 DSE 的 agent 會撈到部署層的搜尋。
- `on_chip_sram`（PAPER-EXPERT-STREAMING）：分成 sram_resident（權重或 KV 常駐片上，SRAM 就是主要記憶體）和 sram_streaming_buffer（片上 SRAM 只當串流緩衝，權重放在外部 DRAM，用到才搬進來）。這篇屬於後者：on_chip_sram 的定義是「片上 SRAM 為主要記憶體」，套在這篇並不準確，兩種設計需要的容量和頻寬也完全不同。
- `simulator`（PAPER-EXPERT-STREAMING）：依評估方式分成 cycle_accurate_sim（RTL 或 cycle-accurate 模擬）、analytical_model（roofline 或行為層級模擬）、silicon_measured（實測測試晶片或實機）。這篇用 5nm 2×2 測試晶片和 RTL 合成結果去校正行為層級模擬器，再拿那個模擬器做 DSE。Tack 要區分 LLMCompass、PLENA、實機、roofline 這幾種評估方式，現在的標籤分不出來。
- `ucie`（PAPER-EXPERT-STREAMING）：分成 ucie_standard（UCIe-S，有機基板）和 ucie_advanced（UCIe-A，中介層或橋接）。這篇 p.4 兩種的數字都有引用，DSE 又以「UCIe x32 module」當頻寬單位。edge 以 UCIe-S 為主，不分開的話查到的數字常常不適用。
- `bandwidth_capacity`（PAPER-EXPERT-STREAMING）：至少分成 bandwidth（再註明是外部記憶體還是 D2D）和 capacity 兩個。這篇的核心結論就是片上容量、DDR 頻寬、D2D 頻寬三者之間的取捨，合在一個標籤裡表達不出來。
- `bandwidth_capacity`（PAPER-GEMINI）：分成 mem_bandwidth_capacity（外部 DRAM 頻寬與容量）、interconnect_bandwidth（NoC／D2D 頻寬配置）、on_chip_buffer（每核或每 die 的 SRAM／GLB 容量）。Gemini 三種都當 DSE 參數掃，合在同一個標籤裡查不出是哪一種。
- `cost_yield`（PAPER-GEMINI）：依 dse_dimensions 的 cost 參數分成 silicon_yield_cost（die 面積與良率）、package_cost（基板面積 × 縮放係數 × 單價）、nre_cost（重用、攤提）。Gemini 的 MC 量化了 silicon、DRAM、package 三項，NRE 只做定性討論；不分開的話，agent 會以為它有 NRE 數字。
- `dnn_inference`（PAPER-GEMINI）：分成 dnn_cnn 和 dnn_transformer_nonllm（非自迴歸、沒有 KV cache）。Gemini 預設工作負載是 Transformer，結果比 CNN 結果更接近 LLM prefill，但跟 decode 和 KV 無關；混在一起時，agent 不知道哪些結果能拿來推估 LLM。
- `proprietary_d2d`（PAPER-GEMINI）：按訊號方式或能耗模型分，不按廠商分：d2d_clock_forwarded（GRS、UCIe 類，按位元計能耗）和 d2d_serdes（時脈內嵌，閒置也耗電）。目前 NV-HBI（中介層、高頻寬）和 Simba 的 GRS（有機基板）都歸在同一個標籤，用在有機基板的 edge 設計時無法區分。
- `simulator`（PAPER-HECATON）：按評估的可信度拆開，對應 Tack 的幾種評估方式：analytical_model（roofline 或解析公式）、perf_simulator（Timeloop、LLMCompass、PLENA 這類效能或週期模擬）、rtl_synthesis（RTL 合成加 PrimeTime 估功耗）、silicon_measured（實機或量產晶片實測）。本文同時用了解析推導、RTL 合成、Timeloop 驗證和 Ramulator，只標一個 simulator 會讓 agent 分不出這些數字可信到什麼程度。
- `latency`（PAPER-HECATON）：拆成 latency_link（ns 等級的 D2D 鏈路或記憶體存取延遲，例如本文 α=10ns、Table IV）和 latency_end_to_end（每次 iteration、每個 token、TTFT/TPOT 這類系統層級延遲）。本文的主要指標是一次訓練 iteration 的延遲，跟執行期 KV 決策要看的 token 延遲不同類，混在一起查會互相干擾。
- `bandwidth_capacity`（PAPER-HECATON）：至少拆成 bandwidth 和 capacity。本文兩者分開比較：一邊掃 DRAM 頻寬（Fig.10），另一邊討論每顆 die 的 SRAM 容量需求和 overflow（p.8 到 p.10）。合在一個標籤裡，agent 分不出這份是在講頻寬還是容量。
- `compute_die`（PAPER-HECATON）：分成 homogeneous_compute（多顆相同的運算 die 往外擴，本文最多 1024 顆）和 heterogeneous_compute（運算 die 搭配不同功能的 die，例如 host SoC 加 NPU chiplet），跟 dse_dimensions.yaml 裡 partition 的 example_values 對齊。edge 比較常見的是後者，混在一起查會被資料中心或 waferscale 的同質擴展淹沒。
- `kv_cache`（PAPER-KIVI）：現在的定義是「放置與搬移」，但實際會被拿來標所有和 KV 有關的文件。建議把它收窄成 kv_placement（放在哪一層：SRAM、DRAM、flash、卸載），演算法類的執行期決策移到新的 kv_policy 組：kv_quantization、kv_eviction、kv_reuse（前綴或跨 session 重用）、sparse_attention、context_compression，正好對應 Tack 的保留、量化、逐出、重用、稀疏、壓縮。本文只能標 kv_quantization。
- `bandwidth_capacity`（PAPER-KIVI）：拆成 capacity 和 bandwidth。本文只量了容量（峰值記憶體少 2.6 倍、batch 大 4 倍），沒有量頻寬。合在一起時，agent 會以為這份文件有頻寬數字；硬體 DSE 裡，容量決定 LPDDR 顆數，頻寬決定 DRAM 技術，兩者是不同的決策。
- `llm_inference`（PAPER-KIVI）：依階段拆成 llm_prefill 和 llm_decode（或另加一個階段標籤）。KIVI 在 prefill 時用精確的 KV，只有 decode 時讀量化後的 KV；它的效益來自 decode 受記憶體限制這一點。兩個階段的瓶頸不同，硬體結論也不同。
- `generic`（PAPER-KIVI）：現在把「方法不限場景」和「數字在哪個平台量的」混在一起。KIVI 的方法是通用的，但效率數字全部來自 A100 80GB、batch 數百，用 scenario=edge 查詢時會一併被當成 edge 參考。建議 catalog 的 scenario 只描述方法適用的範圍，另外加 eval_platform 組（例如 gpu_datacenter、edge_soc、simulator、analytical），或在數字的 condition 欄強制記錄平台。
- `interposer_2_5d`（PAPER-MONAD）：分成 passive_interposer 與 active_interposer。Monad 提到兩者的成本差很多：中介層成本在被動中介層佔總成本 15% 以上，在主動中介層佔 30% 以上（p.3）。主動中介層的 router 放在中介層內，能省下 bump 和 I/O 面積（p.2, p.6），兩者是不同的設計選項。
- `cost_yield`（PAPER-MONAD）：分成 fabrication_cost（die、bonding、基板／中介層的單顆製造成本）與 nre_cost（一次性設計成本與重用攤提）。Monad 只算製造成本（ICKnowledge 28nm），NRE 只說模型可以延伸（p.3）。edge 用 chiplet 的理由主要是 NRE 與重用，用同一個標籤會讓 agent 誤以為這份文件能回答 NRE 問題。
- `simulator`（PAPER-MONAD）：依評估精度分成 analytical_model（解析或 roofline 式，例如 Monad 用 TENET 加 Accelergy，與 ScaleSim 比對誤差在 9.8% 內）、cycle_sim（cycle 級模擬，例如 ScaleSim、LLMCompass、PLENA）、hw_measured（實機量測，例如 H100）。Tack 需要知道數字是從哪種精度的評估來的。
- `dnn_inference`（PAPER-MONAD）：分成 cnn_inference 與 transformer_nonautoregressive（BERT 類 encoder 或單一 Transformer block 的矩陣乘，沒有 decode 也沒有 KV cache）。Monad 的 Transformer 實驗只有 BERT-large 的矩陣乘形狀（p.7），不能標 llm_inference 或 kv_cache。細分後 agent 才知道這些結果最多只能參考 prefill 或矩陣乘階段，不能當成 decode 或 KV 的證據。
- `dse`（PAPER-MONAD）：依搜尋範圍分成 dse_architecture（PE、buffer、dataflow）、dse_integration（封裝、網路、擺放）與 dse_co_opt（兩者聯合）。Monad 的主要結論就是聯合最佳化比只搜其中一邊更好（p.7 圖 8），只用一個 dse 標籤表達不出這個差別。
- `kv_cache`（PAPER-MOONCAKE）：目前「放置與搬移」把多種執行期決策混在一起。建議分成 kv_tiering（HBM／DRAM／SSD 分層放置與傳送）、kv_prefix_reuse、kv_eviction、kv_compression（量化／稀疏注意力／token 篩選）；本文主要落在前三個。
- `latency`（PAPER-MOONCAKE）：本文講的是服務層 SLO 延遲（TTFT、TBT，單位是秒），和 d2d_latency 這類硬體存取延遲（ns）混在同一個標籤。建議分成 serving_latency（TTFT／TBT）與 hw_access_latency（記憶體／D2D 延遲，ns）。
- `bandwidth_capacity`（PAPER-MOONCAKE）：本文的「容量」指 KV 快取容量和命中率，「頻寬」指節點間 RDMA 網路頻寬（800 Gbps），都不是加速器記憶體頻寬。建議分成 mem_capacity、mem_bandwidth、interconnect_bandwidth，避免 agent 以為能在這裡找到記憶體頻寬數字。
- `simulator`（PAPER-NN-BATON）：改成評估方法的三分法：analytical_model（解析／閉式模型，例如 roofline、本文的 C³P）、cycle_or_trace_sim（LLMCompass、PLENA 這類模擬器）、silicon_measured（實機量測，例如 H100）。本文是解析能耗面積模型，runtime 只用利用率估算，跟 cycle-level 模擬的可信度不同，引用時要能分開。
- `compute_die`（PAPER-NN-BATON）：分成 homogeneous_compute（同一顆運算 chiplet 複製 N 顆，例如本文、Simba）和 heterogeneous_compute（host SoC 加上外掛加速 chiplet，或 NPU 加記憶體 chiplet），對應 dse_dimensions 裡 partition 的 example_values。
- `on_chip_sram`（PAPER-NN-BATON）：現在的定義是「SRAM 為主要記憶體」，本文用的是 DRAM 前面的多層 SRAM buffer，套不上。建議分成 sram_primary（權重和 KV 全放片上）與 sram_hierarchy_sizing（決定各層 buffer 容量）。
- `dnn_inference`（PAPER-NN-BATON）：分成 cnn_inference 與 transformer_inference（非 LLM 的 transformer）。本文只評估 CNN（AlexNet、VGG-16、ResNet-50、DarkNet-19），沒有 attention 也沒有 KV。agent 要先知道這點，才能判斷結論能不能用到 LLM decode。
- `kv_cache`（PAPER-SGLANG）：現在一個標籤同時涵蓋放置、搬移和所有執行期策略。建議拆成 kv_placement（放在哪一層記憶體、offload／搬移，服務硬體 DSE）、kv_reuse、kv_eviction、kv_quantization（KV 精度）、kv_compression（稀疏注意力、context 壓縮）。這篇只屬於 kv_reuse 和 kv_eviction，但現在會和 KV offload 到 DRAM 或 flash 的硬體論文混在一起。
- `latency`（PAPER-SGLANG）：建議拆成 ttft（首 token 延遲，主要由 prefill 決定，KV 重用改善的就是這個）、decode_latency（每 token 延遲，主要受記憶體頻寬限制，是硬體 DSE 在看的）、e2e_latency（整個程式或請求的總延遲）。另外 metric 組沒有 throughput，這篇的主要指標 programs/s、tokens/s 沒有標籤可用。這篇三種延遲都有報：首 token 延遲 1.7×、總延遲 3.7×、Fig.8b。
- `compute_die`（PAPER-SIMBA）：分成 compute_die_homogeneous（同一顆運算 die 複製多顆來放大，同一顆 die 也可以單獨出貨，例如 Simba 單顆是 edge 規模、36 顆是資料中心規模）和 compute_die_heterogeneous（host SoC 加外掛加速 chiplet 這類異質組合）。兩者在 DSE 裡的切分決策和成本理由（重用 vs 整合）不一樣。
- `on_chip_sram`（PAPER-SIMBA）：分成 sram_resident（權重常駐在片上或分散的 SRAM，封裝內沒有 DRAM，像 Simba）和 sram_as_buffer（SRAM 只當 DRAM 前面的 buffer 或快取）。跑 LLM 時前者容量通常放不下權重和 KV，agent 要能直接排除或特別當對照。
- `latency`（PAPER-SIMBA）：分成 link_latency（D2D 或 NoC 每跳的 ns 級延遲，例如 Simba 的 NoP 20 ns/hop、NoC 10 ns/hop）和 inference_latency（端到端推論延遲，例如 ResNet-50 batch 1 是 0.50 ms）。兩者單位和用途都不同，混在一起時，agent 用 metric 篩選會拿到錯誤層級的數字。
- `energy`（PAPER-SIMBA）：分成 interconnect_energy（pJ/bit，D2D 或記憶體 I/O）和 compute_energy（pJ/op、TOPS/W）。Simba 兩種都有（0.82–1.75 pJ/bit 和 0.11–0.16 pJ/op），而 DSE 的功耗模型要分開代入這兩種數字。
- `proprietary_d2d`（PAPER-SIMBA）：依訊號方式分成 serial_d2d（少量導線、高速序列，可以跑在有機基板上，例如 GRS 每 pin 11–25 Gbps）和 parallel_d2d（大量導線、低速並列，多半需要中介層或橋接，例如 NV-HBI）。這兩類在 pJ/bit、shoreline 密度、延遲和封裝成本上差別很大，edge 走有機基板時只會考慮前者。
- `kv_cache`（PAPER-VLLM）：改成一組 kv_policy：配置／分頁（kv_paging）、共享與重用（kv_sharing）、逐出與取回（kv_evict_recover），以後再加量化、稀疏或選擇性注意力、壓縮。kv_cache 本身只留給「KV 放在哪一層記憶體」。這份文件同時涉及前三種，只標 kv_cache 時，agent 分不出它講的是哪一種執行期決策。
- `bandwidth_capacity`（PAPER-VLLM）：拆成 capacity 和 bandwidth。這份文件只談容量（KV 容量限制了 batch 大小），沒有給頻寬數字；合在一起會讓找頻寬的 agent 誤查到它。DSE 裡容量和頻寬也是兩個獨立的旋鈕（例如 LPDDR 與 HBM 在兩者上的取捨不同）。
- `latency`（PAPER-VLLM）：拆成硬體存取延遲（ns 等級，D2D／DRAM）和服務層延遲（s/token、TTFT/TPOT、含排隊）。這份文件的 normalized latency 是端到端每 token 延遲，跟 d2d_latency 的 ns 完全不能比。
- `energy`（SPEC-BOW-2.0）：分成 energy_active（滿載時的 pJ/bit，本文 <0.25–1 pJ/bit 依終端方式而定）和 energy_idle（閒置或低流量時的能耗，例如本文說能耗可隨活動量降到約 10% 並定義了 clock gating）。edge 跑 LLM decode 時 D2D 流量時有時無，平均功耗主要看閒置那部分；只標 energy 時，agent 分不出文件給的是滿載數字，還是有閒置或低流量時的行為。終端方式（none/source/double）會讓 pJ/bit 差一倍，建議放在 numbers.csv 的 condition key（例如 term=none|source|double），不要再開標籤。
- `bandwidth_capacity`（SPEC-BOW-2.0）：這份文件的「頻寬」指每條線的速率和每 mm die 邊長的頻寬（2–12+ Tbps/mm），跟記憶體容量無關。建議拆成 capacity（記憶體容量）、bandwidth（總頻寬）、bw_density（每 mm 邊長或每 mm² 的頻寬密度）三個。edge 的 die 小，切多小常常受邊長頻寬限制；合在一起時，agent 用『容量』或『頻寬密度』查都會撈到一堆不相關的文件。
- `bandwidth_capacity`（WP-AMD-CDNA3）：拆成 mem_capacity（放不放得下權重與 KV）和 mem_bandwidth（decode 速度上限）兩個標籤，因為它們對應不同決策。這份文件同時有片上快取頻寬（L2 51.6、LLC 17.2 TB/s）、HBM 頻寬（5.3／6.0 TB/s）、HBM 容量（128～256GB）和封裝間 I/O（896 GB/s），全部標成同一個標籤就分不出來。
- `hybrid_bonding_3d`（WP-AMD-CDNA3）：拆成 logic_on_logic_3d（運算 die 疊在 IO/base die 上，例如這份的 XCD-on-IOD）和 memory_on_logic_3d（SRAM 或 DRAM 疊在運算 die 上）。後者直接關係到 edge 的 KV 容量與頻寬，前者主要影響切分方式。另外，鍵合方式（hybrid bonding 或 microbump）建議放到數字的 condition，不要放進標籤名稱。
- `compute_die`（WP-AMD-CDNA3）：拆成 accel_die（NPU/GPU 運算 die）和 cpu_die（CPU chiplet）。MI300A 同時有 XCD 和 CCD，現有標籤無法表達「host CPU 和加速器放在同一個封裝」，而這正是 edge 常見的 host_soc+accel 切分。
- `io_die`（WP-AMD-CDNA3）：區分單純的 io_die，以及 active_base_die（base die 上放了大型 LLC 和記憶體控制器，運算 die 疊在它上面）。這份文件的 256MB Infinity Cache 在 IOD 裡，用 memory_die 或 on_chip_sram 都會標錯，只標 io_die 又會漏掉「base die 放 LLC」這個設計決策。
- `proprietary_d2d`（WP-AMD-CDNA3）：把同一個私有協定的兩種用途分開：封裝內的 die-to-die（XCD 和 IOD 之間）是一種，封裝之間的 scale-up link（7×x16 Infinity Fabric、32 Gbps）建議另外用 scale_up_link 之類的標籤。這份文件兩種都有，混在一起時，查 D2D 能耗或頻寬密度的 agent 會撈到不相干的板級 link。
- `on_chip_sram`（WP-INTEL-GAUDI3）：拆成 sram_main_memory（SRAM 就是主要記憶體，權重或 KV 全放片上）和 sram_cache（SRAM 當 LLC 或軟體管理的快取，搭配 HBM 或 LPDDR，含 L2／L3 與 per-tensor 配置策略）。Gaudi 3 有 96MB SRAM，但依現有定義不能標，這份文件按 tensor 配置 cache 的作法（對應 KV 放片上還是放 DRAM）因此查不到。
- `bandwidth_capacity`（WP-INTEL-GAUDI3）：拆成 mem_bandwidth 和 mem_capacity。本文 p.16、p.30 把兩者的效果分開講（頻寬決定小模型的速度，容量決定 batch 和能不能避免切分）；合成一個標籤，agent 分不出文件有沒有討論容量的效果。
- `proprietary_d2d`（WP-INTEL-GAUDI3）：定義裡把同一封裝內的 die-to-die（NV-HBI、Infinity Fabric、Gaudi 3 的雙 die 互連）和跨封裝的 chip-to-chip（NVLink-C2C、Gaudi 3 的 24x200GbE RoCE）混在一起。建議拆成 proprietary_d2d（封裝內）和 chip_to_chip_link（跨封裝），不然搜 D2D 能耗或頻寬時會混進 scale-out 的數字。
- `bridge`（WP-INTEL-GAUDI3）：拆成 bridge_in_organic（EMIB 這類，有機基板內嵌橋接，成本較低，edge 可能用得到）和 bridge_in_interposer（CoWoS-L 的 LSI，仍是 RDL 中介層，成本接近 2.5D）。兩者對 edge 的成本判斷差很多。本文只寫「interposer bridge」（p.3），所以給這份文件下 bridge 標籤本身就不確定；本文可能只能歸到後者或標成未知。

</details>

### B4. 文件裡的決策服務哪一種 Tack 決策

hw_dse 82、neither 15、both 15、kv_runtime 15

kv_runtime 很少代表收的文件偏硬體；A 組的 KV 標籤新增後要補 KV 管理論文（附件 A2 ③）。

## C. 由下而上：trace 的 workload 特徵

來源 `traces/stats/2026-11-10.json`，17 個 session。

| 特徵 | 有的 session | 建議 |
|---|---|---|
| 長 context（最大 > 100k token） | 53% | 候選 workload 標籤或 DSE 維度 |
| 觸發過 context 壓縮 | 12% | 分不出差別，先不收 |
| tool 輸出量 > 最大 context 的一半 | 6% | 分不出差別，先不收 |
| 快取命中 > 90% | 82% | 分不出差別，先不收 |
| 用了 subagent | 0% | 分不出差別，先不收 |
| 長任務（> 50 步） | 53% | 候選 workload 標籤或 DSE 維度 |
| tool 時間 > 工作時間 30% | 24% | 候選 workload 標籤或 DSE 維度 |

## D. 現有標籤的涵蓋率

catalog 36 份文件。

| 標籤 | 組 | 文件數 | 檢討 |
|---|---|---|---|
| `lpddr_on_package` | memory | 0 | 0 份：預留中，或刪除 |
| `multi_model` | workload | 0 | 0 份：預留中，或刪除 |

（只列需要檢討的；其他標籤涵蓋率正常。）

