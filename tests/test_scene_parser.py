from __future__ import annotations

import json
from pathlib import Path

import pytest

import visionspace_asset_foundry.scene_llm as scene_llm
from visionspace_asset_foundry.scene_llm import SceneLLMParseResult, SceneLLMUnavailableError
from visionspace_asset_foundry.scene_interpreter import interpret_scene, scene_tool_schema
from visionspace_asset_foundry.scene_parser import parse_scene
from visionspace_asset_foundry.schemas import (
    AssetType,
    DraftEntityPropertiesSpec,
    DraftEntitySpec,
    DraftGlobalConstraintsSpec,
    PlacementSpec,
    SceneDraftSpec,
    SpaceSpec,
)


def _entity_types(text: str) -> set[AssetType]:
    return {entity.type for entity in parse_scene(text).entities}


def test_agv_grid_case() -> None:
    spec = parse_scene("AGV 6대를 700평 직사각형 공장에 격자 배치하고, 출입구 근처 2대는 회피 우선 모드로 설정해줘")
    assert spec.space.type == "factory"
    assert spec.space.shape == "rectangle"
    assert spec.space.area_m2 == 2314.05
    agv = next(entity for entity in spec.entities if entity.type == AssetType.agv)
    assert agv.quantity == 6
    assert agv.placement.pattern == "grid"
    assert agv.placement.near == "entrance"
    assert agv.properties["mode"] == "avoidance_priority"
    assert agv.properties["priority_quantity"] == 2


def test_conveyor_rack_case() -> None:
    spec = parse_scene("1200제곱미터 창고에 컨베이어 3개를 중앙 라인으로 배치하고 양쪽에 랙 12개를 놓아줘")
    assert spec.space.area_m2 == 1200
    assert any(entity.type == AssetType.conveyor and entity.quantity == 3 for entity in spec.entities)
    assert any(entity.type == AssetType.rack and entity.quantity == 12 for entity in spec.entities)
    conveyor = next(entity for entity in spec.entities if entity.type == AssetType.conveyor)
    rack = next(entity for entity in spec.entities if entity.type == AssetType.rack)
    assert conveyor.placement.pattern == "line"
    assert conveyor.placement.zone == "center"
    assert rack.placement.pattern == "parallel_rows"
    assert rack.placement.zone == "both_sides"


def test_robot_arm_worker_case() -> None:
    spec = parse_scene("로봇팔 4대를 조립 셀 주변에 배치하고 작업자 2명은 안전 구역 밖에 위치시켜줘")
    assert spec.space.type == "workspace"
    assert _entity_types(spec.source_text) == {AssetType.robot_arm, AssetType.worker}
    worker = next(entity for entity in spec.entities if entity.type == AssetType.worker)
    assert worker.quantity == 2
    assert worker.placement.zone == "outside_safety_zone"


def test_safety_fence_and_pallet_box_case() -> None:
    spec = parse_scene("창고에 AGV 2대와 로봇팔 1대를 배치하고 안전펜스와 박스 5개를 추가해줘")
    assert any(entity.type == AssetType.safety_fence and entity.quantity == 1 for entity in spec.entities)
    assert any(entity.type == AssetType.pallet_box and entity.quantity == 5 for entity in spec.entities)


def test_mixed_english_case() -> None:
    spec = parse_scene(
        "AMR 8 units, conveyor 2 units, and 1 charging station in a rectangular 900 m2 warehouse. "
        "Prioritize collision avoidance near the entrance."
    )
    assert spec.space.shape == "rectangle"
    assert spec.space.area_m2 == 900
    assert _entity_types(spec.source_text) == {
        AssetType.agv,
        AssetType.conveyor,
        AssetType.charging_station,
    }
    assert spec.global_constraints["collision_avoidance"] is True


def test_ambiguous_case_records_defaults() -> None:
    spec = parse_scene("작은 물류센터에 AGV 여러 대와 랙을 적당히 배치해줘. 속도는 낮게 설정해줘")
    agv = next(entity for entity in spec.entities if entity.type == AssetType.agv)
    rack = next(entity for entity in spec.entities if entity.type == AssetType.rack)
    assert agv.quantity == 3
    assert rack.quantity == 1
    assert agv.properties["speed_profile"] == "low"
    assert "speed_profile" not in rack.properties
    assert len(spec.assumptions) >= 4


def test_all_declared_scene_cases_validate() -> None:
    path = Path("data/scene_cases/text_to_scene_cases.json")
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) == 5
    for case in cases:
        spec = parse_scene(case["input"])
        assert spec.source_text == case["input"]
        assert spec.entities
        assert spec.model_dump(mode="json")


