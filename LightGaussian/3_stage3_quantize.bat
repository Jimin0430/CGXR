@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET "PATH=%ANACONDA%;%ANACONDA%\Library\bin;%ANACONDA%\Scripts;%PATH%"
CALL "%ANACONDA%\Scripts\activate.bat" "%ANACONDA%"
CALL conda activate lightgaussian

SET STAGE2_DIR=D:\JM\cgxr\CGXR\output_lightgaussian\stage2_distilled
SET INPUT_PLY=%STAGE2_DIR%\point_cloud\iteration_40000\point_cloud.ply
SET OUTPUT=D:\JM\cgxr\CGXR\output_lightgaussian\stage3_quantized

IF NOT EXIST "%INPUT_PLY%" (
    echo [ERROR] Stage 2 output not found: %INPUT_PLY%
    echo Run 2_stage2_distill.bat first.
    pause
    exit /b 1
)

echo [Stage 3] VecTree Quantization...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"

python vectree/vectree.py ^
  --important_score_npz_path "%STAGE2_DIR%" ^
  --input_path "%INPUT_PLY%" ^
  --save_path "%OUTPUT%" ^
  --vq_ratio 0.6 ^
  --codebook_size 8192

echo Stage 3 done! Final output: %OUTPUT%
pause
