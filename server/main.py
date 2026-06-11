"""
CGXR Training Server
POST /upload              → 영상 업로드, job_id 반환
GET  /status/{job_id}     → 학습 진행 상태
GET  /download/{job_id}   → 완료된 PLY 다운로드
GET  /jobs                → 전체 잡 목록
DELETE /jobs/{job_id}     → 잡 삭제
"""
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader

import jobs as job_store
import pipeline
import config as cfg

app = FastAPI(title="CGXR Training Server")

# ── 인증 ─────────────────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(key: str = Depends(api_key_header)):
    if key != cfg.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


# ── 업로드 ────────────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    use_sam2: bool = Form(True),
    _: str = Depends(require_api_key),
):
    """영상 파일을 받아 학습을 시작하고 job_id를 반환한다."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {suffix}")

    job = job_store.create_job(use_sam2=use_sam2)
    job_id = job["job_id"]

    # 영상 저장
    cfg.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    video_path = cfg.UPLOADS_DIR / f"{job_id}{suffix}"
    with video_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    job_store.update_job(job_id, video_path=str(video_path))
    job_store.append_log(job_id, f"Video saved: {video_path.name} ({video_path.stat().st_size // 1024} KB)")

    # 백그라운드에서 파이프라인 실행
    background_tasks.add_task(pipeline.run_pipeline, job_id, video_path)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Training started. Poll /status/{job_id} for progress.",
    }


# ── 상태 조회 ─────────────────────────────────────────────────────────────────
@app.get("/status/{job_id}")
def get_status(job_id: str, _: str = Depends(require_api_key)):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id":     job["job_id"],
        "status":     job["status"],
        "use_sam2":   job["use_sam2"],
        "error":      job["error"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "log_tail":   job["log"][-20:],  # 마지막 20줄만
    }


# ── PLY 다운로드 ──────────────────────────────────────────────────────────────
@app.get("/download/{job_id}")
def download_ply(job_id: str, _: str = Depends(require_api_key)):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(
            status_code=425,
            detail=f"Training not complete yet. Current status: {job['status']}",
        )

    ply_path = Path(job.get("result_ply", ""))
    if not ply_path.exists():
        raise HTTPException(status_code=500, detail="PLY file not found on server")

    return FileResponse(
        path=str(ply_path),
        media_type="application/octet-stream",
        filename=f"{job_id}.ply",
    )


# ── 잡 목록 ──────────────────────────────────────────────────────────────────
@app.get("/jobs")
def list_jobs(_: str = Depends(require_api_key)):
    return [
        {
            "job_id":     j["job_id"],
            "status":     j["status"],
            "created_at": j["created_at"],
            "updated_at": j["updated_at"],
        }
        for j in job_store.list_jobs()
    ]


# ── 잡 삭제 ──────────────────────────────────────────────────────────────────
@app.delete("/jobs/{job_id}")
def delete_job(job_id: str, _: str = Depends(require_api_key)):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] in {"pretrain", "finetune", "pruning", "distilling", "quantizing"}:
        raise HTTPException(status_code=409, detail="Cannot delete a running job")

    job_store.delete_job(job_id)
    video = Path(job.get("video_path", ""))
    if video.exists():
        video.unlink()

    return {"message": f"Job {job_id} deleted"}


# ── 헬스체크 ──────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}
