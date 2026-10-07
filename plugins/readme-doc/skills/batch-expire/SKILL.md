---
name: batch-expire
description: Aggressively validate all active documentation chunks and mark stale ones as expired (the mark-expired half of the two-step refresh flow). Use when the user wants to validate docs freshness or prepare stale chunks for refresh.
argument-hint: "(optional) 'just report' to skip renaming"
---

# doc:batch-expire — validate freshness, mark stale chunks expired

This skill is the **mark-expired** half of the two-step refresh flow:
1. `doc:batch-expire` (this) — finds stale chunks, renames them to `.readme/chunks/*.expired.md`.
2. `doc:update` — refreshes (or deletes) those `.expired.md` files.

It runs bundled Python scripts directly (no sub-agent). All doc paths are project-root
relative: active chunks `.readme/chunks/*.md`, expired `.readme/chunks/*.expired.md`,
section indexes `.readme/sections/*.index.md`. Freshness tracking applies to chunks, not
section indexes.

Resolve `PLUGIN_ROOT` before running the commands below. In Claude Code use
`PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"`; in Codex resolve the plugin root from this skill's
installed path (two directories above `SKILL.md`).

## Step 1 — scan + report (JSON)

```bash
python3 "${PLUGIN_ROOT}/scripts/check-docs-expiry.py" --json
```

The script scans `.readme/chunks/*.md` (excluding `*.expired.md`), checks each chunk's
`source_paths`, and flags a chunk expired when: a source file is missing; a source file was
modified (committed changes since `last_verified_at`); there are uncommitted source changes
(`git status --porcelain`); or `last_verified_at` is missing. Report "Found X expired out
of Y", with the reason(s) per chunk.

## Step 2 — mark expired (default)

```bash
python3 "${PLUGIN_ROOT}/scripts/check-docs-expiry.py" --expire --verbose
```

`expire_chunk` is idempotent: removes any prior `expired_reason` before adding a new one,
preserves frontmatter order, inserts the `**⚠️ EXPIRED**` warning once, and renames
`<topic>.md` → `<topic>.expired.md` correctly even with dotted filenames. **Skip Step 2
only if the user says "just report" / "don't rename".**

## Step 3 — regenerate the manifest

```bash
python3 "${PLUGIN_ROOT}/scripts/generate-docs-manifest.py" 2>/dev/null || true
```

Writes `.readme/docs-manifest.json`.

## After completion

Summarize "Validated N chunks, marked M expired" and tell the user the next step: run
`doc:update` to refresh the expired docs.

## Escape hatches

- `--project /path/to/project` overrides project root if auto-detection from cwd fails.
- The checker auto-detects the project root from cwd by finding `.readme/`; split-layout
  workspaces with a `.project-folder` pointer are supported.
