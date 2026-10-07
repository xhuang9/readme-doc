---
name: init
description: Create or update LLM-optimized project documentation (.readme/ 3-tier system). Use when (1) starting a new project needing docs structure, (2) after major architectural changes, (3) documenting custom patterns/integrations, (4) the user explicitly requests documentation, (5) the user runs the init command. Writes section indexes + chunks and maps them from the entry file's "Documentation Sections" table.
argument-hint: "[scope or focus area]  e.g. 'src/services/sync' or 'the whole project'"
---

# doc:init — delegate to the `readme-doc-writer` agent (init mode)

Creating docs means reading source across the codebase and writing many files — heavy work
whose only deliverable is the doc tree. Isolate it in the bundled agent.

**Do this:** spawn the isolated **`readme-doc-writer`** sub-agent, passing **MODE: init** plus
the scope (`$ARGUMENTS`; if none, ask what to document or default to a full-project pass).

- Claude Code: use the bundled Agent tool with
  `subagent_type: "doc:readme-doc-writer"`, `model: "sonnet"`.
- Codex: read `../../agents/readme-doc-writer.md`, `../../references/templates.md`, and
  `../../references/enforcement-rules.md` relative to this skill, then spawn a Codex
  sub-agent with the complete writer instructions and absolute reference/script paths.
  Use the available full-capability sub-agent.

Example task:

> MODE: init. Document <scope or 'this whole project'>. Read the plugin's `references/templates.md` + `enforcement-rules.md` and copy the existing `.readme/` conventions exactly. Run Discovery → Planning → Writing → Verification → Registration, update the entry file's "Documentation Sections" table, and regenerate the manifest. Return the summary.

When it returns, relay its summary (sections/chunks created, entry file updated, manifest
counts) — relay the summary only; the chunk bodies stay in the agent's context.

> Claude pins the bundled agent to `sonnet`. Codex uses its available full-capability
> sub-agent. The writer instructions own the methodology + templates; this skill is the trigger.
