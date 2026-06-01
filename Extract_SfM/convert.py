#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import os
import sys
import logging
import shutil
import subprocess
import fractions
from argparse import ArgumentParser
from pathlib import Path

parser = ArgumentParser("Colmap converter")
parser.add_argument("--skip_matching", action='store_true')
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--camera", default="OPENCV", type=str)
parser.add_argument("--resize", action="store_true")
parser.add_argument("--magick_executable", default="", type=str)
# ── 영상 입력 ──────────────────────────────────────────────────────────────
parser.add_argument("--video", default="", type=str,
                    help="영상 파일 경로. 지정하면 input/ 폴더에 프레임을 자동 추출합니다.")
parser.add_argument("--every_n_frames", default=15, type=int,
                    help="N프레임마다 1장 추출 (기본값: 15)")
parser.add_argument("--min_frames", default=100, type=int,
                    help="최소 추출 장 수 (기본값: 100)")
parser.add_argument("--sequential", action='store_true',
                    help="영상 데이터용 sequential_matcher 사용")
# ── SAM 2 배경 제거 ────────────────────────────────────────────────────────
parser.add_argument("--sam2_checkpoint", default="", type=str,
                    help="SAM 2 가중치(.pt) 경로. 지정하면 배경 제거를 수행합니다.")
parser.add_argument("--sam2_config",
                    default="configs/sam2.1/sam2.1_hiera_l.yaml", type=str,
                    help="SAM 2 설정 파일 (sam2 패키지 기준 상대경로 또는 절대경로)")
parser.add_argument("--sam2_mode", default=None,
                    choices=["center", "video", "auto"],
                    help="center: 중앙포인트 | video: 비디오전파(시퀀스 권장) | auto: 자동마스크\n"
                         "미지정 시 --video 사용이면 video, 아니면 center 로 자동 결정")
parser.add_argument("--skip_sam2", action='store_true',
                    help="SAM 2 배경 제거 단계를 건너뜀")
args = parser.parse_args()

magick_command = '"{}"'.format(args.magick_executable) if len(args.magick_executable) > 0 else "magick"
source = Path(args.source_path)

# SAM 2 모드 자동 결정 (미지정 시)
sam2_mode = args.sam2_mode or ("video" if (args.video or args.sequential) else "center")

