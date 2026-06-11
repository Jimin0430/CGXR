@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET ENV=%ANACONDA%\envs\mobile-gs
SET "PATH=%ENV%;%ENV%\Scripts;%ANACONDA%\Scripts;%PATH%"

SET CGXR_API_KEY=changeme
SET CGXR_BASE=D:\JM\cgxr\CGXR

cd /d "%~dp0"
"%ENV%\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
