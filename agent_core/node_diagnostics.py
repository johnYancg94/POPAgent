"""Pure helpers for diagnosing Blender material and geometry node snapshots."""

from __future__ import annotations

from typing import Any


_PBR_CHANNELS = {
    "base_color": {
        "input_names": {"base color", "basecolor", "color", "albedo"},
        "tokens": {"basecolor", "base_color", "albedo", "diffuse", "color", "col"},
    },
    "roughness": {
        "input_names": {"roughness", "rough"},
        "tokens": {"roughness", "rough"},
    },
    "metallic": {
        "input_names": {"metallic", "metalness", "metal"},
        "tokens": {"metallic", "metalness", "metal"},
    },
    "normal": {
        "input_names": {"normal"},
        "tokens": {"normal", "nrm", "norm"},
    },
    "alpha": {
        "input_names": {"alpha"},
        "tokens": {"alpha", "opacity", "transparent"},
    },
}


_PBR_CHANNEL_ALIASES = {
    token: channel
    for channel, spec in _PBR_CHANNELS.items()
    for token in spec["tokens"] | spec["input_names"] | {channel}
}


def _issue(kind: str, message: str, **context) -> dict:
    data = {"kind": kind, "message": message}
    data.update({k: v for k, v in context.items() if v is not None})
    return data


def _report(issues: list[dict]) -> dict:
    return {
        "ok": len(issues) == 0,
        "issue_count": len(issues),
        "issues": issues,
    }


def _normalize(value: str | None) -> str:
    return (value or "").lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def _tokens(value: str | None) -> set[str]:
    return {token for token in _normalize(value).split("_") if token}


def _node_map(nodes: list[dict]) -> dict[str, dict]:
    return {node.get("name", ""): node for node in nodes}


def _find_principled_nodes(nodes: list[dict]) -> list[dict]:
    return [node for node in nodes if node.get("type") == "BSDF_PRINCIPLED"]


def _link_targets_channel(link: dict, nodes_by_name: dict[str, dict] | None = None) -> str | None:
    socket_name = _normalize(link.get("to_socket"))
    target_node = (nodes_by_name or {}).get(link.get("to_node"), {})
    targets_principled = target_node.get("type") == "BSDF_PRINCIPLED"
    if not targets_principled and "bsdf" not in _normalize(link.get("to_node")):
        return None
    for channel, spec in _PBR_CHANNELS.items():
        normalized_inputs = {_normalize(name) for name in spec["input_names"]}
        if socket_name in normalized_inputs:
            return channel
    return None


def _texture_expected_channel(node: dict) -> str | None:
    image = node.get("image") or {}
    haystack_tokens = set()
    for value in (
        node.get("name"),
        node.get("label"),
        image.get("name"),
        image.get("filepath"),
    ):
        normalized = _normalize(value)
        if normalized:
            haystack_tokens.add(normalized)
            haystack_tokens.update(_tokens(normalized))
    for channel, spec in _PBR_CHANNELS.items():
        for token in spec["tokens"]:
            if _normalize(token) in haystack_tokens:
                return channel
    return None


def _canonical_pbr_channel(value: str) -> str | None:
    normalized = _normalize(value)
    if normalized in _PBR_CHANNELS:
        return normalized
    return _PBR_CHANNEL_ALIASES.get(normalized)


def _connected_pbr_channels(material: dict) -> dict[str, dict]:
    nodes = material.get("nodes", [])
    nodes_by_name = _node_map(nodes)
    surface_principled_names = _surface_principled_node_names(material)
    channels = {
        channel: {"connected": False, "source_node": None, "source_type": None}
        for channel in _PBR_CHANNELS
    }

    normal_map_inputs = {}
    for link in material.get("links", []):
        if _normalize(link.get("to_socket")) == "color":
            to_node = nodes_by_name.get(link.get("to_node"))
            if to_node and to_node.get("type") == "NORMAL_MAP":
                normal_map_inputs[link.get("to_node")] = link.get("from_node")

    for link in material.get("links", []):
        channel = _link_targets_channel(link, nodes_by_name)
        if channel is None:
            continue
        if surface_principled_names and link.get("to_node") not in surface_principled_names:
            continue
        from_node = nodes_by_name.get(link.get("from_node"), {})
        source_node = link.get("from_node")
        source_type = from_node.get("type")
        if channel == "normal" and from_node.get("type") == "NORMAL_MAP":
            source_node = normal_map_inputs.get(link.get("from_node"), source_node)
            source_type = nodes_by_name.get(source_node, {}).get("type")
        channels[channel] = {
            "connected": True,
            "source_node": source_node,
            "source_type": source_type,
        }
    return channels


