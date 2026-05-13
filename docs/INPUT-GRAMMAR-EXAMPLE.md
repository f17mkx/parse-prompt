# Input Grammar Example — template

**This is a template, not a finished grammar.** Fork it, fill it with phrases YOU actually type, and parse-prompt's Step 3.5 will use it to bias dimension classification toward your speech patterns.

The auto-corpus-pass tool (`tools/grammar-corpus-pass.py`) can fill the per-dimension opener tables for you once you've collected ~50+ `prompt-analysis*.md` files. The TL;DR Decision Tree below stays hand-curated — that's where you encode the meaningful semantic markers (`(?)` markers, your own slang for "later", recurring patterns) that the auto-pass can't infer.

The `/trigger` skill is the maintenance tool: `/trigger eventuell 4.6` adds a row to the decision tree below.

---

## TL;DR Decision Tree

The decision tree is the highest-priority anchor. When a prompt phrase matches a row here, route it to that dimension regardless of what the generic Step 4 heuristic would say.

| Phrase | Dimension | Rationale |
|---|---|---|
| `eventuell` / `evtl` / `vielleicht` (with a suggestion, NOT with "later") | 4.7 Tentative-Action | "maybe" + suggestion = needs evaluation, not deferral |
| `(?)` at sentence end | 4.7 Tentative-Action | user putting a suggestion up for discussion |
| `(?)` inline | 4.7 Tentative-Action | user's own uncertainty signal |
| `is it right?` / `am I making sense?` / `does that work?` | 4.7 Tentative-Action | idea-validation sub-type |
| `we could` / `we might` | 4.6 Future Work | soft suggestion, not committed |
| `would be nice to` / `wäre schön` | 4.6 Future Work | aspirational |
| `someday` / `irgendwann` | 4.6 Future Work | explicit deferral |
| `later` / `später` (alone, no eval-aspect) | 4.6 Future Work | explicit deferral |
| `for inspiration` / `to draw from` | 4.6 Future Work | reference material, not a todo |
| `instead of X` / `lieber Y` / `stattdessen Z` | 4.3 Rejection | option-exclusion |
| `not X` / `kein X` | 4.3 Rejection | explicit no |
| `is X done?` / `ist X durch?` | 4.8 Implicit-Followup | trigger mismatch-detection pass |
| `I renamed X to Y` / `X heißt jetzt Y` | 4.8 Implicit-Followup | rename → grep workspace for refs to old name |
| `X is live` / `X is deployed` | 4.8 Implicit-Followup | state change → check for stale refs |
| `ship it` / `los` / `merge it` | (intent=ship in INTENTS) | route to your ship/deploy skill |
| `go` / `yes` / `approved` / `passt` | (intent=confirm in INTENTS) | sign-off |

**Sort rule:** group rows per dimension, alphabetical within a dimension.

**Conflict resolution:** decision-tree (this table, hand-curated) > Step 4 heuristic (generic patterns in the skill). Example: `"maybe docs cleanup"` matches in Step 4 generically as both 4.6 (Speculation: "maybe"-pattern) and 4.7 (Eval-aspect). Decision-tree mapping for `evtl`/`vielleicht`/`maybe` is unambiguous **4.7** → 4.7 wins, item routes to `## Tentative`.

---

## Per-dimension opener fingerprints (auto-generated, refresh via grammar-corpus-pass.py)

These tables are filled by `tools/grammar-corpus-pass.py` from your prompt-analysis corpus. They capture the **top-N opening phrases** per dimension so the heuristic can fall back on actual frequency data when the decision tree doesn't apply.

The skill applies them as a tiebreaker: take the first 4 alpha-tokens (lowercased) of an unclassified phrase, compare against the tables below, the dimension with the strongest match wins.

### 4.1 Explicit Requirements — top openers

(Auto-generated. Re-run `python3 tools/grammar-corpus-pass.py` when your corpus grows by ~50+ analyses.)

| Opener (first 1-3 tokens) | Frequency |
|---|---|
| `add ...` | TBD |
| `change ...` | TBD |
| `fix ...` | TBD |
| `remove ...` | TBD |
| `ship ...` | TBD |
| `update ...` | TBD |
| `mach ...` | TBD |
| `ändere ...` | TBD |
| `entferne ...` | TBD |
| ... | ... |

### 4.2 Questions — top openers

| Opener | Frequency |
|---|---|
| `how ...` | TBD |
| `what ...` | TBD |
| `why ...` | TBD |
| `is it ...` | TBD |
| `did ...` | TBD |
| `wofür ...` | TBD |
| `was macht ...` | TBD |
| ... | ... |

### 4.3 Rejections — top openers

| Opener | Frequency |
|---|---|
| `not ...` | TBD |
| `instead of ...` | TBD |
| `rather ...` | TBD |
| `nicht ...` | TBD |
| `lieber ...` | TBD |
| ... | ... |

### 4.6 Future Work — top openers

| Opener | Frequency |
|---|---|
| `we could ...` | TBD |
| `would be nice ...` | TBD |
| `someday ...` | TBD |
| `for inspiration ...` | TBD |
| `wir könnten ...` | TBD |
| `irgendwann ...` | TBD |
| ... | ... |

### 4.7 Tentative-Action — top openers

| Opener | Frequency |
|---|---|
| `maybe ...` | TBD |
| `eventuell ...` | TBD |
| `evtl ...` | TBD |
| `let's evaluate ...` | TBD |
| `does it make sense ...` | TBD |
| ... | ... |

### 4.8 Implicit Followups — top triggers

| Trigger | Frequency |
|---|---|
| `is X done?` | TBD |
| `I renamed ...` | TBD |
| `X is now Y` | TBD |
| `X is live` | TBD |
| ... | ... |

---

## Top-N bigrams per dimension (auto-generated, fallback)

Fallback heuristic when the opener doesn't match. The corpus-pass tool extracts the most distinctive bigrams per dimension and compares the prompt against them.

(Tables filled by `tools/grammar-corpus-pass.py`.)

---

## How to use this guide

**Adopters:**

1. Fork this file as `docs/INPUT-GRAMMAR.md` (drop the `-EXAMPLE` suffix) in your project — that's the canonical name parse-prompt looks for. The example file stays as-is for reference.
2. Edit the **TL;DR Decision Tree** by hand. Add rows for phrases you find yourself using — the `/trigger` skill is the maintenance tool: `/trigger maybe 4.7` adds a row.
3. Once you have ~50+ `.context/prompt-analysis*.md` files (a few weeks of usage), run `python3 tools/grammar-corpus-pass.py` to auto-fill the per-dimension opener tables.
4. Re-run periodically as your corpus grows. The auto-pass only updates the per-dimension tables, never the TL;DR — that's your hand-curated layer.

**parse-prompt:** the skill reads this guide once at the start of Step 3.5 (if it exists). Decision-tree mapping overrides generic Step 4 heuristic on conflict.

**Graceful degradation:** if the guide is missing, parse-prompt continues with Step 4 alone — no grammar bias. The skill never auto-creates this file.
