#!/usr/bin/env python3
"""
批量 TTS — 用 MiMo TTS 生成有声书音频
用法: python3 scripts/batch_tts.py [起始章节] [结束章节]
章节编号: 0=绪言, 1-23=第1-23章
"""
import sys, os, json, time, base64, struct, re, requests
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
OCR_DIR = PROJECT_DIR / "output" / "ocr_text"
AUDIO_DIR = PROJECT_DIR / "output" / "audio"
FULL_TEXT = OCR_DIR / "full_text.txt"

def get_api_key():
    key = os.environ.get("MIMO_API_KEY", "")
    if key: return key
    cfg = Path.home() / ".openclaw" / "openclaw.json"
    if cfg.exists():
        try: return json.loads(cfg.read_text())["models"]["providers"]["xiaomi"]["apiKey"]
        except: pass
    return ""

API_KEY = get_api_key()
API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
TTS_MODEL = "mimo-v2.5-tts"

# 章节页码范围 (页号, 章节名)
CHAPTERS = [
    (1, 3, "绪言"),
    (4, 38, "第1章"),
    (39, 72, "第2章"),
    (73, 104, "第3章"),
    (105, 132, "第4章"),
    (133, 166, "第5章"),
    (167, 183, "第7章"),
    (184, 215, "第8章"),
    (216, 247, "第9章"),
    (248, 276, "第10章"),
    (277, 305, "第11章"),
    (306, 338, "第12章"),
    (339, 370, "第13章"),
    (371, 400, "第14章"),
    (401, 430, "第15章"),
    (431, 458, "第16章"),
    (459, 486, "第17章"),
    (487, 514, "第18章"),
    (515, 540, "第19章"),
    (541, 566, "第20章"),
    (567, 594, "第21章"),
    (595, 624, "第22章"),
    (625, 667, "第23章"),
]

session = requests.Session()

def split_text(text, max_chars=250):
    """按句子分割文本，合并至max_chars"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    merged, buf = [], ''
    for line in lines:
        if len(buf) + len(line) > max_chars:
            if buf: merged.append(buf)
            buf = line
        else:
            buf = buf + ' ' + line if buf else line
    if buf: merged.append(buf)
    return merged

def tts_chunk(text):
    """调用 MiMo TTS API，返回 PCM bytes 或 None"""
    try:
        r = session.post(f"{API_BASE}/chat/completions",
            json={
                "model": TTS_MODEL,
                "messages": [{"role": "assistant", "content": text}],
                "audio": {"format": "wav", "voice": "mimo_default"}
            },
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=60)
        r.raise_for_status()
        data = r.json()
        audio_b64 = data["choices"][0]["message"]["audio"]["data"]
        return base64.b64decode(audio_b64)
    except Exception as e:
        print(f"    TTS ERR: {e}")
        return None

def save_wav(pcm_data, path, sr=24000):
    """保存 PCM 为 WAV"""
    if pcm_data[:4] == b'RIFF':
        with open(path, 'wb') as f: f.write(pcm_data)
        return
    with open(path, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + len(pcm_data)))
        f.write(b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, 1, sr, sr*2, 2, 16))
        f.write(b'data')
        f.write(struct.pack('<I', len(pcm_data)))
        f.write(pcm_data)

def generate_chapter(ch_idx, start_page, end_page, ch_name):
    """生成单章音频"""
    out_path = AUDIO_DIR / f"chapter_{ch_idx:02d}_{ch_name}.wav"
    if out_path.exists() and out_path.stat().st_size > 1000:
        print(f"  ✓ {ch_name}: 已存在 ({out_path.stat().st_size/1024/1024:.1f}MB)，跳过")
        return True

    # 读取章节文字
    text = ""
    for pn in range(start_page, end_page + 1):
        fpath = OCR_DIR / f"page_{pn:04d}.txt"
        if fpath.exists():
            content = fpath.read_text(encoding='utf-8').strip()
            if content and content != "ERROR":
                text += content + '\n'

    if not text.strip():
        print(f"  ✗ {ch_name}: 无文字")
        return False

    chunks = split_text(text)
    print(f"  {ch_name}: {len(chunks)} 段")

    all_audio = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip(): continue
        audio = tts_chunk(chunk)
        if audio:
            all_audio.append(audio)
        if (i + 1) % 20 == 0:
            print(f"    [{i+1}/{len(chunks)}] 已完成")
        time.sleep(0.2)

    if not all_audio:
        print(f"  ✗ {ch_name}: 无音频生成")
        return False

    # 合并并保存
    combined = b''.join(all_audio)
    save_wav(combined, str(out_path))
    size_mb = len(combined) / 1024 / 1024
    print(f"  ✓ {ch_name}: {size_mb:.1f}MB → {out_path.name}")
    return True

def main():
    if not API_KEY:
        print("❌ 未找到 MIMO_API_KEY")
        sys.exit(1)

    start_ch = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end_ch = int(sys.argv[2]) if len(sys.argv) > 2 else 23
    time_limit = int(sys.argv[3]) if len(sys.argv) > 3 else 85  # 默认85分钟

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    print(f"🎤 TTS 批量生成")
    print(f"   章节范围: {start_ch} - {end_ch}")
    print(f"   时间限制: {time_limit} 分钟")
    print(f"   模型: {TTS_MODEL}")
    print()

    t0 = time.time()
    done = 0
    for idx, (start, end, name) in enumerate(CHAPTERS):
        if idx < start_ch or idx > end_ch:
            continue
        elapsed = time.time() - t0
        if elapsed > time_limit * 60:
            print(f"\n⏰ 已用时 {elapsed/60:.1f} 分钟，到达时间限制，停止")
            break
        generate_chapter(idx, start, end, name)
        done += 1

    elapsed = time.time() - t0
    print(f"\n✅ 本轮完成 {done} 章，耗时 {elapsed/60:.1f} 分钟")

if __name__ == "__main__":
    main()
