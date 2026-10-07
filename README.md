# readme-doc

Shared context for coding agents. `readme-doc` builds a local knowledge space inside your project, a `.readme/` folder of small, verified notes, so every agent session starts from what earlier sessions learned instead of re-reading the codebase.

It works with **Claude Code** and **Codex**. Both read the same files, so knowledge one agent writes, the other uses.

## Who it's for

Best suited to **small and medium-sized projects**: past the point where an agent can hold the whole codebase in context, and small enough that one person or a small team keeps the notes current. Typical signs you're there:

- Agents keep re-discovering the same gotchas.
- The same question about how a part of the system works comes up every week.
- Your `CLAUDE.md` or `AGENTS.md` is turning into a wall of text.

A one-file script rarely needs it. A very large codebase usually needs dedicated documentation tooling.

## How the knowledge space works

Three tiers, so an agent reads only what the task needs:

```
CLAUDE.md "Documentation Sections" table      ← Tier 0: the index every agent loads first
  └─ .readme/sections/<topic>.index.md         ← Tier 1: one page per area, listing its notes
       └─ .readme/chunks/<topic>.<subtopic>.md ← Tier 2: the knowledge itself
.readme/docs-manifest.json                     ← generated index of every section and chunk
```

- **Chunks are small and specific.** Each one names real files, a concrete pattern and at least one gotcha from your project.
- **Chunks know what they describe.** YAML frontmatter records `source_paths` and `last_verified_at`.
- **Stale notes get caught.** `doc:batch-expire` checks each chunk against the files it describes and marks outdated ones `*.expired.md`. `doc:update` then refreshes only those.
- **One entry file.** The index lives in `CLAUDE.md`. `AGENTS.md`, which Codex reads first, is a one-line pointer containing `CLAUDE.md`, so both agents land on the same table.

## Skills

| Skill | What it does |
| --- | --- |
| `doc:init` | Builds or extends the knowledge space for a part of the codebase. |
| `doc:task` | Records the work just finished in a session. You pass a short summary; the writer checks it against the code before writing. |
| `doc:batch-expire` | Finds chunks whose source files changed and marks them expired. |
| `doc:update` | Refreshes expired chunks, and only those. |

The writing itself happens in an isolated writer agent (`agents/readme-doc-writer.md`), so heavy source reading stays out of your main session. Claude Code runs it as a bundled sub-agent. Codex reads the same instructions and runs them in its own sub-agent.

## Install

### Claude Code

```
/plugin marketplace add xhuang9/readme-doc
/plugin install doc@readme-doc
```

### Codex

```bash
codex plugin marketplace add xhuang9/readme-doc
codex plugin add doc@readme-doc
```

Then run `doc:init` in your project to build the first sections.

## Split workspaces

If your agent guidance lives in a workspace folder and the code in a child folder, add a `.project-folder` file at the workspace root naming that child folder. The scripts find the project from it.

## Licence

MIT.
