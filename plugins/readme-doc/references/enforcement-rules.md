# Enforcement Rules

Follow these on every run — they keep documentation complete and trustworthy.

## Working rules

### Rule 1 — Follow every step, in order
Run the workflow as **Discovery → Planning → Writing → Verification → Registration**, each
step depending on the previous: read the source during Discovery, list the files during
Planning, update the entry-file table during Registration, regenerate the manifest at the end.

### Rule 2 — Write real, specific content
Every section carries concrete content drawn from this codebase: actual file paths, real
config values, the behaviour you observed in the source. Each line is specific enough that it
could only describe this project.

### Rule 3 — Document from the source
Read the actual source files, trace the code paths, and verify each claim against the
implementation before you write it.

### Rule 4 — Complete the whole set
Each documentation request results in:
- [ ] Section index created/updated (`.readme/sections/<topic>.index.md`)
- [ ] All relevant chunks created (`.readme/chunks/<topic>.<subtopic>.md`)
- [ ] A row in the entry file's "Documentation Sections" table (the root index) for the section
- [ ] Related chunks linked inline to each other
- [ ] `.readme/docs-manifest.json` regenerated

### Rule 5 — Verify each file
After creating any file, confirm:
```
[ ] YAML frontmatter present: last_verified_at (ISO-8601) + source_paths (array)
[ ] Every source_path resolves on disk
[ ] Every section has specific, real content
[ ] Code examples come from the actual codebase (pedagogical excerpts)
[ ] "Read when" triggers are specific
[ ] Related chunks are linked
[ ] Systems are named by their behaviour (self-contained, readable without planning docs)
```

## Workflow gates

- **Gate 1 (pre-writing):** list the source files to document, read each, outline what you
  will write, and confirm the chunk doesn't already exist.
- **Gate 2 (post-writing, each file):** re-read it, check it against the template, confirm the
  content is specific and `source_paths` resolve.
- **Gate 3 (integration):** the section lists all its chunks, the entry-file table lists the
  section, all cross-references resolve, and the manifest is regenerated.

## Quality thresholds

| File | Typical size | Required structure |
|------|--------------|--------------------|
| Section index | ~30–50 lines | Purpose, Scope, Chunks (one line per chunk: path — summary. `Read when:` triggers, same line) |
| Chunk | ~15–50 lines (narratives may exceed) | Purpose + topic-appropriate semantic sections + Gotchas/Constraints |

**Token economy:** write for an agent, not a reader — dense, specific, zero narration.
No throat-clearing, no restating adjacent code in prose, one example per pattern (the best
one). Every sentence must carry a fact an agent acts on; if a sentence could describe any
project, delete it.

**Specificity — every chunk includes at least:** 1 real file path, 1 concrete code pattern or
config value, 1 specific gotcha or constraint.

## Project-format rules (these win over any generic convention)

- **Root index = the entry file's "Documentation Sections" table.** The top tier lives there;
  add one row per section.
- **Frontmatter is YAML:** `last_verified_at`, `source_paths`, optional `title` / `metadata.type`.
- **Name systems by what they do**, so each chunk reads correctly on its own after planning
  docs are removed.
- **Use the `[project-folder]/` placeholder** in `source_paths` for split workspace-root /
  project-folder repos.

## Model

Run at **`sonnet` or higher** — the invoking skills pin `model="sonnet"`. If the resolved
model is ever lower, stop and report before touching existing chunks (lower tiers can drop
chunks instead of refreshing them).

## Quality practices

1. **Read the source before writing any claim.**
2. **Keep every line specific to this project.**
3. **Finish the whole set** — section index, chunks, entry-file row, and manifest — before stopping.
4. **List every new chunk** in its section index and the entry-file table.
5. **Refresh related chunks and their cross-links** as you go.
6. **Run the expiry/update lifecycle at `sonnet`+** so refreshes are safe.
