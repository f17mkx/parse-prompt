---
name: parse-prompt
description: "Prompt pre-processing — first pass on EVERY user prompt. Extracts requirements, questions, decisions, rejections, context references, and ambiguities into `.context/prompt-analysis-N.md` (full per-turn capture) and routes actionable items into the right project files (BACKLOG.md by default; project-specific delegates if configured). Runs automatically via the UserPromptSubmit hook + tripwire."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(ls *)
  - Bash(cat *)
  - Bash(wc *)
  - Bash(head *)
  - Bash(tail *)
  - Bash(mkdir *)
  - Bash(test *)
  - Bash(date *)
---

# /parse-prompt — pre-processing pass on every prompt

Extracts EVERYTHING noteworthy from a user prompt BEFORE the actual work starts. Not just feature requirements — also: questions, decisions, rejections, context references, credentials, ambiguities, deferred ideas, tentative actions, and implicit followups. Two outputs per run:

1. **`.context/prompt-analysis-N.md`** — full per-turn capture, all 8 dimensions + a proposed plan, incrementally numbered, never overwritten.
2. **Routing of actionable items into the right domain files** — `docs/BACKLOG.md` by default, with universal Future / Tentative sections. Project-specific routing (e.g. classifying items into UX/BUG/FEATURE/DECISION buckets, routing UX items into per-view CONCEPT files, drafting ADRs) can be added by delegating to a project-specific classifier — see `docs/INTEGRATIONS.md` and the example case study in `docs/examples/`.

**Why this exists.** In earlier prompt-processing setups, information slipped through: questions got subsumed into requirements, rejected options got reattempted, "we could do X later" suggestions evaporated after a merge. This skill is intentionally broad — if it's in the prompt, it lands here.

**Arguments**: a file path OR inline text. Empty + auto-hook context → use the current user prompt. Empty + no auto-hook → error.

---

## Step 1: read input

- `$ARGUMENTS` is an existing file path → read the file
- `$ARGUMENTS` is inline text → use directly
- Empty + auto-hook context (UserPromptSubmit) → use the current user prompt
- Completely empty → error

Set: `$INPUT` (raw text), `$SOURCE` (`user-prompt` or filename or `inline-text`), `$TS` (local time `YYYY-MM-DD HH:MM TZ` via `date '+%Y-%m-%d %H:%M %Z'` — e.g. `2024-09-15 21:16 CEST`. NEVER approximate (`~16:00` is forbidden). If `date` is unavailable, fall back to exact UTC with `Z` suffix).

## Step 2: determine routing targets per workspace type

Per item-category per workspace-type, items route to different domain files. Step 5 has the full logic. Quick map by workspace-type:

**Project-specific** (e.g. a project with its own classifier configured):
- 4.1 / 4.6 / 4.7 items → delegated to the project's classifier (see `docs/INTEGRATIONS.md`)
- 4.2 / 4.3 items → stay in `prompt-analysis-N.md` only

**Generic** (default for any other workspace):
- 4.1 / 4.6 / 4.7 items → `docs/BACKLOG.md` (auto-create with header if missing)
- 4.2 / 4.3 items → stay in `prompt-analysis-N.md` only

Save as `$WORKSPACE_TYPE` for Step 5 routing.

## Step 3: detect workspace type (for routing + tag mapping)

Determine `$WORKSPACE_TYPE`:

- A project-specific marker file or directory exists (e.g. `.parseprompt-project` config file, or a project-specific classifier skill is present) → use that project's type
- Otherwise → `generic`

Adopters: see `docs/HOW-TO-CUSTOMIZE.md` for how to add your own workspace-type detection rules. Tag-mapping (mapping prompt keywords to view/area tags inside a project) is also project-specific — see the example case study in `docs/examples/`.

For `generic`: tag from prompt keywords (1-2 words), or `unassigned`.

## Step 3.5: load input-grammar guide (optional)

Before Step 4 dimension-classification: if `docs/INPUT-GRAMMAR-EXAMPLE.md` (or your customized version) exists, read it once and use two anchors during classification.

