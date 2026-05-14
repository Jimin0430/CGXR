@echo off
REM Step 1: Initialize MSVC x64 build tools (provides cl.exe)
CALL "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"

REM Step 2: Initialize conda PATH
SET PATH=C:\Users\USER\anaconda3;C:\Users\USER\anaconda3\Library\mingw-w64\bin;C:\Users\USER\anaconda3\Library\usr\bin;C:\Users\USER\anaconda3\Library\bin;C:\Users\USER\anaconda3\Scripts;%PATH%
CALL C:\Users\USER\anaconda3\Scripts\activate.bat gaussian_splatting

REM Step 3: Required for Windows CUDA compilation
SET DISTUTILS_USE_SDK=1

REM Step 4: Compile and install CUDA extensions
cd /d D:\JM\cgxr\CGXR\Optimize
echo.
echo === Installing diff-gaussian-rasterization ===
pip install submodules/diff-gaussian-rasterization
echo.
echo === Installing simple-knn ===
pip install submodules/simple-knn
echo.
echo === Verifying installs ===
python -c "from diff_gaussian_rasterization import GaussianRasterizer; print('diff_gaussian_rasterization OK')"
python -c "from simple_knn._C import distCUDA2; print('simple_knn OK')"
echo.
echo EXIT CODE: %ERRORLEVEL%
