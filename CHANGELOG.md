# Changelog

All notable changes to parseprompt. Newest at top. Follows SemVer: MAJOR for breaking changes, MINOR for backward-compatible additions, PATCH for backward-compatible fixes.

## v1.1.0 - 2026-05-13

Architectural refactor: monolithic skill -> thin orchestrator + pure-Python lib layer. Backward-compatible (`route_prompt` / `route_text` public API unchanged, `lib/routing.py` keeps its v1.0.0 signature).

### Added
- `lib/parser.py` (712 lines) - public `classify()` API. Handles bullet/sub-item extraction, 8-dimension assignment, workspace-type detection (`detect_workspace_type` + multi-path `detect_referenced_workspaces`), security-flag detection, parenthetical inserts + dash-comments + tool-output extraction.
- `lib/dimensions.py` (568 lines) - trigger-pattern catalog for 4.1-4.8 (`TRIGGER_PATTERNS_4_X`), tag maps (`TAG_MAPPING_PMB`, `TAG_MAPPING_HA`), workspace-type detectors, format templates for routed items. Single source of truth for "what phrase belongs in what dimension".
- `lib/interpretation.py` (246 lines) - Step 5.5 v2 interpretation generator. Builds per-item context strings of the form `<workspace> <subject-tags> <action-verbs> <referenced-entities>` for downstream routing, so recommendations key off what items mean in context, not just on surface keywords. `ConversationContext` dataclass for hook-side resolution.
- `lib/test_parser.py`, `lib/test_dimensions.py`, `lib/test_interpretation.py` - 187 unit tests covering every dimension, sub-item splitting, parenthetical inserts, dash comments, 4.6-vs-4.7 precedence (Stefan-Decision-Tree), conditional-defer-question detection, security flags, conversation context resolution. Run with `python3 -m unittest lib.test_parser lib.test_dimensions lib.test_interpretation` from repo root.
- `skills/handoff.md` - new skill. Adaptive next-session knowledge-transfer doc (Done-State 30-50 lines, Cliff-Hanger 100-200 lines). Pairs with `/session-log` to survive `/compact` lossy summarization between sessions.

### Changed
- `lib/routing.py` - kept the v1 generic API (env-var-driven `PARSEPROMPT_DOMAIN_MAP`, `db_path` kwarg, substring fallback for `frontend` / `backend` / `infra`). Tests in `tests/test_routing.py` continue to pass against this layer.
- `README.md` - new "What's new in v2.0" section, updated "What's inside" tree to reflect lib/ split, line count corrected to ~3k.

### Conceptual additions (live in the parser, documented for users)
- **Sub-item splitting** at conjunction + imperative-stem boundaries (`, lass uns`, `, but`, `, when`, `, change`). One bullet can hold multiple actions.
- **Parenthetical inserts** + **dash comments** classified separately (Question-Insert / Self-Reference / Contrast / Clarification / Note). Robust against unmatched parens.
- **Tool-output detection** for `[program-name]\s+content` lines pasted into prompts.
- **Conditional-defer-question** for the rare case of 4.6 + 4.7-small-scope co-trigger without `evtl`-disambiguator. Both items kept, with `recommended_action: "ask user if this should become a backlog item"`.
- **4.6-vs-4.7 precedence** explicit Decision-Tree: `evtl + later -> 4.6`, `evtl alone -> 4.7`, tie without disambiguator -> 4.7 (drops are more painful than over-eval).
- **v2-pattern Pre-Check-Wrapper**: `evtl X + (vorher pruefen)` triggers small-scope 4.7 not 4.6, because the parenthetical signals "sanity-check first" not "defer".

### Migration notes (v1.0.0 -> v1.1.0)
- `lib/routing.py` keeps the v1.0.0 generic API (`PARSEPROMPT_DOMAIN_MAP` env var, `db_path` kwarg, substring fallback). If you were importing `routing.route_prompt` or `routing.route_text`, no change needed.
- If you were extending the 8-dim classifier by editing `skills/parse-prompt.md` prose: that approach still works, but the recommended path is now to add trigger patterns to `lib/dimensions.py` and let `lib/parser.py classify()` pick them up. Tests guard against regression.
- If you wrote a custom hook calling the skill via subprocess: the skill is still the entry point; the lib modules are an implementation detail.

### Why MINOR (1.0.0 -> 1.1.0) and not MAJOR
Every change in v1.1.0 is additive:
- New `lib/parser.py`, `lib/dimensions.py`, `lib/interpretation.py` modules - importable but not required by existing call sites.
- New `/handoff` skill - opt-in, doesn't affect existing skills.
- New tests in `lib/test_*.py` - additive coverage, no behavior change.
- `lib/routing.py` API surface unchanged from v1.0.0.

No breaking changes -> MINOR bump.

## v1.0.0 - 2026-04-29

Initial public release.

### Added
- `skills/parse-prompt.md` - 8-dimension prompt parser, runs on every UserPromptSubmit via tripwire.
- `skills/trigger.md` - hand-curated trigger-pattern maintenance companion.
- `skills/session-log.md` - synthesis-append for non-recoverable session knowledge.
- `hooks/parse-prompt-tripwire-write.sh` + `parse-prompt-tripwire-check.sh` - enforce parse-prompt-first discipline by blocking mutating tools until analysis is written.
- `hooks/route-prompt.py` - UserPromptSubmit handler that scores capabilities and writes top-3 recommendations.
- `hooks/route-feedback.py` - PostToolUse handler that adjusts keyword weights when a capability is invoked.
- `hooks/session-log-finalize.sh` - Stop-hook that archives `.context/prompt-analysis-*.md` + plan files into `session-logs/<date>-<topic>/`.
- `hooks/routing-edit-reminder.sh` - reminds the user to re-seed the DB when capabilities change.
- `lib/routing.py` - pure-compute routing library, ~200 lines, no external deps beyond stdlib + sqlite3.
- `data/schema.sql` + `data/seed-example.sql` - bootstrap the routing brain.
- `docs/ARCHITECTURE.md` - single source of truth for routing & persistence layers.
- `docs/INPUT-GRAMMAR-EXAMPLE.md` - the 8-dimension trigger catalog with examples.
- `docs/SESSION-LIFECYCLE.md` - how UserPromptSubmit / PreToolUse / Stop hooks compose.
- `docs/INTEGRATIONS.md` - hook wiring for Claude Code, other harnesses.
- `docs/HOW-TO-CUSTOMIZE.md` - knobs and overrides.
- `examples/settings.json` + `examples/claude-md-example.md` - copy-paste wiring.
- `tools/grammar-corpus-pass.py` - re-runnable CLI for corpus-coverage stats against `zzz-session-logs/*/prompt-analysis*.md`.
- `tests/test_routing.py` - smoke tests for the pre-split routing library.
