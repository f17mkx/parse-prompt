"""
Tests for lib/parser.py.

Covers:
- classify() public API: each dimension produces expected Items
- Multi-dimension hits (single text → multiple Items)
- Bullet-extraction integration
- Workspace type detection (each path-fragment → correct type)
- Security flag detection (severity assignment)
- _resolve_4_6_vs_4_7() precedence rules (Stefan-Decision-Tree)
- _classify_4_7_eval_type() sub-classification
- _is_4_7_small_scope() heuristic
- _generate_title() truncation
- Regression: real Stefan-prompts from session-log archives

Run: python3 -m unittest lib/test_parser.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import parser as P
from parser import Item, SecurityFlag


# ---------------------------------------------------------------------------
# Public API: classify()
# ---------------------------------------------------------------------------

class TestClassifyBasic(unittest.TestCase):
    def test_returns_dict_with_all_8_dims(self):
        result = P.classify("test")
        self.assertEqual(set(result.keys()),
                         {"4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8"})

    def test_empty_prompt_returns_empty_lists(self):
        result = P.classify("")
        for items in result.values():
            self.assertEqual(items, [])

    def test_4_1_imperative_match(self):
        result = P.classify("shippe das mal")
        self.assertEqual(len(result["4.1"]), 1)
        self.assertEqual(result["4.1"][0].verbatim, "shippe das mal")
        self.assertIn("matched_pattern", result["4.1"][0].metadata)

    def test_4_2_question_match(self):
        result = P.classify("wie geht das?")
        self.assertEqual(len(result["4.2"]), 1)
        self.assertEqual(result["4.2"][0].dimension, "4.2")

    def test_4_3_rejection_match(self):
        result = P.classify("nicht Postgres bitte")
        self.assertGreaterEqual(len(result["4.3"]), 1)

    def test_4_5_destructive_match(self):
        result = P.classify("rm -rf /tmp/foo")
        self.assertEqual(len(result["4.5"]), 1)


class TestClassifyMultiDim(unittest.TestCase):
    def test_single_text_lands_in_multiple_dims(self):
        # "shippe das spaeter" → 4.1 (imperative) + 4.6 (deferral)
        result = P.classify("shippe das spaeter")
        self.assertEqual(len(result["4.1"]), 1, "should match 4.1 imperative")
        self.assertEqual(len(result["4.6"]), 1, "should match 4.6 deferral")

    def test_imperative_with_path_hits_4_1_and_4_4(self):
        # "shippe /tmp/foo.md" → 4.1 (imperative) + 4.4 (path ref)
        result = P.classify("shippe /tmp/foo.md")
        self.assertGreaterEqual(len(result["4.1"]), 1)
        self.assertGreaterEqual(len(result["4.4"]), 1)


class TestClassifyBullets(unittest.TestCase):
    def test_multi_line_bullets_each_classified(self):
        prompt = """- shippe das
- wie geht das?
- nicht Postgres"""
        result = P.classify(prompt)
        self.assertEqual(len(result["4.1"]), 1, "first bullet → 4.1")
        self.assertEqual(len(result["4.2"]), 1, "second bullet → 4.2")
        self.assertEqual(len(result["4.3"]), 1, "third bullet → 4.3")

    def test_no_bullets_treats_full_text_as_one_item(self):
        prompt = "shippe das jetzt"
        result = P.classify(prompt)
        self.assertEqual(len(result["4.1"]), 1)
        self.assertEqual(result["4.1"][0].verbatim, "shippe das jetzt")

    def test_mixed_bullets_and_prose_extracts_only_bullets(self):
        # extract_bullets() returns only bullet lines; prose paragraphs are skipped.
        # This is per design (skill markdown says "each item is a bullet").
        prompt = """Intro text without bullet.
