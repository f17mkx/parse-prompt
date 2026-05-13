"""
Dimensions library — constants + format templates for parse-prompt 8-Dim classification.

Extracted from `commands/parse-prompt.md` Step 4 + Step 3 (workspace detection + tag mapping)
as part of LIB-EXTRACTION-001 (Phase 1, branch f17mkx/parse-prompt-lib-extract).

This is a pure-data module: no I/O, no logic. The classifier (`lib/parser.py`)
imports these constants and applies them.

Why split? See zzz-session-logs/2026-04-30-parse-prompt-lib-extract/0001-plan-phase1.md
and docs/parseprompt-feedback.md item 3 (browser-Claude review concern: 570-line
Markdown skill is too long for Claude to follow consistently in long sessions).
"""

# Pattern strings are kept as-is (not pre-compiled) so callers can choose whether to
# combine them into one mega-regex or apply them one-by-one with metadata. The parser
# module owns compilation strategy.

# ---------------------------------------------------------------------------
# Dimension metadata
# ---------------------------------------------------------------------------

DIMENSIONS = [
    {
        "id": "4.1",
        "title": "Explicit Requirements",
        "description": "imperative verbs, 'soll'-phrases, bug descriptions, positive confirmations",
        "routes_to_backlog": True,
    },
    {
        "id": "4.2",
        "title": "Questions",
        "description": "direct, clarifying, rhetorical, recall, meta — explicit AND implicit",
        "routes_to_backlog": False,
    },
    {
        "id": "4.3",
        "title": "Rejections",
        "description": "negations, preferences, ordering constraints, exclusions",
        "routes_to_backlog": False,
    },
    {
        "id": "4.4",
        "title": "Context References",
        "description": "paths, entity-IDs, URLs, persons/places, credentials (FLAGGED), dates, versions, numbers",
        "routes_to_backlog": False,
    },
    {
        "id": "4.5",
        "title": "Risks / Ambiguities",
        "description": "ambiguous references, missing values, conflicts, destructive actions, scope-creep",
        "routes_to_backlog": False,
    },
    {
        "id": "4.6",
        "title": "Future Work / Deferred Ideas",
        "description": "deferral phrases ('später', 'for now'), soft-suggestions, inspiration, speculation",
        "routes_to_backlog": True,  # routes to ## Future / ## Someday / ## Ideas
    },
    {
        "id": "4.7",
        "title": "Tentative-Action / Eval-Then-Decide",
        "description": "evtl/eventuell with proposal, '(?)' markers, deep-dive requests, idea-validation",
        "routes_to_backlog": True,  # routes to ## Tentative
    },
    {
        "id": "4.8",
        "title": "Implicit Followups / State-Mismatch",
        "description": "state-change confirmations ('ist durch'), action-past-tense, renames — generates implicit 4.1 items",
        "routes_to_backlog": True,  # via implicit 4.1 items
    },
]

DIMENSION_IDS = [d["id"] for d in DIMENSIONS]


# ---------------------------------------------------------------------------
# 4.1 Explicit Requirements — imperative verbs + soll-phrases + bug descriptions
# ---------------------------------------------------------------------------

