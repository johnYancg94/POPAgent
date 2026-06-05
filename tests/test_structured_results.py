"""Pure Python tests for hidden POPAgent structured result blocks."""

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.structured_results import (
    merge_object_results_json,
    object_result_status,
    object_results_to_json,
    split_structured_results,
)


def test_extracts_hidden_object_results_and_cleans_answer():
    answer = """有的，找到 2 个猴头。

```popagent-results
{"version": 1, "objects": [{"name": "Suzanne", "type": "MESH", "location": [-6.7612, -11.33, 4.07], "note": "猴头"}, {"name": "猴头.001"}]}
```"""

    visible, results_json = split_structured_results(answer)
    results = json.loads(results_json)

    assert visible == "有的，找到 2 个猴头。"
    assert results["version"] == 1
    assert results["objects"] == [
        {"name": "Suzanne", "type": "MESH", "location": [-6.761, -11.33, 4.07], "note": "猴头"},
        {"name": "猴头.001"},
    ]


def test_invalid_result_block_is_hidden_without_controls():
    answer = """Readable answer.

```popagent-results
not json
```"""

    visible, results_json = split_structured_results(answer)

    assert visible == "Readable answer."
    assert results_json == ""


def test_missing_result_block_is_noop():
    visible, results_json = split_structured_results("Only text")

    assert visible == "Only text"
    assert results_json == ""


def test_object_result_status_reports_missing():
    assert object_result_status({"name": "Suzanne.001"}, {"Suzanne.001"}) == "FOUND"
    assert object_result_status({"name": "Suzanne.002"}, {"Suzanne.001"}) == "MISSING"
    assert (
        object_result_status(
            {"name": "Plane.4114"},
            {"Plane.4114"},
            {"Suzanne"},
        )
        == "OUT_OF_VIEW_LAYER"
    )
    assert (
        object_result_status(
            {"name": "Cube"},
            {"Cube"},
            {"Cube"},
            {"Cube"},
        )
        == "UNSELECTABLE"
    )
    assert (
        object_result_status(
            {"name": "aa"},
            {"bb"},
            {"bb"},
            set(),
        )
        == "MISSING"
    )
    assert (
        object_result_status(
            {"name": "aa"},
            {"aa", "bb"},
            {"aa", "bb"},
            set(),
        )
        == "FOUND"
    )


def test_object_name_is_preferred_identity_over_display_name():
    payload = object_results_to_json(
        [
            {
                "name": "mesh data label",
                "object_name": "Cube.001",
                "mesh_data_name": "mesh data label",
                "type": "MESH",
            }
        ]
    )

    result = json.loads(payload)["objects"][0]

    assert result["name"] == "Cube.001"
    assert result["object_name"] == "Cube.001"
    assert result["mesh_data_name"] == "mesh data label"


def test_object_results_json_merges_and_deduplicates():
    primary = object_results_to_json(
        [
            {"name": "Suzanne", "type": "MESH"},
            {"name": "Suzanne.001", "type": "MESH"},
        ]
    )
    fallback = object_results_to_json(
        [
            {"name": "Suzanne", "type": "MESH", "note": "duplicate"},
            {"name": "Cube", "type": "MESH"},
        ]
    )

    merged = json.loads(merge_object_results_json(primary, fallback))

    assert [obj["name"] for obj in merged["objects"]] == [
        "Suzanne",
        "Suzanne.001",
        "Cube",
    ]


def run():
    test_extracts_hidden_object_results_and_cleans_answer()
    test_invalid_result_block_is_hidden_without_controls()
    test_missing_result_block_is_noop()
    test_object_result_status_reports_missing()
    test_object_name_is_preferred_identity_over_display_name()
    test_object_results_json_merges_and_deduplicates()
    print("test_structured_results OK")
    return True


if __name__ == "__main__":
    run()
