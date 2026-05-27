"""Pure Python tests for Blender API documentation search helpers."""

from pathlib import Path
import importlib.util
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "blender_api_docs", ROOT / "builtin_skills" / "blender_api_docs.py"
)
blender_api_docs = importlib.util.module_from_spec(spec)
sys.modules["blender_api_docs"] = blender_api_docs
spec.loader.exec_module(blender_api_docs)


def test_default_docs_base_uses_runtime_minor_version():
    assert blender_api_docs.default_docs_base_url((5, 1, 0)) == (
        "https://docs.blender.org/api/5.1/"
    )


def test_candidate_paths_include_common_api_shapes():
    paths = blender_api_docs.candidate_paths("bpy.ops.object.modifier_apply")

    assert "bpy.ops.object.html" in paths


def test_search_local_docs_finds_matching_html_title_and_snippet():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        page = root / "bpy.types.Operator.html"
        page.write_text(
            """
            <html>
              <head><title>bpy.types.Operator - Blender Python API</title></head>
              <body>
                <h1>bpy.types.Operator</h1>
                <p>Base class for operators. Modal operators can define modal.</p>
              </body>
            </html>
            """,
            encoding="utf-8",
        )

        result = blender_api_docs.search_local_docs(
            str(root), "bpy.types.Operator modal", limit=3
        )

    assert result["ok"] is True
    assert result["source"] == "local"
    assert result["results"][0]["title"] == "bpy.types.Operator - Blender Python API"
    assert result["results"][0]["path"].endswith("bpy.types.Operator.html")
    assert "Modal operators" in result["results"][0]["snippet"]


def test_handler_uses_local_docs_path_when_available():
    class _Prefs:
        blender_api_docs_path = ""
        blender_api_docs_url = "https://docs.blender.org/api/5.1/"
        blender_api_docs_prefer_local = True

    class _Addon:
        preferences = _Prefs()

    class _Preferences:
        addons = {"POPAgent": _Addon()}

    class _Context:
        preferences = _Preferences()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "bpy.app.timers.html").write_text(
            "<html><title>bpy.app.timers</title><body>Timer registration API.</body></html>",
            encoding="utf-8",
        )
        _Prefs.blender_api_docs_path = str(root)

        result = blender_api_docs._handler_api_search(
            context=_Context(),
            query="bpy.app.timers",
            limit=2,
            use_online=False,
        )

    assert result["ok"] is True
    assert result["results"][0]["title"] == "bpy.app.timers"


def run():
    test_default_docs_base_uses_runtime_minor_version()
    test_candidate_paths_include_common_api_shapes()
    test_search_local_docs_finds_matching_html_title_and_snippet()
    test_handler_uses_local_docs_path_when_available()
    print("test_blender_api_docs OK")
    return True


if __name__ == "__main__":
    run()
