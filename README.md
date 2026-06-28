# 📚 欧洲协调时代 · 有声书生成器

> 扫描版PDF → AI OCR → 语音合成 → 手机友好阅读器

将任意中文扫描版PDF书籍，转化为可在手机上收听的有声书。

## 🎯 项目目标

以A.J.P. 泰勒的《争夺欧洲霸权的斗争（1848-1918）》为实践案例，构建一套完整的**扫描版PDF有声书生成管线**：

```
扫描版PDF (667页图片)
    ↓ MiMo OCR (小米云端API)
纯文本 (带段落结构)
    ↓ CosyVoice TTS (本地GPU推理)
WAV音频文件
    ↓ PDF.js阅读器 (手机浏览器)
带音频播放的精美阅读App
```

## 🛠 技术栈

| 组件 | 技术 | 用途 | 运行位置 |
|------|------|------|----------|
| **OCR** | MiMo v2-omni (小米) | 扫描图片→文字 | 云端API |
| **TTS** | CosyVoice 300M (阿里) | 文字→语音 | 本地GPU |
| **阅读器** | PDF.js + 原生HTML | 手机端阅读/播放 | 本地浏览器 |
| **音频提取** | ffmpeg | 视频→音频 | 本地 |
| **B站下载** | Bili23-Downloader | 参考素材获取 | 本地 |

## 📁 项目结构

```
europe-audiobook/
├── README.md                 # 本文件
├── reader/
│   └── reader.html           # 手机友好PDF阅读器（单文件，可打包APK）
├── scripts/
│   ├── mimo_ocr_batch.py     # MiMo OCR批量提取PDF文字
│   ├── tts_generate.py       # CosyVoice语音合成脚本
│   └── setup_cosyvoice.bat   # CosyVoice环境一键安装
├── assets/
│   └── (参考音频、模型等)
└── output/
    └── (生成的音频文件)
```

## 🚀 快速开始

### 前置条件

- Windows 10/11
- Python 3.10+ (推荐用Conda)
- NVIDIA GPU (推荐4GB+显存)
- 有效的MiMo API Key (小米Token Plan)

### 1. 安装CosyVoice环境

```bash
# 安装Miniconda（如果没有）
# 下载: https://docs.conda.io/en/latest/miniconda.html

# 创建环境
conda create -n cosyvoice -y python=3.10
conda activate cosyvoice

# 安装PyTorch (CUDA 12.1)
pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121

# 克隆CosyVoice
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice
pip install -r requirements_win.txt  # 见项目中的Windows适配版

# 下载模型
python -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice-300M', local_dir='pretrained_models/CosyVoice-300M')"
```

### 2. 配置MiMo API

设置环境变量：
```bash
set MIMO_API_KEY=你的API_KEY
set MIMO_API_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
```

或在 `scripts/mimo_ocr_batch.py` 中直接修改 `api_key` 变量。

### 3. 运行OCR提取文字

```bash
cd scripts
python mimo_ocr_batch.py
```

输出: `output/ocr_text/pages_xxx.txt`

### 4. 生成有声书音频

```bash
cd scripts
python tts_generate.py --input output/ocr_text/ --output output/audio/
```

### 5. 使用阅读器

```bash
# 启动本地服务器
cd reader
python -m http.server 8080

# 浏览器打开
# http://localhost:8080/reader.html
```

## 📖 阅读器功能 (reader.html)

基于 **PDF.js** 的单文件手机阅读器，核心功能：

| 功能 | 说明 |
|------|------|
| 📑 目录导航 | 自动提取PDF目录，侧边栏跳转 |
| 🔖 书签系统 | 随时标记重要页面，localStorage持久化 |
| 🌙 夜间模式 | 一键切换深色/浅色主题 |
| ⬆⬇ 手势翻页 | 点击屏幕左/中/右区域翻页或切换UI |
| 📊 进度条 | 底部滑块快速跳页 |
| 🔄 无限滚动 | 滚到底部自动加载后续页面 |
| 📱 移动适配 | 支持刘海屏/药丸屏安全区域 |

### 打包为APK

