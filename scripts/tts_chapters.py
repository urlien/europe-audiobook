#!/usr/bin/env python3
"""TTS 按章节生成 — 4路并行，使用平台内置 MiMo TTS"""
import os, sys, re, json, time, base64, struct, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 平台内置 endpoint，不花用户 tokens
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://api-oc.xiaomimimo.com/v1")

# 从环境变量读取 API key（平台内置）
API_KEY = os.environ.get("MIMO_API_KEY", "")
CHAPTERS_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "chapters")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "audio")

def split_text(text, max_chars=250):
    """将长文本按句子分割成适合 TTS 的短句"""
    sents = re.split(r'([。！？.!?\n])', text)
    chunks, cur = [], ""
    for s in sents:
        if not s.strip():
            continue
        if s in '。！？.!?\n':
            cur += s
            if len(cur) >= 20:
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

def mimo_tts(text, retries=3):
    """调用 MiMo TTS API，返回 PCM 数据"""
    session = requests.Session()
    for attempt in range(retries):
        try:
            r = session.post(
                f"{API_BASE}/chat/completions",
                json={
                    "model": "mimo-v2.5-tts",
                    "messages": [
                        {"role": "user", "content": ""},
                        {"role": "assistant", "content": text}
                    ],
                    "audio": {"format": "pcm16"}
                },
                headers={"Authorization": f"Bearer {API_KEY}"},
                timeout=120
            )
            r.raise_for_status()
            data = r.json()
            msg = data["choices"][0]["message"]
            audio_info = msg.get("audio", {})
            if isinstance(audio_info, dict) and "data" in audio_info:
                return base64.b64decode(audio_info["data"])
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))  # 限流时更长等待
            else:
                print(f"    TTS ERR after {retries} retries: {e}")
    return None

def save_wav(data, path, sr=24000):
    """将 PCM 数据保存为 WAV 文件"""
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

def process_chapter(chapter_file):
    """处理单个章节文件"""
    ch_name = os.path.splitext(chapter_file)[0]
    ch_path = os.path.join(CHAPTERS_DIR, chapter_file)

    with open(ch_path, 'r') as f:
        text = f.read().strip()

    if not text:
        return ch_name, "empty", 0, 0

    chunks = split_text(text)
    all_audio = []
    success = 0

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        audio = mimo_tts(chunk)
        if audio:
            all_audio.append(audio)
            success += 1
        if (i + 1) % 10 == 0:
            print(f"  {ch_name}: {i + 1}/{len(chunks)} segments")
        time.sleep(0.3)  # 平衡速度与限流

    if not all_audio:
        return ch_name, "failed", 0, len(chunks)

    combined = b''.join(all_audio)
    out_path = os.path.join(AUDIO_DIR, f"{ch_name}.wav")
    save_wav(combined, out_path)
    return ch_name, "ok", len(combined), len(chunks)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--chapters", type=str, default="all",
                        help="Chapter files to process, comma-separated or 'all'")
    args = parser.parse_args()

    os.makedirs(AUDIO_DIR, exist_ok=True)

    if not API_KEY:
        print("ERROR: No API key found")
        sys.exit(1)

    all_files = sorted([f for f in os.listdir(CHAPTERS_DIR) if f.endswith('.txt')])
    if args.chapters != "all":
        selected = args.chapters.split(",")
        all_files = [f for f in all_files if any(s in f for s in selected)]

    print(f"🎤 TTS: {len(all_files)} chapters, {args.workers} workers")
    print(f"   API: {API_BASE}")
    print(f"   Output: {AUDIO_DIR}")
    print()

    ok = 0
    fail = 0
    total_bytes = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_chapter, f): f for f in all_files}
        for future in as_completed(futures):
            ch_name, status, size, segments = future.result()
            elapsed = time.time() - start_time
            if status == "ok":
                ok += 1
                total_bytes += size
                print(f"  ✅ {ch_name}: {size / 1024 / 1024:.1f}MB ({segments} segments) [{elapsed / 60:.1f}min]")
            else:
                fail += 1
                print(f"  ❌ {ch_name}: {status} ({segments} segments)")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 50}")
    print(f"✅ TTS 完成: {ok} 成功, {fail} 失败")
    print(f"   总大小: {total_bytes / 1024 / 1024:.1f}MB")
    print(f"   耗时: {elapsed / 60:.1f} 分钟")
    print(f"{'=' * 50}")

if __name__ == "__main__":
    main()
