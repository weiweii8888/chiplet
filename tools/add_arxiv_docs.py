"""從 arXiv 加入文件：書目資料（標題、作者、日期、版本）一律向 arXiv API 抓，不手打；下載 PDF 到 pdfs/。

安全檢查：抓回的標題必須包含預期關鍵字，否則跳過（防止 arXiv 編號記錯）；下載的檔案必須是 PDF。
已在 catalog 的 doc_id 會略過。

用法：python3 tools/add_arxiv_docs.py kv        （加入下面 KV_DOCS 這一批）
"""
import csv
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "chiplet-kb/0.1 (academic research)"}

# (doc_id, arXiv 編號, 標題必含關鍵字, tags, dimensions, priority, 一句摘要)
# 標籤只用現有的；KV 策略標籤（kv_retain 等）等學長確認新增後，再用 tools/tag_mine.py 重標
KV_DOCS = [
    ("PAPER-VLLM", "2309.06180", "PagedAttention", "datacenter;kv_cache;llm_inference;bandwidth_capacity", "memory;workload_ref", "P1",
     "PagedAttention：KV 分頁管理減少碎片，serving 吞吐的基準（KV 管理 serving）"),
    ("PAPER-SGLANG", "2312.07104", "SGLang", "datacenter;kv_cache;llm_inference", "workload_ref", "P2",
     "RadixAttention：多請求共用 prefix 的 KV 重用（KV 重用）"),
    ("PAPER-MOONCAKE", "2407.00079", "Mooncake", "datacenter;kv_cache;llm_inference;bandwidth_capacity", "memory;workload_ref", "P1",
     "以 KV cache 為中心的 P/D 分離 serving，KV 分層放在 GPU／CPU／SSD（KV 重用、P/D 分離）"),
    ("PAPER-DISTSERVE", "2401.09670", "DistServe", "datacenter;llm_inference;latency", "workload_ref", "P2",
     "prefill 與 decode 分到不同 GPU，依延遲目標配置（P/D 分離）"),
    ("PAPER-KIVI", "2402.02750", "KIVI", "generic;kv_cache;llm_inference;bandwidth_capacity", "memory;workload_ref", "P1",
     "KV cache 2-bit 非對稱量化，免微調（KV 量化）"),
    ("PAPER-H2O", "2306.14048", "Heavy-Hitter", "generic;kv_cache;llm_inference", "workload_ref", "P1",
     "只保留注意力分數高的 heavy-hitter token 與最近 token（KV 逐出）"),
    ("PAPER-STREAMINGLLM", "2309.17453", "Attention Sinks", "generic;kv_cache;llm_inference", "workload_ref", "P2",
     "保留 attention sink 加滑動窗口，無限長串流（KV 保留策略）"),
    ("PAPER-CACHEGEN", "2310.07240", "CacheGen", "generic;kv_cache;llm_inference;bandwidth_capacity", "memory;workload_ref", "P2",
     "KV 壓縮編碼後串流傳輸，降低載入重用 KV 的延遲（KV 重用、壓縮）"),
    ("PAPER-SHADOWKV", "2410.21465", "ShadowKV", "generic;kv_cache;llm_inference;bandwidth_capacity", "memory;workload_ref", "P2",
     "長 context：低秩 key 留 GPU、value 卸載到 CPU，加稀疏注意力（KV 卸載、稀疏）"),
    ("PAPER-KELLE", "2510.16040", "Kelle", "edge_embedded;kv_cache;llm_on_device;on_chip_sram", "memory;workload_ref;compute_die", "P1",
     "edge 上 KV 快取策略與 eDRAM 共同設計（edge KV）"),
    ("PAPER-KVNAND", "2512.03608", "KVNAND", "edge_mobile;kv_cache;llm_on_device;nand_flash", "memory;workload_ref", "P1",
     "KV 放 flash、在 flash 內運算，不用 DRAM 的端側推論（edge KV）"),
    ("PAPER-LLMCOMPASS", "2312.03134", "LLMCompass", "generic;llm_inference;simulator;dse", "compute_die;memory;workload_ref", "P1",
     "LLM 推論硬體評估器，Tack 的高保真度評估之一（評估器）"),
]

