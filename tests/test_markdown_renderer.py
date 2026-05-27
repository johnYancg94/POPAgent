"""Pure Python smoke tests for answer Markdown parsing.

Run from the add-on directory with:
    python tests/test_markdown_renderer.py
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.markdown_renderer import parse_markdown_blocks


def test_common_markdown_blocks():
    answer = """# Main Answer
This is **readable** text with `inline code` and [docs](https://example.com).

- First bullet
- Second bullet

1. First step
2. Second step

> A useful note

| Name | Value |
| --- | --- |
| Mode | Compact |

```python
print("hello")
```
"""

    parts = parse_markdown_blocks(answer)
    types = [part["type"] for part in parts]

    assert types == [
        "heading",
        "text",
        "bullet_list",
        "text",
        "list",
        "text",
        "quote",
        "text",
        "table",
        "text",
        "code",
    ], types
    assert parts[0]["content"] == ["Main Answer"]
    assert "readable text" in parts[1]["content"][0]
    assert "`" not in parts[1]["content"][0]
    assert parts[2]["content"] == ["First bullet", "Second bullet"]
    assert parts[4]["content"] == ["1. First step", "2. Second step"]
    assert parts[-3]["content"] == [["Name", "Value"], ["Mode", "Compact"]]
    assert parts[-1]["code_language"] == "Python"
    assert parts[-1]["content"] == ['print("hello")']


def run():
    test_common_markdown_blocks()
    print("test_common_markdown_blocks OK")
    return True


if __name__ == "__main__":
    run()
