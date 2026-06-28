import sys
sys.path.insert(0, r"D:\CosyVoice")
sys.path.insert(0, r"D:\CosyVoice\third_party\Matcha-TTS")

import torch
import torchaudio
import time

print("Loading CosyVoice-300M (zero-shot)...")
from cosyvoice.cli.cosyvoice import AutoModel

model = AutoModel(model_dir=r"D:\CosyVoice\pretrained_models\CosyVoice-300M")
print(f"Model loaded. VRAM: {torch.cuda.memory_allocated() / 1024**2:.0f}MB")

# Reference voice: the UP主's voice from first 30 seconds
ref_wav = r"D:\reasonix-project\voice_clone\ref_voice_30s.wav"
prompt_text = "大家好，今天开一个读书的坑。这个系列我们来讲一讲外交协调时代的欧洲。主要是想讲一下1848革命后，欧洲各国的外交策略。"

# Test text to generate with cloned voice
tts_text = "争夺欧洲霸权的斗争，是十九世纪欧洲外交史上的重要篇章。今天，我们来翻开这段波澜壮阔的历史。"

print(f"\nGenerating with cloned voice...")
start = time.time()

for i, chunk in enumerate(model.inference_zero_shot(tts_text, prompt_text, ref_wav)):
    elapsed = time.time() - start
    out_path = rf"D:\reasonix-project\voice_clone\cloned_{i}.wav"
    torchaudio.save(out_path, chunk['tts_speech'], model.sample_rate)
    print(f"  Chunk {i}: {chunk['tts_speech'].shape[1]/24000:.1f}s -> {out_path}")

elapsed = time.time() - start
print(f"\nTotal generation: {elapsed:.1f}s")
print(f"VRAM used: {torch.cuda.memory_allocated() / 1024**2:.0f}MB")
print("\nDone! Play cloned_0.wav to hear the result.")
