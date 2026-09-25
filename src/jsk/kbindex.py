#!/usr/bin/env python3
"""Index a career knowledge base, and rank its projects against one posting.

Retired as `jsk index`: the career is career/kb.ttl, ranked by `jsk match` and read with
`jsk kb view`. The module stays this release only because `jsk migrate` reads the
Markdown with it; release N+1 deletes it with `jsk migrate` and the `migrate` extra.

Usage: python -m jsk.kbindex <user-knowledgebase.md> [--rank <posting.md>] [--today YYYY-MM-DD]
       --rank     also score every project against the posting's requirements
       --today    the date recency and experience are measured to (default: today)

Exit 0 = printed. Exit 1 = the knowledge base or the posting could not be read as
written, or markdown-it-py and pyyaml are not installed - nothing was printed but the
reason. Exit 2 = called wrongly.

The index is generated, never stored: line numbers move on every edit, so a kept copy
would be wrong after the first answer and nothing would notice. It is the overview an
agent reads instead of the whole file - every section and entry with its line range,
the tags the ranking runs on, the vocabulary a requirement has to be written in - so
that it opens only the ranges a verdict needs.

The ranking is the table in jsk-tailor-analyst.md, computed rather than recited. Every
input is an exact string or a number in a block, so nothing in it needs judgement,
and a model doing 900 lookups in its head was the slowest step of a tailoring run.

markdown-it-py finds the headings - it knows a `###` inside a code fence or an HTML
comment is not one - and pyyaml reads the blocks. Both are the optional `index` extra.
What neither can do is know the spec, so every field the ranking reads is checked by
type and range and refused by entry name: a project that silently fails to parse
scores as absent evidence on every posting.
"""
import datetime
import re
import sys

from .cliutil import docstring_usage, wants_help

try:
    import yaml
    from markdown_it import MarkdownIt
except ImportError:                                 # the optional `index` extra
    yaml = MarkdownIt = None

# Most senior first. The order is the ranking: a project at or above the posting's
# level earns the seniority point.
SENIORITY = ["architecture-ownership", "product-ownership", "platform-design",
             "team-leadership", "technical-ownership", "hands-on-senior", "hands-on",
             "junior"]

WEIGHTS = {"required": 3, "preferred": 1, "implicit": 0}

# Ranking rows that list every missed term. A resume leads with its top few projects;
# the rest of the missed terms are the Coverage table read the other way.
TOP_MISSED = 5


class KBError(Exception):
    """The file is not in the shape the spec describes. Carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


# --- reading ----------------------------------------------------------------

def load_yaml(text, where, first_line, fix="fix the block; kb-spec.md shows each one's shape"):
    """One block as a mapping. `first_line` numbers a syntax error in the file's terms."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        at = f", line {first_line + mark.line}" if mark else ""
        raise KBError(f"{where}{at}: not valid YAML - {getattr(exc, 'problem', None) or exc}",
                      fix) from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise KBError(f"{where}: the block is not `key: value` lines", "kb-spec.md shows the shape")
    return data


