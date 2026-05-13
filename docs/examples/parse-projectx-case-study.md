# Case Study: a project-specific classifier delegate

This is an illustrative example of a project-specific classifier (`/parse-projectx`) that parse-prompt delegates 4.1 / 4.6 / 4.7 items to. The "ProjectX" name is a placeholder — replace with your project's actual name when you adapt this for your own use.

The pattern below is real and battle-tested in production setups. The specific categories, view-tags, and routing destinations are illustrative — yours will look different. What stays the same is the **shape**: a multi-category classifier that knows where in your project's docs each item type belongs.

---

## Why a project-specific classifier?

parse-prompt's default routing is "everything goes into `docs/BACKLOG.md`". For a small project with a single category that's fine. For a large project with multiple item shapes (UI requirements vs bug reports vs architectural decisions vs deferred ideas), you want sharper routing:

- **UI items** → per-area concept docs that designers + frontend devs read
- **Bugs** → BACKLOG with priority + bug-specific format
- **Architectural decisions** → ADR drafts in `docs/adr/`
- **Strategy/pricing items** → a separate `docs/strategy/` doc
- **Compliance items** → `docs/legal/`
- **Deferred ideas** → BACKLOG `## Future` (still goes to one place, just labeled)

A project-specific classifier knows your project's category taxonomy and routes each item to its right place — without parse-prompt's core needing to know about your domain.

---

## ProjectX (fictional example) — overview

ProjectX is a (fictional) SaaS product. It has:

- A web app with ~20 distinct views (the dashboard, settings, onboarding wizard, etc.)
- A backend API
- A growing ADR collection
- A strategy doc tree
- A legal/compliance doc tree

Documentation lives at:

```
docs/
├── BACKLOG.md
├── ROADMAP.md
├── CHANGELOG.md
├── REGISTRY.md
├── STATUS.md
├── adr/
│   ├── 0001-multi-tenancy.md
│   ├── 0002-api-shape.md
│   └── ...
├── strategy/
│   ├── ROADMAP.md
│   └── BACKLOG.md
├── legal/
│   └── BACKLOG.md
└── product/
    └── views/
        ├── dashboard/
        │   └── CONCEPT.md
        ├── kanban-board/
        │   └── CONCEPT.md
        ├── settings/
        │   ├── profile/CONCEPT.md
        │   ├── team/CONCEPT.md
        │   ├── billing/CONCEPT.md
        │   └── ...
        └── onboarding/
            └── CONCEPT.md
```

---

## Category taxonomy

`/parse-projectx` classifies every input item into one of these categories:

| Category | What it catches | Routing target |
|---|---|---|
| **UX** | UI/visual/interaction requirements (look, feel, layout, responsive) | `docs/product/views/<view>/CONCEPT.md` (Target-State section) |
| **BUG** | Defects, broken behavior, regressions | `docs/BACKLOG.md` (Bug section) with `PROJ-NNN` ID |
| **FEATURE** | New functionality without UI specification | `docs/BACKLOG.md` (Feature section) |
| **BACKEND** | API, DB schema, server, performance, infrastructure | `docs/BACKLOG.md` (Backend section) |
| **STRATEGY** | Pricing, positioning, go-to-market, fundraising | `docs/strategy/ROADMAP.md` or `docs/strategy/BACKLOG.md` |
| **LEGAL** | Privacy, GDPR, ToS, imprint | `docs/legal/BACKLOG.md` |
| **DEVOPS** | Deployment, CI/CD, monitoring, server config | `docs/BACKLOG.md` (DevOps section) |
| **DECISION** | Architectural / pattern / schema decision with trade-offs | `docs/adr/<NNNN>-<slug>.md` as a **draft ADR** |
| **FUTURE** | "Do-it-later" idea, no current commitment (matches parse-prompt 4.6) | `docs/BACKLOG.md ## Future` (newest top, verbatim quote, inspiration URLs preserved) |
| **TENTATIVE** | "Maybe, evaluate first" (matches parse-prompt 4.7) | `docs/BACKLOG.md ## Tentative` |
| **META** | Process / workflow / tooling — not a direct product item | Excluded (mentioned only in `.context/notes.md`) |

