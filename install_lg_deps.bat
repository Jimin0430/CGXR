@echo off
SET LG_PIP=C:\Users\USER\anaconda3\envs\lightgaussian\Scripts\pip.exe
SET LG_ENV=C:\Users\USER\anaconda3\envs\lightgaussian
SET VCVARS="C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvarsall.bat"
SET "PATH=%LG_ENV%;%LG_ENV%\Library\mingw-w64\bin;%LG_ENV%\Library\usr\bin;%LG_ENV%\Library\bin;%LG_ENV%\Scripts;C:\Users\USER\anaconda3\Scripts;%PATH%"

echo [Setup] Activating MSVC x64 environment...
SET DISTUTILS_USE_SDK=1
CALL %VCVARS% x64
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] vcvarsall failed & exit /b 1)

echo [1/2] Building simple-knn...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"
"%LG_PIP%" install submodules/simple-knn --no-build-isolation
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] simple-knn build failed & exit /b 1)

echo [2/2] Building compress-diff-gaussian-rasterization...
"%LG_PIP%" install submodules/compress-diff-gaussian-rasterization --no-build-isolation
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] rasterizer build failed & exit /b 1)

echo [DONE] All LightGaussian submodules built successfully.
