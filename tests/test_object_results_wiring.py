"""Static guards for object-results answer wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_finalization_stores_clean_answer_and_object_results():
    source = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "split_structured_results(final_text)" in source
    assert "merge_object_results_json(" in source
    assert "props.answer = visible_text" in source
    assert "props.answer_object_results = object_results" in source
    assert "answer=visible_text" in source
    assert "object_results=object_results" in source


def test_agent_collects_object_results_tool_output():
    source = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")
    prompt_source = (ROOT / "utils" / "chat_setup.py").read_text(encoding="utf-8")

    assert "self._collect_object_results(tc.name, result)" in source
    assert 'tool_name != "blender.object_results"' in source
    assert 'result.get("object_results_json", "")' in source
    assert "call blender.object_results" in prompt_source


def test_new_requests_and_errors_clear_object_results():
    source = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "answer_object_results=\"\"" in source
    assert "props.answer_object_results = \"\"" in source
    assert source.count("chat_properties.answer_object_results = \"\"") >= 4


def test_history_preserves_object_results():
    history_source = (ROOT / "operators" / "operator_history.py").read_text(
        encoding="utf-8"
    )
    item_source = (ROOT / "properties" / "item_history.py").read_text(encoding="utf-8")
    update_source = (ROOT / "properties" / "property_updates.py").read_text(
        encoding="utf-8"
    )

    assert "answer_object_results" in item_source
    assert "history_item.answer_object_results = self.object_results" in history_source
    assert '"answer_object_results": history_item.answer_object_results' in history_source
    assert '"answer_object_results": item.answer_object_results' in history_source
    assert "self.answer_object_results = history_item.answer_object_results" in update_source


def test_select_answer_object_has_view_layer_and_outliner_fallbacks():
    source = (ROOT / "operators" / "operator_answer_view.py").read_text(
        encoding="utf-8"
    )
    panel_source = (ROOT / "panels" / "panel_output.py").read_text(encoding="utf-8")

    assert "not self._is_in_view_layer(context, obj)" in source
    assert "searched = self._show_in_outliner_file_search(context, obj.name)" in source
    assert 'return {"FINISHED"} if searched else {"CANCELLED"}' in source
    assert 'self._set_outliner(context, "BLENDER_FILE", object_name)' in source
    assert 'self._set_outliner(context, "VIEW_LAYER", "")' in source
    assert "self._focus_active_in_outliner(context)" in source
    assert "bpy.ops.outliner.show_active()" in source
    assert "matched = False" in source
    assert "return matched" in source
    assert "except RuntimeError as exc" in source
    assert '"OUT_OF_VIEW_LAYER"' in panel_source
    assert '"UNSELECTABLE"' in panel_source


def test_select_answer_object_reincludes_excluded_collection():
    source = (ROOT / "operators" / "operator_answer_view.py").read_text(
        encoding="utf-8"
    )
    util_source = (ROOT / "utils" / "view_layer_utils.py").read_text(encoding="utf-8")

    assert "from ..utils.view_layer_utils import find_layer_collection_chain" in source
    assert "reincluded = self._reinclude_object(context, obj)" in source
    assert "layer_collection.exclude = False" in source
    assert "def find_layer_collection_chain(" in util_source


def test_object_results_keep_object_names_clickable_when_mesh_data_names_overlap():
    panel_source = (ROOT / "panels" / "panel_output.py").read_text(encoding="utf-8")
    skill_source = (ROOT / "builtin_skills" / "blender_object_results.py").read_text(
        encoding="utf-8"
    )

    assert "mesh_data_name_owners" not in panel_source
    assert '"AMBIGUOUS"' not in panel_source
    assert "mesh_data_name" in skill_source
    assert "object_name" in skill_source


def run():
    test_agent_finalization_stores_clean_answer_and_object_results()
    test_agent_collects_object_results_tool_output()
    test_new_requests_and_errors_clear_object_results()
    test_history_preserves_object_results()
    test_select_answer_object_has_view_layer_and_outliner_fallbacks()
    test_select_answer_object_reincludes_excluded_collection()
    test_object_results_keep_object_names_clickable_when_mesh_data_names_overlap()
    print("test_object_results_wiring OK")
    return True


if __name__ == "__main__":
    run()
