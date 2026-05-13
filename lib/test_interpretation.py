"""
Tests for lib/interpretation.py.

Covers:
- ConversationContext dataclass
- generate_interpretation() integration (full string for sample items)
- extract_subject_tags (PMB tag-mapping, HA tag-mapping, generic fallback)
- extract_action_verbs (DE + EN imperatives + review verbs)
- extract_referenced_entities (PR refs, HA entities, file basenames)
- _get_workspace_tag (workspace → tag mapping, generic → empty)
- Stefan-Beispiele aus parse-prompt.md Step 5.5 (raw → interpretation)

Run: python3 -m unittest lib/test_interpretation.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import interpretation as I
from interpretation import ConversationContext
from parser import Item


# ---------------------------------------------------------------------------
# ConversationContext
# ---------------------------------------------------------------------------

class TestConversationContext(unittest.TestCase):
    def test_minimal_context(self):
        ctx = ConversationContext(workspace_type="pmb", cwd=Path("/tmp"))
        self.assertEqual(ctx.workspace_type, "pmb")
        self.assertEqual(ctx.referenced_files, [])
        self.assertEqual(ctx.referenced_prs, [])
        self.assertIsNone(ctx.last_assistant_text)

    def test_full_context(self):
        ctx = ConversationContext(
            workspace_type="ha-playground",
            cwd=Path("/some/path"),
            referenced_files=["foo.py", "bar.md"],
            referenced_prs=[270, 271],
            last_assistant_text="prior text",
        )
        self.assertEqual(ctx.referenced_prs, [270, 271])


# ---------------------------------------------------------------------------
# extract_subject_tags
# ---------------------------------------------------------------------------

class TestExtractSubjectTags(unittest.TestCase):
    def _make_item(self, verbatim):
        return Item(dimension="4.1", verbatim=verbatim, title=verbatim[:60])

    def test_pmb_dashboard_keyword(self):
        ctx = ConversationContext(workspace_type="pmb", cwd=Path("/tmp"))
        item = self._make_item("dashboard timeline anpassen")
        tags = I.extract_subject_tags(item, ctx)
        # "dashboard" → "dashboard", "timeline" → "dashboard/timeline"
        self.assertIn("dashboard", tags)
        self.assertIn("dashboard/timeline", tags)

    def test_pmb_table_manager(self):
        ctx = ConversationContext(workspace_type="pmb", cwd=Path("/tmp"))
        item = self._make_item("tisch grundriss neu machen")
        tags = I.extract_subject_tags(item, ctx)
        self.assertIn("settings/table-manager", tags)

    def test_ha_yama_chopan(self):
        ctx = ConversationContext(workspace_type="ha-playground", cwd=Path("/tmp"))
        item = self._make_item("yama chopan integration")
        tags = I.extract_subject_tags(item, ctx)
        self.assertIn("yama", tags)
        self.assertIn("integrations", tags)

    def test_generic_fallback_to_keywords(self):
        ctx = ConversationContext(workspace_type="generic", cwd=Path("/tmp"))
        item = self._make_item("fix the routing-system module")
        tags = I.extract_subject_tags(item, ctx)
        # No specific tag-map → fallback to content-words
        self.assertGreater(len(tags), 0)
        self.assertNotIn("the", tags, "stopwords removed")


# ---------------------------------------------------------------------------
# extract_action_verbs
# ---------------------------------------------------------------------------

class TestExtractActionVerbs(unittest.TestCase):
    def _make_item(self, verbatim):
        return Item(dimension="4.1", verbatim=verbatim, title=verbatim[:60])

    def test_german_imperative(self):
        verbs = I.extract_action_verbs(self._make_item("shippe das jetzt"))
        self.assertIn("shipp", verbs)

    def test_english_imperative(self):
        verbs = I.extract_action_verbs(self._make_item("ship and deploy"))
        self.assertIn("ship", verbs)
        self.assertIn("deploy", verbs)

    def test_review_verbs(self):
        verbs = I.extract_action_verbs(self._make_item("verify the checklist + review"))
        self.assertIn("verify", verbs)
        self.assertIn("review", verbs)

    def test_no_verbs_returns_empty(self):
        verbs = I.extract_action_verbs(self._make_item("just status text"))
        self.assertEqual(verbs, [])


# ---------------------------------------------------------------------------
# extract_referenced_entities
# ---------------------------------------------------------------------------

class TestExtractReferencedEntities(unittest.TestCase):
    def _make_item(self, verbatim):
        return Item(dimension="4.1", verbatim=verbatim, title=verbatim[:60])

    def _ctx(self, **kwargs):
        return ConversationContext(workspace_type="pmb", cwd=Path("/tmp"), **kwargs)

    def test_pr_reference(self):
        entities = I.extract_referenced_entities(self._make_item("PR #270 ist offen"), self._ctx())
        self.assertIn("pr-270", entities)

    def test_ha_entity(self):
        entities = I.extract_referenced_entities(
            self._make_item("schalte light.licht_kind_1 ein"), self._ctx()
        )
        self.assertIn("light.licht_kind_1", entities)

    def test_file_basename(self):
        entities = I.extract_referenced_entities(
            self._make_item("siehe /Users/admin/foo/bar.py für details"), self._ctx()
        )
        self.assertIn("bar.py", entities)

    def test_pr_from_context(self):
        # PR established in broader conversation context, not in item itself
        entities = I.extract_referenced_entities(
            self._make_item("Reagier auf das"),
            self._ctx(referenced_prs=[270]),
        )
        self.assertIn("pr-270", entities)


# ---------------------------------------------------------------------------
# _get_workspace_tag
# ---------------------------------------------------------------------------

class TestWorkspaceTag(unittest.TestCase):
    def test_known_types(self):
        self.assertEqual(I._get_workspace_tag("pmb"), "pmb")
        self.assertEqual(I._get_workspace_tag("ha-playground"), "ha-playground")
        self.assertEqual(I._get_workspace_tag("productivity"), "productivity")
        self.assertEqual(I._get_workspace_tag("ha-live-config"), "ha-live-config")

    def test_generic_returns_empty(self):
        self.assertEqual(I._get_workspace_tag("generic"), "")

    def test_unknown_returns_empty(self):
        self.assertEqual(I._get_workspace_tag("unknown"), "")


# ---------------------------------------------------------------------------
# generate_interpretation (integration)
# ---------------------------------------------------------------------------

class TestGenerateInterpretation(unittest.TestCase):
    def _ctx(self, ws_type="pmb", **kwargs):
        return ConversationContext(workspace_type=ws_type, cwd=Path("/tmp"), **kwargs)

    def test_stefan_example_reagier_auf_das_with_context(self):
        # parse-prompt.md Step 5.5 v2 example (verbatim Stefan-quote in skill):
        # Raw item:       "Reagier auf das" (im Kontext PR #270 timeline)
        # Interpretation: "pmb timeline review verify checklist pr-270"
        # We can't fully reproduce the "review verify checklist" without prior-turn
        # text, but pr-270 + workspace-tag MUST be present.
        item = Item(dimension="4.1", verbatim="Reagier auf das", title="Reagier auf das")
        ctx = self._ctx(ws_type="pmb", referenced_prs=[270])
        result = I.generate_interpretation(item, ctx)
        self.assertIn("pmb", result)
        self.assertIn("pr-270", result)

    def test_imperative_with_subject(self):
        item = Item(dimension="4.1", verbatim="shippe das dashboard timeline",
                    title="shippe das dashboard timeline")
        ctx = self._ctx(ws_type="pmb")
        result = I.generate_interpretation(item, ctx)
        # workspace + subject + action all present
        self.assertIn("pmb", result)
        self.assertIn("dashboard", result)
        self.assertIn("shipp", result)

    def test_generic_no_workspace_prefix(self):
        item = Item(dimension="4.1", verbatim="fix the test", title="fix the test")
        ctx = self._ctx(ws_type="generic")
        result = I.generate_interpretation(item, ctx)
        # generic → no leading "generic" tag
        self.assertFalse(result.startswith("generic"))
        self.assertIn("fix", result)

    def test_dedupe_preserves_order(self):
        item = Item(dimension="4.1", verbatim="dashboard dashboard fix", title="...")
        ctx = self._ctx(ws_type="pmb")
        result = I.generate_interpretation(item, ctx)
        # "dashboard" should appear once even though it's matched multiple times
        self.assertEqual(result.count("dashboard"), 1)

    def test_lowercase_output(self):
        item = Item(dimension="4.1", verbatim="SHIPPE DAS Dashboard", title="...")
        ctx = self._ctx(ws_type="pmb")
        result = I.generate_interpretation(item, ctx)
        self.assertEqual(result, result.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
