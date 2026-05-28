from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from visionspace_asset_foundry.models.base import ModelRunner, check_torch_runtime
from visionspace_asset_foundry.paths import MODEL_ENVS_DIR, MODEL_REPOS_DIR
from visionspace_asset_foundry.schemas import GenerationRequest, ModelName


class Hunyuan3DMiniRunner(ModelRunner):
    name = ModelName.hunyuan3d_2mini
    label = "Hunyuan3D-2mini"
    requires_image = True

    def repo_dir(self) -> Path:
        return Path(os.getenv("HUNYUAN3D_REPO", MODEL_REPOS_DIR / "Hunyuan3D-2")).expanduser().resolve()

    def python_bin(self) -> str:
        default_python = MODEL_ENVS_DIR / "hunyuan3d" / "bin" / "python"
        return os.getenv("HUNYUAN3D_PYTHON", str(default_python if default_python.exists() else sys.executable))

    def is_available(self) -> tuple[bool, str]:
        repo = self.repo_dir()
        if not (repo / "hy3dgen").exists():
            return False, (
                "Hunyuan3D-2 repo is not installed. Run `python scripts/setup_model_repos.py --clone` "
                "and install the model environment before generation."
            )
        torch_ready, torch_reason = check_torch_runtime(self.python_bin(), require_cuda=True)
        if not torch_ready:
            return False, (
                "Hunyuan3D-2 repo exists, but the configured HUNYUAN3D_PYTHON is not GPU-ready. "
                f"{torch_reason}"
            )
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{repo}:{env.get('PYTHONPATH', '')}"
        result = subprocess.run(
            [self.python_bin(), "-c", "import hy3dgen"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        if result.returncode != 0:
            return False, (
                "Hunyuan3D-2 repo exists, but hy3dgen is not importable from HUNYUAN3D_PYTHON. "
                "Install the official repo requirements into the Hunyuan model environment."
            )
        return True, f"ready: {torch_reason}"

    def command(self, request: GenerationRequest, run_dir: Path, raw_output_dir: Path) -> list[str]:
        assert request.image_path is not None
        image_path = request.image_path.expanduser().resolve()
        script = run_dir / "run_hunyuan.py"
        model_path = os.getenv("HUNYUAN3D_MODEL_PATH", "tencent/Hunyuan3D-2mini")
        subfolder = os.getenv("HUNYUAN3D_SUBFOLDER", "hunyuan3d-dit-v2-mini")
        variant = os.getenv("HUNYUAN3D_VARIANT", "fp16")
        steps = int(os.getenv("HUNYUAN3D_STEPS", "50"))
        octree_resolution = int(os.getenv("HUNYUAN3D_OCTREE_RESOLUTION", "380"))
        num_chunks = int(os.getenv("HUNYUAN3D_NUM_CHUNKS", "20000"))
        seed = int(os.getenv("HUNYUAN3D_SEED", "12345"))
        output_path = raw_output_dir / "hunyuan-output.glb"
        script.write_text(
            f"""
import sys
import time
from pathlib import Path
sys.path.insert(0, {str(self.repo_dir())!r})
import torch
from PIL import Image
from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

image_path = {str(image_path)!r}
output = Path({str(output_path)!r})
image = Image.open(image_path)
if image.mode != "RGBA":
    image = BackgroundRemover()(image.convert("RGB"))
else:
    image = image.convert("RGBA")
print("Loading Hunyuan3D pipeline...", flush=True)
pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
    {model_path!r},
    subfolder={subfolder!r},
    variant={variant!r},
)
print("Hunyuan3D pipeline loaded.", flush=True)
start = time.time()
with torch.inference_mode():
    mesh = pipeline(
        image=image,
        num_inference_steps={steps},
        octree_resolution={octree_resolution},
        num_chunks={num_chunks},
        generator=torch.manual_seed({seed}),
        output_type="trimesh",
    )[0]
print(f"Hunyuan3D generation seconds: {{time.time() - start:.2f}}")
output.parent.mkdir(parents=True, exist_ok=True)
mesh.export(output)
""".strip()
            + "\n",
            encoding="utf-8",
        )
        return [self.python_bin(), str(script)]
