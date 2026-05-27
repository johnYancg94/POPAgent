"""Small Markdown-to-panel block parser for POPAgent answers.

Blender panels cannot render real Markdown, so this module converts the common
LLM subset into simple block dictionaries consumed by panel_output.py.
"""

import re


_FENCE_RE = re.compile(r"^\s*```(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_NUMBERED_RE = re.compile(r"^(\d+)\.\s+(.+)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"(\*\*|__)(.*?)\1")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def clean_inline_markdown(text: str) -> str:
    """Remove inline Markdown markers while preserving readable text."""
    text = _LINK_RE.sub(r"\1 (\2)", text)
    text = _BOLD_RE.sub(r"\2", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    return text


def _new_part(part_type: str, **extra) -> dict:
    part = {"type": part_type, "content": []}
    part.update(extra)
    return part


def _append_text_part(parts: list, line: str) -> None:
    line = clean_inline_markdown(line)
    if parts and parts[-1]["type"] == "text":
        parts[-1]["content"].append(line)
    else:
        parts.append(_new_part("text"))
        parts[-1]["content"].append(line)


def _append_list_item(parts: list, part_type: str, line: str) -> None:
    line = clean_inline_markdown(line)
    if parts and parts[-1]["type"] == part_type:
        parts[-1]["content"].append(line)
    else:
        parts.append(_new_part(part_type))
        parts[-1]["content"].append(line)


def _parse_table_row(line: str) -> list:
    if "|" not in line:
        return []
    cells = [clean_inline_markdown(cell.strip()) for cell in line.strip().strip("|").split("|")]
    return [cell for cell in cells if cell]


def parse_markdown_blocks(answer: str) -> list:
    """Parse an LLM answer into simple UI blocks.

    Returned blocks keep the existing code/list shape where possible, while
    adding heading, bullet_list, and quote block types for cleaner UI rendering.
    """
    parts = []
    in_code = False
    code_part = None

    for raw_line in answer.splitlines():
        fence = _FENCE_RE.match(raw_line)
        if fence:
            if in_code:
                in_code = False
                code_part = None
                continue

            language = fence.group(1).strip().title()
            code_part = _new_part(
                "code",
                code_language=language,
                error="",
                error_line_number=None,
            )
            parts.append(code_part)
            in_code = True
            continue

        if in_code:
            code_part["content"].append(raw_line)
            continue

        if _TABLE_SEPARATOR_RE.match(raw_line):
            continue

        table_cells = _parse_table_row(raw_line)
        if len(table_cells) >= 2:
            if parts and parts[-1]["type"] == "table":
                parts[-1]["content"].append(table_cells)
            else:
                parts.append(_new_part("table", content=[table_cells]))
            continue

        heading = _HEADING_RE.match(raw_line)
        if heading:
            parts.append(
                _new_part(
                    "heading",
                    level=len(heading.group(1)),
                    content=[clean_inline_markdown(heading.group(2).strip())],
                )
            )
            continue

        numbered = _NUMBERED_RE.match(raw_line)
        if numbered:
            _append_list_item(
                parts,
                "list",
                f"{numbered.group(1)}. {numbered.group(2).strip()}",
            )
            continue

        bullet = _BULLET_RE.match(raw_line)
        if bullet:
            _append_list_item(parts, "bullet_list", bullet.group(1).strip())
            continue

        quote = _QUOTE_RE.match(raw_line)
        if quote:
            _append_list_item(parts, "quote", quote.group(1).strip())
            continue

        _append_text_part(parts, raw_line)

    if not parts:
        parts.append(_new_part("text", content=[""]))

    for index, part in enumerate(parts):
        part["index"] = index

    return parts
