"""Parse hidden structured UI results from POPAgent answers."""

from __future__ import annotations

import json
import re
from typing import Any


_RESULTS_FENCE_RE = re.compile(
    r"(?ms)^```[ \t]*popagent-results[ \t]*\r?\n(.*?)\r?\n```[ \t]*$"
)


def split_structured_results(answer: str) -> tuple[str, str]:
    """Return visible answer text and normalized object-results JSON."""
    objects = []

    def replace_match(match: re.Match) -> str:
        nonlocal objects
        raw_json = match.group(1)
        parsed_objects = _parse_objects(raw_json)
        if parsed_objects is None:
            return ""
        objects.extend(parsed_objects)
        return ""

    visible_answer = _RESULTS_FENCE_RE.sub(replace_match, answer or "").strip()
    if not objects:
        return visible_answer, ""
    payload = {"version": 1, "objects": objects}
    return visible_answer, json.dumps(payload, ensure_ascii=False)


def normalize_object_results_payload(data: Any) -> list[dict]:
    if not isinstance(data, dict) or data.get("version") != 1:
        return []
    raw_objects = data.get("objects")
    if not isinstance(raw_objects, list):
        return []
    objects = []
    for item in raw_objects:
        obj = _normalize_object(item)
        if obj:
            objects.append(obj)
    return objects


def object_results_to_json(objects: list[dict]) -> str:
    normalized = []
    seen = set()
    for item in objects:
        obj = _normalize_object(item)
        name = obj.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(obj)
    if not normalized:
        return ""
    return json.dumps({"version": 1, "objects": normalized}, ensure_ascii=False)


def merge_object_results_json(primary: str, fallback: str) -> str:
    objects = []
    for raw_json in (primary, fallback):
        if not raw_json:
            continue
        try:
            data = json.loads(raw_json)
        except (TypeError, json.JSONDecodeError):
            continue
        objects.extend(normalize_object_results_payload(data))
    return object_results_to_json(objects)


def object_result_status(
    result: dict,
    object_names,
    view_layer_object_names=None,
    unselectable_names=None,
) -> str:
    name = str(result.get("name") or "")
    if not name or name not in set(object_names):
        return "MISSING"
    if view_layer_object_names is not None and name not in set(view_layer_object_names):
        return "OUT_OF_VIEW_LAYER"
    if unselectable_names is not None and name in set(unselectable_names):
        return "UNSELECTABLE"
    return "FOUND"


def _parse_objects(raw_json: str) -> list[dict] | None:
    try:
        data = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return None
    objects = normalize_object_results_payload(data)
    if not objects:
        return None
    return objects


def _normalize_object(item: Any) -> dict:
    if not isinstance(item, dict):
        return {}
    object_name = item.get("object_name")
    name = object_name if isinstance(object_name, str) and object_name.strip() else item.get("name")
    if not isinstance(name, str) or not name.strip():
        return {}

    obj = {"name": name.strip()}
    if isinstance(object_name, str) and object_name.strip():
        obj["object_name"] = object_name.strip()

    mesh_data_name = item.get("mesh_data_name")
    if isinstance(mesh_data_name, str) and mesh_data_name.strip():
        obj["mesh_data_name"] = mesh_data_name.strip()

    obj_type = item.get("type")
    if isinstance(obj_type, str) and obj_type.strip():
        obj["type"] = obj_type.strip()

    location = _normalize_location(item.get("location"))
    if location is not None:
        obj["location"] = location

    note = item.get("note")
    if isinstance(note, str) and note.strip():
        obj["note"] = note.strip()
    return obj


def _normalize_location(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 3:
        return None
    location = []
    for item in value:
        if not isinstance(item, (int, float)):
            return None
        location.append(round(float(item), 3))
    return location
