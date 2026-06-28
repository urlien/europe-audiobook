"""
CosyVoice TTS 语音合成脚本
从OCR提取的文字生成有声书音频
"""
import sys
import os
import re
import argparse

# Add CosyVoice to path
COSYVOICE_PATH = r"D:\CosyVoice"
sys.path.insert(0, COSYVOICE_PATH)
sys.path.insert(0, os.path.join(COSYVOICE_PATH, "third_party", "Matcha-TTS"))


def split_text(text, max_chars=100):
    """将长文本按句子分割成适合TTS的短句"""
    # Split by Chinese/English sentence endings
    sentences = re.split(r'([。！？.!?\n])', text)
    
    chunks = []
    current = ""
    for i, seg in enumerate(sentences):
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


def generate_audio(text_file, output_dir, speaker="中文女", model_dir=None):
    """从文字文件生成音频"""
    import torch
    import torchaudio
    
    if model_dir is None:
        model_dir = os.path.join(COSYVOICE_PATH, "pretrained_models", "CosyVoice-300M-SFT")
    
    print(f"Loading CosyVoice model from {model_dir}...")
    from cosyvoice.cli.cosyvoice import AutoModel
    model = AutoModel(model_dir=model_dir)
    print(f"Model loaded. VRAM: {torch.cuda.memory_allocated() / 1024**2:.0f}MB")
    
    # Read text
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Remove headers like "=== 第X页 ==="
    text = re.sub(r'===.*?===\n?', '', text)
    text = text.strip()
    
    # Split into chunks
    chunks = split_text(text)
    print(f"Text split into {len(chunks)} chunks")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate audio for each chunk
    all_audio = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        print(f"  [{i+1}/{len(chunks)}] Generating: {chunk[:30]}...")
        try:
            for j, output in enumerate(model.inference_sft(chunk, speaker, stream=False)):
                all_audio.append(output['tts_speech'])
        except Exception as e:
            print(f"    Error: {e}")
            continue
    
    # Concatenate all audio
    if all_audio:
        full_audio = torch.cat(all_audio, dim=1)
        out_path = os.path.join(output_dir, os.path.splitext(os.path.basename(text_file))[0] + ".wav")
        torchaudio.save(out_path, full_audio, model.sample_rate)
        duration = full_audio.shape[1] / model.sample_rate
        print(f"\nSaved: {out_path} ({duration:.1f}s)")
        return out_path
    
    return None


def main():
    parser = argparse.ArgumentParser(description="CosyVoice TTS 有声书生成")
    parser.add_argument("--input", "-i", required=True, help="OCR文字文件或目录")
    parser.add_argument("--output", "-o", default="output/audio", help="输出目录")
    parser.add_argument("--speaker", "-s", default="中文女", help="说话人 (中文女/中文男/英文女/英文男)")
    args = parser.parse_args()
    
    input_path = args.input
    output_dir = args.output
    
    if os.path.isfile(input_path):
        generate_audio(input_path, output_dir, args.speaker)
    elif os.path.isdir(input_path):
        files = sorted([f for f in os.listdir(input_path) if f.endswith('.txt')])
        for f in files:
            print(f"\n{'='*50}")
            print(f"Processing: {f}")
            print(f"{'='*50}")
            generate_audio(os.path.join(input_path, f), output_dir, args.speaker)
    else:
        print(f"Error: {input_path} not found")


if __name__ == "__main__":
    main()