def frontmatter(text, what):
    """(the --- block, the text with that block blanked so line numbers still hold)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        raise KBError(f"{what}'s frontmatter never closes", "end it with a --- line")
    # The usual cause is a title with a colon in it, written bare.
    front = load_yaml("\n".join(lines[1:closing]), f"{what}'s frontmatter", 2,
                      'quote any value holding a colon - title: "Engineer II: Payments"')
    return front, "\n" * (closing + 1) + "\n".join(lines[closing + 1:])


def read_kb(text):
    """Headings with line ranges, and each entry's first yaml block. 1-based lines."""
    front, body = frontmatter(text, "the knowledge base")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    tokens = MarkdownIt("commonmark").parse(body)
    heads, fences = [], []
    for k, tok in enumerate(tokens):
        # ATX only: a paragraph above a --- rule is a setext heading to CommonMark.
        if tok.type == "heading_open" and tok.markup in ("##", "###"):
            heads.append([tok.map[0] + 1, len(tok.markup), tokens[k + 1].content.strip()])
        elif tok.type == "fence":
            last = lines[tok.map[1] - 1].strip() if tok.map[1] - 1 > tok.map[0] else ""
            if not last.startswith(tok.markup):
                raise KBError(f"the code fence at line {tok.map[0] + 1} never closes, so "
                              "everything below it would vanish from the index",
                              "close every ``` fence")
            # A fence cannot open inside a fence of its own length, so a line that
            # looks like one means an earlier fence lost its closer and has
            # swallowed the headings in between - the next block's ``` closed it.
            for i, inner in enumerate(tok.content.split("\n")):
                opener = re.match(r"\s*(`{3,}|~{3,})\S", inner)
                if opener and opener.group(1)[0] == tok.markup[0] \
                        and len(opener.group(1)) >= len(tok.markup):
                    raise KBError(f"the code fence at line {tok.map[0] + 1} never closes: "
                                  f"line {tok.map[0] + 2 + i} opens another inside it, and "
                                  "everything between would vanish from the index",
                                  "close every ``` fence")
            fences.append((tok.map[0] + 1, tok.info.strip(), tok.content))

    for k, head in enumerate(heads):
        end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
        while end > head[0] and not lines[end - 1].strip():
            end -= 1
        head.append(end)

    sections, current = [], None
    for line_no, level, title, end in heads:
        if level == 2:
            current = {"title": title, "start": line_no, "end": end, "entries": []}
            sections.append(current)
        elif current is not None:
            current["end"] = end
            block = next(((n, c) for n, info, c in fences
                          if info == "yaml" and line_no < n <= end), None)
            current["entries"].append({
                "title": title, "start": line_no, "end": end, "yaml": block,
                "body": [(n, lines[n - 1]) for n in range(line_no + 1, end + 1)]})
    return front, {s["title"]: s for s in sections}, sections


def entries_with_blocks(section, kind):
    parsed = []
    for entry in section["entries"]:
        if entry["yaml"] is None:
            raise KBError(f"## {section['title']}: `### {entry['title']}` (line {entry['start']}) "
                          f"has no ```yaml block",
                          f"every {kind} carries its block; the index cannot skip one quietly")
        line, content = entry["yaml"]
        block = load_yaml(content, f"`### {entry['title']}`", line + 1)
        if not block.get("id"):
            raise KBError(f"`### {entry['title']}` (line {entry['start']}) has no id: in its block",
                          "write the id the heading carries in backticks")
        parsed.append({**entry, "block": block})
    return parsed


def as_int(block, key, where, low, high):
    raw = block.get(key)
    try:
        value = None if isinstance(raw, bool) else int(str(raw))
    except (TypeError, ValueError):
        value = None
    if value is None:
        raise KBError(f"{where}: `{key}` is {raw!r}, not a whole number",
                      f"write {key}: as an integer")
    if not low <= value <= high:
        raise KBError(f"{where}: `{key}: {value}` is outside {low}-{high}",
                      f"{key} runs {low} to {high}")
    return value


def projects_of(sections):
    section = sections.get("Projects")
    if section is None:
        raise KBError("there is no ## Projects section", "the headings are fixed; see kb-spec.md")
    projects = entries_with_blocks(section, "project")
    for p in projects:
        where = f"{p['block']['id']} (line {p['start']})"
        b = p["block"]
        p["strength"] = as_int(b, "strength", where, 1, 5)
        p["recency"] = as_int(b, "recency", where, 1900, 2200)
        if b.get("seniority") not in SENIORITY:
            raise KBError(f"{where}: seniority {b.get('seniority')!r} is not one of the eight",
                          ", ".join(SENIORITY))
        for key in ("capabilities", "technologies", "domains"):
            value = b.get(key) or []
            # YAML reads a bare `no` or `on` as a boolean: a term that stopped being
            # a string would never match, so it is refused rather than dropped.
            if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
                raise KBError(f"{where}: `{key}` is not a list of terms: {value!r}",
                              f"write {key}: [a, b], quoting any term YAML reads as "
                              "true, false or a number")
            p[key] = value
        if b.get("retired") not in (None, True, False):
            # `retired: "true"` is a string: ignoring it would rank a retired project.
            raise KBError(f"{where}: retired is {b.get('retired')!r}",
                          "write retired: true, unquoted - or leave the key out")
        p["retired"] = b.get("retired") is True
    return projects