参考 [Jessica Diary](https://github.com/urlien/jessica-diary) 项目，使用 Android WebView 壳包装：

```
reader.html → Android WebView → .apk
```

## 🔧 MiMo OCR 说明

### 为什么选择MiMo

| 方案 | 中文OCR质量 | 价格 | 速度 |
|------|------------|------|------|
| **MiMo v2-omni** | ⭐⭐⭐⭐⭐ | Token Plan套餐内 | ~10s/页 |
| PaddleOCR (本地) | ⭐⭐⭐⭐ | 免费 | ~2s/页 (需GPU) |
| Tesseract | ⭐⭐ | 免费 | ~1s/页 (质量差) |
| GPT-4o Vision | ⭐⭐⭐⭐⭐ | $5/1000页 | ~5s/页 |

MiMo的优势：中文识别精准、套餐内免费、API兼容OpenAI格式。

### API调用格式

```python
import urllib.request, json, base64

url = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "api-key": "你的KEY"
}
payload = {
    "model": "mimo-v2-omni",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
            {"type": "text", "text": "请完整提取页面中的所有文字，保持段落结构。"}
        ]
    }],
    "max_tokens": 4096
}
```

## 🎙 CosyVoice 说明

### 模型选择

| 模型 | 大小 | 用途 | 显存需求 |
|------|------|------|----------|
| CosyVoice-300M | ~3GB | Zero-shot声音克隆 | ~2GB |
| CosyVoice-300M-SFT | ~3GB | 内置说话人TTS | ~2GB |
| CosyVoice2-0.5B | ~2GB | 更高质量TTS | ~3GB |

### 推理性能 (RTX 3050 Ti 4GB)

- **SFT模式** (内置中文女声): RTF ~1.2x (1秒音频≈1.2秒生成)
- **Zero-shot模式** (声音克隆): RTF ~22x (1秒音频≈22秒生成)
- **VRAM占用**: ~1.8GB

### 基本用法

```python
from cosyvoice.cli.cosyvoice import AutoModel

model = AutoModel(model_dir='pretrained_models/CosyVoice-300M-SFT')

# 内置中文女声
for chunk in model.inference_sft('你好，这是有声书测试。', '中文女', stream=False):
    torchaudio.save('output.wav', chunk['tts_speech'], model.sample_rate)
```

## 📝 B站素材参考

项目参考了B站UP主"没有奶茶的世界"的有声读书系列：
- [欧洲协调时代（1）——克拉科夫起义](https://www.bilibili.com/video/BV1kJ4m1p7WD/)
- 视频下载工具: [Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader)
- AI字幕可直接提取参考文本

## ⚠️ 注意事项

1. **MiMo API Key**: 仅限编程工具交互式使用，不可用于自动化脚本（官方条款）
2. **CosyVoice**: Apache-2.0 许可证，商用需注意模型的CC BY-NC 4.0限制
3. **PDF版权**: 本项目仅供个人学习研究使用
4. **显存不足**: 4GB显存可跑SFT模式，Zero-shot克隆较慢；推荐8GB+显存

## 🔗 相关项目

- [CosyVoice](https://github.com/FunAudioLLM/CosyVoice) - 阿里语音合成
- [Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) - B站视频下载
- [Jessica Diary](https://github.com/urlien/jessica-diary) - HTML打包APK参考
- [MiMo](https://mimo.xiaomi.com) - 小米多模态模型

## 📊 实验数据

### OCR测试结果 (前20页)

| 页码 | 提取字数 | 状态 |
|------|----------|------|
| 1 (封面) | 60 | ✅ |
| 2 (版权) | 55 | ✅ |
| 3 (版权) | 386 | ✅ |
| 4 (前言) | 691 | ✅ |
| 5 (前言) | 768 | ✅ |
| 6-20 (正文) | 73-942 | ✅ |

### TTS生成结果

| 模式 | 文本长度 | 音频时长 | 生成时间 | 显存 |
|------|----------|----------|----------|------|
| SFT中文女 | 45字 | 8.4s | 10.6s | 1783MB |
| Zero-shot | 45字 | 6.8s | 160s | 1871MB |

---

**Made with ❤️ by Reasonix**