# German imperative verbs (case-insensitive at apply-time).
# 2026-04-30 corpus-pass extension + \w*-suffix fix: stems followed by \w* match
# all German conjugation suffixes (-e, -t, -en, -te, -ten, etc.) — needed because
# Stefan writes "implementiere", "verschiebe", "dokumentiert" not just bare stems.
# Corpus-pass identified 110+ unclassified quotes from 335 historical
# prompt-analysis files using these missing imperatives.
TRIGGER_PATTERNS_4_1 = {
    "imperative_de": r"\b(mach\w*|änder\w*|aender\w*|entfern\w*|zeig\w*|füg\w*|fueg\w*|shipp\w*|erstell\w*|bau\w*|aktualisier\w*|verschieb\w*|updat\w*|schreib\w*|leg\w*\s+an|lösch\w*|loesch\w*|implementier\w*|integrier\w*|konfigurier\w*|validier\w*|dokumentier\w*|migrier\w*|refaktor\w*|optimier\w*|extrahier\w*|konvertier\w*|portier\w*|kopier\w*|start\w*|stopp\w*|reload\w*|restart\w*|deploy\w*|test\w*|push\w*|merg\w*|rebas\w*|bitte\s+(?:änder\w*|aender\w*|fix|mach\w*))\b",
    "imperative_en": r"\b(make|change|remove|show|add|ship|create|build|update|move|write|delete|implement|integrate|configure|validate|document|migrate|refactor|optimize|extract|convert|port|copy|start|stop|reload|restart|deploy|test|push|merge|rebase|please\s+(?:fix|change|add|remove))\b",
    # Confirm-Acknowledge (NEU 2026-05-01 Stefan-Korrektur Turn 8 Punkt 6): positive
    # Bestätigungen sind Items mit Status "Validiert" - Stefan bestätigt einen vorigen
    # Vorschlag/Plan. Aktuell hatte routing.py confirm-intent regex aber dimensions.py
    # nicht - cross-layer-Gap. "ist gut so", "ja passt", "go ahead", "perfect", "shipp es",
    # "machs", "genau", "los", "sign-off". Kann standalone Bullet-Antwort sein
    # ("4 ist gut so") oder am Anfang einer detaillierteren Antwort ("ja, machen wir, aber X").
    # 2026-05-01 Stefan-Korrektur Turn 9: standalone "passt" + standalone "ja" als
    # Confirm hinzugefügt (Stefan: "passt sage ich auch"). Standalone-Form via ^/$ anchor
    # mit optionalem Punkt/Satzzeichen + word-boundary safe.
    "confirm_ack_de": r"\b(ist\s+gut\s+so|ja\s+passt|passt\s+(?:so|genau)|^passt[\.\!\?]*$|^ja[\.\!\?]*$|genau|go\s+ahead|machs|mach\s+ruhig|los|shipp\w*\s+es|approved|sign[\-\s]?off)\b",
    "confirm_ack_en": r"\b(is\s+good|sounds\s+good|looks\s+good|go\s+ahead|approved|let'?s\s+do\s+it|ship\s+it|sign[\-\s]?off|that\s+works)\b",
    "soll_de": r"\b(soll(en|te)?|sollten\s+wir)\b",  # "X soll Y tun", "sollten wir X?"
    "should_en": r"\b(should\s+(we|i)|need\s+to|must)\b",
    "bug_de": r"\b(kaputt|klappt\s+nicht|geht\s+nicht|funktioniert\s+nicht|ist\s+broken)\b",
    "bug_en": r"\b(broken|doesn'?t\s+work|isn'?t\s+working|fails|crashes|errors\s+out)\b",
    "positive_validation": r"\b(funktioniert|works|ist\s+(jetzt\s+)?ok|läuft|laeuft|passt(\s+jetzt)?|durch|done|fertig)\b",
}


# ---------------------------------------------------------------------------
# 4.2 Questions — direct, clarifying, rhetorical, recall, meta
# ---------------------------------------------------------------------------

TRIGGER_PATTERNS_4_2 = {
    "wh_de": r"\b(was|wofür|wofuer|warum|wie|wann|wo|welch(e|er|es))\b",
    "wh_en": r"\b(what|why|how|when|where|which|who)\b",
    "question_mark_terminal": r"\?[\s\.!]*$",  # ends with ? (with optional trailing punct/whitespace)
    "question_mark_inline": r"\?",  # any ? (broader catch)
    "clarifying_de": r"\b(war\s+das\s+so\s+gemeint|stimmt\s+das|oder\s+nicht|richtig\?)\b",
    "clarifying_en": r"\b(is\s+that\s+right|am\s+i\s+correct|did\s+i\s+(get|understand))\b",
    "recall_de": r"\b(weißt\s+du\s+noch|weisst\s+du\s+noch|erinnerst\s+du\s+dich|letztes\s+mal)\b",
    "recall_en": r"\b(do\s+you\s+remember|recall|last\s+time)\b",
    "meta_de": r"\b(wurde\s+\w+\s+gemacht|hat\s+\w+\s+funktioniert|ist\s+\w+\s+durch)\b",
    "meta_en": r"\b(was\s+\w+\s+done|did\s+\w+\s+work|is\s+\w+\s+complete)\b",
}


# ---------------------------------------------------------------------------
# 4.3 Rejections — negations, preferences, ordering, exclusion
# ---------------------------------------------------------------------------

TRIGGER_PATTERNS_4_3 = {
    "negation_de": r"\b(nicht\s+\w+|kein(e|en|er|es)?\s+\w+|ohne\s+\w+|verzicht\s+auf)\b",
    "negation_en": r"\b(not\s+\w+|no\s+\w+|without\s+\w+|skip\s+the)\b",
    "preference_de": r"\b(lieber\s+\w+|stattdessen\s+\w+|besser\s+\w+|eher\s+\w+)\b",
    "preference_en": r"\b(rather\s+\w+|instead\s+of|prefer\s+\w+|better\s+\w+)\b",
    "ordering_de": r"\b(zuerst\s+\w+|bevor\s+\w+|erst\s+\w+\s+dann)\b",
    "ordering_en": r"\b(first\s+\w+\s+then|before\s+\w+|after\s+\w+\s+do)\b",
    "exclusion_de": r"\b(brauchen\s+wir\s+nicht|nicht\s+nötig|nicht\s+noetig)\b",
    "exclusion_en": r"\b(don'?t\s+need|not\s+needed|skip\s+that)\b",
}


