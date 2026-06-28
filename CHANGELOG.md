# 更新日志

## 2026-06-29 · 首次搭建完整管线

### 🎯 目标
以《争夺欧洲霸权的斗争（1848-1918）》为实践案例，构建扫描版PDF有声书生成管线。

### ✅ 完成事项

#### 1. PDF.js 手机阅读器 (`reader/reader.html`)
- 基于PDF.js的单文件阅读器，无需OCR即可渲染扫描版PDF
- 功能：目录导航、书签、夜间模式、手势翻页、进度条、无限滚动
- 可通过Android WebView壳打包为APK（参考Jessica Diary项目）

#### 2. MiMo OCR 文字提取
- **正确的Base URL**: `https://token-plan-cn.xiaomimimo.com/v1`（不是旧的 api.xiaomimimo.com）
- **正确的模型名**: `mimo-v2-omni`（不是 mimo-v2.5-omni）
- **认证方式**: `api-key` header 或 `Authorization: Bearer`
- 测试结果：前20页扫描版PDF全部正确提取，中文识别质量优秀
- 每页耗时约10秒

#### 3. CosyVoice 语音合成
- 从源码编译安装，需要Python 3.10 + PyTorch 2.3.1+CUDA 12.1
- **SFT模式（内置中文女声）**：RTF ~1.2x，效果最佳，推荐使用
- **Zero-shot模式（声音克隆）**：RTF ~22x（4GB显存），效果不稳定
- 环境安装脚本：`scripts/setup_cosyvoice.bat`

#### 4. B站视频下载
- Bili23-Downloader v2.10.4，专门处理B站wbi签名反爬
- 自动生成AI多语言字幕（.ass格式），可直接提取参考文本

### 🔑 关键经验教训

#### MiMo API
1. **Base URL是关键**：Token Plan用户的URL与文档不同，必须用 `token-plan-cn.xiaomimimo.com`
2. **模型命名**：`mimo-v2-omni` 而非 `mimo-v2.5-omni`
3. **图片大小**：200 DPI的PDF页面图片base64后约1-2MB，API限制10MB
4. **OCR质量**：扫描版中文PDF识别率极高，连版权页的小字都能准确提取

#### CosyVoice
1. **必须用Python 3.10**：Python 3.13不兼容
2. **setuptools版本**：需要降到69.5.1才能编译openai-whisper
3. **PyTorch安装**：必须用 `--index-url https://download.pytorch.org/whl/cu121` 指定CUDA版本
4. **Windows适配**：移除deepspeed、tensorrt等Linux-only依赖
5. **SFT优于Zero-shot**：4GB显存下，内置说话人效果远好于声音克隆
6. **AI语音克隆**：比人声更容易处理（无背景音乐），但CosyVoice在低显存下仍不稳定

#### B站下载
1. **yt-dlp无法绕过412反爬**：B站的wbi签名机制
2. **Bili23-Downloader是最佳选择**：Python GUI工具，专门处理B站反爬
3. **AI字幕是意外收获**：下载器自动生成多语言字幕，可直接用于OCR替代方案

#### 整体架构决策
1. **跳过OCR的替代方案**：如果PDF对应的视频有AI字幕，可直接提取文字
2. **TTS选择**：4GB显存优先用SFT内置说话人，不折腾声音克隆
3. **阅读器先行**：PDF.js可以直接渲染扫描版PDF，OCR+TTS是增值功能

### 📊 性能数据

| 环节 | 工具 | 耗时 | 显存 |
|------|------|------|------|
| OCR (每页) | MiMo v2-omni | ~10s | 0 (云端) |
| TTS (45字) | CosyVoice SFT | ~10s | 1783MB |
| TTS (45字) | CosyVoice Zero-shot | ~160s | 1871MB |
| 阅读器加载 | PDF.js | <1s | 0 |

### 🔮 下一步
- [ ] 667页全量OCR（预计1-2小时）
- [ ] 生成完整有声书音频
- [ ] 阅读器集成音频播放功能
- [ ] 打包为APK

### 📁 安装的工具和环境
- Miniconda → `D:\miniconda3`
- CosyVoice conda环境 → `D:\miniconda3\envs\cosyvoice` (Python 3.10)
- CosyVoice源码 → `D:\CosyVoice`
- CosyVoice模型 → `D:\CosyVoice\pretrained_models\CosyVoice-300M` + `CosyVoice-300M-SFT`
- Bili23-Downloader → `D:\B站视频下载器`
- 阅读器 → `D:\reasonix-project\europe-reader`