**Anchor 1 — TL;DR Decision Tree**: hand-curated opener-pattern → dimension mapping. Authoritative, overrides the generic Step 4 heuristic when they conflict. Critical mappings the heuristic alone may miss include phrases like:

- `eventuell` / `evtl` / `vielleicht` / `maybe` (with a suggestion, NOT with "later") → **4.7 Tentative-Action**, NOT 4.6 Future Work
- `(?)` at sentence end or inline → **4.7 Tentative-Action** (Idea-Validation sub-type)
- `go` / `ship it` / `sign-off` / `los` → **Confirm** (intent-match via INTENTS regex in `lib/routing.py`)
- `X is done?!` / `I renamed X` / `X is now Y` / `X is live` → **4.8 Implicit-Followup** (mismatch-detection pass triggered)
- `we could` / `would be nice` / `someday` / `später` → **4.6 Future Work**
- `how` / `what` / `why` / `is there` → **4.2 Questions**
- `not X` / `instead Y` / `rather Z` → **4.3 Rejections**

**Anchor 2 — Per-dimension opener fingerprints**: top-N opener tables per dimension. For ambiguous phrases that don't clearly land in the decision tree:

1. Take the first 4 alpha-tokens (lowercased) of the phrase
2. Compare against the per-dimension opener tables
3. The dimension with strongest match wins
4. Tie → fall back to the TL;DR decision tree
5. No opener match → classify by top-N bigram presence per section

**Conflict resolution:** decision-tree (hand-curated) > Step-4 heuristic (generic).

**Update path:** the TL;DR table is curated via the `/trigger` skill (see `skills/trigger.md`). The auto-pass in `tools/grammar-corpus-pass.py` updates only the per-dimension opener tables, NOT the TL;DR table.

**Graceful degradation:** if the grammar guide is missing → continue with Step 4 without grammar bias. Don't abort, don't auto-create.

## Step 4: parse into 8 dimensions

**Walk each dimension separately. A single sentence can land in multiple dimensions.**

### 4.1 Explicit requirements (imperative verbs / "should")

- Imperative verbs: do, change, remove, show, add, ship, build, update, move, write, create, delete (DE: mach, ändere, entferne, zeige, füge hinzu, shippe, etc.)
- Descriptive "should": "X should do Y", "should look like Z"
- Implicit requirement via suggesting question: "shouldn't we also X?"
- Bug description: "X is broken", "doesn't work", "fails"
- Positive confirmation → status `Validated`

### 4.2 Questions (IMPORTANT: explicit AND implicit)

This is the category that gets lost most often:

- Direct question: "what is X for?", "what does Y do?", "how does Z work?"
- Clarification question: "did I get that right?", "is that correct?"
- Rhetorical question with implicit answer-expectation: "or not?"
- Recall question: "do you remember how we did this last time?"
- Meta question: "did X get done?", "did Y work?"

**Each question gets its own entry.** Don't subsume under a requirement.

### 4.3 Rejections (what the user excludes)

Strictly distinguished from 4.6 (Deferral): this is options that should NOT be implemented (now or ever).

- Negations: "not X", "no X", "without X"
- Preferences: "rather Y", "instead Z", "better W"
- Order constraints: "first X, then Y", "before Z"
- Exclusions: "skip W", "we don't need this"

Recorded so the option doesn't get reattempted next time. **Stays in `prompt-analysis-N.md` only** — no BACKLOG routing (rejection ≠ todo). **Exception: rejections with architectural character** (e.g. "we are NOT using Postgres, instead MySQL") may be routed by a project-specific classifier as a draft ADR.

### 4.4 Context references (IMPORTANT: capture everything concrete)

Everything concrete that appears in the prompt:

