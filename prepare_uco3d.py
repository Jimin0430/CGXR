"""
uCO3D 데이터셋에서 RGB 영상을 뽑아 SfM(COLMAP) 파이프라인으로 연결하는 스크립트.

사용 예:
  # 52개짜리 소규모 디버그 서브셋 다운로드 + SfM 실행
  python prepare_uco3d.py --download_folder data/uco3d --small_subset

  # 특정 슈퍼카테고리만 다운로드
  python prepare_uco3d.py --download_folder data/uco3d --super_categories "vegetables_and_legumes,stationery"

  # 이미 다운로드된 폴더에서 SfM만 실행
  python prepare_uco3d.py --download_folder data/uco3d --skip_download

  # 영상만 복사하고 SfM은 건너뜀
  python prepare_uco3d.py --download_folder data/uco3d --small_subset --skip_sfm
"""

import os
import sys
import shutil
import subprocess
import argparse
import glob
from pathlib import Path


# ──────────────────────────────────────────────
# 인수 파싱
# ──────────────────────────────────────────────
parser = argparse.ArgumentParser("uCO3D → SfM 준비 스크립트")
parser.add_argument("--download_folder", required=True,
                    help="uCO3D 데이터를 저장할 폴더 (예: data/uco3d)")
parser.add_argument("--output_folder", default="",
                    help="SfM 결과를 저장할 루트 폴더. 기본값: <download_folder>_sfm")
parser.add_argument("--uco3d_repo", default="third_party/uco3d",
                    help="uco3d 저장소 경로 (없으면 자동 클론)")
parser.add_argument("--small_subset", action="store_true",
                    help="52개짜리 디버그 서브셋만 다운로드")
parser.add_argument("--super_categories", default="",
                    help="다운로드할 슈퍼카테고리 (콤마 구분). 예: vegetables_and_legumes,stationery")
parser.add_argument("--max_sequences", type=int, default=0,
                    help="처리할 최대 시퀀스 수 (0=전체)")
parser.add_argument("--fps", type=float, default=2.0,
                    help="영상에서 추출할 FPS (기본값: 2.0)")
parser.add_argument("--colmap_executable", default="",
                    help="COLMAP 실행 파일 경로 (기본값: 시스템 PATH의 colmap)")
parser.add_argument("--skip_download", action="store_true",
                    help="다운로드 건너뜀 (이미 받은 경우)")
parser.add_argument("--skip_sfm", action="store_true",
                    help="SfM(COLMAP) 실행 건너뜀 (영상 목록만 출력)")
parser.add_argument("--n_workers", type=int, default=4,
                    help="다운로드 병렬 워커 수")
args = parser.parse_args()

SCRIPT_DIR = Path(__file__).parent.resolve()
CONVERT_PY = SCRIPT_DIR / "Extract_SfM" / "convert.py"
DOWNLOAD_FOLDER = Path(args.download_folder).resolve()
OUTPUT_FOLDER = Path(args.output_folder).resolve() if args.output_folder else DOWNLOAD_FOLDER.parent / (DOWNLOAD_FOLDER.name + "_sfm")
UCO3D_REPO = Path(args.uco3d_repo).resolve() if not Path(args.uco3d_repo).is_absolute() else Path(args.uco3d_repo)
if not UCO3D_REPO.is_absolute():
    UCO3D_REPO = SCRIPT_DIR / args.uco3d_repo


def run(cmd, **kwargs):
    print(f"\n[RUN] {cmd}")
    ret = os.system(cmd)
    if ret != 0:
        print(f"[ERROR] 명령 실패 (exit code {ret}): {cmd}")
        sys.exit(ret)


def run_check(cmd):
    """명령을 실행하고 exit code를 반환 (실패해도 종료하지 않음)."""
    print(f"\n[RUN] {cmd}")
    return os.system(cmd)


# ──────────────────────────────────────────────
# Step 1: uco3d 설치 확인 및 클론
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("Step 1: uco3d 설치 확인")
print("="*60)

try:
    import uco3d
    print(f"[OK] uco3d 이미 설치됨: {uco3d.__file__}")
except ImportError:
    print("[INFO] uco3d 미설치. 저장소 클론 후 pip install 진행...")
    UCO3D_REPO.parent.mkdir(parents=True, exist_ok=True)
    if not UCO3D_REPO.exists():
        run(f'git clone https://github.com/facebookresearch/uco3d.git "{UCO3D_REPO}"')
    run(f'pip install -e "{UCO3D_REPO}"')

# ──────────────────────────────────────────────
# Step 2: 데이터 다운로드
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("Step 2: uCO3D 데이터 다운로드")
print("="*60)

DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

if args.skip_download:
    print("[SKIP] --skip_download 플래그 설정됨. 다운로드 건너뜀.")
