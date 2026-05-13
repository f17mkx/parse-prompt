"""
Routing library — extracted from hooks/route-prompt.py for re-use.

Two entry points:
- `route_prompt(prompt, ...)` — for the UserPromptSubmit-Hook (existing behavior)
- `route_text(text, ...)` — for parse-prompt Step 5.5 per-item routing (NEW Paket B)

Why this split: heretofore route-prompt.py classified the WHOLE prompt and emitted
top-3 candidates per UserPromptSubmit. Stefan's correction (2026-04-29): a single
prompt often contains multiple items (Requirements, Future-Work suggestions,
Questions). Each item needs its own routing recommendation. parse-prompt extracts
those items in Step 4 — Step 5.5 then calls route_text() per item.

Score-tuning (also Paket B):
- MAX_CANDIDATES: 3 -> 5 (more recall)
- MIN_SCORE: 2.0 -> 1.5 (lower floor; data showed 94% of prompts hit only 2 candidates because of the floor, not the cap)

The hook still owns the Action Layer (writing .context/todos.md when
intent=backlog) and the DB-write side-effect (`prompt_classifications` row).
This module is pure compute + DB read.
"""

import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path.home() / ".claude" / "data" / "routing.db"

# Tuned defaults — overridable per-call. Old hook used 3/2.0 hardcoded.
DEFAULT_MAX_CANDIDATES = 5
DEFAULT_MIN_SCORE = 1.5

# 2026-04-28: backlog promoted to position 1 (was 10) so deferral signals
# beat broader audit/plan patterns when both match. See ROUTING-AND-PERSISTENCE.md §3
INTENTS = [
    ("backlog", r"\b(später|spaeter|irgendwann|nicht\s+jetzt|for\s+now|next\s+release|wir\s+könnten|wir\s+koennten|we\s+could|would\s+be\s+nice|wäre\s+eine\s+idee|waere\s+eine\s+idee|could\s+give\s+an\s+option|for\s+inspiration|to\s+draw\s+from|i\s+like\s+the\s+idea|maybe\s+we|vielleicht|hätten\s+wir\s+zeit|haetten\s+wir\s+zeit|wenn\s+wir\s+mal\s+zeit|backlog|remember|merk|add\s+to|in\s+den\s+backlog|speichere)\b"),
    ("ship",    r"\b(create\s+a\s+pr|commit\s+and\s+push|fullmerge|merge\s+onto\s+main|\bship+(en|e|t|est)?\b|deploy|finalize|lande|erledige|pr\s+raus|pull\s+request)\b"),
    ("confirm", r"^\s*(ja+|yes+|ok+|approved|go\s+ahead|continue|mach(s)?|genau|passt|perfect|go|jaaa+|los|shipp+|sign[\- ]?off)\s*[\.\!\?]*\s*$"),
    ("sync",    r"\b(pull|rebase|merge\s+the\s+remote|sync|update\s+from\s+main)\b"),
    ("spawn",   r"\b(ws[\- ]?export|new[\- ]?branch|neuen?\s+branch|create[\- ]a[\- ]workspace|neuer?\s+workspace)\b"),
    ("resume",  r"\b(resume|you\s+stopped|weitermachen|continue\s+where|wo\s+sind\s+wir|where.*left\s+off|hello,\s*you\s+stopped)\b"),
    ("audit",   r"\b(audit|review|analyse|analyze|prüfe|check\s+mal|check\s+the|look\s+(at|into))\b"),
    ("fix",     r"\b(fix|bug|error|broken|kaputt|funktioniert\s+nicht|doesn.t\s+work|geht\s+nicht|behebe|bitte\s+ändern|bitte\s+aendern|bitte\s+fix)\b"),
    ("batch",   r"\b(alle\s+auf\s+einmal|alles\s+fixen|batch|parallel|gleichzeitig|simultan|alles\s+(machen|fixen))\b"),
    ("plan",    r"\b(plan|überleg|denk\s+mal|strategy|approach|wie\s+gehen\s+wir|mach\s+(mal\s+)?(einen|nen)\s+plan)\b"),
    ("draft",   r"\b(verfasse|formuliere|schreib\s+mir|draft|reply\s+to|antworte|entwurf|message\s+for)\b"),
    ("docs",    r"\b(dokumentiere|docs|readme|changelog|beschreib|explain\s+in|document)\b"),
    ("investigate", r"\b(was\s+ist\s+los|warum|why\s+(did|is)|analysiere|debug|untersuche|was\s+passiert)\b"),
    ("meta",    r"\b(skill|agent|routing|parse.prompt|settings\.json|hook|workflow|~/\.claude)\b"),
    ("design",  r"\b(design|ui|ux|style|visual|aesthetic|layout|farbe|color|typography)\b"),
    ("homeassistant", r"\b(home\s+assistant|home-assistant|hassio|zigbee|lovelace|ha\s+mcp|yama.*ha|hacs)\b"),
]

STOPWORDS = set("""
a an the and or but if then else when while für mit von nach bei auf zu zum zur
der die das ein eine einen einem einer und oder aber wenn dann sonst
is are was were be been being have has had do does did will would should could
ich du er sie es wir ihr mein dein sein unser euer auch nur noch schon mal halt
this that these those which what who whom whose why how where there here not
dies das diese dieser jene jeden jenem welche was wer wessen warum wie wo
ist hier da mehr viele mehrere some few many much to of in on at by from into
""".split())


