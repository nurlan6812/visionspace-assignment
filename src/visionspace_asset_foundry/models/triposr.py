from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from visionspace_asset_foundry.models.base import ModelRunner, check_torch_runtime
from visionspace_asset_foundry.paths import MODEL_ENVS_DIR, MODEL_REPOS_DIR
from visionspace_asset_foundry.schemas import GenerationRequest, ModelName


class TripoSRRunner(ModelRunner):
    name = ModelName.triposr
    label = "TripoSR"
    requires_image = True

    def repo_dir(self) -> Path:
        return Path(os.getenv("TRIPOSR_REPO", MODEL_REPOS_DIR / "TripoSR")).expanduser().resolve()

    def python_bin(self) -> str:
        default_python = MODEL_ENVS_DIR / "triposr" / "bin" / "python"
        return os.getenv("TRIPOSR_PYTHON", str(default_python if default_python.exists() else sys.executable))

    def is_available(self) -> tuple[bool, str]:
        repo = self.repo_dir()
        if not (repo / "run.py").exists():
            return False, (
                "TripoSR repo is not installed. Run `python scripts/setup_model_repos.py --clone` "
                "and install the model environment before generation."
            )
        torch_ready, torch_reason = check_torch_runtime(self.python_bin(), require_cuda=True)
        if not torch_ready:
            return False, (
                "TripoSR repo exists, but the configured TRIPOSR_PYTHON is not GPU-ready. "
                f"{torch_reason}"
            )
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{repo}:{env.get('PYTHONPATH', '')}"
        result = subprocess.run(
            [self.python_bin(), "-c", "from tsr.system import TSR; import rembg; import torchmcubes"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        if result.returncode != 0:
            return False, (
                "TripoSR repo exists, but model dependencies are not importable from TRIPOSR_PYTHON. "
                "Run `python scripts/setup_model_envs.py --model triposr`."
            )
        return True, f"ready: {torch_reason}"

    def command(self, request: GenerationRequest, run_dir: Path, raw_output_dir: Path) -> list[str]:
        assert request.image_path is not None
        image_path = request.image_path.expanduser().resolve()
        if request.bake_texture:
            return [
                self.python_bin(),
                str(self.repo_dir() / "run.py"),
                str(image_path),
                "--output-dir",
                str(raw_output_dir),
                "--model-save-format",
                "glb",
                "--bake-texture",
                "--texture-resolution",
                str(request.texture_resolution),
            ]

        script = run_dir / "run_triposr.py"
        output_path = raw_output_dir / "triposr-output.glb"
        pretrained = os.getenv("TRIPOSR_MODEL_PATH", "stabilityai/TripoSR")
        chunk_size = int(os.getenv("TRIPOSR_CHUNK_SIZE", "8192"))
        mc_resolution = int(os.getenv("TRIPOSR_MC_RESOLUTION", "256"))
        foreground_ratio = float(os.getenv("TRIPOSR_FOREGROUND_RATIO", "0.85"))
        script.write_text(
            f"""
import sys
import time
from pathlib import Path
sys.path.insert(0, {str(self.repo_dir())!r})
import numpy as np
import rembg
import torch
from PIL import Image
from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground

image_path = {str(image_path)!r}
output = Path({str(output_path)!r})
device = "cuda:0" if torch.cuda.is_available() else "cpu"

start = time.time()
model = TSR.from_pretrained(
    {pretrained!r},
    config_name="config.yaml",
    weight_name="model.ckpt",
)
model.renderer.set_chunk_size({chunk_size})
model.to(device)

rembg_session = rembg.new_session()
image = remove_background(Image.open(image_path), rembg_session)
image = resize_foreground(image, {foreground_ratio})
array = np.array(image).astype(np.float32) / 255.0
array = array[:, :, :3] * array[:, :, 3:4] + (1 - array[:, :, 3:4]) * 0.5
image = Image.fromarray((array * 255.0).astype(np.uint8))

with torch.inference_mode():
    scene_codes = model([image], device=device)
    meshes = model.extract_mesh(scene_codes, True, resolution={mc_resolution})
output.parent.mkdir(parents=True, exist_ok=True)
meshes[0].export(output)
print(f"TripoSR generation seconds: {{time.time() - start:.2f}}")
""".strip()
            + "\n",
            encoding="utf-8",
        )
        return [self.python_bin(), str(script)]
