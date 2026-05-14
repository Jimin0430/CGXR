@echo off
SET ENV=C:\Users\USER\anaconda3\envs\gaussian_splatting
SET "PATH=%ENV%;%ENV%\Library\mingw-w64\bin;%ENV%\Library\usr\bin;%ENV%\Library\bin;%ENV%\Scripts;C:\Users\USER\anaconda3\Scripts;%PATH%"
"%ENV%\python.exe" D:\JM\cgxr\CGXR\check_sizes.py
