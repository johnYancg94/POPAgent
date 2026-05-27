"""Pure Python regression test for the viewport screenshot skill."""

from pathlib import Path
import base64
import importlib.util
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake"


def _load_blender_query_with_fake_bpy():
    fake_bpy = types.SimpleNamespace()

    def screenshot(**kwargs):
        unexpected = set(kwargs) - {"filepath"}
        if unexpected:
            name = sorted(unexpected)[0]
            raise TypeError(
                f'Converting py args to operator properties:: keyword "{name}" unrecognized'
            )
        Path(kwargs["filepath"]).write_bytes(PNG_BYTES)
        return {"FINISHED"}

    fake_bpy.ops = types.SimpleNamespace(
        screen=types.SimpleNamespace(screenshot=screenshot)
    )
    sys.modules["bpy"] = fake_bpy

    spec = importlib.util.spec_from_file_location(
        "blender_query", ROOT / "builtin_skills" / "blender_query.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["blender_query"] = module
    spec.loader.exec_module(module)
    return module


def test_viewport_screenshot_uses_blender_5_screenshot_signature():
    module = _load_blender_query_with_fake_bpy()

    result = module._handler_viewport_screenshot()

    assert result == {
        "ok": True,
        "image_base64": base64.b64encode(PNG_BYTES).decode("utf-8"),
        "format": "png",
    }


def run():
    test_viewport_screenshot_uses_blender_5_screenshot_signature()
    print("test_viewport_screenshot OK")
    return True


if __name__ == "__main__":
    run()
