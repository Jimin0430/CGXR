@echo off
REM ============================================================
REM  mobile-gs 환경 세팅 스크립트
REM  (이미 설치 완료 - Python 3.11 venv 사용)
REM  ENV: C:\Users\USER\anaconda3\envs\mobile-gs
REM ============================================================
SET PY311=C:\Users\USER\AppData\Local\Programs\Python\Python311\python.exe
SET ENV=C:\Users\USER\anaconda3\envs\mobile-gs
SET MOBILE_GS=D:\JM\cgxr\CGXR\mobile_gs
SET PIP=%ENV%\Scripts\pip.exe
SET PYTHON=%ENV%\Scripts\python.exe

echo [1/4] Python 3.11 venv 생성...
"%PY311%" -m venv "%ENV%"

echo [2/4] PyTorch 2.5.1 + CUDA 11.8 설치...
"%PIP%" install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu118

echo [3/4] 기본 패키지 설치...
"%PIP%" install ninja wheel setuptools tqdm plyfile dahuffman

echo [4/4] CUDA 확장 컴파일...
cd /d "%MOBILE_GS%\submodules\simple-knn"
"%PIP%" install .

cd /d "%MOBILE_GS%\submodules\diff-gaussian-rasterization_ms"
"%PIP%" install .

cd /d "%MOBILE_GS%\submodules\diff-gaussian-rasterization_msori"
"%PIP%" install .

echo.
echo ============================================================
echo  mobile-gs 환경 세팅 완료
echo  주의: TMC(GPCC) 압축 사용 시 tmc3 별도 설치 필요
echo  https://github.com/MPEGGroup/mpeg-pcc-tmc13
echo ============================================================
pause
