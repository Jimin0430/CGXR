@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"

set DISTUTILS_USE_SDK=1
set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.7
set PATH=%CUDA_HOME%\bin;%PATH%

echo nvcc path:
where nvcc

echo.
echo Building diff-gaussian-rasterization_ms...
cd /d "D:\JM\cgxr\CGXR\mobile_gs\submodules\diff-gaussian-rasterization_ms"
"C:\Users\USER\anaconda3\envs\mobile-gs\Scripts\pip.exe" install .
echo Done. Exit code: %ERRORLEVEL%
