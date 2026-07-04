@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

SET MOBILE_GS_PY=C:\Users\USER\anaconda3\envs\mobile-gs\Scripts\python.exe
SET LG_PY=C:\Users\USER\anaconda3\envs\lightgaussian\python.exe
SET COLMAP=D:\JM\cgxr\CGXR\colmap\bin\colmap.exe

SET VIDEO=D:\JM\cgxr\CGXR\my_video.mov
SET SCENE=D:\JM\cgxr\CGXR\test_fresh\scene
SET OUTPUT=D:\JM\cgxr\CGXR\test_fresh\output
SET LG_OUT=D:\JM\cgxr\CGXR\test_fresh\lg_output

SET EXTRACT_SFM=D:\JM\cgxr\CGXR\Extract_SfM
SET GS_TRAIN=D:\JM\cgxr\CGXR\3dgsTrain
SET LG_REPO=D:\JM\cgxr\CGXR\LightGaussian\repo

mkdir "%SCENE%" 2>nul
mkdir "%OUTPUT%" 2>nul
mkdir "%LG_OUT%\stage1" 2>nul
mkdir "%LG_OUT%\stage2" 2>nul
mkdir "%LG_OUT%\stage3" 2>nul

echo [STEP 1] Video -^> Frames + COLMAP
cd /d "%EXTRACT_SFM%"
"%MOBILE_GS_PY%" convert.py --source_path "%SCENE%" --video "%VIDEO%" --every_n_frames 10 --sequential --colmap_executable "%COLMAP%"
IF %ERRORLEVEL% NEQ 0 ( echo [ERROR] COLMAP failed & pause & exit /b 1 )
echo [OK] COLMAP done

echo [STEP 2] 3DGS train (30000 iters)
cd /d "%GS_TRAIN%"
"%LG_PY%" train.py -s "%SCENE%" -m "%OUTPUT%" --eval --iterations 30000 --save_iterations 30000 --checkpoint_iterations 30000
IF %ERRORLEVEL% NEQ 0 ( echo [ERROR] 3DGS failed & pause & exit /b 1 )
echo [OK] 3DGS done

echo [STEP 3] LG Stage1 Prune
cd /d "%LG_REPO%"
"%LG_PY%" prune_finetune.py -s "%SCENE%" -m "%LG_OUT%\stage1" --start_checkpoint "%OUTPUT%\chkpnt30000.pth" --iteration 35000 --prune_percent 0.66 --prune_type v_important_score --prune_decay 1 --position_lr_max_steps 35000 --v_pow 0.1
IF %ERRORLEVEL% NEQ 0 ( echo [ERROR] LG Stage1 failed & pause & exit /b 1 )
echo [OK] LG Stage1 done

echo [STEP 4] LG Stage2 Distill
"%LG_PY%" distill_train.py -s "%SCENE%" -m "%LG_OUT%\stage2" --start_checkpoint "%LG_OUT%\stage1\chkpnt35000.pth" --iteration 40000 --teacher_model "%OUTPUT%\chkpnt30000.pth" --new_max_sh 2 --position_lr_max_steps 40000 --enable_covariance --augmented_view
IF %ERRORLEVEL% NEQ 0 ( echo [ERROR] LG Stage2 failed & pause & exit /b 1 )
echo [OK] LG Stage2 done

echo [STEP 5] LG Stage3 Quantize
"%LG_PY%" vectree/vectree.py --important_score_npz_path "%LG_OUT%\stage2" --input_path "%LG_OUT%\stage2\point_cloud\iteration_40000\point_cloud.ply" --save_path "%LG_OUT%\stage3" --vq_ratio 0.6 --codebook_size 8192
IF %ERRORLEVEL% NEQ 0 ( echo [ERROR] LG Stage3 failed & pause & exit /b 1 )

echo ALL DONE
echo Final PLY: %LG_OUT%\stage3
pause