import sys
print("Python:", sys.version)
import numpy
print("numpy:", numpy.__version__)
import torch
print("torch:", torch.__version__, "CUDA:", torch.cuda.is_available())
