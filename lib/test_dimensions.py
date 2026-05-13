"""
Tests for lib/dimensions.py.

Covers:
- Constants are well-formed (DIMENSIONS list integrity, no duplicate IDs)
- Trigger-pattern regexes compile cleanly
- Sample Stefan-quotes (from session-log archives) match the expected dimension patterns
- Tag-mapping returns expected view-tags for representative keywords
- Format templates produce valid Markdown when filled with placeholder values

Run: python3 -m unittest lib/test_dimensions.py -v
"""

import re
import unittest
from pathlib import Path
import sys

# Allow importing as `from dimensions import ...` when run from repo root
sys.path.insert(0, str(Path(__file__).parent))

import dimensions as D


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------

class TestDimensionsStructure(unittest.TestCase):
    def test_dimensions_list_complete(self):
        self.assertEqual(len(D.DIMENSIONS), 8, "Expected 8 dimensions (4.1-4.8)")

    def test_dimension_ids_unique_and_ordered(self):
        ids = [d["id"] for d in D.DIMENSIONS]
        self.assertEqual(ids, ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8"])
        self.assertEqual(len(set(ids)), 8)

    def test_each_dimension_has_required_fields(self):
        for d in D.DIMENSIONS:
            self.assertIn("id", d)
            self.assertIn("title", d)
            self.assertIn("description", d)
            self.assertIn("routes_to_backlog", d)
            self.assertIsInstance(d["routes_to_backlog"], bool)

    def test_dimension_ids_constant_matches_list(self):
        self.assertEqual(D.DIMENSION_IDS, [d["id"] for d in D.DIMENSIONS])


# ---------------------------------------------------------------------------
# Pattern compilation — every regex must compile (no syntax errors)
# ---------------------------------------------------------------------------

class TestPatternsCompile(unittest.TestCase):
    def _check_pattern_dict(self, patterns, dim_label):
        for name, pat in patterns.items():
            try:
                re.compile(pat, re.IGNORECASE)
            except re.error as e:
                self.fail(f"{dim_label} pattern '{name}' failed to compile: {e}\nPattern: {pat}")

    def test_4_1_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_1, "4.1")

    def test_4_2_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_2, "4.2")

    def test_4_3_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_3, "4.3")

    def test_4_4_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_4, "4.4")

    def test_4_4_secrets_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_4_SECRETS, "4.4-secrets")

    def test_4_5_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_5, "4.5")

    def test_4_6_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_6, "4.6")

    def test_4_7_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_7, "4.7")

    def test_4_8_compiles(self):
        self._check_pattern_dict(D.TRIGGER_PATTERNS_4_8, "4.8")


# ---------------------------------------------------------------------------
# Sample-prompt matching — real Stefan quotes from session-log archives
# ---------------------------------------------------------------------------

def matches_any(text, pattern_dict):
    """Helper: return True if any pattern in dict matches text (case-insensitive)."""
    for pat in pattern_dict.values():
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


class Test4_1Requirements(unittest.TestCase):
    def test_imperative_de(self):
        self.assertTrue(matches_any("mach das mal", D.TRIGGER_PATTERNS_4_1))
        self.assertTrue(matches_any("schreib einen Test", D.TRIGGER_PATTERNS_4_1))
        self.assertTrue(matches_any("entferne die alte Funktion", D.TRIGGER_PATTERNS_4_1))

    def test_soll_phrasing(self):
        self.assertTrue(matches_any("X soll Y tun", D.TRIGGER_PATTERNS_4_1))
        self.assertTrue(matches_any("sollten wir nicht auch X einbauen?", D.TRIGGER_PATTERNS_4_1))

    def test_bug_descriptions(self):
        self.assertTrue(matches_any("das ist kaputt", D.TRIGGER_PATTERNS_4_1))
        self.assertTrue(matches_any("klappt nicht mit dem neuen Build", D.TRIGGER_PATTERNS_4_1))


class Test4_2Questions(unittest.TestCase):
    def test_terminal_question_mark(self):
        self.assertTrue(matches_any("was heißt das?", D.TRIGGER_PATTERNS_4_2))
        # Question mark inline catches it even with trailing whitespace
        self.assertTrue(matches_any("ist das so gemeint? ", D.TRIGGER_PATTERNS_4_2))

    def test_wh_words(self):
        self.assertTrue(matches_any("wie geht das", D.TRIGGER_PATTERNS_4_2))
        self.assertTrue(matches_any("warum nicht so", D.TRIGGER_PATTERNS_4_2))

    def test_recall_question(self):
        self.assertTrue(matches_any("weißt du noch wie das war", D.TRIGGER_PATTERNS_4_2))


