# Next Steps

## Step 1 — Wait for conda env to finish (or check if done)

Open Anaconda Prompt and verify the environment exists:

```bat
conda env list
```

You should see `gaussian_splatting` listed. If not, run the batch file manually:

```bat
D:\JM\cgxr\CGXR\Optimize\create_env.bat
```

---

## Step 2 — Place your images

Copy your **263 original `.jpg` photos** into:

```
D:\JM\cgxr\CGXR\Extract_SfM\images\
```

These are the same photos you originally ran through COLMAP (`IMG_6292.jpg` … sequence).
Training will crash immediately if this folder is empty.

---

## Step 3 — Run training

Open **Anaconda Prompt** (not PowerShell, not Git Bash) and run:

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

Expected training time: **~15–30 min** depending on GPU.
You will see a progress bar counting up to 7000 iterations with loss values.

---

## Step 4 — Collect results

When training finishes, your output is at:

```
D:\JM\cgxr\CGXR\output\
  point_cloud\
    iteration_7000\
      point_cloud.ply     ← trained Gaussian splats (open in Supersplat / SIBR viewer)
  cameras.json            ← camera poses
  input.ply               ← initial point cloud used
  cfg_args                ← saved config for reference
```

---

## Troubleshooting

### "No module named diff_gaussian_rasterization"
The CUDA extension didn't compile. Re-run the batch file and check for MSVC errors:
```bat
D:\JM\cgxr\CGXR\Optimize\create_env.bat
```

### "FileNotFoundError" on images
Images are missing from `Extract_SfM\images\`. Go back to Step 2.

### "CUDA out of memory"
Add `--data_device cpu` to the training command to move dataset off GPU:
```bat
python train.py -s ... -m ... --iterations 7000 --save_iterations 7000 --data_device cpu
```

### Training is slow / want lower resolution
Add `-r 2` (half resolution) or `-r 4` (quarter resolution):
```bat
python train.py -s ... -m ... --iterations 7000 --save_iterations 7000 -r 2
```

### Want to resume or re-run with different settings
Delete or rename the `output\` folder first, then re-run `train.py`.
Or use a different `-m` path to save alongside the previous run.
