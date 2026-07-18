"""
MiMo TTS 语音合成脚本
从OCR提取的文字生成有声书音频
使用 MiMo-V2.5-TTS API（云端推理，无需本地GPU）
"""
import sys
import os
import re
import json
import argparse
import time
import struct
import base64
import urllib.request
import urllib.error


# ── 配置 ──
MIMO_API_BASE = os.environ.get("MIMO_API_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")

# 可用模型
MODELS = {
    "tts": "MiMo-V2.5-TTS",           # 基础TTS
    "voice-design": "MiMo-V2.5-TTS-VoiceDesign",  # 声音设计
    "voice-clone": "MiMo-V2.5-TTS-VoiceClone",     # 声音克隆
}


def split_text(text, max_chars=200):
    """将长文本按句子分割成适合TTS的短句"""
    sentences = re.split(r'([。！？.!?\n])', text)
    chunks = []
    current = ""
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


def mimo_tts(text, model_key="tts", voice_id=None, reference_audio=None):
    """
    调用 MiMo TTS API 生成音频
    返回音频 bytes (WAV/PCM) 或 None
    """
    if not MIMO_API_KEY:
        print("Error: MIMO_API_KEY not set. Set it via environment variable or edit this script.")
        return None

    model_name = MODELS.get(model_key, MODELS["tts"])
    url = f"{MIMO_API_BASE}/audio/speech"
    
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json",
    }
    
    body = {
        "model": model_name,
        "input": text,
    }
    
    if voice_id:
        body["voice"] = voice_id
    
    # 声音克隆：传参考音频
    if model_key == "voice-clone" and reference_audio:
        with open(reference_audio, "rb") as f:
            ref_b64 = base64.b64encode(f.read()).decode()
        body["reference_audio"] = ref_b64
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            
            # API 返回音频二进制或 JSON
            if "audio" in content_type or "octet-stream" in content_type:
                return data
            else:
                # 可能是 JSON 格式的 base64 音频
                try:
                    result = json.loads(data)
                    if "audio" in result:
                        return base64.b64decode(result["audio"])
                    elif "data" in result:
                        return base64.b64decode(result["data"])
                    else:
                        print(f"Unexpected response: {json.dumps(result)[:200]}")
                        return None
                except json.JSONDecodeError:
                    return data  # 直接返回原始数据
                    
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"API Error {e.code}: {err[:200]}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def save_audio(audio_data, output_path, sample_rate=24000):
    """保存音频为 WAV 文件"""
    if audio_data is None:
        return False
    
    # 检查是否已经是 WAV 格式
    if audio_data[:4] == b'RIFF':
        with open(output_path, 'wb') as f:
            f.write(audio_data)
        return True
    
    # 原始 PCM → WAV
    try:
        with open(output_path, 'wb') as f:
            # WAV header
            num_channels = 1
            bits_per_sample = 16
            byte_rate = sample_rate * num_channels * bits_per_sample // 8
            block_align = num_channels * bits_per_sample // 8
            data_size = len(audio_data)
            
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + data_size))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<IHHIIHH', 16, 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample))
            f.write(b'data')
            f.write(struct.pack('<I', data_size))
            f.write(audio_data)
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False


def generate_audio(text_file, output_dir, model_key="tts", voice_id=None, reference_audio=None):
    """从文字文件生成音频"""
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    
    # 移除页码标记
    text = re.sub(r'===.*?===\n?', '', text)
    text = text.strip()
    
    if not text:
        print(f"Empty text: {text_file}")
        return None
    
    chunks = split_text(text)
    print(f"Text split into {len(chunks)} chunks")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成每个片段的音频
    all_audio = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        print(f"  [{i+1}/{len(chunks)}] Generating: {chunk[:50]}...")
        
        audio = mimo_tts(chunk, model_key=model_key, voice_id=voice_id, reference_audio=reference_audio)
        if audio:
            all_audio.append(audio)
            print(f"    ✓ {len(audio)} bytes")
        else:
            print(f"    ✗ Failed")
        
        # 限速：避免API过载
        if i < len(chunks) - 1:
            time.sleep(0.5)
    
    if not all_audio:
        print("No audio generated!")
        return None
    
    # 合并音频
    combined = b''.join(all_audio)
    base_name = os.path.splitext(os.path.basename(text_file))[0]
    out_path = os.path.join(output_dir, f"{base_name}.wav")
    
    if save_audio(combined, out_path):
        print(f"\nSaved: {out_path} ({len(combined)} bytes)")
        return out_path
    
    return None


def main():
    parser = argparse.ArgumentParser(description="MiMo TTS 有声书生成")
    parser.add_argument("--input", "-i", required=True, help="OCR文字文件或目录")
    parser.add_argument("--output", "-o", default="output/audio", help="输出目录")
    parser.add_argument("--model", "-m", default="tts", choices=["tts", "voice-design", "voice-clone"],
                        help="TTS模型: tts(基础), voice-design(声音设计), voice-clone(声音克隆)")
    parser.add_argument("--voice", "-v", default=None, help="声音ID（voice-design/clone时使用）")
    parser.add_argument("--reference", "-r", default=None, help="参考音频文件（voice-clone时使用）")
    parser.add_argument("--api-key", "-k", default=None, help="MiMo API Key (或设置 MIMO_API_KEY 环境变量)")
    args = parser.parse_args()
    
    # 设置 API Key
    global MIMO_API_KEY
    if args.api_key:
        MIMO_API_KEY = args.api_key
    elif not MIMO_API_KEY:
        print("Error: Set MIMO_API_KEY environment variable or use --api-key")
        sys.exit(1)
    
    input_path = args.input
    output_dir = args.output
    
    if os.path.isfile(input_path):
        generate_audio(input_path, output_dir, args.model, args.voice, args.reference)
    elif os.path.isdir(input_path):
        files = sorted([f for f in os.listdir(input_path) if f.endswith('.txt')])
        print(f"Found {len(files)} text files")
        for f in files:
            print(f"\n{'='*50}")
            print(f"Processing: {f}")
            print(f"{'='*50}")
            generate_audio(os.path.join(input_path, f), output_dir, args.model, args.voice, args.reference)
    else:
        print(f"Error: {input_path} not found")
        sys.exit(1)


if __name__ == "__main__":
    main()
