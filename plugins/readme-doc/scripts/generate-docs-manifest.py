#!/usr/bin/env python3
"""
Documentation Manifest Generator

Scans the project's `.readme/` documentation tree (sections + chunks, including
expired chunks) and writes a deterministic JSON manifest to
`.readme/docs-manifest.json` for downstream dashboards / RAG / context-pack tooling.

Usage:
    python3 ~/.claude/skills/doc-batch-expire/generate-docs-manifest.py [--project PATH] [--stdout]

Behaviors:
- Finds project root by locating `.readme/` from cwd (or via --project).
- Honors split-layout workspaces with `.project-folder` (consistent with check-docs-expiry.py).
- Output is sorted by `path` and pretty-printed with 2-space indent and stable field order.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------- project discovery (mirrors check-docs-expiry.py) ----------

def get_project_root(specified_path: Optional[str] = None) -> Path:
    if specified_path:
        return Path(specified_path).resolve()
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / ".readme").is_dir():
            return current
        current = current.parent
    return Path.cwd().resolve()


def get_source_root(project_root: Path) -> Path:
    pointer = project_root / ".project-folder"
    if pointer.is_file():
        try:
            target_name = pointer.read_text(encoding="utf-8").strip()
        except Exception:
            target_name = ""
        if target_name:
            candidate = (project_root / target_name).resolve()
            if candidate.is_dir():
                return candidate
    return project_root


# ---------- minimal YAML front matter parser ----------

def parse_front_matter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end_match = content.find("\n---", 3)
    if end_match == -1:
        return {}
    yaml_content = content[4:end_match]
    result: dict = {}
    current_list = None
    for line in yaml_content.split("\n"):
        line = line.rstrip()
        if not line:
            continue
        # List item — accept both flush "- x" and indented "  - x"
        stripped = line.lstrip()
        if stripped.startswith("- "):
            if current_list is not None:
                current_list.append(stripped[2:].strip())
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if value:
                result[key] = value
                current_list = None
            else:
                result[key] = []
                current_list = result[key]
    return result


# ---------- title + read_when extraction ----------

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def extract_title(body: str, fallback: str) -> str:
    match = H1_RE.search(body)
    if match:
        return match.group(1).strip()
    return fallback


READ_WHEN_RE = re.compile(r"(?:Read when|read_when)\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE)


def extract_read_when_for_chunk(body: str, chunk_basename: str) -> Optional[str]:
    """Best-effort: scan a section index body for a `Read when:` line near the chunk's filename."""
    if chunk_basename not in body:
        return None
    idx = body.find(chunk_basename)
    window = body[idx: idx + 500]
    match = READ_WHEN_RE.search(window)
    if match:
        return match.group(1).strip().rstrip(".")
    return None


# ---------- manifest assembly ----------

def split_front_matter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    end_match = content.find("\n---", 3)
    if end_match == -1:
        return {}, content
    return parse_front_matter(content), content[end_match + 4:]


def build_item(path: Path, project_root: Path, kind: str, status: str,
               read_when: Optional[str] = None) -> dict:
    rel = path.relative_to(project_root).as_posix()
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        content = ""
    fm, body = split_front_matter(content)
    title = extract_title(body, fallback=path.stem)
    source_paths = fm.get("source_paths") or []
    if isinstance(source_paths, str):
        source_paths = [source_paths]
    return {
        "path": rel,
        "kind": kind,
        "status": status,
        "title": title,
        "last_verified_at": fm.get("last_verified_at"),
        "source_paths": list(source_paths),
        "expired_reason": fm.get("expired_reason"),
        "read_when": read_when,
    }


def collect_section_read_when_index(sections: list[Path]) -> dict[str, str]:
    """Map chunk basename → read_when text harvested from any section index."""
    read_when_map: dict[str, str] = {}
    for sec in sections:
        try:
            content = sec.read_text(encoding="utf-8")
        except Exception:
            continue
        _, body = split_front_matter(content)
        # Find every chunk reference like `chunks/<name>.md` or `.readme/chunks/<name>.md`
        for chunk_name in re.findall(r"([a-zA-Z0-9._\-]+\.md)", body):
            if chunk_name in read_when_map:
                continue
            rw = extract_read_when_for_chunk(body, chunk_name)
            if rw:
                read_when_map[chunk_name] = rw
    return read_when_map


def main():
    parser = argparse.ArgumentParser(description="Generate .readme/docs-manifest.json")
    parser.add_argument("--project", type=str, help="Project root (defaults to cwd)")
    parser.add_argument("--stdout", action="store_true", help="Print manifest to stdout instead of writing the file")
    args = parser.parse_args()

    project_root = get_project_root(args.project)
    readme_dir = project_root / ".readme"
    if not readme_dir.is_dir():
        print(f"Error: .readme/ not found under {project_root}", file=sys.stderr)
        sys.exit(1)

    sections_dir = readme_dir / "sections"
    chunks_dir = readme_dir / "chunks"

    section_files = sorted(sections_dir.glob("*.index.md")) if sections_dir.is_dir() else []
    if chunks_dir.is_dir():
        all_chunk_files = sorted(chunks_dir.glob("*.md"))
        active_chunks = [f for f in all_chunk_files if not f.name.endswith(".expired.md")]
        expired_chunks = [f for f in all_chunk_files if f.name.endswith(".expired.md")]
    else:
        active_chunks = []
        expired_chunks = []

    read_when_index = collect_section_read_when_index(section_files)

    items: list[dict] = []

    for sec in section_files:
        items.append(build_item(sec, project_root, kind="section", status="active"))

    for chunk in active_chunks:
        items.append(build_item(
            chunk, project_root, kind="chunk", status="active",
            read_when=read_when_index.get(chunk.name),
        ))

    for chunk in expired_chunks:
        items.append(build_item(
            chunk, project_root, kind="chunk", status="expired",
            read_when=read_when_index.get(chunk.name),
        ))

    items.sort(key=lambda x: x["path"])

    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": str(project_root),
        "counts": {
            "sections": len(section_files),
            "active_chunks": len(active_chunks),
            "expired_chunks": len(expired_chunks),
        },
        "items": items,
    }

    output = json.dumps(manifest, indent=2, ensure_ascii=False)

    if args.stdout:
        print(output)
        return

    out_path = readme_dir / "docs-manifest.json"
    out_path.write_text(output + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(project_root)} "
          f"(sections={manifest['counts']['sections']}, "
          f"active={manifest['counts']['active_chunks']}, "
          f"expired={manifest['counts']['expired_chunks']})")


if __name__ == "__main__":
    main()
