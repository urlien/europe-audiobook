"""
有声书完整流水线 — MiMo OCR + MiMo TTS
在自己电脑上跑，用法：
  python audiobook_pipeline.py

需要：Python 3.8+、pip install pymupdf
"""
import os
import sys
import re
import json
import time
import base64
import struct
import urllib.request
import urllib.error

# ══════════════════════════════════════════
# 配置
# ══════════════════════════════════════════
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")

PDF_PATH = "pdf-books/争夺欧洲霸权的斗争（1848-1918年）.pdf"
OUTPUT_DIR = "output"
OCR_DIR = os.path.join(OUTPUT_DIR, "ocr_text")
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")

# OCR 每批处理页数（避免 API 超时）
BATCH_SIZE = 5
# OCR 起始/结束页（None = 全部）
OCR_START = None
OCR_END = None

# TTS 模型
TTS_MODEL = "MiMo-V2.5-TTS"  # 可选: MiMo-V2.5-TTS-VoiceDesign, MiMo-V2.5-TTS-VoiceClone


# ══════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════
def api_call(url, headers, body, timeout=120):
    """通用 API 调用"""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:300]
        print(f"  API Error {e.code}: {err}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


# ══════════════════════════════════════════
# Step 1: OCR — PDF → 文字
# ══════════════════════════════════════════
def run_ocr():
    """用 MiMo v2-omni 从 PDF 提取文字"""
    try:
        import fitz
    except ImportError:
        print("❌ 需要安装 PyMuPDF: pip install pymupdf")
        sys.exit(1)

    if not MIMO_API_KEY:
        print("❌ 设置 MIMO_API_KEY 环境变量")
        sys.exit(1)

    os.makedirs(OCR_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    total = len(doc)
    start = OCR_START or 1
    end = OCR_END or total

    print(f"📖 PDF: {total} 页, OCR 范围: {start}-{end}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MIMO_API_KEY}",
    }

    all_text = []
    for page_num in range(start, end + 1):
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        img_b64 = base64.b64encode(img_data).decode()

        if len(img_b64) > 10 * 1024 * 1024:
            print(f"  Page {page_num}: too large, skip")
            continue

        payload = {
            "model": "mimo-v2-omni",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": "这是一本书的内页扫描图。请完整提取页面中的所有中文和英文文字，保持原始段落结构。只输出提取到的文字，不要添加任何说明。"}
                ]
            }],
            "max_tokens": 4096
        }

        result = api_call(f"{MIMO_API_BASE}/chat/completions", headers, payload)
        if result and "choices" in result:
            text = result["choices"][0]["message"]["content"]
            all_text.append(f"=== 第{page_num}页 ===\n{text}\n")
            print(f"  Page {page_num}: {len(text)} chars ✓")
        else:
            all_text.append(f"=== 第{page_num}页 === ERROR\n")
            print(f"  Page {page_num}: ✗")

        # 每批保存一次
        if page_num % BATCH_SIZE == 0 or page_num == end:
            batch_file = os.path.join(OCR_DIR, f"pages_{start}_{page_num}.txt")
            with open(batch_file, "w", encoding="utf-8") as f:
                f.write("\n".join(all_text))
            print(f"  💾 Saved: {batch_file}")

        time.sleep(0.5)

    doc.close()

    # 合并所有文本
    merged_file = os.path.join(OCR_DIR, "full_text.txt")
    all_files = sorted([f for f in os.listdir(OCR_DIR) if f.endswith(".txt") and f != "full_text.txt"])
    with open(merged_file, "w", encoding="utf-8") as out:
        for fname in all_files:
            with open(os.path.join(OCR_DIR, fname), "r", encoding="utf-8") as inp:
                out.write(inp.read())
    print(f"\n✅ OCR 完成: {merged_file}")
    return merged_file


