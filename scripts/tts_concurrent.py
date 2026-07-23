#!/usr/bin/env python3
"""并发 TTS — 按章节分片，4 路并行"""
import os, sys, re, json, time, base64, struct, requests, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = ***"MIMO_API_KEY", "")
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
OCR_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "ocr_text")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "audio")

def split_text(text, max_chars=250):
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
    session = requests.Session()
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
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=60)
        r.raise_for_status()
        data = r.json()
        msg = data["choices"][0]["message"]
        audio_info = msg.get("audio", {})
        if isinstance(audio_info, dict) and "data" in audio_info:
            return base64.b64decode(audio_info["data"])
        return None
    except Exception as e:
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

def process_chapter(chapter_num, text_files):
    """处理一个章节（多个文件合并）"""
    all_audio = []
    total_chars = 0
    
    for fpath in text_files:
        with open(fpath) as f:
            text = f.read().strip()
        if not text or text.startswith("ERROR"):
            continue
        total_chars += len(text)
        chunks = split_text(text)
        for chunk in chunks:
            if not chunk.strip(): continue
            audio = mimo_tts(chunk)
            if audio:
                all_audio.append(audio)
            time.sleep(0.2)
    
    if not all_audio:
        return chapter_num, "failed", 0, 0
    
    combined = b''.join(all_audio)
    out_path = os.path.join(AUDIO_DIR, f"chapter_{chapter_num:02d}.wav")
    save_wav(combined, out_path)
    return chapter_num, "ok", len(combined), total_chars

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--start-chapter", type=int, default=1)
    parser.add_argument("--end-chapter", type=int, default=999)
    args = parser.parse_args()
    
    os.makedirs(AUDIO_DIR, exist_ok=True)
    
    # 按章节分组文件（每 30 页一个章节）
    all_files = sorted([f for f in os.listdir(OCR_DIR) if f.endswith('.txt') and f != 'full_text.txt'])
    
    # 按页码分组：每 30 页一组
    chapters = {}
    for f in all_files:
        m = re.search(r'page_(\d+)', f)
        if m:
            pn = int(m.group(1))
            ch = (pn - 1) // 30 + 1  # 每 30 页一章
            if ch < args.start_chapter or ch > args.end_chapter:
                continue
            chapters.setdefault(ch, []).append(os.path.join(OCR_DIR, f))
    
    print(f"🎤 TTS: {len(chapters)} 章, {args.workers} 路并行")
    
    ok = 0
    fail = 0
    total_bytes = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_chapter, ch, files): ch for ch, files in chapters.items()}
        for future in as_completed(futures):
            ch, status, size, chars = future.result()
            if status == "ok":
                ok += 1
                total_bytes += size
                print(f"  ✅ 第{ch}章: {size/1024/1024:.1f}MB ({chars}字)")
            else:
                fail += 1
                print(f"  ❌ 第{ch}章: 失败")
    
    elapsed = time.time() - start_time
    print(f"\n✅ TTS 完成: {ok} 成功, {fail} 失败, {total_bytes/1024/1024:.1f}MB, 耗时 {elapsed/60:.1f} 分钟")

if __name__ == "__main__":
    main()