NS = {"a": "http://www.w3.org/2005/Atom"}


def fetch_meta(arxiv_id):
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    xml = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    e = ET.fromstring(xml).find("a:entry", NS)
    if e is None or e.find("a:title", NS) is None:
        return None
    title = re.sub(r"\s+", " ", e.find("a:title", NS).text).strip()
    authors = [a.find("a:name", NS).text for a in e.findall("a:author", NS)]
    vid = (e.find("a:id", NS).text or "").rsplit("/", 1)[-1]
    return {"title": title, "authors": authors, "published": e.find("a:published", NS).text[:10],
            "updated": e.find("a:updated", NS).text[:10], "version": re.sub(r"^.*?(v\d+)$", r"\1", vid)}


def main():
    batch = {"kv": KV_DOCS}[sys.argv[1]]
    with open(ROOT / "catalog.csv", newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        fields, cat = rd.fieldnames, list(rd)
    have = {r["doc_id"] for r in cat}
    added = []
    for doc_id, aid, kw, tags, dims, prio, summary in batch:
        if doc_id in have:
            print(f"{doc_id}: 已在 catalog，略過")
            continue
        try:
            m = fetch_meta(aid)
        except Exception as e:
            print(f"{doc_id}: arXiv API 失敗 {e}")
            continue
        time.sleep(3)  # arXiv API 要求間隔
        if not m or kw.lower() not in m["title"].lower():
            print(f"{doc_id}: 標題不符（arXiv {aid} → {m and m['title']}），跳過")
            continue
        stem = doc_id.split("-", 1)[1]
        pdf = ROOT / "pdfs" / f"{stem}.pdf"
        try:
            data = urllib.request.urlopen(urllib.request.Request(f"https://arxiv.org/pdf/{aid}", headers=UA), timeout=120).read()
        except Exception as e:
            print(f"{doc_id}: PDF 下載失敗 {e}")
            continue
        time.sleep(3)
        if not data.startswith(b"%PDF"):
            print(f"{doc_id}: 下載的不是 PDF，跳過")
            continue
        pdf.write_bytes(data)
        au = m["authors"]
        cat.append({k: "" for k in fields} | {
            "doc_id": doc_id, "type": "paper", "title": m["title"],
            "org_or_authors": ", ".join(au[:3]) + (" 等" if len(au) > 3 else ""),
            "year": m["published"][:4], "version": f"arXiv {m['version']}（{m['updated']}）",
            "venue": "arXiv（正式會議待確認）", "url": f"https://arxiv.org/abs/{aid}", "access": "公開（arXiv）",
            "license_archive": "待確認", "license_cite": "可引用", "tags": tags, "dimensions": dims,
            "summary": summary, "priority": prio, "status": "已收", "added_by": "claude",
            "added_date": date.today().isoformat(), "notes": "KV 管理（附件 A2 ③）；書目由 arXiv API 取得"})
        added.append(doc_id)
        print(f"{doc_id}: 加入 「{m['title'][:70]}」 {len(data) // 1024} KB")
    with open(ROOT / "catalog.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(cat)
    # 從候選清單移除已加入的
    cp = ROOT / "catalog_candidates.csv"
    if cp.exists() and added:
        with open(cp, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            cf, cand = rd.fieldnames, [r for r in rd if r["doc_id"] not in added]
        with open(cp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cf, lineterminator="\n")
            w.writeheader()
            w.writerows(cand)
    print(f"ADDED {' '.join(added)}")
    (ROOT / "incoming").mkdir(exist_ok=True)
    (ROOT / "incoming/added_docs.txt").write_text(" ".join(added), encoding="utf-8")


if __name__ == "__main__":
    main()
