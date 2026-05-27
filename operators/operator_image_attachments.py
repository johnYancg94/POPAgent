"""Operators for multimodal image attachments."""

from __future__ import annotations
import base64
import ctypes
import os
import struct
import tempfile
from pathlib import Path

import bpy
from bpy.types import Operator

from ..agent_core.vision_inputs import image_payload_from_file


def _renumber(items) -> None:
    for index, item in enumerate(items):
        item.name = str(index)


def _add_image_attachment(context, display_name: str, source: str,
                          media_type: str, image_base64: str) -> None:
    props = context.scene.chat_companion_properties
    items = context.scene.chat_companion_image_attachments
    item = items.add()
    item.name = str(len(items) - 1)
    item.display_name = display_name
    item.source = source
    item.media_type = media_type
    item.image_base64 = image_base64
    item.is_enabled = True
    items.move(len(items) - 1, 0)
    _renumber(items)
    props.selected_image_attachment_item = 0


class CHAT_COMPANION_OT_add_image_file(Operator):
    bl_idname = "chat_companion.add_image_file"
    bl_label = "Add Image"
    bl_description = "Add an image file to the next multimodal prompt"
    bl_options = {"REGISTER", "INTERNAL"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.jpg;*.jpeg;*.gif;*.webp",
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        props = context.scene.chat_companion_properties
        return getattr(props, "multimodal_enabled", False)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            payload = image_payload_from_file(self.filepath)
        except Exception as exc:
            self.report({"WARNING"}, f"Could not add image: {exc}")
            return {"CANCELLED"}

        _add_image_attachment(
            context,
            Path(self.filepath).name,
            self.filepath,
            payload["media_type"],
            payload["data"],
        )
        self.report({"INFO"}, "Image added")
        return {"FINISHED"}


class CHAT_COMPANION_OT_add_blender_image(Operator):
    bl_idname = "chat_companion.add_blender_image"
    bl_label = "Add Blender Image"
    bl_description = "Add the selected Blender image datablock to the next prompt"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        props = context.scene.chat_companion_properties
        return bool(
            getattr(props, "multimodal_enabled", False)
            and getattr(props, "selected_blender_image", "")
        )

    def execute(self, context):
        props = context.scene.chat_companion_properties
        image = bpy.data.images.get(props.selected_blender_image)
        if image is None:
            self.report({"WARNING"}, "Selected Blender image not found")
            return {"CANCELLED"}

        try:
            payload = _payload_from_blender_image(image)
        except Exception as exc:
            self.report({"WARNING"}, f"Could not read Blender image: {exc}")
            return {"CANCELLED"}

        _add_image_attachment(
            context,
            image.name,
            f"bpy.data.images[{image.name!r}]",
            payload["media_type"],
            payload["data"],
        )
        self.report({"INFO"}, "Blender image added")
        return {"FINISHED"}


class CHAT_COMPANION_OT_paste_image_attachment(Operator):
    bl_idname = "chat_companion.paste_image_attachment"
    bl_label = "Paste Image"
    bl_description = "Paste an image or image path from the clipboard"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        props = context.scene.chat_companion_properties
        return getattr(props, "multimodal_enabled", False)

    def execute(self, context):
        try:
            payload, display_name, source = _payload_from_clipboard(context)
        except Exception as exc:
            self.report({"WARNING"}, f"No supported image in clipboard: {exc}")
            return {"CANCELLED"}

        _add_image_attachment(
            context,
            display_name,
            source,
            payload["media_type"],
            payload["data"],
        )
        self.report({"INFO"}, "Clipboard image added")
        return {"FINISHED"}


class CHAT_COMPANION_OT_remove_image_attachment(Operator):
    bl_idname = "chat_companion.remove_image_attachment"
    bl_label = "Remove Image"
    bl_description = "Remove the selected image attachment"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.chat_companion_image_attachments) > 0

    def execute(self, context):
        props = context.scene.chat_companion_properties
        items = context.scene.chat_companion_image_attachments
        index = min(props.selected_image_attachment_item, len(items) - 1)
        items.remove(index)
        _renumber(items)
        props.selected_image_attachment_item = max(0, min(index, len(items) - 1))
        self.report({"INFO"}, "Image removed")
        return {"FINISHED"}


