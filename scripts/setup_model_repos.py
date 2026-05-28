#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from visionspace_asset_foundry.paths import MODEL_REPOS_DIR

REPOS = {
    "TripoSR": "https://github.com/VAST-AI-Research/TripoSR.git",
    "Hunyuan3D-2": "https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git",
}


def run(command: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def clone_repos() -> None:
    MODEL_REPOS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in REPOS.items():
        target = MODEL_REPOS_DIR / name
        if target.exists():
            print(f"skip existing {target}")
            continue
        run(["git", "clone", "--depth", "1", url, str(target)])


def print_install_notes() -> None:
    print(
        """
Model repository setup notes:

1. This machine is aarch64 with NVIDIA GB10/CUDA 13. Standard x86_64 PyTorch CUDA wheels may not work.
2. Install a PyTorch build verified for GB10 first, then install model requirements.
3. TripoSR official command:
   python run.py examples/chair.png --output-dir output/
4. Hunyuan3D runner imports hy3dgen from the official repo and uses:
   Hunyuan3DDiTFlowMatchingPipeline.from_pretrained("tencent/Hunyuan3D-2mini", subfolder="hunyuan3d-dit-v2-mini")
5. Keep Hugging Face cache under models/cache if disk pressure becomes an issue:
   export HF_HOME=/home/jaekwang/visionspace/models/cache/huggingface
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clone", action="store_true", help="Clone official model repositories.")
    args = parser.parse_args()
    if args.clone:
        clone_repos()
    print_install_notes()


if __name__ == "__main__":
    main()
