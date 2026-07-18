"""
有声书流水线 — MiMo OCR + MiMo TTS
"""
import sys, os, re, json, time, base64, struct, requests

API_KEY = os.environ.get("MIMO_API_KEY", "")
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
PDF_PATH = "pdf-books/争夺欧洲霸权的斗争（1848-1918年）.pdf"
OUTPUT = "output"
OCR_DIR = f"{OUTPUT}/ocr_text"
AUDIO_DIR = f"{OUTPUT}/audio"

session = requests.Session()

def api(url, body, timeout=120):
    try:
        r = session.post(url, json=body, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ERR: {e}")
        return None

# ═══ OCR ═══
def run_ocr(start=1, end=0):
    import fitz
    os.makedirs(OCR_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    total = len(doc)
    end = end or total
    print(f"📖 PDF {total} pages, OCR {start}-{end}")

    for pn in range(start, end + 1):
        fpath = f"{OCR_DIR}/page_{pn:04d}.txt"
        if os.path.exists(fpath):
            with open(fpath) as f:
                txt = f.read()
            if txt.strip() and not txt.startswith("ERROR"):
                print(f"  Page {pn}: cached ✓")
                continue

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

        result = api(f"{API_BASE}/chat/completions", payload)
        if result and "choices" in result:
            text = result["choices"][0]["message"]["content"]
            with open(fpath, 'w') as f:
                f.write(text)
            print(f"  Page {pn}: {len(text)} chars ✓")
        else:
            with open(fpath, 'w') as f:
                f.write("ERROR")
            print(f"  Page {pn}: ✗")

        time.sleep(0.3)

    doc.close()

    merged = f"{OCR_DIR}/full_text.txt"
    with open(merged, 'w') as out:
        for f in sorted(os.listdir(OCR_DIR)):
            if f.endswith('.txt') and f != 'full_text.txt':
                with open(f"{OCR_DIR}/{f}") as inp:
                    out.write(inp.read())
    print(f"✅ OCR done: {merged}")
    return merged

# ═══ TTS ═══
def split_text(text, max_chars=200):
    sents = re.split(r'([。！？.!?\n])', text)
    chunks, cur = [], ""
    for s in sents:
        if not s.strip(): continue
        if s in '。！？.!?\n':
            cur += s
            if len(cur) >= 20:
                chunks.append(cur.strip()); cur = ""
        else:
            if len(cur) + len(s) > max_chars:
                if cur: chunks.append(cur.strip())
                cur = s
            else: cur += s
    if cur.strip(): chunks.append(cur.strip())
    return chunks

def mimo_tts(text):
    try:
        r = session.post(f"{API_BASE}/audio/speech",
            json={"model": "MiMo-V2.5-TTS", "input": text},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=60)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "audio" in ct or "octet-stream" in ct:
            return r.content
        try:
            res = r.json()
            return base64.b64decode(res.get("audio") or res.get("data") or "")
        except: return r.content
    except Exception as e:
        print(f"  TTS ERR: {e}")
        return None

def save_wav(data, path, sr=24000):
    if not data: return False
    if data[:4] == b'RIFF':
        with open(path, 'wb') as f: f.write(data)
        return True
    with open(path, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + len(data)))
        f.write(b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, 1, sr, sr*2, 2, 16))
        f.write(b'data')
        f.write(struct.pack('<I', len(data)))
        f.write(data)
    return True

def run_tts(text_file):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(text_file) as f:
        text = re.sub(r'===.*?===\n?', '', f.read()).strip()
    if not text:
        print("❌ Empty text"); return

    chunks = split_text(text)
    print(f"🎤 TTS: {len(chunks)} chunks")

    all_audio = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip(): continue
        print(f"  [{i+1}/{len(chunks)}] {chunk[:50]}...")
        audio = mimo_tts(chunk)
        if audio:
            all_audio.append(audio)
            print(f"    ✓ {len(audio)} bytes")
        else: print(f"    ✗")
        time.sleep(0.3)

    if all_audio:
        combined = b''.join(all_audio)
        out = f"{AUDIO_DIR}/full_audiobook.wav"
        save_wav(combined, out)
        print(f"✅ TTS done: {out} ({len(combined)} bytes)")

# ═══ MAIN ═══
if __name__ == "__main__":
    print("="*50)
    print("📚 有声书生成流水线")
    print("="*50)

    if not API_KEY:
        print("❌ 设置 MIMO_API_KEY 环境变量"); sys.exit(1)

    print("\n--- Step 1: OCR ---")
    ocr_file = f"{OCR_DIR}/full_text.txt"
    if os.path.exists(ocr_file) and os.path.getsize(ocr_file) > 100:
        print("已有OCR结果，跳过")
    else:
        ocr_file = run_ocr()

    print("\n--- Step 2: TTS ---")
    run_tts(ocr_file)

    print("\n✅ 完成！")
