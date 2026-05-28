from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from visionspace_asset_foundry.scene_parser import parse_scene
from visionspace_asset_foundry.schemas import AssetType, SceneDraftSpec

DEFAULT_OPENAI_SCENE_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 900
VALID_ASSET_TYPES = {asset_type.value for asset_type in AssetType}
ASSET_TYPE_ALIASES = {
    "amr": "agv",
    "agv": "agv",
    "robotarm": "robot_arm",
    "robot_arm": "robot_arm",
    "robot-arm": "robot_arm",
    "conveyor": "conveyor",
    "rack": "rack",
    "box": "pallet_box",
    "boxes": "pallet_box",
    "pallet_box": "pallet_box",
    "pallet-box": "pallet_box",
    "worker": "worker",
    "chargingstation": "charging_station",
    "charging_station": "charging_station",
    "charging-station": "charging_station",
    "safetyfence": "safety_fence",
    "safety_fence": "safety_fence",
    "safety-fence": "safety_fence",
    "unknown": "unknown",
}
VALID_SPACE_TYPES = {"factory", "warehouse", "workspace"}
VALID_SPACE_SHAPES = {"rectangle", "unknown", "rectangular"}


class SceneLLMError(RuntimeError):
    """Base error for LLM-backed scene parsing."""


class SceneLLMUnavailableError(SceneLLMError):
    """Raised when the OpenAI runtime is not configured."""


class SceneLLMResponseError(SceneLLMError):
    """Raised when the OpenAI runtime returns an unusable response."""


@dataclass(frozen=True)
class SceneLLMParseResult:
    draft: SceneDraftSpec
    provider: str
    model: str


SCENE_PARSER_INSTRUCTIONS = """You convert industrial simulation instructions into structured scene data.

Return only a schema-valid structured object.

Rules:
- Preserve the user's intent without adding unsupported industrial assets.
- Use only the provided asset type enum values.
- If an entity is mentioned but its exact type is unclear, use "unknown" and record a warning.
- Quantity must be an integer of at least 1 for each entity that appears.
- Do not invent quantities. If quantity is not explicit, default to 1.
- Exception: if the instruction explicitly uses words like "여러 대", "several", or "multiple" for AGV/AMR, use quantity 3 and record that as an assumption.
- Convert area expressions to square meters in area_m2 when possible.
- Use "rectangle" only when the instruction explicitly implies a rectangular space; otherwise use "unknown".
- Use "factory", "warehouse", or "workspace" for space.type.
- Use placement.pattern values like "grid", "line", "parallel_rows", "around_cell", or "unspecified".
- If placement details are missing, keep "unspecified" and record the ambiguity in assumptions or notes.
- Set global_constraints.collision_avoidance to true only when the instruction explicitly asks for collision avoidance or avoidance-priority behavior.
- Keep assumptions and warnings concise and operational for downstream planning.
"""


def openai_scene_model() -> str:
    return os.getenv("VSAF_SCENE_PARSER_OPENAI_MODEL", DEFAULT_OPENAI_SCENE_MODEL)


def openai_scene_base_url() -> str | None:
    base_url = os.getenv("VSAF_SCENE_PARSER_OPENAI_BASE_URL", "").strip()
    return base_url or None


def _scene_api_key(base_url: str | None) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    if base_url:
        return "EMPTY"
    raise SceneLLMUnavailableError("OPENAI_API_KEY is not set.")


def _build_openai_client(*, api_key: str, timeout_seconds: float, base_url: str | None):
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise SceneLLMUnavailableError("The `openai` package is not installed.") from exc

    return OpenAI(api_key=api_key, timeout=timeout_seconds, base_url=base_url)


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
                continue
            text = getattr(item, "text", None)
            if text:
                parts.append(str(text))
        return "\n".join(part for part in parts if part)
    return ""


def _normalize_json_text(content: str) -> str:
    normalized = content.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()
    return normalized


def _coerce_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_coerce_text_list(item))
        return items
    text = str(value).strip()
    return [text] if text else []


