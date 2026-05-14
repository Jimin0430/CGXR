@echo off
SET COLMAP=D:\JM\cgxr\CGXR\colmap_nocuda\bin\colmap.exe
SET SRC=D:\JM\cgxr\CGXR\data\my_video
SET DB=%SRC%\distorted\database.db
SET LOG=D:\JM\cgxr\CGXR\colmap_detail.log

mkdir "%SRC%\distorted\sparse" 2>nul

echo [1/4] Feature extraction...
"%COLMAP%" feature_extractor --database_path "%DB%" --image_path "%SRC%\input" --ImageReader.single_camera 1 > "%LOG%" 2>&1
IF %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Feature extraction failed. See colmap_detail.log
  type "%LOG%"
  exit /b %ERRORLEVEL%
)

echo [2/4] Sequential matching...
"%COLMAP%" sequential_matcher --database_path "%DB%" >> "%LOG%" 2>&1
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Matching failed & type "%LOG%" & exit /b %ERRORLEVEL%)

echo [3/4] Mapper...
"%COLMAP%" mapper --database_path "%DB%" --image_path "%SRC%\input" --output_path "%SRC%\distorted\sparse" --Mapper.ba_global_function_tolerance=0.000001 >> "%LOG%" 2>&1
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Mapper failed & type "%LOG%" & exit /b %ERRORLEVEL%)

echo [4/4] Undistortion...
"%COLMAP%" image_undistorter --image_path "%SRC%\input" --input_path "%SRC%\distorted\sparse\0" --output_path "%SRC%" --output_type COLMAP >> "%LOG%" 2>&1
IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Undistortion failed & type "%LOG%" & exit /b %ERRORLEVEL%)

echo [OK] COLMAP ??
