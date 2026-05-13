---
name: handoff
description: "Knowledge-transfer doc for the next session. Writes `HANDOFF.md` into the current session-log directory so a fresh Claude (or you after `/compact`) can pick up where this one left off without re-reading the whole conversation. Adaptive length: terse when the work is done, verbose when it's a cliff-hanger. Pairs with /session-log."
user-invocable: true
---

# /handoff - next-session knowledge-transfer doc

Documents the current state of work so the next session (another Claude instance, or you after a `/compact`) knows where to continue without re-reading the entire conversation history.

**No code push.** That's `/ship`'s job (or your equivalent). `/handoff` only writes docs.

## When to invoke

- User types `/handoff` explicitly.
- User phrases: "document the state", "write a handoff", "write something for the next session", "session handover".
- "ship and handoff" or "handoff and ship": run both, `/handoff` first (so the doc lands in the commit), then `/ship`.
- NOT auto-trigger when user only says "ship". That's a separate flow.

## Adaptive length

Match the depth of the doc to the state of the work:

- **Done-state** (sprint finished, everything deployed, no open items): one short section "What lives now and where", one optional section "User hand-off items if any", skip the rest. Target: 30-50 lines.
- **Cliff-hanger** (work unfinished, next session must continue): unfold the full structure with sections "What got done", "What lives", "What's open", "Where to continue", "Known bugs / risks", "User hand-off items". Target: 100-200 lines.

Detect done-state when: all tasks completed, ship-equivalent ran successfully, no "TODO" or "NEXT-STEP" markers in your recent output. Otherwise treat as cliff-hanger.

## Pre-step: harvest from prompt-analysis files

If `.context/prompt-analysis-*.md` files exist AND there are more than five of them, sweep them for items you would otherwise lose:

- Unanswered questions (4.2)
- Open ambiguities (4.5)
- Deferred items (4.6)
- Tentative-action items that never got resolved (4.7)

These are the most common drift vectors between phases. Cite the source PA file number in the handoff so the next session can verify.

## Output path

Default location: `zzz-session-logs/<YYYY-MM-DD>-<branch-topic>/HANDOFF.md` where `<branch-topic>` is the current branch name with workflow-prefix stripped (e.g. `feat/login-flow` -> `login-flow`).

If the directory doesn't exist yet, create it. The session-log finalize hook will eventually populate it with `prompt-analysis-*.md` archives anyway.

## Structure (cliff-hanger version)

```markdown
# Handoff - YYYY-MM-DD

**Workspace:** <name>
**Branch:** <branch>
**Started:** <commit SHA at session start>
**Current:** <HEAD SHA>
**Sprint:** <one-line goal>

## What got done

- <bullet per merged PR or completed task>
- <reference: branch / PR# / file paths>

## What lives now

- <feature/file/route that's live and where it lives in the tree>
- <new env vars, new commands, new build steps>

## What's open

- <task X, status, blocker>
- <decision Y, options on the table, recommendation>
- <bug Z, repro steps, suspected cause>

## Where to continue

1. <first concrete action for the next session>
2. <second action>
3. <third action>

State the file paths and commands. Don't make the next session reinvent the navigation.

## Known bugs / risks

- <thing that might bite, mitigation if any>

## User hand-off items

- <questions the user needs to answer>
- <decisions the user needs to make>
- <verifications the user needs to do on the live app>

## Recovered from prompt-analysis files (if applicable)

- PA-12: deferred "dark mode" item, kept in `## Future`
- PA-23: tentative "swap auth library" item, still in `## Tentative`, no resolution this session
```

## Structure (done-state version)

```markdown
# Handoff - YYYY-MM-DD

**Workspace:** <name>
**Branch:** main (merged)
**Sprint:** <one-line goal> - DONE

## What lives now

- <feature, route, env var>
- <link to PR if helpful>

## User hand-off items (if any)

- <verification step on the live app>
- <follow-up question, deferred to a future session>
```

Done. Move on.

## Rules

1. **Adaptive length, not template-filling.** A done-state handoff that's 200 lines is noise; a cliff-hanger that's 30 lines is a future-debt time-bomb. Match length to state.
2. **State file paths and commands.** "Continue the login refactor" is useless. "Edit `src/auth/session.ts:42`, the TODO is the missing `await refreshToken()` call" is a handoff.
3. **Cite PA-files when relevant.** If a recovered item came from `prompt-analysis-12.md`, say so. The next session can verify.
4. **Don't duplicate `/session-log` synthesis.** `/handoff` is prospective (what's next), `/session-log` is retrospective (why decisions were made). Both live in the same session-log dir, both have value, neither should reproduce the other.
5. **Don't push code.** This is doc-only. The user runs `/ship` (or `git commit && git push`) separately.
