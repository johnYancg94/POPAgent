"""Discovery and activation for agentskills.io compatible skill folders."""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path


_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FRONTMATTER_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
_TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
DEFAULT_MAX_RESOURCE_BYTES = 512 * 1024


def _diagnostic(code: str, message: str, path: Path, severity: str = "warning") -> dict:
    return {
        "code": code,
        "message": message,
        "path": str(path),
        "severity": severity,
    }


def _split_skill_file(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :]).strip()
    raise ValueError("SKILL.md frontmatter is missing its closing delimiter")


def parse_skill_file(path: str | Path, *, source: str) -> tuple[dict | None, list[dict]]:
    skill_path = Path(path)
    diagnostics: list[dict] = []
    try:
        text = skill_path.read_text(encoding="utf-8")
        frontmatter_text, body = _split_skill_file(text)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [
            _diagnostic("invalid_skill_file", str(exc), skill_path, severity="error")
        ]

    try:
        import yaml
    except ImportError:
        return None, [
            _diagnostic(
                "yaml_dependency_missing",
                "PyYAML is required to parse Agent Skills",
                skill_path,
                severity="error",
            )
        ]

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        return None, [
            _diagnostic("invalid_yaml", str(exc), skill_path, severity="error")
        ]
    if not isinstance(frontmatter, dict):
        return None, [
            _diagnostic(
                "invalid_yaml",
                "Agent Skill frontmatter must be a mapping",
                skill_path,
                severity="error",
            )
        ]

    raw_name = frontmatter.get("name")
    name = str(raw_name).strip() if raw_name is not None else ""
    raw_description = frontmatter.get("description")
    description = (
        str(raw_description).strip() if raw_description is not None else ""
    )
    if not description:
        diagnostics.append(
            _diagnostic(
                "missing_description",
                "Agent Skill description is required",
                skill_path,
                severity="error",
            )
        )
        return None, diagnostics
    if not name:
        diagnostics.append(
            _diagnostic(
                "missing_name",
                "Agent Skill name is required",
                skill_path,
                severity="error",
            )
        )
        return None, diagnostics

    if len(name) > 64 or not _NAME_RE.fullmatch(name):
        diagnostics.append(
            _diagnostic(
                "invalid_name",
                "Name should be 1-64 lowercase letters, digits, and single hyphens",
                skill_path,
            )
        )
    if name != skill_path.parent.name:
        diagnostics.append(
            _diagnostic(
                "name_directory_mismatch",
                f"Skill name '{name}' does not match directory '{skill_path.parent.name}'",
                skill_path,
            )
        )
    if len(description) > 1024:
        diagnostics.append(
            _diagnostic(
                "description_too_long",
                "Description exceeds the 1024-character specification limit",
                skill_path,
            )
        )
    compatibility = frontmatter.get("compatibility")
    if compatibility is not None and len(str(compatibility)) > 500:
        diagnostics.append(
            _diagnostic(
                "compatibility_too_long",
                "Compatibility exceeds the 500-character specification limit",
                skill_path,
            )
        )
    unknown_fields = sorted(set(frontmatter) - _FRONTMATTER_FIELDS)
    if unknown_fields:
        diagnostics.append(
            _diagnostic(
                "unknown_frontmatter_fields",
                f"Unknown frontmatter fields: {', '.join(unknown_fields)}",
                skill_path,
            )
        )

    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    root = skill_path.parent.resolve()
    record = {
        "name": name,
        "description": description,
        "license": frontmatter.get("license"),
        "compatibility": compatibility,
        "metadata": metadata,
        "allowed_tools": frontmatter.get("allowed-tools"),
        "body": body,
        "source": source,
        "location": str(skill_path.resolve()),
        "root": str(root),
        "diagnostics": diagnostics,
    }
    return record, diagnostics


class ActiveAgentSkills:
    def __init__(self):
        self._records: dict[str, dict] = {}

    def add(self, record: dict) -> bool:
        name = record["name"]
        if name in self._records:
            return False
        self._records[name] = dict(record)
        return True

    def render_instructions(self) -> str:
        if not self._records:
            return ""
        parts = [
            "Activated Agent Skills. Follow these instructions for the rest of "
            "this agent turn. Relative paths resolve from each listed skill root."
        ]
        for name in sorted(self._records):
            record = self._records[name]
            parts.append(
                f"## Agent Skill: {name}\n"
                f"Source: {record['source']}\n"
                f"Root: {record['root']}\n\n"
                f"{record['body']}"
            )
        return "\n\n".join(parts)