def _dedupe_texts(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _coerce_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _canonical_asset_type(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = ASSET_TYPE_ALIASES.get(normalized, normalized)
    if normalized in VALID_ASSET_TYPES:
        return normalized
    return None


def _fallback_draft_payload(user_instruction: str) -> dict[str, Any]:
    fallback_spec = parse_scene(user_instruction)
    entities: list[dict[str, Any]] = []
    for entity in fallback_spec.entities:
        entities.append(
            {
                "type": entity.type.value,
                "quantity": entity.quantity,
                "placement": entity.placement.model_dump(mode="json"),
                "properties": {
                    "mode": entity.properties.get("mode"),
                    "priority_quantity": entity.properties.get("priority_quantity"),
                    "speed_profile": entity.properties.get("speed_profile"),
                    "notes": _coerce_text_list(entity.properties.get("notes")),
                },
            }
        )

    return {
        "source_text": user_instruction,
        "space": fallback_spec.space.model_dump(mode="json"),
        "entities": entities,
        "global_constraints": dict(fallback_spec.global_constraints),
        "assumptions": list(fallback_spec.assumptions),
        "warnings": list(fallback_spec.warnings),
    }


def _match_entity(entities: list[dict[str, Any]], entity_type: str | None) -> dict[str, Any] | None:
    if entity_type:
        for entity in entities:
            if entity.get("type") == entity_type:
                return entity
    return None


def _clean_entity(entity: dict[str, Any]) -> dict[str, Any]:
    placement = _coerce_dict(entity.get("placement"))
    properties = _coerce_dict(entity.get("properties"))
    cleaned: dict[str, Any] = {
        "type": _canonical_asset_type(entity.get("type")) or "unknown",
        "quantity": max(1, _coerce_int(entity.get("quantity")) or 1),
        "placement": {
            "pattern": str(placement.get("pattern") or "unspecified"),
            "zone": placement.get("zone") if isinstance(placement.get("zone"), str) else None,
            "near": placement.get("near") if isinstance(placement.get("near"), str) else None,
            "notes": _dedupe_texts(_coerce_text_list(placement.get("notes"))),
        },
        "properties": {
            "mode": properties.get("mode") if isinstance(properties.get("mode"), str) else None,
            "priority_quantity": _coerce_int(properties.get("priority_quantity")),
            "speed_profile": properties.get("speed_profile") if isinstance(properties.get("speed_profile"), str) else None,
            "notes": _dedupe_texts(_coerce_text_list(properties.get("notes"))),
        },
    }
    return cleaned


def _normalize_vllm_payload(payload: dict[str, Any], user_instruction: str) -> dict[str, Any]:
    normalized = _fallback_draft_payload(user_instruction)
    base_payload = payload
    if (
        isinstance(payload.get("scene"), dict)
        and "source_text" not in payload
        and "space" not in payload
        and "entities" not in payload
    ):
        base_payload = payload["scene"]

    normalized["source_text"] = str(base_payload.get("source_text") or user_instruction)

    space_payload = _coerce_dict(base_payload.get("space"))
    space = _coerce_dict(normalized.get("space"))
    space_type = str(space_payload.get("type") or "").strip().lower()
    if space_type in VALID_SPACE_TYPES:
        space["type"] = space_type
    shape = str(space_payload.get("shape") or "").strip().lower()
    if shape == "rectangular":
        shape = "rectangle"
    if shape in VALID_SPACE_SHAPES:
        space["shape"] = shape
    area_m2 = _coerce_float(space_payload.get("area_m2"))
    if area_m2 is not None:
        space["area_m2"] = area_m2
    area_source = None
    if isinstance(space_payload.get("area_source"), str):
        area_source = space_payload["area_source"].strip()
    elif _coerce_text_list(space_payload.get("notes")):
        area_source = _coerce_text_list(space_payload.get("notes"))[0]
    if area_source:
        space["area_source"] = area_source
    normalized["space"] = space

    assumptions = _dedupe_texts(
        list(normalized.get("assumptions", []))
        + _coerce_text_list(base_payload.get("assumptions"))
        + _coerce_text_list(base_payload.get("notes"))
    )
    warnings = _dedupe_texts(
        list(normalized.get("warnings", []))
        + _coerce_text_list(base_payload.get("warnings"))
    )

    global_constraints = _coerce_dict(normalized.get("global_constraints"))
    top_level_constraints = _coerce_dict(base_payload.get("global_constraints"))
    collision_avoidance = _coerce_bool(top_level_constraints.get("collision_avoidance"))
    if collision_avoidance is not None:
        global_constraints["collision_avoidance"] = collision_avoidance

    entities = [
        _clean_entity(entity)
        for entity in list(normalized.get("entities", []))
        if isinstance(entity, dict)
    ]
    raw_entities = base_payload.get("entities")
    if isinstance(raw_entities, list):
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, dict):
                continue
            entity_type = _canonical_asset_type(raw_entity.get("type"))
            target = _match_entity(entities, entity_type)
            if target is None:
                target = _clean_entity({"type": entity_type or "unknown"})
                entities.append(target)

            if entity_type:
                target["type"] = entity_type
            quantity = _coerce_int(raw_entity.get("quantity"))
            if quantity is not None and quantity >= 1:
                target["quantity"] = quantity

            placement_payload = _coerce_dict(raw_entity.get("placement"))
            target_placement = _coerce_dict(target.get("placement"))
            pattern = placement_payload.get("pattern")
            if isinstance(pattern, str) and pattern.strip():
                target_placement["pattern"] = pattern.strip()
            for field in ("zone", "near"):
                value = placement_payload.get(field)
                if isinstance(value, str) and value.strip():
                    target_placement[field] = value.strip()
            target_placement["notes"] = _dedupe_texts(
                _coerce_text_list(target_placement.get("notes"))
                + _coerce_text_list(placement_payload.get("notes"))
            )
            target["placement"] = target_placement

            properties_payload = _coerce_dict(raw_entity.get("properties"))
            target_properties = _coerce_dict(target.get("properties"))
            mode = properties_payload.get("mode")
            if isinstance(mode, str) and mode.strip():
                target_properties["mode"] = mode.strip()
            priority_quantity = _coerce_int(properties_payload.get("priority_quantity"))
            if priority_quantity is not None and priority_quantity >= 1:
                target_properties["priority_quantity"] = priority_quantity
            speed_profile = properties_payload.get("speed_profile")
            if isinstance(speed_profile, str) and speed_profile.strip():
                target_properties["speed_profile"] = speed_profile.strip()
            target_properties["notes"] = _dedupe_texts(
                _coerce_text_list(target_properties.get("notes"))
                + _coerce_text_list(properties_payload.get("notes"))
                + _coerce_text_list(raw_entity.get("notes"))
            )
            target["properties"] = target_properties

            entity_constraints = _coerce_dict(raw_entity.get("global_constraints"))
            entity_collision_avoidance = _coerce_bool(entity_constraints.get("collision_avoidance"))
            if entity_collision_avoidance is not None and "collision_avoidance" not in global_constraints:
                global_constraints["collision_avoidance"] = entity_collision_avoidance

            assumptions = _dedupe_texts(assumptions + _coerce_text_list(raw_entity.get("assumptions")))

    cleaned_entities = [_clean_entity(entity) for entity in entities]
    has_known_entity = any(entity.get("type") != "unknown" for entity in cleaned_entities)
    if has_known_entity:
        filtered_entities: list[dict[str, Any]] = []
        for entity in cleaned_entities:
            if entity.get("type") != "unknown":
                filtered_entities.append(entity)
                continue
            placement = _coerce_dict(entity.get("placement"))
            properties = _coerce_dict(entity.get("properties"))
            has_specific_location = bool(placement.get("zone") or placement.get("near"))
            has_specific_properties = any(
                properties.get(key) not in (None, "", [], {})
                for key in ("mode", "priority_quantity", "speed_profile")
            )
            if has_specific_location or has_specific_properties:
                filtered_entities.append(entity)
        cleaned_entities = filtered_entities or cleaned_entities

    normalized["entities"] = cleaned_entities
    normalized["global_constraints"] = global_constraints
    normalized["assumptions"] = assumptions
    normalized["warnings"] = warnings
    return normalized


def _parse_scene_with_openai_responses(
    *,
    client,
    model: str,
    user_instruction: str,
    max_output_tokens: int,
) -> SceneLLMParseResult:
    try:
        response = client.responses.parse(
            model=model,
            instructions=SCENE_PARSER_INSTRUCTIONS,
            input=user_instruction,
            text_format=SceneDraftSpec,
            temperature=0,
            max_output_tokens=max_output_tokens,
            store=False,
        )
    except Exception as exc:  # pragma: no cover - SDK/network behavior
        raise SceneLLMResponseError(str(exc)) from exc

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        refusal = getattr(response, "refusal", None)
        if refusal:
            raise SceneLLMResponseError(f"OpenAI refused the request: {refusal}")
        output_text = getattr(response, "output_text", None)
        if output_text:
            raise SceneLLMResponseError(f"OpenAI returned unparsed output: {output_text}")
        raise SceneLLMResponseError("OpenAI did not return parsed structured output.")

    draft = parsed.model_copy(deep=True)
    if not draft.source_text:
        draft.source_text = user_instruction

    return SceneLLMParseResult(
        draft=draft,
        provider="openai",
        model=model,
    )


def _parse_scene_with_vllm(
    *,
    client,
    model: str,
    user_instruction: str,
    max_output_tokens: int,
) -> SceneLLMParseResult:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SCENE_PARSER_INSTRUCTIONS},
                {"role": "user", "content": user_instruction},
            ],
            temperature=0,
            max_tokens=max_output_tokens,
            extra_body={
                "guided_json": SceneDraftSpec.model_json_schema(),
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
    except Exception as exc:  # pragma: no cover - SDK/network behavior
        raise SceneLLMResponseError(str(exc)) from exc

    try:
        choice = response.choices[0]
    except (AttributeError, IndexError) as exc:
        raise SceneLLMResponseError("vLLM did not return any completion choices.") from exc

    message = getattr(choice, "message", None)
    content = _message_text(getattr(message, "content", None))
    if not content:
        raise SceneLLMResponseError("vLLM returned an empty completion message.")

    normalized_content = _normalize_json_text(content)
    try:
        payload = json.loads(normalized_content)
    except json.JSONDecodeError as exc:
        raise SceneLLMResponseError(f"vLLM returned non-JSON output: {normalized_content}") from exc

    try:
        draft = SceneDraftSpec.model_validate(payload)
    except Exception:
        normalized_payload = _normalize_vllm_payload(_coerce_dict(payload), user_instruction)
        try:
            draft = SceneDraftSpec.model_validate(normalized_payload)
        except Exception as exc:
            raise SceneLLMResponseError(f"vLLM returned schema-invalid JSON: {exc}") from exc

    if not draft.source_text:
        draft.source_text = user_instruction

    return SceneLLMParseResult(
        draft=draft,
        provider="vllm",
        model=model,
    )


def parse_scene_with_openai(user_instruction: str) -> SceneLLMParseResult:
    base_url = openai_scene_base_url()
    timeout_seconds = float(
        os.getenv("VSAF_SCENE_PARSER_OPENAI_TIMEOUT_SECONDS", str(DEFAULT_OPENAI_TIMEOUT_SECONDS))
    )
    max_output_tokens = int(
        os.getenv("VSAF_SCENE_PARSER_OPENAI_MAX_OUTPUT_TOKENS", str(DEFAULT_OPENAI_MAX_OUTPUT_TOKENS))
    )
    model = openai_scene_model()
    client = _build_openai_client(
        api_key=_scene_api_key(base_url),
        timeout_seconds=timeout_seconds,
        base_url=base_url,
    )

    if base_url:
        return _parse_scene_with_vllm(
            client=client,
            model=model,
            user_instruction=user_instruction,
            max_output_tokens=max_output_tokens,
        )

    return _parse_scene_with_openai_responses(
        client=client,
        model=model,
        user_instruction=user_instruction,
        max_output_tokens=max_output_tokens,
    )
