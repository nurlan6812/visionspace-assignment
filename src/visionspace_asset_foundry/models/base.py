from __future__ import annotations

import os
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from visionspace_asset_foundry.paths import ASSETS_DIR, MODEL_CACHE_DIR, RUNS_DIR, relative_to_root
from visionspace_asset_foundry.postprocess.inspect_mesh import inspect_mesh
from visionspace_asset_foundry.postprocess.normalize import convert_to_glb, normalize_glb
from visionspace_asset_foundry.schemas import AssetRecord, GenerationRequest, MeshMetrics, ModelName


class ModelExecutionError(RuntimeError):
    pass


def check_torch_runtime(python_bin: str, *, require_cuda: bool = True) -> tuple[bool, str]:
    script = """
import json
try:
    import torch
    payload = {
        "torch": getattr(torch, "__version__", "unknown"),
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": getattr(torch.version, "cuda", None),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    print(json.dumps(payload))
except Exception as exc:
    print(json.dumps({"error": repr(exc)}))
    raise
""".strip()
    try:
        result = subprocess.run(
            [python_bin, "-c", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"Python runtime check failed for {python_bin}: {exc}"
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        return False, f"PyTorch is not importable from {python_bin}. {detail}"
    detail = result.stdout.strip()
    if require_cuda and '"cuda_available": false' in detail:
        return False, f"PyTorch imports from {python_bin}, but CUDA is not available. Runtime: {detail}"
    return True, detail


class ModelRunner(ABC):
    name: ModelName
    label: str
    requires_image: bool = True

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def command(self, request: GenerationRequest, run_dir: Path, raw_output_dir: Path) -> list[str]:
        raise NotImplementedError

    def generate(self, request: GenerationRequest, job_id: str | None = None) -> AssetRecord:
        if self.requires_image and not request.image_path:
            raise ModelExecutionError(
                f"{self.label} is image-to-3D. Provide a reference image for prompt: {request.prompt}"
            )
        available, reason = self.is_available()
        if not available:
            raise ModelExecutionError(reason)

        asset_id = job_id or uuid.uuid4().hex[:12]
        run_dir = RUNS_DIR / asset_id
        raw_output_dir = run_dir / "raw"
        run_dir.mkdir(parents=True, exist_ok=True)
        raw_output_dir.mkdir(parents=True, exist_ok=True)

        cmd = self.command(request, run_dir, raw_output_dir)
        started = time.perf_counter()
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        env.setdefault("HF_HOME", str(MODEL_CACHE_DIR / "huggingface"))
        env.setdefault("HF_HUB_CACHE", str(MODEL_CACHE_DIR / "huggingface" / "hub"))
        env.setdefault("TORCH_HOME", str(MODEL_CACHE_DIR / "torch"))
        env.setdefault("U2NET_HOME", str(MODEL_CACHE_DIR / "u2net"))
        env.setdefault("HY3DGEN_MODELS", str(MODEL_CACHE_DIR / "hy3dgen"))
        timeout_seconds = int(os.getenv("VSAF_MODEL_TIMEOUT_SECONDS", "1800"))
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir(),
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started
            (run_dir / "stdout.log").write_text(exc.stdout or "", encoding="utf-8")
            (run_dir / "stderr.log").write_text(exc.stderr or "", encoding="utf-8")
            raise ModelExecutionError(
                f"{self.label} timed out after {elapsed:.2f}s. "
                f"See {relative_to_root(run_dir / 'stderr.log')}."
            ) from exc
        elapsed = time.perf_counter() - started
        (run_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
        (run_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise ModelExecutionError(
                f"{self.label} failed with exit code {result.returncode}. "
                f"See {relative_to_root(run_dir / 'stderr.log')}."
            )

        raw_path = self.find_output(raw_output_dir)
        if raw_path is None:
            raise ModelExecutionError(f"{self.label} completed but no mesh file was found in {raw_output_dir}.")

        final_glb = ASSETS_DIR / f"{asset_id}-{self.name.value}.glb"
        metrics: MeshMetrics
        if raw_path.suffix.lower() == ".glb":
            final_glb.write_bytes(raw_path.read_bytes())
            metrics = inspect_mesh(final_glb)
        else:
            metrics = convert_to_glb(raw_path, final_glb)

        normalized_path = ASSETS_DIR / f"{asset_id}-{self.name.value}-normalized.glb"
        normalized_metrics = normalize_glb(
            final_glb,
            normalized_path,
            target_largest_dimension_m=(
                max(
                    request.target_dimensions_m.x,
                    request.target_dimensions_m.y,
                    request.target_dimensions_m.z,
                )
                if request.target_dimensions_m
                else 2.0
            ),
        )

        record = AssetRecord(
            id=asset_id,
            prompt_id=request.prompt_id,
            asset_type=request.asset_type,
            model=request.model,
            title=request.prompt_id,
            prompt=request.prompt,
            source_image=relative_to_root(request.image_path) if request.image_path else None,
            raw_path=relative_to_root(raw_path),
            glb_path=relative_to_root(final_glb),
            normalized_path=relative_to_root(normalized_path),
            download_url=f"/generated/assets/{normalized_path.name}",
            metrics=metrics,
            normalized_metrics=normalized_metrics,
            notes=[f"Generation elapsed seconds: {elapsed:.2f}"],
        )
        return record

    def find_output(self, raw_output_dir: Path) -> Path | None:
        candidates: list[Path] = []
        for suffix in ["*.glb", "*.gltf", "*.obj", "*.ply"]:
            candidates.extend(raw_output_dir.rglob(suffix))
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    @abstractmethod
    def repo_dir(self) -> Path:
        raise NotImplementedError
