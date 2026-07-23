#!/usr/bin/env python3
"""
有声书全流程脚本 — OCR + TTS
修正版：使用正确的 MiMo TTS API 格式
"""
import sys, os, re, json, time, base64, struct, requests, argparse
from pathlib import Path

API_KEY = os.environ.get("MIMO_API_KEY", "")
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "pdf-books", "争夺欧洲霸权的斗争（1848-1918年）.pdf")
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "output")
OCR_DIR = os.path.join(OUTPUT, "ocr_text")
AUDIO_DIR = os.path.join(OUTPUT, "audio")

session = requests.Session()
session.headers.update({"Authorization": f"Bearer {API_KEY}"})

# ═══ OCR ═══
def run_ocr(start=1, end=0, workers=1):
    import fitz
    os.makedirs(OCR_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    total = len(doc)
    end = end or total
    print(f"📖 PDF {total} pages, OCR {start}-{end}")

    success = 0
    failed = 0
    skipped = 0

    for pn in range(start, end + 1):
        fpath = os.path.join(OCR_DIR, f"page_{pn:04d}.txt")
        if os.path.exists(fpath):
            with open(fpath) as f:
                txt = f.read()
            if txt.strip() and not txt.startswith("ERROR"):
                skipped += 1
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                r = session.post(f"{API_BASE}/chat/completions", json=payload, timeout=120)
                if r.status_code == 429:
                    wait = min(30, 5 * (attempt + 1))
                    print(f"  Page {pn} rate limited, waiting {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                result = r.json()
                text = result["choices"][0]["message"]["content"]
                if text and text.strip():
                    with open(fpath, 'w') as f:
                        f.write(text)
                    success += 1
                    if success % 10 == 0:
                        print(f"  进度: {success} 页完成, {failed} 失败, {skipped} 跳过")
                else:
                    with open(fpath, 'w') as f:
                        f.write("ERROR")
                    failed += 1
                break
            except requests.exceptions.HTTPError as e:
                if attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)
                    print(f"  Page {pn} HTTP {r.status_code}, retry in {wait}s")
                    time.sleep(wait)
                else:
                    with open(fpath, 'w') as f:
                        f.write("ERROR")
                    failed += 1
                    print(f"  Page {pn} ERR after {max_retries} attempts: {e}")
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)
                    print(f"  Page {pn} err: {e}, retry in {wait}s")
                    time.sleep(wait)
                else:
                    with open(fpath, 'w') as f:
                        f.write("ERROR")
                    failed += 1
                    print(f"  Page {pn} ERR: {e}")

        time.sleep(1)

    doc.close()

    # 合并全文
    merged = os.path.join(OCR_DIR, "full_text.txt")
    with open(merged, 'w') as out:
        for f in sorted(os.listdir(OCR_DIR)):
            if f.endswith('.txt') and f != 'full_text.txt':
                with open(os.path.join(OCR_DIR, f)) as inp:
                    content = inp.read().strip()
                    if content and not content.startswith("ERROR"):
                        out.write(content + "\n")

    print(f"✅ OCR 完成: {success} 成功, {failed} 失败, {skipped} 跳过")
    return merged

# ═══ TTS ═══
def split_text(text, max_chars=1500):
    """按句子分割文本，合并到 max_chars 左右"""
    sents = re.split(r'([。！？.!?\n])', text)
    chunks, cur = [], ""
    for s in sents:
        if not s.strip():
            continue
        if s in '。！？.!?\n':
            cur += s
            if len(cur) >= 100:
                chunks.append(cur.strip())
                cur = ""
        else:
            if len(cur) + len(s) > max_chars:
                if cur:
                    chunks.append(cur.strip())
                cur = s
            else:
                cur += s
    if cur.strip():
        chunks.append(cur.strip())
    return chunks

def mimo_tts(text):
    """调用 MiMo TTS API（正确格式：chat/completions + audio.pcm16）"""
    try:
        r = session.post(f"{API_BASE}/chat/completions",
            json={
                "model": "mimo-v2.5-tts",
                "messages": [
                    {"role": "user", "content": ""},
                    {"role": "assistant", "content": text}
                ],
                "audio": {"format": "pcm16"}
            },
            timeout=60)
        r.raise_for_status()
        data = r.json()
        msg = data["choices"][0]["message"]
        audio_info = msg.get("audio", {})
        if isinstance(audio_info, dict) and "data" in audio_info:
            return base64.b64decode(audio_info["data"])
        return None
    except Exception as e:
        print(f"  TTS ERR: {e}")
        return None