# ---------------------------------------------------------------------------
# 4.4 Context References — extracted as separate categories with own regex
# ---------------------------------------------------------------------------

TRIGGER_PATTERNS_4_4 = {
    "abs_path": r"(?:^|\s)/(?:[\w\-\.]+/)+[\w\-\.]+",  # /path/to/file
    "rel_path": r"(?:[\w\-\.]+/)+[\w\-\.]+\.(?:md|py|sh|yaml|yml|json|toml|js|ts|tsx|sql)\b",
    "url": r"https?://[\w\-\.~:/?#@!$&'()*+,;=%]+",
    "ha_entity": r"\b(?:light|switch|sensor|binary_sensor|media_player|climate|cover|fan|automation|script|scene|input_boolean|input_text)\.[\w]+",
    "version_string": r"\bv\d+\.\d+(?:\.\d+)?(?:-[\w]+)?\b",  # v1.0.9, v2-beta
    "date_iso": r"\b\d{4}-\d{2}-\d{2}\b",
    "date_de_relative": r"\b(?:bis\s+(?:montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)|nächste(?:n|r)?\s+(?:woche|monat))\b",
    "money_eur": r"€\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?\s*(?:€|EUR|euro)",
    "pr_reference": r"#\d{1,5}\b",  # #270, #11
}

# Credentials/secrets - always FLAG when matched (security flag)
TRIGGER_PATTERNS_4_4_SECRETS = {
    "password_keyword": r"\b(?:passwort|password|passwd|pwd)\s*[:=]\s*\S+",
    "token_keyword": r"\b(?:token|api[_\-]?key|secret|bearer)\s*[:=]\s*\S+",
    "high_entropy": r"\b[A-Za-z0-9_\-]{32,}\b",  # heuristic: long random-looking string
}


# ---------------------------------------------------------------------------
# 4.5 Risks / Ambiguities — destructive ops, missing values, conflicts
# ---------------------------------------------------------------------------

TRIGGER_PATTERNS_4_5 = {
    "destructive_cli": r"\b(rm\s+-rf|git\s+(reset\s+--hard|push\s+--force|branch\s+-D)|drop\s+(table|database)|truncate)\b",
    # Note: dropped leading \b before alternation because --no-verify starts with non-word char,
    # which made \b fail to match at string-start. Each alternative is unique enough on its own.
    "skip_safety_de": r"(?:\bohne\s+tests?\b|--no-verify|\bdirekt\s+(?:auf\s+)?(?:production|prod|main)\b)",
    "skip_safety_en": r"\b(skip\s+(tests?|review|hooks)|force\s+merge|bypass\s+(check|hook))\b",
    "ambiguous_ref_de": r"\b(das\s+file|die\s+integration|das\s+ding|das\s+da)\b",  # "welches file?"
    "ambiguous_ref_en": r"\b(this\s+(file|thing|integration)|the\s+(thing|file)\s+(?!is|was|with))\b",
    "scope_creep_de": r"\b(und\s+dann\s+noch\s+kurz|nur\s+noch\s+kurz|nebenbei)\b",
    "scope_creep_en": r"\b(and\s+also|while\s+(you'?re|we'?re)\s+at\s+it|on\s+the\s+side)\b",
}


# ---------------------------------------------------------------------------
# 4.6 Future Work / Deferred Ideas
# ---------------------------------------------------------------------------

TRIGGER_PATTERNS_4_6 = {
    # 2026-05-01: Stefan-Sanity-Check fand 14x "backlog" in dimensions.py ohne backlog-Trigger.
    # Erweitert um explizite "in den backlog"-Phrasings die historisch in routing.py INTENTS waren
    # aber nicht in dimensions.py - das war eine Lücke zwischen den beiden Systemen.
    "deferral_de": r"\b(später|spaeter|irgendwann|nicht\s+jetzt|wenn\s+wir\s+(mal\s+)?zeit\s+haben|next\s+release|in\s+v\d|in\s+den\s+backlog|merk\s+(?:dir|das|vor)|speicher\w*\s+(?:als|in|den))\b",
    "deferral_en": r"\b(later|someday|not\s+(now|today)|for\s+now|next\s+release|down\s+the\s+road|add\s+to\s+(?:the\s+)?backlog|remember\s+to|save\s+(?:as|for))\b",
    "soft_suggestion_de": r"\b(wir\s+könnten|wir\s+koennten|wäre\s+(eine\s+)?idee|waere\s+(eine\s+)?idee|könnte\s+man|koennte\s+man)\b",
    "soft_suggestion_en": r"\b(we\s+could|would\s+be\s+nice|could\s+(give|be)\s+(an?\s+)?(option|nice)|might\s+want\s+to)\b",
    "inspiration_de": r"\b(als\s+inspiration|zum\s+vergleich|davon\s+lernen)\b",
    "inspiration_en": r"\b(for\s+inspiration|to\s+draw\s+from|look\s+at\s+this\s+(repo|for\s+ideas)|i\s+like\s+the\s+idea\s+of)\b",
    "speculation_de": r"\b(vielleicht|hätten\s+wir\s+zeit|haetten\s+wir\s+zeit|man\s+könnte|man\s+koennte)\b",
    "speculation_en": r"\b(maybe\s+we\s+(should|could)|perhaps\s+we|one\s+(could|might))\b",
}


