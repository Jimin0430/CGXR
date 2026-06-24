@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET ENV=%ANACONDA%\envs\mobile-gs
SET "PATH=%ENV%;%ENV%\Scripts;%ANACONDA%\Scripts;%PATH%"

SET CGXR_API_KEY=changeme
SET CGXR_BASE=D:\JM\cgxr\CGXR

cd /d "%~dp0"
if not exist logs mkdir logs
"%ENV%\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-config log_config.json
