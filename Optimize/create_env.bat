@echo off
SET DISTUTILS_USE_SDK=1

REM Initialize conda PATH (needed for SSL and conda itself to work outside Anaconda Prompt)
SET PATH=C:\Users\USER\anaconda3;C:\Users\USER\anaconda3\Library\mingw-w64\bin;C:\Users\USER\anaconda3\Library\usr\bin;C:\Users\USER\anaconda3\Library\bin;C:\Users\USER\anaconda3\Scripts;%PATH%

REM Init conda shell
CALL C:\Users\USER\anaconda3\Scripts\activate.bat C:\Users\USER\anaconda3

cd /d D:\JM\cgxr\CGXR\Optimize
conda env create --file environment.yml
echo EXIT CODE: %ERRORLEVEL%
