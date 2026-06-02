"""Search Blender Python API documentation.

The public skill is read-only. It prefers the configured official online docs,
with an optional local HTML docs path as a fallback or explicit local source.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


_DEFAULT_TIMEOUT = 6
_MAX_PAGE_BYTES = 700_000


def default_docs_base_url(version: tuple[int, int, int] | None = None) -> str:
    if version is None:
        try:
            import bpy

            version = bpy.app.version
        except Exception:
            version = (5, 1, 0)
    return f"https://docs.blender.org/api/{version[0]}.{version[1]}/"


def candidate_paths(query: str) -> list[str]:
    query = (query or "").strip()
    candidates: list[str] = []

    def add(path: str) -> None:
        if path and path not in candidates:
            candidates.append(path)

    dotted = re.findall(r"\b(?:bpy|bmesh|mathutils|gpu|blf|aud|bl_math)(?:\.[A-Za-z_][\w]*)+\b", query)
    for name in dotted:
        if name.startswith("bpy.ops."):
            parts = name.split(".")
            if len(parts) >= 3:
                add(".".join(parts[:3]) + ".html")
        add(name + ".html")

    words = _tokens(query)
    for word in words:
        if "." in word:
            add(word + ".html")
    add("genindex.html")
    add("py-modindex.html")
    return candidates


def search_local_docs(root: str, query: str, limit: int = 5) -> dict:
    docs_root = Path(root).expanduser()
    if not docs_root.exists() or not docs_root.is_dir():
        return _error("local_docs_missing", f"Local docs path not found: {root}")

    tokens = _tokens(query)
    scored = []
    candidate_names = {Path(path).name.lower() for path in candidate_paths(query)}

    for path in docs_root.rglob("*.html"):
        path_name = path.name.lower()
        stem = path.stem.lower()
        file_score = 0
        if path_name in candidate_names:
            file_score += 80
        file_score += sum(12 for token in tokens if token in stem)
        if file_score <= 0 and tokens:
            continue

        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")[:_MAX_PAGE_BYTES]
        except OSError:
            continue

        title = _extract_title(raw) or path.stem
        text = _html_to_text(raw)
        score = file_score + _score_text(title, tokens) * 4 + _score_text(text, tokens)
        if score <= 0:
            continue
        scored.append((score, {
            "title": title,
            "path": str(path),
            "url": path.as_uri(),
            "snippet": _snippet(text, tokens),
        }))

    return _result("local", query, scored, limit)


def search_online_docs(
    base_url: str,
    query: str,
    limit: int = 5,
    fetcher: Callable[[str], str] | None = None,
) -> dict:
    base_url = _normalize_base_url(base_url or default_docs_base_url())
    fetch = fetcher or _fetch_url
    tokens = _tokens(query)
    scored = []
    urls: list[str] = []

    def add_url(path_or_url: str) -> None:
        url = path_or_url if path_or_url.startswith(("http://", "https://")) else urljoin(base_url, path_or_url)
        if url not in urls:
            urls.append(url)

    for path in candidate_paths(query):
        add_url(path)

    for index_path in ("genindex.html", "py-modindex.html"):
        index_url = urljoin(base_url, index_path)
        try:
            index_html = fetch(index_url)
        except Exception:
            continue
        for href, label in _extract_links(index_html):
            label_text = f"{href} {label}".lower()
            if all(token in label_text for token in tokens[:3]) or any(token in label_text for token in tokens):
                add_url(href)
                if len(urls) >= limit * 4 + 8:
                    break

    for url in urls[: limit * 5 + 10]:
        try:
            raw = fetch(url)
        except Exception:
            continue
        title = _extract_title(raw) or url.rsplit("/", 1)[-1]
        text = _html_to_text(raw)
        score = _score_text(title, tokens) * 4 + _score_text(url, tokens) * 3 + _score_text(text, tokens)
        if score <= 0:
            continue
        scored.append((score, {
            "title": title,
            "url": url,
            "path": url,
            "snippet": _snippet(text, tokens),
        }))

    if not scored:
        return _error(
            "no_online_results",
            f"No Blender API docs results found at {base_url}",
            source="online",
        )
    return _result("online", query, scored, limit)


def _handler_api_search(
    context=None,
    query: str = "",
    limit: int = 5,
    use_online: bool = True,
) -> dict:
    if not query.strip():
        return _error("empty_query", "No query provided.")

    limit = max(1, min(int(limit or 5), 10))
    prefs = _get_prefs(context)
    local_path = getattr(prefs, "blender_api_docs_path", "") if prefs else ""
    base_url = getattr(prefs, "blender_api_docs_url", "") if prefs else ""
    prefer_local = bool(getattr(prefs, "blender_api_docs_prefer_local", False)) if prefs else False
    base_url = _normalize_base_url(base_url or default_docs_base_url())

    if prefer_local and local_path:
        local = search_local_docs(local_path, query, limit)
        if local.get("ok") or not use_online:
            return local

    if use_online:
        online = search_online_docs(base_url, query, limit)
        if online.get("ok"):
            return online
        if local_path:
            local = search_local_docs(local_path, query, limit)
            if local.get("ok"):
                local["fallback_reason"] = online.get("error")
                return local
        return online

    if local_path:
        return search_local_docs(local_path, query, limit)
    return _error("docs_source_unavailable", "No local docs path configured and online search is disabled.")


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
        if prefs and hasattr(prefs, "blender_api_docs_url"):
            return prefs
    return None


def _normalize_base_url(value: str) -> str:
    value = (value or "").strip() or default_docs_base_url()
    if not value.endswith("/"):
        value += "/"
    return value


def _fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": "POPAgent Blender API docs search"})
    with urlopen(request, timeout=_DEFAULT_TIMEOUT) as response:
        data = response.read(_MAX_PAGE_BYTES)
    return data.decode("utf-8", errors="ignore")


def _tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z_][\w.]*", text or "")
        if len(token) > 1
    ]


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    if not match:
        return ""
    return _collapse_ws(_strip_tags(match.group(1)))


def _html_to_text(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.I | re.S)
    return _collapse_ws(_strip_tags(html))


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "")


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def _score_text(text: str, tokens: list[str]) -> int:
    low = (text or "").lower()
    return sum(low.count(token) for token in tokens)


def _snippet(text: str, tokens: list[str], width: int = 360) -> str:
    if not text:
        return ""
    low = text.lower()
    positions = [low.find(token) for token in tokens if low.find(token) >= 0]
    start = max(0, min(positions) - 90) if positions else 0
    return text[start:start + width].strip()


def _result(source: str, query: str, scored: list[tuple[int, dict]], limit: int) -> dict:
    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    seen = set()
    for score, item in scored:
        key = item.get("url") or item.get("path")
        if key in seen:
            continue
        seen.add(key)
        item["score"] = score
        results.append(item)
        if len(results) >= limit:
            break
    return {"ok": bool(results), "source": source, "query": query, "results": results}


def _error(kind: str, message: str, source: str = "") -> dict:
    result = {"ok": False, "error_kind": kind, "error": message, "results": []}
    if source:
        result["source"] = source
    return result


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._href = attrs_dict.get("href", "")
            self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, _collapse_ws(" ".join(self._text))))
            self._href = ""
            self._text = []


def _extract_links(html: str) -> list[tuple[str, str]]:
    parser = _LinkParser()
    parser.feed(html or "")
    return parser.links


BLENDER_API_SEARCH = {
    "name": "blender.api_search",
    "description": (
        "Search the configured Blender Python API documentation. Use before "
        "writing or executing Blender Python when API names, operator "
        "parameters, context requirements, or version behavior are uncertain."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "API keyword, class, operator, property, module, or error text to search for.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "default": 5,
            },
            "use_online": {
                "type": "boolean",
                "description": "Allow searching official online Blender API docs.",
                "default": True,
            },
        },
        "required": ["query"],
    },
    "owner": "builtin",
    "handler": _handler_api_search,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "requires_main_thread": False,
        "background_context": "addon_preferences",
        "background_prefs_fields": [
            "blender_api_docs_path",
            "blender_api_docs_url",
            "blender_api_docs_prefer_local",
        ],
    },
}
