#!/usr/bin/env bash
# UserPromptSubmit hook (run first in chain): write tripwire + emit advisory systemMessage.
#
# Purpose: force the agent to call /parse-prompt before any Write/Edit operation.
# The companion hook parse-prompt-tripwire-check.sh blocks mutating tools until a
# fresh .context/prompt-analysis-<N>.md is written (= parse-prompt skill complied).
#
# Tripwire lives in the current workspace's .context/ directory (gitignored).
#
# Workspace guard: only fire when the cwd looks like a real workspace (has .git
# or .context). Without this, running the harness from $HOME would create a
# .context/ directory in $HOME — surprising and undesirable.
set -u
[ ! -d .git ] && [ ! -d .context ] && exit 0

mkdir -p .context 2>/dev/null || true
touch .context/.parse-prompt-tripwire 2>/dev/null || true

cat <<'JSON'
{"systemMessage":"[parse-prompt TRIPWIRE active] First pass: run /parse-prompt on the current user prompt. Write/Edit are BLOCKED until a fresh .context/prompt-analysis-<N>.md is written. The tripwire is automatically cleared when that file is written."}
JSON
