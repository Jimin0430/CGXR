@echo off
SET LG_ENV=C:\Users\USER\anaconda3\envs\lightgaussian
SET "PATH=%LG_ENV%;%LG_ENV%\Library\mingw-w64\bin;%LG_ENV%\Library\usr\bin;%LG_ENV%\Library\bin;%LG_ENV%\Scripts;C:\Users\USER\anaconda3\Scripts;%PATH%"

echo [Stage 3] VecTree Quantization...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo\vectree"

"%LG_ENV%\python.exe" vectree.py ^
  --important_score_npz_path "D:\JM\cgxr\CGXR\output_lightgaussian\stage2_distilled" ^
  --input_path "D:\JM\cgxr\CGXR\output_lightgaussian\stage2_distilled\point_cloud\iteration_40000\point_cloud.ply" ^
  --save_path "D:\JM\cgxr\CGXR\output_lightgaussian\stage3_quantized" ^
  --sh_degree 2 ^
  --vq_ratio 0.6 ^
  --codebook_size 8192

IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Stage 3 failed & exit /b 1)
echo [DONE] Stage 3 complete.
