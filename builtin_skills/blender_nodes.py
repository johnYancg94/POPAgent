"""Read-only Blender 5.1 material and geometry node inspection skills."""

from __future__ import annotations

import bpy

from ..agent_core.node_diagnostics import (
    analyze_geometry_nodes_snapshot,
    analyze_material_snapshot,
    plan_pbr_texture_paths,
    validate_geometry_nodes_snapshot,
    validate_material_snapshot,
)


def _socket_snapshot(socket) -> dict:
    data = {
        "name": socket.name,
        "identifier": getattr(socket, "identifier", socket.name),
        "type": getattr(socket, "type", ""),
        "is_linked": bool(getattr(socket, "is_linked", False)),
    }
    default_value = _socket_default_value(socket)
    if default_value is not None:
        data["default_value"] = default_value
    return data


def _socket_default_value(socket):
    if not hasattr(socket, "default_value"):
        return None
    value = socket.default_value
    if isinstance(value, (int, float, bool, str)):
        return value
    try:
        return list(value)
    except TypeError:
        return str(value)


def _node_snapshot(node) -> dict:
    data = {
        "name": node.name,
        "label": node.label,
        "type": node.type,
        "bl_idname": node.bl_idname,
        "inputs": [_socket_snapshot(socket) for socket in node.inputs],
        "outputs": [_socket_snapshot(socket) for socket in node.outputs],
    }
    image = getattr(node, "image", None)
    if image is not None:
        data["image"] = {
            "name": image.name,
            "filepath": image.filepath,
            "source": getattr(image, "source", ""),
            "color_space": getattr(
                getattr(image, "colorspace_settings", None),
                "name",
                "",
            ),
        }
    return data


def _link_snapshot(link) -> dict:
    return {
        "from_node": link.from_node.name if link.from_node else "",
        "from_socket": link.from_socket.name if link.from_socket else "",
        "to_node": link.to_node.name if link.to_node else "",
        "to_socket": link.to_socket.name if link.to_socket else "",
    }


def _material_snapshot(material) -> dict:
    data = {
        "name": material.name,
        "use_nodes": bool(material.use_nodes),
        "blend_method": getattr(material, "blend_method", ""),
        "surface_render_method": getattr(material, "surface_render_method", ""),
        "nodes": [],
        "links": [],
    }
    if material.use_nodes and material.node_tree:
        data["nodes"] = [_node_snapshot(node) for node in material.node_tree.nodes]
        data["links"] = [_link_snapshot(link) for link in material.node_tree.links]
    return data


def _node_group_snapshot(node_group) -> dict:
    return {
        "name": node_group.name,
        "type": node_group.bl_idname,
        "interface": _node_group_interface_snapshot(node_group),
        "nodes": [_node_snapshot(node) for node in node_group.nodes],
        "links": [_link_snapshot(link) for link in node_group.links],
    }


def _node_group_interface_snapshot(node_group) -> list[dict]:
    interface = getattr(node_group, "interface", None)
    if interface is None:
        return []

    sockets = []
    items_tree = getattr(interface, "items_tree", [])
    for item in items_tree:
        item_type = getattr(item, "item_type", "")
        if item_type and item_type != "SOCKET":
            continue
        sockets.append({
            "name": getattr(item, "name", ""),
            "in_out": getattr(item, "in_out", ""),
            "socket_type": getattr(item, "socket_type", ""),
            "identifier": getattr(item, "identifier", ""),
        })
    return sockets


def _objects_for_scope(context, scope: str):
    if scope == "active":
        return [context.active_object] if context.active_object else []
    if scope == "selected":
        return list(context.selected_objects)
    return list(bpy.data.objects)


def _active_material(context, material_name: str = "", create: bool = True):
    if material_name:
        material = bpy.data.materials.get(material_name)
        if material is None and create:
            material = bpy.data.materials.new(material_name)
    else:
        obj = context.active_object
        if obj is None:
            return None
        material = obj.active_material
        if material is None and create:
            material = bpy.data.materials.new(f"{obj.name} Material")
            obj.data.materials.append(material)
            obj.active_material = material
    if material is not None and not material.use_nodes:
        material.use_nodes = True
    return material