def _has_surface_output_link(material: dict) -> bool:
    return bool(_surface_principled_node_names(material))


def _surface_principled_node_names(material: dict) -> set[str]:
    names = set()
    nodes_by_name = _node_map(material.get("nodes", []))
    for link in material.get("links", []):
        to_node = nodes_by_name.get(link.get("to_node"), {})
        from_node = nodes_by_name.get(link.get("from_node"), {})
        if (
            to_node.get("type") == "OUTPUT_MATERIAL"
            and _normalize(link.get("to_socket")) == "surface"
            and from_node.get("type") == "BSDF_PRINCIPLED"
        ):
            names.add(link.get("from_node"))
    return names


def _material_uses_transparency(material: dict) -> bool | None:
    blend_method = material.get("blend_method")
    if blend_method:
        return str(blend_method).upper() not in {"OPAQUE", "NONE"}
    surface_render_method = material.get("surface_render_method")
    if surface_render_method:
        return str(surface_render_method).upper() not in {"OPAQUE", "NONE"}
    return None


def _is_non_color_space(value: str | None) -> bool:
    normalized = _normalize(value)
    return normalized == "raw" or "non_color" in normalized


def analyze_material_snapshot(snapshot: dict[str, Any]) -> dict:
    materials = []
    for material in snapshot.get("materials", []):
        channels = _connected_pbr_channels(material)
        pbr_score = sum(
            1
            for channel in ("base_color", "roughness", "metallic", "normal")
            if channels.get(channel, {}).get("connected")
        )
        expected_textures = []
        for node in material.get("nodes", []):
            if node.get("type") != "TEX_IMAGE":
                continue
            expected = _texture_expected_channel(node)
            if expected:
                expected_textures.append({
                    "node": node.get("name"),
                    "expected_channel": expected,
                    "connected": bool(channels.get(expected, {}).get("connected")),
                })
        materials.append({
            "name": material.get("name"),
            "has_principled_bsdf": bool(_find_principled_nodes(material.get("nodes", []))),
            "has_surface_output_link": _has_surface_output_link(material),
            "uses_transparency": _material_uses_transparency(material),
            "pbr_score": pbr_score,
            "channels": channels,
            "expected_textures": expected_textures,
        })
    return {"materials": materials}


def plan_pbr_texture_paths(texture_paths: dict[str, Any]) -> dict:
    channels = {}
    ignored = []
    missing = []
    aliases = {}
    duplicates = []
    for channel, value in texture_paths.items():
        channel_name = str(channel)
        canonical = _canonical_pbr_channel(channel_name)
        if canonical is None:
            ignored.append(channel_name)
            continue
        if canonical != channel_name:
            aliases[channel_name] = canonical
        if isinstance(value, str) and value.strip():
            if canonical in channels:
                duplicates.append(channel_name)
                continue
            channels[canonical] = value.strip()
        else:
            missing.append(canonical)
    return {
        "ok": bool(channels),
        "channels": channels,
        "aliases": aliases,
        "duplicate_channels": sorted(duplicates),
        "ignored_channels": sorted(ignored),
        "missing_channels": sorted(missing),
    }


