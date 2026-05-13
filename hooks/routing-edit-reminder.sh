#!/bin/bash
# PreToolUse hook (matcher Edit|Write) — emits a one-time advisory reminder when
# the agent is about to edit a file that's part of the routing infrastructure.
#
# Advisory only. Does NOT block. The rule of thumb: any change to the routing
# layer (parse-prompt skill, route-prompt hook, routing.db schema, ARCHITECTURE
# doc) deserves a careful read of ARCHITECTURE.md and ideally a Workflow-Architect
# consultation for non-trivial changes.
#
# Reads JSON tool-input from stdin, extracts the target path, checks if it
# matches one of the protected patterns. If yes, prints a systemMessage to
# stdout reminding the agent to consult ARCHITECTURE.md first.
#
# Adopters: edit the PROTECTED array below to match where YOU installed these
# files. By default we expect ~/.parseprompt/ — adapt as needed.

set -e

INPUT=$(cat)

# Try to extract the target file path from tool input.
TARGET=$(echo "$INPUT" | python3 -c '
import json, sys
try:
    data = json.loads(sys.stdin.read())
    inp = data.get("tool_input") or data.get("toolInput") or {}
    print(inp.get("file_path") or inp.get("filePath") or inp.get("path") or "")
except Exception:
    print("")
' 2>/dev/null || echo "")

# No target = nothing to check.
[ -z "$TARGET" ] && exit 0

# Routing-infrastructure paths that warrant consultation. Adapt to your install
# location. Default assumes ~/.parseprompt/ as the install root.
INSTALL_ROOT="${PARSEPROMPT_ROOT:-$HOME/.parseprompt}"
PROTECTED=(
  "$INSTALL_ROOT/skills/parse-prompt.md"
  "$INSTALL_ROOT/skills/trigger.md"
  "$INSTALL_ROOT/hooks/route-prompt.py"
  "$INSTALL_ROOT/hooks/route-feedback.py"
  "$INSTALL_ROOT/lib/routing.py"
  "$INSTALL_ROOT/data/routing.db"
  "$INSTALL_ROOT/docs/ARCHITECTURE.md"
)

MATCH=""
for p in "${PROTECTED[@]}"; do
  if [ "$TARGET" = "$p" ]; then
    MATCH="$p"
    break
  fi
done

# Also catch: any path under <install_root>/hooks/route-*.py
case "$TARGET" in
  "$INSTALL_ROOT/hooks/route-"*.py) MATCH="$TARGET" ;;
esac

[ -z "$MATCH" ] && exit 0

# Emit advisory (NOT blocking — exit 0 lets the edit proceed).
cat <<MSGEOF
{"systemMessage":"⚠️ [routing-edit-reminder] About to edit a routing-infrastructure file: $MATCH\n\nThis change touches the routing layer. Before editing, you SHOULD:\n  1. Read docs/ARCHITECTURE.md (the master index of routing layers + persistence)\n  2. For non-trivial changes (new dimension, new routing target, classifier rewrite), consult a Workflow-Architect agent\n  3. Verify the change in your project's CHANGELOG and add an entry\n\nQuick edits (typo fix, comment clarification, single-pattern addition) can proceed without agent consult. Architectural changes deserve more care.\n\nProceeding..."}
MSGEOF

exit 0
