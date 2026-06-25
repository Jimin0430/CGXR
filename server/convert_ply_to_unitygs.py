#!/usr/bin/env python3
"""
PLY (3DGS) → .unitygs 바이너리 변환기.

파일 레이아웃:
  uint32  magic      = 0x41534755 ('UGSA')
  uint32  version    = 1
  uint32  splatCount
  float32[N][3]  positions
  float32[N][3]  scales
  float32[N][4]  rotations  (xyzw quaternion, normalized)
  float32[N][4]  colors     (RGBA 0-1)
  bool           hasSH
  float32[N][48] shCoeffs   (SHTableItemFloat32 레이아웃: 15 float3 + 1 padding float3)
                             if hasSH

사용:
  python convert_ply_to_unitygs.py <input.ply> <output.unitygs>
"""
import os, struct, sys
import numpy as np

try:
    from plyfile import PlyData
except ImportError:
    sys.exit("plyfile package not found. Install with: pip install plyfile")

MAGIC = 0x41534755
VERSION = 1


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -88, 88)))


def _morton_part1by2(v: np.ndarray) -> np.ndarray:
    """21비트 정수마다 2개의 0 비트를 삽입 (GaussianUtils.MortonPart1By2 포팅)."""
    x = v.astype(np.uint64)
    x &= np.uint64(0x1fffff)
    x = (x ^ (x << np.uint64(32))) & np.uint64(0x1f00000000ffff)
    x = (x ^ (x << np.uint64(16))) & np.uint64(0x1f0000ff0000ff)
    x = (x ^ (x << np.uint64(8)))  & np.uint64(0x100f00f00f00f00f)
    x = (x ^ (x << np.uint64(4)))  & np.uint64(0x10c30c30c30c30c3)
    x = (x ^ (x << np.uint64(2)))  & np.uint64(0x1249249249249249)
    return x


def _morton3d_sort_indices(positions: np.ndarray) -> np.ndarray:
    """에디터 ReorderMorton과 동일하게 3D Morton 코드 기준 정렬 인덱스 반환."""
    bmin = positions.min(axis=0)
    bsize = np.maximum(positions.max(axis=0) - bmin, np.float32(1e-8))
    kScaler = float((1 << 21) - 1)
    norm = (positions.astype(np.float32) - bmin) / bsize * kScaler
    ipos = np.clip(norm, 0, kScaler).astype(np.uint32)
    codes = (
        (_morton_part1by2(ipos[:, 2]) << np.uint64(2)) |
        (_morton_part1by2(ipos[:, 1]) << np.uint64(1)) |
         _morton_part1by2(ipos[:, 0])
    )
    return np.argsort(codes, kind='stable')


