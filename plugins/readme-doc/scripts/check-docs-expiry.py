#!/usr/bin/env python3
"""
Documentation Expiry Checker

Checks .readme/chunks/*.md documentation files against source code to detect stale docs.

Strategy:
1. Parse front matter to extract source_paths and last_verified_at
2. Check if source files have been modified since last_verified_at
3. For files with code snippets, verify snippets still exist in source
4. Output JSON report for use by doc-batch-expire skill

Usage:
    python3 ~/.claude/tools/check-docs-expiry.py [--json] [--verbose] [--dry-run]

Options:
    --json      Output as JSON (for scripted use)
    --verbose   Show detailed checking progress
    --dry-run   Don't rename files, just report what would be expired
    --expire    Actually rename expired files to .expired.md
    --project   Path to project root (defaults to current directory)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class ChunkStatus:
    """Status of a documentation chunk."""
    path: str
    source_paths: list[str] = field(default_factory=list)
    last_verified_at: Optional[str] = None
    status: str = "unknown"  # valid, expired, error
    reasons: list[str] = field(default_factory=list)
    modified_sources: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    uncommitted_sources: list[str] = field(default_factory=list)


def get_project_root(specified_path: Optional[str] = None) -> Path:
    """Get project root - uses specified path, or finds .readme directory from cwd."""
    if specified_path:
        return Path(specified_path).resolve()

    # Start from current working directory
    current = Path.cwd().resolve()

    # Look for .readme directory
    while current != current.parent:
        if (current / ".readme").is_dir():
            return current
        current = current.parent

    # Fallback to cwd
    return Path.cwd().resolve()


def get_source_root(project_root: Path) -> Path:
    """Resolve the folder that source_paths are relative to.

    Split-layout workspaces keep `.readme/` at the workspace root while the
    actual repo lives in a child folder. A `.project-folder` file at the
    workspace root contains the child folder name. If present and valid, use
    it; otherwise fall back to project_root.
    """
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


def normalize_source_path(source_path: str, project_folder_name: str) -> str:
    """Reduce a source_path to a path relative to the project-folder.

    Chunks reference code in equivalent forms that all point at the same file
    under the project-folder:
      - bare:          src/lib/db/schema.ts
      - placeholder:   [project-folder]/src/lib/db/schema.ts
      - explicit name: main/src/lib/db/schema.ts
    Strip a leading `[project-folder]/` token or `<project-folder-name>/` prefix
    so the result joins cleanly onto the project-folder root.
    """
    sp = source_path.strip().lstrip("/")
    for prefix in ("[project-folder]/", f"{project_folder_name}/"):
        if sp.startswith(prefix):
            return sp[len(prefix):]
    return sp


def _unquote(value: str) -> str:
    """Strip matching single/double quotes from a YAML scalar."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_front_matter(content: str) -> dict:
    """Parse YAML front matter from markdown content."""
    if not content.startswith("---"):
        return {}

    end_match = content.find("\n---", 3)
    if end_match == -1:
        return {}

    yaml_content = content[4:end_match]
    result = {}

    # Simple YAML parsing (handles our specific format)
    current_key = None
    current_list = None

    for line in yaml_content.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        # List item — accept both flush "- x" and indented "  - x"
        stripped = line.lstrip()
        if stripped.startswith("- "):
            if current_list is not None:
                current_list.append(_unquote(stripped[2:].strip()))
            continue

        # Key-value or key-list
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            if value:
                result[key] = _unquote(value)
                current_key = None
                current_list = None
            else:
                # Start of a list
                result[key] = []
                current_key = key
                current_list = result[key]

    return result