- shippe das
- aktualisiere config"""
        result = P.classify(prompt)
        # Two bullet items, each should hit 4.1 imperative
        self.assertEqual(len(result["4.1"]), 2)


# ---------------------------------------------------------------------------
# extract_bullets()
# ---------------------------------------------------------------------------

class TestExtractBullets(unittest.TestCase):
    def test_dash_bullets(self):
        bullets = P.extract_bullets("- a\n- b\n- c")
        self.assertEqual(bullets, ["a", "b", "c"])

    def test_asterisk_bullets(self):
        bullets = P.extract_bullets("* x\n* y")
        self.assertEqual(bullets, ["x", "y"])

    def test_no_bullets_returns_empty(self):
        self.assertEqual(P.extract_bullets("just prose"), [])

    def test_strip_whitespace(self):
        bullets = P.extract_bullets("- spaced text   ")
        self.assertEqual(bullets, ["spaced text"])

    def test_mixed_with_prose_lines(self):
        bullets = P.extract_bullets("intro\n- bullet1\nmid\n- bullet2")
        self.assertEqual(bullets, ["bullet1", "bullet2"])


# ---------------------------------------------------------------------------
# detect_workspace_type()
# ---------------------------------------------------------------------------

class TestDetectWorkspaceType(unittest.TestCase):
    def test_pmb_detection(self):
        path = Path("/Users/admin/conductor/repos/placemybooking/docs/software/ux-ui/views/")
        self.assertEqual(P.detect_workspace_type(path), "pmb")

    def test_ha_playground_yama(self):
        path = Path("/some/repo/clients/yama/")
        self.assertEqual(P.detect_workspace_type(path), "ha-playground")

    def test_ha_playground_leads(self):
        path = Path("/some/repo/clients/_leads/")
        self.assertEqual(P.detect_workspace_type(path), "ha-playground")

    def test_ha_live_config_homechild(self):
        path = Path("/some/path/homechild/config/")
        self.assertEqual(P.detect_workspace_type(path), "ha-live-config")

    def test_default_generic(self):
        path = Path("/random/repo/")
        self.assertEqual(P.detect_workspace_type(path), "generic")


# ---------------------------------------------------------------------------
# detect_security_flags()
# ---------------------------------------------------------------------------

class TestDetectSecurityFlags(unittest.TestCase):
    def test_password_block_severity(self):
        flags = P.detect_security_flags("passwort=hunter2")
        self.assertGreaterEqual(len(flags), 1)
        block_flags = [f for f in flags if f.severity == "block"]
        self.assertGreaterEqual(len(block_flags), 1)

    def test_token_block_severity(self):
        flags = P.detect_security_flags("api-key=ABC123XYZ")
        block_flags = [f for f in flags if f.severity == "block"]
        self.assertGreaterEqual(len(block_flags), 1)

    def test_high_entropy_warn_severity(self):
        # 32+ char alphanumeric string but no key= prefix → just "warn"
        flags = P.detect_security_flags("ein langer string xyzABC1234567890DEFghi456789012MNopQr")
        warn_only = [f for f in flags if f.severity == "warn"]
        self.assertGreaterEqual(len(warn_only), 1)

    def test_no_secrets_returns_empty(self):
        flags = P.detect_security_flags("normal prompt without secrets")
        block_flags = [f for f in flags if f.severity == "block"]
        self.assertEqual(len(block_flags), 0)

    def test_matched_text_preserved_verbatim(self):
        # Security policy: matched text is NOT redacted in the flag itself
        flags = P.detect_security_flags("password: secret123abc")
        self.assertTrue(any("secret123abc" in f.matched_text for f in flags))


# ---------------------------------------------------------------------------
# 4.6 vs 4.7 precedence resolution
# ---------------------------------------------------------------------------

class TestResolve4_6_vs_4_7(unittest.TestCase):
    def test_evtl_with_spaeter_resolves_to_4_6(self):
        # "evtl machen wir das spaeter" → 4.6 (deferral semantics dominate)
        self.assertEqual(P._resolve_4_6_vs_4_7("evtl machen wir das spaeter"), "4.6")

    def test_evtl_without_deferral_resolves_to_4_7(self):
        # "evtl docs cleanup machen" → 4.7 (eval-then-decide)
        self.assertEqual(P._resolve_4_6_vs_4_7("evtl docs cleanup machen"), "4.7")

    def test_pure_4_6_deferral(self):
        self.assertEqual(P._resolve_4_6_vs_4_7("spaeter machen wir X"), "4.6")

    def test_pure_4_7_eval(self):
        self.assertEqual(P._resolve_4_6_vs_4_7("deep dive in das modul"), "4.7")

    def test_neither_returns_none(self):
        self.assertIsNone(P._resolve_4_6_vs_4_7("normaler text ohne trigger"))

    def test_classify_evtl_spaeter_lands_in_4_6_not_4_7(self):
        result = P.classify("evtl machen wir das spaeter")
        self.assertEqual(len(result["4.6"]), 1)
        self.assertEqual(len(result["4.7"]), 0)

    def test_classify_evtl_alone_lands_in_4_7_not_4_6(self):
        result = P.classify("evtl docs cleanup machen")
        self.assertEqual(len(result["4.7"]), 1)
        self.assertEqual(len(result["4.6"]), 0)


# ---------------------------------------------------------------------------
# 4.7 eval-type sub-classification
# ---------------------------------------------------------------------------

class TestClassify4_7EvalType(unittest.TestCase):
    def test_self_doubt_de_idea_validation(self):
        self.assertEqual(P._classify_4_7_eval_type("rede ich bullshit?"), "Idea-Validation")
        self.assertEqual(P._classify_4_7_eval_type("stimmt das so?"), "Idea-Validation")

    def test_conditional_execute(self):
        self.assertEqual(P._classify_4_7_eval_type("X machen wenn gute idee"),
                         "Conditional-Execute")

    def test_conditional_execute_v2_pre_check_de(self):
        # Stefan-v2-Pattern 2026-05-02: "evtl + (vorher prüfen)" → Conditional-Execute,
        # nicht Deep-Dive (vorher wurde das als Deep-Dive klassifiziert weil das Pattern
        # nicht differenzierte).
        self.assertEqual(
            P._classify_4_7_eval_type("evtl autoTMM ausschalten (vorher prüfen ob off)"),
            "Conditional-Execute")
        self.assertEqual(
            P._classify_4_7_eval_type("vielleicht den service restarten (sanity check)"),
            "Conditional-Execute")

    def test_conditional_execute_v2_pre_check_en(self):
        self.assertEqual(
            P._classify_4_7_eval_type("perhaps restart the service (verify first)"),
            "Conditional-Execute")

    def test_default_deep_dive(self):
        self.assertEqual(P._classify_4_7_eval_type("deep dive in routing"), "Deep-Dive")
        self.assertEqual(P._classify_4_7_eval_type("evtl X machen"), "Deep-Dive")


# ---------------------------------------------------------------------------
# 4.7 small-scope heuristic
# ---------------------------------------------------------------------------

class TestIs4_7SmallScope(unittest.TestCase):
    def test_sanity_check_is_small(self):
        self.assertTrue(P._is_4_7_small_scope("stimmt das so?"))
        self.assertTrue(P._is_4_7_small_scope("sanity check bitte"))

    def test_understanding_is_small(self):
        self.assertTrue(P._is_4_7_small_scope("wie funktioniert das"))

    def test_deep_dive_is_large(self):
        self.assertFalse(P._is_4_7_small_scope("deep dive in das routing-system und mehrere files anschauen"))

    def test_refactor_is_large(self):
        self.assertFalse(P._is_4_7_small_scope("refaktor des routing-systems aus mehreren angles bewerten"))

    def test_short_text_without_large_trigger_is_small(self):
        # No explicit large-trigger, short text → small (default for ambiguous short)
        self.assertTrue(P._is_4_7_small_scope("kurzer text"))

    def test_classify_assigns_scope_metadata(self):
        result = P.classify("evtl docs cleanup machen")
        self.assertEqual(len(result["4.7"]), 1)
        self.assertIn("scope", result["4.7"][0].metadata)

    def test_v2_pre_check_assigns_pre_check_required_metadata(self):
        # Stefan-v2-Pattern 2026-05-02 end-to-end: classifier muss sowohl
        # eval_type=Conditional-Execute als auch pre_check_required=True UND
        # recommended_action setzen, damit der Agent das Verhalten herleiten kann.
        result = P.classify("evtl autoTMM aus (vorher prüfen ob off)")
        self.assertEqual(len(result["4.7"]), 1)
        item = result["4.7"][0]
        self.assertEqual(item.metadata["eval_type"], "Conditional-Execute")
        self.assertEqual(item.metadata["scope"], "small",
                         "v2 pre-check pattern soll small-scope sein für inline-execute")
        self.assertTrue(item.metadata.get("pre_check_required"),
                        "pre_check_required Flag fehlt - Agent kann v2-Verhalten nicht herleiten")
        self.assertIn("pre-check", item.metadata.get("recommended_action", "").lower())


# ---------------------------------------------------------------------------
# _generate_title()
# ---------------------------------------------------------------------------

class TestGenerateTitle(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(P._generate_title("short title"), "short title")

    def test_long_text_truncated(self):
        long_text = "a" * 100
        title = P._generate_title(long_text, max_len=60)
        self.assertTrue(title.endswith("..."))
        self.assertLessEqual(len(title), 65)  # 60 chars + "..." + safety margin

    def test_word_boundary_trim(self):
        text = "this is a longer sentence that should trim cleanly at word boundary"
        title = P._generate_title(text, max_len=30)
        # Should not chop a word in half
        self.assertFalse(title.replace("...", "").endswith(" "))


# ---------------------------------------------------------------------------
# Regression: real Stefan-prompts from session-log archives
# ---------------------------------------------------------------------------

class TestRegressionRealPrompts(unittest.TestCase):
    """Sample real Stefan-prompts that previously caused drops or mis-classifications."""

    def test_frame_coloring_drop_4_6(self):
        # 2026-04-28 Frame-Coloring leak: "wir koennten frame coloring machen"
        # Should now be caught as 4.6 Future Work.
        result = P.classify("wir koennten frame coloring machen")
        self.assertGreaterEqual(len(result["4.6"]), 1)

    def test_evtl_corpus_pattern(self):
        # 2026-04-29 Stefan-Korrektur: "evtl mit Vorschlag, NICHT mit später" → 4.7
        result = P.classify("evtl docs cleanup machen")
        self.assertEqual(len(result["4.7"]), 1)
        self.assertEqual(result["4.7"][0].metadata["scope"], "small")

    def test_implementiere_corpus_imperative(self):
        # 2026-04-30 corpus-pass added "implementiere" — verify classify catches it
        result = P.classify("implementiere ADR-0002")
        self.assertGreaterEqual(len(result["4.1"]), 1)

    def test_sanity_check_inline_classification(self):
        # 2026-04-30 4.7-small-scope rule: "stimmt das?" should be small-scope
        result = P.classify("stimmt das so?")
        self.assertEqual(len(result["4.7"]), 1)
        self.assertEqual(result["4.7"][0].metadata["scope"], "small")
        self.assertEqual(result["4.7"][0].metadata["eval_type"], "Idea-Validation")

    def test_state_change_4_8(self):
        # 2026-04-29 Stefan-Beispiel: "X ist durch?!" → 4.8 implicit followup
        result = P.classify("ha-playground ist schon durch")
        self.assertEqual(len(result["4.8"]), 1)


class TestExtractBulletsNumbered(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 3: numbered bullets erkennen."""

    def test_number_with_space(self):
        bullets = P.extract_bullets("4 ja das ist eine gute idee")
        self.assertEqual(bullets, ["ja das ist eine gute idee"])

    def test_number_with_dot(self):
        bullets = P.extract_bullets("3. nicht so")
        self.assertEqual(bullets, ["nicht so"])

    def test_number_with_colon(self):
        bullets = P.extract_bullets("5: noch ein punkt")
        self.assertEqual(bullets, ["noch ein punkt"])

    def test_number_with_paren(self):
        bullets = P.extract_bullets("2) ja")
        self.assertEqual(bullets, ["ja"])

    def test_mixed_dash_and_numbered(self):
        text = "- erstes\n4 viertes\n* drittes"
        bullets = P.extract_bullets(text)
        self.assertEqual(bullets, ["erstes", "viertes", "drittes"])

    def test_numbered_multi_line(self):
        text = "1. erster punkt\n2. zweiter punkt\n3 dritter"
        bullets = P.extract_bullets(text)
        self.assertEqual(bullets, ["erster punkt", "zweiter punkt", "dritter"])