def _ensure_principled(material):
    if not material.use_nodes:
        material.use_nodes = True
    tree = material.node_tree
    for node in tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    node = tree.nodes.new("ShaderNodeBsdfPrincipled")
    node.name = "Principled BSDF"
    node.location = (0, 0)
    output = None
    for existing in tree.nodes:
        if existing.type == "OUTPUT_MATERIAL":
            output = existing
            break
    if output and "BSDF" in node.outputs and "Surface" in output.inputs:
        tree.links.new(node.outputs["BSDF"], output.inputs["Surface"])
    return node


def _set_non_color(image):
    try:
        image.colorspace_settings.name = "Non-Color"
    except Exception:
        pass


def _enable_material_transparency(material):
    configured = {}
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = "BLEND"
            configured["blend_method"] = getattr(material, "blend_method", "")
        except Exception as exc:
            configured["blend_method_error"] = str(exc)
    if hasattr(material, "surface_render_method"):
        for value in ("BLENDED", "DITHERED"):
            try:
                material.surface_render_method = value
                configured["surface_render_method"] = getattr(
                    material,
                    "surface_render_method",
                    "",
                )
                break
            except Exception as exc:
                configured["surface_render_method_error"] = str(exc)
    return configured


def _load_image(path: str):
    image = bpy.data.images.get(path)
    if image is not None:
        return image
    return bpy.data.images.load(path, check_existing=True)


def _input_by_name(node, names: tuple[str, ...]):
    normalized = {name.lower() for name in names}
    for socket in node.inputs:
        if socket.name.lower() in normalized:
            return socket
    return None


def _socket_by_name(sockets, name: str):
    for socket in sockets:
        if socket.name == name or getattr(socket, "identifier", "") == name:
            return socket
    return None


def _node_by_name(tree, name: str):
    node = tree.nodes.get(name)
    if node is not None:
        return node
    for candidate in tree.nodes:
        if candidate.label == name:
            return candidate
    return None


def _add_node_to_tree(tree, node_type: str, node_name: str = "", location: list | None = None):
    try:
        node = tree.nodes.new(node_type)
    except Exception as exc:
        return None, {
            "ok": False,
            "error_kind": "node_type_not_found",
            "error": str(exc),
            "node_type": node_type,
        }
    if node_name:
        node.name = node_name
        node.label = node_name
    if isinstance(location, list) and len(location) >= 2:
        try:
            node.location = (float(location[0]), float(location[1]))
        except (TypeError, ValueError):
            pass
    return node, None


def _connect_nodes_in_tree(
    tree,
    from_node: str,
    from_socket: str,
    to_node: str,
    to_socket: str,
) -> dict:
    source = _node_by_name(tree, from_node)
    target = _node_by_name(tree, to_node)
    if source is None:
        return {
            "ok": False,
            "error_kind": "source_node_not_found",
            "error": f"Source node not found: {from_node}",
            "node": from_node,
        }
    if target is None:
        return {
            "ok": False,
            "error_kind": "target_node_not_found",
            "error": f"Target node not found: {to_node}",
            "node": to_node,
        }
    output_socket = _socket_by_name(source.outputs, from_socket)
    input_socket = _socket_by_name(target.inputs, to_socket)
    if output_socket is None:
        return {
            "ok": False,
            "error_kind": "source_socket_not_found",
            "error": f"Output socket not found: {from_node}.{from_socket}",
            "node": from_node,
            "socket": from_socket,
        }
    if input_socket is None:
        return {
            "ok": False,
            "error_kind": "target_socket_not_found",
            "error": f"Input socket not found: {to_node}.{to_socket}",
            "node": to_node,
            "socket": to_socket,
        }
    try:
        tree.links.new(output_socket, input_socket)
    except Exception as exc:
        return {
            "ok": False,
            "error_kind": "link_failed",
            "error": str(exc),
            "from_node": from_node,
            "from_socket": from_socket,
            "to_node": to_node,
            "to_socket": to_socket,
        }
    return {
        "ok": True,
        "link": {
            "from_node": source.name,
            "from_socket": output_socket.name,
            "to_node": target.name,
            "to_socket": input_socket.name,
        },
    }


