"""The Markdown knowledge base reader `jsk migrate` moves a career to kb.ttl with.

It was `jsk index`, which printed an overview of a user-knowledgebase.md and ranked its
projects against a posting. That command is retired - the career is career/kb.ttl,
ranked by `jsk match` and read with `jsk kb view` - and so is everything here that only
it used. What is left is the reader: `jsk migrate` runs it over the Markdown and checks
that the graph it wrote says the same thing. Release N+1 deletes this module with
`jsk migrate` and the `migrate` extra; nothing on the graph side imports it.

markdown-it-py finds the headings - it knows a `###` inside a code fence or an HTML
comment is not one - and pyyaml reads the blocks. Both are the optional `migrate` extra.
What neither can do is know the spec, so every field the reader keeps is checked by
type and range and refused by entry name: a project that silently fails to parse
would migrate as absent evidence.
"""
import re

from .graph.scoring import SENIORITY, WEIGHTS
from .graph import scoring

try:
    import yaml
    from markdown_it import MarkdownIt
except ImportError:                                 # the optional `migrate` extra
    yaml = MarkdownIt = None


class KBError(Exception):
    """The file is not in the shape the spec describes. Carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


# --- reading ----------------------------------------------------------------

def load_yaml(text, where, first_line, fix="fix the block; docs/legacy-kb-spec.md shows each one's shape"):
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
        raise KBError(f"{where}: the block is not `key: value` lines", "docs/legacy-kb-spec.md shows the shape")
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
        raise KBError("there is no ## Projects section", "the headings are fixed; see docs/legacy-kb-spec.md")
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


def experience(roles, today):
    """graph.scoring.experience over the Markdown's roles, a date that is not one
    refused as a KBError with its fix, like every other field this reader checks."""
    try:
        return scoring.experience(roles, today)
    except ValueError as exc:
        raise KBError(str(exc), "write start: YYYY-MM") from None


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