# ══════════════════════════════════════════════════════════════════════════════
## Step 0: 영상 → 프레임 추출
# ══════════════════════════════════════════════════════════════════════════════
if args.video:
    if not os.path.exists(args.video):
        logging.error(f"영상 파일을 찾을 수 없습니다: {args.video}")
        exit(1)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames,r_frame_rate",
         "-of", "csv=p=0", args.video],
        capture_output=True, text=True
    )
    parts = probe.stdout.strip().split(",")
    fps_str, nb_frames_str = parts[0], parts[1]
    video_fps = float(fractions.Fraction(fps_str))
    total_frames = int(nb_frames_str)

    every_n = args.every_n_frames
    if total_frames // every_n < args.min_frames:
        every_n = max(1, total_frames // args.min_frames)
        print(f"간격 자동 조정: {args.every_n_frames}프레임→{every_n}프레임마다 1장 (최소 {args.min_frames}장 보장)")

    extract_fps = video_fps / every_n
    estimated = total_frames // every_n
    print(f"영상 정보: 총 {total_frames}프레임 / {video_fps:.1f}fps")
    print(f"추출 설정: {every_n}프레임마다 1장 → 약 {estimated}장")

    input_dir = source / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_cmd = (
        f'ffmpeg -i "{args.video}" -vf "fps={extract_fps:.6f}" '
        f'"{input_dir}/frame_%04d.jpg" -y'
    )
    exit_code = os.system(ffmpeg_cmd)
    if exit_code != 0:
        logging.error(f"프레임 추출 실패 (code {exit_code}). ffmpeg가 설치되어 있는지 확인하세요.")
        exit(exit_code)
    n_frames = len([f for f in os.listdir(input_dir) if f.endswith(".jpg")])
    print(f"[Step 0] 프레임 추출 완료: {n_frames}장\n")

# ══════════════════════════════════════════════════════════════════════════════
## Steps 1–3: COLMAP SfM (원본 이미지 기준 — 마스킹 전에 수행)
# ══════════════════════════════════════════════════════════════════════════════
if not args.skip_matching:
    import pycolmap

    database_path = source / "distorted" / "database.db"
    image_path = source / "input"
    sparse_path = source / "distorted" / "sparse"
    sparse_path.mkdir(parents=True, exist_ok=True)

    print("[1/3] Feature extraction...")
    reader_options = pycolmap.ImageReaderOptions()
    reader_options.camera_model = args.camera
    pycolmap.extract_features(
        database_path=database_path,
        image_path=image_path,
        camera_mode=pycolmap.CameraMode.SINGLE,
        reader_options=reader_options,
    )

    print("[2/3] Feature matching...")
    if args.sequential or args.video:
        pycolmap.match_sequential(database_path=database_path)
    else:
        pycolmap.match_exhaustive(database_path=database_path)

    print("[3/3] Sparse reconstruction (mapper)...")
    reconstructions = pycolmap.incremental_mapping(
        database_path=database_path,
        image_path=image_path,
        output_path=sparse_path,
    )
    if not reconstructions:
        logging.error("Mapper failed: 재구성 결과가 없습니다. 이미지 품질이나 겹침 영역을 확인하세요.")
        exit(1)
    print(f"재구성 완료: {len(reconstructions)}개 모델\n")

# ══════════════════════════════════════════════════════════════════════════════
## Step 4: 이미지 왜곡 보정 → images/ 생성
# ══════════════════════════════════════════════════════════════════════════════
print("[Step 4] Image undistortion...")
pycolmap.undistort_images(
    output_path=source,
    input_path=source / "distorted" / "sparse" / "0",
    image_path=source / "input",
)

sparse_dir = source / "sparse"
sparse_0 = sparse_dir / "0"
sparse_0.mkdir(parents=True, exist_ok=True)
for f in sparse_dir.iterdir():
    if f.name != "0":
        shutil.move(str(f), str(sparse_0 / f.name))
print("[Step 4] 왜곡 보정 완료\n")

# ══════════════════════════════════════════════════════════════════════════════
## Step 5: SAM 2 배경 제거
#   - images_original/ : 왜곡 보정된 원본 백업
#   - images/          : 배경 제거된 이미지 (3DGS 학습 입력)
#   - masks/           : 바이너리 마스크 PNG
# ══════════════════════════════════════════════════════════════════════════════
if args.sam2_checkpoint and not args.skip_sam2:
    print(f"[Step 5] SAM 2 배경 제거 (모드: {sam2_mode})...")

    import numpy as np
    import torch
    from PIL import Image
    from tqdm import tqdm

    # remove_background_sam2.py 를 같은 폴더에서 임포트
    sys.path.insert(0, str(Path(__file__).parent))
    from remove_background_sam2 import (
        IMG_EXTS,
        load_predictor,
        load_video_predictor,
        load_auto_generator,
        predict_center,
        predict_auto,
        process_video_mode,
        _save_results,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    images_dir  = source / "images"
    orig_dir    = source / "images_original"   # 왜곡 보정 원본 백업
    masks_dir   = source / "masks"
    orig_dir.mkdir(exist_ok=True)
    masks_dir.mkdir(exist_ok=True)

    image_files = sorted(
        [f for f in images_dir.iterdir() if f.suffix.lower() in IMG_EXTS]
    )
    if not image_files:
        logging.error(f"[Step 5] {images_dir} 에 이미지 파일이 없습니다. Step 4가 완료됐는지 확인하세요.")
        exit(1)

    print(f"  대상: {len(image_files)}장 / 디바이스: {device}")

    # 원본 undistorted 이미지 백업
    print("  원본 이미지 백업 중 → images_original/ ...")
    for f in image_files:
        shutil.copy2(f, orig_dir / f.name)

    # ── SAM 2 실행 ──────────────────────────────────────────────────────────
    if sam2_mode == "video":
        # 첫 프레임에만 중앙 포인트 프롬프트 → 전체 시퀀스 전파
        # 결과를 images/ 에 덮어쓰기, masks/ 에 저장
        predictor = load_video_predictor(args.sam2_checkpoint, args.sam2_config, device)
        process_video_mode(
            predictor, images_dir, images_dir, masks_dir, image_files, device
        )

    elif sam2_mode == "auto":
        # 가장 큰 마스크 영역을 피사체로 인식
        generator = load_auto_generator(args.sam2_checkpoint, args.sam2_config, device)
        for fp in tqdm(image_files, desc="  SAM2 auto"):
            img_np = np.array(Image.open(fp).convert("RGB"))
            mask   = predict_auto(generator, img_np)
            _save_results(img_np, mask, fp, images_dir, masks_dir)

    else:  # center (기본)
        # 중앙 9-포인트 그리드 프롬프트로 피사체 마스킹
        predictor = load_predictor(args.sam2_checkpoint, args.sam2_config, device)
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        with torch.inference_mode(), torch.autocast(device, dtype=dtype):
            for fp in tqdm(image_files, desc="  SAM2 center"):
                img_np = np.array(Image.open(fp).convert("RGB"))
                mask   = predict_center(predictor, img_np)
                _save_results(img_np, mask, fp, images_dir, masks_dir)

    print(
        f"[Step 5] 배경 제거 완료\n"
        f"  images/          ← 배경 제거 이미지 (3DGS 학습 입력)\n"
        f"  masks/           ← 바이너리 마스크\n"
        f"  images_original/ ← 왜곡 보정 원본 백업\n"
    )

elif args.skip_sam2 or not args.sam2_checkpoint:
    if not args.sam2_checkpoint:
        print("[Step 5] 건너뜀 (--sam2_checkpoint 미지정). 원본 images/ 를 그대로 사용합니다.\n")
    else:
        print("[Step 5] 건너뜀 (--skip_sam2 플래그).\n")

# ══════════════════════════════════════════════════════════════════════════════
## 선택: 이미지 리사이즈 (배경 제거 후 수행)
# ══════════════════════════════════════════════════════════════════════════════
if args.resize:
    print("이미지 리사이즈 중...")
    magick_command = '"{}"'.format(args.magick_executable) if len(args.magick_executable) > 0 else "magick"
    for scale, suffix in [("50%", "images_2"), ("25%", "images_4"), ("12.5%", "images_8")]:
        out_dir = source / suffix
        out_dir.mkdir(exist_ok=True)
        for f in (source / "images").iterdir():
            dst = out_dir / f.name
            shutil.copy2(f, dst)
            exit_code = os.system(f'{magick_command} mogrify -resize {scale} "{dst}"')
            if exit_code != 0:
                logging.error(f"Resize {scale} failed. Exiting.")
                exit(exit_code)

print("Done.")
