#!/usr/bin/env python3
"""
Feedback-loop hook. Runs on Stop (end of turn).

For each prompt_classification logged during this session:
  - Query a session-message store for what was actually invoked
  - Compare to recommended_capability_id
  - Update outcome + adjust capability keyword weights

Weight adjustments:
  match     -> weights x 1.05 (capped at WEIGHT_CAP)
  skipped   -> weights x 0.98
  corrected -> used x 1.10, recommended x 0.90 (capped/floored)

Runs silently. No stdout. Errors are appended to <install_root>/route-feedback.log.

## Session DB integration (CHOOSE ONE)

The hook needs read access to a SQLite session-message store to know which
skills/agents were actually invoked. Set `SESSION_DB_PATH` to the absolute path
of that DB. If unset, the feedback loop is skipped (the hook still runs but
does no learning).

Default schema assumption: a table `session_messages(session_id TEXT, role TEXT,
content TEXT, sent_at DATETIME)` where assistant `content` contains JSON-encoded
tool calls with keys like `"subagent_type"` and `"skill"`. See docs/INTEGRATIONS.md
for known session-store schemas this matches out-of-the-box. Adopters with a
different schema can fork this file or override the query.

Env vars:
  SESSION_DB_PATH         absolute path to session-message SQLite DB
  PARSEPROMPT_ROOT        install root (default: ~/.parseprompt)
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# Resolve install root + DB locations.
INSTALL_ROOT = Path(os.environ.get("PARSEPROMPT_ROOT", Path.home() / ".parseprompt"))
ROUTING_DB = Path(os.environ.get("PARSEPROMPT_DB", INSTALL_ROOT / "data" / "routing.db"))
LOG = INSTALL_ROOT / "route-feedback.log"

# Optional: session-message store. If unset/missing, feedback is skipped.
SESSION_DB_PATH = os.environ.get("SESSION_DB_PATH", "")

WEIGHT_CAP = 5.0
WEIGHT_FLOOR = 0.1


def log(msg):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


def find_invoked_capabilities(session_id):
    """Return set of capability names invoked via Skill or Agent tool in this session.

    Returns an empty set if SESSION_DB_PATH is unset, the file doesn't exist, or
    the schema doesn't match. Feedback loop is silently skipped — the hook still
    logs prompt_classifications, just doesn't update weights.
    """
    if not SESSION_DB_PATH or not session_id:
        return set()
    db = Path(SESSION_DB_PATH)
    if not db.exists():
        return set()
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = conn.cursor()
        # Default query: Conductor-style session_messages schema.
        # Override by forking this hook if your store has a different shape.
        cur.execute("""
            SELECT content FROM session_messages
            WHERE session_id = ? AND role = 'assistant'
              AND sent_at > datetime('now', '-1 day')
        """, (session_id,))
        invoked = set()
        for (content,) in cur.fetchall():
            if not content:
                continue
            # Extract Agent tool invocations
            for m in re.findall(r'"subagent_type"\s*:\s*"([^"]+)"', content):
                invoked.add(m)
            # Extract Skill tool invocations
            for m in re.findall(r'"skill"\s*:\s*"([^"]+)"', content):
                invoked.add(m)
        conn.close()
        return invoked
    except Exception as e:
        log(f"session-store query failed: {e}")
        return set()


def adjust_weights(cap_id, factor, conn):
    cur = conn.cursor()
    cur.execute("""
        UPDATE capability_keywords
        SET weight = MAX(?, MIN(?, weight * ?)),
            updated_at = CURRENT_TIMESTAMP
        WHERE capability_id = ?
    """, (WEIGHT_FLOOR, WEIGHT_CAP, factor, cap_id))


def process(session_id):
    conn = sqlite3.connect(ROUTING_DB)
    cur = conn.cursor()

    # Pending classifications (outcome='unknown') for this session
    cur.execute("""
        SELECT id, prompt, recommended_capability_id, matched_capabilities_json
        FROM prompt_classifications
        WHERE session_id = ? AND outcome = 'unknown'
    """, (session_id,))
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return

    invoked_names = find_invoked_capabilities(session_id)

    # Resolve invoked names to capability IDs
    invoked_ids = set()
    if invoked_names:
        placeholders = ",".join("?" for _ in invoked_names)
        cur.execute(f"""
            SELECT id FROM capabilities WHERE name IN ({placeholders})
        """, list(invoked_names))
        invoked_ids = {r[0] for r in cur.fetchall()}

    adjustments = 0
    for row_id, prompt, recommended, matched_json in rows:
        try:
            matched = json.loads(matched_json) if matched_json else {}
        except Exception:
            matched = {}

        used_cap_id = None
        outcome = "skipped"

        if invoked_ids and recommended and recommended in invoked_ids:
            outcome = "success"
            used_cap_id = recommended
            adjust_weights(recommended, 1.05, conn)
        elif invoked_ids:
            # Something invoked, but not the one we recommended
            outcome = "corrected"
            if recommended:
                adjust_weights(recommended, 0.90, conn)
            for iid in invoked_ids:
                adjust_weights(iid, 1.10, conn)
            used_cap_id = next(iter(invoked_ids))
        elif recommended:
            outcome = "skipped"
            adjust_weights(recommended, 0.98, conn)

        cur.execute("""
            UPDATE prompt_classifications
            SET outcome = ?, used_capability_id = ?
            WHERE id = ?
        """, (outcome, used_cap_id, row_id))
        adjustments += 1

    conn.commit()
    conn.close()
    log(f"session={session_id} processed={adjustments} invoked={len(invoked_ids)}")


def find_pending_sessions():
    """All session_ids with at least one outcome='unknown' classification.

    Used as catch-up: every Stop hook gets a chance to clear stale unknowns
    from previous sessions that ended without producing a CLAUDE_SESSION_ID.
    """
    try:
        conn = sqlite3.connect(f"file:{ROUTING_DB}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT session_id FROM prompt_classifications
            WHERE outcome = 'unknown' AND session_id != ''
            ORDER BY id DESC
        """)
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        log(f"find_pending_sessions failed: {e}")
        return []


def main():
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if not session_id:
        try:
            data = sys.stdin.read().strip()
            if data.startswith("{"):
                meta = json.loads(data)
                session_id = meta.get("session_id", "")
        except Exception:
            pass

    if session_id:
        try:
            process(session_id)
        except Exception as e:
            log(f"process failed (session={session_id}): {e}")

    # ALWAYS run catch-up for older pending sessions, not only when current
    # session_id is absent. Cap at 10 sessions to keep stop-hook latency low.
    pending = find_pending_sessions()
    if session_id:
        pending = [s for s in pending if s != session_id]
    if pending:
        log(f"catch-up: {len(pending)} pending sessions, processing top 10")
    for sid in pending[:10]:
        try:
            process(sid)
        except Exception as e:
            log(f"catch-up failed (session={sid}): {e}")


if __name__ == "__main__":
    main()
