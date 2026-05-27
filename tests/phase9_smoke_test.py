"""Phase 9 smoke test: streaming + tool_call assembly.

Feeds canonical SSE-style lines into each provider's StreamParser and asserts
that finalize() yields the correct text, tool_calls, and finish_reason.

Run from Blender's scripting console:

    import importlib, sys
    for mod in list(sys.modules):
        if mod.startswith("POPAgent.tests.phase9_smoke_test"):
            del sys.modules[mod]
    from POPAgent.tests import phase9_smoke_test
    phase9_smoke_test.run()
"""

from POPAgent.providers import OpenAICompatProvider, AnthropicProvider


# --- OpenAI / DeepSeek streaming -------------------------------------------

def _openai_chunks():
    """Realistic streaming sequence: text delta + multi-fragment tool_call."""
    return [
        # Text fragment 1
        'data: {"choices":[{"index":0,"delta":{"content":"Hello"}}]}',
        # Text fragment 2
        'data: {"choices":[{"index":0,"delta":{"content":" world"}}]}',
        # Tool call begins: id+name on first fragment
        'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_abc","type":"function","function":{"name":"select_object","arguments":""}}]}}]}',
        # Tool call args fragment 1
        'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"name"}}]}}]}',
        # Tool call args fragment 2
        'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\":\\"Cube\\"}"}}]}}]}',
        # Finish chunk
        'data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}',
        'data: [DONE]',
    ]


def test_openai_stream():
    provider = OpenAICompatProvider("openai")
    parser = provider.create_stream_parser()

    text_events = []
    tool_events = []
    done_events = []
    for line in _openai_chunks():
        for ev in parser.feed_line(line):
            if ev.kind == "text":
                text_events.append(ev.payload)
            elif ev.kind == "tool_call":
                tool_events.append(ev.payload)
            elif ev.kind == "done":
                done_events.append(ev.payload)

    resp = parser.finalize()

    assert text_events == ["Hello", " world"], f"text events: {text_events}"
    assert resp.text == "Hello world", f"final text: {resp.text!r}"
    assert len(resp.tool_calls) == 1, f"tool_calls: {resp.tool_calls}"
    tc = resp.tool_calls[0]
    assert tc.id == "call_abc", tc.id
    assert tc.name == "select_object", tc.name
    assert tc.arguments == {"name": "Cube"}, tc.arguments
    assert resp.finish_reason == "tool_calls", resp.finish_reason
    # tool_call should have been emitted live when finish_reason arrived.
    assert len(tool_events) == 1, tool_events
    return "openai_stream OK"


# --- Anthropic Claude streaming --------------------------------------------

def _claude_lines():
    """SSE protocol: each event is `event:` line then `data:` line."""
    return [
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_1","model":"claude"}}',
        # Block 0: text
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi"}}',
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" there"}}',
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":0}',
        # Block 1: tool_use
        "event: content_block_start",
        'data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"tool_xyz","name":"set_active","input":{}}}',
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"name"}}',
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"\\":\\"Sphere\\"}"}}',
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":1}',
        # Final
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
        "event: message_stop",
        'data: {"type":"message_stop"}',
    ]


def test_claude_stream():
    provider = AnthropicProvider()
    parser = provider.create_stream_parser()

    text_events = []
    tool_events = []
    done_events = []
    for line in _claude_lines():
        for ev in parser.feed_line(line):
            if ev.kind == "text":
                text_events.append(ev.payload)
            elif ev.kind == "tool_call":
                tool_events.append(ev.payload)
            elif ev.kind == "done":
                done_events.append(ev.payload)

    resp = parser.finalize()

    assert text_events == ["Hi", " there"], f"text events: {text_events}"
    assert resp.text == "Hi there", f"final text: {resp.text!r}"
    assert len(resp.tool_calls) == 1, f"tool_calls: {resp.tool_calls}"
    tc = resp.tool_calls[0]
    assert tc.id == "tool_xyz", tc.id
    assert tc.name == "set_active", tc.name
    assert tc.arguments == {"name": "Sphere"}, tc.arguments
    assert resp.finish_reason == "tool_use", resp.finish_reason
    # tool_call event emitted at content_block_stop time.
    assert len(tool_events) == 1, tool_events
    # message_stop emitted a done event.
    assert done_events == ["tool_use"], done_events
    return "claude_stream OK"


# --- Edge cases ------------------------------------------------------------

def test_openai_text_only():
    """Pure text response (no tool calls)."""
    provider = OpenAICompatProvider("deepseek")
    parser = provider.create_stream_parser()
    lines = [
        'data: {"choices":[{"index":0,"delta":{"content":"All "}}]}',
        'data: {"choices":[{"index":0,"delta":{"content":"good."}}]}',
        'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
        'data: [DONE]',
    ]
    for line in lines:
        parser.feed_line(line)
    resp = parser.finalize()
    assert resp.text == "All good.", resp.text
    assert resp.tool_calls == [], resp.tool_calls
    assert resp.finish_reason == "stop", resp.finish_reason
    return "openai_text_only OK"


def test_claude_text_only():
    provider = AnthropicProvider()
    parser = provider.create_stream_parser()
    lines = [
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"OK"}}',
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":0}',
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
        "event: message_stop",
        'data: {"type":"message_stop"}',
    ]
    for line in lines:
        parser.feed_line(line)
    resp = parser.finalize()
    assert resp.text == "OK", resp.text
    assert resp.tool_calls == [], resp.tool_calls
    assert resp.finish_reason == "end_turn", resp.finish_reason
    return "claude_text_only OK"


def run():
    tests = [
        test_openai_stream,
        test_claude_stream,
        test_openai_text_only,
        test_claude_text_only,
    ]
    results = []
    failed = 0
    for t in tests:
        try:
            results.append(t())
        except AssertionError as e:
            results.append(f"{t.__name__} FAIL: {e}")
            failed += 1
        except Exception as e:
            results.append(f"{t.__name__} ERROR: {type(e).__name__}: {e}")
            failed += 1
    for r in results:
        print(r)
    print(f"\n[phase9] {len(tests) - failed}/{len(tests)} tests passed.")
    return failed == 0


if __name__ == "__main__":
    run()
