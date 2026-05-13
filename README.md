# parseprompt — `(?)→!`

> Turn vague AI-coding prompts into structured, routed, persistent intent.

**About the name `(?)→!`**: `(?)` is the trigger pattern itself — every time you write a parenthetical question mark in a prompt ("does that make sense (?)"), you're flagging an uncertainty / sanity-check / "is this a good idea?" moment. `parseprompt` catches every `(?)` and converts it into a concrete `!` (action or resolution): small-scope sanity-checks get answered inline in the same turn, large-scope eval-then-decide items get persisted to the backlog under `## Tentative` so they don't get dropped. The name is the trigger, the arrow is the workflow, the `!` is the answer that doesn't disappear.

Every prompt you send to your AI coding assistant has 8 dimensions: explicit asks, questions, rejections, context refs, risks, deferred ideas, tentative actions, and implicit followups. Most assistants only catch the explicit ask. The rest leak.

`parseprompt` is a tiny system of skills + hooks + a SQLite routing brain that catches all 8 — automatically, on every prompt, before any code touches your repo. It's small (~700 lines), forkable, and works with Claude Code (or any harness that supports UserPromptSubmit / PreToolUse / Stop hooks).

## What it does

```
You type:        "we could add a dark theme later, also fix the login bug"
                                       │
                                       ▼
parseprompt:     ┌─ 4.6 Future Work: dark theme         → docs/BACKLOG.md ## Future
                 ├─ 4.1 Requirement:  fix login bug      → docs/BACKLOG.md (with PROJ-NNN id)
                 ├─ Per-item routing recommendation:    [SKILL] backend-test (score 4.2)
                 └─ Full 8-dimension capture in:        .context/prompt-analysis-N.md

Then on Stop:    session-logs/2024-09-15-fix-login/
                  ├── prompt-analysis.md, prompt-analysis-2.md, ...
                  ├── notes.md (skill invocation log)
                  ├── todos.md (workspace-local backlog)
                  └── session-log.md (auto-stub + your synthesis)
```

Three things make it different from "another prompt logger":

1. **Tripwire enforcement**. The `parse-prompt` skill is forced on every prompt — Write/Edit are blocked until the analysis runs. No "I'll do it later" drift.
2. **Routing brain that learns**. A SQLite DB scores every prompt against your skills + agents, recommends top-N candidates, and adjusts keyword weights based on what you actually invoke. Cold start works fine; the longer you use it, the sharper the recommendations.
3. **Per-turn capture survives merges**. `.context/prompt-analysis-N.md` is gitignored (rough drafts), but the Stop hook archives it into git-tracked `session-logs/` at session end. Audit-trail "why" sits next to git's "what".

## Install

```bash
git clone https://github.com/f17mkx/parseprompt ~/.parseprompt

# Bootstrap routing DB
mkdir -p ~/.parseprompt/data
sqlite3 ~/.parseprompt/data/routing.db < ~/.parseprompt/data/schema.sql
sqlite3 ~/.parseprompt/data/routing.db < ~/.parseprompt/data/seed-example.sql

# Wire hooks into Claude Code (or your harness's equivalent)
# See ~/.parseprompt/examples/settings.json for the full config
```

Then add the snippet from `examples/claude-md-example.md` to your project's `CLAUDE.md` (or global `~/.claude/CLAUDE.md`).

That's it. Next prompt you send fires the tripwire, parse-prompt runs, you get a structured analysis.

## Configure

Three env vars, all optional:

```bash
# Where to put the routing DB (default ~/.parseprompt/data/routing.db)
export PARSEPROMPT_DB="$HOME/.parseprompt/data/routing.db"

# Workspace → routing-domain mapping for boosting in-domain capabilities
export PARSEPROMPT_DOMAIN_MAP='{"my-saas": "frontend", "my-api": "backend"}'

# Session-message store for the feedback loop (silent no-op if unset)
export SESSION_DB_PATH="$HOME/Library/Application Support/com.conductor.app/conductor.db"
```

See `docs/HOW-TO-CUSTOMIZE.md` for the full surface.

## What's inside

```
parseprompt/
├── skills/          # parse-prompt, trigger, session-log, handoff (Markdown skills)
├── hooks/           # tripwire-write, tripwire-check, route-prompt, route-feedback,
│                    # session-log-finalize, routing-edit-reminder
├── lib/             # pure-Python compute layer (split in v2)
│   ├── parser.py        # classify() — bullets, sub-items, 8-dim assignment
│   ├── dimensions.py    # trigger patterns, tag maps, format templates
│   ├── interpretation.py # per-item interpretation generation (Step 5.5 v2)
│   ├── routing.py       # route_text() / route_prompt() — score capabilities
│   └── test_*.py        # 187 unit tests, runs without external deps
├── data/            # routing.db schema + seed example
├── docs/            # ARCHITECTURE, INPUT-GRAMMAR-EXAMPLE, SESSION-LIFECYCLE,
│                    # INTEGRATIONS, HOW-TO-CUSTOMIZE, examples/
├── examples/        # settings.json (hook wiring), claude-md-example.md
├── tools/           # grammar-corpus-pass.py (auto-fill grammar opener tables)
└── tests/           # smoke tests for lib/routing.py
```

The whole thing is ~3k lines of Python + Bash + Markdown. No magic. Read `docs/ARCHITECTURE.md` and you know how it works.

## Why this exists

Three categories of prompt-content keep leaking out of normal AI-assisted dev workflows:

- **Soft suggestions** ("we could do X later") — neither a requirement nor a rejection, so they evaporate after merge.
- **Tentative ideas** ("eventuell X machen", "is this right?") — need evaluation, not deferral.
- **Implicit followups** ("X is done", "I renamed Y") — the consequences (stale refs, broken paths) are never explicit but always real.

Each of these is now a dedicated dimension (4.6, 4.7, 4.8) with its own trigger patterns, routing target, and verbatim-quote contract. The architecture documents the leak paths in detail and shows the triple-catch that closes them.

## Privacy note

`hooks/route-prompt.py` logs the full text of every prompt into `routing.db` (the `prompt_classifications.prompt` column) so the feedback loop can correlate prompts with which capabilities were invoked. The DB lives in your install root and is gitignored by default. If you paste secrets / API keys / PII into prompts, they end up in this DB. Two options if that's a concern:

- Truncate or hash the prompt before it's logged (edit `log_classification` in `route-prompt.py:36`)
- Set the DB path to a workspace-local location and gitignore it per-project

The default behavior is "log full prompt" because the feedback loop benefits from it — make this an explicit choice, not a surprise.

## Status

Experimental. Designed for one user's workflow originally, then generalized. The patterns are battle-tested; the public packaging is fresh. Slow response on issues — fork-friendly is the model.

License: MIT. See `LICENSE`.

## Acknowledgments

Built on top of Claude Code's hook system (UserPromptSubmit / PreToolUse / Stop). Inspired by the realization that a prompt is rarely a single intent — it's a small structured document, and treating it as one unlocks a lot.

---

> **Logo:** `(?)→!` — from uncertain question to executable action.