def validate_material_snapshot(snapshot: dict[str, Any]) -> dict:
    issues: list[dict] = []
    analysis = analyze_material_snapshot(snapshot)
    analysis_by_name = {
        item.get("name"): item
        for item in analysis.get("materials", [])
    }

    for material in snapshot.get("materials", []):
        material_name = material.get("name", "<material>")
        if not material.get("use_nodes"):
            issues.append(_issue(
                "nodes_disabled",
                f"Material '{material_name}' does not use nodes.",
                material=material_name,
            ))
            continue

        nodes = material.get("nodes", [])
        node_types = {node.get("type") for node in nodes}
        if "BSDF_PRINCIPLED" not in node_types:
            issues.append(_issue(
                "missing_principled_bsdf",
                f"Material '{material_name}' has no Principled BSDF node.",
                material=material_name,
            ))
        elif not _has_surface_output_link(material):
            issues.append(_issue(
                "missing_surface_output_link",
                f"Material '{material_name}' has no Principled BSDF link to Material Output Surface.",
                material=material_name,
            ))

        for node in nodes:
            if node.get("type") != "TEX_IMAGE":
                continue
            image = node.get("image") or {}
            if not image.get("filepath"):
                issues.append(_issue(
                    "missing_image_filepath",
                    f"Image texture node '{node.get('name', '<node>')}' has no filepath.",
                    material=material_name,
                    node=node.get("name"),
                    image=image.get("name"),
                ))
            expected_channel = _texture_expected_channel(node)
            color_space = image.get("color_space", "")
            if (
                expected_channel in {"roughness", "metallic", "normal", "alpha"}
                and color_space
                and not _is_non_color_space(color_space)
            ):
                issues.append(_issue(
                    "wrong_texture_color_space",
                    (
                        f"Texture node '{node.get('name', '<node>')}' looks like "
                        f"{expected_channel} but uses color space '{color_space}'."
                    ),
                    material=material_name,
                    node=node.get("name"),
                    expected_channel=expected_channel,
                    color_space=color_space,
                ))

        material_analysis = analysis_by_name.get(material.get("name"), {})
        if (
            material_analysis.get("channels", {}).get("alpha", {}).get("connected")
            and _material_uses_transparency(material) is False
        ):
            issues.append(_issue(
                "alpha_channel_requires_transparency",
                (
                    f"Material '{material_name}' has Alpha connected but is still "
                    "configured as opaque."
                ),
                material=material_name,
                blend_method=material.get("blend_method"),
                surface_render_method=material.get("surface_render_method"),
            ))
        normal_channel = material_analysis.get("channels", {}).get("normal", {})
        if (
            normal_channel.get("connected")
            and normal_channel.get("source_type") == "TEX_IMAGE"
        ):
            issues.append(_issue(
                "normal_texture_requires_normal_map",
                (
                    f"Material '{material_name}' connects a normal texture "
                    "directly to Principled BSDF Normal. Insert a Normal Map node."
                ),
                material=material_name,
                node=normal_channel.get("source_node"),
            ))
        for texture in material_analysis.get("expected_textures", []):
            if not texture.get("connected"):
                issues.append(_issue(
                    "unconnected_pbr_texture",
                    (
                        f"Texture node '{texture.get('node')}' looks like "
                        f"{texture.get('expected_channel')} but is not connected to that channel."
                    ),
                    material=material_name,
                    node=texture.get("node"),
                    expected_channel=texture.get("expected_channel"),
                ))

        for link in material.get("links", []):
            if not all([
                link.get("from_node"),
                link.get("from_socket"),
                link.get("to_node"),
                link.get("to_socket"),
            ]):
                issues.append(_issue(
                    "invalid_link",
                    f"Material '{material_name}' has a link with missing endpoint data.",
                    material=material_name,
                    link=link,
                ))

    return _report(issues)


def _summarize_interface(interface: list[dict]) -> dict:
    inputs = [socket for socket in interface if socket.get("in_out") == "INPUT"]
    outputs = [socket for socket in interface if socket.get("in_out") == "OUTPUT"]
    return {
        "input_count": len(inputs),
        "output_count": len(outputs),
        "geometry_inputs": [
            socket.get("name")
            for socket in inputs
            if "Geometry" in (socket.get("socket_type") or socket.get("type") or "")
        ],
        "geometry_outputs": [
            socket.get("name")
            for socket in outputs
            if "Geometry" in (socket.get("socket_type") or socket.get("type") or "")
        ],
    }


_GEOMETRY_OUTPUT_SOCKET_NAMES = {
    "geometry",
    "mesh",
    "curve",
    "curves",
    "points",
    "instances",
    "volume",
}


def _node_output_socket(node: dict, socket_name: str) -> dict | None:
    normalized_name = _normalize(socket_name)
    for socket in node.get("outputs", []):
        if _normalize(socket.get("name")) == normalized_name:
            return socket
    return None


def _link_source_is_geometry(node: dict, socket_name: str) -> bool:
    socket = _node_output_socket(node, socket_name)
    socket_type = _normalize((socket or {}).get("type"))
    if socket_type:
        return socket_type == "geometry" or "geometry" in socket_type
    return _normalize(socket_name) in _GEOMETRY_OUTPUT_SOCKET_NAMES


