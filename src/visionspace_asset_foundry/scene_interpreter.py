from __future__ import annotations

from collections import OrderedDict

from visionspace_asset_foundry.scene_llm import (
    SceneLLMError,
    parse_scene_with_openai,
)
from visionspace_asset_foundry.scene_parser import parse_scene
from visionspace_asset_foundry.schemas import (
    DownstreamTaskSpec,
    DraftEntityPropertiesSpec,
    DraftEntitySpec,
    EntitySpec,
    SceneDraftSpec,
    SceneGraphEdge,
    SceneGraphNode,
    SceneGraphSpec,
    SceneParseRequest,
    SceneParserStrategy,
    SceneSpec,
    ToolCallSpec,
)

SCENE_PARSING_TOOL_CONTRACT = {
    "type": "function",
    "function": {
        "name": "parse_scene_to_scene_spec",
        "description": (
            "Convert a user's natural-language industrial simulation instruction into a schema-validated "
            "SceneSpec that downstream asset, layout, simulator export, and validation tools can consume."
        ),
        "parameters": SceneParseRequest.model_json_schema(),
        "returns": "SceneSpec",
    },
}


def _entity_node_id(entity: EntitySpec, index: int) -> str:
    return f"entity:{entity.type.value}:{index}"


def _dedupe(items: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(items))


def _draft_properties_to_dict(properties: DraftEntityPropertiesSpec) -> dict[str, object]:
    raw = properties.model_dump(mode="json")
    return {
        key: value
        for key, value in raw.items()
        if value not in (None, "", [], {})
    }


def _draft_entity_to_entity_spec(entity: DraftEntitySpec) -> EntitySpec:
    return EntitySpec(
        type=entity.type,
        quantity=max(1, entity.quantity),
        placement=entity.placement,
        properties=_draft_properties_to_dict(entity.properties),
    )


def draft_to_scene_spec(draft: SceneDraftSpec) -> SceneSpec:
    return SceneSpec(
        source_text=draft.source_text,
        space=draft.space,
        entities=[_draft_entity_to_entity_spec(entity) for entity in draft.entities],
        global_constraints=draft.global_constraints.model_dump(mode="json"),
        assumptions=draft.assumptions,
        warnings=draft.warnings,
    )


def normalize_scene_spec(spec: SceneSpec, source_text: str) -> SceneSpec:
    spec.source_text = source_text
    spec.entities = [
        EntitySpec(
            type=entity.type,
            quantity=max(1, entity.quantity),
            placement=entity.placement,
            properties=entity.properties,
        )
        for entity in spec.entities
    ]

    for entity in spec.entities:
        if entity.placement.pattern == "unspecified":
            default_note = "Placement pattern was not explicit; default placement is required downstream."
            if default_note not in entity.placement.notes:
                entity.placement.notes.append(default_note)

    if not spec.entities:
        spec.warnings.append("No known industrial entity type was detected.")

    if spec.space.area_m2 is None:
        spec.assumptions.append("Space area was not specified; downstream layout should request confirmation.")
    if spec.space.shape == "unknown":
        spec.assumptions.append("Space shape was not specified; rectangular layout is the recommended default.")

    spec.assumptions = _dedupe(spec.assumptions)
    spec.warnings = _dedupe(spec.warnings)

    if "collision_avoidance" not in spec.global_constraints:
        spec.global_constraints["collision_avoidance"] = any(
            entity.properties.get("mode") == "avoidance_priority" for entity in spec.entities
        )

    spec.required_asset_types = list(
        OrderedDict.fromkeys(entity.type for entity in spec.entities)
    )
    return spec


def build_scene_graph(spec: SceneSpec) -> SceneGraphSpec:
    nodes: list[SceneGraphNode] = [
        SceneGraphNode(
            id="space:main",
            kind="space",
            label=f"{spec.space.type}:{spec.space.shape}",
            ref_type=spec.space.type,
            attributes=spec.space.model_dump(mode="json"),
        )
    ]
    edges: list[SceneGraphEdge] = []
    zone_nodes: set[str] = set()

    for index, entity in enumerate(spec.entities):
        entity_id = _entity_node_id(entity, index)
        nodes.append(
            SceneGraphNode(
                id=entity_id,
                kind="entity_group",
                label=f"{entity.quantity} x {entity.type.value}",
                ref_type=entity.type.value,
                attributes={
                    "quantity": entity.quantity,
                    "placement": entity.placement.model_dump(mode="json"),
                    "properties": entity.properties,
                },
            )
        )
        edges.append(SceneGraphEdge(source=entity_id, target="space:main", relation="placed_in"))

        if entity.placement.near:
            zone_id = f"zone:{entity.placement.near}"
            if zone_id not in zone_nodes:
                zone_nodes.add(zone_id)
                nodes.append(
                    SceneGraphNode(
                        id=zone_id,
                        kind="zone",
                        label=entity.placement.near,
                        ref_type="zone",
                    )
                )
            edges.append(SceneGraphEdge(source=entity_id, target=zone_id, relation="near"))

        if entity.placement.zone:
            zone_id = f"zone:{entity.placement.zone}"
            if zone_id not in zone_nodes:
                zone_nodes.add(zone_id)
                nodes.append(
                    SceneGraphNode(
                        id=zone_id,
                        kind="zone",
                        label=entity.placement.zone,
                        ref_type="zone",
                    )
                )
            edges.append(SceneGraphEdge(source=entity_id, target=zone_id, relation="assigned_to_zone"))

    if spec.global_constraints.get("collision_avoidance"):
        nodes.append(
            SceneGraphNode(
                id="constraint:collision_avoidance",
                kind="constraint",
                label="collision_avoidance",
                ref_type="safety_constraint",
                attributes={"enabled": True},
            )
        )
        for index, entity in enumerate(spec.entities):
            if entity.properties.get("mode") == "avoidance_priority":
                edges.append(
                    SceneGraphEdge(
                        source=_entity_node_id(entity, index),
                        target="constraint:collision_avoidance",
                        relation="governed_by",
                    )
                )

    return SceneGraphSpec(nodes=nodes, edges=edges)


