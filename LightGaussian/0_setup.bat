@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET "PATH=%ANACONDA%;%ANACONDA%\Library\bin;%ANACONDA%\Scripts;%PATH%"
CALL "%ANACONDA%\Scripts\activate.bat" "%ANACONDA%"

cd /d "D:\JM\cgxr\CGXR\LightGaussian"

IF EXIST "repo\train.py" (
    echo [OK] repo already exists, skipping clone.
) ELSE (
    echo [1/2] Cloning LightGaussian...
    git clone --recursive https://github.com/VITA-Group/LightGaussian.git repo
)

echo [2/2] Creating conda env lightgaussian...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"
conda env create --file environment.yml

echo.
echo Setup complete! Next: run 1_stage1_prune.bat
pause