# ---------------------------------------------------------------------------
# 4.7 Tentative-Action — eval-then-decide
# ---------------------------------------------------------------------------

# Stefan-confirmed 2026-04-29: "evtl mit Vorschlag, NICHT mit später" → distinguish from 4.6
TRIGGER_PATTERNS_4_7 = {
    "evtl_with_proposal_de": r"\b(eventuell|evtl|vielleicht)\b",  # combined with NOT-later check in parser
    "question_in_parens": r"\(\?\)",  # (?) anywhere
    "self_doubt_de": r"\b(rede\s+ich\s+bullshit|stimmt\s+das|ist\s+das\s+sinnvoll|gute\s+idee\?)\b",
    "self_doubt_en": r"\b(am\s+i\s+talking\s+nonsense|does\s+that\s+make\s+sense|is\s+this\s+a\s+good\s+idea)\b",
    "deep_dive_de": r"\b(deep\s+dive|tieferer\s+blick|genauere\s+betrachtung)\b",
    "deep_dive_en": r"\b(deep\s+dive|take\s+a\s+closer\s+look|investigate\s+(further|more))\b",
    "evaluate_de": r"\b(abwägen|abwaegen|prüfen|pruefen|überlegen|ueberlegen)\b",
    "evaluate_en": r"\b(evaluate|consider\s+whether|weigh\s+(the\s+)?(pros|options))\b",
    # Stefan-Korrektur 2026-05-02 (v2-Pattern aus commit 72366c0): "evtl X + (vorher prüfen)"
    # ist ein eigener Sub-Type "Conditional-Execute mit Pre-Check". Behavior:
    # Sanity-Check ausführen, GRÜN → inline-execute (kein BLOCKING-Stop), ROT → stop + erklären.
    # Vorher in stefan-input-grammar.md textuell hinterlegt, aber dimensions.py kannte das
    # Pattern nicht - der Klassifier konnte es nicht von simplem "evtl X" unterscheiden.
    # Beispiele: "evtl autoTMM aus (vorher prüfen ob schon off)" /
    # "vielleicht den table droppen (sanity check)" / "perhaps restart the service (verify first)".
    # Regex-Anker: Trigger-Wort + Klammer mit prüf/check/sanity/verify-Stem im selben Item.
    "conditional_pre_check_de": r"\b(eventuell|evtl|vielleicht)\b[^(]*\([^)]*?(?:prüf\w*|pruef\w*|check\w*|sanity|verifiz\w*|überprüf\w*|ueberprüf\w*)[^)]*\)",
    "conditional_pre_check_en": r"\b(maybe|perhaps|might)\b[^(]*\([^)]*?(?:check|verify|sanity[\s-]?check|pre[\s-]?check|first[\s-]?(?:check|verify))[^)]*\)",
}

# Eval-Type sub-classification (set in parser based on which patterns matched).
# Conditional-Execute (NEU 2026-05-02 voll verdrahtet): Pre-Check-Pattern matched →
# parser setzt eval_type="Conditional-Execute" + metadata pre_check_required=True.
# Agent reagiert: erst Pre-Check, GRÜN → execute, ROT → stop + erklären.
EVAL_TYPES = ["Deep-Dive", "Conditional-Execute", "Idea-Validation"]

