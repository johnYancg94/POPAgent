"""Tavily-backed web search skill."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_DEFAULT_ENDPOINT = "https://api.tavily.com/search"
_DEFAULT_TIMEOUT = 20
_MAX_CONTENT_CHARS = 1200
_SEARCH_DEPTHS = {"basic", "advanced", "fast", "ultra-fast"}
_TOPICS = {"general", "news", "finance"}
_TIME_RANGES = {"day", "week", "month", "year", "d", "w", "m", "y"}


def tavily_search(
    *,
    api_key: str,
    endpoint: str,
    query: str,
    limit: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    time_range: str = "",
    fetcher: Callable[[str, dict, dict, int], dict] | None = None,
) -> dict:
    query = (query or "").strip()
    if not query:
        return _error("empty_query", "No query provided.")

    api_key = (api_key or "").strip()
    if not api_key:
        return _error("missing_api_key", "Tavily API key is not configured.")

    endpoint = (endpoint or _DEFAULT_ENDPOINT).strip() or _DEFAULT_ENDPOINT
    limit = max(1, min(int(limit or 5), 10))
    search_depth = search_depth if search_depth in _SEARCH_DEPTHS else "basic"
    topic = topic if topic in _TOPICS else "general"
    time_range = (time_range or "").strip()

    payload = {
        "query": query,
        "search_depth": search_depth,
        "topic": topic,
        "max_results": limit,
        "include_answer": "basic",
        "include_raw_content": False,
        "include_favicon": True,
        "include_usage": True,
    }
    if time_range in _TIME_RANGES:
        payload["time_range"] = time_range

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "POPAgent Tavily web search",
    }

    try:
        data = (fetcher or _post_json)(endpoint, headers, payload, _DEFAULT_TIMEOUT)
    except HTTPError as exc:
        return _error("http_error", f"Tavily API returned HTTP {exc.code}.")
    except (URLError, TimeoutError, OSError) as exc:
        return _error("network_error", f"Tavily request failed: {exc}")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return _error("invalid_response", f"Tavily response was not valid JSON: {exc}")

    return _normalize_response(data, query, limit)


def _handler_web_search(
    context=None,
    query: str = "",
    limit: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    time_range: str = "",
) -> dict:
    prefs = _get_prefs(context)
    if prefs and not bool(getattr(prefs, "web_search_enabled", True)):
        return _error("search_disabled", "Web search is disabled in POPAgent preferences.")

    api_key = getattr(prefs, "tavily_api_key", "") if prefs else ""
    endpoint = getattr(prefs, "tavily_endpoint", _DEFAULT_ENDPOINT) if prefs else _DEFAULT_ENDPOINT
    return tavily_search(
        api_key=api_key,
        endpoint=endpoint,
        query=query,
        limit=limit,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
    )


def _post_json(endpoint: str, headers: dict, payload: dict, timeout: int) -> dict:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(2_000_000)
    return json.loads(raw.decode("utf-8", errors="replace"))


def _normalize_response(data: dict, query: str, limit: int) -> dict:
    if not isinstance(data, dict):
        return _error("invalid_response", "Tavily response was not a JSON object.")

    results = []
    for item in (data.get("results") or [])[:limit]:
        if not isinstance(item, dict):
            continue
        content = _truncate(_collapse_ws(str(item.get("content") or "")), _MAX_CONTENT_CHARS)
        results.append({
            "title": _collapse_ws(str(item.get("title") or "")),
            "url": str(item.get("url") or ""),
            "content": content,
            "score": item.get("score"),
            "favicon": item.get("favicon"),
        })

    return {
        "ok": bool(results or data.get("answer")),
        "source": "tavily",
        "query": data.get("query") or query,
        "answer": _truncate(_collapse_ws(str(data.get("answer") or "")), _MAX_CONTENT_CHARS),
        "results": results,
        "response_time": data.get("response_time"),
        "usage": data.get("usage") or {},
        "request_id": data.get("request_id"),
    }


def _get_prefs(context):
    if isinstance(context, dict):
        return SimpleNamespace(**context)

    if context is None:
        try:
            import bpy

            context = bpy.context
        except Exception:
            return None

    addons = getattr(getattr(context, "preferences", None), "addons", None)
    if addons is None:
        return None

    for key in ("POPAgent", __package__.split(".")[0] if __package__ else ""):
        if not key:
            continue
        try:
            return addons[key].preferences
        except Exception:
            pass

    try:
        iterable = addons.values()
    except Exception:
        iterable = addons
    for addon in iterable:
        prefs = getattr(addon, "preferences", None)
        if prefs and hasattr(prefs, "tavily_api_key"):
            return prefs
    return None


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _error(kind: str, message: str) -> dict:
    return {"ok": False, "source": "tavily", "error_kind": kind, "error": message, "results": []}


WEB_SEARCH = {
    "name": "web.search",
    "description": (
        "Search the web with Tavily for current or external information. Use "
        "when the user asks for latest information, news, prices, product "
        "details, external documentation, or online sources."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Web search query.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
            },
            "search_depth": {
                "type": "string",
                "description": "Tavily search depth.",
                "enum": ["basic", "advanced", "fast", "ultra-fast"],
                "default": "basic",
            },
            "topic": {
                "type": "string",
                "description": "Tavily search topic.",
                "enum": ["general", "news", "finance"],
                "default": "general",
            },
            "time_range": {
                "type": "string",
                "description": "Optional recency filter: day, week, month, year, d, w, m, or y.",
                "enum": ["", "day", "week", "month", "year", "d", "w", "m", "y"],
                "default": "",
            },
        },
        "required": ["query"],
    },
    "owner": "builtin",
    "handler": _handler_web_search,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "requires_main_thread": False,
        "background_context": "addon_preferences",
        "background_prefs_fields": [
            "web_search_enabled",
            "tavily_api_key",
            "tavily_endpoint",
        ],
    },
}