def save_wav(data, path, sr=24000):
    """保存 PCM 为 WAV 文件"""
    if not data:
        return False
    if data[:4] == b'RIFF':
        with open(path, 'wb') as f:
            f.write(data)
        return True
    with open(path, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + len(data)))
        f.write(b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, 1, sr, sr * 2, 2, 16))
        f.write(b'data')
        f.write(struct.pack('<I', len(data)))
        f.write(data)
    return True

def run_tts(text_file, output_name="audiobook"):
    """从文字文件生成音频"""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(text_file) as f:
        text = re.sub(r'===.*?===\n?', '', f.read()).strip()
    if not text:
        print("❌ 文本为空")
        return None

    chunks = split_text(text)
    print(f"🎤 TTS: {len(chunks)} 个片段")

    all_audio = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip() or re.match(r'^[.\s…]+$', chunk.strip()):
            continue
        print(f"  [{i+1}/{len(chunks)}] {chunk[:50]}...")
        audio = mimo_tts(chunk)
        if audio:
            all_audio.append(audio)
            print(f"    ✓ {len(audio)} bytes")
        else:
            print(f"    ✗ 失败")
        time.sleep(0.3)

    if not all_audio:
        print("❌ 没有生成任何音频")
        return None

    combined = b''.join(all_audio)
    out_path = os.path.join(AUDIO_DIR, f"{output_name}.wav")
    save_wav(combined, out_path)
    print(f"✅ TTS 完成: {out_path} ({len(combined)} bytes)")
    return out_path

def run_tts_chapters(text_dir, chapters=None):
    """按章节生成音频"""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(text_dir) if f.endswith('.txt') and f != 'full_text.txt'])

    if chapters:
        # 按章节范围过滤
        filtered = []
        for f in files:
            for ch_start, ch_end in chapters:
                # 从文件名提取页码
                m = re.search(r'page_(\d+)', f)
                if m:
                    pn = int(m.group(1))
                    if ch_start <= pn <= ch_end:
                        filtered.append(f)
                        break
        files = filtered

    print(f"📖 共 {len(files)} 个文件待处理")

    # 按文件合并（每250页一个音频）
    batch_size = 250
    for batch_idx in range(0, len(files), batch_size):
        batch = files[batch_idx:batch_idx + batch_size]
        all_audio = []
        for f in batch:
            fpath = os.path.join(text_dir, f)
            with open(fpath) as fh:
                text = fh.read().strip()
            if not text or text.startswith("ERROR"):
                continue

            chunks = split_text(text)
            for chunk in chunks:
                if not chunk.strip():
                    continue
                audio = mimo_tts(chunk)
                if audio:
                    all_audio.append(audio)
                time.sleep(0.3)

        if all_audio:
            combined = b''.join(all_audio)
            batch_num = batch_idx // batch_size + 1
            out_path = os.path.join(AUDIO_DIR, f"audiobook_part{batch_num}.wav")
            save_wav(combined, out_path)
            print(f"✅ Part {batch_num}: {out_path} ({len(combined)} bytes)")

# ═══ MAIN ═══
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="有声书生成流水线")
    parser.add_argument("--mode", choices=["ocr", "tts", "all"], default="all")
    parser.add_argument("--start", type=int, default=1, help="OCR 起始页")
    parser.add_argument("--end", type=int, default=0, help="OCR 结束页（0=全部）")
    parser.add_argument("--text", type=str, help="TTS 输入文件")
    parser.add_argument("--output", type=str, default="audiobook", help="TTS 输出文件名")
    args = parser.parse_args()

    if not API_KEY:
        print("❌ 设置 MIMO_API_KEY 环境变量")
        sys.exit(1)

    print("=" * 50)
    print("📚 有声书生成流水线")
    print("=" * 50)

    if args.mode in ("ocr", "all"):
        print("\n--- Step 1: OCR ---")
        ocr_file = os.path.join(OCR_DIR, "full_text.txt")
        if os.path.exists(ocr_file) and os.path.getsize(ocr_file) > 100:
            print("已有 OCR 结果，跳过")
        else:
            ocr_file = run_ocr(start=args.start, end=args.end)

    if args.mode in ("tts", "all"):
        print("\n--- Step 2: TTS ---")
        text_file = args.text or os.path.join(OCR_DIR, "full_text.txt")
        if os.path.exists(text_file):
            run_tts(text_file, args.output)
        else:
            print(f"❌ 找不到文本文件: {text_file}")

    print("\n✅ 完成！")
