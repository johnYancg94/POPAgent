"""Consumer side of the JSONL usage sink (see usage_log.py for the producer).

usage_log.py only *writes* episodes to disk. This module reads them back and
aggregates the mechanical signals so a developer can hand a small, accurate,
structured summary to a top-tier offline agent (Claude / Codex) for distilling
"what skill to add / which prompt to fix / which skill nobody uses".

Division of labour (intentional):
- This module ONLY counts and groups. It produces facts
  ("naming.batch_rename failed 12x", "no_skill_matched hit these 8 prompts"),
  never judgements ("you should change it to X"). The judgement step is done
  offline by a stronger model, on top of these facts plus a few sampled
  raw episodes.

Constraints (same as usage_log.py):
- stdlib only, NO bpy import -> fully unit-testable off the main thread.
- tolerant reader: bad/blank lines are skipped, missing files ignored.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


# Cap on how many sampled episode_ids we keep per problem bucket. The offline
# agent needs a few concrete examples for "why", not the whole haystack.
_SAMPLE_LIMIT = 5

# Subdirectories whose name starts with this are infrastructure (archive of
# already-exported logs), never live episode data. read_episodes skips them so
# a re-export does not re-count logs that were already archived.
_RESERVED_PREFIX = "_"


def _iter_log_files(
    log_dir: str | Path,
    *,
    user_ids: Iterable[str] | None = None,
    days: Iterable[str] | None = None,
) -> list[Path]:
    """Yield the live `<log_dir>/<user_id>/<day>.jsonl` files (sorted).

    Skips `_`-prefixed dirs (e.g. `_archive`) so archived logs are never
    re-read. Shared by read_episodes (reads them) and export_and_archive
    (zips + moves them) so both agree on exactly which files are "live".
    """
    root = Path(log_dir).expanduser()
    if not root.is_dir():
        return []

    want_users = set(user_ids) if user_ids is not None else None
    want_days = set(days) if days is not None else None

    files: list[Path] = []
    for user_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if user_dir.name.startswith(_RESERVED_PREFIX):
            continue
        if want_users is not None and user_dir.name not in want_users:
            continue
        for day_file in sorted(user_dir.glob("*.jsonl")):
            if want_days is not None and day_file.stem not in want_days:
                continue
            files.append(day_file)
    return files


def read_episodes(
    log_dir: str | Path,
    *,
    user_ids: Iterable[str] | None = None,
    days: Iterable[str] | None = None,
) -> list[dict]:
    """Read episodes back from `<log_dir>/<user_id>/<YYYY-MM-DD>.jsonl`.

    Inverse of usage_log.append_episode. Walks every user dir and every day
    file, json-decoding one record per line. Tolerant by design: a malformed
    or blank line is skipped rather than aborting the whole read, because logs
    are appended live and the last line may be partially flushed.

    `user_ids` / `days` optionally restrict which files are read (membership
    test against the path components). Episodes come back sorted by `ts`.
    """
    episodes: list[dict] = []
    for day_file in _iter_log_files(log_dir, user_ids=user_ids, days=days):
        episodes.extend(_read_one_file(day_file))

    episodes.sort(key=lambda e: e.get("ts", ""))
    return episodes


def _read_one_file(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


def _bump_sample(bucket: list, episode_id: str) -> None:
    if episode_id and len(bucket) < _SAMPLE_LIMIT and episode_id not in bucket:
        bucket.append(episode_id)


def aggregate(
    episodes: list[dict],
    *,
    known_skills: Iterable[str] | None = None,
) -> dict:
    """Count and group the mechanical signals across many episodes.

    Returns facts only, never recommendations. Shape:

        {
          "episode_count": int,
          "tool_call_count": int,
          "totals": {error_count, aborted, any_denied, no_skill_matched},
          "per_skill": {                 # one entry per skill that was called
              name: {calls, errors, denied, error_kinds:{kind:n},
                     owner, confirm_level, fail_samples:[episode_id,...]}
          },
          "no_skill_matched": {          # the gap: user wanted X, no skill fit
              "count": int,
              "prompts": [ {prompt, episode_id}, ... ]   # capped sample
          },
          "aborts": {reason: count},
          "never_used": [name, ...]      # only if known_skills was passed
        }

    `known_skills` is the current registry's skill names; passing it lets the
    report flag registered-but-never-called skills (dead weight to consider
    cutting). Without it, "never_used" is omitted (can't know the universe).
    """
    per_skill: dict[str, dict] = {}
    abort_reasons: Counter = Counter()
    no_skill_prompts: list[dict] = []
    no_skill_count = 0

    totals = {
        "error_count": 0,
        "aborted": 0,
        "any_denied": 0,
        "no_skill_matched": 0,
    }
    tool_call_count = 0

    for ep in episodes:
        episode_id = ep.get("episode_id", "") or ""
        signals = ep.get("signals", {}) or {}

        totals["error_count"] += int(signals.get("error_count", 0) or 0)
        if signals.get("aborted"):
            totals["aborted"] += 1
            abort_reasons[signals.get("abort_reason", "") or "unknown"] += 1
        if signals.get("any_denied"):
            totals["any_denied"] += 1
        if signals.get("no_skill_matched"):
            totals["no_skill_matched"] += 1
            no_skill_count += 1
            prompt = (ep.get("request", {}) or {}).get("prompt_preview", "")
            if len(no_skill_prompts) < _SAMPLE_LIMIT:
                no_skill_prompts.append(
                    {"prompt": prompt, "episode_id": episode_id}
                )

        for tool in ep.get("tools", []) or []:
            tool_call_count += 1
            name = tool.get("name", "") or "(unnamed)"
            entry = per_skill.setdefault(
                name,
                {
                    "calls": 0,
                    "errors": 0,
                    "denied": 0,
                    "error_kinds": Counter(),
                    "owner": tool.get("owner", "") or "",
                    "confirm_level": tool.get("confirm_level", "") or "",
                    "fail_samples": [],
                },
            )
            entry["calls"] += 1
            if not tool.get("ok", True):
                entry["errors"] += 1
                kind = tool.get("error_kind", "") or "unknown"
                entry["error_kinds"][kind] += 1
                if kind == "user_denied":
                    entry["denied"] += 1
                _bump_sample(entry["fail_samples"], episode_id)

    for entry in per_skill.values():
        entry["error_kinds"] = dict(entry["error_kinds"])

    report = {
        "episode_count": len(episodes),
        "tool_call_count": tool_call_count,
        "totals": totals,
        "per_skill": per_skill,
        "no_skill_matched": {
            "count": no_skill_count,
            "prompts": no_skill_prompts,
        },
        "aborts": dict(abort_reasons),
    }

    if known_skills is not None:
        called = set(per_skill)
        report["never_used"] = sorted(set(known_skills) - called)

    return report


def format_report(report: dict, *, top_n: int = 10) -> str:
    """Render an aggregate() report as plain text for a console / .txt dump.

    This is the artifact a developer pastes (or attaches) to a top-tier agent
    along with a few sampled raw episodes. It states facts; the agent judges.
    """
    lines: list[str] = []
    ec = report.get("episode_count", 0)
    tc = report.get("tool_call_count", 0)
    lines.append(f"POPAgent usage report — {ec} episodes, {tc} tool calls")
    lines.append("=" * 56)

    totals = report.get("totals", {}) or {}
    lines.append(
        "Totals: errors={error_count} aborted={aborted} "
        "denied={any_denied} no_skill_matched={no_skill_matched}".format(
            **{
                "error_count": totals.get("error_count", 0),
                "aborted": totals.get("aborted", 0),
                "any_denied": totals.get("any_denied", 0),
                "no_skill_matched": totals.get("no_skill_matched", 0),
            }
        )
    )

    nsm = report.get("no_skill_matched", {}) or {}
    if nsm.get("count"):
        lines.append("")
        lines.append(f"[GAP] no_skill_matched x{nsm['count']} "
                     "(user wanted something no skill could do):")
        for item in nsm.get("prompts", []):
            lines.append(f"  - \"{item.get('prompt', '')}\""
                         f"  ({item.get('episode_id', '')[:8]})")

    per_skill = report.get("per_skill", {}) or {}
    failing = sorted(
        (v for v in per_skill.items() if v[1]["errors"]),
        key=lambda kv: kv[1]["errors"],
        reverse=True,
    )
    if failing:
        lines.append("")
        lines.append("[UNSTABLE] skills by error count:")
        for name, e in failing[:top_n]:
            kinds = ", ".join(f"{k}:{n}" for k, n in e["error_kinds"].items())
            samples = ", ".join(s[:8] for s in e["fail_samples"])
            lines.append(
                f"  {name}: {e['errors']}/{e['calls']} failed"
                f"  [{kinds}]"
                + (f"  e.g. {samples}" if samples else "")
            )

    denied = sorted(
        (v for v in per_skill.items() if v[1]["denied"]),
        key=lambda kv: kv[1]["denied"],
        reverse=True,
    )
    if denied:
        lines.append("")
        lines.append("[FRICTION] skills users denied (confirm level too "
                     "strict?):")
        for name, e in denied[:top_n]:
            lines.append(
                f"  {name}: denied {e['denied']}x "
                f"(confirm_level={e['confirm_level'] or '?'})"
            )

    aborts = report.get("aborts", {}) or {}
    if aborts:
        lines.append("")
        lines.append("[ABORTS] by reason:")
        for reason, n in sorted(aborts.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {reason}: {n}")

    if "never_used" in report:
        never = report["never_used"]
        lines.append("")
        lines.append(f"[DEAD WEIGHT] {len(never)} registered skills never "
                     "called:")
        if never:
            lines.append("  " + ", ".join(never))

    lines.append("")
    return "\n".join(lines)


def _sanitize_label(label: str) -> str:
    """Keep a label filesystem-safe: alnum, dash, underscore only."""
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
    return cleaned.strip("_") or "unknown"


def _unique_path(directory: Path, stem: str, ext: str) -> Path:
    """`<dir>/<stem><ext>`, appending -2, -3... if it already exists.

    This is the collision guard: two exports on the same day by the same
    person (or two members whose archive lands in the same folder) never
    overwrite each other.
    """
    candidate = directory / f"{stem}{ext}"
    n = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{n}{ext}"
        n += 1
    return candidate


def export_and_archive(
    log_dir: str | Path,
    dest_dir: str | Path,
    *,
    label: str = "unknown",
    known_skills: Iterable[str] | None = None,
    today: str | None = None,
) -> dict:
    """Cut (not copy) the live logs into a single self-contained zip.

    Pipeline, in order:
      1. read every live episode (archived `_`-dirs are skipped)
      2. aggregate + render report.txt
      3. write a uniquely-named zip into dest_dir containing report.txt plus
         every raw .jsonl (the "why" evidence the offline agent samples)
      4. MOVE the consumed .jsonl files into `<log_dir>/_archive/<day>/...`
         so the live area is emptied -> next export is naturally incremental

    Returns {zip_path, episode_count, archived_files, skipped: False} or, when
    there is nothing to export, {skipped: True, ...}. Never deletes raw data:
    archiving keeps it locally as a safety net and as offline evidence.
    """
    log_root = Path(log_dir).expanduser()
    dest_root = Path(dest_dir).expanduser()
    day = today or datetime.now().strftime("%Y-%m-%d")

    live_files = _iter_log_files(log_root)
    episodes = read_episodes(log_root)
    if not episodes or not live_files:
        return {"skipped": True, "episode_count": 0, "archived_files": 0,
                "zip_path": None}

    report = aggregate(episodes, known_skills=known_skills)
    report_text = format_report(report)

    dest_root.mkdir(parents=True, exist_ok=True)
    stem = f"popagent_{_sanitize_label(label)}_{day}"
    zip_path = _unique_path(dest_root, stem, ".zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.txt", report_text)
        for f in live_files:
            # arc path keeps the <user_id>/<day>.jsonl shape for traceability
            zf.write(f, arcname=str(f.relative_to(log_root)))

    archive_root = log_root / f"{_RESERVED_PREFIX}archive" / day
    archived = 0
    for f in live_files:
        rel = f.relative_to(log_root)
        target = _unique_path(archive_root / rel.parent, f.stem, f.suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(target))
        archived += 1

    return {
        "skipped": False,
        "zip_path": str(zip_path),
        "episode_count": len(episodes),
        "archived_files": archived,
    }