# Scope sub-classification for 4.7 items (NEU 2026-04-30, Stefan-Korrektur).
# Stefan: "wenn der scope nicht zu groß ist soll es immer gleich geprüft / entschieden werden".
# Small-scope items are answered inline in the chat, NOT routed to BACKLOG ## Tentative.
# Large-scope items (deep-dive, multi-file eval, architecture decisions) still route to backlog.
TRIGGER_PATTERNS_4_7_SMALL_SCOPE = {
    "sanity_check_de": r"\b(sanity[\s-]?check|stimmt\s+das|ist\s+das\s+so\s+richtig|rede\s+ich\s+bullshit|ist\s+das\s+sinnvoll|gute\s+idee\?)\b",
    "sanity_check_en": r"\b(sanity[\s-]?check|is\s+that\s+(right|correct)|am\s+i\s+(right|correct)|does\s+that\s+(make|sound)\s+(sense|right))\b",
    "verstehen_de": r"\b(wie\s+funktioniert|verstehe\s+ich\s+das\s+richtig|kannst\s+du\s+(?:mir\s+)?erklär\w*)\b",
    "verstehen_en": r"\b(how\s+does\s+\w+\s+work|do\s+i\s+understand|can\s+you\s+explain)\b",
    "trailing_question_short": r"^.{1,80}\(\?\)\s*$",  # short statement with (?) at end - inline-resolvable
}



# Indicators that an eval is large-scope. Routing depends on context:
# - If the topic OVERLAPS with the current task/workspace → handle inline with agent/skill help
#   (Stefan-Korrektur 2026-05-01: "wenn es zur aktuellen Aufgabe passt, sollen auch solche
#   sachen gleich von einem oder mehreren Agenten / Skills geprüft werden")
# - If the topic is OFF-TOPIC or pure future-work → BACKLOG ## Tentative
# - Future improvement: scope-detection via DEPENDENCIES.md (DEPS-INIT-001)
TRIGGER_PATTERNS_4_7_LARGE_SCOPE = {
    "deep_dive_explicit": r"\b(deep\s+dive|tieferer\s+blick|genauere\s+untersuchung|gründliche?\s+analyse|gruendliche?\s+analyse)\b",
    "multi_file_implication": r"\b(refaktor\w*|umbau\w*|architektur\w+|durch\s+\w+\s+ersetz\w*|migration|umstellung)\b",
    "evaluate_alternatives": r"\b(abwägen\s+ob|abwaegen\s+ob|prüfen\s+ob\s+wir|pruefen\s+ob\s+wir|alternative\s+(zu|von))\b",
}


# ---------------------------------------------------------------------------
# 4.8 Implicit Followups / State-Mismatch Detection
# ---------------------------------------------------------------------------

TRIGGER_PATTERNS_4_8 = {
    "state_confirm_de": r"\b(ist\s+(schon\s+)?durch|ist\s+(schon\s+)?erledigt|ist\s+(jetzt\s+)?live|funktioniert|ist\s+gemerged|ist\s+deployed)\b",
    "state_confirm_en": r"\b(is\s+(already\s+)?done|is\s+(now\s+)?live|works\s+now|is\s+(merged|deployed|shipped))\b",
    # Allow 1-3 intermediate words between "habe" and the past-participle verb,
    # to catch "habe das X gemacht" and "habe die Datei verschoben" (article + noun) alike.
    # 2026-05-01 Stefan-Korrektur Turn 9: erweitert um git/dev-action past-participles
    # (gepullt, geclont, gepusht, ausgecheckt, gemerged, gerebased, deployed, gestartet).
    "action_past_de": r"\bhabe\s+(?:\w+\s+){0,3}(?:gemacht|umbenannt|verschoben|gelöscht|geloescht|geändert|geaendert|gepullt|geclont|gepusht|ausgecheckt|gemerged|gemerget|gerebased|deployed|gestartet|gestoppt|installiert|aktualisiert)\b",
    "action_past_en": r"\b(i\s+(?:have\s+)?(?:already\s+)?(renamed|moved|deleted|changed|updated|removed)\s+\w+)\b",
    "existence_negation_de": r"\b(\w+\s+gibt\s+es\s+nicht\s+mehr|\w+\s+ist\s+weg|\w+\s+existiert\s+nicht)\b",
    "existence_negation_en": r"\b(\w+\s+(?:is\s+)?gone|\w+\s+(?:is\s+)?no\s+longer\s+(exists?|there)|removed\s+\w+)\b",
    "rename_de": r"\b(\w+\s+heißt\s+jetzt\s+\w+|heisst\s+jetzt|wurde\s+zu\s+\w+|umbenannt\s+(in|zu)\s+\w+)\b",
    "rename_en": r"\b(\w+\s+is\s+now\s+called\s+\w+|renamed\s+(to|from)|formerly\s+known\s+as)\b",
}


# ---------------------------------------------------------------------------
# Workspace type detection (from Step 3)
# ---------------------------------------------------------------------------

