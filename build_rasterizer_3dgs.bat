@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"

set DISTUTILS_USE_SDK=1
set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.7
set PATH=%CUDA_HOME%\bin;%PATH%

echo nvcc path:
where nvcc

echo.
echo Building diff-gaussian-rasterization (standard 3DGS)...
cd /d "D:\JM\cgxr\CGXR\3dgsTrain\submodules\diff-gaussian-rasterization"
"C:\Users\USER\anaconda3\envs\mobile-gs\Scripts\pip.exe" install .
echo Done. Exit code: %ERRORLEVEL%

echo.
echo Building simple-knn...
cd /d "D:\JM\cgxr\CGXR\3dgsTrain\submodules\simple-knn"
"C:\Users\USER\anaconda3\envs\mobile-gs\Scripts\pip.exe" install .
echo Done. Exit code: %ERRORLEVEL%