class Test4_3Rejections(unittest.TestCase):
    def test_negation(self):
        self.assertTrue(matches_any("nicht Postgres", D.TRIGGER_PATTERNS_4_3))
        self.assertTrue(matches_any("ohne tests bitte nicht", D.TRIGGER_PATTERNS_4_3))

    def test_preference(self):
        self.assertTrue(matches_any("lieber MySQL", D.TRIGGER_PATTERNS_4_3))
        self.assertTrue(matches_any("stattdessen den Cache nehmen", D.TRIGGER_PATTERNS_4_3))


class Test4_4ContextRefs(unittest.TestCase):
    def test_path_extraction(self):
        m = re.search(D.TRIGGER_PATTERNS_4_4["abs_path"], "siehe /Users/admin/foo.md", re.IGNORECASE)
        self.assertIsNotNone(m)
        # rel_path requires a known extension
        m2 = re.search(D.TRIGGER_PATTERNS_4_4["rel_path"], "in commands/parse-prompt.md")
        self.assertIsNotNone(m2)

    def test_url(self):
        m = re.search(D.TRIGGER_PATTERNS_4_4["url"], "siehe https://github.com/f17mkx/parseprompt")
        self.assertIsNotNone(m)

    def test_ha_entity(self):
        m = re.search(D.TRIGGER_PATTERNS_4_4["ha_entity"], "schalte light.licht_kind_1 ein")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(0), "light.licht_kind_1")

    def test_iso_date(self):
        m = re.search(D.TRIGGER_PATTERNS_4_4["date_iso"], "deadline 2026-04-30")
        self.assertIsNotNone(m)

    def test_pr_reference(self):
        m = re.search(D.TRIGGER_PATTERNS_4_4["pr_reference"], "PR #270 ist offen")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(0), "#270")


class Test4_4Secrets(unittest.TestCase):
    def test_password_match(self):
        self.assertTrue(matches_any("passwort=hunter2", D.TRIGGER_PATTERNS_4_4_SECRETS))
        self.assertTrue(matches_any("password: secret123", D.TRIGGER_PATTERNS_4_4_SECRETS))

    def test_token_match(self):
        self.assertTrue(matches_any("api-key=ABC123XYZ", D.TRIGGER_PATTERNS_4_4_SECRETS))
        self.assertTrue(matches_any("bearer:xyz789", D.TRIGGER_PATTERNS_4_4_SECRETS))


class Test4_5RisksAmbiguities(unittest.TestCase):
    def test_destructive_cli(self):
        self.assertTrue(matches_any("rm -rf /tmp/foo", D.TRIGGER_PATTERNS_4_5))
        self.assertTrue(matches_any("git reset --hard origin/main", D.TRIGGER_PATTERNS_4_5))

    def test_skip_safety(self):
        self.assertTrue(matches_any("ohne tests merge das durch", D.TRIGGER_PATTERNS_4_5))
        self.assertTrue(matches_any("--no-verify einfach committen", D.TRIGGER_PATTERNS_4_5))


class Test4_6FutureWork(unittest.TestCase):
    def test_deferral_de(self):
        self.assertTrue(matches_any("später machen wir X", D.TRIGGER_PATTERNS_4_6))
        self.assertTrue(matches_any("irgendwann sollten wir Y", D.TRIGGER_PATTERNS_4_6))
        self.assertTrue(matches_any("wenn wir mal Zeit haben", D.TRIGGER_PATTERNS_4_6))

    def test_soft_suggestion(self):
        self.assertTrue(matches_any("wir könnten frame coloring machen", D.TRIGGER_PATTERNS_4_6))
        self.assertTrue(matches_any("would be nice to have X", D.TRIGGER_PATTERNS_4_6))

    def test_inspiration(self):
        self.assertTrue(matches_any("for inspiration: github.com/foo/bar", D.TRIGGER_PATTERNS_4_6))
        self.assertTrue(matches_any("look at this repo for ideas", D.TRIGGER_PATTERNS_4_6))