class AgentSkillRegistry:
    def __init__(self, *, max_resource_bytes: int = DEFAULT_MAX_RESOURCE_BYTES):
        self.max_resource_bytes = max_resource_bytes
        self._bundled_roots: dict[str, Path] = {}
        self._skills: dict[str, dict] = {}
        self._diagnostics: list[dict] = []

    def register_bundled_root(self, owner: str, root: str | Path) -> None:
        self._bundled_roots[owner] = Path(root)

    def unregister_bundled_root(self, owner: str) -> None:
        self._bundled_roots.pop(owner, None)

    def clear_bundled_roots(self) -> None:
        self._bundled_roots.clear()

    def refresh(
        self,
        *,
        user_home: str | Path | None = None,
        blend_file: str | Path = "",
    ) -> list[dict]:
        self._skills = {}
        self._diagnostics = []
        roots: list[tuple[int, str, Path]] = []
        for owner, root in sorted(self._bundled_roots.items()):
            roots.append((0, f"bundled:{owner}", root))

        home = Path(user_home).expanduser() if user_home is not None else Path.home()
        roots.append((1, "user", home / ".agents" / "skills"))

        if blend_file:
            blend_path = Path(blend_file)
            roots.append((2, "project", blend_path.parent / ".agents" / "skills"))

        for precedence, source, root in roots:
            self._scan_root(root, source=source, precedence=precedence)
        return self.all()

    def _scan_root(self, root: Path, *, source: str, precedence: int) -> None:
        if not root.is_dir():
            return
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            self._diagnostics.append(
                _diagnostic("scan_failed", str(exc), root, severity="error")
            )
            return
        for child in children:
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            skill_path = child / "SKILL.md"
            if not skill_path.is_file():
                continue
            record, diagnostics = parse_skill_file(skill_path, source=source)
            self._diagnostics.extend(diagnostics)
            if record is None:
                continue
            record["_precedence"] = precedence
            previous = self._skills.get(record["name"])
            if previous is not None:
                winner = record if precedence >= previous["_precedence"] else previous
                loser = previous if winner is record else record
                self._diagnostics.append(
                    _diagnostic(
                        "name_collision",
                        (
                            f"Agent Skill '{record['name']}' from {winner['source']} "
                            f"shadows {loser['source']}"
                        ),
                        skill_path,
                    )
                )
                self._skills[record["name"]] = winner
            else:
                self._skills[record["name"]] = record

    def get(self, name: str) -> dict | None:
        record = self._skills.get(name)
        return dict(record) if record is not None else None

    def all(self) -> list[dict]:
        return [dict(self._skills[name]) for name in sorted(self._skills)]

    def diagnostics(self) -> list[dict]:
        return [dict(item) for item in self._diagnostics]

    def render_catalog(self) -> str:
        if not self._skills:
            return ""
        lines = [
            "Available Agent Skills (agentskills.io format). Only metadata is "
            "listed here. When a task matches a description, call "
            "`agent.activate_skill` before proceeding.",
            "",
        ]
        for record in self.all():
            description = " ".join(record["description"].split())
            lines.append(
                f"- {record['name']} [{record['source']}]: {description}"
            )
        return "\n".join(lines)

    def activate(self, name: str, resource: str = "") -> dict:
        record = self._skills.get(name)
        if record is None:
            return {
                "ok": False,
                "error_kind": "agent_skill_not_found",
                "error": f"No Agent Skill discovered: {name}",
            }
        if resource:
            return self._read_resource(record, resource)
        return {
            "ok": True,
            "name": record["name"],
            "description": record["description"],
            "source": record["source"],
            "location": record["location"],
            "root": record["root"],
            "frontmatter": {
                "name": record["name"],
                "description": record["description"],
                "license": record["license"],
                "compatibility": record["compatibility"],
                "metadata": record["metadata"],
                "allowed-tools": record["allowed_tools"],
            },
            "body": record["body"],
            "resources": self._list_resources(Path(record["root"])),
        }

    def _list_resources(self, root: Path) -> list[str]:
        resources = []
        try:
            paths = sorted(root.rglob("*"))
        except OSError:
            return resources
        for path in paths:
            if not path.is_file() or path.name == "SKILL.md":
                continue
            try:
                resources.append(path.relative_to(root).as_posix())
            except ValueError:
                continue
        return resources

    def _read_resource(self, record: dict, resource: str) -> dict:
        root = Path(record["root"]).resolve()
        requested = Path(resource)
        if requested.is_absolute() or ".." in requested.parts:
            return _resource_error("invalid_resource_path", resource)
        try:
            path = (root / requested).resolve(strict=True)
            path.relative_to(root)
        except (OSError, ValueError):
            candidate = root / requested
            if not candidate.exists():
                return _resource_error("resource_not_found", resource)
            return _resource_error("invalid_resource_path", resource)
        if not path.is_file():
            return _resource_error("resource_not_found", resource)
        try:
            size = path.stat().st_size
        except OSError as exc:
            return _resource_error("resource_unavailable", resource, str(exc))
        if size > self.max_resource_bytes:
            return _resource_error(
                "resource_too_large",
                resource,
                f"Resource is {size} bytes; limit is {self.max_resource_bytes}",
            )

        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        result = {
            "ok": True,
            "name": record["name"],
            "resource": requested.as_posix(),
            "path": str(path),
            "size": size,
            "media_type": media_type,
        }
        if path.suffix.lower() in _TEXT_SUFFIXES:
            try:
                result["content"] = path.read_text(encoding="utf-8")
                result["binary"] = False
                return result
            except UnicodeError:
                pass
            except OSError as exc:
                return _resource_error("resource_unavailable", resource, str(exc))
        result["binary"] = True
        return result


def _resource_error(kind: str, resource: str, detail: str = "") -> dict:
    message = f"Cannot read Agent Skill resource: {resource}"
    if detail:
        message = f"{message}. {detail}"
    return {"ok": False, "error_kind": kind, "error": message}


registry = AgentSkillRegistry()
