import sys
sys.path.insert(0, r"D:\CosyVoice")

import urllib.request
import json
import fitz
import base64
import os

api_key = "tp-ck28xttpyqtlkqx91awxqeu4azknkgw4o8npovnhuxloeu6x"
api_url = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"

pdf_path = r"C:\Users\uerling\Desktop\争夺欧洲霸权的斗争（1848-1918年）.pdf"
doc = fitz.open(pdf_path)
output_dir = r"D:\reasonix-project\voice_clone\ocr_text"
os.makedirs(output_dir, exist_ok=True)

# OCR first 20 pages to test quality
pages_to_ocr = list(range(1, 21))

all_text = []
for page_num in pages_to_ocr:
    page = doc[page_num - 1]
    pix = page.get_pixmap(dpi=200)
    img_data = pix.tobytes("png")
    img_b64 = base64.b64encode(img_data).decode()
    
    # Check size (API limit ~10MB base64)
    if len(img_b64) > 10 * 1024 * 1024:
        print(f"Page {page_num}: too large, skipping")
        continue
    
    payload = {
        "model": "mimo-v2-omni",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    },
                    {
                        "type": "text",
                        "text": "这是一本书的内页扫描图。请完整提取页面中的所有中文和英文文字，保持原始段落结构。只输出提取到的文字，不要添加任何说明。"
                    }
                ]
            }
        ],
        "max_tokens": 4096
    }
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    req = urllib.request.Request(api_url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read())
        text = data['choices'][0]['message']['content']
        all_text.append(f"=== 第{page_num}页 ===\n{text}\n")
        print(f"Page {page_num}: {len(text)} chars OK")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        all_text.append(f"=== 第{page_num}页 === ERROR: {body}\n")
        print(f"Page {page_num}: HTTP {e.code}")
    except Exception as e:
        all_text.append(f"=== 第{page_num}页 === ERROR: {e}\n")
        print(f"Page {page_num}: {e}")

doc.close()

# Save all extracted text
output_file = os.path.join(output_dir, "pages_1_20.txt")
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(all_text))

print(f"\nSaved to {output_file}")
print(f"Total: {len(all_text)} pages processed")