class Test4_7TentativeAction(unittest.TestCase):
    def test_evtl(self):
        self.assertTrue(matches_any("evtl docs cleanup machen", D.TRIGGER_PATTERNS_4_7))
        self.assertTrue(matches_any("eventuell könnten wir das so", D.TRIGGER_PATTERNS_4_7))

    def test_question_in_parens(self):
        self.assertTrue(matches_any("(?) macht das Sinn", D.TRIGGER_PATTERNS_4_7))
        self.assertTrue(matches_any("X dann (?)", D.TRIGGER_PATTERNS_4_7))

    def test_evaluate(self):
        self.assertTrue(matches_any("abwägen ob das geht", D.TRIGGER_PATTERNS_4_7))
        self.assertTrue(matches_any("deep dive in das Thema", D.TRIGGER_PATTERNS_4_7))

    def test_conditional_pre_check_de(self):
        # Stefan-v2-Pattern (2026-05-02): "evtl X + (vorher prüfen)" muss als 4.7 matchen
        # UND specific den conditional_pre_check_de pattern triggern. Verschiedene Wordings
        # die Stefan im Real-World gibt: prüf/check/sanity/verify, mit/ohne "vorher".
        self.assertTrue(matches_any(
            "evtl autoTMM ausschalten (vorher prüfen ob schon off)",
            D.TRIGGER_PATTERNS_4_7))
        self.assertTrue(matches_any(
            "vielleicht den table droppen (sanity check)",
            D.TRIGGER_PATTERNS_4_7))
        self.assertTrue(matches_any(
            "eventuell den service neu starten (kurz checken ob läuft)",
            D.TRIGGER_PATTERNS_4_7))
        # Specific pattern check - muss conditional_pre_check_de matchen, nicht nur evtl_with_proposal
        import re
        self.assertTrue(re.search(
            D.TRIGGER_PATTERNS_4_7["conditional_pre_check_de"],
            "evtl autoTMM aus (vorher prüfen)",
            re.IGNORECASE))

    def test_conditional_pre_check_en(self):
        self.assertTrue(matches_any(
            "perhaps restart the service (verify first)",
            D.TRIGGER_PATTERNS_4_7))
        self.assertTrue(matches_any(
            "maybe drop the table (sanity check)",
            D.TRIGGER_PATTERNS_4_7))

    def test_conditional_pre_check_NOT_matching_simple_evtl(self):
        # Negative-test: simples "evtl X" OHNE Klammer-mit-Pre-Check soll NICHT
        # conditional_pre_check matchen (nur evtl_with_proposal_de).
        import re
        text = "evtl docs cleanup machen"
        self.assertFalse(re.search(
            D.TRIGGER_PATTERNS_4_7["conditional_pre_check_de"], text, re.IGNORECASE))
        self.assertTrue(re.search(
            D.TRIGGER_PATTERNS_4_7["evtl_with_proposal_de"], text, re.IGNORECASE))


class Test4_7ScopeClassification(unittest.TestCase):
    """Stefan-Regel 2026-04-30: small-scope 4.7-items werden inline beantwortet,
    nicht in BACKLOG geschoben. Large-scope 4.7-items gehen ins ## Tentative."""

    def test_small_scope_sanity_check(self):
        self.assertTrue(matches_any("stimmt das so", D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE))
        self.assertTrue(matches_any("sanity check bitte", D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE))
        self.assertTrue(matches_any("ist das so richtig?", D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE))
        self.assertTrue(matches_any("rede ich bullshit?", D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE))

    def test_small_scope_understanding(self):
        self.assertTrue(matches_any("wie funktioniert das", D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE))
        self.assertTrue(matches_any("verstehe ich das richtig", D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE))
        self.assertTrue(matches_any("kannst du mir erklären", D.TRIGGER_PATTERNS_4_7_SMALL_SCOPE))

    def test_large_scope_deep_dive(self):
        self.assertTrue(matches_any("deep dive in das Modul", D.TRIGGER_PATTERNS_4_7_LARGE_SCOPE))
        self.assertTrue(matches_any("tieferer blick auf X", D.TRIGGER_PATTERNS_4_7_LARGE_SCOPE))

    def test_large_scope_refactor(self):
        self.assertTrue(matches_any("refaktor des routing-systems", D.TRIGGER_PATTERNS_4_7_LARGE_SCOPE))
        self.assertTrue(matches_any("migration auf neuen ansatz", D.TRIGGER_PATTERNS_4_7_LARGE_SCOPE))


class Test4_1NewImperatives(unittest.TestCase):
    """Corpus-pass 2026-04-30 fand 110+ unclassified quotes mit imperativen Verben
    die nicht in der Original-Liste waren. Diese Tests verifizieren die Erweiterung."""

    def test_new_de_imperatives(self):
        for verb in ("implementiere das", "starte den server", "dokumentiere die api",
                     "validier die config", "migrier die db", "konfigurier nginx",
                     "integriere sonos", "kopier den ordner", "restart hassio"):
            self.assertTrue(matches_any(verb, D.TRIGGER_PATTERNS_4_1),
                           f"Expected match for '{verb}' but got none")

    def test_new_en_imperatives(self):
        for verb in ("implement the api", "validate the config", "migrate the db",
                     "configure nginx", "integrate sonos", "test the script",
                     "deploy to staging", "rebase the branch"):
            self.assertTrue(matches_any(verb, D.TRIGGER_PATTERNS_4_1),
                           f"Expected match for '{verb}' but got none")


