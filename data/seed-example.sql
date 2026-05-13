-- seed-example.sql — sample capabilities + keywords for a fresh routing.db.
--
-- Apply after schema.sql:
--   sqlite3 ~/.parseprompt/data/routing.db < seed-example.sql
--
-- This is an EXAMPLE seed — replace the capabilities below with the
-- skills + agents YOU want the router to recommend. The keyword weights are
-- starting points; the feedback loop (route-feedback.py) will adjust them
-- over time as it observes which capabilities actually get invoked.

-- =====================================================================
-- Built-in parseprompt capabilities (the skills shipped with this repo)
-- =====================================================================

INSERT INTO capabilities (kind, name, file_path, description, domain, trigger_hint) VALUES
  ('skill', 'parse-prompt', 'skills/parse-prompt.md',
   'Pre-processing pass on every user prompt. Extracts 8 dimensions into prompt-analysis-N.md and routes actionable items to BACKLOG.md.',
   'global', 'auto-runs via UserPromptSubmit hook'),
  ('skill', 'trigger', 'skills/trigger.md',
   'Add a curated trigger phrase to the input-grammar decision tree. Hand-curated grammar maintenance.',
   'global', 'when adding a new phrase like "(?)" or "eventuell" to the grammar guide'),
  ('skill', 'session-log', 'skills/session-log.md',
   'Synthesis-append for the current session log. Use for architecture decisions, failed attempts, surprising discoveries.',
   'global', 'at session end if something synthesis-worthy happened');

-- Keywords for parse-prompt (high weights — it's the entry point)
INSERT INTO capability_keywords (capability_id, keyword, weight, source) VALUES
  ((SELECT id FROM capabilities WHERE name='parse-prompt'), 'prompt', 2.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='parse-prompt'), 'parse', 2.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='parse-prompt'), 'analysis', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='parse-prompt'), 'requirements', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='parse-prompt'), 'extract', 1.5, 'seed');

INSERT INTO capability_keywords (capability_id, keyword, weight, source) VALUES
  ((SELECT id FROM capabilities WHERE name='trigger'), 'trigger', 2.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='trigger'), 'grammar', 2.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='trigger'), 'phrase', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='trigger'), 'opener', 1.0, 'seed');

INSERT INTO capability_keywords (capability_id, keyword, weight, source) VALUES
  ((SELECT id FROM capabilities WHERE name='session-log'), 'session', 2.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='session-log'), 'architecture', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='session-log'), 'decision', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='session-log'), 'discovery', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='session-log'), 'synthesis', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='session-log'), 'failure', 1.0, 'seed');

-- =====================================================================
-- Generic example skills (replace with YOUR project's skills)
-- =====================================================================

INSERT INTO capabilities (kind, name, file_path, description, domain, trigger_hint) VALUES
  ('skill', 'example-frontend-build', 'commands/frontend-build.md',
   'Example: build the frontend bundle and verify output size.',
   'frontend', 'when prompt mentions build / bundle / compile / vite / webpack'),
  ('skill', 'example-backend-test', 'commands/backend-test.md',
   'Example: run backend test suite with coverage.',
   'backend', 'when prompt mentions test / unit / integration / pytest / coverage'),
  ('skill', 'example-deploy', 'commands/deploy.md',
   'Example: deploy to staging or production.',
   'global', 'when prompt mentions deploy / release / prod / staging / push to prod'),
  ('agent', 'example-code-reviewer', 'agents/code-reviewer.md',
   'Example: independent code review focused on correctness, maintainability, security.',
   'global', 'after major code changes or before merge');

INSERT INTO capability_keywords (capability_id, keyword, weight, source) VALUES
  ((SELECT id FROM capabilities WHERE name='example-frontend-build'), 'build', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-frontend-build'), 'bundle', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-frontend-build'), 'compile', 1.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-frontend-build'), 'vite', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-frontend-build'), 'webpack', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-frontend-build'), 'frontend', 1.0, 'seed');

INSERT INTO capability_keywords (capability_id, keyword, weight, source) VALUES
  ((SELECT id FROM capabilities WHERE name='example-backend-test'), 'test', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-backend-test'), 'unit', 1.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-backend-test'), 'integration', 1.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-backend-test'), 'pytest', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-backend-test'), 'coverage', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-backend-test'), 'backend', 1.0, 'seed');

INSERT INTO capability_keywords (capability_id, keyword, weight, source) VALUES
  ((SELECT id FROM capabilities WHERE name='example-deploy'), 'deploy', 2.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-deploy'), 'release', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-deploy'), 'prod', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-deploy'), 'production', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-deploy'), 'staging', 1.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-deploy'), 'rollout', 1.0, 'seed');

INSERT INTO capability_keywords (capability_id, keyword, weight, source) VALUES
  ((SELECT id FROM capabilities WHERE name='example-code-reviewer'), 'review', 2.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-code-reviewer'), 'audit', 1.5, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-code-reviewer'), 'feedback', 1.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-code-reviewer'), 'merge', 1.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-code-reviewer'), 'pr', 1.0, 'seed'),
  ((SELECT id FROM capabilities WHERE name='example-code-reviewer'), 'pull-request', 1.0, 'seed');