class CHAT_COMPANION_OT_clear_image_attachments(Operator):
    bl_idname = "chat_companion.clear_image_attachments"
    bl_label = "Clear Images"
    bl_description = "Remove all image attachments"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.chat_companion_image_attachments) > 0

    def execute(self, context):
        context.scene.chat_companion_image_attachments.clear()
        context.scene.chat_companion_properties.selected_image_attachment_item = 0
        self.report({"INFO"}, "Images cleared")
        return {"FINISHED"}


def _payload_from_blender_image(image) -> dict[str, str]:
    filepath = bpy.path.abspath(getattr(image, "filepath", "") or "")
    if filepath and os.path.exists(filepath):
        return image_payload_from_file(filepath)

    packed = getattr(image, "packed_file", None)
    data = getattr(packed, "data", None)
    if data:
        suffix = Path(filepath).suffix.lower()
        media_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        return {
            "media_type": media_type,
            "data": base64.b64encode(bytes(data)).decode("ascii"),
        }

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path = tmp.name
    try:
        image.save_render(temp_path)
        return image_payload_from_file(temp_path)
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _payload_from_clipboard(context) -> tuple[dict[str, str], str, str]:
    clipboard_text = (context.window_manager.clipboard or "").strip().strip('"')
    if clipboard_text and os.path.exists(clipboard_text):
        payload = image_payload_from_file(clipboard_text)
        return payload, Path(clipboard_text).name, clipboard_text

    if os.name == "nt":
        file_path = _windows_clipboard_file_path()
        if file_path:
            payload = image_payload_from_file(file_path)
            return payload, Path(file_path).name, file_path

        png_path = _windows_clipboard_image_to_png()
        try:
            payload = image_payload_from_file(png_path)
            return payload, Path(png_path).name, "clipboard"
        finally:
            try:
                os.unlink(png_path)
            except OSError:
                pass

    raise RuntimeError("clipboard does not contain an image path or bitmap")


def _windows_clipboard_file_path() -> str:
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    CF_HDROP = 15
    user32.GetClipboardData.restype = ctypes.c_void_p

    if not user32.OpenClipboard(None):
        raise RuntimeError("could not open clipboard")
    try:
        handle = user32.GetClipboardData(CF_HDROP)
        if not handle:
            return ""
        count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
        for index in range(count):
            length = shell32.DragQueryFileW(handle, index, None, 0)
            buffer = ctypes.create_unicode_buffer(length + 1)
            shell32.DragQueryFileW(handle, index, buffer, length + 1)
            path = buffer.value
            try:
                image_payload_from_file(path)
                return path
            except Exception:
                continue
        return ""
    finally:
        user32.CloseClipboard()


def _windows_clipboard_image_to_png() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalSize.restype = ctypes.c_size_t
    CF_DIB = 8

    if not user32.OpenClipboard(None):
        raise RuntimeError("could not open clipboard")
    try:
        handle = user32.GetClipboardData(CF_DIB)
        if not handle:
            raise RuntimeError("no bitmap data")
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            raise RuntimeError("could not lock bitmap data")
        try:
            size = kernel32.GlobalSize(handle)
            dib = ctypes.string_at(ptr, size)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()

    bmp_path = _write_dib_as_bmp(dib)
    png_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    image = None
    try:
        image = bpy.data.images.load(bmp_path)
        image.save_render(png_path)
        return png_path
    finally:
        if image is not None:
            bpy.data.images.remove(image)
        try:
            os.unlink(bmp_path)
        except OSError:
            pass


def _write_dib_as_bmp(dib: bytes) -> str:
    if len(dib) < 4:
        raise RuntimeError("invalid bitmap data")
    header_size = struct.unpack_from("<I", dib, 0)[0]
    if len(dib) < header_size:
        raise RuntimeError("invalid bitmap header")
    bpp = struct.unpack_from("<H", dib, 14)[0] if header_size >= 16 else 24
    colors = 0
    if bpp <= 8 and header_size >= 36:
        colors = struct.unpack_from("<I", dib, 32)[0]
        if colors == 0:
            colors = 1 << bpp
    pixel_offset = 14 + header_size + colors * 4
    file_size = 14 + len(dib)
    bmp_header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, pixel_offset)
    bmp_path = tempfile.NamedTemporaryFile(suffix=".bmp", delete=False).name
    Path(bmp_path).write_bytes(bmp_header + dib)
    return bmp_path
