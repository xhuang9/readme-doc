# Documentation Templates

These templates reflect the **current, real** format of a mature `.readme/` tree
(reverse-engineered from a production project — the source of truth). Follow them exactly.

## The three tiers

```
<entry file> "Documentation Sections" table ← Tier 0: the root index IS a table in the entry file
  └─ .readme/sections/<topic>.index.md       ← Tier 1: section TOC (Purpose/Scope/Chunks)
       └─ .readme/chunks/<topic>.<subtopic>.md  ← Tier 2: the actual knowledge
.readme/docs-manifest.json                   ← generated index of every section + chunk
```

The entry file's "Documentation Sections" table is the top tier — that table is the root index.

**Entry file.** One real file holds the table: `CLAUDE.md`. `AGENTS.md`, which Codex and most other agents read first, is a pointer whose whole content is the text `CLAUDE.md`.

- `CLAUDE.md` exists → write the table there. Never copy it into `AGENTS.md`.
- Only `AGENTS.md` exists and holds real content → write the table in `AGENTS.md`.
- Neither exists → create `CLAUDE.md`, and an `AGENTS.md` containing only `CLAUDE.md`.

## Naming

- Chunks: strict kebab-case `<topic>.<subtopic>.md` — e.g. `billing.refund-window.md`, `sync.offline-queue-replay.md`. Topics cluster (`architecture.*`, `billing.*`, `sync.*`).
- Sections: `<topic>.index.md`.

---

## Tier 0 — entry-file "Documentation Sections" row

Add/maintain one row per section in the table under `## Documentation Sections` in
the entry file. Exact column format:

```markdown
| Section | Purpose | Read when |
|---------|---------|-----------|
| `<topic>.index.md` | <one-line purpose; may name a specific high-value chunk inline as `code`> | <comma-separated trigger contexts> |
```

- Section cell is the bare `<topic>.index.md` in backticks.
- Purpose may inline-reference a notable chunk: ``see `.readme/chunks/<topic>.<subtopic>.md` for …``.
- "Read when" is a comma-separated list of concrete trigger scenarios.

---

## Tier 1 — Section index (`.readme/sections/<topic>.index.md`)

```markdown
---
last_verified_at: <ISO-8601, e.g. 2026-01-17T09:12:39Z>
source_paths:
  - <path or dir, e.g. package.json or src/lib/local-db/>
---

# <Section Name>

## Purpose
<one sentence: what this section covers>

## Scope
<2–4 bullet lines or short prose: the boundaries of this section>

## Chunks

- `.readme/chunks/<topic>.<subtopic>.md` — <dense content summary>. Read when: <comma-separated concrete trigger contexts>.
- `.readme/chunks/<topic>.<other>.md` — <…>. Read when: <…>.
```

Chunk entries are ONE line each: path — summary — `Read when:` triggers, all on the same
line (the manifest generator greps for `Read when:` near the chunk path). Merge redundancy
between summary and triggers, but keep every unique trigger keyword (error strings, file
names, feature names, symptoms) — those are how a fresh agent finds the chunk.

Keep section indexes lean (≈30–50 lines): a TOC + a short domain overview. Implementation
detail lives in the chunks.

---

## Tier 2 — Chunk (`.readme/chunks/<topic>.<subtopic>.md`)

```markdown
---
last_verified_at: <ISO-8601>
source_paths:
  - <real path(s) the chunk documents; dirs OK, e.g. src/services/sync/>
  - <use the [project-folder]/ placeholder for split-workspace repos>
# optional:
# title: <override H1 used in the manifest display>
# metadata:
#   type: reference | feature | gotcha
---

# <Feature / System Name>

## Purpose
<one sentence: what problem this solves / what it is>

## <Semantic sections as the topic demands — pick what fits>
<e.g. "## Key Deviations", "## Architecture / Implementation", "## Render conditions",
"## Changes by Phase". Use real file paths and concrete patterns.>

## Gotchas / Constraints
<the non-obvious traps; for bug/trap chunks use the Symptom → Root Cause → Detection →
Prevention shape that this project favours>
```

Chunk rules (match the real tree):
- **Frontmatter is YAML** with `last_verified_at` (ISO-8601) + `source_paths` (array). Optional `title:` overrides the H1 in the manifest; optional `metadata.type`.
- Size ≈ 15–50 lines typical; longer for genuine narratives (refactors, architecture).
- **Code examples are pedagogical** — a short excerpt that illustrates the pattern.
- Every chunk has **≥1 real file path, ≥1 concrete pattern/config, ≥1 specific gotcha/constraint**.
- **Link related chunks inline yourself:** ``see `.readme/chunks/<other>.md```.
- **Name systems by what they do**, so the chunk reads correctly on its own after planning docs are removed.

---

## Minimal chunk (simple feature)

```markdown
---
last_verified_at: <ISO-8601>
source_paths:
  - <path>
---

# <Feature Name>

## Purpose
<one sentence>

## Implementation
- Location: `<file/path>`
- Pattern: <brief>

## Gotchas
- <key thing to know>
```

---

## Manifest (`.readme/docs-manifest.json`)

The script writes it. Regenerate it after any docs change. `PLUGIN_ROOT` is `${CLAUDE_PLUGIN_ROOT}` in Claude Code; elsewhere it is the plugin folder, two directories above any of its `SKILL.md` files:

```bash
python3 "$PLUGIN_ROOT/scripts/generate-docs-manifest.py" 2>/dev/null || true
```

Shape (for reference): `{ generated_at, project, counts:{sections,active_chunks,expired_chunks}, items:[ { path, kind, status, title, last_verified_at, source_paths, expired_reason, read_when } ] }`.