def month(value, where, end=False):
    match = re.match(r"^(\d{4})(?:-(\d{2}))?", str(value or ""))
    if not match:
        raise KBError(f"{where}: {value!r} is not a YYYY-MM date", "write start: YYYY-MM")
    return int(match.group(1)) * 12 + int(match.group(2) or (12 if end else 1)) - 1


def experience(roles, today):
    """Months covered by the union of every role's dates. Overlaps count once."""
    spans, notes = [], []
    now = today.year * 12 + today.month - 1
    for r in roles:
        b, where = r["block"], f"{r['block']['id']} (line {r['start']})"
        if not b.get("start"):
            notes.append(f"{b['id']} has no start date and is not counted")
            continue
        first = month(b["start"], where)
        if b.get("end"):
            last = month(b["end"], where, end=True)
        elif b.get("state") == "ongoing":
            last = now
        else:
            # `unknown` - or ended, or unstated - with no end date. Running it to
            # today would inflate the one number an eligibility gate compares.
            notes.append(f"{b['id']} has no end date and state {b.get('state')!r}, "
                         f"so it is not counted")
            continue
        spans.append((first, last))
    covered, cursor = 0, None
    for first, last in sorted(spans):
        if cursor is not None and first <= cursor:
            if last > cursor:
                covered += last - cursor
                cursor = last
            continue
        covered += last - first + 1
        cursor = last
    return covered, notes


# --- the posting --------------------------------------------------------------

def read_posting(text):
    """The posting's frontmatter, with its requirements checked."""
    front, _ = frontmatter(text, "the posting")
    if not front:
        raise KBError("the posting has no frontmatter", "posting.md opens with a --- block")
    reqs = front.get("requirements") or []
    if not isinstance(reqs, list) or not all(isinstance(r, dict) for r in reqs):
        raise KBError("requirements is not a list of mappings",
                      "one `- value:` item per requirement, as jsk-tailor-analyst.md shows")
    for n, req in enumerate(reqs, 1):
        if not isinstance(req.get("value"), str) or not req["value"]:
            raise KBError(f"requirement {n} has no value", "every requirement names its term")
        if req.get("necessity") not in WEIGHTS:
            raise KBError(f"requirement {req['value']!r}: necessity {req.get('necessity')!r}",
                          "necessity is required, preferred or implicit")
    if not reqs:
        raise KBError("the posting has no requirements to rank against",
                      "the analyst writes requirements[] first")
    return front


# --- the ranking --------------------------------------------------------------

def recency_points(year, today):
    age = today.year - year
    return 1.0 if age <= 3 else 0.5 if age <= 6 else 0.0


def rank(projects, posting, today):
    reqs = posting["requirements"]
    level = posting.get("seniority")
    level_at = SENIORITY.index(level) if level in SENIORITY else None
    rows = []
    for p in projects:
        if p["retired"]:
            continue
        terms = set(p["capabilities"]) | set(p["technologies"])
        matched = [r for r in reqs if r["value"] in terms and r["necessity"] != "implicit"]
        missed = [r["value"] for r in reqs if r["necessity"] == "required"
                  and r["value"] not in terms]
        rec = recency_points(p["recency"], today)
        sen = 1 if level_at is not None and SENIORITY.index(p["block"]["seniority"]) <= level_at else 0
        score = sum(WEIGHTS[r["necessity"]] for r in matched) + 2 * p["strength"] + rec + sen
        why = [r["value"] + ("" if r["necessity"] == "required" else " (preferred)")
               for r in matched]
        why.append(f"strength {p['strength']}")
        if rec:
            why.append("recent" if rec == 1 else "recency half")
        if sen:
            why.append("seniority-match")
        rows.append({"id": p["block"]["id"], "score": score, "matched": why, "missed": missed,
                     "strength": p["strength"], "recency": p["recency"]})
    rows.sort(key=lambda r: (-r["score"], -r["strength"], -r["recency"], r["id"]))
    return rows


