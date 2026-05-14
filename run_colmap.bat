@echo off
SET COLMAP=D:\JM\cgxr\CGXR\colmap_nocuda\bin\colmap.exe
SET SRC=D:\JM\cgxr\CGXR\data\my_video
SET DB=%SRC%\distorted\database.db

mkdir "%SRC%\distorted\sparse" 2>nul

echo [1/4] Feature extraction...
"%COLMAP%" feature_extractor --database_path "%DB%" --image_path "%SRC%\input" --ImageReader.single_camera 1 --ImageReader.camera_model OPENCV --FeatureExtraction.use_gpu 0
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Feature extraction failed & exit /b %ERRORLEVEL%)

echo [2/4] Sequential matching...
"%COLMAP%" sequential_matcher --database_path "%DB%" --FeatureMatching.use_gpu 0
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Matching failed & exit /b %ERRORLEVEL%)

echo [3/4] Mapper...
"%COLMAP%" mapper --database_path "%DB%" --image_path "%SRC%\input" --output_path "%SRC%\distorted\sparse" --Mapper.ba_global_function_tolerance=0.000001
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Mapper failed & exit /b %ERRORLEVEL%)

echo [4/4] Undistortion...
"%COLMAP%" image_undistorter --image_path "%SRC%\input" --input_path "%SRC%\distorted\sparse\0" --output_path "%SRC%" --output_type COLMAP
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Undistortion failed & exit /b %ERRORLEVEL%)

echo [OK] COLMAP ??