def tokenize(text):
    """Strip code fences/inline code/markdown punctuation, return lowercase content tokens."""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"[*_#>\[\]()]", " ", text)
    tokens = re.findall(r"[a-zA-Z0-9äöüÄÖÜß\-]{3,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS and not t.isdigit()]


def detect_intent(prompt):
    """First-match-wins against INTENTS list. Returns label or 'unknown'."""
    for label, pattern in INTENTS:
        if re.search(pattern, prompt, re.I):
            return label
    return "unknown"


def detect_complexity(prompt):
    """Heuristic 1-5 based on word count + question count + attachments + paths."""
    wc = len(prompt.split())
    q = prompt.count("?")
    attachments = len(re.findall(r"@⟦", prompt))
    if wc < 20 and q <= 1:
        return 1
    if wc < 100 and attachments == 0:
        return 2
    if wc < 300 and attachments <= 1:
        return 3
    if wc < 800 or attachments <= 3:
        return 4
    return 5


def detect_workspace_domain(cwd=None):
    """Map current working directory to a routing domain (boost factor 1.5x)."""
    cwd = (cwd or os.getcwd()).lower()
    if "placemybooking" in cwd:
        return "pmb"
    if "yama" in cwd:
        return "yama"
    if "ha-playground" in cwd:
        return "ha"
    if "productivity" in cwd:
        return "productivity"
    return "global"


def score_capabilities(prompt_keywords, intent, workspace_domain,
                       max_candidates=DEFAULT_MAX_CANDIDATES,
                       min_score=DEFAULT_MIN_SCORE,
                       db_path=DB):
    """Rank capabilities by keyword-overlap weight + domain boost. Read-only DB query."""
    if not prompt_keywords:
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = conn.cursor()
    scores = {}
    descriptions = {}
    placeholders = ",".join("?" for _ in prompt_keywords)
    cur.execute(f"""
        SELECT c.id, c.name, c.kind, c.domain, c.description, c.status,
               ck.keyword, ck.weight
        FROM capabilities c
        JOIN capability_keywords ck ON ck.capability_id = c.id
        WHERE ck.keyword IN ({placeholders})
          AND c.status = 'active'
    """, list(prompt_keywords))
    for cap_id, name, kind, domain, desc, _status, _kw, weight in cur.fetchall():
        base = weight
        if domain == workspace_domain:
            base *= 1.5
        elif domain == "global":
            base *= 1.0
        elif domain == "agency":
            base *= 0.5  # de-prio agency-agents (was 0.85, lowered 2026-04-29 after smoke-test showed Carousel Growth Engine matched "PreToolUse Hook" prompts via random keyword overlap; agency-agents have noisy keyword maps)
        else:
            base *= 0.7
        scores[cap_id] = scores.get(cap_id, 0) + base
        descriptions[cap_id] = (name, kind, domain, desc or "")
    conn.close()
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    results = []
    for cap_id, score in ranked[:max_candidates * 2]:
        if score < min_score:
            break
        name, kind, domain, desc = descriptions[cap_id]
        results.append({
            "id": cap_id,
            "name": name,
            "kind": kind,
            "domain": domain,
            "description": desc[:160],
            "score": round(score, 2),
        })
    return results[:max_candidates]


def route_text(text, max_candidates=DEFAULT_MAX_CANDIDATES,
               min_score=DEFAULT_MIN_SCORE, cwd=None, top_keywords_n=50,
               context_prefix=""):
    """
    Library entry point — used by parse-prompt Step 5.5 for per-item routing.

    Given an item-text (one Requirement / one Future-Work bullet), return
    ranked capability candidates. No DB writes, no side effects.

    `context_prefix` (NEW 2026-04-29 Step 5.5 v2): an interpretation/tag-string
    prepended to `text` before tokenization. Use it to inject workspace tag +
    subject tags + action verbs that the raw item-text doesn't contain.
    Example: route_text("Reagier auf das", context_prefix="pmb timeline review verify pr-270")
    -> tokens contain pmb, timeline, review, verify, pr-270 alongside whatever
    the raw text yields. Without the prefix, vague items like "Reagier auf das"
    return 0 candidates. Stefan-Korrektur 2026-04-29: routing should be based on
    the interpretation of words in context, not the raw words.
    """
    full_text = f"{context_prefix} {text}".strip() if context_prefix else text
    keywords = tokenize(full_text)
    if not keywords:
        return {"intent": "unknown", "complexity": 1, "candidates": []}
    intent = detect_intent(full_text)
    complexity = detect_complexity(text)  # complexity = on raw, not interpretation
    workspace_domain = detect_workspace_domain(cwd)
    kw_counter = Counter(keywords)
    top_kws = [kw for kw, _ in kw_counter.most_common(top_keywords_n)]
    candidates = score_capabilities(set(top_kws), intent, workspace_domain,
                                    max_candidates=max_candidates,
                                    min_score=min_score)
    return {
        "intent": intent,
        "complexity": complexity,
        "workspace_domain": workspace_domain,
        "keywords": top_kws[:20],
        "candidates": candidates,
        "context_prefix": context_prefix,  # echo back for traceability
    }


# CLI for ad-hoc testing: echo "fix the timeline bug" | python3 -m routing
if __name__ == "__main__":
    import json
    import sys
    txt = sys.stdin.read()
    print(json.dumps(route_text(txt), indent=2, ensure_ascii=False))
