@echo off
SET ENV=C:\Users\USER\anaconda3\envs\gaussian_splatting
SET "PATH=%ENV%;%ENV%\Library\mingw-w64\bin;%ENV%\Library\usr\bin;%ENV%\Library\bin;%ENV%\Scripts;C:\Users\USER\anaconda3\Scripts;%PATH%"

echo [STEP 1] 3DGS Training on lego dataset (min_opacity=0.01)...
cd /d "D:\JM\cgxr\CGXR\Optimize"

"%ENV%\python.exe" train.py ^
  -s "D:\JM\cgxr\CGXR\data\lego" ^
  -m "D:\JM\cgxr\CGXR\output_opacity01" ^
  --eval ^
  --white_background ^
  --min_opacity 0.01 ^
  --save_iterations 7000 30000 ^
  --checkpoint_iterations 30000 ^
  --disable_viewer

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Training failed with code %ERRORLEVEL%.
    exit /b 1
)
echo [DONE] Training complete.
