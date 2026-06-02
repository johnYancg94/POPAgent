"""Pure Python tests for live agent progress events."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "progress", ROOT / "agent_core" / "progress.py"
)
progress = importlib.util.module_from_spec(spec)
sys.modules["progress"] = progress
spec.loader.exec_module(progress)


AgentProgressEvent = progress.AgentProgressEvent
ProgressSink = progress.ProgressSink
tool_status_text = progress.tool_status_text


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_tool_status_text_maps_common_blender_tools():
    assert tool_status_text("blender.api_search") == "查询 Blender API 文档"
    assert tool_status_text("dev.run_python") == "执行 Python 脚本"
    assert tool_status_text("blender.material.inspect_nodes") == "处理材质节点"
    assert tool_status_text("blender.geometry_nodes.inspect") == "处理 Geometry Nodes"
    assert tool_status_text("blender.scene_info") == "查看当前 Blender 场景信息"
    assert tool_status_text("custom.tool") == "调用工具：custom.tool"


def test_progress_sink_throttles_stream_text_and_flushes_final_value():
    clock = _Clock()
    text_updates = []
    sink = ProgressSink(
        status_writer=lambda _text, _icon: None,
        text_writer=text_updates.append,
        min_text_interval=0.2,
        monotonic=clock,
    )

    sink.emit(AgentProgressEvent(kind="model_stream_text", text_delta="a"))
    clock.now = 0.05
    sink.emit(AgentProgressEvent(kind="model_stream_text", text_delta="b"))
    clock.now = 0.10
    sink.emit(AgentProgressEvent(kind="model_stream_text", text_delta="c"))

    assert text_updates == []

    clock.now = 0.25
    sink.emit(AgentProgressEvent(kind="model_stream_text", text_delta="d"))

    assert text_updates == ["abcd"]

    sink.emit(AgentProgressEvent(kind="model_stream_text", text_delta="e"))
    sink.flush_text()

    assert text_updates == ["abcd", "abcde"]


def test_progress_sink_shows_tool_call_status():
    statuses = []
    sink = ProgressSink(
        status_writer=lambda text, icon: statuses.append((text, icon)),
        text_writer=lambda _text: None,
    )

    sink.emit(AgentProgressEvent(kind="tool_call_start", tool_name="blender.api_search"))
    sink.emit(AgentProgressEvent(kind="tool_call_finish", tool_name="blender.api_search", duration_ms=123))

    assert statuses == [
        ("准备调用：查询 Blender API 文档", "TOOL_SETTINGS"),
        ("完成：查询 Blender API 文档（123 ms）", "CHECKMARK"),
    ]


def test_progress_sink_does_not_flush_empty_text():
    text_updates = []
    sink = ProgressSink(
        status_writer=lambda _text, _icon: None,
        text_writer=text_updates.append,
    )

    sink.flush_text()

    assert text_updates == []


def run():
    test_tool_status_text_maps_common_blender_tools()
    test_progress_sink_throttles_stream_text_and_flushes_final_value()
    test_progress_sink_shows_tool_call_status()
    test_progress_sink_does_not_flush_empty_text()
    print("test_agent_progress OK")
    return True


if __name__ == "__main__":
    run()