# Ordered list: first match wins. Each entry = (path-fragment, workspace-type).
# Applied against the absolute workspace path string with trailing-slash normalization.
# Stefan-Decision 2026-05-01: "werde nur mit conductor arbeiten, generic als fallback".
# Detectors prefer conductor-Pfad-Strukturen (~/conductor/repos/<repo> oder
# ~/conductor/workspaces/<repo>/<workspace>/) plus structural fallbacks für PMB-Views
# und ha-config-Repos.
WORKSPACE_TYPE_DETECTORS = [
    # Conductor-Workspaces (primary detection):
    ("/conductor/repos/placemybooking/", "pmb"),
    ("/conductor/workspaces/placemybooking/", "pmb"),
    ("/conductor/repos/ha-playground/", "ha-playground"),
    ("/conductor/workspaces/ha-playground/", "ha-playground"),
    ("/conductor/repos/productivity/", "productivity"),
    ("/conductor/workspaces/productivity/", "productivity"),
    ("/conductor/repos/productivity-v1/", "productivity"),
    ("/conductor/workspaces/productivity-v1/", "productivity"),
    # Structural fallbacks (catch PMB/ha-playground content even if path convention changes):
    ("docs/software/ux-ui/views/", "pmb"),
    ("clients/yama/", "ha-playground"),
    ("clients/_leads/", "ha-playground"),
    # ha-live-config (separate from ha-playground - this is the actual HA install config):
    ("homechild", "ha-live-config"),
    ("yama-ha-config", "ha-live-config"),
    # Other conductor repos (claude-dotfiles, conductor-playground, audiocontrol2-work,
    # deskpilot, superpro-shutter-card) intentionally fall through to "generic" - they
    # don't have workspace-specific routing rules.
]

WORKSPACE_TYPE_DEFAULT = "generic"


# ---------------------------------------------------------------------------
# Tag mapping per workspace type
# ---------------------------------------------------------------------------

# PMB tags — keyword (case-insensitive substring) → view-tag
TAG_MAPPING_PMB = {
    "tisch": "settings/table-manager",
    "table": "settings/table-manager",
    "grundriss": "settings/table-manager",
    "floor plan": "settings/table-manager",
    "dnd": "settings/table-manager",
    "timeline": "dashboard/timeline",
    "zeitraster": "dashboard/timeline",
    "ghost row": "dashboard/timeline",
    "demo": "demo-setup",
    "demo-setup": "demo-setup",
    "demorestaurant": "demo-setup",
    "standort": "settings/locations",
    "location": "settings/locations",
    "multi-restaurant": "settings/locations",
    "dashboard": "dashboard",
    "reservierung": "dashboard",
    "hauptansicht": "dashboard",
    "commandbar": "dashboard/commandbar",
    "cmd+k": "dashboard/commandbar",
    "command palette": "dashboard/commandbar",
    "login": "login",
    "anmeldung": "login",
    "passwort": "login",
    "onboarding": "onboarding",
    "wizard": "onboarding",
    "gaestebuch": "settings/gaestebuch",
    "guest book": "settings/gaestebuch",
    "statistik": "settings/statistics",
    "analytics": "settings/statistics",
    "oeffnungszeiten": "settings/opening-hours",
    "opening hours": "settings/opening-hours",
    "theme": "settings/display-theme",
    "design": "settings/display-theme",
    "dark mode": "settings/display-theme",
    "branding": "settings/branding",
    "logo": "settings/branding",
    "user": "settings/users",
    "rolle": "settings/users",
    "permission": "settings/users",
    "billing": "settings/billing",
    "abo": "settings/billing",
    "trial": "settings/billing",
    "landingpage": "landingpage",
    "marketing": "landingpage",
    "booking": "public-booking",
    "public": "public-booking",
    "walk-in": "dashboard/walk-in",
    "laufkundschaft": "dashboard/walk-in",
    "kapazitaet": "dashboard/capacity-strip",
    "capacity": "dashboard/capacity-strip",
    "notification": "settings/notifications",
    "reservation-actions": "dashboard/reservation-actions",
    "popup": "dashboard/reservation-actions",
    "new-reservation": "dashboard/new-reservation",
    "nrm": "dashboard/new-reservation",
    "reservierungsliste": "dashboard/list",
    "reslist": "dashboard/list",
    "admin-surfaces": "admin-surfaces-2-0",
}

# ha-playground tags — keyword → tag
TAG_MAPPING_HA = {
    "yama": "yama",
    "chopan": "yama",
    "dashboard": "dashboard",
    "view": "dashboard",
    "integration": "integrations",
    "sonos": "integrations/sonos",
    "miele": "integrations/miele",
    "smartthings": "integrations/smartthings",
    "home_connect": "integrations/home_connect",
    "heos": "integrations/heos",
    "knx": "integrations/knx",
    "user": "users",
    "benutzer": "users",
    "login": "users",
    "passwort": "users",
    "automation": "automations",
    "szene": "automations",
    "scene": "automations",
    "device": "devices",
    "gerät": "devices",
    "geraet": "devices",
    "entity": "devices",
    "hacs": "frontend",
    "mushroom": "frontend",
    "bubble-card": "frontend",
    "backup": "operations",
    "snapshot": "operations",
    "recovery": "operations",
    "angebot": "business",
    "preis": "business",
    "kunde": "business",
}

