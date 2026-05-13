#!/usr/bin/env python3
"""
grammar-corpus-pass.py

Aggregates user phrasings from existing prompt-analysis*.md files across all
session-logs to build the per-dimension opener tables in your input-grammar guide.

Input  : <session-logs-root>/**/prompt-analysis*.md
Output : <out-path>/INPUT-GRAMMAR.md (default: ./docs/INPUT-GRAMMAR.md)

Why: parse-prompt's regex-based intent classifier misses many user phrasings
("please change..." matches no intent and lands as 'unknown'). This script
extracts opening-phrase + bigram patterns per parse-prompt dimension
(4.1 Requirements / 4.2 Questions / 4.3 Rejections / 4.6 Future Work) so the
grammar guide becomes data-driven rather than hand-rolled.

Usage:
  python3 tools/grammar-corpus-pass.py
  python3 tools/grammar-corpus-pass.py --root /path/to/session-logs --out docs/INPUT-GRAMMAR.md
  python3 tools/grammar-corpus-pass.py --top 50 --top-bigrams 30 --samples 8
"""

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path


# Section header patterns — match the variants used across analysis files.
SECTION_PATTERNS = {
    "requirements": re.compile(r"^##\s+(?:Explicit\s+)?Requirements\b", re.M | re.I),
    "questions":    re.compile(r"^##\s+Questions\b", re.M | re.I),
    "rejections":   re.compile(r"^##\s+(?:Decisions\s*/\s*Rejections|Decisions|Rejections)\b", re.M | re.I),
    "future":       re.compile(r"^##\s+(?:Future\s+Work|Deferred)\b", re.M | re.I),
}

# Bullet (- text) and blockquote (> "text") extraction.
BULLET_RE = re.compile(r"^[\s]*-\s+(.+)$", re.M)
QUOTE_RE  = re.compile(r"^>\s*[\"„'`]?(.+?)[\"„'`]?\s*$", re.M)

# Stopwords (English + German) — signal-poor connectors that should be filtered
# out of bigram tables. Adopters: extend this set for your working language.
STOPWORDS = set("""
the a an and or but if then else when while der die das ein eine einen einem einer
auf in zu zum zur und oder als bei mit von nach für ist sind war waren wird werden
ich du er sie es wir ihr mein dein sein unser euer auch nur noch schon mal halt
this that these those which what who whom whose why how where there here not
ist hier da mehr viele mehrere some few many much to of in on at by from into
status open closed offen verbatim quelle source
""".split())


def extract_section(text, pat):
    """Pull the body of a section (header `## Foo`) up to the next `## ` header."""
    m = pat.search(text)
    if not m:
        return None
    start = m.end()
    next_h = re.search(r"^##\s+\S", text[start:], re.M)
    end = start + next_h.start() if next_h else len(text)
    return text[start:end]


def normalize_phrase(s):
    """Strip common parse-prompt prefixes like `R1: `, `[tag] `, bold markers."""
    s = re.sub(r"^[A-Z]\d+\s*[:\.\)\-]\s*", "", s)            # R1: / D2. / Q3) prefix
    s = re.sub(r"^\[[\w\-]+\]\s*", "", s)                     # [tag] prefix
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)                  # **bold** -> bold
    s = re.sub(r"`([^`]+)`", r"\1", s)                        # `code` -> code
    s = re.sub(r"\s+\-\s+Status:.*$", "", s, flags=re.I)      # trailing - Status: Open
    s = s.strip()
    return s


def extract_phrases(content):
    """Return list of normalized phrases from bullets and blockquotes in section."""
    if not content:
        return []
    out = []
    for m in BULLET_RE.finditer(content):
        line = normalize_phrase(m.group(1))
        if line and len(line) > 4:
            out.append(line)
    for m in QUOTE_RE.finditer(content):
        line = normalize_phrase(m.group(1))
        if line and len(line) > 4:
            out.append(line)
    return out


def opening_words(phrase, n=4):
    """First n alpha tokens, lowercased — the 'opener fingerprint'."""
    toks = re.findall(r"[a-zA-ZäöüÄÖÜß]+", phrase.lower())
    if len(toks) < 2:
        return None
    return " ".join(toks[:n])


