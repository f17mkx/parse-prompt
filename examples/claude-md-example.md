# CLAUDE.md additions for adopters

If you use Claude Code (or a compatible harness that reads project-level instruction files), add the snippet below to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for global). It tells the agent how to behave with parseprompt's tripwire and the per-turn analysis discipline.

Adapt paths to your installation.

---

## Snippet — drop into CLAUDE.md

```markdown
## Parse-prompt enforcement (tripwire)

The `UserPromptSubmit` hook writes `.context/.parse-prompt-tripwire` per prompt. A `PreToolUse` hook (matcher `Write|Edit`) blocks persistent file changes until a fresh `.context/prompt-analysis-<N>.md` exists. The agent must run `/parse-prompt` (or manually write the analysis) before editing code/docs.

Bypass paths (intentionally allowed):
- `Read`, `Grep`, `Glob`, `Bash` — always allowed (investigation without enforcement)
- `Write` to `.context/prompt-analysis*.md` — allowed, clears tripwire (skill-escape)

Scripts: `<install_root>/hooks/parse-prompt-tripwire-write.sh` + `<install_root>/hooks/parse-prompt-tripwire-check.sh`.

## Skill context logging

**Every skill invocation** must append an entry to `.context/notes.md` in the workspace (create the file if missing). `.context/` is gitignored — this is workspace-local state only.

Format:
```
## /<skill-name> [args] - <date>
- What was done (1–3 bullets)
```

## Session logging

The session-log-finalize Stop hook auto-creates `session-logs/<YYYY-MM-DD>-<branch-topic>/` and copies all `.context/prompt-analysis*.md`, `notes.md`, and `todos.md` into it.

For synthesis (architecture decisions, failed attempts, surprising discoveries), use the `/session-log` skill — adds a `### <Title>` section to `session-log.md`.

For routine sessions: the auto-stub from the hook is enough, no manual append needed.

## Routing & persistence

`<install_root>/docs/ARCHITECTURE.md` is the master index for the 2 routing layers (parse-prompt skill + routing.db hook). Read it before editing any routing-infrastructure file:

- `<install_root>/skills/parse-prompt.md`
- `<install_root>/skills/trigger.md`
- `<install_root>/hooks/route-prompt.py`
- `<install_root>/hooks/route-feedback.py`
- `<install_root>/lib/routing.py`

For a project-specific classifier (e.g. `/parse-<projectname>`), see `<install_root>/docs/INTEGRATIONS.md` §3 and the case study in `<install_root>/docs/examples/parse-projectx-case-study.md`.
```

---

## Why these rules?

**Tripwire enforcement** ensures every prompt gets a structured analysis before code changes. Without it, parse-prompt is just a recommendation and gets skipped under deadline pressure — exactly when you need the discipline most.

**Skill context logging** is how a future you (or another agent picking up the workspace later) reconstructs what already happened. `.context/notes.md` is workspace-local, low-cost to maintain, high-signal to read.

**Session logging** is how the work survives merge. `prompt-analysis*.md` files are gitignored on purpose (they're rough drafts) but the session-log Stop hook copies them into a tracked session-logs dir before the session ends.

**Routing & persistence** is the architectural layer. Adopters who edit it without reading ARCHITECTURE.md will break things that other adopters depend on (the `prompt_classifications` table schema, the tripwire skill-escape contract, etc.). The reminder is a low-friction nudge.
