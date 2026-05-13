"""
Interpretation library — Step 5.5 v2 Interpretation-Generator.

Extracted from `commands/parse-prompt.md` Step 5.5 (per-Item routing v2,
2026-04-29 Stefan-Korrektur "das routing soll nicht basierend auf meinen worten
passieren sondern aus der Interpretation meiner Worte im Kontext") as part of
LIB-EXTRACTION-001 Phase 1, Tranche 3.

The interpretation string format is:
  "<workspace-tag> <subject-tags> <action-verbs> <referenced-entities>"

Example:
  Raw item:       "Reagier auf das" (im Kontext PR #270 timeline)
  Interpretation: "pmb timeline review verify checklist pr-270"

This interpretation feeds into `lib/routing.py route_text(item_text, context_prefix=...)`
for per-item routing recommendations. The interpretation amplifies signal beyond
what raw item text alone provides — context-dependent prompts ("fix das", "shippe es")
become routable when interpretation includes the surrounding context.

Pure-compute module: no I/O, no DB, no file reads. The skill orchestrator
(`commands/parse-prompt.md`) builds the ConversationContext and passes it in.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Allow `from interpretation import ...` when run from repo root
sys.path.insert(0, str(Path(__file__).parent))
import dimensions as D
from parser import Item, _matches_any  # share parser helpers


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConversationContext:
    """Context surrounding an item that helps build a meaningful interpretation.

    Built by the parse-prompt skill orchestrator before calling
    generate_interpretation(item, context) per-item.

    workspace_type: from detect_workspace_type(cwd) - the active workspace
    cwd: working directory Path for the current session
    referenced_files: paths the user mentioned in the broader prompt or recent turn
    referenced_prs: PR numbers parsed from the broader prompt (e.g. "PR #270")
    last_assistant_text: optional - text of the previous assistant message,
                         used when current item is short and context-dependent
                         ("Reagier auf das" → context_prefix from prior turn)
    """
    workspace_type: str
    cwd: Path
    referenced_files: list[str] = field(default_factory=list)
    referenced_prs: list[int] = field(default_factory=list)
    last_assistant_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Tag-Mapping aggregation per workspace type
# ---------------------------------------------------------------------------

# Map workspace_type → which tag dictionary to use for subject extraction
_TAG_MAP_BY_WORKSPACE = {
    "pmb": D.TAG_MAPPING_PMB,
    "ha-playground": D.TAG_MAPPING_HA,
    "ha-live-config": D.TAG_MAPPING_HA,
    # productivity + generic + others: no specific tag map, fall through to keyword extraction
}


# Action verbs aggregated from 4.1 imperative patterns. Used to extract action-tags
# from item text. List is curated from D.TRIGGER_PATTERNS_4_1 imperative_de + _en.
ACTION_VERB_STEMS = [
    "ship", "fix", "add", "remove", "update", "implement", "integrate", "configure",
    "validate", "document", "migrate", "refactor", "optimize", "extract", "convert",
    "port", "copy", "start", "stop", "reload", "restart", "deploy", "test", "push",
    "merge", "rebase", "make", "change", "build", "create", "write", "delete", "move",
    "show",
    # German equivalents (stems):
    "shipp", "mach", "änder", "aender", "entfern", "zeig", "füg", "fueg",
    "erstell", "bau", "aktualisier", "verschieb", "updat", "schreib", "lösch", "loesch",
    "implementier", "integrier", "konfigurier", "validier", "dokumentier", "migrier",
    "refaktor", "optimier", "extrahier", "konvertier", "portier", "kopier", "starte",
    "stopp", "teste",
    # Review/eval verbs (4.7-flavored)
    "review", "verify", "check", "audit", "abwäg", "abwaeg", "prüf", "pruef",
]


# Stopwords (small subset relevant for interpretation tags)
_STOPWORDS = set("""
das die der den dem ist sind ein eine einen einem auf von für mit zu zur zum
und oder aber wenn dann sonst nicht kein keine wir uns mich mir dich dir
the a an and or but if then else this that these those is are be was were
to from of for at in on by with into out over under
""".split())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_interpretation(item: Item, context: ConversationContext) -> str:
    """Generate the v2 interpretation string for an item.

    Format: "<workspace-tag> <subject-tags> <action-verbs> <referenced-entities>"

    All components are space-separated, lowercased, deduplicated. Empty components
    are skipped (e.g. if no subject-tags found, that section is empty).

    The interpretation feeds into `lib/routing.py route_text(item.verbatim,
    context_prefix=interpretation)` for per-item routing recommendations.
    """
    parts: list[str] = []

    # 1. Workspace-tag (always present)
    ws_tag = _get_workspace_tag(context.workspace_type)
    if ws_tag:
        parts.append(ws_tag)

    # 2. Subject-tags (from TAG_MAPPING_PMB/HA + entity extraction)
    subject_tags = extract_subject_tags(item, context)
    parts.extend(subject_tags)

    # 3. Action-verbs (from 4.1 imperative patterns matched in item)
    action_verbs = extract_action_verbs(item)
    parts.extend(action_verbs)

    # 4. Referenced entities (PR #s, paths, HA entities)
    entities = extract_referenced_entities(item, context)
    parts.extend(entities)

    # Dedupe preserving order
    seen: set = set()
    deduped = []
    for p in parts:
        p_lower = p.lower()
        if p_lower not in seen:
            seen.add(p_lower)
            deduped.append(p_lower)

    return " ".join(deduped)


def extract_subject_tags(item: Item, context: ConversationContext) -> list[str]:
    """Extract subject-tags from item.verbatim using workspace-specific TAG_MAPPING.

    For PMB: maps keywords like "tisch", "dashboard" to "settings/table-manager", etc.
    For ha-playground: maps "yama", "sonos" to "yama", "integrations/sonos", etc.
    Other workspaces: extract content-words (stopwords removed) as fallback tags.

    Returns: list of tags in document-order. Empty if no matches.
    """
    text_lower = item.verbatim.lower()
    tag_map = _TAG_MAP_BY_WORKSPACE.get(context.workspace_type, {})

    tags: list[str] = []
    for keyword, tag in tag_map.items():
        if keyword in text_lower and tag not in tags:
            tags.append(tag)

    if tags:
        return tags

    # Fallback: extract content-words (no stopwords, no numbers, length >= 3)
    words = re.findall(r"\b[a-zäöüß][\w\-]{2,}\b", text_lower)
    return [w for w in words if w not in _STOPWORDS][:5]  # cap at 5 to avoid noise


def extract_action_verbs(item: Item) -> list[str]:
    """Extract action verbs from item.verbatim that match known imperative stems.

    Uses ACTION_VERB_STEMS list (aggregated from D.TRIGGER_PATTERNS_4_1).
    Returns the matched stems (not the conjugated forms) for canonical-form routing.

    Returns: list of stem-form action verbs in document order. Empty if none.
    """
    text_lower = item.verbatim.lower()
    found: list[str] = []
    for stem in ACTION_VERB_STEMS:
        if re.search(rf"\b{re.escape(stem)}\w*\b", text_lower) and stem not in found:
            found.append(stem)
    return found


def extract_referenced_entities(item: Item, context: ConversationContext) -> list[str]:
    """Extract referenced entities from item.verbatim: PR refs, HA entities, paths-tail.

    Pulls from item.metadata if it has refs (set by parser._extract_context_refs),
    else extracts inline.

    Returns: list of entity strings (e.g. "pr-270", "light.licht_kind_1", "foo.py").
    """
    entities: list[str] = []

    # PR references: "#270" → "pr-270"
    pr_refs = re.findall(D.TRIGGER_PATTERNS_4_4["pr_reference"], item.verbatim)
    for pr in pr_refs:
        canonical = "pr-" + pr.lstrip("#")
        if canonical not in entities:
            entities.append(canonical)

    # HA entities: full entity-id stays as-is (e.g. "light.licht_kind_1")
    ha_entities = re.findall(D.TRIGGER_PATTERNS_4_4["ha_entity"], item.verbatim)
    for ha in ha_entities:
        if ha not in entities:
            entities.append(ha)

    # Path tails (last component of file paths) — useful for routing "fix the foo.py" type
    abs_paths = re.findall(D.TRIGGER_PATTERNS_4_4["abs_path"], item.verbatim)
    rel_paths = re.findall(D.TRIGGER_PATTERNS_4_4["rel_path"], item.verbatim)
    for path in abs_paths + rel_paths:
        # Take just the basename (filename) as entity for routing
        tail = path.strip().split("/")[-1] if "/" in path else path.strip()
        if tail and tail not in entities and len(tail) > 2:
            entities.append(tail)

    # Add PRs from context (the broader conversation may have established PR scope)
    for pr_num in context.referenced_prs:
        canonical = f"pr-{pr_num}"
        if canonical not in entities:
            entities.append(canonical)

    return entities


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_workspace_tag(workspace_type: str) -> str:
    """Map workspace type to its routing tag.

    Most types use their name directly. "generic" returns empty string
    (no workspace-tag for generic workspaces, just rely on subject/action signal).
    """
    if workspace_type in ("pmb", "ha-playground", "productivity", "ha-live-config"):
        return workspace_type
    return ""  # generic/other → no workspace-tag prefix