def _set_socket_default(socket, value) -> dict:
    if not hasattr(socket, "default_value"):
        return {
            "ok": False,
            "error_kind": "socket_has_no_default",
            "error": f"Socket '{socket.name}' does not expose default_value.",
            "socket": socket.name,
        }
    current = socket.default_value
    try:
        if isinstance(current, (int, float, bool, str)):
            socket.default_value = value
        else:
            values = value if isinstance(value, list) else [value]
            for index in range(min(len(current), len(values))):
                current[index] = values[index]
    except Exception as exc:
        return {
            "ok": False,
            "error_kind": "set_default_failed",
            "error": str(exc),
            "socket": socket.name,
            "value": value,
        }
    return {
        "ok": True,
        "socket": socket.name,
        "value": list(socket.default_value) if hasattr(socket.default_value, "__len__") and not isinstance(socket.default_value, str) else socket.default_value,
    }


def _set_node_input_default(tree, node_name: str, socket_name: str, value) -> dict:
    node = _node_by_name(tree, node_name)
    if node is None:
        return {
            "ok": False,
            "error_kind": "node_not_found",
            "error": f"Node not found: {node_name}",
            "node": node_name,
        }
    socket = _socket_by_name(node.inputs, socket_name)
    if socket is None:
        return {
            "ok": False,
            "error_kind": "input_socket_not_found",
            "error": f"Input socket not found: {node_name}.{socket_name}",
            "node": node_name,
            "socket": socket_name,
        }
    result = _set_socket_default(socket, value)
    result["node"] = node.name
    return result


def _handler_add_material_node(
    context=None,
    node_type: str = "",
    material_name: str = "",
    node_name: str = "",
    location: list | None = None,
) -> dict:
    if context is None:
        context = bpy.context
    material = _active_material(context, material_name=material_name, create=True)
    if material is None:
        return {
            "ok": False,
            "error_kind": "no_active_object",
            "error": "No active object available for material assignment.",
        }
    node, error = _add_node_to_tree(material.node_tree, node_type, node_name, location)
    if error:
        return error
    snapshot = {"materials": [_material_snapshot(material)]}
    return {
        "ok": True,
        "material": material.name,
        "node": _node_snapshot(node),
        "analysis": analyze_material_snapshot(snapshot),
        "validation": validate_material_snapshot(snapshot),
    }


def _handler_connect_material_nodes(
    context=None,
    from_node: str = "",
    from_socket: str = "",
    to_node: str = "",
    to_socket: str = "",
    material_name: str = "",
) -> dict:
    if context is None:
        context = bpy.context
    material = _active_material(context, material_name=material_name, create=False)
    if material is None or material.node_tree is None:
        return {
            "ok": False,
            "error_kind": "material_not_found",
            "error": "Material not found or has no node tree.",
            "material": material_name,
        }
    result = _connect_nodes_in_tree(
        material.node_tree,
        from_node,
        from_socket,
        to_node,
        to_socket,
    )
    if not result.get("ok"):
        return result
    snapshot = {"materials": [_material_snapshot(material)]}
    result.update({
        "material": material.name,
        "analysis": analyze_material_snapshot(snapshot),
        "validation": validate_material_snapshot(snapshot),
    })
    return result


def _handler_set_material_node_input(
    context=None,
    node_name: str = "",
    socket_name: str = "",
    value=None,
    material_name: str = "",
) -> dict:
    if context is None:
        context = bpy.context
    material = _active_material(context, material_name=material_name, create=False)
    if material is None or material.node_tree is None:
        return {
            "ok": False,
            "error_kind": "material_not_found",
            "error": "Material not found or has no node tree.",
            "material": material_name,
        }
    result = _set_node_input_default(
        material.node_tree,
        node_name=node_name,
        socket_name=socket_name,
        value=value,
    )
    if not result.get("ok"):
        return result
    snapshot = {"materials": [_material_snapshot(material)]}
    result.update({
        "material": material.name,
        "analysis": analyze_material_snapshot(snapshot),
        "validation": validate_material_snapshot(snapshot),
    })
    return result


