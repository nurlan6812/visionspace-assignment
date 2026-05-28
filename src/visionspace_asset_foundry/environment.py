from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

import psutil

from visionspace_asset_foundry.schemas import EnvironmentInfo


def _run(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _human_bytes(value: int | float | None) -> str | None:
    if value is None:
        return None
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return None


def detect_environment(root: Path | None = None) -> EnvironmentInfo:
    smi = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    cuda = _run(["nvidia-smi", "--query", "--display=COMPUTE"])
    gpu_name = None
    gpu_memory_total = None
    if smi:
        parts = [part.strip() for part in smi.splitlines()[0].split(",")]
        if parts:
            gpu_name = parts[0]
        if len(parts) > 1 and parts[1] != "[N/A]":
            gpu_memory_total = parts[1]

    cuda_version = None
    smi_full = _run(["nvidia-smi"])
    if smi_full and "CUDA Version:" in smi_full:
        cuda_version = smi_full.split("CUDA Version:", 1)[1].split()[0]
    elif cuda:
        cuda_version = "detected"

    torch_version = None
    torch_cuda_available = False
    torch_cuda_version = None
    try:
        import torch

        torch_available = True
        torch_version = getattr(torch, "__version__", None)
        torch_cuda_available = bool(torch.cuda.is_available())
        torch_cuda_version = getattr(torch.version, "cuda", None)
    except Exception:
        torch_available = False

    node_version = _run(["node", "--version"])
    npm_version = _run(["npm", "--version"])
    disk_available = None
    if root:
        usage = shutil.disk_usage(root)
        disk_available = _human_bytes(usage.free)

    info = EnvironmentInfo(
        platform=platform.platform(),
        machine=platform.machine(),
        python_version=sys.version.split()[0],
        cuda_version=cuda_version,
        gpu_name=gpu_name,
        gpu_memory_total=gpu_memory_total,
        system_memory_total=_human_bytes(psutil.virtual_memory().total),
        disk_available=disk_available,
        node_version=node_version,
        npm_version=npm_version,
        blender_available=shutil.which("blender") is not None,
        ffmpeg_available=shutil.which("ffmpeg") is not None,
        torch_available=torch_available,
        torch_version=torch_version,
        torch_cuda_available=torch_cuda_available,
        torch_cuda_version=torch_cuda_version,
    )
    info.recommendations = recommendations(info)
    return info


def recommendations(info: EnvironmentInfo) -> list[str]:
    notes: list[str] = []
    if info.machine == "aarch64":
        notes.append(
            "This is an aarch64 machine. Install PyTorch from a wheel/container known to support "
            "NVIDIA GB10/CUDA 13 instead of assuming standard x86_64 CUDA wheels."
        )
    if info.gpu_name and "GB10" in info.gpu_name:
        notes.append(
            "NVIDIA GB10 was detected. Prefer isolated per-model virtual environments and verify "
            "torch.cuda.is_available() before downloading large checkpoints."
        )
    if not info.torch_available:
        notes.append("PyTorch is not installed in the active Python environment.")
    elif not info.torch_cuda_available:
        notes.append(
            "PyTorch is installed, but torch.cuda.is_available() is false in the active environment. "
            "Use scripts/setup_model_envs.py and point TRIPOSR_PYTHON/HUNYUAN3D_PYTHON to the model envs."
        )
    if not info.blender_available:
        notes.append(
            "Blender CLI is not available. The default postprocess path uses trimesh scale normalization; "
            "mesh decimation can be enabled later with Blender or PyMeshLab."
        )
    if info.disk_available:
        notes.append(f"Available project disk space: {info.disk_available}. Keep model caches under models/cache.")
    return notes
