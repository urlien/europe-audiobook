#!/usr/bin/env python3
"""并发 OCR — 5 线程跑 667 页"""
import os, sys, base64, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

API_KEY = os.environ.get("MIMO_API_KEY", "")
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "pdf-books", "争夺欧洲霸权的斗争（1848-1918年）.pdf")
OCR_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "ocr_text")

def ocr_page(pn, page_data):
    """OCR 单页"""
    fpath = os.path.join(OCR_DIR, f"page_{pn:04d}.txt")
    # 跳过已有结果
    if os.path.exists(fpath):
        with open(fpath) as f:
            txt = f.read()
        if txt.strip() and not txt.startswith("ERROR"):
            return pn, "cached", 0
    
    session = requests.Session()
    img_b64 = base64.b64encode(page_data).decode()
    
    payload = {
        "model": "mimo-v2.5",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": "这是扫描版书籍的内页。请完整提取所有文字，保持段落结构。只输出文字，不要说明。"}
        ]}],
        "max_tokens": 4096
    }
    
    try:
        r = session.post(f"{API_BASE}/chat/completions", json=payload,
                        headers={"Authorization": f"Bearer {API_KEY}"},
                        timeout=120)
        r.raise_for_status()
        result = r.json()
        text = result["choices"][0]["message"]["content"]
        if text and text.strip():
            with open(fpath, 'w') as f:
                f.write(text)
            return pn, "ok", len(text)
        else:
            with open(fpath, 'w') as f:
                f.write("ERROR")
            return pn, "empty", 0
    except Exception as e:
        with open(fpath, 'w') as f:
            f.write("ERROR")
        return pn, f"error: {e}", 0

def main():
    import fitz
    os.makedirs(OCR_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    total = len(doc)
    print(f"📖 PDF {total} pages, 5 线程并发 OCR")
    
    # 预渲染所有页面为 PNG bytes
    print("⏳ 预渲染页面...")
    pages = {}
    for pn in range(1, total + 1):
        fpath = os.path.join(OCR_DIR, f"page_{pn:04d}.txt")
        if os.path.exists(fpath):
            with open(fpath) as f:
                txt = f.read()
            if txt.strip() and not txt.startswith("ERROR"):
                continue  # 跳过已有
        page = doc[pn - 1]
        pix = page.get_pixmap(dpi=150)
        pages[pn] = pix.tobytes("png")
    doc.close()
    
    print(f"📝 需要 OCR: {len(pages)} 页 (跳过 {total - len(pages)} 页)")
    
    if not pages:
        print("✅ 所有页面已缓存")
        return
    
    # 并发 OCR
    ok = 0
    fail = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(ocr_page, pn, data): pn for pn, data in pages.items()}
        for future in as_completed(futures):
            pn, status, chars = future.result()
            if status == "ok":
                ok += 1
            elif status == "cached":
                pass
            else:
                fail += 1
            
            done = ok + fail
            if done % 20 == 0 or done == len(pages):
                elapsed = time.time() - start_time
                rate = done / elapsed * 60 if elapsed > 0 else 0
                print(f"  进度: {done}/{len(pages)} ({ok}✓ {fail}✗) {rate:.1f}页/分钟")
    
    elapsed = time.time() - start_time
    print(f"\n✅ OCR 完成: {ok} 成功, {fail} 失败, 耗时 {elapsed/60:.1f} 分钟")
    
    # 合并全文
    merged = os.path.join(OCR_DIR, "full_text.txt")
    with open(merged, 'w') as out:
        for f in sorted(os.listdir(OCR_DIR)):
            if f.endswith('.txt') and f != 'full_text.txt':
                fpath = os.path.join(OCR_DIR, f)
                with open(fpath) as inp:
                    content = inp.read().strip()
                    if content and not content.startswith("ERROR"):
                        out.write(content + "\n")
    print(f"📄 合并: {merged}")

if __name__ == "__main__":
    main()