- **Paths**: absolute + relative (e.g. `docs/concept.md`, `clients/<name>/`)
- **Entity / device IDs**: `light.kitchen_main`, `media_player.living_room`, etc.
- **URLs**: `https://...`, GitHub links, vendor docs
- **People / rooms / devices**: names, locations, products
- **Credentials in cleartext** → **FLAG as security warning** (see Step 7)
- **Dates / deadlines**: "by Friday", "next week", "2024-10-01"
- **Version / feature flags**: "v2", "--no-verify"
- **Numbers / prices / limits**: "$5,900", "4 people", "max 50 devices"

These references land ONLY in `.context/prompt-analysis-N.md` for the current turn.

### 4.5 Risks + ambiguities

Where is the prompt unclear? What should you ask back about before starting?

- Ambiguous references: "that file" (which?), "the integration" (which?)
- Missing values: price without currency, number without unit
- Conflicts with existing rules: "contrary to CONTRIBUTING.md"
- Destructive actions: `rm -rf`, `git reset --hard`, DB drops
- Implicitly risky: "ship straight to prod", "without tests"
- Scope-creep risk: "and then quickly also..."

### 4.6 Future Work / Deferred ideas

Catches "do-it-later" suggestions that are NEITHER current requirements (4.1) NOR rejections (4.3). This is the dimension where deferred ideas leak when missed — trigger patterns are deliberately wide.

Trigger patterns:

- **Deferral (DE/EN)**: "later", "someday", "not now", "for now", "next release", "in v2", "when we have time"
- **Soft-suggestion (modal verbs)**: "we could", "would be nice", "could give an option", "should we also"
- **Inspiration**: "for inspiration", "to draw from", "look at this repo for ideas", "I like the idea of"
- **Speculation**: "maybe we should", "perhaps", "if we had time for"

**Routing (universal, all workspace types)**: 4.6 items go into `docs/BACKLOG.md` under a Future-style section. Section name varies by workspace convention:

- Generic / no project marker → `## Ideas` (auto-create if missing)
- Project with established convention → `## Future` or `## Someday` (per project config)

**4.6 item format** (verbatim quote is mandatory, like 4.1):

```markdown
## $TS - <Title>

> "<verbatim quote from the prompt>"

**What to do:** <one-sentence hint> or "TBD".
**Status:** Future. **Source:** $SOURCE.
```

**Duplicate check:** before writing, grep for the verbatim opening phrase in the BACKLOG. If already present → SKIP + log in notes.md.

**Inspiration URLs from 4.4:** if a 4.6 item references external URLs, include the URLs in the 4.6 entry (otherwise they get lost).

**Disambiguation:**
- 4.1 vs 4.6: imperative "ship X" → 4.1. Soft "we could X" → 4.6.
- 4.3 vs 4.6: "no X" / "instead Y" → 4.3. "X later" / "X as an idea" → 4.6.
- 4.6 is the most important deferral bucket. When in doubt, prefer 4.6 over nothing.

### 4.7 Tentative-Action / "Eval-then-decide"

**Catches items that are NOT 4.1 (do-it-now), NOT 4.6 (defer-to-later), and NOT 4.3 (rejected). Instead: "evaluate first, then act based on the result".**

Three sub-cases:
1. **Deep-Dive Request**: user wants a topic investigated, outcome open
2. **Conditional-Execute**: "do it if it's a good idea" — action depends on eval result
3. **Idea-Validation**: user doubts their own idea, wants a check

Trigger patterns:

- `eventuell` / `evtl` / `maybe` / `perhaps` (with a suggestion, NOT with "later")
- `(?)` at sentence end — user putting a suggestion up for discussion
- `(?)` inline — user's own uncertainty, same logic
- "Am I talking nonsense?" / "Is that right?" / "Does that make sense?"
- "deep dive" + topic without a clear action
- "evaluate" / "check" / "consider"

**Routing (universal, all workspace types)** — see Step 5.4.5:
- All workspace types → `docs/BACKLOG.md` `## Tentative` (auto-create)

**4.7 item format**:

```markdown
## $TS - <Title>

> "<verbatim quote from the prompt>"

**Eval-Type:** Deep-Dive | Conditional-Execute | Idea-Validation
**What to evaluate:** <concrete check question> or "TBD".
**Action if positive:** <what happens if eval comes out positive>.
**Action if negative:** <drop, defer, or other if negative>.
**Status:** Tentative. **Source:** $SOURCE.
```

