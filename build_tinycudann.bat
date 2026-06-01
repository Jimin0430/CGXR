@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"

set DISTUTILS_USE_SDK=1
set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.7
set PATH=%CUDA_HOME%\bin;%PATH%

echo nvcc path:
where nvcc
nvcc --version

echo.
echo Installing tinycudann...
"C:\Users\USER\anaconda3\envs\mobile-gs\Scripts\pip.exe" install git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
