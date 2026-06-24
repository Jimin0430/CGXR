from pathlib import Path
import os

BASE = Path(os.getenv("CGXR_BASE", r"D:\JM\cgxr\CGXR"))

# 프로젝트 디렉터리
GS_TRAIN_DIR   = BASE / "3dgsTrain"
LG_REPO_DIR    = BASE / "LightGaussian" / "repo"
EXTRACT_SFM_DIR = BASE / "Extract_SfM"

# 실행 파일
COLMAP_EXE    = BASE / "colmap" / "bin" / "colmap.exe"
SAM2_ENV_PY   = BASE / "sam2_env" / "Scripts" / "python.exe"
SAM2_CKPT     = BASE / "sam2.1_hiera_large.pt"
SAM2_CFG      = "configs/sam2.1/sam2.1_hiera_l.yaml"

ANACONDA      = Path(os.getenv("CONDA_ROOT", r"C:\Users\USER\anaconda3"))
MOBILE_GS_PY  = ANACONDA / "envs" / "mobile-gs"  / "Scripts" / "python.exe"
LG_PY         = ANACONDA / "envs" / "lightgaussian" / "python.exe"

# 서버 내부 경로
SERVER_DIR    = BASE / "server"
JOBS_STORE    = SERVER_DIR / "jobs_store"
UPLOADS_DIR   = SERVER_DIR / "uploads"
WORKDIR       = SERVER_DIR / "workdir"

# 학습 설정
GS_TRAIN_ITERS    = 30_000
LG_PRUNE_ITERS    = 35_000
LG_DISTILL_ITERS  = 40_000
LG_PRUNE_PERCENT  = 0.66
LG_VQ_RATIO       = 0.6
LG_CODEBOOK_SIZE  = 8192

# Unity 배치 모드 변환
UNITY_EXE         = Path(os.getenv("UNITY_EXE",
                        r"C:\Program Files\Unity\Hub\Editor\6000.5.0f1\Editor\Unity.exe"))
UNITY_PROJECT_DIR = BASE / "UnityProject"
UNITY_QUALITY     = os.getenv("UNITY_QUALITY", "Medium")

# API 인증
API_KEY = os.getenv("CGXR_API_KEY", "changeme")