def _connect_texture_channel(material, tree, principled, channel: str, path: str) -> dict:
    image = _load_image(path)
    image_node = tree.nodes.new("ShaderNodeTexImage")
    image_node.name = f"POPAgent {channel}"
    image_node.label = channel
    image_node.image = image

    color_output = image_node.outputs.get("Color")
    if channel in {"roughness", "metallic", "normal", "alpha"}:
        _set_non_color(image)

    if channel == "normal":
        normal_map = tree.nodes.new("ShaderNodeNormalMap")
        normal_map.name = "POPAgent Normal Map"
        if color_output and normal_map.inputs.get("Color"):
            tree.links.new(color_output, normal_map.inputs["Color"])
        target = _input_by_name(principled, ("Normal",))
        if target and normal_map.outputs.get("Normal"):
            tree.links.new(normal_map.outputs["Normal"], target)
    else:
        input_names = {
            "base_color": ("Base Color",),
            "roughness": ("Roughness",),
            "metallic": ("Metallic",),
            "alpha": ("Alpha",),
        }.get(channel, ())
        target = _input_by_name(principled, input_names)
        if target and color_output:
            tree.links.new(color_output, target)

    result = {"channel": channel, "path": path, "image": image.name}
    if channel == "alpha":
        result["material_transparency"] = _enable_material_transparency(material)
    return result


def _handler_connect_pbr_textures(
    context=None,
    texture_paths: dict | None = None,
    material_name: str = "",
) -> dict:
    if context is None:
        context = bpy.context
    plan = plan_pbr_texture_paths(texture_paths or {})
    if not plan["ok"]:
        return {
            "ok": False,
            "error_kind": "no_supported_textures",
            "error": "Provide at least one supported PBR texture path.",
            "aliases": plan.get("aliases", {}),
            "duplicate_channels": plan.get("duplicate_channels", []),
            "ignored_channels": plan["ignored_channels"],
            "missing_channels": plan.get("missing_channels", []),
        }

    material = _active_material(context, material_name=material_name, create=True)
    if material is None:
        return {
            "ok": False,
            "error_kind": "no_active_object",
            "error": "No active object available for material assignment.",
        }

    principled = _ensure_principled(material)
    tree = material.node_tree
    connected = []
    for channel, path in plan["channels"].items():
        try:
            connected.append(_connect_texture_channel(
                material,
                tree,
                principled,
                channel,
                path,
            ))
        except Exception as exc:
            return {
                "ok": False,
                "error_kind": "image_load_failed",
                "error": str(exc),
                "channel": channel,
                "path": path,
                "connected": connected,
                "aliases": plan.get("aliases", {}),
                "duplicate_channels": plan.get("duplicate_channels", []),
                "ignored_channels": plan["ignored_channels"],
                "missing_channels": plan.get("missing_channels", []),
            }

    snapshot = {"materials": [_material_snapshot(material)]}
    return {
        "ok": True,
        "material": material.name,
        "connected": connected,
        "aliases": plan.get("aliases", {}),
        "duplicate_channels": plan.get("duplicate_channels", []),
        "ignored_channels": plan["ignored_channels"],
        "missing_channels": plan.get("missing_channels", []),
        "analysis": analyze_material_snapshot(snapshot),
        "validation": validate_material_snapshot(snapshot),
    }


def _handler_inspect_material_nodes(context=None, scope: str = "active") -> dict:
    if context is None:
        context = bpy.context

    materials = []
    seen = set()
    for obj in _objects_for_scope(context, scope):
        if obj is None:
            continue
        for slot in getattr(obj, "material_slots", []):
            material = slot.material
            if material is None or material.name in seen:
                continue
            seen.add(material.name)
            mat = _material_snapshot(material)
            mat["users"] = [obj.name]
            materials.append(mat)

    snapshot = {"ok": True, "scope": scope, "materials": materials}
    snapshot["analysis"] = analyze_material_snapshot(snapshot)
    snapshot["validation"] = validate_material_snapshot(snapshot)
    return snapshot


def _handler_validate_material_nodes(context=None, scope: str = "active") -> dict:
    snapshot = _handler_inspect_material_nodes(context=context, scope=scope)
    validation = snapshot["validation"]
    validation["scope"] = scope
    validation["material_count"] = len(snapshot.get("materials", []))
    return validation