**4.6 vs 4.7 disambiguation:**
- 4.6 "for later" = sure to do, just not now → defer
- 4.7 "maybe, not sure if good idea" = uncertain whether to do at all → eval first
- "for later if it turns out to be a good idea" = both, but **primarily 4.7** (eval aspect dominant)

**4.7 items dropped are particularly painful** because they're often core strategy questions that can't be reconstructed from memory. When in doubt, prefer 4.7 routing over nothing.

### 4.8 Implicit Followups / State-Mismatch Detection

**Catches items NOT explicitly stated but that IMPLICITLY follow from the user's statement.** When the user states a fact or mentions a state change, the consequences are often not spelled out — but they follow logically.

**Trigger patterns:**

- **State-change confirmation:** "X is done", "is already through", "is finished", "is live", "works now"
- **Past-tense action:** "I did X", "I renamed X", "I moved X", "I deleted X"
- **Existence statement:** "X is gone", "X doesn't exist anymore"
- **Renames:** "X is now called Y", "X became Y"
- **Status clarifications:** "is already released", "is deployed", "is merged"

**When trigger detected → mismatch-detection pass:**

1. **Identify the state change:** what changed? (Repo name? File path? Config value? Status of a feature?)
2. **Scan workspace for refs to old state:** `grep -rn "<old name or value>" .` (limited to tracked files via `git ls-files`)
3. **For each mismatch found, generate an IMPLICIT 4.1 requirement:**
   ```
   - [implicit-followup] Update <file>:<line> - <old-value> -> <new-value> (Source: user statement "X is done")
   ```
4. **Route the implicit requirements like regular 4.1 items** (in `docs/BACKLOG.md ## Tomorrow` with tag `[implicit-followup]`)

**Generic example:**

User statement: "I renamed `oldproject` to `newproject` on GitHub"

State change: GitHub repo rename.

Mismatch-detection pass:
```
$ git ls-files | xargs grep -l "oldproject" | head
docs/SETUP.md
README.md
.github/workflows/ci.yml
```

Generated 4.1 items:
- `[implicit-followup] Update docs/SETUP.md:42 - oldproject -> newproject`
- `[implicit-followup] Update README.md:N (Install section) - oldproject -> newproject`
- `[implicit-followup] Update remote URL: git remote set-url origin git@github.com:<owner>/newproject.git`

**Edge cases:**

- **Fact unconfirmed** (user asks "is X done?"): verify first (e.g. via API), then run mismatch-detection
- **Renames need old + new name:** if only one is known, ask the user
- **Cross-repo scope:** primarily current repo. Cross-repo refs go in a `docs/DEPENDENCIES.md` file if you maintain one
- **False positives:** "Bot is done" can mean "Bot broken" or "Bot deployed". On ambiguity → 4.7 Tentative-Action instead of 4.8

**Disambiguation:**

- 4.1 explicit: "ship that" — explicit imperative
- 4.6 defer: "do X later" — consciously postponed
- 4.7 tentative: "maybe X" — uncertain whether to do at all
- **4.8 implicit:** "X is done" + UNNAMED followups that LOGICALLY follow

**4.8 items route like 4.1**, with a `[implicit-followup]` tag to make clear they were derived from a user statement, not directly requested. Reviewers can spot-check the inferred work before merging.

## Step 5: route items to domain files (per workspace type)

**Items from 4.1 (Requirements), 4.6 (Future Work), and 4.7 (Tentative-Action) get routed. Items from 4.2 (Questions) and 4.3 (Rejections) stay in `prompt-analysis-N.md` only and are NOT written to domain files.** Rationale: questions + answers are persisted in the conversation transcript anyway, and prompt-analysis is committed via the session-log finalize hook — sufficient persistence, no separate domain-file entry needed. **Exception: rejections with architectural character** (e.g. "we are NOT using Postgres") may be routed by a project-specific classifier as draft ADRs. 4.6 items route UNIVERSALLY into `docs/BACKLOG.md` Future-style section (Step 5.4). 4.7 items route UNIVERSALLY into `docs/BACKLOG.md ## Tentative` (Step 5.4.5).

