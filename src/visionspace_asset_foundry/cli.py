from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn
from rich import print
from rich.table import Table

from visionspace_asset_foundry.environment import detect_environment
from visionspace_asset_foundry.models import list_model_status
from visionspace_asset_foundry.paths import ROOT, ensure_runtime_dirs
from visionspace_asset_foundry.postprocess import inspect_mesh, normalize_glb
from visionspace_asset_foundry.prompts import load_prompts
from visionspace_asset_foundry.scene_interpreter import interpret_scene, scene_tool_schema
from visionspace_asset_foundry.schemas import AssetType, GenerationRequest, ModelName, SceneParserStrategy
from visionspace_asset_foundry.models import get_runner

app = typer.Typer(help="VisionSpace Asset Foundry CLI")


@app.command("env")
def env_command() -> None:
    info = detect_environment(ROOT)
    print(info.model_dump_json(indent=2))


@app.command("models")
def models_command() -> None:
    table = Table("name", "label", "ready", "reason", "repo")
    for item in list_model_status():
        table.add_row(
            str(item["name"]),
            str(item["label"]),
            str(item["ready"]),
            str(item["reason"]),
            str(item["repo"]),
        )
    print(table)


@app.command("prompts")
def prompts_command() -> None:
    table = Table("id", "asset_type", "title")
    for prompt in load_prompts():
        table.add_row(prompt.id, prompt.asset_type.value, prompt.title)
    print(table)


@app.command("scene")
def scene_command(text: str, strategy: SceneParserStrategy = "hybrid_fallback") -> None:
    spec = interpret_scene(text, strategy=strategy)
    print(spec.model_dump_json(indent=2))




@app.command("scene-tool-schema")
def scene_tool_schema_command() -> None:
    print(json.dumps(scene_tool_schema(), ensure_ascii=False, indent=2))

@app.command("inspect")
def inspect_command(path: Path) -> None:
    print(inspect_mesh(path).model_dump_json(indent=2))


@app.command("normalize")
def normalize_command(
    input_path: Path,
    output_path: Path,
    target_largest_dimension_m: float = 2.0,
) -> None:
    metrics = normalize_glb(input_path, output_path, target_largest_dimension_m)
    print(metrics.model_dump_json(indent=2))


@app.command("generate")
def generate_command(
    model: ModelName,
    image_path: Path,
    prompt: str,
    asset_type: AssetType = AssetType.unknown,
    prompt_id: str | None = None,
) -> None:
    ensure_runtime_dirs()
    request = GenerationRequest(
        model=model,
        image_path=image_path,
        prompt=prompt,
        prompt_id=prompt_id,
        asset_type=asset_type,
    )
    asset = get_runner(model).generate(request)
    print(asset.model_dump_json(indent=2))


@app.command("validate-scenes")
def validate_scenes_command(path: Path = ROOT / "data" / "scene_cases" / "text_to_scene_cases.json") -> None:
    cases = json.loads(path.read_text(encoding="utf-8"))
    for case in cases:
        spec = interpret_scene(case["input"])
        print(f"[bold]{case['id']}[/bold]")
        print(spec.model_dump_json(indent=2))


@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    ensure_runtime_dirs()
    uvicorn.run("visionspace_asset_foundry.api:app", host=host, port=port, reload=False)
