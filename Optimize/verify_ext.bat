@echo off
SET PATH=C:\Users\USER\anaconda3;C:\Users\USER\anaconda3\Library\mingw-w64\bin;C:\Users\USER\anaconda3\Library\usr\bin;C:\Users\USER\anaconda3\Library\bin;C:\Users\USER\anaconda3\Scripts;%PATH%
CALL C:\Users\USER\anaconda3\Scripts\activate.bat gaussian_splatting

python -c "from diff_gaussian_rasterization import GaussianRasterizer; print('diff_gaussian_rasterization: OK')"
python -c "import simple_knn; print('simple_knn: OK')"
python -c "import torch; print('torch:', torch.__version__, '| CUDA:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
