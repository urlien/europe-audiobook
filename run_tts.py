#!/usr/bin/env python3
"""TTS for chapters 7-11"""
import os, requests, base64, time

API_KEY = os.environ.get('MIMO_API_KEY', '')
API_BASE = os.environ.get('MIMO_API_BASE_URL', '')
OCR_DIR = 'output/ocr_text'
AUDIO_DIR = 'output/audio'
os.makedirs(AUDIO_DIR, exist_ok=True)

def merge_paragraphs(text, max_len=250):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    merged, buf = [], ''
    for line in lines:
        if len(buf) + len(line) > max_len:
            if buf: merged.append(buf)
            buf = line
        else:
            buf = buf + ' ' + line if buf else line
    if buf: merged.append(buf)
    return merged

def tts_segment(text, output_path):
    try:
        r = requests.post(f'{API_BASE}/chat/completions', json={
            'model': 'mimo-v2.5-tts',
            'messages': [{'role': 'user', 'content': text}],
            'audio': {'format': 'pcm16'}
        }, headers={'Authorization': f'Bearer {API_KEY}'}, timeout=120)
        d = r.json()
        audio_b64 = d.get('choices', [{}])[0].get('message', {}).get('audio', {}).get('data', '')
        if not audio_b64:
            return False
        pcm_data = base64.b64decode(audio_b64)
        with open(output_path, 'ab') as f:
            f.write(pcm_data)
        return True
    except Exception as e:
        print(f'  TTS ERR: {e}')
        return False

def process_chapter(ch_num, start_page, end_page):
    chapter_text = ''
    for pn in range(start_page, end_page + 1):
        fpath = f'{OCR_DIR}/page_{pn:04d}.txt'
        if os.path.exists(fpath):
            with open(fpath) as f:
                content = f.read()
            if content.strip() and not content.startswith('ERROR'):
                chapter_text += content + '\n'
    if not chapter_text.strip():
        return ch_num, 'no text'
    segments = merge_paragraphs(chapter_text)
    audio_path = f'{AUDIO_DIR}/chapter_{ch_num:02d}.pcm'
    if os.path.exists(audio_path):
        os.remove(audio_path)
    success = 0
    for i, seg in enumerate(segments):
        if tts_segment(seg, audio_path):
            success += 1
        if (i + 1) % 10 == 0:
            print(f'  Ch{ch_num}: {i+1}/{len(segments)} segments done')
    size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
    return ch_num, f'{success}/{len(segments)} segments, {size/1024/1024:.1f}MB'

chapters = [
    (7, 167, 183),
    (8, 184, 215),
    (9, 216, 247),
    (10, 248, 276),
    (11, 277, 305),
]

print(f'开始 TTS: {len(chapters)} 章')
start_time = time.time()

for ch_num, start, end in chapters:
    ch_start = time.time()
    result = process_chapter(ch_num, start, end)
    elapsed = time.time() - ch_start
    print(f'  第{ch_num}章: {result[1]} ({elapsed:.0f}s)')

total_elapsed = time.time() - start_time
print(f'\nTTS 完成: 耗时 {total_elapsed:.0f}s')