else:
    # uco3d 저장소 안의 download_dataset.py 찾기
    download_script = UCO3D_REPO / "dataset_download" / "download_dataset.py"
    if not download_script.exists():
        # pip install로 설치된 경우 직접 import
        import uco3d as _uco3d_module
        _uco3d_root = Path(_uco3d_module.__file__).parent.parent
        download_script = _uco3d_root / "dataset_download" / "download_dataset.py"
    if not download_script.exists():
        print(f"[ERROR] download_dataset.py를 찾을 수 없습니다: {download_script}")
        sys.exit(1)

    dl_cmd = (
        f'python "{download_script}"'
        f' --download_folder "{DOWNLOAD_FOLDER}"'
        f' --n_download_workers {args.n_workers}'
        f' --n_extract_workers {args.n_workers}'
        f' --download_modalities "metadata,rgb_videos"'
        f' --clear_archives_after_unpacking'
    )

    if args.small_subset:
        dl_cmd += " --download_small_subset"
        print("[INFO] 소규모 서브셋(52개 시퀀스) 다운로드...")
    elif args.super_categories:
        dl_cmd += f' --download_super_categories "{args.super_categories}"'
        print(f"[INFO] 슈퍼카테고리 다운로드: {args.super_categories}")
    else:
        print("[WARNING] --small_subset 또는 --super_categories를 지정하지 않으면 전체 ~19TB를 다운로드합니다!")
        reply = input("계속하시겠습니까? (yes/no): ").strip().lower()
        if reply != "yes":
            print("중단.")
            sys.exit(0)

    run(dl_cmd)

# ──────────────────────────────────────────────
# Step 3: rgb_video.mp4 파일 탐색
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("Step 3: rgb_video.mp4 파일 탐색")
print("="*60)

video_files = sorted(DOWNLOAD_FOLDER.rglob("rgb_video.mp4"))

if not video_files:
    print(f"[WARNING] {DOWNLOAD_FOLDER} 에서 rgb_video.mp4 파일을 찾을 수 없습니다.")
    print("  다운로드가 완료되었는지, 경로가 올바른지 확인하세요.")
    sys.exit(0)

print(f"[OK] {len(video_files)}개 rgb_video.mp4 발견")

if args.max_sequences > 0:
    video_files = video_files[: args.max_sequences]
    print(f"[INFO] --max_sequences={args.max_sequences} → {len(video_files)}개 처리")

for i, vf in enumerate(video_files):
    # 경로 구조: <download_folder>/<super_cat>/<category>/<sequence>/rgb_video.mp4
    parts = vf.relative_to(DOWNLOAD_FOLDER).parts
    seq_id = "/".join(parts[:-1])  # super_cat/category/sequence
    print(f"  [{i+1:03d}] {seq_id}")

# ──────────────────────────────────────────────
# Step 4: 각 영상에 대해 SfM (COLMAP) 실행
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("Step 4: SfM 파이프라인 실행")
print("="*60)

if args.skip_sfm:
    print("[SKIP] --skip_sfm 플래그 설정됨. SfM 건너뜀.")
    print("\n아래 명령으로 개별 시퀀스의 SfM을 수동 실행할 수 있습니다:")
    example = video_files[0]
    parts = example.relative_to(DOWNLOAD_FOLDER).parts
    seq_dir = OUTPUT_FOLDER / Path(*parts[:-1])
    colmap_opt = f' --colmap_executable "{args.colmap_executable}"' if args.colmap_executable else ""
    print(f'  python "{CONVERT_PY}" -s "{seq_dir}" --video "{example}" --fps {args.fps} --sequential{colmap_opt}')
    sys.exit(0)

success_list = []
fail_list = []

for i, video_path in enumerate(video_files):
    parts = video_path.relative_to(DOWNLOAD_FOLDER).parts
    seq_name = "_".join(parts[:-1])  # super_cat_category_sequence (파일시스템 친화적)
    seq_sfm_dir = OUTPUT_FOLDER / Path(*parts[:-1])

    print(f"\n[{i+1}/{len(video_files)}] {seq_name}")
    print(f"  영상: {video_path}")
    print(f"  출력: {seq_sfm_dir}")

    seq_sfm_dir.mkdir(parents=True, exist_ok=True)

    colmap_opt = f' --colmap_executable "{args.colmap_executable}"' if args.colmap_executable else ""
    sfm_cmd = (
        f'python "{CONVERT_PY}"'
        f' -s "{seq_sfm_dir}"'
        f' --video "{video_path}"'
        f' --fps {args.fps}'
        f' --sequential'
        f'{colmap_opt}'
    )

    ret = run_check(sfm_cmd)
    if ret == 0:
        success_list.append(seq_name)
        print(f"  [OK] SfM 완료 → {seq_sfm_dir}")
    else:
        fail_list.append(seq_name)
        print(f"  [FAIL] SfM 실패 (code {ret})")

# ──────────────────────────────────────────────
# 결과 요약
# ──────────────────────────────────────────────
print("\n" + "="*60)
print("완료 요약")
print("="*60)
print(f"성공: {len(success_list)} / {len(video_files)}")
if fail_list:
    print(f"실패: {len(fail_list)}")
    for f in fail_list:
        print(f"  - {f}")
print(f"\nSfM 결과 위치: {OUTPUT_FOLDER}")
print("\n다음 단계: Optimize/train.py 로 3DGS 학습")
print(f'  python Optimize/train.py -s "<위 경로 중 하나>"')
