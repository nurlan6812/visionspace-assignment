from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class AssetType(StrEnum):
    agv = "agv"
    robot_arm = "robot_arm"
    conveyor = "conveyor"
    rack = "rack"
    pallet_box = "pallet_box"
    worker = "worker"
    charging_station = "charging_station"
    safety_fence = "safety_fence"
    unknown = "unknown"


class ModelName(StrEnum):
    triposr = "triposr"
    hunyuan3d_2mini = "hunyuan3d_2mini"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    postprocessing = "postprocessing"
    completed = "completed"
    failed = "failed"


class Dimensions(BaseModel):
    x: float
    y: float
    z: float


class PromptSpec(BaseModel):
    id: str
    asset_type: AssetType
    title: str
    prompt: str
    target_dimensions_m: Dimensions | None = None
    notes: str | None = None


class MeshMetrics(BaseModel):
    file_size_bytes: int = 0
    vertices: int | None = None
    faces: int | None = None
    mesh_count: int | None = None
    bounding_box_m: Dimensions | None = None
    largest_dimension_m: float | None = None
    is_watertight: bool | None = None
    has_materials: bool | None = None
    has_textures: bool | None = None
    warnings: list[str] = Field(default_factory=list)


class GenerationRequest(BaseModel):
    prompt_id: str | None = None
    prompt: str
    asset_type: AssetType = AssetType.unknown
    model: ModelName
    image_path: Path | None = None
    target_dimensions_m: Dimensions | None = None
    bake_texture: bool = False
    texture_resolution: int = 1024


class AssetRecord(BaseModel):
    id: str
    prompt_id: str | None = None
    title: str | None = None
    asset_type: AssetType
    model: ModelName
    prompt: str
    source_image: str | None = None
    raw_path: str | None = None
    glb_path: str
    normalized_path: str | None = None
    download_url: str | None = None
    metrics: MeshMetrics | None = None
    normalized_metrics: MeshMetrics | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: list[str] = Field(default_factory=list)


class GenerationJob(BaseModel):
    id: str
    status: JobStatus = JobStatus.queued
    request: GenerationRequest
    asset: AssetRecord | None = None
    error: str | None = None
    logs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EnvironmentInfo(BaseModel):
    platform: str
    machine: str
    python_version: str
    cuda_version: str | None = None
    gpu_name: str | None = None
    gpu_memory_total: str | None = None
    system_memory_total: str | None = None
    disk_available: str | None = None
    node_version: str | None = None
    npm_version: str | None = None
    blender_available: bool = False
    ffmpeg_available: bool = False
    torch_available: bool = False
    torch_version: str | None = None
    torch_cuda_available: bool = False
    torch_cuda_version: str | None = None
    recommendations: list[str] = Field(default_factory=list)


class SpaceSpec(BaseModel):
    type: Literal["factory", "warehouse", "workspace"] = "warehouse"
    shape: Literal["rectangle", "unknown"] = "unknown"
    area_m2: float | None = None
    area_source: str | None = None
    units: Literal["m"] = "m"


class PlacementSpec(BaseModel):
    pattern: str = "unspecified"
    zone: str | None = None
    near: str | None = None
    notes: list[str] = Field(default_factory=list)


class EntitySpec(BaseModel):
    type: AssetType
    quantity: int = 1
    placement: PlacementSpec = Field(default_factory=PlacementSpec)
    properties: dict[str, Any] = Field(default_factory=dict)


class DraftEntityPropertiesSpec(BaseModel):
    mode: str | None = None
    priority_quantity: int | None = None
    speed_profile: str | None = None
    notes: list[str] = Field(default_factory=list)


class DraftEntitySpec(BaseModel):
    type: AssetType
    quantity: int = 1
    placement: PlacementSpec = Field(default_factory=PlacementSpec)
    properties: DraftEntityPropertiesSpec = Field(default_factory=DraftEntityPropertiesSpec)


class DraftGlobalConstraintsSpec(BaseModel):
    collision_avoidance: bool = False


class SceneGraphNode(BaseModel):
    id: str
    kind: Literal["space", "entity_group", "zone", "constraint", "task"]
    label: str
    ref_type: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SceneGraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class SceneGraphSpec(BaseModel):
    nodes: list[SceneGraphNode] = Field(default_factory=list)
    edges: list[SceneGraphEdge] = Field(default_factory=list)


SceneParserStrategy = Literal["deterministic_tool", "llm_structured_output", "hybrid_fallback"]


class SceneParseRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_instruction: str = Field(
        description="Natural-language instruction describing an industrial simulation scene.",
        validation_alias=AliasChoices("user_instruction", "text"),
    )
    strategy: SceneParserStrategy = "hybrid_fallback"


class ToolCallSpec(BaseModel):
    name: str = "parse_scene_to_scene_spec"
    version: str = "0.1"
    strategy: SceneParserStrategy = "deterministic_tool"
    input_schema_ref: str = "SceneParseRequest"
    output_schema_ref: str = "SceneSpec"
    validation: Literal["pending", "passed", "failed"] = "passed"
    provider: str | None = None
    model: str | None = None
    executor: str | None = None
    fallback_used: bool = False
    notes: list[str] = Field(default_factory=list)


class DownstreamTaskSpec(BaseModel):
    name: Literal["asset_resolution", "layout_generation", "simulation_export", "scene_validation"]
    status: Literal["ready", "needs_confirmation", "blocked"] = "ready"
    consumes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SceneDraftSpec(BaseModel):
    source_text: str
    space: SpaceSpec
    entities: list[DraftEntitySpec]
    global_constraints: DraftGlobalConstraintsSpec = Field(default_factory=DraftGlobalConstraintsSpec)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SceneSpec(BaseModel):
    version: str = "0.2"
    source_text: str
    space: SpaceSpec
    entities: list[EntitySpec]
    global_constraints: dict[str, Any] = Field(default_factory=dict)
    required_asset_types: list[AssetType] = Field(default_factory=list)
    scene_graph: SceneGraphSpec = Field(default_factory=SceneGraphSpec)
    downstream_tasks: list[DownstreamTaskSpec] = Field(default_factory=list)
    tool_call: ToolCallSpec = Field(default_factory=ToolCallSpec)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