def _handler_inspect_geometry_nodes(context=None, scope: str = "active") -> dict:
    if context is None:
        context = bpy.context

    objects = []
    for obj in _objects_for_scope(context, scope):
        if obj is None:
            continue
        modifiers = []
        for modifier in obj.modifiers:
            if modifier.type != "NODES":
                continue
            node_group = getattr(modifier, "node_group", None)
            modifiers.append({
                "name": modifier.name,
                "type": modifier.type,
                "node_group": _node_group_snapshot(node_group) if node_group else None,
            })
        if modifiers:
            objects.append({"name": obj.name, "type": obj.type, "modifiers": modifiers})

    snapshot = {"ok": True, "scope": scope, "objects": objects}
    snapshot["analysis"] = analyze_geometry_nodes_snapshot(snapshot)
    snapshot["validation"] = validate_geometry_nodes_snapshot(snapshot)
    return snapshot


def _handler_validate_geometry_nodes(context=None, scope: str = "active") -> dict:
    snapshot = _handler_inspect_geometry_nodes(context=context, scope=scope)
    validation = snapshot["validation"]
    validation["scope"] = scope
    validation["object_count"] = len(snapshot.get("objects", []))
    return validation


def _new_geometry_node_group(name: str):
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.interface.new_socket(
        name="Geometry",
        in_out="INPUT",
        socket_type="NodeSocketGeometry",
    )
    group.interface.new_socket(
        name="Geometry",
        in_out="OUTPUT",
        socket_type="NodeSocketGeometry",
    )
    input_node = group.nodes.new("NodeGroupInput")
    output_node = group.nodes.new("NodeGroupOutput")
    input_node.location = (-200, 0)
    output_node.location = (200, 0)
    if input_node.outputs and output_node.inputs:
        group.links.new(input_node.outputs[0], output_node.inputs[0])
    return group


def _handler_ensure_basic_geometry_nodes(
    context=None,
    modifier_name: str = "POPAgent Geometry Nodes",
    node_group_name: str = "POPAgent Basic Geometry Nodes",
) -> dict:
    if context is None:
        context = bpy.context
    obj = context.active_object
    if obj is None:
        return {
            "ok": False,
            "error_kind": "no_active_object",
            "error": "No active object available for Geometry Nodes modifier.",
        }

    modifier = obj.modifiers.get(modifier_name)
    created_modifier = False
    if modifier is None:
        modifier = obj.modifiers.new(modifier_name, "NODES")
        created_modifier = True

    created_group = False
    if getattr(modifier, "node_group", None) is None:
        group = _new_geometry_node_group(node_group_name)
        modifier.node_group = group
        created_group = True

    snapshot = _handler_inspect_geometry_nodes(context=context, scope="active")
    return {
        "ok": True,
        "object": obj.name,
        "modifier": modifier.name,
        "node_group": modifier.node_group.name if modifier.node_group else None,
        "created_modifier": created_modifier,
        "created_node_group": created_group,
        "analysis": snapshot["analysis"],
        "validation": snapshot["validation"],
    }


def _active_geometry_node_group(context, modifier_name: str = "", create: bool = True):
    obj = context.active_object
    if obj is None:
        return None, None, {
            "ok": False,
            "error_kind": "no_active_object",
            "error": "No active object available for Geometry Nodes modifier.",
        }
    modifier = obj.modifiers.get(modifier_name) if modifier_name else None
    if modifier is None:
        for candidate in obj.modifiers:
            if candidate.type == "NODES":
                modifier = candidate
                break
    if modifier is None and create:
        modifier = obj.modifiers.new(modifier_name or "POPAgent Geometry Nodes", "NODES")
    if modifier is None:
        return obj, None, {
            "ok": False,
            "error_kind": "geometry_nodes_modifier_not_found",
            "error": "No Geometry Nodes modifier found.",
            "modifier": modifier_name,
        }
    if getattr(modifier, "node_group", None) is None and create:
        modifier.node_group = _new_geometry_node_group("POPAgent Geometry Nodes")
    if getattr(modifier, "node_group", None) is None:
        return obj, modifier, {
            "ok": False,
            "error_kind": "missing_node_group",
            "error": "Geometry Nodes modifier has no node group.",
            "modifier": modifier.name,
        }
    return obj, modifier, None


