# How to customize parseprompt

Most adopters won't need to touch core files. The configuration surface for common customizations:

| What you want to change | How |
|---|---|
| Where the routing DB lives | `PARSEPROMPT_DB` env var |
| Where the install root is | `PARSEPROMPT_ROOT` env var |
| Which workspace dirs map to which routing domain (1.5x boost) | `PARSEPROMPT_DOMAIN_MAP` env var (JSON) |
| Where session-message store lives (for feedback loop) | `SESSION_DB_PATH` env var |
| Add a new intent pattern | `/trigger` skill OR fork `lib/routing.py` |
| Add a new decision-tree mapping | `/trigger` skill (edits `docs/INPUT-GRAMMAR-EXAMPLE.md` or your fork) |
| Make the tripwire advisory instead of blocking | one-line edit in `parse-prompt-tripwire-check.sh` |
| Add a project-specific classifier delegate | see `docs/INTEGRATIONS.md` §3 |
| Change session-log directory naming | edit `session-log-finalize.sh` topic-extraction |

---

## Setup

```bash
# Install location (default ~/.parseprompt — pick anywhere).
export PARSEPROMPT_ROOT="$HOME/.parseprompt"

# Routing DB location (default $PARSEPROMPT_ROOT/data/routing.db).
export PARSEPROMPT_DB="$PARSEPROMPT_ROOT/data/routing.db"

# Optional: workspace-domain mapping (JSON: {"substring": "domain"}).
# When the cwd path contains <substring>, capabilities tagged domain=<domain>
# get a 1.5x boost in routing scores.
export PARSEPROMPT_DOMAIN_MAP='{"my-saas": "frontend", "my-api": "backend", "client-work": "consulting"}'

# Optional: session storage for feedback loop. See INTEGRATIONS.md §2.
export SESSION_DB_PATH="$HOME/Library/Application Support/com.conductor.app/conductor.db"
```

Bootstrap the routing DB:

```bash
mkdir -p "$PARSEPROMPT_ROOT/data"
sqlite3 "$PARSEPROMPT_DB" < data/schema.sql
sqlite3 "$PARSEPROMPT_DB" < data/seed-example.sql
```

Wire the hooks into your harness's settings (see `examples/settings.json`).

---

## Adding your own intent

The `INTENTS` list in `lib/routing.py` is a list of `(label, regex)` tuples. First match wins. To add a new intent without forking:

```python
# Monkey-patch from your own startup file:
import sys
sys.path.insert(0, "/path/to/parseprompt/lib")
import routing
routing.INTENTS.insert(0, ("review-board", r"\b(review\s+board|RB|architecture\s+review)\b"))
```

Or fork `lib/routing.py` directly — it's ~200 lines and the INTENTS list is the only thing you'd typically change.

The recommended path is `/trigger`: it adds the regex to `route-prompt.py` AND the decision-tree mapping in your grammar guide AND a CHANGELOG entry. Doing all three by hand is error-prone.

---

## Adding your own dimension

The 8 default dimensions (4.1-4.8) cover most cases. If you need a project-specific one (say, "Compliance items"), you can:

1. **Fork `skills/parse-prompt.md`** — add a 4.9 section with your trigger patterns, format, and routing.
2. **Add a project-specific classifier delegate** (recommended for project-specific dimensions; see INTEGRATIONS.md §3) — keeps the core skill clean.

The cost of forking the skill: every parseprompt update needs a manual merge. The cost of a delegate: indirection (parse-prompt → your delegate), but updates flow cleanly.

---

## Customizing workspace-type detection

`parse-prompt.md` Step 3 has the workspace-type detection rule. The default rule recognizes:

- `.parseprompt-project` marker file → project-specific routing
- Otherwise → generic

To add your own detection:

```markdown
## Step 3: detect workspace type (modified)

- A `.parseprompt-project` marker file exists → use project-specific routing
- The cwd path contains `my-saas/` → use the my-saas project routing
- The cwd path contains `client-work/` → use generic with `consulting` domain tag
- Otherwise → generic
```

Then make sure your project-specific classifier (`/parse-<projectname>`) exists.

---

## Customizing the tripwire

The tripwire is the enforcement mechanism that blocks Write/Edit until parse-prompt has run. Three knobs:

**Make it advisory (no blocking)**: edit `parse-prompt-tripwire-check.sh`, change the BLOCK section's `exit 2` to `exit 0`. The hook still emits the warning to stderr; the agent just isn't blocked.

**Skip on trivial prompts**: edit `parse-prompt-tripwire-write.sh`, add a length check at the top:

```bash
prompt=$(cat || echo "")
[ ${#prompt} -lt 10 ] && exit 0
```

**Whitelist additional read-only tools**: edit `parse-prompt-tripwire-check.sh`, add to the case-statement that whitelists tool names. The default whitelist covers the common Claude-Code tools (Read/Grep/Glob/Skill/ToolSearch/...). Add your custom MCP servers' read-only tool patterns:

```bash
# Add patterns matching read-only MCP tools you use:
case "$tool" in
  mcp__yourserver__get_*) exit 0 ;;
  mcp__yourserver__list_*) exit 0 ;;
esac
```

---

## Per-project routing DB

Default `routing.db` is shared across all projects (one DB, learns globally). For per-project DBs:

```bash
# In your project's CLAUDE.md or shell profile when entering the workspace:
export PARSEPROMPT_DB="$PWD/.local/routing.db"

# First time:
mkdir -p "$PWD/.local"
sqlite3 "$PARSEPROMPT_DB" < /path/to/parseprompt/data/schema.sql
sqlite3 "$PARSEPROMPT_DB" < /path/to/parseprompt/data/seed-example.sql
```

Trade-off: per-project DBs start with no learning history, take longer to converge on good keyword weights. Use shared if you want cross-project learning, per-project if you want isolation.

---

## Customizing the session-log archive

`session-log-finalize.sh` archives prompt-analysis files at session end. Default archive location: `<workspace>/session-logs/<YYYY-MM-DD>-<branch-topic>/`.

To add a global mirror (e.g. archive all session logs to `~/.parseprompt/session-logs/` for cross-workspace search):

```bash
# At the bottom of session-log-finalize.sh, after the existing exit 0:
GLOBAL_DIR="$HOME/.parseprompt/session-logs/${DATE}-${TOPIC}"
mkdir -p "$GLOBAL_DIR" 2>/dev/null && cp -p -r "$DIR/." "$GLOBAL_DIR/" 2>/dev/null || true
```

To auto-commit the workspace's session-logs to git: `git add session-logs/...` + `git commit -m "session-log archive"` from a background process. Be careful — auto-commits can interact badly with rebase/cherry-pick workflows. Most users don't enable this.

---

## Adding a custom dimension via fork

If you do fork the skill, name the fork. The community fork-graph is more useful when forks are discoverable. Suggested naming: `parseprompt-<flavor>` (e.g. `parseprompt-compliance`, `parseprompt-academic`).

If your fork adds a dimension or a delegate that's reusable, consider a PR to upstream — `docs/examples/` is the right place for project-specific patterns.

---

## What you should NOT customize

- The 8-dimension contract (4.1-4.8) — adopters who customize this lose interop with the example case study and any future shared content.
- The tripwire's "write to `.context/prompt-analysis-N.md` clears the tripwire" rule — this is the skill-escape contract that the rest of parseprompt depends on.
- The `prompt_classifications` table schema — `route-feedback.py` reads it, downstream tools may too.
- The auto-numbering of `prompt-analysis-N.md` — clutter or other naming patterns will confuse the session-log archive step.
