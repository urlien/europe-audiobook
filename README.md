## ⛔ 删除保护

**此仓库及其所有内容严禁自行删除。任何删除操作必须经过赵的明确同意。**

---

# 📚 欧洲协调时代 · 有声书生成器

> 扫描版PDF → AI OCR → 语音合成 → 手机友好阅读器

将任意中文扫描版PDF书籍，转化为可在手机上收听的有声书。

## 🎯 项目目标

以A.J.P. 泰勒的《争夺欧洲霸权的斗争（1848-1918）》为实践案例，构建一套完整的**扫描版PDF有声书生成管线**：

```
扫描版PDF (667页图片)
    ↓ MiMo OCR (小米云端API)
纯文本 (带段落结构)
    ↓ MiMo TTS (小米云端API)
WAV音频文件
    ↓ PDF.js阅读器 (手机浏览器)
带音频播放的精美阅读App
```

## 🛠 技术栈

| 组件 | 技术 | 用途 | 运行位置 |
|------|------|------|----------|
| **OCR** | MiMo v2-omni | 扫描图片→文字 | 云端API |
| **TTS** | MiMo-V2.5-TTS / VoiceDesign / VoiceClone | 文字→语音 | 云端API |
| **阅读器** | PDF.js + 原生HTML | 手机端阅读/播放 | 本地浏览器 |

## 📁 项目结构

```
europe-audiobook/
├── README.md
├── reader/
│   └── reader.html           # 手机友好PDF阅读器
├── scripts/
│   ├── mimo_ocr_batch.py     # MiMo OCR批量提取PDF文字
│   └── tts_generate.py       # MiMo TTS语音合成脚本
├── pdf-books/
│   └── 争夺欧洲霸权的斗争（1848-1918年）.pdf
├── voice-clones/
│   └── (声音克隆参考音频)
└── output/
    └── (生成的音频文件)
```

## 🚀 快速开始

### 前置条件

- Python 3.8+
- 有效的 MiMo API Key (小米Token Plan)
- 无需GPU，无需PyTorch，无需CosyVoice

### 1. 配置MiMo API

```bash
# 设置环境变量
export MIMO_API_KEY="你的API密钥"
export MIMO_API_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
```

或在脚本中直接修改 `MIMO_API_KEY` 变量。

### 2. 运行OCR提取文字

```bash
cd scripts
python mimo_ocr_batch.py
```

输出: `output/ocr_text/pages_xxx.txt`

### 3. 生成有声书音频

```bash
# 基础TTS
python tts_generate.py -i output/ocr_text/ -o output/audio/

# 声音克隆（需要参考音频）
python tts_generate.py -i output/ocr_text/ -o output/audio/ -m voice-clone -r ../voice-clones/reference.mp4

# 声音设计（自定义声音ID）
python tts_generate.py -i output/ocr_text/ -o output/audio/ -m voice-design -v "your-voice-id"
```

### 4. 手机端阅读

将 `reader/reader.html` 传到手机，用浏览器打开即可。

## 🎤 TTS 模型说明

| 模型 | 用途 | 说明 |
|------|------|------|
| `tts` | 基础TTS | 直接文字转语音，无需额外配置 |
| `voice-design` | 声音设计 | 自定义声音特征（语速、音色等） |
| `voice-clone` | 声音克隆 | 用参考音频克隆声音，需提供 `--reference` 参数 |

## 📖 关于这本书

A.J.P. 泰勒的《争夺欧洲霸权的斗争（1848-1918年）》是欧洲近代外交史的经典著作。扫描版PDF共667页，通过本项目转化为有声书后可在手机上随时收听。