class TestExtractParentheticalInserts(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 5."""

    def test_basic_clarification(self):
        inserts = P.extract_parenthetical_inserts("X (also wie dieses hier)")
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0].text, "also wie dieses hier")
        self.assertEqual(inserts[0].insert_type, "Clarification")
        self.assertTrue(inserts[0].closed)

    def test_question_insert(self):
        inserts = P.extract_parenthetical_inserts("X (macht das Sinn?)")
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0].insert_type, "Question-Insert")

    def test_self_reference(self):
        inserts = P.extract_parenthetical_inserts("X (weißt schon wie ich meine)")
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0].insert_type, "Self-Reference")

    def test_contrast(self):
        inserts = P.extract_parenthetical_inserts("X (statt Y)")
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0].insert_type, "Contrast")

    def test_unmatched_paren_until_newline(self):
        # Stefan vergisst die schließende Klammer
        text = "X (also dieser einschub ohne ende\nNeue Zeile"
        inserts = P.extract_parenthetical_inserts(text)
        self.assertGreaterEqual(len(inserts), 1)
        self.assertFalse(inserts[0].closed, "should mark as not-closed")

    def test_multiple_inserts(self):
        text = "X (also dies) und Y (statt Z)"
        inserts = P.extract_parenthetical_inserts(text)
        self.assertEqual(len(inserts), 2)
        self.assertEqual(inserts[0].insert_type, "Clarification")
        self.assertEqual(inserts[1].insert_type, "Contrast")

    def test_empty_parens_skipped(self):
        inserts = P.extract_parenthetical_inserts("X () Y")
        self.assertEqual(len(inserts), 0)


class TestExtractDashComments(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 5."""

    def test_basic_dash_comment(self):
        comments = P.extract_dash_comments("X - klarstellung dazu")
        self.assertGreaterEqual(len(comments), 1)

    def test_hyphenated_word_not_matched(self):
        # "ha-playground" hat keinen Space vor "-", soll nicht matchen
        comments = P.extract_dash_comments("ha-playground ist okay")
        self.assertEqual(len(comments), 0)

    def test_dash_with_contrast(self):
        comments = P.extract_dash_comments("nehme A - aber B wäre besser")
        self.assertGreaterEqual(len(comments), 1)
        # Type sollte "Contrast" sein wegen "aber"
        self.assertEqual(comments[0].insert_type, "Contrast")


class TestSplitIntoSubitems(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 6."""

    def test_stefan_example_4_subitems(self):
        # Stefan's exact Beispiel
        text = "4 ist gut so, ändere nur X, lass uns Y für später speichern, wenn nicht Z"
        subs = P.split_into_subitems(text)
        self.assertEqual(len(subs), 4)
        self.assertIn("4 ist gut so", subs[0])
        self.assertIn("ändere nur X", subs[1])
        self.assertIn("lass uns Y", subs[2])
        self.assertIn("wenn nicht Z", subs[3])

    def test_no_split_for_simple_list(self):
        # "ändere X, Y, und Z" ist eine Liste-of-Args, KEIN Split
        text = "ändere X, Y, und Z"
        subs = P.split_into_subitems(text)
        self.assertEqual(len(subs), 1)

    def test_split_at_aber(self):
        text = "X machen, aber Y vorher checken"
        subs = P.split_into_subitems(text)
        self.assertEqual(len(subs), 2)

    def test_empty_input(self):
        self.assertEqual(P.split_into_subitems(""), [])

    def test_single_item_no_conjunction(self):
        text = "shippe das"
        subs = P.split_into_subitems(text)
        self.assertEqual(subs, ["shippe das"])


class TestDetectReferencedWorkspaces(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 7 Punkt 2: multi-path workspace detection."""

    def test_two_workspaces_referenced(self):
        text = ("siehe /Users/admin/conductor/workspaces/claude-dotfiles/task-tripwire/foo.py "
                "und /Users/admin/conductor/workspaces/ha-playground/minnetonka-v3/README.md")
        result = P.detect_referenced_workspaces(text)
        types = [t for t, _ in result]
        # claude-dotfiles fällt auf "generic" zurück (nicht in conductor-pmb-Liste),
        # ha-playground ist eigene type. Beide sollten erkannt werden.
        self.assertIn("ha-playground", types)

    def test_pmb_path_detected(self):
        text = "fix /Users/admin/conductor/workspaces/placemybooking/foo/bar.py"
        result = P.detect_referenced_workspaces(text)
        types = [t for t, _ in result]
        self.assertIn("pmb", types)

    def test_no_paths_returns_empty(self):
        result = P.detect_referenced_workspaces("just text without paths")
        self.assertEqual(result, [])

    def test_dominant_first(self):
        text = ("/Users/admin/conductor/workspaces/ha-playground/x/foo.py "
                "/Users/admin/conductor/workspaces/ha-playground/y/bar.py "
                "/Users/admin/conductor/workspaces/placemybooking/z/baz.py")
        result = P.detect_referenced_workspaces(text)
        # ha-playground sollte 2x, pmb 1x → ha-playground dominant
        self.assertEqual(result[0][0], "ha-playground")
        self.assertEqual(result[0][1], 2)


class TestConductorWorkspaceDetectors(unittest.TestCase):
    """Stefan-Decision 2026-05-01: nur conductor-Repos, generic als fallback."""

    def test_conductor_pmb_repo(self):
        path = Path("/Users/admin/conductor/repos/placemybooking/")
        self.assertEqual(P.detect_workspace_type(path), "pmb")

    def test_conductor_pmb_workspace(self):
        path = Path("/Users/admin/conductor/workspaces/placemybooking/munich-v2/")
        self.assertEqual(P.detect_workspace_type(path), "pmb")

    def test_conductor_ha_playground(self):
        path = Path("/Users/admin/conductor/workspaces/ha-playground/minnetonka-v3/")
        self.assertEqual(P.detect_workspace_type(path), "ha-playground")

    def test_conductor_productivity_v1(self):
        path = Path("/Users/admin/conductor/repos/productivity-v1/")
        self.assertEqual(P.detect_workspace_type(path), "productivity")

    def test_conductor_claude_dotfiles_is_generic(self):
        # Stefan-Decision: claude-dotfiles ist "generic" (kein eigener type)
        path = Path("/Users/admin/conductor/workspaces/claude-dotfiles/porto/")
        self.assertEqual(P.detect_workspace_type(path), "generic")


class TestMultiNumberBullets(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 8 Punkt 5: '5,6,7 ok' / '2-6 ok' / '4+5'."""

    def test_comma_separated(self):
        bullets = P.extract_bullets("5,6,7 ok")
        self.assertEqual(bullets, ["ok"])

    def test_plus_separated_no_space(self):
        bullets = P.extract_bullets("4+5 funktioniert")
        self.assertEqual(bullets, ["funktioniert"])

    def test_plus_separated_with_space(self):
        bullets = P.extract_bullets("5 + 6 sind ok")
        self.assertEqual(bullets, ["sind ok"])

    def test_range(self):
        bullets = P.extract_bullets("2-6 ok")
        self.assertEqual(bullets, ["ok"])

    def test_extract_bullet_numbers_comma(self):
        self.assertEqual(P.extract_bullet_numbers("5,6,7"), [5, 6, 7])

    def test_extract_bullet_numbers_plus(self):
        self.assertEqual(P.extract_bullet_numbers("4 + 5"), [4, 5])

    def test_extract_bullet_numbers_range(self):
        self.assertEqual(P.extract_bullet_numbers("2-6"), [2, 3, 4, 5, 6])

    def test_extract_bullet_numbers_single(self):
        self.assertEqual(P.extract_bullet_numbers("4"), [4])

    def test_extract_bullet_numbers_no_numbers(self):
        self.assertEqual(P.extract_bullet_numbers("- foo"), [])


class TestConfirmAcknowledge(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 8 Punkt 6: Confirm-Acknowledge als 4.1-Pattern."""

    def test_ist_gut_so(self):
        result = P.classify("ist gut so")
        self.assertEqual(len(result["4.1"]), 1)
        self.assertEqual(result["4.1"][0].metadata["matched_pattern"], "confirm_ack_de")

    def test_passt_so(self):
        result = P.classify("passt so")
        self.assertEqual(len(result["4.1"]), 1)

    def test_go_ahead(self):
        result = P.classify("go ahead")
        self.assertEqual(len(result["4.1"]), 1)

    def test_machs(self):
        result = P.classify("machs")
        self.assertGreaterEqual(len(result["4.1"]), 1)

    def test_stefan_4_ist_gut_so_subitem(self):
        # Stefan-Beispiel aus Turn 7: "4 ist gut so" als ein Sub-Item
        # nach split_into_subitems müsste dieser confirm_ack_de matchen
        result = P.classify("4 ist gut so")
        # Confirm-ack matched
        self.assertGreaterEqual(len(result["4.1"]), 1)


class TestConditionalDeferQuestion(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 9 Punkt 1: 4.6 + 4.7 simultaneous matching."""

    def test_hard_block_for_later_question(self):
        # Stefan-Beispiel verbatim
        text = "hard block für später, weil wir ja grad noch die dependencies testen(?)"
        result = P.classify(text)
        self.assertEqual(len(result["4.6"]), 1, "should match 4.6 (für später)")
        self.assertEqual(len(result["4.7"]), 1, "should match 4.7 ((?))")
        self.assertTrue(result["4.6"][0].metadata.get("conditional_defer_question"))
        self.assertTrue(result["4.7"][0].metadata.get("conditional_defer_question"))
        self.assertTrue(result["4.7"][0].metadata.get("paired_with_4_6"))
        self.assertIn("backlog", result["4.6"][0].metadata.get("recommended_action", "").lower())

    def test_evtl_spaeter_still_4_6_only(self):
        # Regression: evtl + spaeter darf NICHT als conditional_defer triggern
        # weil _resolve_4_6_vs_4_7 schon korrekt 4.6 entscheidet
        result = P.classify("evtl machen wir das spaeter")
        self.assertEqual(len(result["4.6"]), 1)
        self.assertEqual(len(result["4.7"]), 0)
        self.assertFalse(result["4.6"][0].metadata.get("conditional_defer_question"))


class TestExtractToolOutput(unittest.TestCase):
    """NEU 2026-05-01 Stefan-Korrektur Turn 9 Punkt 2."""

    def test_basic_tool_output(self):
        text = "[init-deps-update] workspace_type=ha-playground"
        lines = P.extract_tool_output_lines(text)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "[init-deps-update] workspace_type=ha-playground")

    def test_multiple_tool_lines(self):
        text = """- normaler bullet
[init-deps-update] line 1 with details
[init-deps-update] line 2 with more details
- anderer bullet"""
        lines = P.extract_tool_output_lines(text)
        self.assertEqual(len(lines), 2)

    def test_no_tool_output(self):
        self.assertEqual(P.extract_tool_output_lines("just text"), [])

    def test_full_stefan_example(self):
        text = """- ich habe gepullt und dann: python3 ~/.claude/scripts/init-deps-update.py
[init-deps-update] workspace_type=ha-playground, repo=ha-playground
[init-deps-update] updated docs/DEPENDENCIES.md - +122 added, -0 removed, now 466 files indexed.
- new item"""
        bullets = P.extract_bullets(text)
        tool_lines = P.extract_tool_output_lines(text)
        self.assertEqual(len(bullets), 2, "2 bullets (excluding tool-output lines)")
        self.assertEqual(len(tool_lines), 2, "2 tool-output lines")


class TestPullActionAs48(unittest.TestCase):
    """Stefan-Korrektur Turn 9: 4.8 erweitert um git/dev verbs."""

    def test_habe_gepullt(self):
        result = P.classify("ich habe gepullt und dann python ausgeführt")
        self.assertGreaterEqual(len(result["4.8"]), 1)


class TestComplexStefanPromptIntegration(unittest.TestCase):
    """Integration: ein realistischer Stefan-Prompt mit Bullets + Sub-Items + Parens."""

    def test_full_stefan_prompt(self):
        prompt = """- 4 ist gut so, ändere nur X, lass uns Y für später speichern
- siehe /Users/admin/conductor/workspaces/ha-playground/foo/README.md (also der pfad)
- evtl docs cleanup machen (?)"""
        result = P.classify(prompt)
        # Erwartet: 4.1 (ändere nur X), 4.6 (lass uns Y für später), 4.4 (path ref),
        # 4.7 (evtl docs cleanup), evtl. mehr
        self.assertGreater(sum(len(items) for items in result.values()), 0,
                           "complex prompt should produce items")
        # Specific: lib should split sub-items and catch the imperative + defer
        self.assertGreater(len(result["4.1"]) + len(result["4.6"]) + len(result["4.7"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
