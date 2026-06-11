"""
SAM 2를 이용한 배경 제거 스크립트
- images/ 폴더의 이미지를 읽어 피사체만 남기고 배경을 검정으로 처리
- images_masked/  : 배경 제거된 결과 이미지 (3DGS 학습용)
- masks/          : 바이너리 마스크 PNG (흰색=피사체, 검정=배경)

사용법:
  # 단일 이미지 방식 (center-point prompt)
  python remove_background_sam2.py -s <source_path> --checkpoint <sam2.pt>

  # 비디오 전파 방식 (프레임 시퀀스 → 시간적 일관성 보장)
  python remove_background_sam2.py -s <source_path> --checkpoint <sam2.pt> --mode video

  # 자동 마스크 생성 방식 (피사체 위치를 모를 때)
  python remove_background_sam2.py -s <source_path> --checkpoint <sam2.pt> --mode auto
"""

import os
import sys
import argparse
import numpy as np
from pathlib import Path
from PIL import Image
import torch

IMG_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


def load_predictor(checkpoint: str, config: str, device: str):
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    model = build_sam2(config, checkpoint, device=device)
    return SAM2ImagePredictor(model)


def load_video_predictor(checkpoint: str, config: str, device: str):
    from sam2.build_sam import build_sam2_video_predictor

    return build_sam2_video_predictor(config, checkpoint, device=device)


def load_auto_generator(checkpoint: str, config: str, device: str):
    from sam2.build_sam import build_sam2
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

    model = build_sam2(config, checkpoint, device=device)
    return SAM2AutomaticMaskGenerator(
        model=model,
        points_per_side=32,
        pred_iou_thresh=0.88,
        stability_score_thresh=0.95,
        min_mask_region_area=500,
    )


