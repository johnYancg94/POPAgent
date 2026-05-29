"""
Pure helpers for .blend incremental file versioning.

No bpy dependency — kept here so the version-bump rule is unit-testable without
Blender. The convention: a trailing _NNN (zero-padded, >= 3 digits) before the
.blend extension is the version counter. Files without a counter get _001.

Examples:
    char_chef.blend        -> char_chef_001.blend
    char_chef_001.blend    -> char_chef_002.blend
    char_chef_009.blend    -> char_chef_010.blend
    char_chef_v3.blend     -> char_chef_v3_001.blend  (v3 is not the counter)
"""

from __future__ import annotations

import os
import re

_VERSION_RE = re.compile(r"^(?P<stem>.*?)_(?P<num>\d{3,})$")


def next_incremental_path(current_path: str) -> str:
    """Return the next versioned path for current_path.

    current_path may or may not already carry a _NNN counter. The directory and
    .blend extension are preserved; only the numeric suffix is added or bumped.
    """
    directory, filename = os.path.split(current_path)
    root, ext = os.path.splitext(filename)
    if not ext:
        ext = ".blend"

    match = _VERSION_RE.match(root)
    if match:
        width = len(match.group("num"))
        nxt = int(match.group("num")) + 1
        new_root = f"{match.group('stem')}_{nxt:0{width}d}"
    else:
        new_root = f"{root}_001"

    return os.path.join(directory, new_root + ext)


def ensure_blend_extension(path: str) -> str:
    """Append .blend if the path has no extension; leave other extensions alone."""
    root, ext = os.path.splitext(path)
    if not ext:
        return path + ".blend"
    return path
