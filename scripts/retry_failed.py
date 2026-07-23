#!/usr/bin/env python3
"""重试 OCR 失败的页面"""
import os, sys, base64, time, requests, fitz

API_KEY = os.environ.get("MIMO_API_KEY", "")
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "pdf-books", "争夺欧洲霸权的斗争（1848-1918年）.pdf")
OCR_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "ocr_text")
FAILED = [116, 118, 199, 204, 208, 241, 477, 635]

session = requests.Session()
session.headers.update({"Authorization": f"Bearer {API_KEY}"})

doc = fitz.open(PDF_PATH)
ok = 0
fail = 0

for pn in FAILED:
    fpath = os.path.join(OCR_DIR, f"page_{pn:04d}.txt")
    page = doc[pn - 1]
    pix = page.get_pixmap(dpi=150)
    img_b64 = base64.b64encode(pix.tobytes("png")).decode()

    payload = {
        "model": "mimo-v2.5",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": "这是扫描版书籍的内页。请完整提取所有文字，保持段落结构。只输出文字，不要说明。"}
        ]}],
        "max_tokens": 4096
    }

    for attempt in range(3):
        try:
            r = session.post(f"{API_BASE}/chat/completions", json=payload, timeout=120)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            if text and text.strip():
                with open(fpath, "w") as f:
                    f.write(text)
                ok += 1
                print(f"  ✓ page {pn}: {len(text)} chars")
            else:
                print(f"  ✗ page {pn}: empty response")
                fail += 1
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                print(f"  ✗ page {pn}: {e}")
                fail += 1
    time.sleep(1)

doc.close()

# 重新合并全文
merged = os.path.join(OCR_DIR, "full_text.txt")
with open(merged, "w") as out:
    for f in sorted(os.listdir(OCR_DIR)):
        if f.endswith(".txt") and f != "full_text.txt":
            fpath = os.path.join(OCR_DIR, f)
            with open(fpath) as inp:
                content = inp.read().strip()
                if content and not content.startswith("ERROR"):
                    out.write(content + "\n")

print(f"\n完成: {ok} 成功, {fail} 失败")
print(f"合并全文: {merged}")
