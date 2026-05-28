#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from visionspace_asset_foundry.environment import detect_environment
from visionspace_asset_foundry.paths import MODEL_CACHE_DIR, MODEL_ENVS_DIR, MODEL_REPOS_DIR, ROOT

TORCH_VERSION = "2.12.0"
TORCHVISION_VERSION = "0.27.0"


@dataclass(frozen=True)
class ModelEnv:
    name: str
    repo_dir: Path
    env_dir: Path
    import_check: str

    @property
    def python_bin(self) -> Path:
        return self.env_dir / "bin" / "python"

    @property
    def requirements(self) -> Path:
        return self.repo_dir / "requirements.txt"


MODEL_ENVS = {
    "triposr": ModelEnv(
        name="triposr",
        repo_dir=MODEL_REPOS_DIR / "TripoSR",
        env_dir=MODEL_ENVS_DIR / "triposr",
        import_check="import torch; from tsr.system import TSR; import torchmcubes",
    ),
    "hunyuan3d": ModelEnv(
        name="hunyuan3d",
        repo_dir=MODEL_REPOS_DIR / "Hunyuan3D-2",
        env_dir=MODEL_ENVS_DIR / "hunyuan3d",
        import_check=(
            "import torch; import hy3dgen; "
            "from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline"
        ),
    ),
}


def run(command: list[str], *, dry_run: bool, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    if dry_run:
        return
    subprocess.run(command, check=True, env=env)


def model_names(selection: str) -> list[str]:
    if selection == "all":
        return list(MODEL_ENVS)
    return [selection]


def find_uv_python(candidate: str) -> str | None:
    result = subprocess.run(
        ["uv", "python", "find", candidate],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def base_python(*, dry_run: bool) -> str:
    managed_version = "3.12.13"
    managed_python = find_uv_python(managed_version)
    if managed_python:
        return managed_python
    if dry_run:
        return managed_version
    run(["uv", "python", "install", managed_version], dry_run=False)
    managed_python = find_uv_python(managed_version)
    if managed_python:
        return managed_python
    for candidate in ["3.12"]:
        result = subprocess.run(
            ["uv", "python", "find", candidate],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return shutil.which("python3.12") or shutil.which("python3") or sys.executable


def torch_backend() -> str:
    info = detect_environment(ROOT)
    if info.cuda_version and info.cuda_version.startswith("13"):
        return "cu130"
    return "auto"


def parse_requirements(path: Path) -> list[str]:
    requirements: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirements.append(line)
    return requirements


def create_env(spec: ModelEnv, *, dry_run: bool, recreate: bool) -> None:
    if recreate and spec.env_dir.exists():
        print(f"remove existing {spec.env_dir}")
        if not dry_run:
            shutil.rmtree(spec.env_dir)
    if spec.python_bin.exists():
        print(f"skip existing env {spec.env_dir}")
        return
    spec.env_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["uv", "venv", "--python", base_python(dry_run=dry_run), str(spec.env_dir)], dry_run=dry_run)


def install_torch(spec: ModelEnv, *, backend: str, dry_run: bool) -> None:
    packages = [
        f"torch=={TORCH_VERSION}",
        f"torchvision=={TORCHVISION_VERSION}",
    ]
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(spec.python_bin),
            "--torch-backend",
            backend,
            *packages,
        ],
        dry_run=dry_run,
    )


def install_triposr_requirements(spec: ModelEnv, *, dry_run: bool, include_texture_tools: bool) -> None:
    requirements = parse_requirements(spec.requirements)
    torchmcubes = [req for req in requirements if "torchmcubes" in req]
    texture_tools = {"xatlas", "moderngl"}
    other_requirements = []
    for req in requirements:
        package_name = req.lower().split("==", 1)[0].split("[", 1)[0]
        if "torchmcubes" in req:
            continue
        if not include_texture_tools and package_name in texture_tools:
            continue
        other_requirements.append(req)
    if other_requirements:
        if not any(req.lower().startswith("onnxruntime") for req in other_requirements):
            other_requirements.append("onnxruntime")
        run(
            ["uv", "pip", "install", "--python", str(spec.python_bin), *other_requirements],
            dry_run=dry_run,
        )
    for req in torchmcubes:
        build_env = os.environ.copy()
        build_env.setdefault("TORCH_CUDA_ARCH_LIST", "12.1a")
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(spec.python_bin),
                "scikit-build-core",
                "cmake",
                "ninja",
                "pybind11",
            ],
            dry_run=dry_run,
        )
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(spec.python_bin),
                "--no-build-isolation",
                req,
            ],
            dry_run=dry_run,
            env=build_env,
        )


