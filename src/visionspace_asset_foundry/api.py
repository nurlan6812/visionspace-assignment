from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from visionspace_asset_foundry.environment import detect_environment
from visionspace_asset_foundry.jobs import job_store
from visionspace_asset_foundry.models import list_model_status
from visionspace_asset_foundry.paths import OUTPUTS_DIR, ROOT, UPLOADS_DIR, ensure_runtime_dirs
from visionspace_asset_foundry.prompts import get_prompt, load_prompts
from visionspace_asset_foundry.scene_llm import SceneLLMError, SceneLLMUnavailableError
from visionspace_asset_foundry.scene_interpreter import interpret_scene, scene_tool_schema
from visionspace_asset_foundry.schemas import (
    AssetType,
    Dimensions,
    GenerationRequest,
    ModelName,
    SceneParseRequest,
)

ensure_runtime_dirs()

app = FastAPI(title="VisionSpace Asset Foundry", version="0.1.0")

frontend_origins = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
}
if configured_origins := os.getenv("FRONTEND_ORIGIN"):
    frontend_origins.update(origin.strip() for origin in configured_origins.split(",") if origin.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(frontend_origins),
    allow_origin_regex=(
        r"https?://("
        r"localhost|127\.0\.0\.1|"
        r"10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
        r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}|"
        r"(?:[A-Za-z0-9-]+\.)+[A-Za-z0-9-]+\.ts\.net"
        r"):\d+"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/generated", StaticFiles(directory=OUTPUTS_DIR), name="generated")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/environment")
def environment():
    return detect_environment(ROOT)


@app.get("/api/models")
def models():
    return list_model_status()


@app.get("/api/prompts")
def prompts():
    return load_prompts()


@app.get("/api/scene/cases")
def scene_cases():
    path = ROOT / "data" / "scene_cases" / "text_to_scene_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/scene/tool-schema")
def scene_tool_contract():
    return scene_tool_schema()


@app.post("/api/scene/parse")
async def parse_scene_endpoint(payload: SceneParseRequest):
    try:
        return interpret_scene(payload.user_instruction, strategy=payload.strategy)
    except SceneLLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SceneLLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/generate")
async def generate(
    prompt: Annotated[str, Form()],
    model: Annotated[ModelName, Form()],
    asset_type: Annotated[AssetType, Form()] = AssetType.unknown,
    prompt_id: Annotated[str | None, Form()] = None,
    target_dimensions_m: Annotated[str | None, Form()] = None,
    bake_texture: Annotated[bool, Form()] = False,
    image: UploadFile | None = File(default=None),
):
    image_path: Path | None = None
    prompt_spec = get_prompt(prompt_id) if prompt_id else None
    if prompt_spec:
        asset_type = prompt_spec.asset_type
        if not prompt:
            prompt = prompt_spec.prompt

    dimensions = prompt_spec.target_dimensions_m if prompt_spec else None
    if target_dimensions_m:
        try:
            dimensions = Dimensions.model_validate(json.loads(target_dimensions_m))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid target_dimensions_m: {exc}") from exc

    if image and image.filename:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = Path(image.filename).suffix or ".png"
        image_path = UPLOADS_DIR / f"{model.value}-{Path(image.filename).stem}{suffix}"
        with image_path.open("wb") as output:
            shutil.copyfileobj(image.file, output)

    request = GenerationRequest(
        prompt_id=prompt_id,
        prompt=prompt,
        asset_type=asset_type,
        model=model,
        image_path=image_path,
        target_dimensions_m=dimensions,
        bake_texture=bake_texture,
    )
    return job_store.create(request)


@app.get("/api/jobs")
def jobs():
    return job_store.list()


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    found = job_store.get(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found.")
    return found


@app.get("/api/assets")
def assets():
    return [job.asset for job in job_store.list() if job.asset is not None]
