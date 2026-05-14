import re, json, os
import numpy as np

def count_log(path, keywords):
    try:
        with open(path, 'rb') as f:
            data = f.read().decode('utf-8', errors='replace')
        lines = re.split(r'[\r\n]+', data)
        result = []
        for l in lines:
            if any(k.lower() in l.lower() for k in keywords):
                result.append(l.strip())
        return result
    except Exception as e:
        return [str(e)]

# 1. 이미지 수 (transforms_train.json)
try:
    with open('D:/JM/cgxr/CGXR/data/lego/transforms_train.json') as f:
        tj = json.load(f)
    print(f"[이미지 수] train: {len(tj['frames'])} 장")
except Exception as e:
    print(f"[이미지 수] 오류: {e}")

try:
    with open('D:/JM/cgxr/CGXR/data/lego/transforms_test.json') as f:
        tj = json.load(f)
    print(f"[이미지 수] test: {len(tj['frames'])} 장")
except:
    pass

# 2. SfM 초기 포인트 수 (train_log에서 "Number of points" 등)
print("\n--- train_log.txt (SfM 초기 + 3DGS) ---")
for l in count_log('D:/JM/cgxr/CGXR/train_log.txt',
    ['point', 'gaussian', 'Number of', 'points at', 'densif', 'total', 'scene', 'loaded']):
    print(l)

# 3. PLY 파일로 가우시안 수 직접 세기
def count_ply_points(path):
    try:
        with open(path, 'rb') as f:
            header = b''
            while True:
                line = f.readline()
                header += line
                if line.strip() == b'end_header':
                    break
        header_str = header.decode('utf-8', errors='replace')
        m = re.search(r'element vertex (\d+)', header_str)
        return int(m.group(1)) if m else -1
    except Exception as e:
        return str(e)

plys = [
    ('3DGS 30k', 'D:/JM/cgxr/CGXR/output/point_cloud/iteration_30000/point_cloud.ply'),
    ('Stage1 35k', 'D:/JM/cgxr/CGXR/output_lightgaussian/stage1_pruned/point_cloud/iteration_35000/point_cloud.ply'),
    ('Stage2 40k', 'D:/JM/cgxr/CGXR/output_lightgaussian/stage2_distilled/point_cloud/iteration_40000/point_cloud.ply'),
]
print("\n--- PLY 파일 가우시안 수 ---")
for name, path in plys:
    n = count_ply_points(path)
    print(f"[{name}] {n:,} 개" if isinstance(n, int) else f"[{name}] {n}")

# Stage3 quantized - npz로 확인
print("\n--- Stage3 VecTree Quantized ---")
stage3_dir = 'D:/JM/cgxr/CGXR/output_lightgaussian/stage3_quantized/extreme_saving'
if os.path.isdir(stage3_dir):
    for f in os.listdir(stage3_dir):
        fp = os.path.join(stage3_dir, f)
        try:
            data = np.load(fp)
            for k in data.files:
                print(f"  {f} [{k}]: shape={data[k].shape}")
        except Exception as e:
            print(f"  {f}: {e}")