def number(score):
    return str(int(score)) if score == int(score) else f"{score:.1f}"


# --- output -------------------------------------------------------------------

def vocabulary(section):
    groups = {}
    if section is None:
        return groups
    for entry in section["entries"]:
        terms = []
        for _, line in entry["body"]:
            terms += re.findall(r"^\s*-\s+`([^`]+)`", line)
        if terms:
            groups[entry["title"]] = terms
    return groups


def table_rows(section, lines_of):
    for n, line in lines_of(section):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and cells and cells[0] not in ("id", "") \
                and not set(cells[0]) <= set("-: "):
            yield n, cells


def section_lines(text):
    all_lines = text.split("\n")
    return lambda s: ((n, all_lines[n - 1]) for n in range(s["start"] + 1, s["end"] + 1))


def build(text, posting_text=None, today=None):
    today = today or datetime.date.today()
    front, by_title, sections = read_kb(text)
    projects = projects_of(by_title)
    roles = entries_with_blocks(by_title["Roles"], "role") if "Roles" in by_title else []
    lines_of = section_lines(text)
    total = len(text.rstrip("\n").split("\n"))

    out = [f"# Index - user-knowledgebase.md ({total} lines, kb: {front.get('kb', '?')})", "",
           "Generated; line numbers are true now and stale after the next edit. Read an entry",
           "with `Read offset=<start> limit=<end - start + 1>`.", "", "## Sections", "",
           "| Section | Lines | Entries |", "|---|---|---|"]
    for s in sections:
        out.append(f"| {s['title']} | {s['start']}-{s['end']} | {len(s['entries']) or ''} |")

    out += ["", "## Roles", ""]
    for r in roles:
        b = r["block"]
        out.append(f"- `{b['id']}` L{r['start']}-{r['end']} | {b.get('title', '')} | "
                   f"{b.get('start', '?')} to {b.get('end') or b.get('state', 'now')} | "
                   f"{b.get('seniority', '')} | {b.get('status', '')}")
    months, notes = experience(roles, today)
    out.append("")
    out.append(f"Experience: {months // 12}y {months % 12}m, the union of every role's dates "
               f"to {today.isoformat()} - overlaps count once.")
    out += [f"- {n}" for n in notes]

    out += ["", "## Projects", ""]
    for p in projects:
        b = p["block"]
        name = p["title"].split(" `")[0]
        out.append(f"- `{b['id']}` L{p['start']}-{p['end']} | {name} | {b.get('role', '')} | "
                   f"strength {p['strength']} | {p['recency']} | {b['seniority']} | "
                   f"{b.get('status', '')}{' | RETIRED' if p['retired'] else ''}")
        out.append(f"  - capabilities: {', '.join(p['capabilities'])}")
        out.append(f"  - technologies: {', '.join(p['technologies'])}")
        if p["domains"]:
            out.append(f"  - domains: {', '.join(p['domains'])}")
        out.append(f"  - headline_metric: {b.get('headline_metric', '')}")

    out += ["", "## Vocabulary", ""]
    for group, terms in vocabulary(by_title.get("Vocabulary")).items():
        out.append(f"- {group}: {', '.join(terms)}")
    used = sorted({t for p in projects for t in p["technologies"]})
    out.append(f"- technologies in use: {', '.join(used)}")

    if "Skills" in by_title:
        out += ["", "## Skills", ""]
        for _, line in lines_of(by_title["Skills"]):
            if re.match(r"^\s*-\s+\S", line):
                out.append("- " + line.strip()[2:])

    if "Metrics" in by_title:
        out += ["", "## Metrics", ""]
        for n, cells in table_rows(by_title["Metrics"], lines_of):
            subject = cells[1] if len(cells) > 1 else ""
            status = cells[-1] if len(cells) > 2 else ""
            out.append(f"- `{cells[0]}` L{n} | {subject} | {status}")

    if "Open questions" in by_title:
        open_rows = [(n, c) for n, c in table_rows(by_title["Open questions"], lines_of)
                     if len(c) >= 5 and not c[4]]
        out += ["", f"## Open questions - {len(open_rows)} unanswered", ""]
        for n, cells in open_rows:
            out.append(f"- `{cells[0]}` L{n} | about {cells[2]}")

    if posting_text is not None:
        posting = read_posting(posting_text)
        reqs = posting["requirements"]
        known = {t for terms in vocabulary(by_title.get("Vocabulary")).values() for t in terms}
        known |= set(used)
        out += ["", "# Ranking", "",
                f"Against `{posting.get('title', 'the posting')}` at {posting.get('seniority') or 'no stated seniority'}: "
                f"{sum(r['necessity'] == 'required' for r in reqs)} required, "
                f"{sum(r['necessity'] == 'preferred' for r in reqs)} preferred, "
                f"{sum(r['necessity'] == 'implicit' for r in reqs)} implicit (implicit scores nothing).",
                "Required ×3 · preferred ×1 · strength ×2 · recency +1 within 3 years, +0.5 at 4-6 · "
                "seniority +1 at or above the posting's.", "",
                "| Project | Score | Matched | Missed |", "|---|---|---|---|"]
        if posting.get("seniority") not in SENIORITY:
            out.insert(-4, "The posting's seniority is missing or not one of the eight, so no "
                           "project earns the seniority point.")
        # Missed terms in full for the projects a resume leads with; below that the
        # Coverage table says the same thing from the requirement's side.
        for place, row in enumerate(rank(projects, posting, today)):
            missed = (", ".join(row["missed"]) if place < TOP_MISSED
                      else f"{len(row['missed'])} required - see Coverage")
            out.append(f"| {row['id']} | {number(row['score'])} | {', '.join(row['matched'])} | "
                       f"{missed} |")

        out += ["", "# Coverage", "",
                "Which projects carry each requirement's term. A tag is not evidence: a project",
                "whose prose never shows the work is `unevidenced`. Read those ranges.", "",
                "| Requirement | Need | Tagged on | Note |", "|---|---|---|---|"]
        for r in reqs:
            carriers = [p["block"]["id"] for p in projects if not p["retired"]
                        and r["value"] in set(p["capabilities"]) | set(p["technologies"])]
            note = "" if r["value"] in known else "not in the vocabulary"
            out.append(f"| {r['value']} | {r['necessity']} | {', '.join(carriers) or 'none'} | {note} |")
    return "\n".join(out) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2

    options = {}
    for flag in ("--rank", "--today"):
        if flag in argv:
            at = argv.index(flag)
            if at + 1 >= len(argv):
                print(f"{flag} needs a value")
                return 2
            options[flag] = argv[at + 1]
            del argv[at:at + 2]
    if len(argv) != 1:
        print("usage: python -m jsk.kbindex <user-knowledgebase.md> [--rank <posting.md>] [--today YYYY-MM-DD]")
        return 2
    try:
        today = datetime.date.fromisoformat(options["--today"]) if "--today" in options else None
    except ValueError:
        print(f"--today {options['--today']!r} is not YYYY-MM-DD")
        return 2

    if yaml is None or MarkdownIt is None:
        print("FAIL  jsk.kbindex needs markdown-it-py and pyyaml, and this Python has not got them")
        print('fix:  python -m pip install markdown-it-py pyyaml   (the "index" extra)')
        return 1

    try:
        with open(argv[0], encoding="utf-8") as fh:
            text = fh.read()
        posting = None
        if "--rank" in options:
            with open(options["--rank"], encoding="utf-8") as fh:
                posting = fh.read()
        report = build(text, posting, today)
    except OSError as exc:
        print(f"FAIL  cannot read {exc.filename}: {exc.strerror}")
        return 1
    except KBError as exc:
        print(f"FAIL  {exc}")
        print(f"fix:  {exc.fix}")
        return 1
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
