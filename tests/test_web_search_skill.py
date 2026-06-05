"""Pure Python tests for the Tavily web search skill."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "web_search", ROOT / "builtin_skills" / "web_search.py"
)
web_search = importlib.util.module_from_spec(spec)
sys.modules["web_search"] = web_search
spec.loader.exec_module(web_search)


def test_empty_query_is_rejected_before_network():
    result = web_search.tavily_search(
        api_key="tvly-test",
        endpoint="https://api.tavily.com/search",
        query=" ",
    )

    assert result["ok"] is False
    assert result["error_kind"] == "empty_query"


def test_missing_api_key_is_clear():
    result = web_search.tavily_search(
        api_key="",
        endpoint="https://api.tavily.com/search",
        query="Blender 5.1",
    )

    assert result["ok"] is False
    assert result["error_kind"] == "missing_api_key"


def test_tavily_payload_is_bounded_and_normalized():
    captured = {}

    def fake_fetcher(endpoint, headers, payload, timeout):
        captured.update({
            "endpoint": endpoint,
            "headers": headers,
            "payload": payload,
            "timeout": timeout,
        })
        return {
            "query": payload["query"],
            "answer": "Short answer",
            "results": [
                {
                    "title": " Result title ",
                    "url": "https://example.com",
                    "content": " ".join(["chunk"] * 400),
                    "score": 0.9,
                    "favicon": "https://example.com/favicon.ico",
                }
            ],
            "response_time": 1.2,
            "usage": {"credits": 1},
            "request_id": "req_123",
        }

    result = web_search.tavily_search(
        api_key="tvly-test",
        endpoint="https://api.tavily.com/search",
        query="Blender release notes",
        limit=20,
        search_depth="unknown",
        topic="news",
        time_range="week",
        fetcher=fake_fetcher,
    )

    assert result["ok"] is True
    assert captured["payload"]["max_results"] == 10
    assert captured["payload"]["search_depth"] == "basic"
    assert captured["payload"]["topic"] == "news"
    assert captured["payload"]["time_range"] == "week"
    assert captured["payload"]["include_answer"] == "basic"
    assert captured["headers"]["Authorization"] == "Bearer tvly-test"
    assert result["results"][0]["title"] == "Result title"
    assert len(result["results"][0]["content"]) <= 1200


def test_handler_reads_preferences_from_context_dict():
    result = web_search._handler_web_search(
        context={"web_search_enabled": False, "tavily_api_key": "tvly-test"},
        query="Blender",
    )

    assert result["ok"] is False
    assert result["error_kind"] == "search_disabled"


def test_skill_schema_is_read_only_and_uses_background_prefs():
    skill = web_search.WEB_SEARCH

    assert skill["name"] == "web.search"
    assert skill["owner"] == "builtin"
    assert skill["metadata"]["modifies_scene"] is False
    assert skill["metadata"]["requires_confirmation"] == "never"
    assert "tavily_api_key" in skill["metadata"]["background_prefs_fields"]


def run():
    test_empty_query_is_rejected_before_network()
    test_missing_api_key_is_clear()
    test_tavily_payload_is_bounded_and_normalized()
    test_handler_reads_preferences_from_context_dict()
    test_skill_schema_is_read_only_and_uses_background_prefs()
    print("test_web_search_skill OK")
    return True


if __name__ == "__main__":
    run()