# ══════════════════════════════════════════
# Step 2: TTS — 文字 → 音频
# ══════════════════════════════════════════
def split_text(text, max_chars=200):
    """按句子分割文本"""
    sentences = re.split(r'([。！？.!?\n])', text)
    chunks, current = [], ""
    for seg in sentences:
        if not seg.strip():
            continue
        if seg in '。！？.!?\n':
            current += seg
            if len(current) >= 20:
                chunks.append(current.strip())
                current = ""
        else:
            if len(current) + len(seg) > max_chars:
                if current:
                    chunks.append(current.strip())
                current = seg
            else:
                current += seg
    if current.strip():
        chunks.append(current.strip())
    return chunks


def mimo_tts(text):
    """调用 MiMo TTS API"""
    if not MIMO_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {"model": TTS_MODEL, "input": text}

    try:
        req = urllib.request.Request(
            f"{MIMO_API_BASE}/audio/speech",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            if "audio" in content_type or "octet-stream" in content_type:
                return data
            try:
                result = json.loads(data)
                if "audio" in result:
                    return base64.b64decode(result["audio"])
                elif "data" in result:
                    return base64.b64decode(result["data"])
            except json.JSONDecodeError:
                return data
    except Exception as e:
        print(f"  TTS Error: {e}")
    return None


def save_wav(audio_data, path, sample_rate=24000):
    """保存为 WAV"""
    if not audio_data:
        return False
    if audio_data[:4] == b'RIFF':
        with open(path, 'wb') as f:
            f.write(audio_data)
        return True
    # PCM → WAV
    with open(path, 'wb') as f:
        nch, bps = 1, 16
        br = sample_rate * nch * bps // 8
        ba = nch * bps // 8
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + len(audio_data)))
        f.write(b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, nch, sample_rate, br, ba, bps))
        f.write(b'data')
        f.write(struct.pack('<I', len(audio_data)))
        f.write(audio_data)
    return True


def run_tts(text_file):
    """从文字文件生成音频"""
    os.makedirs(AUDIO_DIR, exist_ok=True)

    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()

    text = re.sub(r'===.*?===\n?', '', text).strip()
    if not text:
        print("❌ 空文本")
        return

    chunks = split_text(text)
    print(f"🎤 TTS: {len(chunks)} 个片段")

    all_audio = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        print(f"  [{i+1}/{len(chunks)}] {chunk[:50]}...")
        audio = mimo_tts(chunk)
        if audio:
            all_audio.append(audio)
            print(f"    ✓ {len(audio)} bytes")
        else:
            print(f"    ✗ Failed")
        if i < len(chunks) - 1:
            time.sleep(0.3)

    if all_audio:
        combined = b''.join(all_audio)
        out_path = os.path.join(AUDIO_DIR, "full_audiobook.wav")
        save_wav(combined, out_path)
        print(f"\n✅ TTS 完成: {out_path} ({len(combined)} bytes)")
    else:
        print("❌ 没有生成任何音频")


# ══════════════════════════════════════════
# Main
# ══════════════════════════════════════════
def main():
    print("=" * 50)
    print("📚 有声书生成流水线")
    print("=" * 50)

    if not MIMO_API_KEY:
        print("\n❌ 请设置 MIMO_API_KEY:")
        print("  export MIMO_API_KEY='你的key'")
        print("  或修改脚本顶部的 MIMO_API_KEY 变量")
        sys.exit(1)

    # Step 1: OCR
    print("\n--- Step 1: OCR ---")
    ocr_file = os.path.join(OCR_DIR, "full_text.txt")
    if os.path.exists(ocr_file):
        print(f"已有 OCR 结果: {ocr_file}, 跳过")
    else:
        ocr_file = run_ocr()

    # Step 2: TTS
    print("\n--- Step 2: TTS ---")
    run_tts(ocr_file)

    print("\n" + "=" * 50)
    print("✅ 完成！")
    print(f"  OCR 文本: {OCR_DIR}/")
    print(f"  音频文件: {AUDIO_DIR}/")
    print("=" * 50)


if __name__ == "__main__":
    main()
