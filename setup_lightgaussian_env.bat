@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET "PATH=%ANACONDA%;%ANACONDA%\Library\bin;%ANACONDA%\Scripts;%PATH%"
CALL "%ANACONDA%\Scripts\activate.bat" "%ANACONDA%"

echo [1/4] Creating lightgaussian env (Python 3.9)...
conda create -n lightgaussian python=3.9 -y
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] conda create failed & exit /b 1)

echo [2/4] Installing PyTorch 1.12.1 + CUDA 11.6...
CALL conda activate lightgaussian
pip install torch==1.12.1+cu116 torchvision==0.13.1+cu116 torchaudio==0.12.1 --extra-index-url https://download.pytorch.org/whl/cu116
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] torch install failed & exit /b 1)

echo [3/4] Installing other dependencies...
pip install plyfile==0.8.1 icecream tqdm lpips
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] pip deps failed & exit /b 1)

echo [4/4] Building LightGaussian submodules...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"
pip install submodules/simple-knn
pip install submodules/compress-diff-gaussian-rasterization
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] submodule build failed & exit /b 1)

echo [DONE] lightgaussian env ready.
