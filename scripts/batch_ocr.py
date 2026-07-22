#!/usr/bin/env python3
"""
批量OCR — 用 MiMo Omni 识别 PDF 扫描页
用法: python3 scripts/batch_ocr.py [起始页] [结束页]
默认: 处理所有缺失页面 (4-667)
"""
import sys, os, json, time, base64, fitz, requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_DIR = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_DIR / "pdf-books" / "争夺欧洲霸权的斗争（1848-1918年）.pdf"
OCR_DIR = PROJECT_DIR / "output" / "ocr_text"

# 读取 API Key
def get_api_key():
    key = os.environ.get("MIMO_API_KEY", "")
    if key:
        return key
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
            return cfg["models"]["providers"]["xiaomi"]["apiKey"]
        except (KeyError, TypeError, json.JSONDecodeError):
            pass
    return ""

API_KEY = get_api_key()
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
OCR_PROMPT = "这是扫描版书籍的内页。请完整提取所有文字，保持段落结构。只输出文字，不要说明。"

session = requests.Session()

def ocr_page(pn):
    """OCR 单页，返回 (page_num, text_or_None)"""
    fpath = OCR_DIR / f"page_{pn:04d}.txt"

    # 跳过已有且有效的文件
    if fpath.exists():
        content = fpath.read_text().strip()
        if content and content != "ERROR":
            return pn, "CACHED"

    # PDF → PNG → base64
    doc = fitz.open(str(PDF_PATH))
    page = doc[pn - 1]
    pix = page.get_pixmap(dpi=150)
    img_b64 = base64.b64encode(pix.tobytes("png")).decode()
    doc.close()

    # 调用 MiMo Omni API
    payload = {
        "model": "mimo-v2.5",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": OCR_PROMPT}
        ]}],
        "max_tokens": 8192
    }

    try:
        r = session.post(
            f"{API_BASE}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=60
        )
        r.raise_for_status()
        result = r.json()
        text = result["choices"][0]["message"]["content"]
        fpath.write_text(text, encoding="utf-8")
        return pn, text
    except Exception as e:
        fpath.write_text("ERROR", encoding="utf-8")
        return pn, f"ERROR: {e}"


def main():
    if not API_KEY:
        print("❌ 未找到 MIMO_API_KEY")
        sys.exit(1)

    start = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 667

    OCR_DIR.mkdir(parents=True, exist_ok=True)

    # 统计已有缓存
    cached = 0
    pages_to_do = []
    for pn in range(start, end + 1):
        fpath = OCR_DIR / f"page_{pn:04d}.txt"
        if fpath.exists():
            content = fpath.read_text().strip()
            if content and content != "ERROR":
                cached += 1
                continue
        pages_to_do.append(pn)

    print(f"📖 PDF OCR 批量处理")
    print(f"   范围: {start}-{end} ({end - start + 1} 页)")
    print(f"   缓存跳过: {cached} 页")
    print(f"   待处理: {len(pages_to_do)} 页")
    print(f"   预计耗时: {len(pages_to_do) * 9 / 60:.0f} 分钟")
    print()

    if not pages_to_do:
        print("✅ 全部已完成！")
        return

    success = 0
    fail = 0
    t0 = time.time()

    # 并发3线程
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(ocr_page, pn): pn for pn in pages_to_do}
        for i, future in enumerate(as_completed(futures), 1):
            pn, result = future.result()
            if result == "CACHED":
                pass
            elif result.startswith("ERROR"):
                fail += 1
                print(f"  ✗ Page {pn}: {result}")
            else:
                success += 1
                chars = len(result)
                print(f"  ✓ Page {pn}: {chars} chars  [{i}/{len(pages_to_do)}]")

            # 每50页报告进度
            if i % 50 == 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                remaining = (len(pages_to_do) - i) / rate
                print(f"  --- 进度 {i}/{len(pages_to_do)} ({i*100//len(pages_to_do)}%) "
                      f"| 成功{success} 失败{fail} "
                      f"| 剩余约{remaining/60:.0f}分钟 ---")

    elapsed = time.time() - t0

    # 合并全文
    print("\n📝 合并全文...")
    merged_path = OCR_DIR / "full_text.txt"
    with open(merged_path, "w", encoding="utf-8") as out:
        for f in sorted(OCR_DIR.glob("page_*.txt")):
            content = f.read_text().strip()
            if content and content != "ERROR":
                out.write(content)
                out.write("\n")
    final_size = merged_path.stat().st_size

    print(f"\n{'='*50}")
    print(f"✅ OCR 完成")
    print(f"   缓存跳过: {cached} 页")
    print(f"   本次处理: {len(pages_to_do)} 页")
    print(f"   成功: {success}")
    print(f"   失败: {fail}")
    print(f"   耗时: {elapsed/60:.1f} 分钟")
    print(f"   全文: {merged_path} ({final_size:,} bytes)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
