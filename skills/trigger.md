---
name: trigger
description: "Hand-curated grammar maintenance for parse-prompt. Add a trigger word/phrase to the input-grammar decision tree, optionally extending the route-prompt.py INTENTS regex too. The auto-corpus-pass tool fills in opener tables; this skill curates the override mappings that the heuristic alone misses."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Bash(date *)
---

# /trigger — hand-curated grammar maintenance

Adds a curated trigger (word/phrase) to the `docs/INPUT-GRAMMAR-EXAMPLE.md` decision tree (or your customized version), optionally also to the `hooks/route-prompt.py` INTENTS regex.

**Why this exists.** An auto-corpus-pass over a body of prompt-analysis files produces topic vocabulary (project names, feature areas, file paths) — but it misses semantic markers like `(?)` or `eventuell` that have *meaning* across topics. The auto-pass fills the per-dimension opener tables; this skill curates the high-priority TL;DR decision-tree overrides that the heuristic can't infer alone.

## Inputs

`/trigger <word_or_phrase> [<dimension>]`

- `<word_or_phrase>` — the exact phrase, e.g. `"eventuell"`, `"(?)"`, `"forget it"`
- `<dimension>` (optional) — one of `4.1 4.2 4.3 4.5 4.6 4.7 4.8` or a description like `"Future Work"` / `"Question"` / `"Rejection"`. If omitted, the skill tries to infer from context. On ambiguity, asks the user back.

## Workflow

### Step 1: parse input

- If `<dimension>` is provided, use it
- If missing: search recent prompts (in your session storage, if available — see SESSION_DB_PATH config) for the phrase and try to classify from context
- If unclear: ask ONE clarifying question — `"'<word>' appeared in N prompts, mostly in context X — does it belong in 4.6 Future Work or 4.2 Question?"`

### Step 2: duplicate check

Grep the grammar guide's "TL;DR Decision Tree" section. If `<word>` is already mapped, ask: `"Already mapped as <existing> — update?"`. User can confirm overwrite or skip.

### Step 3: decision-tree update

In your grammar guide (default `docs/INPUT-GRAMMAR-EXAMPLE.md` or wherever you keep your project copy), insert a new row in the "TL;DR Decision Tree" block:

```markdown
| '<word_or_phrase>' (confirmed YYYY-MM-DD) | <dimension> | <rationale or "user-provided"> |
```

Sort: group per dimension, alphabetical within a dimension.

### Step 4 (optional): INTENTS regex extension

If the phrase has a clear intent category (e.g. `"forget it"` = `confirm`, `"evtl"` = `backlog`), additionally extend the `INTENTS` list in `hooks/route-prompt.py`:

```python
("backlog", r"\b(later|someday|...|eventuell|evtl)\b"),
```

Optional — only when the phrase is an unambiguous intent signal (user confirmation recommended).

### Step 5: CHANGELOG entry

Append to your project's CHANGELOG (or the parseprompt CHANGELOG if you're maintaining one):

```markdown
- `docs: input-grammar trigger added` — confirmed: '<word>' → <dimension>. <one-line why>.
```

### Step 6: confirmation message

One short line in the chat:

```
✅ Trigger '<word>' → <dimension> added to grammar guide.
   [optional: INTENTS regex extended]
```

## Edge cases

- **Phrase contains special characters** (e.g. `(?)`, `:)`, `!`): escape in the table if necessary, but keep the raw form because that's what the user actually types
- **Phrase is ambiguous** (e.g. `"mal"` — can be a softener or imperative): mark `dimension = "context-dependent"` and describe both cases in the row
- **Later correction** (`/trigger eventuell 4.5` after an earlier 4.6 mapping): overwrite — delete old row, insert new one

## What does NOT belong here

- Bulk import of a whole word list → separate skill (e.g. `/trigger-bulk`)
- Changes to parse-prompt.md itself → manual or via writing-skills
- Changes to route-prompt.py outside the INTENTS regex → manual

## Examples

```
/trigger eventuell 4.6
→ ✅ 'eventuell' → 4.6 Future Work added to grammar guide.

/trigger "(?)"
→ Question: "'(?)' appeared in N prompts, mostly at sentence-end after a
   suggestion. Does it belong in 4.2 Question (strategic check) or 4.7
   Tentative-Action (idea-validation)?"

/trigger "forget it" confirm
→ ✅ 'forget it' → 4.3 Rejection (intent=confirm in INTENTS regex extended).
```

## Persistence paths

- Main change: your grammar guide (default `docs/INPUT-GRAMMAR-EXAMPLE.md` or your project copy)
- Optional: `hooks/route-prompt.py`
- Always: your project CHANGELOG

## Connection to other skills

- **parse-prompt** reads the grammar guide's decision tree in Step 3.5
- **route-prompt.py** hook uses the INTENTS regex (parallel to the grammar guide)
- **CHANGELOG** logs every change