def _has_geometry_output_link(node_group: dict) -> bool:
    nodes_by_name = _node_map(node_group.get("nodes", []))
    for link in node_group.get("links", []):
        to_node = nodes_by_name.get(link.get("to_node"), {})
        from_node = nodes_by_name.get(link.get("from_node"), {})
        if (
            to_node.get("type") == "GROUP_OUTPUT"
            and _normalize(link.get("to_socket")) == "geometry"
            and _link_source_is_geometry(from_node, link.get("from_socket"))
            and bool(link.get("from_node"))
            and bool(link.get("from_socket"))
        ):
            return True
    return False


def analyze_geometry_nodes_snapshot(snapshot: dict[str, Any]) -> dict:
    objects = []
    for obj in snapshot.get("objects", []):
        modifiers = []
        for modifier in obj.get("modifiers", []):
            node_group = modifier.get("node_group")
            if not node_group:
                modifiers.append({
                    "name": modifier.get("name"),
                    "type": modifier.get("type"),
                    "node_group": None,
                })
                continue
            interface = node_group.get("interface", [])
            modifiers.append({
                "name": modifier.get("name"),
                "type": modifier.get("type"),
                "node_group": {
                    "name": node_group.get("name"),
                    "interface_summary": _summarize_interface(interface),
                    "has_geometry_output_link": _has_geometry_output_link(node_group),
                },
            })
        objects.append({
            "name": obj.get("name"),
            "type": obj.get("type"),
            "modifiers": modifiers,
        })
    return {"objects": objects}


def validate_geometry_nodes_snapshot(snapshot: dict[str, Any]) -> dict:
    issues: list[dict] = []

    for obj in snapshot.get("objects", []):
        object_name = obj.get("name", "<object>")
        for modifier in obj.get("modifiers", []):
            if modifier.get("type") != "NODES":
                continue
            modifier_name = modifier.get("name", "<modifier>")
            node_group = modifier.get("node_group")
            if not node_group:
                issues.append(_issue(
                    "missing_node_group",
                    f"Geometry Nodes modifier '{modifier_name}' has no node group.",
                    object=object_name,
                    modifier=modifier_name,
                ))
                continue

            nodes = node_group.get("nodes", [])
            node_types = {node.get("type") for node in nodes}
            interface_summary = _summarize_interface(node_group.get("interface", []))
            if not interface_summary["geometry_inputs"]:
                issues.append(_issue(
                    "missing_geometry_input_socket",
                    f"Node group '{node_group.get('name', '<node group>')}' has no Geometry input interface socket.",
                    object=object_name,
                    modifier=modifier_name,
                    node_group=node_group.get("name"),
                ))
            if not interface_summary["geometry_outputs"]:
                issues.append(_issue(
                    "missing_geometry_output_socket",
                    f"Node group '{node_group.get('name', '<node group>')}' has no Geometry output interface socket.",
                    object=object_name,
                    modifier=modifier_name,
                    node_group=node_group.get("name"),
                ))
            if "GROUP_INPUT" not in node_types:
                issues.append(_issue(
                    "missing_group_input",
                    f"Node group '{node_group.get('name', '<node group>')}' has no Group Input.",
                    object=object_name,
                    modifier=modifier_name,
                    node_group=node_group.get("name"),
                ))
            if "GROUP_OUTPUT" not in node_types:
                issues.append(_issue(
                    "missing_group_output",
                    f"Node group '{node_group.get('name', '<node group>')}' has no Group Output.",
                    object=object_name,
                    modifier=modifier_name,
                    node_group=node_group.get("name"),
                ))
            elif not _has_geometry_output_link(node_group):
                issues.append(_issue(
                    "missing_geometry_output_link",
                    f"Node group '{node_group.get('name', '<node group>')}' does not feed Geometry into Group Output.",
                    object=object_name,
                    modifier=modifier_name,
                    node_group=node_group.get("name"),
                ))

            for link in node_group.get("links", []):
                if not all([
                    link.get("from_node"),
                    link.get("from_socket"),
                    link.get("to_node"),
                    link.get("to_socket"),
                ]):
                    issues.append(_issue(
                        "invalid_link",
                        f"Node group '{node_group.get('name', '<node group>')}' has a link with missing endpoint data.",
                        object=object_name,
                        modifier=modifier_name,
                        node_group=node_group.get("name"),
                        link=link,
                    ))

    return _report(issues)
