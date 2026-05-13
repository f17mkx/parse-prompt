"""
Parser library — classify prompt text into the 8 parse-prompt dimensions.

Extracted from `commands/parse-prompt.md` Step 4 logic + Step 3 (workspace detection)
+ Step 7 (security flags) as part of LIB-EXTRACTION-001 Phase 1, Tranche 2
(branch f17mkx/parse-prompt-lib-extract).

Public API:
- classify(prompt_text)          -> dict[dim_id → list[Item]]
- detect_workspace_type(path)    -> str
- detect_security_flags(text)    -> list[SecurityFlag]
- extract_bullets(text)          -> list[str]

Internal helpers (underscore-prefixed, exposed for testing):
- _generate_title(text, max_len)
- _matches_any(text, pattern_dict)
- _classify_4_7_eval_type(item, text)
- _is_4_7_small_scope(verbatim)
- _resolve_4_6_vs_4_7(text)

Pure-compute module: no I/O, no DB access, no file writes. The skill orchestrator
(`commands/parse-prompt.md`) handles file routing based on classify() output.

Stateless. Same input always produces same output. Tests are deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Allow `from parser import ...` when run from repo root
import sys
sys.path.insert(0, str(Path(__file__).parent))
import dimensions as D


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Item:
    """A single classified item from a prompt.

    A prompt can yield 0..N items per dimension. Same verbatim text may appear
    in multiple dimensions if it triggers multiple patterns (e.g. "shippe das
    spaeter" hits both 4.1 imperative and 4.6 deferral).
    """
    dimension: str          # "4.1", "4.2", ..., "4.8"
    verbatim: str           # original quote, never paraphrased
    title: str              # short auto-generated title (first ~60 chars)
    metadata: dict = field(default_factory=dict)
    # metadata keys per dimension:
    # - 4.1: {"matched_pattern": str}
    # - 4.6: {"deferral_keyword": str, "inspiration_urls": list[str]}
    # - 4.7: {"eval_type": "Deep-Dive"|"Conditional-Execute"|"Idea-Validation",
    #         "scope": "small"|"large"}
    # - 4.8: {"state_change_type": str, "old_value": str, "new_value": str | None}


@dataclass
class SecurityFlag:
    """A detected cleartext credential or secret in the prompt."""
    pattern_name: str       # which pattern dict key matched (e.g. "password_keyword")
    matched_text: str       # the matching substring (verbatim, NOT redacted)
    severity: str           # "warn" (likely false-positive risk) or "block" (clear secret)


@dataclass
class ParentheticalInsert:
    """A parenthetical insert in the prompt: '(also wie dieses hier)'.

    Stefan macht oft Klammer-Einschübe für Klarstellung, Kontrast, Self-Reference
    oder Frage-Inserts. Diese sollen erkannt und sub-klassifiziert werden, damit
    der Skill versteht ob der Einschub eine Klarstellung (kein eigenes Item),
    eine Frage (small-scope 4.7) oder ein Kontrast (4.3-Hinweis) ist.

    insert_type: "Clarification" | "Contrast" | "Question-Insert" | "Self-Reference" | "Note"
    closed: True wenn die schließende Klammer im Text war, False wenn vergessen
    (Stefan-Bemerkung: "ich kann mal eine klammer zu schließen vergessen").
    """
    text: str               # content innerhalb der Klammern (ohne ( ))
    insert_type: str
    closed: bool = True


@dataclass
class DashComment:
    """Ein Dash-Comment: 'X - klarstellung dazu' oder 'A - aber B'.

    Wie Parenthetical-Inserts aber via " - " statt "( )". Gleiche Sub-Types.
    """
    text: str
    insert_type: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(prompt_text: str) -> dict[str, list[Item]]:
    """Classify a prompt into all 8 dimensions.

    Strategy:
    1. Extract bullets from the prompt (multi-line `^- ` or `^* ` items).
       If no bullets, treat the whole prompt as a single item.
    2. For each item: run all 8 dimension pattern-checks.
    3. Apply 4.6-vs-4.7 precedence resolution (Decision-Tree from stefan-input-grammar.md).
    4. For 4.7 items: assign eval_type and scope sub-classification.
    5. Return dict[dim_id → list[Item]]. Empty list if no hits for that dim.

    Returns: dict with keys "4.1" through "4.8", each mapping to list of Item.
    """
    # Initialize empty result dict for all 8 dimensions (consistent shape).
    result: dict[str, list[Item]] = {dim["id"]: [] for dim in D.DIMENSIONS}

    # Step 1: split prompt into bullet-items. If no bullets: full text as one item.
    bullets = extract_bullets(prompt_text)
    if not bullets:
        bullets = [prompt_text.strip()]

    # Step 2: split each bullet into sub-items (Stefan-Korrektur 2026-05-01 Punkt 6:
    # ein Bullet wie "4 ist gut, ändere X, lass uns Y für später, wenn nicht Z (?)"
    # enthält mehrere Items die separat klassifiziert werden müssen).
    items_text: list[str] = []
    for bullet in bullets:
        sub = split_into_subitems(bullet)
        items_text.extend(sub if sub else [bullet])

    # Step 3: classify each (sub-)item independently against all 8 dimensions.
    for item_text in items_text:
        if not item_text.strip():
            continue
        _classify_single_item(item_text, result)

    return result


def detect_workspace_type(workspace_path: Path) -> str:
    """Detect workspace type from a single path (typically the cwd).

    Stefan-Decision 2026-05-01: detects conductor repos primarily.
    Returns one of: "pmb", "ha-playground", "productivity", "ha-live-config", "generic".

    Detection: ordered fragment-search via D.WORKSPACE_TYPE_DETECTORS (conductor paths
    first, then structural fallbacks). First-match-wins. Trailing-slash normalization
    so Path("foo/") works as expected (Path strips trailing slashes during construction).

    For multi-path detection (when an item references files in different workspaces),
    use detect_referenced_workspaces() instead.
    """
    path_str = str(workspace_path).rstrip("/") + "/"

    for fragment, ws_type in D.WORKSPACE_TYPE_DETECTORS:
        if fragment in path_str:
            return ws_type

    return D.WORKSPACE_TYPE_DEFAULT


def detect_referenced_workspaces(text: str) -> list[tuple[str, int]]:
    """Detect workspace types from paths REFERENCED in the text (Stefan-Korrektur 2026-05-01 Punkt 2).

    Use case: a Stefan-prompt like
      "siehe /Users/admin/conductor/workspaces/claude-dotfiles/task-tripwire/foo.py
       und /Users/admin/conductor/workspaces/ha-playground/minnetonka-v3/README.md"
    references files in TWO workspaces. The cwd-based detect_workspace_type would
    return only the cwd's type and miss the cross-workspace references.

    Strategy:
    1. Find all path-like substrings in text (matching D.TRIGGER_PATTERNS_4_4 paths).
    2. For each path: run the same fragment-matching as detect_workspace_type.
    3. Count occurrences per type. Return list[(type, count)] sorted by count desc.

    Returns: list of (workspace_type, occurrence_count) tuples. Dominant type first.
             Empty list if no paths found in text. "generic" matches are excluded
             (they'd swamp results with random conductor sub-paths).
    """
    from collections import Counter

    # Workspace-detection uses ONLY absolute paths - relative paths like
    # "commands/parse-prompt.md" don't carry workspace info, and abs_path +
    # rel_path overlap (rel_path matches tail of abs_path), so using both
    # double-counts workspace hits.
    abs_paths = re.findall(D.TRIGGER_PATTERNS_4_4["abs_path"], text)
    seen: set = set()
    deduped: list[str] = []
    for p in abs_paths:
        s = p.strip()
        if s and s not in seen:
            seen.add(s)
            deduped.append(s)

    counts: Counter = Counter()
    for path_str in deduped:
        normalized = path_str.rstrip("/") + "/"
        for fragment, ws_type in D.WORKSPACE_TYPE_DETECTORS:
            if fragment in normalized:
                counts[ws_type] += 1
                break  # first-match-wins per path

    return counts.most_common()


def detect_security_flags(prompt_text: str) -> list[SecurityFlag]:
    """Detect cleartext credentials/secrets in the prompt.

    Returns list of SecurityFlag objects. Empty list if none found.

    Severity levels:
    - "block": clear key=value pair with high confidence (password=X, token=X)
    - "warn":  high-entropy string only (could be UUID, hash, or actual secret)
    """
    flags: list[SecurityFlag] = []

    for name, pattern in D.TRIGGER_PATTERNS_4_4_SECRETS.items():
        for m in re.finditer(pattern, prompt_text, re.IGNORECASE):
            severity = "warn" if name == "high_entropy" else "block"
            flags.append(SecurityFlag(
                pattern_name=name,
                matched_text=m.group(0),
                severity=severity,
            ))

    return flags


def extract_bullets(text: str) -> list[str]:
    """Extract bullet items from prompt text. Supports `- `, `* ` AND numbered markers.

    NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 3: Stefan antwortet oft mit
    "NUMMER verbatim" auf nummerierte Listen vom Assistant - z.B. "4 ja, das ist
    eine gute idee" oder "3. nicht so" oder "5: noch ein punkt" oder "2) ja".
    Diese werden jetzt als gleichwertig zu "- " bullets erkannt.

    Bullet markers (alle case-sensitive, am Zeilenanfang):
    - `^- text`      → dash bullet
    - `^* text`      → asterisk bullet
    - `^\\d+ text`   → numbered without separator
    - `^\\d+. text`  → numbered with dot
    - `^\\d+: text`  → numbered with colon
    - `^\\d+) text`  → numbered with paren

    Each bullet content is stripped. Multi-line bullets (continuation) are NOT
    supported in v1 — each match is its own bullet. Most Stefan-prompts are
    single-line bullets so this is fine.

    Returns: list of bullet contents in document order. Empty list if no bullets.
    """
    bullet_re = re.compile(D.ANY_BULLET_PATTERN, re.MULTILINE)
    return [m.group(1).strip() for m in bullet_re.finditer(text)]


def extract_bullet_numbers(bullet_marker: str) -> list[int]:
    """Extract all integer numbers from a bullet marker (NEU 2026-05-01 Punkt 5).

    Stefan adressiert mit Bullets oft mehrere voraus-Items gleichzeitig:
      "5,6,7 ok"     → [5, 6, 7]
      "2-6 ok"       → [2, 3, 4, 5, 6]   (range expansion)
      "4+5"          → [4, 5]
      "5 + 6"        → [5, 6]
      "4"            → [4]
      "- foo"        → []                (no numbers)

    Range-Expansion ist konservativ - nur 2-stelliger Range, keine reverse-ranges,
    keine offene Ranges.

    Returns: list of int IDs in the order they appear. Empty list if no numbers.
    """
    # Range-Pattern zuerst, weil "2-6" sonst als einzelne 2 + 6 interpretiert würde
    range_match = re.match(r"^(\d+)\s*-\s*(\d+)\s*$", bullet_marker.strip())
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        if lo <= hi:
            return list(range(lo, hi + 1))
        return [lo, hi]  # reverse-range degeneriert auf endpoints

    # Sonst: alle Integer-Substrings extrahieren in der Reihenfolge
    return [int(n) for n in re.findall(r"\d+", bullet_marker)]


def extract_parenthetical_inserts(text: str) -> list[ParentheticalInsert]:
    """Extract parenthetical inserts from text (NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 5).

    Robust gegen unmatched Klammern (Stefan-Bemerkung: "ich kann mal eine klammer
    zu schließen vergessen") - matched bis schließende Klammer ODER Zeilenende
    ODER nächstem Bullet-Marker.

    Sub-Klassifizierung pro Insert:
    - "Question-Insert": Klammer-Inhalt endet mit "?"
    - "Clarification": "also", "z.B.", "i.e.", "siehe", "d.h." (DE/EN)
    - "Contrast": "statt", "aber", "dagegen", "instead", "but" (DE/EN)
    - "Self-Reference": "weißt schon", "you know", "sozusagen" (DE/EN)
    - "Note": fallback wenn kein anderer Sub-Type matched

    Returns: list of ParentheticalInsert in document order.
    """
    inserts: list[ParentheticalInsert] = []
    for m in re.finditer(D.PARENTHETICAL_PATTERN, text, re.MULTILINE):
        content = m.group(1).strip()
        if not content:
            continue
        # closed=True wenn matched-region mit ")" endet, sonst False (vergessen)
        closed = text[m.end() - 1] == ")" if m.end() <= len(text) else False
        insert_type = _classify_parenthetical_type(content)
        inserts.append(ParentheticalInsert(text=content, insert_type=insert_type, closed=closed))
    return inserts


def extract_dash_comments(text: str) -> list[DashComment]:
    """Extract dash-comments from text (NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 5).

    Pattern: " - X" mit min. einem Space vor dem Dash, um Bindestrich-Wörter
    (z.B. "ha-playground", "small-scope") als false-positive auszuschließen.

    Sub-Klassifizierung wie bei Parenthetical-Inserts (Clarification/Contrast/
    Question-Insert/Self-Reference/Note).

    Returns: list of DashComment in document order.
    """
    comments: list[DashComment] = []
    for m in re.finditer(D.DASH_COMMENT_PATTERN, text):
        content = m.group(1).strip()
        if not content or len(content) < 3:
            continue
        insert_type = _classify_parenthetical_type(content)
        comments.append(DashComment(text=content, insert_type=insert_type))
    return comments


def extract_tool_output_lines(text: str) -> list[str]:
    """Extract tool-output lines from text (NEU 2026-05-01 Stefan-Korrektur Turn 9 Punkt 2).

    Stefan paste'd manchmal Command-Output in den Prompt - z.B. nach `python3
    ~/.claude/scripts/init-deps-update.py` paste'd er den Output mit Lines wie
    `[init-deps-update] workspace_type=ha-playground, repo=ha-playground`.

    Diese Lines sind weder Requirements noch Questions noch Reject - sie sind
    Tool-Execution-Context. classify() ignoriert sie aber sie sollen separat
    extrahierbar sein damit sie als 4.4 Context-Reference behandelt werden können.

    Pattern: `^[program-name]\\s+content` (square-bracketed program-name als prefix).

    Returns: list of tool-output lines (full line incl. brackets) in document order.
    """
    return [m.group(0) for m in re.finditer(D.TOOL_OUTPUT_PATTERN, text, re.MULTILINE)]


def split_into_subitems(bullet_text: str) -> list[str]:
    """Split a bullet into sub-items if it contains multiple actions/topics.

    NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 6.

    Beispiel: "4 ist gut so, ändere nur X, lass uns Y für später, wenn nicht Z (?)"
    → splittet in ["4 ist gut so", "ändere nur X", "lass uns Y für später",
                   "wenn nicht Z (?)"]

    Trigger sind Komma + Konjunktion ODER Komma + Imperativ-Stem (siehe
    D.SUBITEM_SPLIT_PATTERNS). Konservativ - splitten nur an klaren Boundaries
    um false-positives ("ändere X, Y, und Z" als Liste-of-Args) zu vermeiden.

    Returns: list of sub-item strings. Single-element list wenn kein split-Trigger.
    """
    if not bullet_text.strip():
        return []

    # Build kombinierten split-Pattern aus allen SUBITEM_SPLIT_PATTERNS (OR-merged)
    combined = "|".join(D.SUBITEM_SPLIT_PATTERNS)
    parts = re.split(combined, bullet_text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Internal helpers (exposed for testing)
# ---------------------------------------------------------------------------

def _classify_single_item(item_text: str, result: dict[str, list[Item]]) -> None:
    """Classify a single item-text against all 8 dimensions, mutating result in-place.

    A single item can land in multiple dimensions. We check each dimension's
    pattern dict; if any pattern matches, an Item is created in result[dim].
    """
    # 4.1 Explicit Requirements
    matched, pat_name = _matches_any(item_text, D.TRIGGER_PATTERNS_4_1)
    if matched:
        result["4.1"].append(Item(
            dimension="4.1",
            verbatim=item_text,
            title=_generate_title(item_text),
            metadata={"matched_pattern": pat_name},
        ))

    # 4.2 Questions
    matched, pat_name = _matches_any(item_text, D.TRIGGER_PATTERNS_4_2)
    if matched:
        result["4.2"].append(Item(
            dimension="4.2",
            verbatim=item_text,
            title=_generate_title(item_text),
            metadata={"matched_pattern": pat_name},
        ))

    # 4.3 Rejections
    matched, pat_name = _matches_any(item_text, D.TRIGGER_PATTERNS_4_3)
    if matched:
        result["4.3"].append(Item(
            dimension="4.3",
            verbatim=item_text,
            title=_generate_title(item_text),
            metadata={"matched_pattern": pat_name},
        ))

    # 4.4 Context References — extracted differently (every match is its own ref)
    refs = _extract_context_refs(item_text)
    if refs:
        result["4.4"].append(Item(
            dimension="4.4",
            verbatim=item_text,
            title=_generate_title(item_text),
            metadata={"refs": refs},
        ))

    # 4.5 Risks / Ambiguities
    matched, pat_name = _matches_any(item_text, D.TRIGGER_PATTERNS_4_5)
    if matched:
        result["4.5"].append(Item(
            dimension="4.5",
            verbatim=item_text,
            title=_generate_title(item_text),
            metadata={"matched_pattern": pat_name},
        ))

    # 4.6 vs 4.7 Precedence: "evtl + Vorschlag" → 4.7, "evtl + später" → 4.6
    # Resolve before assigning to dim.
    dim_46_47 = _resolve_4_6_vs_4_7(item_text)

    # Stefan-Korrektur 2026-05-01 Turn 9 Punkt 1: bei 4.6 + 4.7-small-scope-Trigger
    # simultaneous (z.B. "hard block für später (?)") sollen BEIDE matchen + ein
    # Marker "conditional_defer_question" - das ist ein Sanity-Check-Pattern wo Stefan
    # fragt OB ein Backlog-Item gemacht werden soll.
    # Wichtig: NUR triggern wenn KEINE evtl/vielleicht im Text - sonst hat
    # _resolve_4_6_vs_4_7 schon die richtige Decision (evtl+spaeter -> 4.6 only).
    has_evtl_marker = bool(re.search(r"\b(eventuell|evtl|vielleicht)\b", item_text, re.IGNORECASE))
    matches_46, _ = _matches_any(item_text, D.TRIGGER_PATTERNS_4_6)
    matches_47, _ = _matches_any(item_text, D.TRIGGER_PATTERNS_4_7)
    is_small_47 = matches_47 and _is_4_7_small_scope(item_text)
    is_conditional_defer = matches_46 and is_small_47 and not has_evtl_marker

    if dim_46_47 == "4.6" or is_conditional_defer:
        matched, pat_name = _matches_any(item_text, D.TRIGGER_PATTERNS_4_6)
        if matched:
            urls = _extract_urls(item_text)
            md: dict = {
                "deferral_keyword": pat_name,
                "inspiration_urls": urls,
            }
            if is_conditional_defer:
                md["conditional_defer_question"] = True
                md["recommended_action"] = "Ask user: should this become a backlog item?"
            result["4.6"].append(Item(
                dimension="4.6",
                verbatim=item_text,
                title=_generate_title(item_text),
                metadata=md,
            ))

    if dim_46_47 == "4.7" or is_conditional_defer:
        matched, pat_name = _matches_any(item_text, D.TRIGGER_PATTERNS_4_7)
        if matched:
            eval_type = _classify_4_7_eval_type(item_text)
            scope = "small" if _is_4_7_small_scope(item_text) else "large"
            md_47: dict = {
                "eval_type": eval_type,
                "scope": scope,
                "matched_pattern": pat_name,
            }
            # Stefan-Korrektur 2026-05-02 (v2-Pattern wiring): wenn das Conditional-Pre-Check
            # Pattern matched, setze pre_check_required als handlungsleitendes Flag. Agent
            # liest das aus prompt-analysis-N.md und reagiert: erst Pre-Check, GRÜN → execute,
            # ROT → stop + erklären. Verhindert blocking-Stop bei trivialen No-Op-Fällen.
            # Direct re.search statt pat_name-Check, weil _matches_any den ersten Treffer
            # zurückgibt - das wäre meist evtl_with_proposal_de (kommt im Dict zuerst), nicht
            # conditional_pre_check_de. Beide Patterns matchen den selben Text - wir brauchen
            # die spezifische Detection.
            has_pre_check = bool(
                re.search(D.TRIGGER_PATTERNS_4_7["conditional_pre_check_de"],
                          item_text, re.IGNORECASE)
                or re.search(D.TRIGGER_PATTERNS_4_7["conditional_pre_check_en"],
                             item_text, re.IGNORECASE)
            )
            if has_pre_check:
                md_47["pre_check_required"] = True
                md_47["recommended_action"] = (
                    "Run pre-check first. If green: inline-execute (no stop). "
                    "If red: stop + explain. If mixed-signal: describe then ask."
                )
            if is_conditional_defer:
                md_47["conditional_defer_question"] = True
                md_47["paired_with_4_6"] = True
            result["4.7"].append(Item(
                dimension="4.7",
                verbatim=item_text,
                title=_generate_title(item_text),
                metadata=md_47,
            ))

    # 4.8 Implicit Followups (state changes)
    matched, pat_name = _matches_any(item_text, D.TRIGGER_PATTERNS_4_8)
    if matched:
        result["4.8"].append(Item(
            dimension="4.8",
            verbatim=item_text,
            title=_generate_title(item_text),
            metadata={
                "state_change_type": pat_name,
                # old/new values: not extracted in v1 - requires NLP pass beyond regex.
                # Stop-hook can do git-grep based mismatch-detection separately.
            },
        ))


def _matches_any(text: str, pattern_dict: dict) -> tuple[bool, Optional[str]]:
    """Check if any pattern in dict matches text. Returns (matched, pattern_name).

    Pattern_name is the dict key of the FIRST matching pattern (deterministic
    by dict-insertion order, which is stable in Python 3.7+).
    """
    for name, pat in pattern_dict.items():
        if re.search(pat, text, re.IGNORECASE):
            return True, name
    return False, None


def _generate_title(text: str, max_len: int = 60) -> str:
    """Generate a short title from item-text. First ~max_len chars, word-boundary trimmed."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Trim back to last word boundary if possible
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


def _resolve_4_6_vs_4_7(text: str) -> Optional[str]:
    """Resolve 4.6 vs 4.7 precedence per stefan-input-grammar.md TL;DR Decision Tree.

    Rules:
    - "evtl" / "eventuell" / "vielleicht" + deferral keyword ("später", "for now") → 4.6
      (deferral wins because Stefan signals "not now AND uncertain")
    - "evtl" / "eventuell" / "vielleicht" + proposal (no deferral keyword) → 4.7
      (Stefan signals "uncertain whether to do at all")
    - Pure 4.6 patterns (no evtl/vielleicht) → 4.6
    - Pure 4.7 patterns (no deferral) → 4.7
    - Neither → None

    Returns: "4.6", "4.7", or None.
    """
    has_evtl = bool(re.search(r"\b(eventuell|evtl|vielleicht)\b", text, re.IGNORECASE))
    has_deferral = bool(re.search(
        r"\b(später|spaeter|irgendwann|nicht\s+jetzt|for\s+now|next\s+release|in\s+v\d|later|someday)\b",
        text, re.IGNORECASE
    ))
    matches_4_7, _ = _matches_any(text, D.TRIGGER_PATTERNS_4_7)
    matches_4_6, _ = _matches_any(text, D.TRIGGER_PATTERNS_4_6)

    if has_evtl and has_deferral:
        # "evtl machen wir das später" → 4.6 (deferral semantics dominate)
        return "4.6"
    if has_evtl and not has_deferral:
        # "evtl docs cleanup machen" → 4.7 (eval-then-decide)
        return "4.7"
    if matches_4_7 and not matches_4_6:
        return "4.7"
    if matches_4_6 and not matches_4_7:
        return "4.6"
    if matches_4_6 and matches_4_7:
        # Tie without evtl-disambiguator: prefer 4.7 (Stefan: "im Zweifel 4.7, drops sind schmerzhafter")
        return "4.7"
    return None


def _classify_4_7_eval_type(text: str) -> str:
    """Sub-classify a 4.7 item into Deep-Dive / Conditional-Execute / Idea-Validation.

    Per parse-prompt.md Step 4.7 sub-cases:
    - Deep-Dive: explicit "deep dive", "abwägen", "prüfen" without conditional structure
    - Conditional-Execute: "wenn ... gute idee" / "if ... worth it" structure ODER
      v2-Pattern (Stefan 2026-05-02) "evtl X + (vorher prüfen)" - Pre-Check-Wrapper
    - Idea-Validation: self-doubt phrasings ("rede ich bullshit?", "stimmt das?")

    Reihenfolge wichtig: Idea-Validation hat Vorrang, weil self-doubt explizit nach
    Validierung fragt (kein Execute), während Conditional-Execute aktiv ausgeführt
    werden soll wenn der Pre-Check grün ist.
    """
    if re.search(D.TRIGGER_PATTERNS_4_7["self_doubt_de"], text, re.IGNORECASE):
        return "Idea-Validation"
    if re.search(D.TRIGGER_PATTERNS_4_7["self_doubt_en"], text, re.IGNORECASE):
        return "Idea-Validation"
    # Stefan-v2-Pattern (2026-05-02): "evtl + Klammer mit prüf/check/sanity/verify".
    # Höhere Priorität als das ältere "wenn-gute-idee"-Pattern, weil v2 expliziter ist
    # (Pre-Check-Verb in Klammern signalisiert deterministisch Conditional-Execute-Intent).
    if re.search(D.TRIGGER_PATTERNS_4_7["conditional_pre_check_de"], text, re.IGNORECASE):
        return "Conditional-Execute"
    if re.search(D.TRIGGER_PATTERNS_4_7["conditional_pre_check_en"], text, re.IGNORECASE):
        return "Conditional-Execute"
    if re.search(r"\b(wenn\s+(es\s+)?(sich\s+)?(eine\s+)?gute\s+idee|if\s+(it'?s\s+)?worth)\b",
                 text, re.IGNORECASE):
        return "Conditional-Execute"
    return "Deep-Dive"


def _is_4_7_small_scope(text: str) -> bool:
    """Heuristic: is this 4.7 item small-scope (inline-resolvable) or large-scope?

    Stefan-Korrektur 2026-04-30: small-scope sanity-checks werden inline beantwortet,
    nicht in BACKLOG geschoben.

    Stefan-Korrektur 2026-05-02 (v2-Pattern): "evtl + (vorher prüfen)" → small-scope.
    Begründung: Pre-Check + ggf. inline-execute ist per Definition keine Architektur-
    Entscheidung, sondern eine binäre go/no-go-Action im aktuellen Kontext. Wenn der
    Pre-Check teuer/architektonisch wird, matched zusätzlich large-scope-trigger und
    überschreibt diese Heuristik.

    Heuristic:
    1. Matches large-scope-trigger (deep-dive, multi-file, evaluate-alternatives) → large
       (overrides everything because explicit large-signal wins)
    2. Matches conditional-pre-check (v2 evtl + check) → small
    3. Matches small-scope-trigger (sanity-check, verstehen, trailing-(?)) → small
    4. Short text (<80 chars) without large-trigger → small
    5. Otherwise → large
    """
    matches_small, _ = _matches_any(text, D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE)
    matches_large, _ = _matches_any(text, D.TRIGGER_PATTERNS_4_7_LARGE_SCOPE)
    matches_conditional_precheck = bool(
        re.search(D.TRIGGER_PATTERNS_4_7["conditional_pre_check_de"], text, re.IGNORECASE)
        or re.search(D.TRIGGER_PATTERNS_4_7["conditional_pre_check_en"], text, re.IGNORECASE)
    )

    # Large-scope-Signal hat Vorrang - wenn jemand explizit "deep dive" oder "refaktor"
    # sagt, ist auch eine Pre-Check-Klammer drin nicht klein-scoped.
    if matches_large:
        return False
    if matches_conditional_precheck:
        return True
    if matches_small:
        return True
    # Short text + no large-trigger = probably small-scope question
    if len(text) < 80:
        return True
    return False


def _extract_context_refs(text: str) -> dict[str, list[str]]:
    """Extract context references (paths, URLs, entity-IDs, dates, etc.) from text.

    Returns dict keyed by ref-type with list of matched substrings per type.
    Empty dict if no refs found.
    """
    refs: dict[str, list[str]] = {}
    for name, pattern in D.TRIGGER_PATTERNS_4_4.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # findall returns list of strings or list of tuples (if regex has groups).
            # Normalize: take first group element if tuple, else the string itself.
            normalized = [m if isinstance(m, str) else m[0] for m in matches]
            refs[name] = normalized
    return refs


def _extract_urls(text: str) -> list[str]:
    """Extract URLs from text (helper for 4.6 inspiration-URL preservation)."""
    return re.findall(D.TRIGGER_PATTERNS_4_4["url"], text, re.IGNORECASE)


def _classify_parenthetical_type(content: str) -> str:
    """Sub-classify a parenthetical or dash-comment content into a type.

    Order: Question-Insert (most specific) > Self-Reference > Contrast >
    Clarification > Note (fallback).

    Returns: "Question-Insert" | "Self-Reference" | "Contrast" | "Clarification" | "Note"
    """
    stripped = content.rstrip(".").strip()

    if stripped.endswith("?"):
        return "Question-Insert"

    matched, _ = _matches_any(content, {
        k: v for k, v in D.PARENTHETICAL_TYPE_PATTERNS.items() if "self_reference" in k
    })
    if matched:
        return "Self-Reference"

    matched, _ = _matches_any(content, {
        k: v for k, v in D.PARENTHETICAL_TYPE_PATTERNS.items() if "contrast" in k
    })
    if matched:
        return "Contrast"

    matched, _ = _matches_any(content, {
        k: v for k, v in D.PARENTHETICAL_TYPE_PATTERNS.items() if "clarification" in k
    })
    if matched:
        return "Clarification"

    return "Note"
