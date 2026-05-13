#!/usr/bin/env bash
# Stop hook: auto-finalize the session log at session end.
#
# What it does:
# - Creates session-logs/<YYYY-MM-DD>-<branch-topic>/ in the workspace if missing
# - Copies .context/prompt-analysis*.md, notes.md, todos.md into that dir
# - Stubs a minimal session-log.md if none exists (so the /session-log skill has
#   a target to append synthesis sections to)
# - Idempotent: multiple Stops per session are safe
#
# What it does NOT do:
# - Mirror to any global location (an earlier private fork did; that's a personal
#   convention and not part of this tool)
# - Auto-commit / auto-push (also private convention)
#
# Adopters who want a global mirror or auto-commit can fork this and add their
# own logic at the bottom — the core archive step is intentionally minimal.
set -u

# Skip if neither .git nor .context exists: not a real workspace.
[ ! -d .git ] && [ ! -d .context ] && exit 0

DATE=$(date +%Y-%m-%d)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "no-branch")
# Strip optional org/user prefix (everything before the last `/`) and trailing -vN
# from the branch name to get a stable topic.
TOPIC=$(echo "$BRANCH" | sed 's|.*/||' | sed 's|-v[0-9]*$||')
[ -z "$TOPIC" ] && TOPIC="no-topic"

DIR="session-logs/${DATE}-${TOPIC}"

# Multi-session-same-day-same-topic disambiguation: append -1/-2/... when the
# existing dir was created from a different HEAD commit.
CURRENT_SHA=$(git rev-parse HEAD 2>/dev/null | head -c8)
if [ -d "$DIR" ] && [ -f "$DIR/session-log.md" ] && [ -n "${CURRENT_SHA}" ]; then
  if ! grep -q "${CURRENT_SHA}" "$DIR/session-log.md" 2>/dev/null; then
    for n in 1 2 3 4 5; do
      if [ ! -d "${DIR}-${n}" ]; then
        DIR="${DIR}-${n}"
        break
      fi
    done
  fi
fi

mkdir -p "$DIR" 2>/dev/null || exit 0

# Copy prompt-analysis*.md (the per-turn structured-analysis files — the "gold"
# of a session that conductor.db / session storage cannot regenerate).
for f in .context/prompt-analysis*.md; do
  [ -f "$f" ] && cp -p "$f" "$DIR/$(basename "$f")" 2>/dev/null || true
done

# Copy notes.md (skill-invocation log) + todos.md (session-bridging todo store).
[ -f .context/notes.md ] && cp -p .context/notes.md "$DIR/notes.md" 2>/dev/null || true
[ -f .context/todos.md ] && cp -p .context/todos.md "$DIR/todos.md" 2>/dev/null || true

# Stub session-log.md only if there isn't one yet.
if [ ! -f "$DIR/session-log.md" ]; then
  WORKSPACE=$(basename "$(pwd)")
  cat > "$DIR/session-log.md" <<STUB
## Session - ${DATE}
- **Workspace:** ${WORKSPACE}
- **Branch:** ${BRANCH}
- **Commit at start:** ${CURRENT_SHA}

### Auto-stub

(Session log auto-created by session-log-finalize.sh. Use the \`/session-log\`
skill to append synthesis sections (architecture decisions, failed attempts,
surprising discoveries) — anything that the raw session storage cannot
regenerate on its own.)
STUB
fi

exit 0
