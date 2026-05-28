from __future__ import annotations

import json
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock

from visionspace_asset_foundry.models import get_runner
from visionspace_asset_foundry.paths import METRICS_DIR, ROOT
from visionspace_asset_foundry.schemas import GenerationJob, GenerationRequest, JobStatus


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)
        METRICS_DIR.mkdir(parents=True, exist_ok=True)

    def create(self, request: GenerationRequest) -> GenerationJob:
        job = GenerationJob(id=uuid.uuid4().hex[:12], request=request)
        with self._lock:
            self._jobs[job.id] = job
            self._persist(job)
        self._executor.submit(self._run, job.id)
        return job

    def list(self) -> list[GenerationJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def get(self, job_id: str) -> GenerationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _update(self, job_id: str, **updates: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            job.updated_at = datetime.utcnow()
            self._persist(job)

    def _persist(self, job: GenerationJob) -> None:
        path = METRICS_DIR / f"job-{job.id}.json"
        path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        self._update(job_id, status=JobStatus.running, logs=[*job.logs, "Generation started."])
        try:
            runner = get_runner(job.request.model)
            asset = runner.generate(job.request, job_id=job.id)
            self._update(
                job_id,
                status=JobStatus.completed,
                asset=asset,
                logs=[*self.get(job_id).logs, "Generation and normalization completed."],  # type: ignore[union-attr]
            )
            self._write_asset_index()
        except Exception as exc:
            tb = traceback.format_exc()
            self._update(
                job_id,
                status=JobStatus.failed,
                error=str(exc),
                logs=[*self.get(job_id).logs, tb],  # type: ignore[union-attr]
            )

    def _write_asset_index(self) -> None:
        assets = [job.asset for job in self.list() if job.asset is not None]
        index_path = ROOT / "outputs" / "assets.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps([asset.model_dump(mode="json") for asset in assets], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


job_store = JobStore()
