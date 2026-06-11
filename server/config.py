from pathlib import Path
import os

BASE = Path(os.getenv("CGXR_BASE", r"D:\JM\cgxr\CGXR"))

# 프로젝트 디렉터리
MOBILE_GS_DIR  = BASE / "mobile_gs"
LG_REPO_DIR    = BASE / "LightGaussian" / "repo"
EXTRACT_SFM_DIR = BASE / "Extract_SfM"

# 실행 파일
COLMAP_EXE    = BASE / "colmap_nocuda" / "bin" / "colmap.exe"
SAM2_ENV_PY   = BASE / "sam2_env" / "Scripts" / "python.exe"
SAM2_CKPT     = BASE / "sam2.1_hiera_large.pt"
SAM2_CFG      = "configs/sam2.1/sam2.1_hiera_l.yaml"

ANACONDA      = Path(os.getenv("CONDA_ROOT", r"C:\Users\USER\anaconda3"))
MOBILE_GS_PY  = ANACONDA / "envs" / "mobile-gs"  / "python.exe"
LG_PY         = ANACONDA / "envs" / "lightgaussian" / "python.exe"

# 서버 내부 경로
SERVER_DIR    = BASE / "server"
JOBS_STORE    = SERVER_DIR / "jobs_store"
UPLOADS_DIR   = SERVER_DIR / "uploads"
WORKDIR       = SERVER_DIR / "workdir"

# 학습 설정
PRETRAIN_ITERS    = 30_000
LG_PRUNE_ITERS    = 35_000
LG_DISTILL_ITERS  = 40_000
LG_PRUNE_PERCENT  = 0.66
LG_VQ_RATIO       = 0.6
LG_CODEBOOK_SIZE  = 8192

# API 인증
API_KEY = os.getenv("CGXR_API_KEY", "changeme")
