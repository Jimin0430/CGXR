"""
각 학습 단계를 subprocess로 실행하고 job 상태를 업데이트한다.
모든 단계는 순차 실행 — 실패하면 즉시 중단.
"""
import subprocess
import shutil
from pathlib import Path

import jobs as job_store
import config as cfg


def _run(job_id: str, cmd: list, cwd: Path, label: str):
    """subprocess 실행 + 로그 기록. 실패 시 RuntimeError."""
    job_store.append_log(job_id, f"START: {label}")
    job_store.append_log(job_id, " ".join(str(c) for c in cmd))

    result = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.stdout:
        job_store.append_log(job_id, result.stdout[-3000:])  # 마지막 3000자
    if result.stderr:
        job_store.append_log(job_id, result.stderr[-2000:])

    if result.returncode != 0:
        raise RuntimeError(f"{label} failed (exit {result.returncode})")

    job_store.append_log(job_id, f"DONE: {label}")


def run_pipeline(job_id: str, video_path: Path):
    job = job_store.get_job(job_id)
    use_sam2 = job["use_sam2"]
    workdir = Path(job["workdir"])  # server/workdir/<job_id>/
    scene_dir = workdir / "scene"
    output_dir = workdir / "output"
    lg_out = workdir / "lg_output"

    scene_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    lg_out.mkdir(parents=True, exist_ok=True)

    try:
        # ── [1] 영상 → 프레임 + COLMAP ───────────────────────────────
        job_store.update_job(job_id, status="extracting")
        _run(job_id, [
            cfg.MOBILE_GS_PY,
            cfg.EXTRACT_SFM_DIR / "convert.py",
            "--source_path", scene_dir,
            "--video", video_path,
            "--every_n_frames", 10,
            "--colmap_executable", cfg.COLMAP_EXE,
            "--sequential",
        ], cwd=cfg.EXTRACT_SFM_DIR, label="video→frames")

        # ── [2] COLMAP 완료 확인 후 상태 업데이트 ────────────────────
        job_store.update_job(job_id, status="colmap")
        job_store.append_log(job_id, "COLMAP already ran inside convert.py")

        # ── [3] SAM2 배경 제거 (선택) ─────────────────────────────────
        if use_sam2 and cfg.SAM2_CKPT.exists():
            job_store.update_job(job_id, status="sam2")
            _run(job_id, [
                cfg.SAM2_ENV_PY,
                cfg.EXTRACT_SFM_DIR / "remove_background_sam2.py",
                "--source_path", scene_dir,
                "--checkpoint", cfg.SAM2_CKPT,
                "--config", cfg.SAM2_CFG,
                "--mode", "video",
                "--out_images_dir", "images",
            ], cwd=cfg.EXTRACT_SFM_DIR, label="SAM2 background removal")
        else:
            job_store.append_log(job_id, "SAM2 skipped")

        # ── [4] Mobile-GS Pretrain ────────────────────────────────────
        job_store.update_job(job_id, status="pretrain")
        pretrain_ckpt = output_dir / f"chkpnt{cfg.PRETRAIN_ITERS}.pth"
        _run(job_id, [
            cfg.MOBILE_GS_PY,
            cfg.MOBILE_GS_DIR / "pretrain.py",
            "-s", scene_dir,
            "-m", output_dir,
            "--eval",
            "--imp_metric", "outdoor",
            "--sh_degree", 3,
            "--iterations", cfg.PRETRAIN_ITERS,
            "--save_iterations", cfg.PRETRAIN_ITERS,
            "--checkpoint_iterations", cfg.PRETRAIN_ITERS,
        ], cwd=cfg.MOBILE_GS_DIR, label="Mobile-GS pretrain")

        # ── [5] Mobile-GS Fine-tuning ─────────────────────────────────
        job_store.update_job(job_id, status="finetune")
        _run(job_id, [
            cfg.MOBILE_GS_PY,
            cfg.MOBILE_GS_DIR / "train.py",
            "-s", scene_dir,
            "-m", output_dir,
            "--eval",
            "--start_checkpoint", pretrain_ckpt,
        ], cwd=cfg.MOBILE_GS_DIR, label="Mobile-GS fine-tune")

        # ── [6] LightGaussian Stage 1: Prune + Finetune ───────────────
        job_store.update_job(job_id, status="pruning")
        stage1_dir = lg_out / "stage1_pruned"
        stage1_dir.mkdir(exist_ok=True)
        _run(job_id, [
            cfg.LG_PY,
            cfg.LG_REPO_DIR / "prune_finetune.py",
            "-s", scene_dir,
            "-m", stage1_dir,
            "--start_checkpoint", pretrain_ckpt,
            "--iteration", cfg.LG_PRUNE_ITERS,
            "--prune_percent", cfg.LG_PRUNE_PERCENT,
            "--prune_type", "v_important_score",
            "--prune_decay", 1,
            "--position_lr_max_steps", cfg.LG_PRUNE_ITERS,
            "--v_pow", 0.1,
        ], cwd=cfg.LG_REPO_DIR, label="LG stage1 prune")

        # ── [7] LightGaussian Stage 2: SH Distillation ───────────────
        job_store.update_job(job_id, status="distilling")
        stage2_dir = lg_out / "stage2_distilled"
        stage2_dir.mkdir(exist_ok=True)
        stage1_ckpt = stage1_dir / f"chkpnt{cfg.LG_PRUNE_ITERS}.pth"
        _run(job_id, [
            cfg.LG_PY,
            cfg.LG_REPO_DIR / "distill_train.py",
            "-s", scene_dir,
            "-m", stage2_dir,
            "--start_checkpoint", stage1_ckpt,
            "--iteration", cfg.LG_DISTILL_ITERS,
            "--teacher_model", pretrain_ckpt,
            "--new_max_sh", 2,
            "--position_lr_max_steps", cfg.LG_DISTILL_ITERS,
            "--enable_covariance",
            "--augmented_view",
        ], cwd=cfg.LG_REPO_DIR, label="LG stage2 distill")

        # ── [8] LightGaussian Stage 3: VecTree 압축 ──────────────────
        job_store.update_job(job_id, status="quantizing")
        stage3_dir = lg_out / "stage3_quantized"
        stage3_dir.mkdir(exist_ok=True)
        stage2_ply = stage2_dir / "point_cloud" / f"iteration_{cfg.LG_DISTILL_ITERS}" / "point_cloud.ply"
        _run(job_id, [
            cfg.LG_PY,
            cfg.LG_REPO_DIR / "vectree" / "vectree.py",
            "--important_score_npz_path", stage2_dir,
            "--input_path", stage2_ply,
            "--save_path", stage3_dir,
            "--vq_ratio", cfg.LG_VQ_RATIO,
            "--codebook_size", cfg.LG_CODEBOOK_SIZE,
        ], cwd=cfg.LG_REPO_DIR, label="LG stage3 quantize")

        # ── 최종 PLY 위치 기록 ────────────────────────────────────────
        final_ply = stage3_dir / "extreme_saving" / "point_cloud.ply"
        if not final_ply.exists():
            # fallback: stage2 PLY 사용
            final_ply = stage2_ply

        job_store.update_job(job_id, status="done", result_ply=str(final_ply))
        job_store.append_log(job_id, f"Pipeline complete. PLY: {final_ply}")

    except Exception as e:
        job_store.update_job(job_id, status="failed", error=str(e))
        job_store.append_log(job_id, f"FAILED: {e}")
