# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# pyright: reportInvalidTypeForm=false

import bpy


class UsagePropertyGroup(bpy.types.PropertyGroup):
    request_id: bpy.props.StringProperty()
    created_at: bpy.props.StringProperty()
    prompt_preview: bpy.props.StringProperty()

    llm_organization: bpy.props.StringProperty()
    model: bpy.props.StringProperty()
    mode: bpy.props.StringProperty()

    input_tokens: bpy.props.IntProperty(default=0)
    output_tokens: bpy.props.IntProperty(default=0)
    cache_creation_tokens: bpy.props.IntProperty(default=0)
    cache_read_tokens: bpy.props.IntProperty(default=0)
    reasoning_tokens: bpy.props.IntProperty(default=0)
    total_tokens: bpy.props.IntProperty(default=0)

    estimated_cost_rmb: bpy.props.FloatProperty(default=0.0, precision=6)
    cost_is_estimated: bpy.props.BoolProperty(default=False)

    latency_ms: bpy.props.IntProperty(default=0)
    status_code: bpy.props.IntProperty(default=0)
    is_error: bpy.props.BoolProperty(default=False)
    error_message: bpy.props.StringProperty(default="")
