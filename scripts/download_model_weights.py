#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from visionspace_asset_foundry.paths import MODEL_CACHE_DIR


@dataclass(frozen=True)
class SnapshotSpec:
    name: str
    repo_id: str
    allow_patterns: list[str] | None = None


SNAPSHOTS = {
    "triposr": SnapshotSpec(name="triposr", repo_id="stabilityai/TripoSR"),
    "hunyuan3d_2mini": SnapshotSpec(
        name="hunyuan3d_2mini",
        repo_id="tencent/Hunyuan3D-2mini",
        allow_patterns=["hunyuan3d-dit-v2-mini/*"],
    ),
}


def link_hy3dgen_layout(spec: SnapshotSpec, snapshot_path: str) -> None:
    if not spec.repo_id.startswith("tencent/Hunyuan3D"):
        return
    target = MODEL_CACHE_DIR / "hy3dgen" / spec.repo_id
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists():
        if target.resolve() == Path(snapshot_path).resolve():
            return
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    target.symlink_to(Path(snapshot_path).resolve(), target_is_directory=True)
    print(f"  hy3dgen local layout linked at {target}")


def selected_names(selection: str) -> list[str]:
    if selection == "all":
        return list(SNAPSHOTS)
    return [selection]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Hugging Face model snapshots into models/cache.")
    parser.add_argument("--model", choices=["all", *SNAPSHOTS], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("HF_HOME", str(MODEL_CACHE_DIR / "huggingface"))
    os.environ.setdefault("HF_HUB_CACHE", str(MODEL_CACHE_DIR / "huggingface" / "hub"))
    os.environ.setdefault("HY3DGEN_MODELS", str(MODEL_CACHE_DIR / "hy3dgen"))

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for name in selected_names(args.model):
        spec = SNAPSHOTS[name]
        print(f"snapshot: {spec.repo_id}")
        if args.dry_run:
            print(f"  cache_dir={MODEL_CACHE_DIR / 'huggingface'}")
            print(f"  allow_patterns={spec.allow_patterns or '*'}")
            continue
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise SystemExit("Install project model helpers first: `uv pip install -e '.[models]'`.") from exc
        path = snapshot_download(
            repo_id=spec.repo_id,
            cache_dir=str(MODEL_CACHE_DIR / "huggingface"),
            allow_patterns=spec.allow_patterns,
        )
        print(f"  downloaded to {path}")
        link_hy3dgen_layout(spec, path)


if __name__ == "__main__":
    main()
