from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    env_root = os.getenv("VSAF_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path.cwd().resolve()


ROOT = project_root()
DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
ASSETS_DIR = OUTPUTS_DIR / "assets"
RUNS_DIR = OUTPUTS_DIR / "model-runs"
METRICS_DIR = OUTPUTS_DIR / "metrics"
RENDERS_DIR = OUTPUTS_DIR / "renders"
MODEL_REPOS_DIR = ROOT / "models" / "repos"
MODEL_ENVS_DIR = ROOT / "models" / "envs"
MODEL_CACHE_DIR = ROOT / "models" / "cache"


def ensure_runtime_dirs() -> None:
    for path in [
        OUTPUTS_DIR,
        UPLOADS_DIR,
        ASSETS_DIR,
        RUNS_DIR,
        METRICS_DIR,
        RENDERS_DIR,
        MODEL_REPOS_DIR,
        MODEL_ENVS_DIR,
        MODEL_CACHE_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())