DEFAULT_TAG = "unassigned"


# ---------------------------------------------------------------------------
# Format templates (Markdown heredoc-style strings for prompt-analysis output)
# ---------------------------------------------------------------------------

# 4.6 Future Work item template (used by the routing layer that writes to BACKLOG.md)
FORMAT_TEMPLATE_4_6 = """## {timestamp} - {title}

> "{verbatim_quote}"

**Was zu tun ist:** {action_hint}
**Status:** Future. **Quelle:** {source}.
"""

# 4.7 Tentative-Action item template
FORMAT_TEMPLATE_4_7 = """## {timestamp} - {title}

> "{verbatim_quote}"

**Eval-Type:** {eval_type}
**Was zu pruefen ist:** {evaluation_question}
**Action wenn positiv:** {action_if_positive}
**Action wenn negativ:** {action_if_negative}
**Status:** Tentative. **Quelle:** {source}.
"""

# 4.1 Generic backlog item (universal — used by ha-playground/generic backlog)
FORMAT_TEMPLATE_4_1_GENERIC = """## {timestamp} - {title}

> "{verbatim_quote}"

**Was zu tun ist:** {action_hint}
**Status:** Offen.
**Quelle:** {source}.
"""

# 4.1 ha-playground compact bullet (under ## Tomorrow)
FORMAT_TEMPLATE_4_1_HA = "- `[{tag}]` {title} - {description}. Quelle: {source}, {timestamp}.\n"


# ---------------------------------------------------------------------------
# Bullet patterns (NEU 2026-05-01 Stefan-Korrektur Turn 7)
# ---------------------------------------------------------------------------
# Stefan antwortet oft mit "NUMMER verbatim" auf nummerierte Listen vom Assistant -
# z.B. "4 ja, das ist eine gute idee" oder "3. nicht so" oder "5: noch ein punkt".
# extract_bullets() muss diese als gleichwertig zu - / * Bullets erkennen.

# Tool-output Detection (NEU 2026-05-01 Stefan-Korrektur Turn 9 Punkt 2):
# Stefan paste'd manchmal Command-Output in den Prompt. Diese Lines starten mit
# `[program-name]` plus content. Sollen NICHT als requirement klassifiziert werden,
# sondern als 4.4 Context-Reference (= Tool-Execution-Context).
# Beispiele:
#   [init-deps-update] workspace_type=ha-playground, repo=ha-playground
#   [parser-bench] runtime=42ms, classified=187 items
#   [git] On branch f17mkx/foo
TOOL_OUTPUT_PATTERN = r"^\[[\w\-_\.]+\]\s+.+$"


DASH_BULLET_PATTERN = r"^[-*]\s+(.+?)$"
# Numbered: "4 ", "4. ", "4: ", "4) " jeweils + content. Optional . : ) als Trenner.
NUMBERED_BULLET_PATTERN = r"^(\d+)[\.\:\)]?\s+(.+?)$"

# Multi-Number-Bullet (NEU 2026-05-01 Stefan-Korrektur Turn 8 Punkt 5):
# Stefan adressiert oft mehrere Antwort-Items gleichzeitig:
#   "5,6,7 ok"     (comma-separated)
#   "2-6 ok"       (range)
#   "4+5"          (plus-separated, no space)
#   "5 + 6"        (plus-separated with space)
# Pattern matched die Number-Group am Zeilenanfang plus den Content. Group 1 = number-spec
# (für späteres Parsing der Einzelnummern), Group 2 = content.
MULTI_NUMBERED_BULLET_PATTERN = r"^(\d+(?:\s*[,+\-]\s*\d+)+)[\.\:\)]?\s+(.+?)$"

# Kombi-Pattern für extract_bullets: matched DASH ODER MULTI_NUMBERED ODER NUMBERED.
# Reihenfolge wichtig: MULTI vor SINGLE damit "5,6,7 ok" als multi matched, nicht single "5".
# Capture-Group 1 = content (nicht number-spec - die wird von extract_bullet_numbers separat extrahiert).
ANY_BULLET_PATTERN = r"^(?:[-*]\s+|\d+(?:\s*[,+\-]\s*\d+)+[\.\:\)]?\s+|\d+[\.\:\)]?\s+)(.+?)$"


