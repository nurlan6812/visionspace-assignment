from __future__ import annotations

from visionspace_asset_foundry.models.base import ModelRunner
from visionspace_asset_foundry.models.hunyuan import Hunyuan3DMiniRunner
from visionspace_asset_foundry.models.triposr import TripoSRRunner
from visionspace_asset_foundry.schemas import ModelName


def runners() -> dict[ModelName, ModelRunner]:
    return {
        ModelName.triposr: TripoSRRunner(),
        ModelName.hunyuan3d_2mini: Hunyuan3DMiniRunner(),
    }


def get_runner(name: ModelName | str) -> ModelRunner:
    model_name = ModelName(name)
    return runners()[model_name]


def list_model_status() -> list[dict[str, str | bool]]:
    status = []
    for name, runner in runners().items():
        ready, reason = runner.is_available()
        status.append(
            {
                "name": name.value,
                "label": runner.label,
                "ready": ready,
                "reason": reason,
                "requires_image": runner.requires_image,
                "repo": str(runner.repo_dir()),
            }
        )
    return status
