#!/usr/bin/env bash
# PreToolUse hook: block mutating tools until parse-prompt wrote a fresh prompt-analysis-<N>.md.
#
# Whitelists read-only / investigation tools so the agent can still Read/Grep/Glob/Bash
# while preparing the analysis. Anything that mutates persistent state (Write/Edit,
# Notebook edits, etc.) is BLOCKED until the tripwire is cleared.
#
# Input: JSON on stdin describing the tool call.
# Exit 2 = block, exit 0 = allow.
set -u

input=$(cat)

tool=$(python3 -c "
import json, sys
try:
  d = json.loads(sys.argv[1])
  print(d.get('tool_name',''))
except Exception:
  print('')
" "$input" 2>/dev/null)

target=$(python3 -c "
import json, sys
try:
  d = json.loads(sys.argv[1])
  p = d.get('tool_input', {}) or {}
  print(p.get('file_path', '') or '')
except Exception:
  print('')
" "$input" 2>/dev/null)

# Whitelist: read-only / investigation tools always pass (parse-prompt itself needs these).
case "$tool" in
  Read|Grep|Glob|Skill|ToolSearch|WebFetch|WebSearch|NotebookRead) exit 0 ;;
  TaskGet|TaskList|TaskOutput) exit 0 ;;
  ListMcpResourcesTool|ReadMcpResourceTool|Monitor) exit 0 ;;
esac

# Whitelist: read-only MCP tool patterns. Extend this list with your own MCP
# servers' read-only tools — the convention is to allow tools whose names start
# with `get_`, `list_`, `read_`, `search_` etc. and block writes/mutations.
# Examples are intentionally minimal — adopters add their own.
case "$tool" in
  mcp__*__get_*|mcp__*__list_*|mcp__*__read_*|mcp__*__search_*|mcp__*__find_*) exit 0 ;;
esac

trip=".context/.parse-prompt-tripwire"
[ ! -f "$trip" ] && exit 0

# Skill-escape: writes to .context/prompt-analysis*.md fulfill the requirement.
case "$target" in
  *"/.context/prompt-analysis"*".md"|".context/prompt-analysis"*".md"|"prompt-analysis"*".md")
    rm -f "$trip" 2>/dev/null || true
    exit 0
    ;;
esac

# Compliance-check: if any prompt-analysis*.md is newer than the tripwire, compliance already happened.
# Use POSIX `find -newer` instead of platform-specific `stat` so this works on macOS + Linux.
if ls .context/prompt-analysis*.md >/dev/null 2>&1; then
  if find .context -maxdepth 1 -name 'prompt-analysis*.md' -newer "$trip" 2>/dev/null | head -1 | grep -q .; then
    rm -f "$trip" 2>/dev/null || true
    exit 0
  fi
fi

# BLOCK
cat >&2 <<EOF
🚨 TRIPWIRE BLOCK: parse-prompt has not run yet for this turn.
Tool: $tool → $target
Tripwire: $(pwd)/$trip
Fix: Call /parse-prompt on the current user prompt first.
The tripwire is removed automatically when .context/prompt-analysis-<N>.md is written.
EOF
exit 2
