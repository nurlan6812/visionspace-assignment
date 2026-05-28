from __future__ import annotations

import json
from pathlib import Path

from visionspace_asset_foundry.paths import DATA_DIR
from visionspace_asset_foundry.schemas import PromptSpec


DEFAULT_PROMPTS_PATH = DATA_DIR / "prompts" / "industrial_assets.jsonl"


def load_prompts(path: Path = DEFAULT_PROMPTS_PATH) -> list[PromptSpec]:
    prompts: list[PromptSpec] = []
    if not path.exists():
        return prompts
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        prompts.append(PromptSpec.model_validate(json.loads(line)))
    return prompts


def get_prompt(prompt_id: str, path: Path = DEFAULT_PROMPTS_PATH) -> PromptSpec | None:
    for prompt in load_prompts(path):
        if prompt.id == prompt_id:
            return prompt
    return None