def test_interpreter_enriches_scene_with_tool_contract_graph_and_handoff() -> None:
    spec = interpret_scene(
        "AGV 6대를 700평 직사각형 공장에 격자 배치하고, 출입구 근처 2대는 회피 우선 모드로 설정해줘",
        strategy="deterministic_tool",
    )
    assert spec.tool_call.name == "parse_scene_to_scene_spec"
    assert spec.tool_call.validation == "passed"
    assert spec.tool_call.executor == "deterministic_rule_parser"
    assert any(node.id == "space:main" for node in spec.scene_graph.nodes)
    assert any(edge.relation == "placed_in" for edge in spec.scene_graph.edges)
    assert any(task.name == "asset_resolution" and task.status == "ready" for task in spec.downstream_tasks)
    assert any(task.name == "simulation_export" for task in spec.downstream_tasks)


def test_scene_llm_normalizes_vllm_wrapper_payload() -> None:
    payload = {
        "scene": {
            "space": {
                "type": "factory",
                "shape": "rectangle",
                "area_m2": 2312.5,
                "notes": "Converted 700 pyeong to square meters (1 pyeong ≈ 3.3058 m²).",
            },
            "entities": [
                {
                    "type": "AGV",
                    "quantity": 6,
                    "placement": {
                        "pattern": "grid",
                        "notes": "Grid placement specified for all 6 AGVs.",
                    },
                    "global_constraints": {"collision_avoidance": False},
                    "assumptions": [
                        "Specific behavior for 2 AGVs near the entrance was recorded as a local constraint."
                    ],
                }
            ],
            "notes": [
                "2 AGVs are specified to be near the entrance with avoidance priority mode."
            ],
        }
    }

    normalized = scene_llm._normalize_vllm_payload(
        payload,
        "700평 직사각형 공장에 AGV 6대를 격자 배치하고 출입구 근처 2대는 회피 우선 모드로 해줘",
    )
    draft = SceneDraftSpec.model_validate(normalized)
    agv = draft.entities[0]

    assert draft.source_text == "700평 직사각형 공장에 AGV 6대를 격자 배치하고 출입구 근처 2대는 회피 우선 모드로 해줘"
    assert draft.space.area_m2 == 2312.5
    assert draft.space.area_source == "Converted 700 pyeong to square meters (1 pyeong ≈ 3.3058 m²)."
    assert agv.type == AssetType.agv
    assert agv.placement.pattern == "grid"
    assert agv.placement.near == "entrance"
    assert agv.properties.mode == "avoidance_priority"
    assert agv.properties.priority_quantity == 2


def test_scene_llm_filters_spurious_unknown_entities_from_vllm_payload() -> None:
    payload = {
        "scene": {
            "entities": [
                {"type": "AGV", "quantity": 2},
                {"type": "unknown", "quantity": 1},
            ]
        }
    }

    normalized = scene_llm._normalize_vllm_payload(payload, "AGV 2대를 배치해줘")

    assert [entity["type"] for entity in normalized["entities"]] == ["agv"]


def test_scene_llm_routes_to_vllm_when_base_url_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    draft = SceneDraftSpec(
        source_text="창고에 AGV 2대와 로봇팔 1대를 배치해줘",
        space=SpaceSpec(type="warehouse", shape="unknown"),
        entities=[
            DraftEntitySpec(
                type=AssetType.agv,
                quantity=2,
                placement=PlacementSpec(pattern="line", near="entrance"),
                properties=DraftEntityPropertiesSpec(mode="avoidance_priority", priority_quantity=1),
            )
        ],
        global_constraints=DraftGlobalConstraintsSpec(collision_avoidance=True),
        assumptions=["Space area missing."],
        warnings=[],
    )
    client = object()
    captured: dict[str, object] = {}

    monkeypatch.setenv("VSAF_SCENE_PARSER_OPENAI_BASE_URL", "http://127.0.0.1:8003/v1")
    monkeypatch.setenv("VSAF_SCENE_PARSER_OPENAI_MODEL", "local-main")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def _fake_build_openai_client(*, api_key: str, timeout_seconds: float, base_url: str | None):
        captured["client_args"] = {
            "api_key": api_key,
            "timeout_seconds": timeout_seconds,
            "base_url": base_url,
        }
        return client

    def _fake_parse_scene_with_vllm(*, client: object, model: str, user_instruction: str, max_output_tokens: int) -> SceneLLMParseResult:
        captured["parse_args"] = {
            "client": client,
            "model": model,
            "user_instruction": user_instruction,
            "max_output_tokens": max_output_tokens,
        }
        return SceneLLMParseResult(
            draft=draft.model_copy(update={"source_text": user_instruction}),
            provider="vllm",
            model=model,
        )

    monkeypatch.setattr(scene_llm, "_build_openai_client", _fake_build_openai_client)
    monkeypatch.setattr(scene_llm, "_parse_scene_with_vllm", _fake_parse_scene_with_vllm)

    result = scene_llm.parse_scene_with_openai("창고에 AGV 2대와 로봇팔 1대를 배치해줘")

    assert result.provider == "vllm"
    assert result.model == "local-main"
    assert captured["client_args"] == {
        "api_key": "EMPTY",
        "timeout_seconds": 30.0,
        "base_url": "http://127.0.0.1:8003/v1",
    }
    assert captured["parse_args"] == {
        "client": client,
        "model": "local-main",
        "user_instruction": "창고에 AGV 2대와 로봇팔 1대를 배치해줘",
        "max_output_tokens": 900,
    }