def bigrams(phrase):
    toks = [t for t in re.findall(r"[a-zA-ZäöüÄÖÜß]+", phrase.lower())
            if t not in STOPWORDS and len(t) > 2]
    return [f"{toks[i]} {toks[i+1]}" for i in range(len(toks) - 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="session-logs",
                    help="Root directory containing session-logs/<date>-<topic>/prompt-analysis*.md")
    ap.add_argument("--out",  default="docs/INPUT-GRAMMAR.md",
                    help="Output file path")
    ap.add_argument("--top",  type=int, default=30, help="Top-N opener phrases per section")
    ap.add_argument("--top-bigrams", type=int, default=20, help="Top-N bigrams per section")
    ap.add_argument("--samples", type=int, default=5, help="Verbatim sample quotes per section")
    args = ap.parse_args()

    root = Path(args.root)
    files = sorted(root.rglob("prompt-analysis*.md"))
    if not files:
        print(f"No prompt-analysis files under {root}")
        return 1

    openers = defaultdict(Counter)
    bgs = defaultdict(Counter)
    samples = defaultdict(list)
    file_count_per_section = defaultdict(int)

    for fp in files:
        try:
            text = fp.read_text(errors="ignore")
        except Exception:
            continue
        for section, pat in SECTION_PATTERNS.items():
            content = extract_section(text, pat)
            phrases = extract_phrases(content)
            if phrases:
                file_count_per_section[section] += 1
            for phr in phrases:
                op = opening_words(phr, n=4)
                if op:
                    openers[section][op] += 1
                for bg in bigrams(phr):
                    bgs[section][bg] += 1
                if len(samples[section]) < args.samples:
                    src = fp.parent.name
                    samples[section].append((phr[:160], src))

    # Write the guide
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Input Grammar Guide")
    lines.append("")
    lines.append(f"**Auto-generated from {len(files)} prompt-analysis files** in `{args.root}`.")
    lines.append("This guide helps `parse-prompt` classify incoming prompts correctly into the 8 dimensions.")
    lines.append("")
    lines.append("Source: `tools/grammar-corpus-pass.py`. Re-run when the corpus grows materially.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## TL;DR Decision Tree")
    lines.append("")
    lines.append("When parsing a prompt, route phrases by their first 1-3 tokens:")
    lines.append("")
    lines.append("| Opener Pattern | Likely Dimension | Rationale |")
    lines.append("|---|---|---|")
    lines.append("| imperative verb (do, ship, fix, change, remove) | 4.1 Requirements | classic action ask |")
    lines.append("| 'can you' / 'könnten wir' + present | 4.1 Requirements (soft-ask) | polite imperative |")
    lines.append("| 'we could' / 'wir könnten' + 'also' / 'auch' | 4.6 Future Work | speculative add-on |")
    lines.append("| 'how' / 'what' / 'why' / 'wie' / 'was' | 4.2 Questions | direct interrogative |")
    lines.append("| 'should we' / 'sollten wir' / 'would be nice' | 4.6 Future Work | soft suggest |")
    lines.append("| 'instead of X, Y' / 'lieber Y' / 'rather Y' | 4.3 Rejections | preference-with-alternative |")
    lines.append("| 'for later' / 'someday' / 'irgendwann' | 4.6 Future Work | explicit deferral |")
    lines.append("| 'maybe' / 'eventuell' / 'evtl' | 4.7 Tentative-Action | uncertainty + suggestion |")
    lines.append("| 'check this' / 'is this right' | 4.2 Questions or 4.7 Tentative | calibrate by suggestion-aspect |")
    lines.append("| 'X is broken' / 'doesn't work' / 'funktioniert nicht' | 4.1 Requirements (bug) | bug-as-implicit-request |")
    lines.append("| 'please fix' / 'bitte ändern' | 4.1 Requirements | explicit polite request |")
    lines.append("| 'X is done' / 'I renamed Y' / 'X ist durch' | 4.8 Implicit-Followup | trigger mismatch-detection pass |")
    lines.append("")
    lines.append("---")
    lines.append("")

    section_titles = {
        "requirements": "4.1 Requirements (Imperatives + Soft-Asks)",
        "questions":    "4.2 Questions (Explicit + Implicit)",
        "rejections":   "4.3 Rejections (Negations + Preferences)",
        "future":       "4.6 Future Work / Deferrals",
    }

    for section, title in section_titles.items():
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"Aggregated from {file_count_per_section[section]} files containing this section.")
        lines.append("")
        lines.append(f"### Top-{args.top} opener fingerprints (first 4 tokens)")
        lines.append("")
        lines.append("| Count | Opener |")
        lines.append("|---:|---|")
        for op, cnt in openers[section].most_common(args.top):
            if cnt < 2:
                break
            lines.append(f"| {cnt} | `{op}` |")
        lines.append("")
        lines.append(f"### Top-{args.top_bigrams} content bigrams (signal words)")
        lines.append("")
        lines.append("| Count | Bigram |")
        lines.append("|---:|---|")
        for bg, cnt in bgs[section].most_common(args.top_bigrams):
            if cnt < 2:
                break
            lines.append(f"| {cnt} | `{bg}` |")
        lines.append("")
        lines.append(f"### Sample verbatim quotes (first {args.samples})")
        lines.append("")
        for txt, src in samples[section]:
            lines.append(f"- `{txt}` _(from `{src}`)_")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## How to use this guide in parse-prompt")
    lines.append("")
    lines.append("In `parse-prompt.md` Step 3.5, reference this file. When encountering an")
    lines.append("ambiguous phrase during dimension classification:")
    lines.append("")
    lines.append("1. Take the first 4 alpha tokens (lowercased) of the phrase")
    lines.append("2. Compare against the opener tables above per dimension")
    lines.append("3. The dimension whose opener matches most strongly wins")
    lines.append("4. If tie, fall back to the TL;DR Decision Tree heuristics")
    lines.append("5. Edge cases: if no opener matches, classify based on bigram presence")
    lines.append("")
    lines.append("Re-run `tools/grammar-corpus-pass.py` after material corpus growth")
    lines.append("(say >50 new prompt-analysis files) to refresh frequencies.")
    lines.append("")

    out.write_text("\n".join(lines))
    print(f"Wrote {out}")
    print(f"Sections processed: {dict(file_count_per_section)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