class Test4_8ImplicitFollowups(unittest.TestCase):
    def test_state_confirm(self):
        self.assertTrue(matches_any("X ist durch", D.TRIGGER_PATTERNS_4_8))
        self.assertTrue(matches_any("ist schon erledigt", D.TRIGGER_PATTERNS_4_8))
        self.assertTrue(matches_any("ist jetzt live", D.TRIGGER_PATTERNS_4_8))

    def test_action_past(self):
        self.assertTrue(matches_any("habe das umbenannt", D.TRIGGER_PATTERNS_4_8))
        self.assertTrue(matches_any("habe die Datei verschoben", D.TRIGGER_PATTERNS_4_8))

    def test_rename(self):
        self.assertTrue(matches_any("ha-playground heißt jetzt smarthome-playground", D.TRIGGER_PATTERNS_4_8))


# ---------------------------------------------------------------------------
# Tag mapping tests
# ---------------------------------------------------------------------------

class TestTagMappingPMB(unittest.TestCase):
    def test_dashboard_keyword(self):
        self.assertEqual(D.TAG_MAPPING_PMB.get("dashboard"), "dashboard")

    def test_table_manager_keywords(self):
        self.assertEqual(D.TAG_MAPPING_PMB["tisch"], "settings/table-manager")
        self.assertEqual(D.TAG_MAPPING_PMB["table"], "settings/table-manager")
        self.assertEqual(D.TAG_MAPPING_PMB["grundriss"], "settings/table-manager")

    def test_login(self):
        self.assertEqual(D.TAG_MAPPING_PMB["login"], "login")
        self.assertEqual(D.TAG_MAPPING_PMB["passwort"], "login")


class TestTagMappingHA(unittest.TestCase):
    def test_yama_chopan_share_tag(self):
        self.assertEqual(D.TAG_MAPPING_HA["yama"], "yama")
        self.assertEqual(D.TAG_MAPPING_HA["chopan"], "yama")

    def test_integrations(self):
        self.assertEqual(D.TAG_MAPPING_HA["sonos"], "integrations/sonos")
        self.assertEqual(D.TAG_MAPPING_HA["knx"], "integrations/knx")


# ---------------------------------------------------------------------------
# Workspace detection
# ---------------------------------------------------------------------------

class TestWorkspaceDetectors(unittest.TestCase):
    def test_detectors_ordered_list(self):
        self.assertIsInstance(D.WORKSPACE_TYPE_DETECTORS, list)
        for entry in D.WORKSPACE_TYPE_DETECTORS:
            self.assertEqual(len(entry), 2, f"each detector must be (path-fragment, type) tuple, got: {entry}")

    def test_default_is_generic(self):
        self.assertEqual(D.WORKSPACE_TYPE_DEFAULT, "generic")


# ---------------------------------------------------------------------------
# Format templates
# ---------------------------------------------------------------------------

class TestFormatTemplates(unittest.TestCase):
    def test_4_6_template_format(self):
        rendered = D.FORMAT_TEMPLATE_4_6.format(
            timestamp="2026-04-30 18:35 CEST",
            title="Frame Coloring",
            verbatim_quote="wir könnten frame coloring machen",
            action_hint="TBD",
            source="user-prompt",
        )
        self.assertIn("Frame Coloring", rendered)
        self.assertIn("**Status:** Future", rendered)
        self.assertIn("> \"wir könnten", rendered)

    def test_4_7_template_format(self):
        rendered = D.FORMAT_TEMPLATE_4_7.format(
            timestamp="2026-04-30 18:35 CEST",
            title="Docs Cleanup",
            verbatim_quote="evtl docs cleanup machen",
            eval_type="Conditional-Execute",
            evaluation_question="Lohnt sich das?",
            action_if_positive="machen",
            action_if_negative="droppen",
            source="user-prompt",
        )
        self.assertIn("**Eval-Type:** Conditional-Execute", rendered)
        self.assertIn("**Status:** Tentative", rendered)

    def test_4_1_ha_compact_template(self):
        rendered = D.FORMAT_TEMPLATE_4_1_HA.format(
            tag="yama",
            title="Sonos Setup",
            description="Sonos Beam in Wohnzimmer integrieren",
            source="user-prompt",
            timestamp="2026-04-30",
        )
        self.assertTrue(rendered.startswith("- `[yama]`"))
        self.assertTrue(rendered.endswith("\n"))


# ---------------------------------------------------------------------------
# Section-name maps
# ---------------------------------------------------------------------------

class TestSectionNames(unittest.TestCase):
    def test_future_section_per_workspace_complete(self):
        for ws in ("pmb", "ha-playground", "ha-live-config", "productivity", "generic"):
            self.assertIn(ws, D.FUTURE_SECTION_PER_WORKSPACE)

    def test_tentative_universal(self):
        self.assertEqual(D.TENTATIVE_SECTION_NAME, "## Tentative")


if __name__ == "__main__":
    unittest.main(verbosity=2)
