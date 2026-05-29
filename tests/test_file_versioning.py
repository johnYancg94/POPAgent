"""Pure Python tests for .blend incremental versioning helpers."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "file_versioning", ROOT / "agent_core" / "file_versioning.py"
)
file_versioning = importlib.util.module_from_spec(spec)
sys.modules["file_versioning"] = file_versioning
spec.loader.exec_module(file_versioning)

next_incremental_path = file_versioning.next_incremental_path
ensure_blend_extension = file_versioning.ensure_blend_extension


def test_adds_counter_when_absent():
    assert next_incremental_path("/proj/char_chef.blend").endswith("char_chef_001.blend")


def test_bumps_existing_counter():
    assert next_incremental_path("/proj/char_chef_001.blend").endswith("char_chef_002.blend")


def test_preserves_zero_padding_width():
    assert next_incremental_path("/proj/char_009.blend").endswith("char_010.blend")
    assert next_incremental_path("/proj/char_099.blend").endswith("char_100.blend")


def test_non_counter_suffix_is_not_treated_as_version():
    # _v3 is only 1 digit after the v, not a >=3 digit counter
    result = next_incremental_path("/proj/char_v3.blend")
    assert result.endswith("char_v3_001.blend")


def test_preserves_directory():
    result = next_incremental_path("/a/b/c/model.blend")
    assert result.replace("\\", "/").startswith("/a/b/c/")


def test_ensure_blend_extension_appends_when_missing():
    assert ensure_blend_extension("/proj/scene") == "/proj/scene.blend"


def test_ensure_blend_extension_leaves_existing():
    assert ensure_blend_extension("/proj/scene.blend") == "/proj/scene.blend"


def run():
    test_adds_counter_when_absent()
    test_bumps_existing_counter()
    test_preserves_zero_padding_width()
    test_non_counter_suffix_is_not_treated_as_version()
    test_preserves_directory()
    test_ensure_blend_extension_appends_when_missing()
    test_ensure_blend_extension_leaves_existing()
    print("test_file_versioning OK")
    return True


if __name__ == "__main__":
    run()