def _handler_add_geometry_node(
    context=None,
    node_type: str = "",
    modifier_name: str = "",
    node_name: str = "",
    location: list | None = None,
) -> dict:
    if context is None:
        context = bpy.context
    obj, modifier, error = _active_geometry_node_group(
        context,
        modifier_name=modifier_name,
        create=True,
    )
    if error:
        return error
    node, error = _add_node_to_tree(modifier.node_group, node_type, node_name, location)
    if error:
        return error
    snapshot = _handler_inspect_geometry_nodes(context=context, scope="active")
    return {
        "ok": True,
        "object": obj.name,
        "modifier": modifier.name,
        "node_group": modifier.node_group.name,
        "node": _node_snapshot(node),
        "analysis": snapshot["analysis"],
        "validation": snapshot["validation"],
    }


def _handler_connect_geometry_nodes(
    context=None,
    from_node: str = "",
    from_socket: str = "",
    to_node: str = "",
    to_socket: str = "",
    modifier_name: str = "",
) -> dict:
    if context is None:
        context = bpy.context
    obj, modifier, error = _active_geometry_node_group(
        context,
        modifier_name=modifier_name,
        create=False,
    )
    if error:
        return error
    result = _connect_nodes_in_tree(
        modifier.node_group,
        from_node,
        from_socket,
        to_node,
        to_socket,
    )
    if not result.get("ok"):
        return result
    snapshot = _handler_inspect_geometry_nodes(context=context, scope="active")
    result.update({
        "object": obj.name,
        "modifier": modifier.name,
        "node_group": modifier.node_group.name,
        "analysis": snapshot["analysis"],
        "validation": snapshot["validation"],
    })
    return result


def _handler_set_geometry_node_input(
    context=None,
    node_name: str = "",
    socket_name: str = "",
    value=None,
    modifier_name: str = "",
) -> dict:
    if context is None:
        context = bpy.context
    obj, modifier, error = _active_geometry_node_group(
        context,
        modifier_name=modifier_name,
        create=False,
    )
    if error:
        return error
    result = _set_node_input_default(
        modifier.node_group,
        node_name=node_name,
        socket_name=socket_name,
        value=value,
    )
    if not result.get("ok"):
        return result
    snapshot = _handler_inspect_geometry_nodes(context=context, scope="active")
    result.update({
        "object": obj.name,
        "modifier": modifier.name,
        "node_group": modifier.node_group.name,
        "analysis": snapshot["analysis"],
        "validation": snapshot["validation"],
    })
    return result


def _node_type_domain_prefixes(domain: str) -> tuple[str, ...]:
    if domain == "shader":
        return ("ShaderNode",)
    if domain == "geometry":
        return ("GeometryNode",)
    return ("ShaderNode", "GeometryNode")


def _node_type_info(type_name: str, cls) -> dict:
    bl_rna = getattr(cls, "bl_rna", None)
    return {
        "identifier": getattr(bl_rna, "identifier", type_name),
        "name": getattr(bl_rna, "name", type_name),
        "description": getattr(bl_rna, "description", ""),
        "python_type": type_name,
    }


def _handler_search_node_types(
    context=None,
    domain: str = "all",
    query: str = "",
    max_results: int = 40,
) -> dict:
    del context
    prefixes = _node_type_domain_prefixes(domain)
    needle = query.lower().strip()
    limit = max(1, min(int(max_results or 40), 100))

    results = []
    for type_name in sorted(dir(bpy.types)):
        if not type_name.startswith(prefixes):
            continue
        cls = getattr(bpy.types, type_name, None)
        info = _node_type_info(type_name, cls)
        haystack = " ".join([
            info["identifier"],
            info["name"],
            info["description"],
            info["python_type"],
        ]).lower()
        if needle and needle not in haystack:
            continue
        results.append(info)
        if len(results) >= limit:
            break

    return {
        "ok": True,
        "domain": domain,
        "query": query,
        "count": len(results),
        "results": results,
    }


_SCOPE_SCHEMA = {
    "type": "string",
    "enum": ["active", "selected", "all"],
    "description": "Which objects to inspect.",
}