**Hybrid items**: an item touching both UX and Backend (e.g. "Show offline indicator only when API is unreachable") routes to BOTH targets with cross-references.

---

## DECISION classifier sub-rule (when ADR vs CONCEPT)

A statement like "rather Y instead of X" or "we use pattern Z" lands as a **draft ADR** only when it has architectural character:

- **ADR-worthy**: data model choice, API shape, auth pattern, library choice, multi-tenancy strategy, sync pattern, storage layer, schema boundary. Short: trade-off with alternatives + long-lived consequences.
- **NOT ADR-worthy**: UX taste (button color, tab order, wording), individual view specs. These go in the Target-State section of the relevant `CONCEPT.md`.

When in doubt: write a draft ADR (the user can later promote it to a CONCEPT) rather than burying an architectural decision in a CONCEPT where nobody finds it later.

---

## Keyword → view-tag mapping (UX category)

For UX items, the classifier needs to know which view each phrase corresponds to. Hand-curated mapping, ~25 rows for ProjectX (your project's mapping will differ):

| Keywords | Target view CONCEPT.md |
|---|---|
| `kanban`, `board`, `columns`, `card` | `docs/product/views/kanban-board/CONCEPT.md` |
| `sprint`, `iteration`, `planning` | `docs/product/views/sprint-planning/CONCEPT.md` |
| `timeline`, `gantt`, `schedule` | `docs/product/views/schedule/CONCEPT.md` |
| `dashboard`, `home`, `overview` | `docs/product/views/dashboard/CONCEPT.md` |
| `command palette`, `cmd+k`, `quick search` | `docs/product/views/command-palette/CONCEPT.md` |
| `login`, `signin`, `password` | `docs/product/views/login/CONCEPT.md` |
| `onboarding`, `setup`, `wizard` | `docs/product/views/onboarding/CONCEPT.md` |
| `profile`, `account settings` | `docs/product/views/settings/profile/CONCEPT.md` |
| `team`, `members`, `permissions`, `roles` | `docs/product/views/settings/team/CONCEPT.md` |
| `billing`, `subscription`, `plan`, `trial` | `docs/product/views/settings/billing/CONCEPT.md` |
| `notifications`, `alerts`, `email digest` | `docs/product/views/settings/notifications/CONCEPT.md` |
| `integrations`, `webhooks`, `slack`, `github` | `docs/product/views/settings/integrations/CONCEPT.md` |
| `theme`, `dark mode`, `appearance` | `docs/product/views/settings/appearance/CONCEPT.md` |
| `analytics`, `metrics`, `reports` | `docs/product/views/analytics/CONCEPT.md` |
| `landing`, `marketing`, `homepage` | `docs/product/views/landing/CONCEPT.md` |
| ... | ... |

Your project's mapping will look completely different — same shape, different keywords + paths.

---

## ID assignment

For each routed item, the classifier assigns a stable ID:

- UX items: `UX-<view-prefix>-NNN`, e.g. `UX-DASH-042`, `UX-BILL-007`
- BUG items: `PROJ-NNN`, monotonically increasing across the project
- FEATURE items: `PROJ-NNN`, same numbering as BUG
- BACKEND items: `PROJ-NNN`
- DECISION drafts: `<NNNN>-<slug>` (4-digit sequential, slug derived from title)

The classifier reads the next available ID from `docs/REGISTRY.md` (or wherever your project tracks ID counters).

---

## Item format per category

### UX item (in CONCEPT.md Target-State section)

```markdown
### UX-DASH-042: [Title]
> "[verbatim or message-faithful paraphrase of the user phrase]"

**What to do:** [clear actionable description]

**Source:** [filename or "inline-text"], YYYY-MM-DD
**Status:** Open
```

Note: for CONCEPT.md sections (which are spec docs, not audit trails), message-faithful paraphrasing is acceptable. Don't change semantic meaning, but feel free to clean up typos or ambiguity. BACKLOG and ADR items, by contrast, keep verbatim quotes for trace-back.

### BUG / FEATURE / BACKEND / DEVOPS item (in BACKLOG.md)

```markdown
## YYYY-MM-DD HH:MM — PROJ-NNN: [Title]

> "[verbatim quote from input]"

**What to do:** [actionable description]
**Category:** Bug | Feature | Backend | DevOps
**Priority:** TBD
**Status:** Open
**Source:** [filename or inline-text]

---
```

### DECISION draft (in `docs/adr/<NNNN>-<slug>.md`)

```markdown
# ADR <NNNN>: [Title]

**Status:** Draft (auto-extracted YYYY-MM-DD, awaiting review)
**Source:** [where this came from]

## Context

[What's the problem this decision addresses? Lift from input + surrounding context.]

## Decision

[The position the user took. Verbatim quote where possible.]

## Consequences

[TBD — to fill in during review.]

## Alternatives considered

[TBD]
```

### FUTURE item (in `## Future` section of BACKLOG.md)

Same format as parse-prompt 4.6 — see `skills/parse-prompt.md` Step 4.6.

### TENTATIVE item (in `## Tentative` section of BACKLOG.md)

Same format as parse-prompt 4.7 — see `skills/parse-prompt.md` Step 4.7.

---

## Workflow

When parse-prompt detects a ProjectX workspace (Step 3 detection rule) and finds 4.1 / 4.6 / 4.7 items in Step 4, it delegates them to `/parse-projectx`:

```
Invoke Skill: parse-projectx
Args: [inline text of the items, one per block, with verbatim quote]
```

The classifier:

1. Reads each item
2. Classifies by keyword + structure → category
3. For UX items: maps keywords → target CONCEPT.md
4. Assigns IDs from `docs/REGISTRY.md`
5. Writes to the right destination file (creating it if missing, appending newest-top)
6. Logs to `.context/notes.md`
7. Returns a table of files written

parse-prompt accepts the result and continues; no double-logging.

---

## Optional: derived state DB

For projects with many items, a DB-backed status view is useful. The pattern:

1. BACKLOG.md / CONCEPT.md / ADR drafts are the **source of truth** (markdown, hand-editable, git-tracked)
2. A periodic ingest step (e.g. `tools/ingest.sh`) parses these markdown files into a SQLite DB
3. A status skill (`/status`) reads the DB to give a snapshot view

Why this works: the markdown stays authoritative (you can hand-edit), the DB is fast for queries ("show me all open backlog items in category X assigned to view Y"). Markdown is the slow path; DB is the fast path. Ingest can be cheap (a few seconds even for thousands of items).

This is opt-in — small projects don't need it.

---

## What to keep / drop when adapting this pattern to your project

**Keep:**
- The category taxonomy idea (multi-category classifier)
- The keyword → view-tag mapping
- The ADR-vs-CONCEPT decision rule
- The verbatim-quote-for-audit / paraphrase-for-spec distinction
- The ID-assignment via central REGISTRY

**Replace:**
- Categories themselves (your project's items are different)
- View-tag keywords (your project has different views/areas)
- Routing target paths (your project's doc layout is different)

**Drop if you don't need them:**
- ADR drafting (small projects don't have ADRs)
- The strategy + legal sub-trees (most projects don't have these)
- The DB-backed status view (only worth it for large projects)
- Hybrid-item cross-referencing (only matters when items span categories)

A small project with one CONCEPT.md and one BACKLOG.md doesn't need a project-specific classifier at all — parse-prompt's default routing is enough.
