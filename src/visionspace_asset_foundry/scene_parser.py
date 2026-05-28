from __future__ import annotations

import re
from collections import OrderedDict

from visionspace_asset_foundry.schemas import (
    AssetType,
    EntitySpec,
    PlacementSpec,
    SceneSpec,
    SpaceSpec,
)

AREA_PYEONG_TO_M2 = 3.305785

ENTITY_ALIASES: dict[AssetType, list[str]] = {
    AssetType.agv: ["agv", "amr", "AGV", "AMR", "무인운반차", "이동로봇"],
    AssetType.robot_arm: ["로봇팔", "robot arm", "robot_arm", "cobot", "협동로봇"],
    AssetType.conveyor: ["컨베이어", "conveyor", "conveyors"],
    AssetType.rack: ["랙", "rack", "racks", "선반"],
    AssetType.pallet_box: ["팔레트", "박스", "상자", "pallet", "pallet box", "box", "boxes"],
    AssetType.worker: ["작업자", "worker", "workers", "사람"],
    AssetType.charging_station: ["충전기", "충전 스테이션", "charging station", "charging dock"],
    AssetType.safety_fence: ["안전펜스", "안전 펜스", "펜스", "울타리", "safety fence", "safety_fence", "fence"],
}


def _parse_area(text: str) -> tuple[float | None, str | None]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(평|제곱미터|m2|㎡|square meters?)", text, re.IGNORECASE)
    if not match:
        return None, None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "평":
        return round(value * AREA_PYEONG_TO_M2, 2), f"{value:g}평"
    return value, f"{value:g} m2"


def _parse_space(text: str) -> SpaceSpec:
    area_m2, area_source = _parse_area(text)
    lower = text.lower()
    shape = "rectangle" if any(token in lower for token in ["직사각형", "rectangular", "rectangle"]) else "unknown"
    if "공장" in text or "factory" in lower:
        space_type = "factory"
    elif "셀" in text or "workspace" in lower or "workcell" in lower:
        space_type = "workspace"
    else:
        space_type = "warehouse"
    return SpaceSpec(type=space_type, shape=shape, area_m2=area_m2, area_source=area_source)


def _count_near_alias(text: str, alias: str) -> int | None:
    escaped = re.escape(alias)
    patterns = [
        rf"(\d+)\s*(?:대|개|명|units?|ea)?\s*(?:의\s*)?{escaped}",
        rf"{escaped}\s*(\d+)\s*(?:대|개|명|units?|ea)?",
        rf"{escaped}\s*(?:은|는|을|를|이|가|총|each)?\s*(\d+)\s*(?:대|개|명|units?|ea)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _placement_for(text: str, asset_type: AssetType) -> PlacementSpec:
    lower = text.lower()
    notes: list[str] = []
    pattern = "unspecified"
    zone = None
    near = None
    if asset_type == AssetType.rack and ("양쪽" in text or "both sides" in lower):
        pattern = "parallel_rows"
        zone = "both_sides"
    elif asset_type == AssetType.conveyor and ("중앙" in text or "central" in lower):
        pattern = "line"
        zone = "center"
    elif "격자" in text or "grid" in lower:
        pattern = "grid"
    elif "중앙" in text or "central" in lower:
        pattern = "line"
        zone = "center"
    elif "주변" in text or "around" in lower:
        pattern = "around_cell"

    if "출입구" in text or "entrance" in lower:
        near = "entrance"
    if asset_type == AssetType.worker and ("안전 구역 밖" in text or "outside safety" in lower):
        zone = "outside_safety_zone"
    if pattern == "unspecified":
        notes.append("Placement pattern was not explicit; default placement is required downstream.")
    return PlacementSpec(pattern=pattern, zone=zone, near=near, notes=notes)


def _properties_for(text: str, asset_type: AssetType, quantity: int) -> dict[str, object]:
    lower = text.lower()
    props: dict[str, object] = {}
    if asset_type == AssetType.agv and (
        "회피 우선" in text or "collision avoidance" in lower or "avoidance" in lower
    ):
        props["mode"] = "avoidance_priority"
        if asset_type == AssetType.agv:
            priority_count = re.search(r"(?:근처\s*)?(\d+)\s*대는\s*회피 우선", text)
            props["priority_quantity"] = int(priority_count.group(1)) if priority_count else min(2, quantity)
    if asset_type in {AssetType.agv, AssetType.conveyor} and ("속도는 낮게" in text or "low speed" in lower):
        props["speed_profile"] = "low"
    return props


def parse_scene(text: str) -> SceneSpec:
    entities_by_type: "OrderedDict[AssetType, EntitySpec]" = OrderedDict()
    assumptions: list[str] = []
    warnings: list[str] = []

    for asset_type, aliases in ENTITY_ALIASES.items():
        found_alias = next((alias for alias in aliases if re.search(re.escape(alias), text, re.IGNORECASE)), None)
        if not found_alias:
            continue
        quantity = None
        for alias in aliases:
            quantity = _count_near_alias(text, alias)
            if quantity is not None:
                break
        if quantity is None:
            quantity = 3 if asset_type == AssetType.agv and "여러" in text else 1
            assumptions.append(f"{asset_type.value} quantity defaulted to {quantity}.")

        entities_by_type[asset_type] = EntitySpec(
            type=asset_type,
            quantity=quantity,
            placement=_placement_for(text, asset_type),
            properties=_properties_for(text, asset_type, quantity),
        )

    if not entities_by_type:
        warnings.append("No known industrial entity type was detected.")

    space = _parse_space(text)
    if space.area_m2 is None:
        assumptions.append("Space area was not specified; downstream layout should request confirmation.")
    if space.shape == "unknown":
        assumptions.append("Space shape was not specified; rectangular layout is the recommended default.")

    required_asset_types = list(entities_by_type.keys())
    return SceneSpec(
        source_text=text,
        space=space,
        entities=list(entities_by_type.values()),
        global_constraints={
            "collision_avoidance": any(
                entity.properties.get("mode") == "avoidance_priority"
                for entity in entities_by_type.values()
            )
        },
        required_asset_types=required_asset_types,
        assumptions=assumptions,
        warnings=warnings,
    )