def convert(ply_path: str, out_path: str, include_sh: bool = True) -> None:
    print(f"[convert_ply_to_unitygs] Reading {ply_path}")
    plydata = PlyData.read(ply_path)
    v = plydata["vertex"]
    n = len(v.data)
    print(f"[convert_ply_to_unitygs] {n:,} splats")

    # ── Positions (xyz) ──────────────────────────────────────────────────
    positions = np.column_stack([
        v["x"].astype(np.float32),
        v["y"].astype(np.float32),
        v["z"].astype(np.float32),
    ])

    # ── Scales (log-space → linear) ──────────────────────────────────────
    scales = np.exp(np.column_stack([
        v["scale_0"].astype(np.float32),
        v["scale_1"].astype(np.float32),
        v["scale_2"].astype(np.float32),
    ]))

    # ── Rotations (quaternion, xyzw, normalize) ───────────────────────────
    # 3DGS PLY 저장 규약: rot_0=w, rot_1=x, rot_2=y, rot_3=z (wxyz 순서)
    # Unity/로더 규약: [x, y, z, w] 순서로 저장해야 Quaternion(x,y,z,w)로 올바르게 읽힘
    rotations = np.column_stack([
        v["rot_1"].astype(np.float32),  # x
        v["rot_2"].astype(np.float32),  # y
        v["rot_3"].astype(np.float32),  # z
        v["rot_0"].astype(np.float32),  # w
    ])
    norms = np.linalg.norm(rotations, axis=1, keepdims=True)
    rotations = rotations / np.maximum(norms, 1e-8)

    # ── Colors (DC SH → RGBA) ─────────────────────────────────────────────
    # 3DGS DC SH → 컬러: color = f_dc * SH_C0 + 0.5  (선형 변환, sigmoid 아님)
    # opacity → alpha:  alpha = sigmoid(opacity)
    # Unity HLSL의 ShadeSH: "col = sh0 * SH_C0 + 0.5 is already precomputed"
    _SH_C0 = 0.28209479177387814
    r = np.clip(v["f_dc_0"].astype(np.float32) * _SH_C0 + 0.5, 0.0, 1.0)
    g = np.clip(v["f_dc_1"].astype(np.float32) * _SH_C0 + 0.5, 0.0, 1.0)
    b = np.clip(v["f_dc_2"].astype(np.float32) * _SH_C0 + 0.5, 0.0, 1.0)
    a = np.clip(_sigmoid(v["opacity"].astype(np.float32)), 0.0, 1.0)
    colors = np.column_stack([r, g, b, a])

    # ── SH coefficients ───────────────────────────────────────────────────
    # PLY 저장 형식: R 채널 coeffs 전체 → G 채널 → B 채널
    #   degree1: rest 9개  (채널당 3)
    #   degree2: rest 24개 (채널당 8)  ← LightGaussian --new_max_sh 2
    #   degree3: rest 45개 (채널당 15)
    # .unitygs SH 형식: SHTableItemFloat32 = 15 float3 + 1 padding = 48 floats/splat
    #   sh[i*3+0]=R, sh[i*3+1]=G, sh[i*3+2]=B for coefficient i (0-indexed)
    #   degree보다 높은 계수는 0으로 패딩
    rest_names = sorted([k for k in v.data.dtype.names if k.startswith("f_rest_")],
                        key=lambda s: int(s.split("_")[-1]))
    has_sh = include_sh and len(rest_names) >= 9  # degree1 이상이면 SH 포함

    if has_sh:
        coeffs_per_ch = len(rest_names) // 3      # 채널당 계수 수 (3, 8, 15 중 하나)
        actual_coeffs = min(coeffs_per_ch, 15)    # SHTableItemFloat32 최대 15개
        sh = np.zeros((n, 48), dtype=np.float32)  # 15 float3 + 1 padding float3
        for i in range(actual_coeffs):
            sh[:, i * 3 + 0] = v[rest_names[i]].astype(np.float32)                    # R
            sh[:, i * 3 + 1] = v[rest_names[i + coeffs_per_ch]].astype(np.float32)    # G
            sh[:, i * 3 + 2] = v[rest_names[i + 2 * coeffs_per_ch]].astype(np.float32) # B
        print(f"[convert_ply_to_unitygs] SH degree={coeffs_per_ch} ({len(rest_names)} rest coeffs)")

    # ── Morton 3D 재정렬 (에디터 ReorderMorton과 동일) ──────────────────────
    # 에디터는 splat을 3D 공간 Morton 순서로 재정렬한 뒤 저장한다.
    # 정렬 없이 렌더링 시 저장 순서 그대로 합성되므로 공간 순서가 화질에 직접 영향.
    order = _morton3d_sort_indices(positions)
    positions  = positions[order]
    scales     = scales[order]
    rotations  = rotations[order]
    colors     = colors[order]
    if has_sh:
        sh = sh[order]
    print(f"[convert_ply_to_unitygs] Morton 3D reordering done")

    # ── Write .unitygs ────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(struct.pack("<III", MAGIC, VERSION, n))
        f.write(positions.astype(np.float32).tobytes())
        f.write(scales.astype(np.float32).tobytes())
        f.write(rotations.astype(np.float32).tobytes())
        f.write(colors.astype(np.float32).tobytes())
        f.write(struct.pack("?", has_sh))
        if has_sh:
            f.write(sh.tobytes())

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"[convert_ply_to_unitygs] → {out_path} ({size_mb:.1f} MB, hasSH={has_sh})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_ply_to_unitygs.py <input.ply> <output.unitygs>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
