---
name: task
description: Document the work completed in the current conversation thread into the project's .readme/ docs. Use after implementing a feature or making changes, or when the user asks to capture/document what was just built.
argument-hint: "[specific focus areas]  (optional)"
---

# doc:task — delegate to the `readme-doc-writer` agent (task mode)

The agent runs in an isolated context and **cannot see this conversation**, so YOU (main
thread) must hand it the facts.

**Do this:**

1. From the current conversation, write a concise **work summary**: what was built/changed,
   the key files touched, new patterns/conventions/decisions, config changes, and anything
   non-standard worth documenting. (This is the part only you can do — the agent has no
   access to the thread.)
2. Spawn the isolated **`readme-doc-writer`** sub-agent, passing **MODE: task**, your work
   summary, and `$ARGUMENTS`:
   - Claude Code: use the bundled Agent tool with
     `subagent_type: "doc:readme-doc-writer"`, `model: "sonnet"`.
   - Codex: read `../../agents/readme-doc-writer.md`, `../../references/templates.md`, and
     `../../references/enforcement-rules.md` relative to this skill, then spawn a Codex
     sub-agent with the complete writer instructions and absolute reference/script paths.
   Tell it to verify the summary against actual code, create/refresh the relevant section
   indexes + chunks, update the entry-file table, and regenerate the manifest.
3. Relay the agent's summary of what it documented.

> Route durable BEHAVIOURAL rules (a "never do X" / "always do Y" guardrail) to a guardrail
> skill via `local-skills`, not only a chunk — a chunk is read only if its section is
> opened, whereas a guardrail skill's description auto-invokes. Mention this to the agent so
> it flags such items rather than burying them.

> Claude pins the bundled agent to `sonnet`; Codex uses its available full-capability sub-agent.