SEARCH_NODE_TYPES = {
    "name": "blender.nodes.search_types",
    "description": (
        "Search the current Blender 5.1 runtime for available ShaderNode and GeometryNode "
        "types. Use this before creating or discussing specific node bl_idname values when "
        "the exact Blender 5.1 node type is uncertain."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "enum": ["all", "shader", "geometry"],
                "description": "Node domain to search.",
            },
            "query": {
                "type": "string",
                "description": "Optional case-insensitive text search.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return, capped at 100.",
            },
        },
        "required": [],
    },
    "owner": "builtin.nodes",
    "handler": _handler_search_node_types,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


INSPECT_MATERIAL_NODES = {
    "name": "blender.material.inspect_nodes",
    "description": (
        "Inspect Blender 5.1 material node trees for the active, selected, or all objects. "
        "Returns material nodes, sockets, links, image texture paths, and validation issues."
    ),
    "parameters": {
        "type": "object",
        "properties": {"scope": _SCOPE_SCHEMA},
        "required": [],
    },
    "owner": "builtin.nodes",
    "handler": _handler_inspect_material_nodes,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


VALIDATE_MATERIAL_NODES = {
    "name": "blender.material.validate_nodes",
    "description": (
        "Validate Blender material node trees for common production issues: missing nodes, "
        "invalid links, and image texture nodes without file paths."
    ),
    "parameters": {
        "type": "object",
        "properties": {"scope": _SCOPE_SCHEMA},
        "required": [],
    },
    "owner": "builtin.nodes",
    "handler": _handler_validate_material_nodes,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


CONNECT_PBR_TEXTURES = {
    "name": "blender.material.connect_pbr_textures",
    "description": (
        "Connect explicit PBR texture file paths to a Blender 5.1 material's Principled BSDF. "
        "Supports base_color, roughness, metallic, normal, and alpha. Creates a material on "
        "the active object when needed and returns post-connection analysis/validation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "texture_paths": {
                "type": "object",
                "description": "Map of PBR channel names to image file paths.",
            },
            "material_name": {
                "type": "string",
                "description": "Optional existing or new material name. Defaults to active object material.",
            },
        },
        "required": ["texture_paths"],
    },
    "owner": "builtin.nodes",
    "handler": _handler_connect_pbr_textures,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


ADD_MATERIAL_NODE = {
    "name": "blender.material.add_node",
    "description": (
        "Add a specific ShaderNode type to the active or named material node tree. "
        "Use blender.nodes.search_types first when the exact Blender 5.1 node type is uncertain."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "node_type": {
                "type": "string",
                "description": "Blender shader node bl_idname, e.g. ShaderNodeTexCoord.",
            },
            "material_name": {
                "type": "string",
                "description": "Optional existing or new material name. Defaults to active object material.",
            },
            "node_name": {
                "type": "string",
                "description": "Optional node name/label to assign.",
            },
            "location": {
                "type": "array",
                "description": "Optional [x, y] node editor location.",
            },
        },
        "required": ["node_type"],
    },
    "owner": "builtin.nodes",
    "handler": _handler_add_material_node,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


CONNECT_MATERIAL_NODES = {
    "name": "blender.material.connect_nodes",
    "description": (
        "Connect two existing nodes in the active or named material node tree by exact "
        "node and socket names."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "from_node": {"type": "string", "description": "Source node name or label."},
            "from_socket": {"type": "string", "description": "Source output socket name or identifier."},
            "to_node": {"type": "string", "description": "Target node name or label."},
            "to_socket": {"type": "string", "description": "Target input socket name or identifier."},
            "material_name": {"type": "string", "description": "Optional material name."},
        },
        "required": ["from_node", "from_socket", "to_node", "to_socket"],
    },
    "owner": "builtin.nodes",
    "handler": _handler_connect_material_nodes,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


SET_MATERIAL_NODE_INPUT = {
    "name": "blender.material.set_node_input",
    "description": (
        "Set an existing material node input socket default_value by node and socket name. "
        "Use this for controlled parameter edits such as Roughness, Value, or Color."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "node_name": {"type": "string", "description": "Node name or label."},
            "socket_name": {"type": "string", "description": "Input socket name or identifier."},
            "value": {
                "type": ["number", "integer", "boolean", "string", "array"],
                "description": "Default value to assign. Use arrays for vectors/colors.",
            },
            "material_name": {"type": "string", "description": "Optional material name."},
        },
        "required": ["node_name", "socket_name", "value"],
    },
    "owner": "builtin.nodes",
    "handler": _handler_set_material_node_input,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


INSPECT_GEOMETRY_NODES = {
    "name": "blender.geometry_nodes.inspect",
    "description": (
        "Inspect Blender 5.1 Geometry Nodes modifiers and node groups for the active, "
        "selected, or all objects. Returns nodes, sockets, links, and validation issues."
    ),
    "parameters": {
        "type": "object",
        "properties": {"scope": _SCOPE_SCHEMA},
        "required": [],
    },
    "owner": "builtin.nodes",
    "handler": _handler_inspect_geometry_nodes,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


VALIDATE_GEOMETRY_NODES = {
    "name": "blender.geometry_nodes.validate",
    "description": (
        "Validate Blender Geometry Nodes modifiers for common structural issues: missing "
        "node groups, missing group input/output nodes, and invalid links."
    ),
    "parameters": {
        "type": "object",
        "properties": {"scope": _SCOPE_SCHEMA},
        "required": [],
    },
    "owner": "builtin.nodes",
    "handler": _handler_validate_geometry_nodes,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


ENSURE_BASIC_GEOMETRY_NODES = {
    "name": "blender.geometry_nodes.ensure_basic_group",
    "description": (
        "Create or repair a basic Blender 5.1 Geometry Nodes modifier on the active object. "
        "Ensures a GeometryNodeTree with Geometry input/output and a pass-through link."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "modifier_name": {
                "type": "string",
                "description": "Modifier name to create or reuse.",
            },
            "node_group_name": {
                "type": "string",
                "description": "Node group name to create when the modifier has no group.",
            },
        },
        "required": [],
    },
    "owner": "builtin.nodes",
    "handler": _handler_ensure_basic_geometry_nodes,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


ADD_GEOMETRY_NODE = {
    "name": "blender.geometry_nodes.add_node",
    "description": (
        "Add a specific GeometryNode type to the active object's Geometry Nodes node group. "
        "Use blender.nodes.search_types first when the exact Blender 5.1 node type is uncertain."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "node_type": {
                "type": "string",
                "description": "Blender geometry node bl_idname, e.g. GeometryNodeJoinGeometry.",
            },
            "modifier_name": {
                "type": "string",
                "description": "Optional Geometry Nodes modifier name.",
            },
            "node_name": {
                "type": "string",
                "description": "Optional node name/label to assign.",
            },
            "location": {
                "type": "array",
                "description": "Optional [x, y] node editor location.",
            },
        },
        "required": ["node_type"],
    },
    "owner": "builtin.nodes",
    "handler": _handler_add_geometry_node,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


CONNECT_GEOMETRY_NODES = {
    "name": "blender.geometry_nodes.connect_nodes",
    "description": (
        "Connect two existing nodes in the active object's Geometry Nodes node group by "
        "exact node and socket names."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "from_node": {"type": "string", "description": "Source node name or label."},
            "from_socket": {"type": "string", "description": "Source output socket name or identifier."},
            "to_node": {"type": "string", "description": "Target node name or label."},
            "to_socket": {"type": "string", "description": "Target input socket name or identifier."},
            "modifier_name": {"type": "string", "description": "Optional Geometry Nodes modifier name."},
        },
        "required": ["from_node", "from_socket", "to_node", "to_socket"],
    },
    "owner": "builtin.nodes",
    "handler": _handler_connect_geometry_nodes,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


SET_GEOMETRY_NODE_INPUT = {
    "name": "blender.geometry_nodes.set_node_input",
    "description": (
        "Set an existing Geometry Nodes node input socket default_value by node and socket "
        "name. Use this for controlled parameter edits on supported sockets."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "node_name": {"type": "string", "description": "Node name or label."},
            "socket_name": {"type": "string", "description": "Input socket name or identifier."},
            "value": {
                "type": ["number", "integer", "boolean", "string", "array"],
                "description": "Default value to assign. Use arrays for vectors/colors.",
            },
            "modifier_name": {"type": "string", "description": "Optional Geometry Nodes modifier name."},
        },
        "required": ["node_name", "socket_name", "value"],
    },
    "owner": "builtin.nodes",
    "handler": _handler_set_geometry_node_input,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}
