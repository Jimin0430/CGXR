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
from argparse import ArgumentParser
import shutil

# This Python script is based on the shell converter script provided in the MipNerF 360 repository.
parser = ArgumentParser("Colmap converter")
parser.add_argument("--no_gpu", action='store_true')
parser.add_argument("--skip_matching", action='store_true')
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--camera", default="OPENCV", type=str)
parser.add_argument("--colmap_executable", default="", type=str)
parser.add_argument("--resize", action="store_true")
parser.add_argument("--magick_executable", default="", type=str)
parser.add_argument("--video", default="", type=str, help="영상 파일 경로. 지정하면 input/ 폴더에 프레임을 자동 추출합니다.")
parser.add_argument("--every_n_frames", default=15, type=int, help="N프레임마다 1장 추출 (기본값: 15, 30fps 영상 기준 0.5초마다 1장)")
parser.add_argument("--min_frames", default=100, type=int, help="최소 추출 장 수. 간격대로 뽑았을 때 이보다 적으면 자동으로 간격 조정 (기본값: 100)")
parser.add_argument("--sequential", action='store_true', help="영상 데이터용 sequential_matcher 사용 (기본: exhaustive_matcher)")
args = parser.parse_args()
colmap_command = '"{}"'.format(args.colmap_executable) if len(args.colmap_executable) > 0 else "colmap"
magick_command = '"{}"'.format(args.magick_executable) if len(args.magick_executable) > 0 else "magick"
use_gpu = 1 if not args.no_gpu else 0

## Step 0: 영상에서 프레임 추출
if args.video:
    if not os.path.exists(args.video):
        logging.error(f"영상 파일을 찾을 수 없습니다: {args.video}")
        exit(1)

    import subprocess, fractions
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

    input_dir = os.path.join(args.source_path, "input")
    os.makedirs(input_dir, exist_ok=True)
    ffmpeg_cmd = f'ffmpeg -i "{args.video}" -vf "fps={extract_fps:.6f}" "{input_dir}/frame_%04d.jpg" -y'
    exit_code = os.system(ffmpeg_cmd)
    if exit_code != 0:
        logging.error(f"프레임 추출 실패 (code {exit_code}). ffmpeg가 설치되어 있는지 확인하세요.")
        exit(exit_code)
    n_frames = len([f for f in os.listdir(input_dir) if f.endswith(".jpg")])
    print(f"추출 완료: {n_frames}장")

if not args.skip_matching:
    os.makedirs(args.source_path + "/distorted/sparse", exist_ok=True)

    ## Feature extraction
    feat_extracton_cmd = colmap_command + " feature_extractor "\
        "--database_path " + args.source_path + "/distorted/database.db \
        --image_path " + args.source_path + "/input \
        --ImageReader.single_camera 1 \
        --ImageReader.camera_model " + args.camera + " \
        --FeatureExtraction.use_gpu " + str(use_gpu)
    exit_code = os.system(feat_extracton_cmd)
    if exit_code != 0:
        logging.error(f"Feature extraction failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ## Feature matching
    matcher = "sequential_matcher" if args.sequential or args.video else "exhaustive_matcher"
    feat_matching_cmd = colmap_command + f" {matcher} \
        --database_path " + args.source_path + "/distorted/database.db \
        --FeatureMatching.use_gpu " + str(use_gpu)
    exit_code = os.system(feat_matching_cmd)
    if exit_code != 0:
        logging.error(f"Feature matching failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ### Bundle adjustment
    # The default Mapper tolerance is unnecessarily large,
    # decreasing it speeds up bundle adjustment steps.
    mapper_cmd = (colmap_command + " mapper \
        --database_path " + args.source_path + "/distorted/database.db \
        --image_path "  + args.source_path + "/input \
        --output_path "  + args.source_path + "/distorted/sparse \
        --Mapper.ba_global_function_tolerance=0.000001")
    exit_code = os.system(mapper_cmd)
    if exit_code != 0:
        logging.error(f"Mapper failed with code {exit_code}. Exiting.")
        exit(exit_code)

### Image undistortion
## We need to undistort our images into ideal pinhole intrinsics.
img_undist_cmd = (colmap_command + " image_undistorter \
    --image_path " + args.source_path + "/input \
    --input_path " + args.source_path + "/distorted/sparse/0 \
    --output_path " + args.source_path + "\
    --output_type COLMAP")
exit_code = os.system(img_undist_cmd)
if exit_code != 0:
    logging.error(f"Mapper failed with code {exit_code}. Exiting.")
    exit(exit_code)

files = os.listdir(args.source_path + "/sparse")
os.makedirs(args.source_path + "/sparse/0", exist_ok=True)
# Copy each file from the source directory to the destination directory
for file in files:
    if file == '0':
        continue
    source_file = os.path.join(args.source_path, "sparse", file)
    destination_file = os.path.join(args.source_path, "sparse", "0", file)
    shutil.move(source_file, destination_file)

if(args.resize):
    print("Copying and resizing...")

    # Resize images.
    os.makedirs(args.source_path + "/images_2", exist_ok=True)
    os.makedirs(args.source_path + "/images_4", exist_ok=True)
    os.makedirs(args.source_path + "/images_8", exist_ok=True)
    # Get the list of files in the source directory
    files = os.listdir(args.source_path + "/images")
    # Copy each file from the source directory to the destination directory
    for file in files:
        source_file = os.path.join(args.source_path, "images", file)

        destination_file = os.path.join(args.source_path, "images_2", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 50% " + destination_file)
        if exit_code != 0:
            logging.error(f"50% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

        destination_file = os.path.join(args.source_path, "images_4", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 25% " + destination_file)
        if exit_code != 0:
            logging.error(f"25% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

        destination_file = os.path.join(args.source_path, "images_8", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 12.5% " + destination_file)
        if exit_code != 0:
            logging.error(f"12.5% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

print("Done.")