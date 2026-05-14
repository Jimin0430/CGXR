import os

files = [
    ("SfM 초기 (input.ply)",         "D:/JM/cgxr/CGXR/output/input.ply"),
    ("3DGS 30k (point_cloud.ply)",    "D:/JM/cgxr/CGXR/output/point_cloud/iteration_30000/point_cloud.ply"),
    ("Stage1 Pruned (point_cloud.ply)","D:/JM/cgxr/CGXR/output_lightgaussian/stage1_pruned/point_cloud/iteration_35000/point_cloud.ply"),
    ("Stage2 Distilled (point_cloud.ply)","D:/JM/cgxr/CGXR/output_lightgaussian/stage2_distilled/point_cloud/iteration_40000/point_cloud.ply"),
    ("Stage3 Quantized (extreme_saving.zip)","D:/JM/cgxr/CGXR/output_lightgaussian/stage3_quantized/extreme_saving.zip"),
]

print(f"{'단계':<40} {'크기(MB)':>10}")
print("-" * 52)
for name, path in files:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"{name:<40} {size_mb:>9.2f} MB")
    else:
        print(f"{name:<40} {'파일 없음':>10}")