def install_hunyuan_requirements(spec: ModelEnv, *, backend: str, dry_run: bool) -> None:
    requirements = []
    for req in parse_requirements(spec.requirements):
        normalized = req.lower().split("==", 1)[0].split(">=", 1)[0]
        if normalized in {"torch", "torchvision"}:
            continue
        requirements.append(req)
    if requirements:
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(spec.python_bin),
                "--torch-backend",
                backend,
                *requirements,
            ],
            dry_run=dry_run,
        )
    run(
        ["uv", "pip", "install", "--python", str(spec.python_bin), "--no-deps", "-e", str(spec.repo_dir)],
        dry_run=dry_run,
    )


def verify(spec: ModelEnv, *, dry_run: bool) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{spec.repo_dir}:{env.get('PYTHONPATH', '')}"
    env.setdefault("HF_HOME", str(MODEL_CACHE_DIR / "huggingface"))
    env.setdefault("HF_HUB_CACHE", str(MODEL_CACHE_DIR / "huggingface" / "hub"))
    env.setdefault("TORCH_HOME", str(MODEL_CACHE_DIR / "torch"))
    env.setdefault("HY3DGEN_MODELS", str(MODEL_CACHE_DIR / "hy3dgen"))
    script = f"""
import json
{spec.import_check}
payload = {{
    "torch": torch.__version__,
    "cuda": torch.version.cuda,
    "cuda_available": torch.cuda.is_available(),
    "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
}}
print(json.dumps(payload, ensure_ascii=False))
""".strip()
    run([str(spec.python_bin), "-c", script], dry_run=dry_run, env=env)


def install_model(
    spec: ModelEnv,
    *,
    backend: str,
    dry_run: bool,
    recreate: bool,
    torch_only: bool,
    include_texture_tools: bool,
) -> None:
    if not spec.repo_dir.exists():
        raise SystemExit(
            f"{spec.repo_dir} does not exist. Run `python scripts/setup_model_repos.py --clone` first."
        )
    create_env(spec, dry_run=dry_run, recreate=recreate)
    install_torch(spec, backend=backend, dry_run=dry_run)
    if not torch_only:
        if spec.name == "triposr":
            install_triposr_requirements(
                spec,
                dry_run=dry_run,
                include_texture_tools=include_texture_tools,
            )
        elif spec.name == "hunyuan3d":
            install_hunyuan_requirements(spec, backend=backend, dry_run=dry_run)
    verify(spec, dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create isolated GB10-ready model environments.")
    parser.add_argument("--model", choices=["all", *MODEL_ENVS], default="all")
    parser.add_argument("--backend", default=torch_backend())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--torch-only", action="store_true")
    parser.add_argument(
        "--include-texture-tools",
        action="store_true",
        help="Install TripoSR texture-baking dependencies such as xatlas/moderngl.",
    )
    args = parser.parse_args()

    print(f"Using PyTorch backend: {args.backend}")
    for name in model_names(args.model):
        install_model(
            MODEL_ENVS[name],
            backend=args.backend,
            dry_run=args.dry_run,
            recreate=args.recreate,
            torch_only=args.torch_only,
            include_texture_tools=args.include_texture_tools,
        )

    print(
        "\nSet these variables before running generation:\n"
        f"export TRIPOSR_PYTHON={MODEL_ENVS['triposr'].python_bin}\n"
        f"export HUNYUAN3D_PYTHON={MODEL_ENVS['hunyuan3d'].python_bin}\n"
        f"export HF_HOME={MODEL_CACHE_DIR / 'huggingface'}\n"
    )


if __name__ == "__main__":
    main()
