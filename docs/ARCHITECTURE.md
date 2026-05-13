# Architecture — Routing & Persistence

**Single source of truth** for: where does what land, which layer triggers when, what persists across sessions, what's advisory vs. blocking. Read this before changing anything in `skills/`, `hooks/`, or `data/`.

---

## TL;DR — the 2 persistence layers

| Layer | Where | Writes? | Reads? | Persistence |
|---|---|---|---|---|
| **L1 parse-prompt skill** | `skills/parse-prompt.md` (auto-hook UserPromptSubmit, then forced by tripwire) | YES — `docs/BACKLOG.md` and equivalents, `.context/prompt-analysis-N.md` | none | git-tracked (BACKLOG / project domain files), gitignored (.context) |
| **L2 routing.db hook** | `hooks/route-prompt.py` (auto-hook, fires after the tripwire) | YES — `routing.db` `prompt_classifications` row + `.context/todos.md` | YES — `capabilities`, `capability_keywords` for top-N candidates | SQLite, gitignored |

Optional L3 (project-specific): if your workspace has a project-specific status DB or domain DB (e.g. a per-project SQLite that's rebuilt by an ingest step from BACKLOG.md / PRs / ADRs), parse-prompt's writes to BACKLOG.md feed into it via your ingest pipeline. parseprompt itself doesn't ship an L3 — see `docs/examples/` for a worked case study.

**The leak this architecture closes**: an idea like "we could do X later" used to hit all three points and persist in **none** of them. Now it's caught at L1 (4.6 dimension → BACKLOG ## Future) AND at L2 (.context/todos.md auto-write). Belt-and-suspenders pre-commit audit (see INTEGRATIONS.md for the `/ship`-style pattern) catches multi-turn drift if both fail.

---

## 1. Hook order (UserPromptSubmit)

Recommended ordering in your harness's settings (e.g. `examples/settings.json`):

```
1. parse-prompt-tripwire-write.sh   # writes .context/.parse-prompt-tripwire (forces /parse-prompt before any Write/Edit)
2. <your custom UserPromptSubmit hooks here, if any>
3. route-prompt.py                  # classifies intent, queries routing.db, emits candidate systemMessage, AUTO-APPENDS to .context/todos.md when intent=backlog
```

**PreToolUse hooks**:

```
1. parse-prompt-tripwire-check.sh   (matcher: *)
2. routing-edit-reminder.sh         (matcher: Edit|Write — fires advisory message on routing-infrastructure file edits)
```

**Stop hooks**:

```
1. route-feedback.py                # processes current session + catches up older pending sessions (gracefully no-ops if SESSION_DB_PATH not set)
2. session-log-finalize.sh
```

The `/parse-prompt` skill itself is invoked manually by the agent in response to the tripwire (skill-as-imperative), NOT auto-hooked. So L1 routing happens later in the same turn, after the tripwire forces it.

## 2. parse-prompt 8-dimension parse → routing targets

| Dimension | Catches | Generic target | Stays in prompt-analysis only? |
|---|---|---|---|
| 4.1 Requirements | imperative verbs ("do", "ship", "change"…) + "should" | `docs/BACKLOG.md` | no, routed |
| 4.2 Questions | direct + implicit + clarification | — | yes |
| 4.3 Rejections | "not X", "instead Z" | — (exception: architectural rejections may become draft ADRs in projects that use ADRs) | yes |
| 4.4 Context Refs | paths, URLs, entity IDs, dates, prices | — | yes |
| 4.5 Risks/Ambiguities | unclear refs, conflicts, destructive actions | — | yes |
| 4.6 Future Work | "later", "we could", "would be nice", "for inspiration", "maybe" | `docs/BACKLOG.md ## Ideas` (or `## Future` / `## Someday` per project convention) | no, routed |
| 4.7 Tentative-Action | "eventuell", "(?)", "deep dive", "evaluate" | `docs/BACKLOG.md ## Tentative` | no, routed |
| 4.8 Implicit Followups | "X is done", "I renamed Y", state changes | `docs/BACKLOG.md ## Tomorrow` (with `[implicit-followup]` tag) | no, routed |

Dimension 4.6 was added after the team realized "deferral" was leaking — soft suggestions without a clear imperative were neither requirements (4.1) nor rejections (4.3), and the original parser had no bucket for them. 4.7 (Tentative) and 4.8 (Implicit) followed for the same reason: each closes a class of "user-said-something-meaningful-but-actionable-only-on-second-look" that the original 5 dimensions missed.

## 3. routing.db — what it actually does

**Schema** (`data/schema.sql` for the full DDL):

- `capabilities`: every skill + agent indexed by name + keywords
- `capability_keywords`: weighted keyword → capability mapping (used for scoring)
- `prompt_classifications`: per-prompt log w/ intent, complexity, candidates, outcome
- `routes` / `route_chain` / `route_modifiers`: optional advanced tables for multi-step pipelines (intentionally empty in the seed example — adopters fill in their own)

**Intent classifier** (`hooks/route-prompt.py` → `lib/routing.py` INTENTS, first-match-wins):

```
backlog → ship → confirm → sync → spawn → resume → audit → fix → batch → plan → draft → docs → investigate → meta → design
```

`backlog` is at position 1 deliberately so deferral signals win when both `backlog` and a broader pattern (`audit`, `plan`, etc.) match. The regex catches the obvious cases: `later|someday|nicht jetzt|for now|next release|wir könnten|we could|would be nice|wäre eine Idee|for inspiration|to draw from|i like the idea|maybe we|vielleicht|backlog|remember|merk|add to|speichere`.

**Action layer**: when `intent='backlog'`, the hook **auto-appends** to `.context/todos.md` in cwd:

```markdown
## YYYY-MM-DD HH:MM - backlog/deferral detected
> <verbatim prompt excerpt, 240 chars>

**Status:** Open. **Source:** route-prompt.py auto-detect (intent=backlog).
**Next:** parse-prompt 4.6 should promote to docs/BACKLOG.md ## Future/Someday/Ideas.
```

Idempotent (skips if first 60 chars already in file). Fail-safe (try/except, never breaks the hook).

## 4. The triple-catch for deferred ideas

Soft suggestions ("we could do X later") used to evaporate: classified as audit/plan, parse-prompt put them in 4.3 Decisions ("not now"), 4.3 was prompt-analysis-only, prompt-analysis got committed but no human-readable backlog entry surfaced.

**What's different now**:

- L1 parse-prompt 4.6 catches them as Future Work → routes to `docs/BACKLOG.md ## Future / ## Someday / ## Ideas`
- L2 route-prompt.py classifier `backlog` priority + `.context/todos.md` auto-write
- Optional L3 `/ship`-style pre-commit audit (see INTEGRATIONS.md): cross-checks `.context/prompt-analysis*.md` and `.context/todos.md` against the tracked diff before allowing a commit. Advisory gate, not hard block

Three independent catches — any one prevents the leak.

## 5. `.context/todos.md` — the workspace-local todo store

**What it is**: a known file pattern. `session-log-finalize.sh` mirrors it to `session-logs/<date>-<topic>/todos.md` at session end. Also **auto-written** by `route-prompt.py` when intent=backlog.

**Pros**:

- Workspace-local, gitignored — no commit pressure for in-flight todos
- Auto-archived at session end alongside `notes.md` and `prompt-analysis-*.md`
- Complement to `notes.md` (which is the skill-invocation log, not the todo list)
- Survives across turns within a session, distinct from in-conversation TaskCreate (which evaporates after session)

**Distinction from in-conversation task tools**: those are in-session breakdowns visible in your harness's session storage — they evaporate after the session. `.context/todos.md` is session-bridging persistence — for things to revisit when you reopen the workspace.

## 6. Per-item routing (interpretation-based)

When a single prompt contains multiple items (e.g. a Requirement + a Future-Work suggestion + a Question), each item benefits from its own routing recommendation. parse-prompt Step 5.5 calls `routing.route_text()` per item.

But raw item text alone is often too sparse — `"react to that"` yields 0 candidates without context. The fix: prepend an **interpretation** of the item (workspace tag + subject tags + action verbs + referenced entities) before routing:

```python
import routing
result = routing.route_text(item_text, context_prefix="frontend timeline review verify pr-42")
```

Without `context_prefix`, vague items like "react to that" return 0 candidates. With it, the right capabilities surface. The trade-off: the agent has to author the interpretation per-item — but that's cheap because the agent already has the conversation context.

## 7. Open architectural choices for adopters

**Where you keep the routing DB.** Default is `~/.parseprompt/routing.db` (overridable via `PARSEPROMPT_DB`). Reasonable alternatives: in your repo at `.local/routing.db` (per-project), or in a shared dotfiles dir. Trade-off: per-project DB makes feedback noise local to a project; shared DB lets you learn across projects.

**Whether to wire up the feedback loop.** `route-feedback.py` needs read access to a session-message store to know which skill/agent was actually invoked. If you can point `SESSION_DB_PATH` at one (see INTEGRATIONS.md for known schemas), the routing.db learns. If not, the feedback loop silently no-ops and the rest still works fine — you just don't get adaptive keyword weights.

**How aggressive the tripwire should be.** The default tripwire blocks Write/Edit until parse-prompt runs. Some users prefer advisory-only (just emit a systemMessage, don't block). To soften: change `parse-prompt-tripwire-check.sh` to `exit 0` instead of `exit 2` at the BLOCK section. Trade-off: less friction vs less enforcement.

## 8. Maintainers

- The routing layer is intentionally small and forkable. ~700 lines of Python + Bash + Markdown skill. Read it, fork it, adapt.
- Non-trivial changes (new dimension, new routing target, classifier rewrite) deserve a Workflow-Architect-style review (advisory hook in `routing-edit-reminder.sh` reminds you).
- Keep this doc up to date when routing logic changes — it's the only place where the layers and their interactions are described together.
