-- routing.db schema for parseprompt.
--
-- Bootstrap a fresh DB:
--   sqlite3 ~/.parseprompt/data/routing.db < schema.sql
--   sqlite3 ~/.parseprompt/data/routing.db < seed-example.sql
--
-- Two layers of state:
--   1. Capabilities (skills + agents you want the router to recommend) +
--      their keywords. This is the WHAT-CAN-BE-RECOMMENDED layer.
--   2. Prompt classifications (per-prompt log of intent + candidates +
--      outcome). This is the LEARNING layer that route-feedback.py adjusts.

-- =====================================================================
-- Layer 1: capabilities and keywords
-- =====================================================================

CREATE TABLE capabilities (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('skill','agent')),
  name TEXT NOT NULL UNIQUE,
  file_path TEXT NOT NULL,
  description TEXT,
  domain TEXT DEFAULT 'global',
  trigger_hint TEXT,
  skip_hint TEXT,
  status TEXT DEFAULT 'active',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE capability_keywords (
  id INTEGER PRIMARY KEY,
  capability_id INTEGER NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  weight REAL DEFAULT 1.0,
  source TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(capability_id, keyword)
);

CREATE INDEX idx_capability_keywords_keyword ON capability_keywords(keyword);
CREATE INDEX idx_capabilities_status ON capabilities(status);
CREATE INDEX idx_capabilities_domain ON capabilities(domain);

-- =====================================================================
-- Layer 2: prompt classifications (per-prompt log + feedback loop state)
-- =====================================================================

CREATE TABLE prompt_classifications (
  id INTEGER PRIMARY KEY,
  session_id TEXT,
  prompt_hash TEXT,
  prompt TEXT NOT NULL,
  intent TEXT,
  keywords_json TEXT,
  complexity INTEGER,
  matched_capabilities_json TEXT,
  recommended_capability_id INTEGER,
  used_capability_id INTEGER,
  outcome TEXT CHECK(outcome IN ('success','fail','skipped','corrected','unknown')),
  user_feedback TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_classifications_session ON prompt_classifications(session_id);
CREATE INDEX idx_classifications_intent ON prompt_classifications(intent);
CREATE INDEX idx_classifications_created ON prompt_classifications(created_at);

-- =====================================================================
-- Optional advanced tables (intentionally empty in seed example)
-- =====================================================================
-- These tables enable multi-step routing pipelines (e.g. "for backend bugs in
-- domain X, run agents A then B then C"). Default seed leaves them empty —
-- they are forward-compatible for adopters who want chained routing.

CREATE TABLE routes (
  id INTEGER PRIMARY KEY,
  intent TEXT NOT NULL,
  task_type TEXT,
  pattern_keywords_json TEXT NOT NULL,
  domain TEXT DEFAULT 'global',
  confidence REAL DEFAULT 0.5,
  matched_count INTEGER DEFAULT 0,
  success_count INTEGER DEFAULT 0,
  source TEXT DEFAULT 'learned',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  last_matched_at TEXT
);

CREATE TABLE route_chain (
  id INTEGER PRIMARY KEY,
  route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  capability_id INTEGER NOT NULL REFERENCES capabilities(id),
  is_gate INTEGER DEFAULT 0,
  UNIQUE(route_id, position)
);

CREATE TABLE route_modifiers (
  id INTEGER PRIMARY KEY,
  route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  modifier_keyword TEXT NOT NULL,
  injected_capability_id INTEGER NOT NULL REFERENCES capabilities(id),
  position INTEGER,
  UNIQUE(route_id, modifier_keyword)
);

CREATE TABLE conditional_gates (
  id INTEGER PRIMARY KEY,
  route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  blocking_keyword TEXT NOT NULL,
  required_capability_id INTEGER REFERENCES capabilities(id),
  required_artifact TEXT
);

CREATE TABLE pre_commit_rules (
  id INTEGER PRIMARY KEY,
  domain TEXT NOT NULL,
  task_type TEXT NOT NULL,
  rule TEXT NOT NULL,
  severity TEXT DEFAULT 'required'
);

CREATE TABLE commit_invariants (
  id INTEGER PRIMARY KEY,
  domain TEXT NOT NULL,
  pattern TEXT NOT NULL,
  description TEXT,
  severity TEXT DEFAULT 'error'
);
