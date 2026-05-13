"""
Smoke tests for lib/routing.py.

Run with: python3 -m pytest tests/

These tests do NOT require a routing.db — they exercise the pure-compute
functions (tokenize, detect_intent, detect_complexity, route_text without DB).
DB-dependent tests (score_capabilities) are gated on a fixture DB created at
test setup.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

# Make the lib importable when running pytest from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

import routing  # noqa: E402


class TokenizeTests(TestCase):
    def test_strips_code_fences(self):
        text = "before ```code block``` after"
        tokens = routing.tokenize(text)
        self.assertIn("before", tokens)
        self.assertIn("after", tokens)
        self.assertNotIn("code", tokens)

    def test_strips_inline_code(self):
        text = "use `git commit` to commit"
        tokens = routing.tokenize(text)
        self.assertIn("use", tokens)
        self.assertIn("commit", tokens)
        self.assertNotIn("git", tokens)  # was inside backticks

    def test_lowercases(self):
        tokens = routing.tokenize("FRONTEND backend Database")
        self.assertEqual(tokens, ["frontend", "backend", "database"])

    def test_filters_stopwords(self):
        tokens = routing.tokenize("this is the test of stopwords")
        self.assertNotIn("this", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("the", tokens)
        self.assertIn("test", tokens)
        self.assertIn("stopwords", tokens)

    def test_keeps_german_umlauts(self):
        tokens = routing.tokenize("änderung über überprüfen")
        # ä ö ü ß should survive
        self.assertIn("änderung", tokens)
        self.assertIn("überprüfen", tokens)


class IntentDetectionTests(TestCase):
    def test_backlog_intent(self):
        self.assertEqual(routing.detect_intent("we could do this later"), "backlog")
        self.assertEqual(routing.detect_intent("would be nice to add a feature"), "backlog")
        self.assertEqual(routing.detect_intent("für später"), "backlog")
        self.assertEqual(routing.detect_intent("vielleicht sollten wir das machen"), "backlog")
        self.assertEqual(routing.detect_intent("wir könnten das auch noch machen"), "backlog")

    def test_ship_intent(self):
        self.assertEqual(routing.detect_intent("ship it"), "ship")
        self.assertEqual(routing.detect_intent("create a PR"), "ship")
        self.assertEqual(routing.detect_intent("commit and push"), "ship")
        self.assertEqual(routing.detect_intent("merge onto main"), "ship")

    def test_confirm_intent(self):
        self.assertEqual(routing.detect_intent("yes"), "confirm")
        self.assertEqual(routing.detect_intent("ok"), "confirm")
        self.assertEqual(routing.detect_intent("genau"), "confirm")
        self.assertEqual(routing.detect_intent("perfect"), "confirm")
        self.assertEqual(routing.detect_intent("go ahead"), "confirm")

    def test_fix_intent(self):
        self.assertEqual(routing.detect_intent("fix the bug in login"), "fix")
        self.assertEqual(routing.detect_intent("X is broken"), "fix")
        self.assertEqual(routing.detect_intent("funktioniert nicht"), "fix")

    def test_audit_intent(self):
        self.assertEqual(routing.detect_intent("review this PR"), "audit")
        self.assertEqual(routing.detect_intent("check the logs"), "audit")
        self.assertEqual(routing.detect_intent("look at the dashboard"), "audit")

    def test_unknown_for_nothing_matches(self):
        self.assertEqual(routing.detect_intent("the weather is nice"), "unknown")

    def test_backlog_beats_audit(self):
        # 'we could' and 'review' both match — backlog has priority 1, audit later.
        prompt = "we could review the dashboard later"
        self.assertEqual(routing.detect_intent(prompt), "backlog")

    def test_backlog_beats_plan(self):
        # 'maybe we' and 'plan' both match — backlog is first.
        prompt = "maybe we should plan a refactor"
        self.assertEqual(routing.detect_intent(prompt), "backlog")


class ComplexityDetectionTests(TestCase):
    def test_short_simple(self):
        self.assertEqual(routing.detect_complexity("fix the bug"), 1)

    def test_short_with_question(self):
        self.assertEqual(routing.detect_complexity("does this work?"), 1)

    def test_medium(self):
        prompt = " ".join(["word"] * 50)
        self.assertEqual(routing.detect_complexity(prompt), 2)

    def test_longer(self):
        prompt = " ".join(["word"] * 200)
        self.assertEqual(routing.detect_complexity(prompt), 3)

    def test_very_long(self):
        prompt = " ".join(["word"] * 500)
        self.assertEqual(routing.detect_complexity(prompt), 4)


class WorkspaceDomainTests(TestCase):
    def test_default_global(self):
        self.assertEqual(routing.detect_workspace_domain("/some/random/path"), "global")

    def test_frontend_substring(self):
        self.assertEqual(routing.detect_workspace_domain("/repos/my-frontend-app"), "frontend")

    def test_backend_substring(self):
        self.assertEqual(routing.detect_workspace_domain("/repos/api-server"), "backend")

    def test_env_var_override(self):
        os.environ["PARSEPROMPT_DOMAIN_MAP"] = '{"my-saas": "saas-app", "client-x": "consulting"}'
        try:
            self.assertEqual(routing.detect_workspace_domain("/repos/my-saas/web"), "saas-app")
            self.assertEqual(routing.detect_workspace_domain("/repos/client-x/yz"), "consulting")
        finally:
            del os.environ["PARSEPROMPT_DOMAIN_MAP"]


class RouteTextNoDBTests(TestCase):
    """route_text() returns intent + complexity + workspace_domain even when DB is missing."""

    def test_returns_unknown_for_empty(self):
        result = routing.route_text("")
        self.assertEqual(result["intent"], "unknown")
        self.assertEqual(result["candidates"], [])

    def test_returns_intent_without_db(self):
        # Use a nonexistent DB path — should silently return [] candidates but still classify intent.
        result = routing.route_text("we could ship this later", db_path="/tmp/nonexistent.db")
        self.assertEqual(result["intent"], "backlog")
        self.assertEqual(result["candidates"], [])

    def test_context_prefix_changes_keywords(self):
        # Without prefix, "react to that" has no useful tokens after stopword filtering.
        result_raw = routing.route_text("react to that", db_path="/tmp/nonexistent.db")
        result_prefixed = routing.route_text(
            "react to that",
            context_prefix="frontend timeline review verify pr-42",
            db_path="/tmp/nonexistent.db"
        )
        self.assertIn("context_prefix", result_prefixed)
        self.assertEqual(result_prefixed["context_prefix"], "frontend timeline review verify pr-42")
        # The interpretation should produce more keywords
        self.assertGreater(len(result_prefixed["keywords"]), len(result_raw["keywords"]))


class ScoreCapabilitiesTests(TestCase):
    """DB-backed tests using a temporary fixture DB."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.db = Path(cls.tmp) / "test_routing.db"

        # Build minimal schema + fixture data.
        conn = sqlite3.connect(cls.db)
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE capabilities (
              id INTEGER PRIMARY KEY,
              kind TEXT, name TEXT UNIQUE, file_path TEXT,
              description TEXT, domain TEXT DEFAULT 'global',
              trigger_hint TEXT, skip_hint TEXT,
              status TEXT DEFAULT 'active'
            );
            CREATE TABLE capability_keywords (
              id INTEGER PRIMARY KEY,
              capability_id INTEGER, keyword TEXT,
              weight REAL DEFAULT 1.0,
              source TEXT, updated_at TEXT
            );

            INSERT INTO capabilities (kind, name, file_path, description, domain) VALUES
              ('skill', 'frontend-build', 'skills/frontend-build.md', 'Build the frontend', 'frontend'),
              ('skill', 'backend-test',   'skills/backend-test.md',   'Run backend tests',  'backend'),
              ('skill', 'global-deploy',  'skills/global-deploy.md',  'Deploy globally',    'global');

            INSERT INTO capability_keywords (capability_id, keyword, weight) VALUES
              (1, 'build', 3.0),
              (1, 'frontend', 2.0),
              (2, 'test', 3.0),
              (2, 'backend', 2.0),
              (3, 'deploy', 3.0),
              (3, 'release', 2.0);
        """)
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_keyword_match(self):
        keywords = {"build", "frontend"}
        results = routing.score_capabilities(
            keywords, intent="meta", workspace_domain="global",
            db_path=self.db
        )
        names = [r["name"] for r in results]
        self.assertIn("frontend-build", names)
        # backend-test shouldn't match because keywords don't overlap
        self.assertNotIn("backend-test", names)

    def test_domain_boost(self):
        # frontend-build with workspace=frontend should score higher than with workspace=global
        keywords = {"build"}
        r_frontend = routing.score_capabilities(
            keywords, intent="meta", workspace_domain="frontend", db_path=self.db
        )
        r_global = routing.score_capabilities(
            keywords, intent="meta", workspace_domain="global", db_path=self.db
        )
        # find frontend-build score in each
        score_in_frontend = next(r["score"] for r in r_frontend if r["name"] == "frontend-build")
        score_in_global = next(r["score"] for r in r_global if r["name"] == "frontend-build")
        self.assertGreater(score_in_frontend, score_in_global)

    def test_min_score_floor(self):
        # A keyword that doesn't exist returns nothing.
        results = routing.score_capabilities(
            {"nonexistent-keyword-xyzzy"}, intent="meta", workspace_domain="global",
            db_path=self.db
        )
        self.assertEqual(results, [])

    def test_max_candidates_cap(self):
        # All three capabilities have unique keywords, but limit to 2.
        keywords = {"build", "test", "deploy"}
        results = routing.score_capabilities(
            keywords, intent="meta", workspace_domain="global",
            db_path=self.db, max_candidates=2
        )
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    main()