def get_git_modified_time(file_path: Path, project_root: Path) -> Optional[datetime]:
    """Get the last modification time of a file from git."""
    try:
        rel_path = file_path.relative_to(project_root)
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(rel_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse ISO format datetime
            dt_str = result.stdout.strip()
            # Handle timezone offset format (+00:00 or Z)
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        pass
    return None


# Cumulative changed lines (insertions + deletions) since a doc was last verified,
# below which drift is treated as trivial and does not flag the chunk.
DRIFT_LINE_THRESHOLD = 15


def get_git_change_magnitude(file_path: Path, project_root: Path, since: datetime) -> int:
    """Total lines changed for a file across commits since `since`.

    Lets the checker ignore trivial drift so a small unrelated edit doesn't mark a
    whole chunk stale. Returns 0 on any error (treated as no meaningful change).
    """
    try:
        rel_path = file_path.relative_to(project_root)
        result = subprocess.run(
            ["git", "log", f"--since={since.isoformat()}", "--numstat", "--format=",
             "--", str(rel_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return 0
        total = 0
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                ins, dele = parts[0], parts[1]
                total += (int(ins) if ins.isdigit() else 0) + (int(dele) if dele.isdigit() else 0)
        return total
    except Exception:
        return 0


def git_has_uncommitted_changes(file_path: Path, project_root: Path) -> bool:
    """Return True if `git status --porcelain` reports working-tree changes for this file."""
    try:
        rel_path = file_path.relative_to(project_root)
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", str(rel_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
    except Exception:
        pass
    return False


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    """Parse ISO format datetime string."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def extract_code_references(content: str) -> list[str]:
    """Extract file references from code blocks and surrounding context."""
    references = []

    # Pattern to find code blocks with file references
    # Look for patterns like: File: src/..., From: src/..., path: src/...
    patterns = [
        r"[Ff]ile:\s*`?([a-zA-Z0-9/_\-\.]+\.[a-zA-Z]+)`?",
        r"[Ff]rom:\s*`?([a-zA-Z0-9/_\-\.]+\.[a-zA-Z]+)`?",
        r"[Pp]ath:\s*`?([a-zA-Z0-9/_\-\.]+\.[a-zA-Z]+)`?",
        r"[Ll]ocation:\s*`?([a-zA-Z0-9/_\-\.]+\.[a-zA-Z]+)`?",
        r"`(src/[a-zA-Z0-9/_\-\.]+\.[a-zA-Z]+)`",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            ref = match.group(1)
            if ref not in references:
                references.append(ref)

    return references


def check_chunk(chunk_path: Path, project_root: Path, source_root: Optional[Path] = None, verbose: bool = False) -> ChunkStatus:
    """Check a single documentation chunk for staleness."""
    status = ChunkStatus(path=str(chunk_path.relative_to(project_root)))

    try:
        content = chunk_path.read_text(encoding="utf-8")
    except Exception as e:
        status.status = "error"
        status.reasons.append(f"Cannot read file: {e}")
        return status

    # Parse front matter
    front_matter = parse_front_matter(content)
    status.source_paths = front_matter.get("source_paths", [])
    status.last_verified_at = front_matter.get("last_verified_at")

    # If no source_paths in front matter, try to extract from content
    if not status.source_paths:
        status.source_paths = extract_code_references(content)

    # If still no source paths, can't verify
    if not status.source_paths:
        status.status = "valid"  # Can't verify, assume valid
        if verbose:
            status.reasons.append("No source_paths to verify")
        return status

    # Parse last_verified_at
    verified_at = parse_iso_datetime(status.last_verified_at) if status.last_verified_at else None

    # Resolve the base folder for source_paths (split-layout workspaces use .project-folder)
    base = source_root if source_root is not None else project_root

    # Check each source file
    for source_path in status.source_paths:
        full_path = base / normalize_source_path(source_path, base.name)
        in_project = True

        if not full_path.exists():
            # Workspace-root fallback: some chunks document sibling folders
            # (debug/, social/, .readme/, .claude/) that live at the workspace
            # root rather than under the project-folder.
            alt = project_root / source_path.strip().lstrip("/")
            if alt.exists():
                full_path, in_project = alt, False
            else:
                status.missing_sources.append(source_path)
                continue

        # Git freshness checks apply to files inside the project-folder repo.
        if in_project:
            if git_has_uncommitted_changes(full_path, base):
                status.uncommitted_sources.append(source_path)

            if verified_at:
                source_modified = get_git_modified_time(full_path, base)
                if source_modified and source_modified > verified_at:
                    # Only count meaningful drift; ignore trivial post-verification edits.
                    magnitude = get_git_change_magnitude(full_path, base, verified_at)
                    if magnitude >= DRIFT_LINE_THRESHOLD:
                        status.modified_sources.append(source_path)

    # Determine status.
    #   "expired" (hard) = a documented source file is GONE — actionable; --expire renames these.
    #   "review"  (soft) = the doc may have drifted but its sources still exist — reported,
    #                      never auto-renamed, so still-accurate docs aren't churned by a sweep.
    if status.missing_sources:
        status.status = "expired"
        status.reasons.append(f"Missing source files: {', '.join(status.missing_sources)}")
    elif status.modified_sources:
        status.status = "review"
        status.reasons.append(f"Source files modified since last verification: {', '.join(status.modified_sources)}")
    elif status.uncommitted_sources:
        status.status = "review"
        for src in status.uncommitted_sources:
            status.reasons.append(f"Source file has uncommitted changes: {src}")
    elif not verified_at:
        status.status = "review"
        status.reasons.append("No last_verified_at timestamp in front matter")
    else:
        status.status = "valid"

    return status


EXPIRED_WARNING = "**\u26a0\ufe0f EXPIRED**: Awaiting refresh."


def _strip_existing_expired_reason(front_matter: str) -> str:
    """Remove any existing `expired_reason: ...` line from the YAML front matter.

    Preserves the rest of the front matter and its ordering. Only matches
    top-level (non-indented) keys to avoid clobbering nested fields.
    """
    kept_lines = []
    for line in front_matter.splitlines():
        if re.match(r"^expired_reason\s*:", line):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def expire_chunk(chunk_path: Path, reason: str, dry_run: bool = False) -> bool:
    """Rename chunk to .expired.md and add expired_reason to front matter.

    Safety:
    - Removes any existing `expired_reason` line before adding the new one (no duplicates).
    - Preserves the original front-matter ordering otherwise.
    - Inserts the EXPIRED warning only once; skips when the body already contains it.
    - Renames `<name>.md` \u2192 `<name>.expired.md` (works even when stem already has dots).
    """
    if dry_run:
        return True

    try:
        content = chunk_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return False

        end_match = content.find("\n---", 3)
        if end_match == -1:
            return False

        front_matter = content[4:end_match]
        body = content[end_match + 4:]

        # 1. Strip existing expired_reason to avoid duplicates, then append the new one.
        cleaned_fm = _strip_existing_expired_reason(front_matter).rstrip()
        # Escape embedded double quotes in reason
        safe_reason = reason.replace('"', '\\"')
        new_front_matter = f"{cleaned_fm}\nexpired_reason: \"{safe_reason}\"\n"

        # 2. Insert EXPIRED warning only once.
        if EXPIRED_WARNING in body:
            new_body = body
        else:
            # Body typically begins with "\n\n# Title..."; preserve leading whitespace
            stripped = body.lstrip("\n")
            leading = body[: len(body) - len(stripped)]
            if not leading:
                leading = "\n\n"
            new_body = f"{leading}{EXPIRED_WARNING}\n\n{stripped}"

        new_content = f"---\n{new_front_matter}---{new_body}"

        # Rename file: <name>.md -> <name>.expired.md (handles names with dots like topic.subtopic.md)
        expired_path = chunk_path.with_name(chunk_path.stem + ".expired.md")
        chunk_path.write_text(new_content, encoding="utf-8")
        chunk_path.rename(expired_path)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Check documentation for staleness")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show detailed progress")
    parser.add_argument("--dry-run", action="store_true", help="Don't rename files")
    parser.add_argument("--expire", action="store_true", help="Actually expire stale docs")
    parser.add_argument("--project", type=str, help="Path to project root (defaults to cwd)")
    args = parser.parse_args()

    project_root = get_project_root(args.project)
    source_root = get_source_root(project_root)
    chunks_dir = project_root / ".readme" / "chunks"

    if not chunks_dir.exists():
        if args.json:
            print(json.dumps({"error": f"Chunks directory not found: {chunks_dir}", "total": 0, "valid": 0, "expired": 0}))
        else:
            print(f"Error: Chunks directory not found: {chunks_dir}", file=sys.stderr)
            print(f"Make sure you're in a project with .readme/chunks/ or use --project", file=sys.stderr)
        sys.exit(1)

    # Find all active chunks (not already expired)
    chunk_files = [
        f for f in chunks_dir.glob("*.md")
        if not f.name.endswith(".expired.md")
    ]

    if args.verbose:
        print(f"Project root: {project_root}", file=sys.stderr)
        if source_root != project_root:
            print(f"Source root: {source_root} (from .project-folder)", file=sys.stderr)
        print(f"Found {len(chunk_files)} active documentation chunks", file=sys.stderr)

    results = {
        "project": str(project_root),
        "total": len(chunk_files),
        "valid": 0,
        "review": 0,
        "expired": 0,
        "error": 0,
        "chunks": [],
    }

    for chunk_path in sorted(chunk_files):
        status = check_chunk(chunk_path, project_root, source_root=source_root, verbose=args.verbose)
        results["chunks"].append(asdict(status))
        results[status.status] = results.get(status.status, 0) + 1

        if args.verbose and not args.json:
            symbol = "\u2705" if status.status == "valid" else "\u274c" if status.status == "expired" else "\u26a0\ufe0f"
            print(f"{symbol} {status.path}: {status.status}", file=sys.stderr)
            for reason in status.reasons:
                print(f"   {reason}", file=sys.stderr)

        # Expire if requested
        if args.expire and status.status == "expired":
            reason = "; ".join(status.reasons)
            if expire_chunk(chunk_path, reason, dry_run=args.dry_run):
                if args.verbose:
                    action = "Would expire" if args.dry_run else "Expired"
                    print(f"   {action}: {chunk_path.name}", file=sys.stderr)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\nSummary:")
        print(f"  Project: {project_root}")
        print(f"  Total chunks: {results['total']}")
        print(f"  Valid: {results['valid']}")
        print(f"  Review (soft / drifted): {results.get('review', 0)}")
        print(f"  Expired (hard / missing source): {results['expired']}")
        print(f"  Errors: {results['error']}")

        if results["expired"] > 0:
            print(f"\nExpired chunks:")
            for chunk in results["chunks"]:
                if chunk["status"] == "expired":
                    print(f"  - {chunk['path']}")
                    for reason in chunk["reasons"]:
                        print(f"      {reason}")
                    if chunk.get("uncommitted_sources"):
                        print(f"      Uncommitted sources: {', '.join(chunk['uncommitted_sources'])}")

    # Exit with code 1 if any expired
    sys.exit(1 if results["expired"] > 0 else 0)


if __name__ == "__main__":
    main()
