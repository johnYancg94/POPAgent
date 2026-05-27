"""Pure Python tests for multimodal image input helpers."""

from pathlib import Path
import base64
import importlib.util
import sys
import tempfile
import types


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "vision_inputs", ROOT / "agent_core" / "vision_inputs.py"
)
vision_inputs = importlib.util.module_from_spec(spec)
sys.modules["vision_inputs"] = vision_inputs


class _Item:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _load_module():
    spec.loader.exec_module(vision_inputs)
    return vision_inputs


def test_image_payload_from_file_encodes_supported_image():
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.png"
        path.write_bytes(b"png-bytes")

        payload = module.image_payload_from_file(str(path))

    assert payload == {
        "media_type": "image/png",
        "data": base64.b64encode(b"png-bytes").decode("ascii"),
    }


def test_image_payload_from_file_rejects_unsupported_extension():
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "notes.txt"
        path.write_text("not image", encoding="utf-8")

        try:
            module.image_payload_from_file(str(path))
        except ValueError as exc:
            assert "Unsupported image type" in str(exc)
        else:
            raise AssertionError("expected unsupported extension to fail")


def test_collect_enabled_image_payloads_skips_disabled_items():
    module = _load_module()
    items = [
        _Item(is_enabled=True, media_type="image/png", image_base64="aaa"),
        _Item(is_enabled=False, media_type="image/jpeg", image_base64="bbb"),
        _Item(is_enabled=True, media_type="", image_base64="ccc"),
    ]

    assert module.collect_enabled_image_payloads(items) == [
        {"media_type": "image/png", "data": "aaa"}
    ]


def run():
    test_image_payload_from_file_encodes_supported_image()
    test_image_payload_from_file_rejects_unsupported_extension()
    test_collect_enabled_image_payloads_skips_disabled_items()
    print("test_vision_inputs OK")
    return True


if __name__ == "__main__":
    run()