# ─── 중앙 포인트 프롬프트로 피사체 마스크 예측 ───────────────────────────────
def predict_center(predictor, img_np: np.ndarray) -> np.ndarray:
    H, W = img_np.shape[:2]
    cx, cy = W // 2, H // 2

    # 중앙 + 주변 9개 포인트로 안정성 향상
    offsets = [
        (0, 0),
        (W // 6, 0), (-W // 6, 0), (0, H // 6), (0, -H // 6),
        (W // 6, H // 6), (-W // 6, H // 6), (W // 6, -H // 6), (-W // 6, -H // 6),
    ]
    points = np.array([[cx + dx, cy + dy] for dx, dy in offsets], dtype=np.float32)
    labels = np.ones(len(points), dtype=np.int32)

    predictor.set_image(img_np)
    masks, scores, _ = predictor.predict(
        point_coords=points,
        point_labels=labels,
        multimask_output=True,
    )
    # 가장 높은 점수의 마스크 선택
    best = np.argmax(scores)
    return masks[best].astype(bool)


# ─── 자동 마스크에서 가장 큰 마스크(=피사체)를 선택 ────────────────────────
def predict_auto(generator, img_np: np.ndarray) -> np.ndarray:
    anns = generator.generate(img_np)
    if not anns:
        H, W = img_np.shape[:2]
        return np.ones((H, W), dtype=bool)

    # area 기준 내림차순 정렬, 가장 큰 마스크 = 피사체
    anns_sorted = sorted(anns, key=lambda x: x["area"], reverse=True)
    return anns_sorted[0]["segmentation"].astype(bool)


# ─── 비디오 전파 방식 (시간적 일관성) ──────────────────────────────────────
def process_video_mode(
    predictor,
    images_dir: Path,
    masked_dir: Path,
    masks_dir: Path,
    image_files: list,
    device: str,
):
    """
    SAM 2 비디오 예측기로 첫 프레임에 프롬프트를 주고
    전체 시퀀스에 전파. JPEG/PNG 혼합이면 임시 심볼릭 구조를 사용.
    """
    import shutil, tempfile

    # SAM 2 video predictor는 디렉터리 내 정렬된 이미지를 읽음
    # 파일명이 숫자 순 정렬이 보장된 경우 images_dir 그대로 사용 가능
    # 그렇지 않으면 임시 폴더에 복사
    tmpdir = tempfile.mkdtemp(prefix="sam2_frames_")
    try:
        for idx, fp in enumerate(image_files):
            ext = fp.suffix.lower()
            dst = Path(tmpdir) / f"{idx:06d}{ext}"
            shutil.copy2(fp, dst)

        H_ref, W_ref = np.array(Image.open(image_files[0]).convert("RGB")).shape[:2]
        cx, cy = W_ref // 2, H_ref // 2

        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        with torch.inference_mode(), torch.autocast(device, dtype=dtype):
            state = predictor.init_state(video_path=tmpdir)
            predictor.reset_state(state)

            # 첫 프레임에 중앙 포인트 프롬프트
            points = np.array([[cx, cy]], dtype=np.float32)
            labels = np.array([1], dtype=np.int32)
            _, out_obj_ids, _ = predictor.add_new_points_or_box(
                inference_state=state,
                frame_idx=0,
                obj_id=1,
                points=points,
                labels=labels,
            )

            # 전체 시퀀스 전파
            masks_dict: dict[int, np.ndarray] = {}
            for frame_idx, obj_ids, mask_logits in predictor.propagate_in_video(state):
                # mask_logits: (N_obj, 1, H, W)
                combined = (mask_logits[0, 0] > 0.0).cpu().numpy()
                masks_dict[frame_idx] = combined

        for idx, fp in enumerate(image_files):
            img_np = np.array(Image.open(fp).convert("RGB"))
            mask = masks_dict.get(idx, np.ones(img_np.shape[:2], dtype=bool))
            _save_results(img_np, mask, fp, masked_dir, masks_dir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _save_results(
    img_np: np.ndarray,
    mask: np.ndarray,
    src_path: Path,
    masked_dir: Path,
    masks_dir: Path,
):
    result = img_np.copy()
    result[~mask] = 0  # 배경 → 검정

    suffix = src_path.suffix
    Image.fromarray(result).save(masked_dir / src_path.name)
    Image.fromarray((mask * 255).astype(np.uint8)).save(
        masks_dir / (src_path.stem + ".png")
    )


def main():
    from tqdm import tqdm

    parser = argparse.ArgumentParser("SAM 2 Background Removal")
    parser.add_argument("--source_path", "-s", required=True,
                        help="COLMAP source 폴더 (images/ 서브폴더 포함)")
    parser.add_argument("--images_dir", default="images",
                        help="이미지가 있는 서브폴더 이름 (기본: images)")
    parser.add_argument("--checkpoint", required=True,
                        help="SAM 2 가중치 파일 경로 (.pt)")
    parser.add_argument("--config", default="configs/sam2.1/sam2.1_hiera_l.yaml",
                        help="SAM 2 설정 파일 경로 (sam2 패키지 내 상대경로 또는 절대경로)")
    parser.add_argument("--mode", choices=["center", "video", "auto"], default="center",
                        help="center: 중앙 포인트 | video: 비디오 전파 | auto: 자동 마스크")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu",
                        help="실행 디바이스 (cuda / cpu)")
    parser.add_argument("--out_images_dir", default="images_masked",
                        help="결과 이미지 저장 폴더 이름 (기본: images_masked)")
    parser.add_argument("--out_masks_dir", default="masks",
                        help="마스크 저장 폴더 이름 (기본: masks)")
    args = parser.parse_args()

    source = Path(args.source_path)
    images_dir = source / args.images_dir
    masked_dir = source / args.out_images_dir
    masks_dir = source / args.out_masks_dir

    if not images_dir.exists():
        print(f"[ERROR] 이미지 폴더가 없습니다: {images_dir}")
        sys.exit(1)

    masked_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    image_files = sorted(
        [f for f in images_dir.iterdir() if f.suffix in IMG_EXTS]
    )
    if not image_files:
        print(f"[ERROR] {images_dir} 에 이미지 파일이 없습니다.")
        sys.exit(1)

    print(f"디바이스: {args.device}")
    print(f"처리 이미지 수: {len(image_files)}")
    print(f"모드: {args.mode}")
    print(f"결과 저장 위치:\n  이미지 → {masked_dir}\n  마스크 → {masks_dir}")
    print()

    # ── 비디오 전파 모드 ──────────────────────────────────────────────────
    if args.mode == "video":
        predictor = load_video_predictor(args.checkpoint, args.config, args.device)
        process_video_mode(predictor, images_dir, masked_dir, masks_dir, image_files, args.device)
        print(f"\n완료: {len(image_files)}장 처리됨")
        return

    # ── 자동 마스크 모드 ──────────────────────────────────────────────────
    if args.mode == "auto":
        generator = load_auto_generator(args.checkpoint, args.config, args.device)
        for fp in tqdm(image_files, desc="auto mask"):
            img_np = np.array(Image.open(fp).convert("RGB"))
            mask = predict_auto(generator, img_np)
            _save_results(img_np, mask, fp, masked_dir, masks_dir)
        print(f"\n완료: {len(image_files)}장 처리됨")
        return

    # ── 중앙 포인트 모드 (기본) ───────────────────────────────────────────
    predictor = load_predictor(args.checkpoint, args.config, args.device)
    dtype = torch.bfloat16 if args.device == "cuda" else torch.float32
    with torch.inference_mode(), torch.autocast(args.device, dtype=dtype):
        for fp in tqdm(image_files, desc="center-point"):
            img_np = np.array(Image.open(fp).convert("RGB"))
            mask = predict_center(predictor, img_np)
            _save_results(img_np, mask, fp, masked_dir, masks_dir)

    print(f"\n완료: {len(image_files)}장 처리됨")


if __name__ == "__main__":
    main()
