# CGXR Project Setup Log

## 1. Environment Analysis

- **CUDA**: 11.7 installed (nvcc) — compatible with `cudatoolkit=11.6` in env.yml
- **Conda**: Found at `C:\Users\USER\anaconda3` (v22.9.0), only `base` env existed
- **Visual Studio**: 2019 Community + 2022 both present; MSVC `cl.exe` confirmed at VS2019
- **Submodules**: All 3 directories existed but were **empty** (no `.gitmodules`, not real git submodules)

---

## 2. Repo Structure Clarification

The actual working codebase lives under `Optimize/`:

```
CGXR/
├── Extract_SfM/          ← COLMAP reconstruction output + images (images/ was empty)
│   ├── sparse/0/         ← cameras.bin, images.bin, points3D.bin
│   └── images/           ← ⚠ needs 263 .jpg files placed here
├── SfM_to_Gaussian/      ← converted point cloud + helper scripts
│   └── points3D.ply      ← 84,663 points, format: x,y,z,nx,ny,nz,r,g,b
├── Optimize/             ← 3DGS training code (train.py, scene/, etc.)
│   ├── submodules/       ← CUDA extension source (was empty)
│   ├── environment.yml
│   └── train.py
└── tandt_db/             ← example datasets
```

---

## 3. Submodules Populated

**Source**: `https://github.com/jonstephens85/gaussian-splatting-Windows` (shallow clone `--depth 1`, no git history)

Cloned to `temp_gs/gs_win/`, then copied without `.git` dirs into `Optimize/submodules/`:

| Submodule | Contents |
|-----------|----------|
| `diff-gaussian-rasterization` | CUDA rasterizer + `third_party/glm` |
| `simple-knn` | KNN CUDA extension |
| `fused-ssim` | *(empty — not in Windows fork)* |

Temp clone deleted after copy.

---

## 4. environment.yml Fixed

Removed `fused-ssim` pip entry — it has no source in the Windows fork:

```yaml
# Before:
  - pip:
    - submodules/diff-gaussian-rasterization
    - submodules/simple-knn
    - submodules/fused-ssim   # ← removed
    - opencv-python
    - joblib

# After:
  - pip:
    - submodules/diff-gaussian-rasterization
    - submodules/simple-knn
    - opencv-python
    - joblib
```

Note: `train.py` imports `fused_ssim` with a `try/except` — gracefully falls back if absent.

---

## 5. Initial Point Cloud Wired In

`dataset_readers.py` (line 205-214) checks for `sparse/0/points3D.ply` before converting from `.bin`. Placing our PLY there means the trainer uses it directly as the Gaussian initialization.

**Action**: Copied `SfM_to_Gaussian/points3D.ply` → `Extract_SfM/sparse/0/points3D.ply`

- 84,663 points
- Format verified compatible: `x,y,z,nx,ny,nz,red(u1),green(u1),blue(u1)`

---

## 6. Conda Environment Creation (In Progress)

**Issue encountered**: Git Bash interprets `/c` as the `C:\` drive mount — `cmd /c` was silently doing nothing. Fixed by using `cmd //c`.

**Second issue**: `CondaSSLError` — OpenSSL DLLs not in PATH when running outside Anaconda Prompt.

**Fix**: Created `Optimize/create_env.bat` that initializes Anaconda PATH before calling conda:

```bat
SET DISTUTILS_USE_SDK=1
SET PATH=C:\Users\USER\anaconda3;...\Library\bin;...\Scripts;%PATH%
CALL C:\Users\USER\anaconda3\Scripts\activate.bat C:\Users\USER\anaconda3
cd /d D:\JM\cgxr\CGXR\Optimize
conda env create --file environment.yml
```

**Status**: Running in background (task `b8jkqc8hd`). Will install:
- Python 3.7.13, PyTorch 1.12.1, cudatoolkit=11.6, torchaudio, torchvision, tqdm, plyfile
- Compile & install `diff-gaussian-rasterization` (CUDA)
- Compile & install `simple-knn` (CUDA)
- Install `opencv-python`, `joblib`

---

## 7. Training Setup (Pending — images needed)

**Blocker**: `Extract_SfM/images/` is empty. The COLMAP reconstruction references **263 `.jpg` files** (`IMG_6292.jpg` … sequence). These must be placed at:
```
D:\JM\cgxr\CGXR\Extract_SfM\images\
```

**Training command** (once env + images are ready — run from Anaconda Prompt):

```bat
conda activate gaussian_splatting
cd D:\JM\cgxr\CGXR\Optimize

python train.py ^
  -s D:\JM\cgxr\CGXR\Extract_SfM ^
  -m D:\JM\cgxr\CGXR\output ^
  --iterations 7000 ^
  --save_iterations 7000 ^
  --test_iterations 7000
```

**Expected output**:
```
output/
  point_cloud/iteration_7000/point_cloud.ply   ← trained Gaussian splats
  cameras.json                                 ← camera poses
  input.ply                                    ← copy of initial points3D.ply
  cfg_args                                     ← saved run config
```

---

## Remaining Steps

| Step | Status |
|------|--------|
| conda env `gaussian_splatting` created | ⏳ running |
| Place 263 `.jpg` images in `Extract_SfM/images/` | ❌ needs user action |
| Run training | ❌ blocked on above two |
