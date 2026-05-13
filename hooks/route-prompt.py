#!/usr/bin/env python3
"""
Route-prompt hook. Runs on UserPromptSubmit.

Reads prompt from stdin, classifies intent + extracts keywords, queries
routing.db for top candidate skills/agents via the shared routing library
at ../lib/routing.py.

This hook owns the side effects:
- writes a prompt_classifications row (DB log for the feedback loop)
- writes .context/todos.md when intent=backlog (action layer)
- emits a systemMessage with ranked candidates

Pure compute (tokenize / detect_intent / score_capabilities) lives in the
shared library, so parse-prompt's per-item Step 5.5 can call the same logic.

Does NOT auto-invoke anything. Advisory only. Silent if no candidates.

Adopters: set PARSEPROMPT_ROOT env var to your install root if it isn't
~/.parseprompt/ (lib path resolution + default DB location both follow it).
"""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Resolve the shared lib. Default install root is ~/.parseprompt/, override
# with PARSEPROMPT_ROOT env var if you installed elsewhere.
INSTALL_ROOT = Path(os.environ.get("PARSEPROMPT_ROOT", Path.home() / ".parseprompt"))
sys.path.insert(0, str(INSTALL_ROOT / "lib"))
import routing  # noqa: E402

DB = routing.DEFAULT_DB


def log_classification(session_id, prompt, intent, keywords, complexity, candidates):
    """Persist row in prompt_classifications for feedback-loop analysis."""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    matched = {str(c["id"]): c["score"] for c in candidates}
    recommended = candidates[0]["id"] if candidates else None
    cur.execute("""
        INSERT INTO prompt_classifications
        (session_id, prompt_hash, prompt, intent, keywords_json, complexity,
         matched_capabilities_json, recommended_capability_id, outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unknown')
    """, (session_id, prompt_hash, prompt, intent,
          json.dumps(list(keywords)), complexity,
          json.dumps(matched), recommended))
    conn.commit()
    conn.close()


def write_backlog_todo(prompt):
    """Auto-append to .context/todos.md when intent=backlog. Idempotent.

    Rationale: deferral signals ("we could do X later", "remember to Y") deserve
    workspace-local persistence so they survive past the current turn but don't
    clutter the tracked git history yet. parse-prompt Step 4.6 (the skill side)
    promotes promising entries to docs/BACKLOG.md ## Future/Someday/Ideas.

    Workspace guard: only fires when cwd looks like a real workspace (has .git
    or .context already). Without this, running the harness from $HOME would
    create a .context/ directory in $HOME.
    """
    try:
        cwd = Path(os.getcwd())
        if not (cwd / ".git").exists() and not (cwd / ".context").exists():
            return
        cwd_todos = cwd / ".context" / "todos.md"
        cwd_todos.parent.mkdir(parents=True, exist_ok=True)
        existing = cwd_todos.read_text() if cwd_todos.exists() else ""
        head = prompt.strip().replace("\n", " ")[:60]
        if head and head not in existing:
            iso = datetime.now().strftime("%Y-%m-%d %H:%M")
            excerpt = prompt.strip().replace("\n", " ")[:240]
            cwd_todos.touch(exist_ok=True)
            with cwd_todos.open("a") as f:
                f.write(f"\n## {iso} - backlog/deferral detected\n")
                f.write(f"> {excerpt}\n\n")
                f.write(f"**Status:** Open. **Source:** route-prompt.py auto-detect (intent=backlog).\n")
                f.write(f"**Next:** parse-prompt 4.6 should promote to docs/BACKLOG.md ## Future/Someday/Ideas.\n\n---\n")
    except Exception:
        pass  # never fail the hook on todos write


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        return

    prompt = raw.strip()
    stdin_session_id = ""
    if prompt.startswith("{"):
        try:
            data = json.loads(prompt)
            prompt = data.get("prompt") or data.get("message") or prompt
            stdin_session_id = data.get("session_id") or data.get("sessionId") or ""
        except Exception:
            pass

    if not prompt or len(prompt) < 5:
        return

    # Use the shared library — same logic used by parse-prompt Step 5.5
    result = routing.route_text(prompt, cwd=os.getcwd())
    intent = result["intent"]
    complexity = result["complexity"]
    keywords = result["keywords"]
    candidates = result["candidates"]

    # Side effect 1: log to DB for feedback loop
    session_id = stdin_session_id or os.environ.get("CLAUDE_SESSION_ID", "")
    try:
        log_classification(session_id, prompt, intent, keywords, complexity, candidates)
    except Exception:
        pass  # never break the hook on log failure

    # Side effect 2: backlog -> .context/todos.md (action layer)
    if intent == "backlog":
        write_backlog_todo(prompt)

    # Side effect 3: emit systemMessage with ranked candidates
    if not candidates:
        return  # silent fallthrough
    lines = [f"[router] intent={intent} complexity={complexity} workspace={result['workspace_domain']}"]
    lines.append("Top capability candidates for this prompt:")
    for i, c in enumerate(candidates, 1):
        marker = "SKILL" if c["kind"] == "skill" else "AGENT"
        lines.append(f"  {i}. [{marker}] {c['name']} (score {c['score']}, domain {c['domain']}): {c['description']}")
    lines.append("These are advisory - pick only if they fit. If none fits, ignore this hint.")
    print(json.dumps({"systemMessage": "\n".join(lines)}))


if __name__ == "__main__":
    main()
