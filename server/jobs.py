import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from config import JOBS_STORE, WORKDIR

JOBS_STORE.mkdir(parents=True, exist_ok=True)

STAGES = [
    "queued",
    "extracting",   # 영상 → 프레임
    "colmap",       # SfM
    "sam2",         # 배경 제거
    "pretrain",     # Mobile-GS pretrain
    "finetune",     # Mobile-GS fine-tune
    "pruning",      # LG stage 1
    "distilling",   # LG stage 2
    "quantizing",   # LG stage 3
    "converting",   # Unity PLY → .bytes
    "done",
    "failed",
]


def _path(job_id: str) -> Path:
    return JOBS_STORE / f"{job_id}.json"


def create_job(use_sam2: bool = True) -> dict:
    job_id = str(uuid.uuid4())
    job = {
        "job_id":    job_id,
        "status":    "queued",
        "use_sam2":  use_sam2,
        "stage_idx": 0,
        "log":       [],
        "error":     None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "workdir":   str(WORKDIR / job_id),
    }
    _path(job_id).write_text(json.dumps(job, indent=2), encoding="utf-8")
    Path(job["workdir"]).mkdir(parents=True, exist_ok=True)
    return job


def get_job(job_id: str) -> Optional[dict]:
    p = _path(job_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def update_job(job_id: str, **kwargs) -> dict:
    job = get_job(job_id)
    job.update(kwargs)
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    _path(job_id).write_text(json.dumps(job, indent=2), encoding="utf-8")
    return job


def append_log(job_id: str, msg: str):
    job = get_job(job_id)
    job["log"].append(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    _path(job_id).write_text(json.dumps(job, indent=2), encoding="utf-8")


def delete_job(job_id: str):
    import shutil
    job = get_job(job_id)
    if job:
        shutil.rmtree(job["workdir"], ignore_errors=True)
        _path(job_id).unlink(missing_ok=True)


def list_jobs() -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(JOBS_STORE.glob("*.json"))
    ]
