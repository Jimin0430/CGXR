@echo off
SET PATH=C:\Users\USER\anaconda3;C:\Users\USER\anaconda3\Library\mingw-w64\bin;C:\Users\USER\anaconda3\Library\usr\bin;C:\Users\USER\anaconda3\Library\bin;C:\Users\USER\anaconda3\Scripts;%PATH%
CALL C:\Users\USER\anaconda3\Scripts\activate.bat gaussian_splatting

pip install opencv-python joblib
python -c "import cv2; print('cv2 OK:', cv2.__version__)"
python -c "import joblib; print('joblib OK:', joblib.__version__)"
