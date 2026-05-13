# Session Lifecycle

Full pipeline of a single user prompt — from the moment it lands until the session log is archived. This is what "complete prompt processing" looks like end-to-end.

```
┌─ UserPromptSubmit ─────────────────────────────────────────────────────┐
│                                                                         │
│  1. parse-prompt-tripwire-write.sh  (writes .context/.parse-prompt-tripwire)
│  2. <your custom hooks here>                                            │
│  3. route-prompt.py                 (classifies, writes routing.db row, │
│                                      auto-appends to .context/todos.md  │
│                                      if intent=backlog,                 │
│                                      emits candidate systemMessage)     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    Agent reads tripwire, runs /parse-prompt skill
                                  │
                                  ▼
            Skill writes .context/prompt-analysis-N.md
            + routes 4.1/4.6/4.7 items to docs/BACKLOG.md (or delegate)
            + logs to .context/notes.md
                                  │
                                  ▼
                  Tripwire cleared (the prompt-analysis write itself)
                                  │
                                  ▼
              Agent does the actual work (Read, Edit, Write, Bash, ...)
                                  │
              ┌─ PreToolUse (per tool call) ──────────────────────────┐
              │                                                         │
              │  1. parse-prompt-tripwire-check.sh  (passes if cleared) │
              │  2. routing-edit-reminder.sh        (advisory on        │
              │                                      routing-infra      │
              │                                      file edits)        │
              │                                                         │
              └─────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                                Stop
                                  │
                  ┌─ Stop hooks ─────────────────────────────────────┐
                  │                                                    │
                  │  1. route-feedback.py  (updates routing.db keyword│
                  │                         weights based on which    │
                  │                         capabilities were actually │
                  │                         invoked vs recommended)    │
                  │  2. session-log-finalize.sh  (creates              │
                  │                              session-logs/<date>/, │
                  │                              copies prompt-        │
                  │                              analyses, notes,      │
                  │                              todos)                │
                  │                                                    │
                  └────────────────────────────────────────────────────┘
```

---

## What persists where

| Artifact | Lives | Lifetime | Tracked? |
|---|---|---|---|
| Tripwire | `.context/.parse-prompt-tripwire` | per turn | gitignored |
| Per-turn analysis | `.context/prompt-analysis-N.md` | until session-log archive | gitignored, archived at Stop |
| Skill-invocation log | `.context/notes.md` | until session-log archive | gitignored, archived at Stop |
| Workspace-local todos | `.context/todos.md` | session-bridging | gitignored, archived at Stop |
| Routing classifications | `routing.db` `prompt_classifications` table | indefinite (DB) | gitignored |
| Session-log dir | `session-logs/<YYYY-MM-DD>-<branch-topic>/` | permanent | git-tracked |
| Backlog items (4.1) | `docs/BACKLOG.md` (Tomorrow / Now / Soon) | until done | git-tracked |
| Future-work items (4.6) | `docs/BACKLOG.md ## Future` / `## Someday` / `## Ideas` | until decided | git-tracked |
| Tentative items (4.7) | `docs/BACKLOG.md ## Tentative` | until evaluated | git-tracked |
| Synthesis (manual) | `session-logs/<...>/session-log.md` | permanent | git-tracked |

---

## The two-loop persistence story

**Inner loop (per turn):**
- UserPromptSubmit → tripwire forces /parse-prompt → analysis written → routing done → tripwire cleared → work proceeds.

**Outer loop (per session):**
- Stop hooks: feedback updates routing weights, session-log finalize archives the artifacts.

The architecture's strength is that both loops are independent: the inner loop runs for every prompt regardless of whether the outer loop is wired up. If you don't have a `SESSION_DB_PATH` configured, the feedback loop silently no-ops; everything else still works.

---

## Session-log directory structure

After Stop, the workspace has:

```
session-logs/2024-09-15-fix-timeline-bug/
├── session-log.md            # auto-stub by hook, optionally enriched by /session-log skill
├── notes.md                  # copy of .context/notes.md (skill invocations)
├── todos.md                  # copy of .context/todos.md (in-flight backlog signals)
├── prompt-analysis.md        # turn 1 full capture
├── prompt-analysis-2.md      # turn 2
├── prompt-analysis-3.md      # ...
└── 0001-some-plan.md         # any plan-files you wrote during the session
```

`<branch-topic>` is the current git branch with optional org/user prefix stripped (everything before the last `/`) and trailing `-vN` removed. Examples: `someuser/fix-timeline-bug-v2` → `fix-timeline-bug`. `feat/new-onboarding` → `new-onboarding`. `main` → `main`.

If multiple sessions land on the same date + topic with different HEAD commits, the hook appends `-1`, `-2`, ... to the directory name to disambiguate.

---

## When to use the `/session-log` skill

The Stop hook auto-stubs `session-log.md` with workspace + branch + commit metadata. It does NOT do the synthesis layer.

Use `/session-log` for:
- Architecture decisions with trade-offs
- Failed attempts (what didn't work, what worked instead)
- Surprising discoveries (something non-obvious you learned about the system)

DON'T use it for:
- Routine implementation (git log + CHANGELOG cover that)
- Verbatim user quotes (those are in prompt-analysis files)
- Tool-call dumps (your harness's session storage already has those)

About 90% of sessions don't need a manual `/session-log` append — the auto-stub is enough.

---

## Recovering past sessions

**If you need to know which skills/agents ran in a past session**: query your harness's session storage. parseprompt's session-log archive captures the *intent and decisions*, not the *tool-call trace* — your harness has the latter.

**If you need the structured analysis of a past prompt**: open `session-logs/<date>-<topic>/prompt-analysis-N.md`. Each is a complete 8-dimension parse for one turn.

**If you need to recover an idea that was supposed to make it to BACKLOG but didn't**: check `.context/prompt-analysis*.md` archived in session-logs. The 4.6 / 4.7 sections capture deferred and tentative items even if the routing layer missed them.

---

## Failure modes and recovery

**Tripwire stuck (nothing wrote prompt-analysis-N.md, hook keeps blocking):**
- Manually create an empty `.context/prompt-analysis.md` — the file's existence + recency clears the tripwire.
- Or delete `.context/.parse-prompt-tripwire` directly. (You're skipping the enforcement; do it deliberately.)

**routing.db missing or corrupted:**
- The hook silently fails (try/except wraps the DB write).
- Re-create from `data/schema.sql` + `data/seed-example.sql`.

**`SESSION_DB_PATH` not set or pointing at a nonexistent file:**
- `route-feedback.py` silently no-ops (no learning, but the rest works).
- See `docs/INTEGRATIONS.md` for known session-store schemas.

**session-log-finalize.sh fails mid-run:**
- The `cp -p` calls are idempotent — re-running is safe.
- The hook is best-effort by design (`exit 0` even on partial copy).

---

## Auditable trail

For any commit on a tracked branch, you can reconstruct the conversation that produced it:

1. The session-log dir is committed alongside the code change
2. `prompt-analysis*.md` shows what the user asked, what was extracted, what was routed
3. `notes.md` shows which skills ran
4. `session-log.md` (if `/session-log` was used) shows the synthesis: *why* this particular shape of solution

This is intentional. Prompt-analysis-as-archive is the auditable "why", separate from git's "what".