# ---------------------------------------------------------------------------
# Parenthetical inserts + dash-comments (NEU 2026-05-01 Stefan-Korrektur Turn 7)
# ---------------------------------------------------------------------------
# Stefan macht oft Einschübe in Klammern oder mit "-": "(also wie dieses hier)" oder
# "X - klarstellung dazu". Diese Einschübe haben verschiedene Sub-Types die für
# Konversations-Verständnis wichtig sind:
#
# - Clarification: "also", "z.B.", "i.e.", "siehe", "d.h."
# - Contrast:      "statt", "aber", "dagegen", "im Gegensatz"
# - Question-Insert: endet mit "?" innerhalb der Klammer
# - Self-Reference: "weißt schon", "you know", "sozusagen"
# - Note:          fallback wenn kein anderer Sub-Type matched

# Robust-Klammer-Regex: matched bis schließende Klammer ODER Zeilenende ODER nächstem
# Bullet-Marker. Berücksichtigt Stefan-Bemerkung: "ich kann mal eine klammer zu
# schließen vergessen". Nicht-greedy.
PARENTHETICAL_PATTERN = r"\(([^)]*?)(?:\)|$|\n[-*\d])"

# Dash-Comment: " - X" am Ende einer Phrase oder Zeile. Mind. 1 Space vor "-" um
# false-positives mit Bindestrich-Wörtern (z.B. "ha-playground") zu vermeiden.
DASH_COMMENT_PATTERN = r"\s+-\s+([^-\n]+?)(?=\s+-\s+|$|\n)"

PARENTHETICAL_TYPE_PATTERNS = {
    "clarification_de": r"\b(also|z\.?b\.?|i\.?e\.?|siehe|d\.?h\.?|nämlich|naemlich)\b",
    "clarification_en": r"\b(i\.?e\.?|e\.?g\.?|that\s+is|see|namely)\b",
    "contrast_de": r"\b(statt|aber|dagegen|im\s+gegensatz|nicht\s+(?:aber|sondern))\b",
    "contrast_en": r"\b(instead|but|whereas|in\s+contrast|not\s+(?:but|rather))\b",
    "self_reference_de": r"\b(weißt\s+schon|weisst\s+schon|sozusagen|verstehst|du\s+weißt)\b",
    "self_reference_en": r"\b(you\s+know|so\s+to\s+speak|kind\s+of)\b",
    # Question-Insert wird separat erkannt (per "?" am Ende des Klammer-Inhalts)
}


# ---------------------------------------------------------------------------
# Sub-Item Splitting innerhalb eines Bullets (NEU 2026-05-01 Stefan-Korrektur Turn 7)
# ---------------------------------------------------------------------------
# Ein Bullet kann mehrere Items enthalten:
# "4 ist gut so, ändere nur X, lass uns Y für später speichern, wenn nicht Z (?)"
# → splittet in 4 Sub-Items (1 confirm, 1 imperative, 1 defer, 1 conditional).
#
# Trigger sind Komma + Konjunktion ODER Komma + Imperativ-Stem. Konservativ - wir
# splitten nur an klaren Boundaries um false-positives ("ändere X, Y, und Z" als
# Liste-of-Args) zu vermeiden.

SUBITEM_SPLIT_PATTERNS = [
    r",\s+(?=lass\s+uns\b)",         # ", lass uns Y machen"
    r",\s+(?=lasst\s+uns\b)",        # ", lasst uns"
    r",\s+(?=aber\s+)",              # ", aber X"
    r",\s+(?=und\s+dann\s+)",        # ", und dann X"
    r",\s+(?=wenn\s+(?:nicht\s+|kein\s+)?\w)",  # ", wenn (nicht/kein) X"
    r",\s+(?=if\s+\w)",              # ", if X"
    # Komma + bekannte Imperativ-Stems (Auswahl der häufigsten):
    r",\s+(?=(?:ändere|aendere|änder|aender|entferne|entfern|schreib|mach|update|aktualisier|implementier|integrier|konfigurier|migrier|teste|deploy|push|merge)\w*\s)",
    r",\s+(?=(?:change|remove|write|make|implement|integrate|configure|migrate|test|push|merge)\s)",
]


# ---------------------------------------------------------------------------
# Sub-section names used in BACKLOG.md per workspace type (4.6 Future Work)
# ---------------------------------------------------------------------------

FUTURE_SECTION_PER_WORKSPACE = {
    "pmb": "## Future",
    "ha-playground": "## Someday",
    "ha-live-config": "## Ideas",
    "productivity": "## Ideas",
    "generic": "## Ideas",
}

# 4.7 Tentative section is universal across all workspace types
TENTATIVE_SECTION_NAME = "## Tentative"
