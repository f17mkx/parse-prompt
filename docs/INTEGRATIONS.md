# Integrations

How to wire parseprompt into a larger workflow. Three integration points are documented here:

1. **/ship-style pre-commit leak audit** — pattern, not bundled skill
2. **SESSION_DB_PATH wiring** — hooking the feedback loop into your session storage
3. **Project-specific classifier delegate** — handing 4.1 items to a project-specific skill

---

## 1. /ship-style pre-commit leak audit (pattern)

parseprompt does NOT ship a `/ship` skill — that's git-workflow territory and belongs in a separate suite. But the pattern of a pre-commit "leak audit" that cross-checks `.context/` artifacts against the tracked diff IS a valuable integration. Here's the recipe.

The problem: an idea like "we could do X later" gets caught at L1 (parse-prompt 4.6) AND L2 (.context/todos.md). But if no one promotes it to `docs/BACKLOG.md` before the commit lands, it can still evaporate after merge.

The solution: a pre-commit step that scans `.context/prompt-analysis*.md` (Future Work / Tentative sections) AND `.context/todos.md` (unchecked items, or auto-appended backlog/deferral headers), cross-checks against `git diff origin/main -- docs/BACKLOG.md docs/adr/` (or whatever tracked files you'd expect to change), and warns if the `.context/` items have no corresponding tracked-diff entry.

### Drop-in bash snippet

Add this as Step 3.5 of your ship/commit pipeline:

```bash
# Leak audit: catch ideas that parse-prompt 4.6 OR routing.db backlog-detection
# captured in .context/ but nobody promoted to a tracked file.
LEAKS=()

# (a) Future Work / Decisions / Rejections sections in prompt-analysis files
if compgen -G ".context/prompt-analysis*.md" >/dev/null; then
  while IFS= read -r line; do
    LEAKS+=("$line")
  done < <(grep -A4 "^## Future Work\|^### 4.6\|## Decisions / Rejections" .context/prompt-analysis*.md 2>/dev/null \
    | grep -E "^.*\.md.*[A-Za-z]" | head -10)
fi

# (b) Unchecked todos in .context/todos.md (lines starting with "- [ ]" OR
# "## YYYY...backlog/deferral")
if [ -f .context/todos.md ]; then
  while IFS= read -r line; do
    LEAKS+=("$line")
  done < <(grep -nE "^- \[ \]|^## .*backlog/deferral" .context/todos.md 2>/dev/null)
fi

# (c) Cross-check: are these items already mentioned in tracked diffs?
TRACKED_DIFF=$(git diff origin/main -- docs/BACKLOG.md docs/adr/ 2>/dev/null)

if [ ${#LEAKS[@]} -gt 0 ]; then
  echo ""
  echo "⚠️  Possibly unrouted ideas detected (.context/prompt-analysis*.md or .context/todos.md):"
  for leak in "${LEAKS[@]}"; do
    echo "   - ${leak:0:140}"
  done
  echo ""
  echo "Cross-check: have these been promoted to docs/BACKLOG.md or docs/adr/ in this branch?"
  if [ -z "$TRACKED_DIFF" ]; then
    echo "   ❌ No BACKLOG.md / ADR changes in this branch's diff against origin/main."
    echo "   These ideas may evaporate after merge."
    echo ""
    echo "Continue anyway? (y/n)"
    read -r ANSWER
    [ "$ANSWER" != "y" ] && echo "Ship aborted - go promote the items first." && exit 1
  else
    echo "   ✓ BACKLOG.md / ADR has changes - assume the items were promoted. Continuing."
  fi
fi
```

Notes:
- Advisory gate, not hard block. The user can always answer `y` to proceed.
- Designed for the "deferred-idea-leak" pattern: deferral text in `.context/`, no corresponding BACKLOG.md commit.
- If `.context/todos.md` accumulates many old entries (workspace re-use), prefer to clean it before shipping rather than spam-acknowledging them every time.

---

## 2. SESSION_DB_PATH wiring

`route-feedback.py` (Stop hook) needs read access to a session-message store to know which skills/agents were actually invoked during the session. Without it, the feedback loop silently no-ops — `prompt_classifications` rows still get logged but `outcome` stays at `'unknown'` and keyword weights don't adapt.

The hook reads `SESSION_DB_PATH` from the environment. Set it to the absolute path of a SQLite DB whose schema matches:

```sql
session_messages (
  session_id TEXT,
  role TEXT,        -- 'user' or 'assistant'
  content TEXT,     -- assistant content contains JSON-encoded tool calls
  sent_at DATETIME
)
```

Assistant `content` should contain JSON-encoded tool calls with the following keys (the hook regex-extracts these):

- `"subagent_type": "<agent-name>"` — for Agent tool invocations
- `"skill": "<skill-name>"` — for Skill tool invocations

### Known session stores that match this schema

**Conductor.app** (a Claude Code companion that runs many parallel agent workspaces): stores its session DB at `~/Library/Application Support/com.conductor.app/conductor.db`. The `session_messages` schema matches the default — point `SESSION_DB_PATH` at it and the feedback loop works.

```bash
export SESSION_DB_PATH="$HOME/Library/Application Support/com.conductor.app/conductor.db"
```

**Other harnesses**: if your harness stores sessions in a different shape, you have two options:

1. **Fork `route-feedback.py`** and override the SQL query in `find_invoked_capabilities()` to match your schema
2. **Build an adapter** that mirrors your harness's storage into a SQLite DB matching the expected schema (cheap if your harness exposes a JSONL log)

If your harness stores sessions as JSONL files in a directory (Claude Code's default), you can write a small wrapper that exposes them as a SQLite view, OR you can fork the hook to read directly from the JSONL files. Either is a small adapter — the rest of parseprompt doesn't need to change.

---

## 3. Project-specific classifier delegate

parse-prompt routes 4.1 / 4.6 / 4.7 items to `docs/BACKLOG.md` by default. For a single project this is fine. For a complex project with multiple categorizations (UX vs BUG vs FEATURE vs INFRA, per-area concept files, ADR drafting, etc.), you may want to **delegate** to a project-specific classifier skill.

The delegate pattern:

1. Add a `.parseprompt-project` marker file to your project root, OR teach parse-prompt's Step 3 detection rule to recognize your project.
2. Create a `/parse-<projectname>` skill that:
   - Accepts inline text (the 4.1 items)
   - Classifies each item into your project's categories
   - Writes per-category to your project's domain files (per-area CONCEPT.md files, BACKLOG.md, ADR drafts, etc.)
   - Logs results to `.context/notes.md`
   - Returns a table of files written
3. Add a Step 3 rule in `parse-prompt.md` so when your project is detected, it delegates 4.1 items to `/parse-<projectname>` instead of routing them generically.

See `docs/examples/parse-projectx-case-study.md` for a worked example: a fictional SaaS product with multi-category classification (UX/BUG/FEATURE/BACKEND/STRATEGY/LEGAL/DEVOPS/DECISION/FUTURE/TENTATIVE), per-area concept files, ADR drafting for architectural decisions, and ID assignment from a central REGISTRY.

---

## 4. Customizing intent classification

The `INTENTS` list in `lib/routing.py` controls intent detection. Default patterns are bilingual (English + German) and cover common cases. To add your own:

```python
# In a fork of lib/routing.py, or via a monkey-patch:
import routing
routing.INTENTS.insert(0, ("review-board", r"\b(review board|RB|architecture review)\b"))
```

Or fork `lib/routing.py` directly — it's ~200 lines, easy to maintain.

The `/trigger` skill is the recommended way to add intent patterns + decision-tree mappings together.

---

## 5. Customizing the tripwire enforcement

By default, `parse-prompt-tripwire-check.sh` BLOCKS Write/Edit when the tripwire is active (exit 2). To change to advisory-only:

```bash
# In parse-prompt-tripwire-check.sh, change the BLOCK section's `exit 2` to:
exit 0
```

Trade-off: less friction, less enforcement. parse-prompt becomes a recommendation rather than a requirement. For first-time adopters this can be a softer entry point.

---

## 6. Skipping the tripwire entirely

Some prompt patterns shouldn't trigger the tripwire (e.g. very short status questions: "ok", "thanks"). The tripwire fires unconditionally on every UserPromptSubmit, but the parse-prompt skill itself handles silent-skip on null prompts.

If you want the hook to skip writing the tripwire for trivial prompts: edit `parse-prompt-tripwire-write.sh` and add a length check before `touch`:

```bash
# Skip tripwire for very short prompts (the skill handles silent-skip anyway).
prompt=$(cat || echo "")
[ ${#prompt} -lt 10 ] && exit 0
```

This is opt-in. Default behavior keeps the tripwire firing on every prompt — safer.

---

## 7. Sharing routing weights across projects

By default `routing.db` lives at `~/.parseprompt/routing.db` (overridable via `PARSEPROMPT_DB`). One DB, learning across all projects. Pros: cross-project learning ("user often invokes X for plan-tasks regardless of repo"). Cons: noise from one project's vocabulary bleeds into another's recommendations.

To go per-project: set `PARSEPROMPT_DB` to a project-local path:

```bash
# In your project's CLAUDE.md or shell profile when entering the workspace:
export PARSEPROMPT_DB="$PWD/.local/routing.db"
```

Trade-off: each project starts with no learning history, takes longer to converge.
