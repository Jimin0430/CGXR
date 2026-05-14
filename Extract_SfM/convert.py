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
parser.add_argument("--video", default="", type=str, help="영상 파일 경로. 지정하면 input/ 폴더에 프레임을 자동 추출합니다.")
parser.add_argument("--every_n_frames", default=15, type=int, help="N프레임마다 1장 추출 (기본값: 15)")
parser.add_argument("--min_frames", default=100, type=int, help="최소 추출 장 수 (기본값: 100)")
parser.add_argument("--sequential", action='store_true', help="영상 데이터용 sequential_matcher 사용")
args = parser.parse_args()

magick_command = '"{}"'.format(args.magick_executable) if len(args.magick_executable) > 0 else "magick"
source = Path(args.source_path)

## Step 0: 영상에서 프레임 추출
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
    ffmpeg_cmd = f'ffmpeg -i "{args.video}" -vf "fps={extract_fps:.6f}" "{input_dir}/frame_%04d.jpg" -y'
    exit_code = os.system(ffmpeg_cmd)
    if exit_code != 0:
        logging.error(f"프레임 추출 실패 (code {exit_code}). ffmpeg가 설치되어 있는지 확인하세요.")
        exit(exit_code)
    n_frames = len([f for f in os.listdir(input_dir) if f.endswith(".jpg")])
    print(f"추출 완료: {n_frames}장")

## Step 1~3: COLMAP SfM (pycolmap)
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
    print(f"재구성 완료: {len(reconstructions)}개 모델")

## Step 4: 이미지 왜곡 보정
print("[4/4] Image undistortion...")
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

if args.resize:
    print("Copying and resizing...")
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