### 5.1 Project-specific routing (delegate)

If your workspace has a project-specific classifier (e.g. `/parse-<projectname>` skill that knows your project's category taxonomy), delegate the 4.1 items to it. The classifier knows which items go to per-area concept files, which to BACKLOG, which become draft ADRs, and which deserve a full plan-file. See `docs/examples/` for a worked case study.

Example invocation (auto-hook context):

```
Invoke Skill: parse-<projectname>
Args: [inline text of 4.1 requirements, one item per block, with verbatim quote]
```

The delegate logs its result to `.context/notes.md` and returns a table of files written. parse-prompt accepts the result without double-logging.

### 5.2 Generic routing

Write 4.1 items into `docs/BACKLOG.md`. Create the file if missing with header:

```markdown
# Backlog

Append-only list of open tasks. Newest at top.

---
```

Format per item:

```markdown
## $TS — <Title>

> „<verbatim quote>"

**What to do:** <action description>.
**Status:** Open.
**Source:** $SOURCE.

---
```

### 5.4 When 4.6 Future Work is detected (universal)

Per 4.6 item:

1. Determine the future-style section name (project-config-driven, default `## Ideas`):
   - Generic → `## Ideas`
   - Project conventions: `## Future` or `## Someday` if the project uses those
2. If `docs/BACKLOG.md` doesn't exist → create with header (Step 5.2 template)
3. If the section doesn't exist → append at end of file
4. Append the verbatim entry in the 4.6 format (Step 4.6), **newest-top** within the section
5. Duplicate check: grep for the first 30-50 chars of the verbatim quote. Match → SKIP + log "duplicate skipped: future" in notes.md
6. Carry forward inspiration URLs from 4.4 (otherwise they get lost)

### 5.4.5 When 4.7 Tentative-Action is detected (universal)

Per 4.7 item:

1. Section is always `## Tentative` (universal, no per-workspace naming)
2. If `docs/BACKLOG.md` doesn't exist → create with header (Step 5.2 template)
3. If `## Tentative` doesn't exist → append at end of file
4. Use the 4.7 format from Step 4.7 (Eval-Type / What to evaluate / Action if positive / Action if negative / Status: Tentative). Newest-top
5. Duplicate check: grep for the first 30-50 chars of the verbatim quote. Match → SKIP + log "duplicate skipped: tentative" in notes.md
6. Carry forward inspiration URLs from 4.4

**4.7 drops are particularly painful** — when in doubt, prefer 4.7 routing over nothing.

### Rules (all workspace types)

- **Verbatim**: never reformulate quotes, never shorten, never typo-correct
- **Use language-appropriate quote marks** in domain files (curly DE „..." or curly EN "..." per project convention)
- **Newest-top** in BACKLOG.md within Tomorrow / Now / Soon sections
- **Duplicate check**: before writing, grep for key phrases or IDs. If an identical item already exists → SKIP + log in notes.md
- **Don't touch** CHANGELOG / ROADMAP / REGISTRY — those are human-maintained or owned by the ship pipeline. parse-prompt only writes prompt-analysis-N.md + (via routing) BACKLOG.md / project domain files / notes.md

## Step 5.5: Per-Item Routing (interpretation-based)

**Why interpretation, not raw text?** A single user prompt often contains multiple items. Each item benefits from its own routing recommendation. But raw item text alone is often too sparse — "react to that" yields 0 candidates without context. The fix: prepend an **interpretation** of the item (workspace tag + subject tags + action verbs + referenced entities) before routing.

Per item from 4.1 (Requirements), 4.6 (Future Work), and 4.7 (Tentative-Action):

### Step A: generate interpretation

Read the item + the conversation context (what was the previous turn? Which PRs/files were referenced? What's the active workspace?). Produce a **one-line interpretation** in the format:

```
<workspace-tag> <subject-tags> <action-verbs> <referenced-entities>
```

Examples:

| Raw item | Interpretation | Reasoning |
|---|---|---|
| "react to that" (in PR-review context) | `frontend timeline review verify checklist pr-42` | workspace=frontend (cwd), subject=timeline (PR content), action=review/verify, entity=pr-42 |
| "fix that" (in a header-component bug context) | `frontend header-component fix bug` | workspace=frontend, subject=header-component, action=fix |
| "ship everything" | `<workspace> ship pr commit push deploy` | action-only fallback when no subject |
| "we could add theming options later" | `<workspace> theming future-work styles` | 4.6, deferral, subject=theming |
| "maybe docs cleanup" | `<workspace> docs cleanup tentative evaluate` | 4.7, action=cleanup, eval-aspect |

### Step B: call route_text() with the interpretation

```python
import sys; sys.path.insert(0, "<install-root>/lib")
import routing
result = routing.route_text(item_text, context_prefix="frontend timeline review verify")
```

Library defaults: `MAX_CANDIDATES=5, MIN_SCORE=1.5`.

### Step C: write the routing block into prompt-analysis-N.md

```markdown
## Item Routing (per-item, interpretation-based)

### Item 1 (4.1): "<verbatim opening, truncated to 80 chars>"
- **Raw text:** <full verbatim>
- **Interpretation:** "<workspace-tag> <subject-tags> <action-verbs> <entities>"
- **Routing:** intent=<intent>, workspace=<dom>, complexity=<1-5>
- **Top candidates:**
  1. [SKILL] <name> (score X.Y, domain Z): <description-truncated>
  2. [AGENT] <name> (score X.Y, domain Z): <description-truncated>
  ...

### Item 2 (4.7): ...
```

### Side-effect status

Step 5.5 writes **nothing** to routing.db (per-item logging would be DB noise). Writes **nothing** to domain files. Output goes **only** into prompt-analysis-N.md. Recommendation-only.

## Step 6: analysis report (incrementally numbered) in `.context/prompt-analysis*.md`

This report is **created per turn** with an incrementing suffix — NEVER overwritten. Every analysis is a record that should survive into future sessions.

**Tripwire integration:** the `UserPromptSubmit` hook writes a tripwire file `.context/.parse-prompt-tripwire`. A `PreToolUse` hook blocks Write/Edit until a fresh `.context/prompt-analysis-<N>.md` is written. Writing the analysis file itself is the operation that clears the tripwire (the hook detects the target path and removes the tripwire). Read/Grep/Glob/Bash remain unblocked.

**Filename rule:**
- First analysis in `.context/`: `prompt-analysis.md`
- Second: `prompt-analysis-2.md`
- Third: `prompt-analysis-3.md`
- Then: `-4.md`, `-5.md`, ...

**Implementation:** count existing `.context/prompt-analysis*.md` files. Write to the next free slot.

```
n = count(.context/prompt-analysis.md) + count(.context/prompt-analysis-*.md)
if n == 0: $ANALYSIS_PATH = .context/prompt-analysis.md
else:      $ANALYSIS_PATH = .context/prompt-analysis-<n+1>.md
```

`.context/` is gitignored. The session-log Stop hook copies all `prompt-analysis*.md` files into a session-log directory at session end (see `docs/SESSION-LIFECYCLE.md`).

Format:

```markdown
# Prompt Analysis - $TS

Source: $SOURCE
Workspace: $WORKSPACE_TYPE

## Intent (your summary)

1-2 sentences: what is the user actually trying to accomplish in this turn?

## Explicit Requirements (N)

- Title - Status
- ...

## Questions (N)

- Title
- ...

## Decisions / Rejections (N)

- Title
- ...

## Context References

- **Paths**: ...
- **Entities/IDs**: ...
- **URLs**: ...
- **Credentials/Secrets** ⚠️: ...
- **Names/People/Places**: ...
- **Dates**: ...

## Risks / Ambiguities

- Description - clarification suggestion
- ...

## Future Work / Deferred Ideas (N)

- ...

## Tentative-Action / Eval-Then-Decide (N)

- ...

## Implicit Followups / State-Mismatch (N)

- ...

## Item Routing (per-item)

- ...

## Proposed Plan

Numbered steps following from the dimensions above.
```

This file is for the AGENT in the current turn, not for the user. Keep it tight — for trivial prompts, leave most sections empty.

## Step 7: security flags

If **Step 4.4** found cleartext credentials (recognized by patterns like "password", "token", "api-key", "secret", or key-value pairs with high entropy):

1. In `.context/prompt-analysis.md`, mark the ⚠️ "Credentials/Secrets" section in bold with a warning:
   ```
   ⚠️ **Cleartext credentials in prompt detected**: "<verbatim>".
   → don't write to git-tracked files without redaction
   → remind the user to rotate the credential later
   ```
2. Add a line to `.context/notes.md`:
   ```
   ⚠️ Security flag: cleartext credential in prompt ($TS) — see prompt-analysis.md
   ```

**Don't** mask the cleartext credential in the verbatim quote (quote fidelity > masking). But flag it separately.

## Step 8: log to `.context/notes.md`

Append:

```markdown
## /parse-prompt - $TS
- Input: $SOURCE
- Workspace: $WORKSPACE_TYPE
- $a Reqs, $b Questions, $c Decisions
- Routing: $a items → [list of files written, e.g. "docs/BACKLOG.md (2 items)"]
- Full capture: $ANALYSIS_PATH (e.g. .context/prompt-analysis-3.md)
```

For silent-skip (input has nothing actionable):

```markdown
## /parse-prompt - $TS
- Input: $SOURCE
- 0 actionable entries (skip — pure conversation, only prompt-analysis-N.md written)
```

## Step 9: output

- **Auto-hook context** (the normal case): **no text output to the user**. Parse silently, write prompt-analysis-N.md + domain files, continue with the main task. The user shouldn't see a table on every prompt.
- **Manual invocation** (`/parse-prompt` typed by the user): show a short table with category / title / routing-target / status, plus a pointer to the analysis file.
- **Security flag active**: emit ONE line in auto-mode: `⚠️ Cleartext credential in prompt detected, see .context/prompt-analysis-N.md`.

---

## Quick rules

1. **8 dimensions, not just requirements** — Requirements + Questions + Rejections + Context + Risks + Future Work + Tentative + Implicit Followups (all in `prompt-analysis-N.md`)
2. **Verbatim quotes** — never reformulate, never typo-correct
3. **`prompt-analysis-N.md` = full per-turn capture** (all dimensions + plan, incrementally numbered, never overwritten). Copied to the session-log directory at session end (see `docs/SESSION-LIFECYCLE.md`)
4. **Items from 4.1 / 4.6 / 4.7** route to domain files:
   - Project-specific → delegate to project classifier
   - Generic → `docs/BACKLOG.md`
5. **Items from 4.2 / 4.3** stay in `prompt-analysis-N.md` only — no separate persistence needed
6. **Auto-hook: silent** except for security flags
7. **Silent-skip** on null entries (`ok`, `thanks`, pure status questions): write prompt-analysis-N.md with empty sections + log "0 actionable" to notes.md
8. **Security flag** on cleartext credentials: warn but don't mask the verbatim quote
9. **Don't touch** CHANGELOG / ROADMAP / REGISTRY — those are human-maintained or owned by the ship pipeline
10. **Duplicate check on routing**: before writing to a domain file, grep for key phrases / IDs. If already present → SKIP + log "duplicate skipped" in notes.md
11. **Exact timestamp + TZ**: `$TS` via `date '+%Y-%m-%d %H:%M %Z'` (local time + TZ suffix like `CEST` / `CET` / `UTC`). NEVER approximate. If the tripwire blocks Bash, write prompt-analysis-N.md first with `$TS` placeholder string, update after the first `date` call.
