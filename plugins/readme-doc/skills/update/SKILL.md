---
name: update
description: Refresh all expired documentation chunks by updating or deleting them. Use after /batch-expire has marked stale chunks, or when the user asks to refresh expired docs.
argument-hint: "(optional) focus area"
---

# doc:update — delegate to the `readme-doc-writer` agent (update mode)

Refreshing expired chunks means re-reading each chunk's `source_paths` and rewriting from
current reality — isolate it in the agent.

**Hard scope:** the expired chunks (`.readme/chunks/*.expired.md`) and the section indexes /
entry-file rows that reference them. (Create new docs or touch other chunks only if the user
explicitly asks.)

**Do this:** spawn the isolated **`readme-doc-writer`** sub-agent, passing **MODE: update**
and `$ARGUMENTS`.

- Claude Code: use the bundled Agent tool with
  `subagent_type: "doc:readme-doc-writer"`, `model: "sonnet"`.
- Codex: read `../../agents/readme-doc-writer.md`, `../../references/templates.md`, and
  `../../references/enforcement-rules.md` relative to this skill, then spawn a Codex
  sub-agent with the complete writer instructions and absolute reference/script paths.

Example task:

> MODE: update. Glob `.readme/chunks/*.expired.md`. For each: read its `source_paths` — if the source still exists, refresh ONLY that chunk to match reality, rename back to `<topic>.md`, bump `last_verified_at`, clear `expired_reason`; if the source is gone, delete the chunk and remove its references from the section index + entry-file table. Keep to the expired chunks. Regenerate the manifest. Return the summary.

When it returns, relay its summary (chunks updated / deleted, manifest counts).

> Claude pins the bundled agent to `sonnet`; Codex uses its available full-capability sub-agent.