def test_llm_strategy_uses_openai_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    draft = SceneDraftSpec(
        source_text="창고에 AGV 2대와 로봇팔 1대를 배치해줘",
        space=SpaceSpec(type="warehouse", shape="unknown"),
        entities=[
            DraftEntitySpec(
                type=AssetType.agv,
                quantity=2,
                placement=PlacementSpec(pattern="line", near="entrance"),
                properties=DraftEntityPropertiesSpec(mode="avoidance_priority", priority_quantity=1),
            ),
            DraftEntitySpec(
                type=AssetType.robot_arm,
                quantity=1,
                placement=PlacementSpec(pattern="around_cell"),
            ),
        ],
        global_constraints=DraftGlobalConstraintsSpec(collision_avoidance=True),
        assumptions=["Space area missing."],
        warnings=[],
    )

    monkeypatch.setattr(
        "visionspace_asset_foundry.scene_interpreter.parse_scene_with_openai",
        lambda user_instruction: SceneLLMParseResult(
            draft=draft.model_copy(update={"source_text": user_instruction}),
            provider="openai",
            model="gpt-5.4-mini",
        ),
    )

    spec = interpret_scene("창고에 AGV 2대와 로봇팔 1대를 배치해줘", strategy="llm_structured_output")

    assert spec.tool_call.provider == "openai"
    assert spec.tool_call.model == "gpt-5.4-mini"
    assert spec.tool_call.executor == "openai_structured_output"
    assert spec.tool_call.fallback_used is False
    assert spec.global_constraints["collision_avoidance"] is True
    assert spec.required_asset_types == [AssetType.agv, AssetType.robot_arm]


def test_llm_strategy_surfaces_vllm_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    draft = SceneDraftSpec(
        source_text="창고에 컨베이어 3개를 중앙 라인으로 배치해줘",
        space=SpaceSpec(type="warehouse", shape="rectangle", area_m2=900),
        entities=[
            DraftEntitySpec(
                type=AssetType.conveyor,
                quantity=3,
                placement=PlacementSpec(pattern="line", zone="center"),
            )
        ],
        global_constraints=DraftGlobalConstraintsSpec(collision_avoidance=False),
        assumptions=[],
        warnings=[],
    )

    monkeypatch.setattr(
        "visionspace_asset_foundry.scene_interpreter.parse_scene_with_openai",
        lambda user_instruction: SceneLLMParseResult(
            draft=draft.model_copy(update={"source_text": user_instruction}),
            provider="vllm",
            model="local-main",
        ),
    )

    spec = interpret_scene("창고에 컨베이어 3개를 중앙 라인으로 배치해줘", strategy="llm_structured_output")

    assert spec.tool_call.provider == "vllm"
    assert spec.tool_call.model == "local-main"
    assert spec.tool_call.executor == "vllm_guided_json"
    assert spec.tool_call.fallback_used is False


def test_hybrid_strategy_falls_back_to_rule_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_: str) -> SceneLLMParseResult:
        raise SceneLLMUnavailableError("OPENAI_API_KEY is not set.")

    monkeypatch.setattr("visionspace_asset_foundry.scene_interpreter.parse_scene_with_openai", _raise)

    spec = interpret_scene("AGV 3대를 공장에 배치해줘", strategy="hybrid_fallback")

    assert spec.tool_call.executor == "deterministic_rule_parser"
    assert spec.tool_call.fallback_used is True
    assert any("Fallback reason:" in note for note in spec.tool_call.notes)
    assert any(entity.type == AssetType.agv and entity.quantity == 3 for entity in spec.entities)


def test_scene_tool_schema_exposes_function_contract() -> None:
    schema = scene_tool_schema()
    assert schema["tool"]["type"] == "function"
    assert schema["tool"]["function"]["name"] == "parse_scene_to_scene_spec"
    assert "user_instruction" in schema["input_schema"]["properties"]
    assert "properties" in schema["output_schema"]
