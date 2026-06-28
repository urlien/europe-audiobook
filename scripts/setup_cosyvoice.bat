@echo off
chcp 65001 >nul
echo ========================================
echo   CosyVoice 环境安装脚本 (Windows)
echo ========================================
echo.

:: Check if conda exists
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 conda，请先安装 Miniconda:
    echo https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo [1/6] 创建 conda 环境 (Python 3.10)...
conda create -n cosyvoice -y python=3.10
if %errorlevel% neq 0 (
    echo [ERROR] 创建环境失败
    pause
    exit /b 1
)

echo.
echo [2/6] 激活环境...
call conda activate cosyvoice

echo.
echo [3/6] 安装 PyTorch (CUDA 12.1)...
pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121
if %errorlevel% neq 0 (
    echo [ERROR] PyTorch 安装失败
    pause
    exit /b 1
)

echo.
echo [4/6] 克隆 CosyVoice...
if not exist "D:\CosyVoice" (
    git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git D:\CosyVoice
)
cd D:\CosyVoice

echo.
echo [5/6] 安装 CosyVoice 依赖...
pip install setuptools==69.5.1
pip install --no-build-isolation openai-whisper==20231117
pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com ^
    conformer==0.3.2 diffusers==0.29.0 hydra-core==1.3.2 HyperPyYAML==1.2.3 ^
    inflect==7.3.1 librosa==0.10.2 lightning==2.2.4 matplotlib==3.7.5 ^
    modelscope==1.20.0 omegaconf==2.3.0 onnxruntime==1.18.0 ^
    pydantic==2.7.0 pyworld==0.3.4 soundfile==0.12.1 x-transformers==2.11.24 ^
    gdown pyarrow wget

echo.
echo [6/6] 下载 CosyVoice-300M-SFT 模型...
python -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice-300M-SFT', local_dir='pretrained_models/CosyVoice-300M-SFT')"
python -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice-300M', local_dir='pretrained_models/CosyVoice-300M')"

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 使用方法:
echo   conda activate cosyvoice
echo   cd D:\CosyVoice
echo   python example.py
echo.
pause