def plan_downstream_tasks(spec: SceneSpec) -> list[DownstreamTaskSpec]:
    layout_notes: list[str] = []
    layout_status = "ready"
    if spec.space.area_m2 is None:
        layout_status = "needs_confirmation"
        layout_notes.append("Space area is missing; layout solver should request or infer dimensions.")
    if spec.space.shape == "unknown":
        layout_status = "needs_confirmation"
        layout_notes.append("Space shape is missing; rectangular layout can be used as a default assumption.")
    if not spec.entities:
        layout_status = "blocked"
        layout_notes.append("No entities were detected, so layout generation is blocked.")

    return [
        DownstreamTaskSpec(
            name="asset_resolution",
            status="ready" if spec.required_asset_types else "blocked",
            consumes=["SceneSpec.required_asset_types"],
            produces=["AssetRequirement[]", "missing_asset_queue"],
            notes=["Resolve existing GLB assets first; call Track 1 asset generation only for missing asset classes."],
        ),
        DownstreamTaskSpec(
            name="layout_generation",
            status=layout_status,
            consumes=["SceneSpec.space", "SceneSpec.entities", "SceneGraphSpec"],
            produces=["positioned_scene_graph", "spawn_plan"],
            notes=layout_notes,
        ),
        DownstreamTaskSpec(
            name="simulation_export",
            status="ready" if spec.entities else "blocked",
            consumes=["positioned_scene_graph", "resolved_assets"],
            produces=["Unity/Unreal/Isaac scene config", "simulator asset manifest"],
            notes=["Exporter should remain simulator-agnostic until target runtime is selected."],
        ),
        DownstreamTaskSpec(
            name="scene_validation",
            status="ready",
            consumes=["SceneSpec", "SceneGraphSpec"],
            produces=["validation_report"],
            notes=["Validate schema, missing parameters, collision policy, asset availability, and scale consistency."],
        ),
    ]


def _deterministic_scene_spec(user_instruction: str) -> SceneSpec:
    return normalize_scene_spec(parse_scene(user_instruction), user_instruction)


def _llm_scene_spec(user_instruction: str) -> tuple[SceneSpec, ToolCallSpec]:
    result = parse_scene_with_openai(user_instruction)
    spec = normalize_scene_spec(draft_to_scene_spec(result.draft), user_instruction)
    runtime_label = "vLLM guided JSON output" if result.provider == "vllm" else "OpenAI structured output"
    executor = "vllm_guided_json" if result.provider == "vllm" else "openai_structured_output"
    return spec, ToolCallSpec(
        strategy="llm_structured_output",
        validation="passed",
        provider=result.provider,
        model=result.model,
        executor=executor,
        notes=[
            f"SceneSpec was produced with {runtime_label} and then normalized for downstream tools.",
        ],
    )


def interpret_scene(
    user_instruction: str,
    strategy: SceneParserStrategy = "hybrid_fallback",
) -> SceneSpec:
    if strategy == "deterministic_tool":
        spec = _deterministic_scene_spec(user_instruction)
        tool_call = ToolCallSpec(
            strategy=strategy,
            validation="passed",
            executor="deterministic_rule_parser",
            notes=[
                "SceneSpec is treated as the structured function output contract for downstream tools.",
                "The runtime used deterministic alias and regex rules only.",
            ],
        )
    elif strategy == "llm_structured_output":
        spec, tool_call = _llm_scene_spec(user_instruction)
    else:
        try:
            spec, tool_call = _llm_scene_spec(user_instruction)
            tool_call.strategy = "hybrid_fallback"
            tool_call.notes.append("Hybrid mode selected; LLM structured output succeeded, so rule fallback was not used.")
        except SceneLLMError as exc:
            spec = _deterministic_scene_spec(user_instruction)
            tool_call = ToolCallSpec(
                strategy="hybrid_fallback",
                validation="passed",
                executor="deterministic_rule_parser",
                fallback_used=True,
                notes=[
                    "Hybrid mode selected; LLM structured output was unavailable or invalid.",
                    f"Fallback reason: {exc}",
                    "Deterministic parser output was used to preserve pipeline continuity.",
                ],
            )

    spec.tool_call = tool_call
    spec.scene_graph = build_scene_graph(spec)
    spec.downstream_tasks = plan_downstream_tasks(spec)
    return spec


def scene_tool_schema() -> dict[str, object]:
    return {
        "tool": SCENE_PARSING_TOOL_CONTRACT,
        "input_schema": SceneParseRequest.model_json_schema(),
        "output_schema": SceneSpec.model_json_schema(),
    }
