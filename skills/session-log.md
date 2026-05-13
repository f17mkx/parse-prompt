---
name: session-log
description: Synthesis-append for the current session log. Use when you have an architecture decision, a failed attempt, or a surprising discovery worth preserving — something the raw session storage can't regenerate. The session-log-finalize Stop hook creates the directory and copies prompt-analysis files automatically; this skill is for the synthesis layer on top.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(ls *)
  - Bash(cat *)
  - Bash(date *)
  - Bash(git rev-parse *)
  - Bash(mkdir *)
---

# /session-log — session-log synthesis append

The `session-log-finalize.sh` Stop hook creates `session-logs/<YYYY-MM-DD>-<branch-topic>/` automatically and copies all `.context/prompt-analysis*.md`, `notes.md`, and `todos.md` into it. What the hook does NOT do is the **synthesis**: what was the architectural decision in this session, which approach didn't work, what surprising thing did you discover.

That synthesis is the only thing the raw session storage can't reconstruct. This skill captures it.

## When to use

- You made an architectural decision with trade-offs (pattern, schema, library, API shape)
- You tried an approach that DIDN'T work (failed-attempt — valuable for future sessions that should avoid the same mistake)
- You found something surprising in the code/system (surprising-discovery — e.g. "feedback hook silently fails when CLAUDE_SESSION_ID env var is missing")
- The user explicitly says "log that in the session"

## When NOT to use

- Routine implementation without synthesis-worthy context (the Stop hook stub is enough — prompt-analysis-N.md is already the record)
- Anything already in git log or CHANGELOG (that's not session-log material)
- Anything that belongs in CLAUDE.md / persistent memory (long-lived cross-session knowledge)

## Inputs

`/session-log [architecture|failure|discovery|free] <title>`

Default mode if called without arguments: `free`. Title is asked back if not inline.

## Workflow

1. **Find the session-log directory:** `session-logs/<YYYY-MM-DD>-<branch-topic>/` in the current workspace
   - Topic = branch name with optional org/user prefix stripped, no trailing `-vN`
   - Stop hook has already created it — if missing, create manually
2. **Read the existing session-log.md** (auto-stubbed by the hook)
3. **Append a `### <Title>` section** with the mode-specific body below
4. **Append a `.context/notes.md` entry**: `## /session-log <mode> <title> - <YYYY-MM-DD HH:MM>` with one line
5. **Confirm in one line**: `✅ Session-log appended: <Title> in <path>`

## Body format per mode

### Mode: `architecture`

```markdown
### <Title>

**Decision:** <what was decided, 1-2 sentences>
**Trade-off:** <what we gave up, 1 sentence>
**Why now:** <trigger, 1 sentence>
**Reversibility:** <how hard would rollback be, 1 sentence>
```

### Mode: `failure`

```markdown
### Failed: <Title>

**Tried:** <what was attempted, 1-2 sentences>
**Why it didn't work:** <diagnosis, 1-2 sentences>
**What worked instead:** <the plan-B that did work>
**Lesson:** <generalizable takeaway>
```

### Mode: `discovery`

```markdown
### Discovery: <Title>

**Found:** <what was discovered, 1-2 sentences>
**Where:** <path / component / system>
**Implication:** <why it matters for future sessions>
```

### Mode: `free`

```markdown
### <Title>

<free text, 2-5 lines, your voice>
```

## Examples

```
/session-log architecture INBOX-Sunset variant C over A
```
writes:
```markdown
### INBOX-Sunset variant C over A

**Decision:** parse-prompt routes items directly into domain files; the legacy INBOX file is deprecated.
**Trade-off:** the verbatim-block format of the INBOX is gone. Per-item routing is more code but spares a 1456-line dead-letter file.
**Why now:** observation that the INBOX was a write-only sink — no downstream skill ever read it.
**Reversibility:** medium — variant A (full removal) would be a 30min revert. Variant C back to INBOX-append would be 1h.
```

```
/session-log failure parse-projectx skill-inception approach
```
writes:
```markdown
### Failed: parse-projectx skill-inception approach

**Tried:** parse-prompt should call parse-projectx internally via the Skill tool.
**Why it didn't work:** Skill-tool invocation from within a running skill caused a double hook roundtrip — performance + complexity hit.
**What worked instead:** parse-prompt inlined parse-projectx's logic directly in Step 5.
**Lesson:** skills are instructions, not functions. Inline is usually better than skill-to-skill calls.
```

```
/session-log discovery feedback-hook silent-fails
```
writes:
```markdown
### Discovery: feedback-hook silent-fails

**Found:** route-feedback.py on the Stop hook had logged 47 classifications but updated 0 outcomes.
**Where:** hooks/route-feedback.py + data/routing.db
**Implication:** the routing DB is passively collecting, not learning. Likely cause: CLAUDE_SESSION_ID env var missing in the Stop-hook context. Fix needed.
```

## Anti-patterns

- **DON'T call this for every session.** When nothing synthesis-worthy happened (~90% of sessions), the auto-stub from the hook is enough.
- **DON'T document routine implementation here.** That's code + commit + CHANGELOG.
- **DON'T dump verbatim user quotes here.** Those are in `prompt-analysis-N.md`. This file is for synthesis.
- **DON'T dump tool-call logs here.** Session storage already has that — irrelevant for future-self.

## Relation to other skills + hooks

- **session-log-finalize.sh** (Stop hook, automatic): creates the directory + copies prompt-analysis*.md / notes.md / todos.md. Handles the file boilerplate.
- **/session-log** (manual, this skill): does the synthesis. Adds what the hook can't know.
- **/parse-prompt** (UserPromptSubmit hook, automatic): writes prompt-analysis-N.md that the Stop hook copies.

## Logging in `.context/notes.md`

After every append:

```markdown
## /session-log <mode> <title> - YYYY-MM-DD HH:MM
- Appended to session-logs/<date>-<topic>/session-log.md
```
