#!/usr/bin/env python3
"""Migrate a Markdown knowledge base to the graph record, one way.

Usage: jsk migrate <user-knowledgebase.md> [--dry-run]
       --dry-run   print every file it would write, and write nothing

The workspace is the folder holding user-knowledgebase.md. It writes career/kb.ttl and
career/log.ttl there (logged as r1, `j:by j:migrate`, so `jsk kb` reads it as clean),
and for each applications/<dir>/: posting.ttl, posting.md as the advert alone, and
application.ttl when the application was frozen. The old posting.md is kept whole as
posting.orig.md. Nothing is deleted: user-knowledgebase.md, log.md, application.md,
gaps.md and resume.json stay where they are.

Exit 0 = migrated (or, with --dry-run, would be). Exit 1 = refused and nothing was
written: career/kb.ttl already exists, the file is not in the shape docs/legacy-kb-spec.md
describes, a value has nowhere to go, the result would not validate, or it would not
read back as what was read; also when markdown-it-py, pyyaml or pyoxigraph is missing.
Exit 2 = called wrongly.

Why it refuses rather than doing its best: a migration that loses a line loses it for
good, because the next thing anyone reads is kb.ttl, not the Markdown it came from.
The Markdown is read into a dictionary of entries - every value it holds, including
the ones the ontology has no field for, which become `j:note`s on their entry. YAML is
read with nothing retyped (0400123456 stays a phone number, NO a country, 8.40 a
grade): the predicate a value lands in decides its type, and numbers keep their
characters. Three checks follow, and any failure refuses:

- the round trip: the graph is written, parsed back and projected into the same
  dictionary, and must equal it, datatype and characters. This proves the writer and
  the parser, not the reader - a value the reader dropped is in neither side.
- coverage, which proves the reader against the Markdown itself: every YAML value was
  handed to a triple or a note and is still spelled out in kb.ttl, and every other
  non-blank line has each of its words in kb.ttl or in log.ttl's note. Section
  headings, HTML comments and the template's placeholders are layout, not content.
  It compares words, not order: it finds a line that vanished, not one reworded.
- `jsk index`'s own reader (kbindex) is run over the Markdown, and its view of the
  projects, roles, years of experience, metrics and questions must equal the same view
  of the graph.

Every write happens after every check: the new files are validated together, in
memory, with the loader `jsk kb` uses, before the first byte lands. kb.ttl is written
last, so a kb.ttl that exists is a migration that finished.
"""
import datetime
import glob
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from .cliutil import docstring_usage, wants_help

ORIG = "posting.orig.md"

# Old id prefix -> the one the ontology and URS use.
RENAMES = {"proj": "prj", "role": "pos", "metric": "met"}

# Old enum values -> URS values, per ontology enum.
ENUM_MAP = {"confidence": {"self-reported": "reported"},
            "authKind": {"work-visa": "employment-visa"}}

KNOWN_SECTIONS = ("Identity", "Positioning", "Work authorization and languages", "Vocabulary",
                  "Organisations", "Roles", "Projects", "Metrics", "Skills", "Education",
                  "Certifications", "Open source", "Open questions")

PLACEHOLDER = re.compile(r"_(None recorded yet|None held|Not captured yet)\._")
COMMENT = re.compile(r"<!--.*?-->", re.S)
ID_IN_HEADING = re.compile(r"^(?P<title>.*?)\s*`(?P<id>[A-Za-z]+_[A-Za-z0-9_\-]+)`\s*(?P<rest>.*)$")
SUB_ITEM = re.compile(r"^\s+[-*]\s+(?P<key>[A-Za-z_][\w-]*):\s*(?P<value>.*)$")
TOP_ITEM = re.compile(r"^[-*]\s+(?P<text>.*)$")
TERM_ITEM = re.compile(r"^\s*[-*]\s+`(?P<term>[^`]+)`\s*(?P<rest>.*)$")
FULL_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATED_DIR = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
PROSE = (("problem", re.compile(r"^\*\*The problem\.?\*\*\s*")),
         ("decision", re.compile(r"^\*\*What I decided\.?\*\*\s*")),
         ("outcome", re.compile(r"^\*\*What changed\.?\*\*\s*")),
         ("bullets", re.compile(r"^\*\*Bullets\.?\*\*\s*$")))
CONTACTS = ("email", "phone", "linkedin", "github", "website")
COVERAGE_SHOWN = 12                     # lost lines named in a refusal; the rest counted
EVENT_COLUMNS = ("date", "event", "channel", "note", "due")

# Language names a KB wrote where BCP 47 wants a tag.
LANGUAGES = {"english": "en", "hindi": "hi", "tamil": "ta", "malayalam": "ml", "telugu": "te",
             "kannada": "kn", "marathi": "mr", "bengali": "bn", "gujarati": "gu", "punjabi": "pa",
             "urdu": "ur", "french": "fr", "german": "de", "spanish": "es", "portuguese": "pt",
             "italian": "it", "dutch": "nl", "arabic": "ar", "mandarin": "zh", "chinese": "zh",
             "cantonese": "yue", "japanese": "ja", "korean": "ko", "russian": "ru",
             "indonesian": "id", "malay": "ms", "vietnamese": "vi", "thai": "th",
             "tagalog": "tl", "filipino": "fil", "polish": "pl", "turkish": "tr",
             "greek": "el", "hebrew": "he", "swedish": "sv", "norwegian": "no",
             "danish": "da", "finnish": "fi", "sinhala": "si", "nepali": "ne", "persian": "fa"}


class Refused(Exception):
    """Why nothing was written: (detail, fix) pairs."""

    def __init__(self, reasons):
        super().__init__("; ".join(d for d, _ in reasons))
        self.reasons = reasons


# --- values as written ---------------------------------------------------------------------

class Leaf(str):
    """A YAML scalar exactly as written, with the file line it came from. The coverage
    check reads every one back out of the graph by that line."""
    line = 0


class Lex(str):
    """A number's lexical form, kept as written - 8.40 stays 8.40, 0400 stays 0400 - with
    its datatype. The writer and the parser both keep lexical forms, so the round trip
    can hold a number to the exact characters the Markdown had."""

    def __new__(cls, text, dt):
        out = super().__new__(cls, text)
        out.dt = dt
        return out


# Only null keeps its YAML 1.1 reading. Everything else a YAML 1.1 loader would turn
# into a number, a boolean or a date - 0400123456 read as octal, NO as false, 8.40 as
# 8.4 - is a string here, and the ontology predicate it lands in decides its type.
KEEP_RESOLVERS = ("tag:yaml.org,2002:null", "tag:yaml.org,2002:merge")
_LOADER = []


def yaml_loader():
    if _LOADER:
        return _LOADER[0]
    import yaml

    class Loader(yaml.SafeLoader):
        first = 1

        def construct_mapping(self, node, deep=False):
            # SafeLoader keeps the last of two equal keys and says nothing.
            seen = set()
            for key, _ in node.value:
                if isinstance(key, yaml.ScalarNode):
                    if key.value in seen:
                        raise yaml.constructor.ConstructorError(
                            None, None, f"duplicate key {key.value!r}", key.start_mark)
                    seen.add(key.value)
            return super().construct_mapping(node, deep)

    def scalar(loader, node):
        leaf = Leaf(loader.construct_scalar(node))
        leaf.line = loader.first + node.start_mark.line
        return leaf

    Loader.yaml_implicit_resolvers = {
        ch: [(tag, rx) for tag, rx in rs if tag in KEEP_RESOLVERS]
        for ch, rs in yaml.SafeLoader.yaml_implicit_resolvers.items()}
    Loader.add_constructor("tag:yaml.org,2002:str", scalar)
    _LOADER.append(Loader)
    return Loader


def load_yaml(text, where, first_line, leaves,
              fix="fix the block; docs/legacy-kb-spec.md shows each one's shape"):
    """One block as a mapping of Leaf values, as kbindex.load_yaml reads it but with
    nothing retyped. Every value (not key) is appended to `leaves`."""
    import yaml

    from .kbindex import KBError

    loader = yaml_loader()(text)
    loader.first = first_line
    try:
        data = loader.get_single_data()
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        at = f", line {first_line + mark.line}" if mark else ""
        raise KBError(f"{where}{at}: not valid YAML - {getattr(exc, 'problem', None) or exc}",
                      fix) from None
    finally:
        loader.dispose()
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise KBError(f"{where}: the block is not `key: value` lines",
                      "docs/legacy-kb-spec.md shows the shape")

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            leaves.append(x)
    walk(data)
    return data


def tokens(text):
    """The words and numbers of a text, case-folded; "40,000" is one number, 40000."""
    text = re.sub(r"\d{1,3}(?:,\d{3})+", lambda m: m.group().replace(",", ""), str(text))
    return set(re.findall(r"[^\W_]+", text.casefold()))


# --- the entries, as a dictionary ----------------------------------------------------------

@dataclass
class Node:
    cls: str
    props: dict = field(default_factory=lambda: defaultdict(set))

    def frozen(self):
        return (self.cls, {p: frozenset(lexical(x) for x in v) for p, v in self.props.items()
                           if v})


def lexical(v):
    """A value as its datatype and exact characters: 8.40 and 8.4 are different values."""
    if isinstance(v, bool):
        return ("boolean", "true" if v else "false")
    if isinstance(v, Lex):
        return (v.dt, str(v))
    if isinstance(v, int):
        return ("integer", str(v))
    if isinstance(v, Decimal):
        return ("decimal", str(v))
    if isinstance(v, datetime.date):
        return ("date", v.isoformat())
    return ("string", str(v))


@dataclass
class Plan:
    """Everything a migration would write, and what it had to say about it."""
    root: str
    nodes: dict = field(default_factory=dict)            # kb.ttl: iri -> Node
    notices: list = field(default_factory=list)          # printed as `note     ...`
    refusals: list = field(default_factory=list)         # (detail, fix)
    files: dict = field(default_factory=dict)            # workspace name -> text
    copies: list = field(default_factory=list)           # (from name, to name)
    records: list = field(default_factory=list)          # resume.json paths
    apps: int = 0
    defaulted: int = 0                                   # entries with no status: inferred
    store: object = None                                 # the new workspace, validated
    used: set = field(default_factory=set)               # id() of each Leaf handed on
    unwritten: set = field(default_factory=set)          # ... that no triple spells out

    def refuse(self, detail, fix):
        self.refusals.append((detail, fix))

    def mark(self, value, spelled=True):
        """Record that a value read from YAML was handed on - into a triple or a note.
        `spelled=False` when what it became does not spell it: `retired: true` is a
        date, the kb: format number is no triple at all."""
        if isinstance(value, dict):
            for v in value.values():
                self.mark(v, spelled)
        elif isinstance(value, list):
            for v in value:
                self.mark(v, spelled)
        elif isinstance(value, Leaf):
            self.used.add(id(value))
            if not spelled:
                self.unwritten.add(id(value))


def ontology():
    """The graph's format tables - imported late, so `jsk --help` never pays for them."""
    from .graph import ontology as onto
    return onto


def local_id(old):
    """An old id in the ontology's shape: proj_ -> prj_, role_ -> pos_, metric_ -> met_."""
    old = str(old).strip()
    prefix, _, rest = old.partition("_")
    prefix = RENAMES.get(prefix.lower(), prefix.lower())
    slug = re.sub(r"[^a-z0-9]+", "_", rest.lower()).strip("_")
    return f"{prefix}_{slug}"


def kid(old):
    return ontology().K + local_id(old)


def slug(text, sep="-"):
    folded = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    folded = folded.replace("#", "sharp").replace("+", "plus")
    return re.sub(r"[^a-z0-9]+", sep, folded).strip(sep)


def raw_text(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def empty(value):
    return value is None or (isinstance(value, str) and not value.strip()) or value == [] \
        or value == {}


def number(value):
    """A Lex (integer or decimal) from a number or its text, the characters kept - except
    a thousands comma, which no xsd number can hold ("40,000" is 40000). None otherwise."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Lex(str(value), "integer")
    if isinstance(value, float):
        return Lex(repr(value), "decimal")
    if isinstance(value, Decimal):
        return Lex(str(value), "decimal")
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?", text):
        text = text.replace(",", "")
    if re.fullmatch(r"[+-]?\d+", text):
        return Lex(text, "integer")
    if re.fullmatch(r"[+-]?\d*\.\d+", text):
        return Lex(text, "decimal")
    return None


QUALIFIED = re.compile(r"(?P<pre>[~≈<>])?\s*(?P<a>\d[\d,]*(?:\.\d+)?)"
                       r"(?:\s*[-–]\s*(?P<b>\d[\d,]*(?:\.\d+)?))?\s*(?P<plus>\+)?")
QUALIFIER = {"~": "about", "≈": "about", "<": "under", ">": "over"}


def qualified(value):
    """(value, upper or None, qualifier or None) for a metric as people write one - "15+",
    "~12", "<1", "15-20", "~20-30", "300-800+" - or None when it is not one number, or
    one range, stated so. Several numbers in one cell are several metrics, and stay
    refused."""
    m = QUALIFIED.fullmatch(str(value).strip())
    if not m or (m["pre"] and m["plus"]):
        return None
    low, high = number(m["a"]), number(m["b"]) if m["b"] else None
    if low is None or (m["b"] and (high is None or Decimal(high) <= Decimal(low))):
        return None
    qualifier = "at-least" if m["plus"] else QUALIFIER.get(m["pre"])
    return low, high, qualifier


def as_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    if FULL_DATE.fullmatch(text):
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            return None
    return None


class Builder:
    """Puts values on entries by the ontology's rules. A value that does not fit its
    predicate is kept as a `j:note` on the entry and reported - never dropped."""

    def __init__(self, plan, nodes=None):
        self.plan = plan
        self.nodes = plan.nodes if nodes is None else nodes

    def node(self, iri, cls):
        if iri in self.nodes and self.nodes[iri].cls != cls:
            self.plan.refuse(f"{curie(iri)} is both a {self.nodes[iri].cls} and a {cls}",
                             "give one of them another id")
        return self.nodes.setdefault(iri, Node(cls))

    def note(self, iri, key, value, why=None):
        self.plan.mark(value)
        self.nodes[iri].props["note"].add(f"{key}: {raw_text(value)}")
        if why:
            self.plan.notices.append(f"{curie(iri)}: {key} {raw_text(value)!r} kept as a "
                                     f"j:note - {why}")

    def put(self, iri, pred, value, key=None):
        """Set `pred` on the entry from a Markdown value; returns True when it fit."""
        onto = ontology()
        key = key or pred
        self.plan.mark(value)
        if empty(value):
            return False
        n = self.nodes[iri]
        p = onto.BY_NAME[n.cls].preds[pred]
        typed, why = self.typed(p, value)
        if typed is None:
            self.note(iri, key, value, why)
            return False
        if p.card in "1?" and n.props[pred] and typed not in n.props[pred]:
            self.note(iri, key, value, f"it already has a {pred}")
            return False
        n.props[pred].add(typed)
        if isinstance(typed, str) and isinstance(value, str) and FULL_DATE.fullmatch(value.strip()) \
                and typed != value.strip():
            # A day where the ontology keeps a month: the month is the value, the day a note.
            self.note(iri, key, value.strip())
        return True

    def typed(self, p, value):
        onto = ontology()
        obj = p.obj
        if isinstance(obj, onto.Enum):
            text = str(value).strip()
            text = ENUM_MAP.get(obj.name, {}).get(text, text)
            if text in onto.ENUMS[obj.name]:
                return text, None
            return None, f"not one of {', '.join(onto.ENUMS[obj.name])}"
        if isinstance(obj, (onto.Ref, onto.Concept)):
            return str(value), None
        types = obj.types
        if isinstance(value, (list, dict)):
            return None, "a list or a mapping where one value belongs"
        if "date" in types:
            d = as_date(value)
            if d is not None:
                return d, None
            if types == ("date",):
                return None, "not a YYYY-MM-DD date"
        if "boolean" in types:
            if isinstance(value, bool):
                return value, None
            if str(value).strip().lower() in ("true", "false") and len(types) == 1:
                return str(value).strip().lower() == "true", None
            if len(types) == 1:
                return None, "not true or false"
        if "integer" in types or "decimal" in types:
            num = number(value)
            if num is not None and num.dt not in types:
                num = None
            if num is not None:
                at = Decimal(str(num))
                if (obj.lo is not None and at < obj.lo) or (obj.hi is not None and at > obj.hi):
                    return None, f"outside {obj.lo}-{obj.hi}"
                return num, None
            if "string" not in types:
                return None, "not a number"
        text = value.isoformat() if isinstance(value, (datetime.date, datetime.datetime)) \
            else raw_text(value)
        if obj.pattern:
            if obj.pattern.startswith(r"\d{4}(-") and FULL_DATE.fullmatch(text):
                text = text[:7]              # a day where a month is kept: the month
            if not re.fullmatch(obj.pattern, text):
                return None, f"not in the form {obj.pattern}"
        if isinstance(value, str) and p.obj is not onto.TEXT:
            text = text.strip()
        return text, None


def curie(iri):
    from .graph.writer import curie as c
    return c(iri)


# --- the vocabulary ----------------------------------------------------------------------

class Vocabulary:
    """Terms to concepts: the shipped vocabulary first, by id then by a unique label."""

    def __init__(self):
        from .graph import io
        from .graph.store import SHIPPED_VOCABULARY

        onto = ontology()
        self.shipped, self.labels = {}, defaultdict(set)
        self.names = defaultdict(set)            # concept iri -> its labels, as written
        try:
            quads = io.parse(SHIPPED_VOCABULARY).quads
        except (OSError, io.GraphError):
            quads = []
        for q in quads:
            if q.predicate.value == onto.RDF_TYPE:
                self.shipped[q.subject.value] = q.object.value[len(onto.J):]
            elif q.predicate.value in (onto.J + "label", onto.J + "former"):
                self.labels[onto.norm(q.object.value)].add(q.subject.value)
                self.names[q.subject.value].add(q.object.value)

    def concept(self, term):
        """(iri, own) - own when the person's kb.ttl must define it."""
        onto = ontology()
        key = onto.norm(str(term))
        if onto.CONCEPT_SLUG.fullmatch(key) and onto.C + key in self.shipped:
            return onto.C + key, False
        named = self.labels.get(key, set())
        if len(named) == 1:
            return next(iter(named)), False
        own = onto.C + slug(term)
        return (own, False) if own in self.shipped else (own, True)


# --- reading the Markdown --------------------------------------------------------------------

def clean(lines):
    """Lines without HTML comments or the template's placeholders, trimmed of blank edges."""
    text = COMMENT.sub("", "\n".join(lines))
    out = [line.rstrip() for line in text.split("\n")]
    out = [line for line in out if not PLACEHOLDER.fullmatch(line.strip())]
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def own_lines(section, all_lines):
    """A section's lines that are not in one of its ### entries."""
    inside = set()
    for e in section["entries"]:
        inside |= set(range(e["start"], e["end"] + 1))
    return [all_lines[n - 1] for n in range(section["start"] + 1, section["end"] + 1)
            if n not in inside]


def body_without_yaml(entry):
    """An entry's body lines, less its yaml block."""
    skip = set()
    if entry["yaml"]:
        first, content = entry["yaml"]
        skip = set(range(first, first + content.count("\n") + 2))
    return [line for n, line in entry["body"] if n not in skip]


def yaml_blocks(numbered, where, leaves, fenced):
    """(blocks, the other lines) - each ```yaml fence in [(line no, line)] parsed as a
    mapping; the fence's line numbers go into `fenced`. A fence that never closes is
    not a block: its lines stay text."""
    blocks, rest, inside, buf = [], [], None, []
    for n, line in numbered:
        if inside is None and re.match(r"^\s*```\s*yaml\s*$", line):
            inside, buf = n, [line]
        elif inside is not None and re.match(r"^\s*```\s*$", line):
            blocks.append(load_yaml("\n".join(buf[1:]), where, inside + 1, leaves))
            fenced.update(range(inside, n + 1))
            inside = None
        elif inside is not None:
            buf.append(line)
        else:
            rest.append(line)
    if inside is not None:
        rest += buf
    return blocks, rest


def list_items(lines):
    """([{head, more, subs}], leftover lines) for `- item` lists with `  - key: value`."""
    items, leftover, cur = [], [], None
    for line in lines:
        if not line.strip():
            continue
        top = TOP_ITEM.match(line)
        sub = SUB_ITEM.match(line)
        if top:
            cur = {"head": top["text"].strip(), "more": [], "subs": []}
            items.append(cur)
        elif sub and cur is not None:
            cur["subs"].append((sub["key"], sub["value"].strip()))
        elif cur is not None and line[:1] in (" ", "\t") and not cur["subs"]:
            cur["more"].append(line.strip())
        else:
            leftover.append(line)
    return items, leftover


def split_id(text):
    m = ID_IN_HEADING.match(text)
    return (m["title"].strip(), m["id"], m["rest"].strip()) if m else (text.strip(), None, "")


def table(lines):
    """(header, rows, leftover): a Markdown table's cells, split on unescaped pipes."""
    header, rows, leftover = None, [], []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if not s.startswith("|"):
            leftover.append(line)
            continue
        cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s.strip("|"))]
        if header is None:
            header = [c.lower() for c in cells]
        elif all(set(c) <= set("-: ") for c in cells):
            continue
        else:
            rows.append(dict(zip(header, cells + [""] * (len(header) - len(cells)))))
            if len(cells) > len(header):
                rows[-1]["_extra"] = cells[len(header):]
    return header, rows, leftover


# What `jsk new`'s template pre-filled in a row the person never completed: a contact
# with no value, a work authorization with no jurisdiction, a language with no language.
# A row holding only these carries nothing; a row holding anything more is kept.
TEMPLATE_DEFAULTS = {"contact": {"kind", "primary"}, "work_authorization": {"status"},
                     "language": {"native"}}

# Words the coverage check reads as the file's layout rather than its content: section
# and prose headings, table columns, sub-item keys, the old id prefixes and enum values
# the migration renames.
STRUCTURE_WORDS = tokens(" ".join(
    list(KNOWN_SECTIONS) + ["Log", "The problem", "What I decided", "What changed", "Bullets",
                            "aliases alias metric metrics status state id true false",
                            "none quantified reason retired", " ".join(EVENT_COLUMNS),
                            "subject baseline value unit direction confidence source",
                            "question about asked answered"]
    + list(RENAMES) + [k for m in ENUM_MAP.values() for k in m]))

TITLE = re.compile(r"#\s+Career knowledge base\s*[-–—]\s*(?P<who>.+?)\s*")


class Reader:
    """user-knowledgebase.md into Plan.nodes: one Node per entry the graph will hold.

    Every value it reads lands in a triple or in a `j:note` on the nearest entry, or the
    migration is refused - nothing is skipped. `coverage()` holds it to that afterwards,
    against the graph as written."""

    def __init__(self, plan, text, vocab, today):
        from .kbindex import read_kb

        self.plan, self.vocab, self.today = plan, vocab, today
        self.b = Builder(plan)
        self.leaves = []                         # every YAML value read, as a Leaf
        self.structure = set()                   # line numbers read as layout, not content
        self.ids = {}                            # entry iri -> the id it was written as
        self.lines = text.split("\n")
        self.front, blanked, self.front_end = self.frontmatter(text)
        _, self.by_title, self.sections = read_kb(blanked)
        self.concept_use = defaultdict(set)      # iri -> {"Domain", "Capability", "Technology"}
        self.concept_terms = defaultdict(set)    # own concept iri -> terms written
        self.bullets = []                        # (project iri, text, explicit id, rank, subs)
        self.log_text = []
        updated = as_date(self.front.get("updated"))
        self.retired_on = updated or today

    def frontmatter(self, text):
        """(the --- block, the text with it blanked, its closing line's index or -1).
        Read here with migrate's loader; kbindex then sees a file with no frontmatter,
        whose line numbers still hold."""
        from .kbindex import KBError

        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            return {}, text, -1
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if closing is None:
            raise KBError("the knowledge base's frontmatter never closes", "end it with a --- line")
        front = load_yaml("\n".join(lines[1:closing]), "the knowledge base's frontmatter", 2,
                          self.leaves, 'quote any value holding a colon - title: "Engineer II: '
                                       'Payments"')
        self.structure.update(range(1, closing + 2))
        return front, "\n" * (closing + 1) + "\n".join(lines[closing + 1:]), closing

    # -- helpers
    def numbered(self, s):
        """[(line no, line)] of a section, below its heading."""
        return [(n, self.lines[n - 1]) for n in range(s["start"] + 1, s["end"] + 1)]

    def claim(self, old):
        """The iri an entry's id names - refused when another entry already has it, even
        one written differently: org_Acme and org_acme are one id once normalised, and
        two entries merged into one is a meaning changed."""
        self.plan.mark(old)
        iri = kid(old)
        if iri in self.ids:
            self.plan.refuse(f"{self.ids[iri]} and {old} both name {curie(iri)}",
                             "give one of them another id")
        else:
            self.ids[iri] = str(old)
        return iri

    def unique(self, iri):
        n, out = 2, iri
        while out in self.plan.nodes:
            out, n = f"{iri}_{n}", n + 1
        self.ids.setdefault(out, "an entry written with no id (its id was minted)")
        return out

    def heading(self, iri, entry, *values):
        """A ### heading that says more than the values taken from it is kept as a note."""
        taken = tokens(" ".join(str(v) for v in values if not empty(v)))
        if not tokens(entry["title"]) <= taken:
            self.b.note(iri, "heading", entry["title"])

    def status(self, iri, value, other=None):
        """`status:` split: an `other` enum's value goes there; a provenance is provenance."""
        onto = ontology()
        self.plan.mark(value)
        if empty(value):
            return
        text = str(value).strip()
        if other and ENUM_MAP.get(other[1], {}).get(text, text) in onto.ENUMS[other[1]]:
            self.b.put(iri, other[0], text, "status")
        elif text in onto.ENUMS["provenance"]:
            self.b.put(iri, "provenance", text, "status")
        else:
            self.b.note(iri, "status", text, "not a provenance"
                        + (f" or a {other[0]}" if other else ""))

    def retired(self, iri, block):
        value = block.get("retired")
        text = value.strip().lower() if isinstance(value, str) else value
        if value is True or text == "true":
            self.plan.mark(value, spelled=False)      # it becomes the day it was retired
            n = self.plan.nodes[iri]
            n.props["retired"].add(self.retired_on)
            given = False
            for key in ("reason", "retired_reason"):
                given = self.b.put(iri, "reason", block.get(key), key) or given
            if not given and not n.props["reason"]:
                n.props["reason"].add("Retired in user-knowledgebase.md, which recorded no "
                                      "reason.")
            return
        if value is False or text == "false":
            self.plan.mark(value, spelled=False)
        elif not empty(value):
            self.b.note(iri, "retired", value, "not true or false")
        for key in ("reason", "retired_reason"):
            if not empty(block.get(key)):
                self.b.note(iri, key, block[key], "a reason, but the entry is not retired")

    def extra(self, iri, block, known, prefix=""):
        for k, v in block.items():
            if k not in known and not empty(v):
                self.b.note(iri, prefix + k, v, "the ontology has no field for it")

    def use(self, term, as_class):
        self.plan.mark(term)
        iri, own = self.vocab.concept(term)
        if own:
            self.concept_use[iri].add(as_class)
            self.concept_terms[iri].add(str(term))
        else:
            self.concept_use.setdefault(iri, set())
        return iri

    def terms(self, iri, pred, value, cls, key):
        for t in value if isinstance(value, list) else [value]:
            if empty(t):
                continue
            if isinstance(t, str):
                self.b.put(iri, pred, self.use(t, cls), key)
            else:
                self.b.note(iri, key, t, "not a term")

    def kb_note(self, heading, lines):
        lines = clean(lines)
        if lines:
            self.b.note(ontology().K + "kb", heading, "\n".join(lines),
                        "no field of the graph holds it, so it is kept word for word")

    def sub_map(self, iri, pairs):
        """`  - key: value` sub-items as a mapping; a key written twice keeps its earlier
        value as a note, where a plain dict would have dropped it."""
        out = {}
        for k, v in pairs:
            if k in out and not empty(out[k]):
                self.b.note(iri, k, out[k], "written twice under one item; the last is read")
            out[k] = v
        return out

    # -- the whole file
    def read(self):
        onto = ontology()
        kb = self.b.node(onto.K + "kb", "KB")
        kb.props["format"].add(onto.FORMAT)
        name = self.front.get("name")
        if empty(name):
            self.plan.refuse("the frontmatter has no name:", "add `name: Their Name` to it")
        else:
            self.plan.mark(name)
            kb.props["name"].add(str(name).strip())
        kb.props["updated"].add(self.today)
        version = self.front.get("kb")
        if str(version).strip() not in ("1", "2"):
            self.plan.refuse(f"kb: {version!r} - this reads the kb: 2 format",
                             "set `kb: 2` once the file follows docs/legacy-kb-spec.md")
        self.plan.mark(version, spelled=False)
        if not empty(self.front.get("updated")):
            self.b.note(onto.K + "kb", "updated", self.front["updated"],
                        "the day this migration ran is j:updated; the Markdown's is kept here")
        self.extra(onto.K + "kb", self.front, {"name", "kb", "updated"})
        self.b.node(onto.K + "person", "Person")
        first = self.sections[0]["start"] if self.sections else len(self.lines) + 1
        before = []
        for n in range(self.front_end + 2, first):
            m = TITLE.fullmatch(self.lines[n - 1])
            if m and not empty(name) and m["who"] == str(name).strip():
                self.structure.add(n)                # the template's own title
            else:
                before.append(self.lines[n - 1])
        self.kb_note("before the first section", before)
        seen = set()
        for s in self.sections:
            title = s["title"]
            if title in seen or (title not in KNOWN_SECTIONS and title != "Log"):
                self.kb_note(f"## {title}", self.lines[s["start"]:s["end"]])
                continue
            seen.add(title)
            self.structure.add(s["start"])
            if title == "Log":
                self.log_text = clean(self.lines[s["start"]:s["end"]])
                continue
            getattr(self, "sec_" + slug(title, "_"))(s)
        self.concepts()
        if onto.K + "person" in self.plan.nodes and \
                not self.plan.nodes[onto.K + "person"].props["fullName"] and not empty(name):
            self.plan.nodes[onto.K + "person"].props["fullName"].add(str(name).strip())

    # -- sections
    def sec_identity(self, s):
        person = ontology().K + "person"
        blocks, rest = yaml_blocks(self.numbered(s), "## Identity", self.leaves, self.structure)
        self.kb_note("## Identity", rest)
        for block in blocks:
            for key, pred in (("full_name", "fullName"), ("given_name", "givenName"),
                              ("family_name", "familyName"), ("headline", "headline")):
                self.b.put(person, pred, block.get(key), key)
            loc = block.get("location")
            if isinstance(loc, dict):
                for key, pred in (("city", "city"), ("region", "region"), ("country", "country"),
                                  ("mode", "workMode")):
                    v = loc.get(key)
                    self.plan.mark(v)
                    if key == "country" and isinstance(v, str) and len(v.strip()) == 2:
                        v = v.strip().upper()
                    self.b.put(person, pred, v, "location." + key)
                self.extra(person, loc, {"city", "region", "country", "mode"}, "location.")
            elif not empty(loc):
                self.b.note(person, "location", loc, "not a mapping")
            contacts = block.get("contacts")
            if not empty(contacts) and not isinstance(contacts, list):
                self.b.note(person, "contacts", contacts, "not a list")
            elif contacts:
                for c in contacts:
                    self.contact(person, c)
            self.status(person, block.get("status"))
            self.extra(person, block, {"full_name", "given_name", "family_name", "headline",
                                       "location", "contacts", "status"})

    def contact(self, person, c):
        if not isinstance(c, dict):
            if not empty(c):
                self.b.note(person, "contact", c, "a contact is a kind: and a value:")
            return
        kind = str(c.get("kind") or "").strip()
        if empty(c.get("value")):
            if {k for k, v in c.items() if not empty(v)} <= TEMPLATE_DEFAULTS["contact"]:
                self.plan.mark(c, spelled=False)      # the template's row, never filled in
            else:
                self.b.note(person, f"contact {kind or '(no kind)'}", c, "a contact with no value:")
            return
        self.plan.mark(c.get("kind"))
        primary = c.get("primary")
        flag = primary.strip().lower() if isinstance(primary, str) else primary
        landed = False
        if kind in CONTACTS:
            landed = self.b.put(person, kind, c["value"], "contact " + kind)
        else:
            self.b.note(person, f"contact {kind or '(no kind)'}", c["value"],
                        f"not one of {', '.join(CONTACTS)}")
        if landed and (flag is True or flag == "true"):
            self.plan.mark(primary, spelled=False)
            self.b.put(person, "primary", c["value"], "primary")
        elif landed and (flag is False or flag == "false"):
            self.plan.mark(primary, spelled=False)
        elif not empty(primary):
            self.b.note(person, f"contact {kind}.primary", primary)
        self.extra(person, c, {"kind", "value", "primary"}, f"contact {kind}.")

    def sec_positioning(self, s):
        # Prose, all of it: a ### inside it is part of what they wrote.
        lines = clean(self.lines[s["start"]:s["end"]])
        if lines:
            self.b.put(ontology().K + "person", "positioning", "\n".join(lines))

    def listed_in(self, block, key, iri):
        """A block's list under `key`, or [] with anything else there kept as a note."""
        value = block.get(key)
        if not empty(value) and not isinstance(value, list):
            self.b.note(iri, key, value, "not a list")
            return []
        return value or []

    def sec_work_authorization_and_languages(self, s):
        onto = ontology()
        person = onto.K + "person"
        blocks, rest = yaml_blocks(self.numbered(s), "## Work authorization and languages",
                                   self.leaves, self.structure)
        self.kb_note("## Work authorization and languages", rest)
        for block in blocks:
            for item in self.listed_in(block, "work_authorization", person):
                if not isinstance(item, dict):
                    if not empty(item):
                        self.b.note(person, "work authorization", item,
                                    "not a mapping with a jurisdiction:")
                    continue
                if empty(item.get("jurisdiction")):
                    filled = {k for k, v in item.items() if not empty(v)}
                    if filled <= TEMPLATE_DEFAULTS["work_authorization"]:
                        self.plan.mark(item, spelled=False)   # the template's row
                    else:
                        self.plan.refuse(f"a work authorization with no jurisdiction: {item}",
                                         "write its jurisdiction: (a country code, or EU)")
                    continue
                iri = self.unique(onto.K + "auth_" + slug(item["jurisdiction"], "_"))
                self.b.node(iri, "WorkAuthorization")
                self.b.put(iri, "jurisdiction", item["jurisdiction"])
                self.b.put(iri, "kind", item.get("kind"))
                self.b.put(iri, "authorization", item.get("authorization"))
                self.status(iri, item.get("status"), ("authorization", "authorization"))
                self.b.put(iri, "provenance", item.get("provenance"))
                self.b.put(iri, "validUntil", item.get("valid_until"), "valid_until")
                self.b.put(iri, "validUntil", item.get("expires"), "expires")
                self.extra(iri, item, {"jurisdiction", "kind", "authorization", "status",
                                       "provenance", "valid_until", "expires"})
            for item in self.listed_in(block, "languages", person):
                if not isinstance(item, dict):
                    if not empty(item):
                        self.b.note(person, "language", item, "not a mapping with a language:")
                    continue
                if empty(item.get("language")):
                    filled = {k for k, v in item.items() if not empty(v)}
                    if filled <= TEMPLATE_DEFAULTS["language"]:
                        self.plan.mark(item, spelled=False)   # the template's row
                    else:
                        self.b.note(person, "language", item,
                                    "a language with no language: - kept whole")
                    continue
                self.plan.mark(item["language"])
                name = str(item["language"]).strip()
                tag = LANGUAGES.get(name.lower(), name)
                iri = self.unique(onto.K + "lang_" + slug(tag, "_"))
                self.b.node(iri, "Language")
                if not self.b.put(iri, "language", tag, "language"):
                    self.plan.refuse(f"language {name!r} is not a BCP 47 tag this knows",
                                     "write its tag - en, hi, fr-CA - in language:")
                elif tag != name:
                    self.b.note(iri, "written as", name)
                for key in ("native", "scheme", "level"):
                    self.b.put(iri, key, item.get(key))
                self.status(iri, item.get("status"))
                self.extra(iri, item, {"language", "native", "scheme", "level", "status"})
            self.extra(onto.K + "kb", block, {"work_authorization", "languages"},
                       "work authorization block ")

    def sec_vocabulary(self, s):
        from .graph.scoring import SENIORITY

        self.kb_note("## Vocabulary", own_lines(s, self.lines))
        classes = {"capabilit": "Capability", "domain": "Domain", "technolog": "Technology"}
        for e in s["entries"]:
            body = [x for _, x in e["body"]]
            whole = [f"### {e['title']}"] + body
            if e["title"].lower().startswith("seniority"):
                # The fixed list, as the template wrote it, is the ontology's seniority
                # enum already; anything else under it is theirs and is kept.
                text = "\n".join(clean(body))
                if tuple(re.findall(r"`([^`]+)`", text)) == SENIORITY and \
                        not re.sub(r"`[^`]+`|[-\s]", "", text):
                    self.structure.update(range(e["start"], e["end"] + 1))
                else:
                    self.kb_note(f"## Vocabulary / ### {e['title']}", whole)
                continue
            cls = next((c for k, c in classes.items() if e["title"].lower().startswith(k)), None)
            if cls is None:
                self.kb_note(f"## Vocabulary / ### {e['title']}", whole)
                continue
            self.structure.add(e["start"])
            rest = []
            for line in body:
                m = TERM_ITEM.match(line)
                if m:
                    iri = self.use(m["term"], cls)
                    tail = m["rest"].lstrip("-—–: ").strip()
                    if tail:
                        self.b.node(iri, "Concept")
                        self.b.note(iri, "vocabulary", tail)
                else:
                    rest.append(line)
            self.kb_note(f"## Vocabulary / ### {e['title']}", rest)

    def entries(self, s, kind):
        """Each ### entry with its first yaml block - kbindex.entries_with_blocks, read
        with migrate's loader."""
        from .kbindex import KBError

        self.kb_note(f"## {s['title']}", own_lines(s, self.lines))
        parsed = []
        for entry in s["entries"]:
            if entry["yaml"] is None:
                raise KBError(f"## {s['title']}: `### {entry['title']}` (line {entry['start']}) "
                              f"has no ```yaml block",
                              f"every {kind} carries its block; the index cannot skip one "
                              "quietly")
            line, content = entry["yaml"]
            block = load_yaml(content, f"`### {entry['title']}`", line + 1, self.leaves)
            self.structure.update(range(line, line + content.count("\n") + 2))
            if empty(block.get("id")):
                raise KBError(f"`### {entry['title']}` (line {entry['start']}) has no id: in its "
                              "block", "write the id the heading carries in backticks")
            parsed.append({**entry, "block": block})
        return parsed

    def body_note(self, iri, entry):
        lines = clean(body_without_yaml(entry))
        if lines:
            self.b.note(iri, "text", "\n".join(lines))

    def about(self, iri, qid, value):
        """A question's `about`: an id, several ("proj_a, proj_b"), or a section's name
        ("Skills", "Open source") - a question about the career as a whole, k:kb, with
        the section kept in a note."""
        if empty(value):
            return
        self.plan.mark(value)
        onto = ontology()
        sections = {s.lower(): s for s in KNOWN_SECTIONS}
        for part in (x.strip() for x in str(value).split(",")):
            if not part:
                continue
            if part.lower() in sections:
                self.plan.nodes[iri].props["about"].add(onto.K + "kb")
                self.b.note(iri, "about", f"the {sections[part.lower()]} section")
            elif onto.ID.fullmatch(local_id(part)) and "_" in part:
                self.b.put(iri, "about", kid(part), "about")
            else:
                self.plan.refuse(f"question {qid}: about {part!r} is not an id",
                                 "name the entry it is about by its id, or a section by "
                                 "its heading, then run `jsk migrate` again")

    def ref(self, iri, pred, old, key):
        """A reference to another entry, by its old id."""
        if not empty(old):
            self.plan.mark(old)
            if not ("_" in str(old) and ontology().ID.fullmatch(local_id(old))):
                self.plan.refuse(f"{curie(iri)} {key}: {str(old).strip()!r} is not an id",
                                 "name the entry by its id (`role_x`, `proj_x`, ...), then "
                                 "run `jsk migrate` again")
                return
            self.b.put(iri, pred, kid(old), key)

    def sec_organisations(self, s):
        for e in self.entries(s, "organisation"):
            b = e["block"]
            iri = self.claim(b["id"])
            self.b.node(iri, "Organisation")
            name = b.get("name") or split_id(e["title"])[0]
            self.b.put(iri, "name", name, "name")
            self.heading(iri, e, name, b["id"])
            if empty(b.get("relationship")):
                self.plan.notices.append(f"{curie(iri)}: no relationship: - recorded as employer")
            self.b.put(iri, "relationship", b.get("relationship") or "employer", "relationship")
            self.terms(iri, "industry", b.get("industry"), "Domain", "industry")
            self.b.put(iri, "size", b.get("size"))
            self.status(iri, b.get("status"))
            self.retired(iri, b)
            self.extra(iri, b, {"id", "name", "relationship", "industry", "size", "status",
                                "retired", "reason", "retired_reason"})
            self.body_note(iri, e)

    def sec_roles(self, s):
        for e in self.entries(s, "role"):
            b = e["block"]
            iri = self.claim(b["id"])
            self.b.node(iri, "Position")
            self.ref(iri, "organisation", b.get("organisation"), "organisation")
            title = b.get("title") or split_id(e["title"])[0].split(" - ")[0]
            self.b.put(iri, "title", title, "title")
            org = self.plan.nodes.get(kid(b["organisation"])) if not empty(b.get("organisation")) \
                else None
            self.heading(iri, e, title, b["id"], *(org.props.get("name", ()) if org else ()))
            self.b.put(iri, "functionalTitle", b.get("functional_title"), "functional_title")
            self.b.put(iri, "start", b.get("start"))
            self.b.put(iri, "end", b.get("end"))
            state = b.get("state")
            if empty(state):
                state = "ended" if not empty(b.get("end")) else "unknown"
                self.plan.notices.append(f"{curie(iri)}: no state: - recorded as {state}")
            self.b.put(iri, "state", state)
            self.b.put(iri, "seniority", b.get("seniority"))
            self.b.put(iri, "change", b.get("change"))
            self.b.put(iri, "engagementKind", b.get("engagement_kind"), "engagement_kind")
            self.b.put(iri, "engagementKind", b.get("kind"), "kind")
            self.status(iri, b.get("status"))
            self.retired(iri, b)
            self.extra(iri, b, {"id", "organisation", "title", "functional_title", "start", "end",
                                "state", "seniority", "change", "engagement_kind", "kind",
                                "status", "retired", "reason", "retired_reason"})
            self.body_note(iri, e)

    def sec_projects(self, s):
        for p in self.entries(s, "project"):
            b = p["block"]
            iri = self.claim(b["id"])
            self.b.node(iri, "Project")
            name = b.get("name") or split_id(p["title"])[0]
            self.b.put(iri, "name", name, "name")
            self.heading(iri, p, name, b["id"])
            self.ref(iri, "position", b.get("role"), "role")
            for key in ("strength", "recency", "seniority"):
                self.b.put(iri, key, b.get(key))
            self.terms(iri, "domain", b.get("domains"), "Domain", "domains")
            self.terms(iri, "uses", b.get("capabilities"), "Capability", "capabilities")
            self.terms(iri, "uses", b.get("technologies"), "Technology", "technologies")
            head = b.get("headline_metric")
            if isinstance(head, str) and head.strip() == "none-quantified":
                self.plan.mark(head, spelled=False)
                self.b.put(iri, "noneQuantified", True, "headline_metric")
            else:
                self.ref(iri, "headlineMetric", head, "headline_metric")
            self.status(iri, b.get("status"))
            self.retired(iri, b)
            self.extra(iri, b, {"id", "name", "role", "strength", "recency", "seniority",
                                "domains", "capabilities", "technologies", "headline_metric",
                                "status", "retired", "reason", "retired_reason"})
            self.prose(iri, body_without_yaml(p))

    def prose(self, iri, lines):
        parts, cur = defaultdict(list), "pre"
        for line in lines:
            for name, rx in PROSE:
                m = rx.match(line)
                if m:
                    cur = name
                    line = line[m.end():]
                    if name == "bullets":
                        line = ""
                    break
            parts[cur].append(line)
        pre = clean(parts["pre"])
        if pre:
            self.b.note(iri, "text", "\n".join(pre))
        for name in ("problem", "decision", "outcome"):
            text = "\n".join(clean(parts[name]))
            if text:
                self.b.put(iri, name, text)
        items, leftover = list_items(clean(parts["bullets"]))
        for rank, item in enumerate(items, 1):
            text = " ".join([item["head"]] + item["more"]).strip()
            self.bullets.append((iri, text, rank, item["subs"]))
        if leftover:
            self.b.note(iri, "bullets", "\n".join(leftover),
                        "lines under **Bullets** that are not a bullet")

    def sec_metrics(self, s):
        # The whole section: a ### inside it is not a row, and is kept as text.
        header, rows, leftover = table(self.lines[s["start"]:s["end"]])
        self.kb_note("## Metrics", leftover)
        known = {"id", "subject", "baseline", "value", "unit", "direction", "confidence",
                 "source", "status"}
        for row in rows:
            if empty(row.get("id")):
                self.kb_note("## Metrics row with no id", [" | ".join(raw_text(v) for v in
                                                                      row.values())])
                continue
            iri = self.claim(row["id"])
            v1 = iri + ".v1"
            self.b.node(iri, "Metric")
            self.b.node(v1, "MetricVersion")
            self.b.put(iri, "subject", row.get("subject"))
            self.b.put(iri, "unit", row.get("unit"))
            self.b.put(iri, "direction", row.get("direction"))
            self.plan.nodes[v1].props["of"].add(iri)
            self.b.put(v1, "baseline", row.get("baseline"))
            stated = qualified(row.get("value")) if number(row.get("value")) is None else None
            if stated:
                # "~20-30": the bottom is the value, the top and the "~" their own fields.
                low, high, qualifier = stated
                self.plan.mark(row.get("value"))
                self.b.put(v1, "value", low)
                self.b.put(v1, "upper", high)
                self.b.put(v1, "qualifier", qualifier)
            elif not self.b.put(v1, "value", row.get("value")):
                self.plan.refuse(f"metric {row['id']}: value {row.get('value')!r} is not a number",
                                 "write the value as a number (the unit has its own column), "
                                 "or move the row into the project's prose")
            if empty(row.get("confidence")):
                self.plan.notices.append(f"{curie(v1)}: no confidence - recorded as reported")
            self.b.put(v1, "confidence", row.get("confidence") or "reported", "confidence")
            self.b.put(v1, "source", row.get("source"))
            self.status(v1, row.get("status"))
            for k, v in row.items():
                if k not in known and k != "_extra" and not empty(v):
                    self.b.note(v1, k, v, "a column the ontology has no field for")
            if row.get("_extra"):
                self.b.note(v1, "cells", row["_extra"], "more cells than the header names")

    def sec_skills(self, s):
        onto = ontology()
        self.kb_note("## Skills", own_lines(s, self.lines))
        for e in s["entries"]:
            category = split_id(e["title"])[0]
            items, leftover = list_items(clean([x for _, x in e["body"]]))
            self.kb_note(f"## Skills / ### {e['title']}", leftover)
            for rank, item in enumerate(items, 1):
                head = " ".join([item["head"]] + item["more"])
                m = re.match(r"^(?P<name>.*?)\s*(?:`(?P<id>[A-Za-z]+_[A-Za-z0-9_\-]+)`)?\s*"
                             r"(?:[—–-]+\s*aliases?:\s*(?P<aliases>.*))?$", head)
                name = (m["name"] or "").strip()
                iri = self.claim(m["id"]) if m["id"] else \
                    self.unique(onto.K + "skill_" + slug(name, "_"))
                self.b.node(iri, "Skill")
                self.b.put(iri, "name", name)
                self.b.put(iri, "category", category)
                self.plan.nodes[iri].props["rank"].add(rank)
                for alias in (m["aliases"] or "").split(","):
                    self.b.put(iri, "alias", alias.strip())
                for k, v in item["subs"]:
                    self.b.note(iri, k, v, "a skill has no such field")

    def sec_education(self, s):
        for e in self.entries(s, "education"):
            b = e["block"]
            iri = self.claim(b["id"])
            self.b.node(iri, "Education")
            for key in ("institution", "qualification", "field", "level", "start", "end"):
                self.b.put(iri, key, b.get(key))
            self.heading(iri, e, b["id"], b.get("institution"), b.get("qualification"),
                         b.get("field"))
            grade = b.get("grade")
            if isinstance(grade, dict):
                self.b.put(iri, "gradeScheme", grade.get("scheme"), "grade.scheme")
                self.b.put(iri, "gradeValue", grade.get("value"), "grade.value")
                self.extra(iri, grade, {"scheme", "value"}, "grade.")
            elif not empty(grade):
                self.b.put(iri, "gradeValue", grade, "grade")
            self.status(iri, b.get("status"))
            self.retired(iri, b)
            self.extra(iri, b, {"id", "institution", "qualification", "field", "level", "start",
                                "end", "grade", "status", "retired", "reason", "retired_reason"})
            self.body_note(iri, e)

    def listed(self, s, prefix, cls):
        """The list-item sections: Certifications, Open source. The whole section is
        read: a ### inside it is not an item, and is kept as text."""
        onto = ontology()
        items, leftover = list_items(clean(self.lines[s["start"]:s["end"]]))
        self.kb_note(f"## {s['title']}", leftover)
        out = []
        for item in items:
            name, old, rest = split_id(" ".join([item["head"]] + item["more"]))
            iri = self.claim(old) if old else self.unique(onto.K + f"{prefix}_" + slug(name, "_"))
            self.b.node(iri, cls)
            self.b.put(iri, "name", name)
            if rest:
                self.b.note(iri, "heading", rest)
            out.append((iri, self.sub_map(iri, item["subs"])))
        return out

    def sec_certifications(self, s):
        for iri, subs in self.listed(s, "cred", "Credential"):
            for key in ("issuer", "issued", "expires", "url"):
                self.b.put(iri, key, subs.get(key))
            self.status(iri, subs.get("status"), ("credentialState", "credentialState"))
            self.b.put(iri, "credentialState", subs.get("state"), "state")
            self.b.put(iri, "provenance", subs.get("provenance"))
            n = self.plan.nodes[iri]
            if not n.props["credentialState"]:
                expires = str(subs.get("expires") or "")
                state = "expired" if expires and expires < self.today.isoformat()[:len(expires)] \
                    else "active"
                n.props["credentialState"].add(state)
                self.plan.notices.append(f"{curie(iri)}: no active/expired status - recorded as "
                                         f"{state}")
            self.retired(iri, subs)
            self.extra(iri, subs, {"issuer", "issued", "expires", "url", "status", "state",
                                   "provenance", "retired", "reason", "retired_reason"})

    def sec_open_source(self, s):
        for iri, subs in self.listed(s, "os", "OpenSource"):
            self.b.put(iri, "url", subs.get("url"))
            self.b.put(iri, "role", subs.get("role"))
            self.status(iri, subs.get("status"))
            self.retired(iri, subs)
            self.extra(iri, subs, {"url", "role", "status", "retired", "reason", "retired_reason"})

    def sec_open_questions(self, s):
        header, rows, leftover = table(self.lines[s["start"]:s["end"]])
        self.kb_note("## Open questions", leftover)
        for row in rows:
            if empty(row.get("id")):
                self.kb_note("## Open questions row with no id",
                             [" | ".join(raw_text(v) for v in row.values())])
                continue
            iri = self.claim(row["id"])
            self.b.node(iri, "Question")
            self.about(iri, row["id"], row.get("about"))
            self.b.put(iri, "question", row.get("question"))
            if empty(row.get("asked")):
                self.plan.nodes[iri].props["asked"].add(self.retired_on)
                self.b.note(iri, "asked", "not recorded; set to the knowledge base's updated day",
                            "the question had no asked date")
            else:
                self.b.put(iri, "asked", row.get("asked"))
            self.b.put(iri, "answered", row.get("answered"))
            for k, v in row.items():
                if k not in {"id", "about", "question", "asked", "answered", "_extra"} \
                        and not empty(v):
                    self.b.note(iri, k, v, "a column the ontology has no field for")
            if row.get("_extra"):
                self.b.note(iri, "cells", row["_extra"], "more cells than the header names")

    # -- after every section
    def concepts(self):
        """The person's own concepts get a class and, when the slug changed the term, the
        term as a label - so matching still finds what they wrote."""
        onto = ontology()
        for iri, uses in self.concept_use.items():
            if iri not in self.concept_terms:
                continue
            n = self.b.node(iri, "Concept")
            cls = next(c for c in ("Domain", "Capability", "Technology") if c in uses)
            n.props["a"].add(cls)
            for term in self.concept_terms[iri]:
                if onto.norm(term) != iri[len(onto.C):]:
                    n.props["label"].add(term)
            if not onto.CONCEPT_SLUG.fullmatch(iri[len(onto.C):]):
                self.plan.refuse(f"the term {sorted(self.concept_terms[iri])[0]!r} has no "
                                 f"letters or digits to name a concept by", "rename the term")


def as_list(value):
    if empty(value):
        return []
    return value if isinstance(value, list) else [value]


# --- bullets and the records that sent them ----------------------------------------------------

def records_of(root):
    return sorted(glob.glob(os.path.join(glob.escape(root), "applications", "*", "resume.json")))


def achievements(path):
    """(id, text) of every achievement a URS record holds, wherever it sits."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("id"), str) and x["id"].startswith("ach_") \
                    and isinstance(x.get("text"), str):
                out.append((x["id"], x["text"]))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return out


def same_words(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def mint_bullets(plan, reader, root):
    """Each bullet's id: the one a sent resume.json already gave the same words, else
    minted from its project and its words. So an application's links survive."""
    from .graph.edit import mint_bullet, words

    onto = ontology()
    sent = defaultdict(list)
    for path in records_of(root):
        for aid, text in achievements(path):
            sent[same_words(text)].append(aid)
    taken = set(plan.nodes)
    b = Builder(plan)
    for project, text, rank, pairs in reader.bullets:
        subs = dict(pairs)
        iri = None
        if not empty(subs.get("id")):
            iri = kid(subs["id"])
        for aid in sent.get(same_words(text), []):
            if iri:
                break
            cand = onto.K + aid
            m = onto.ID.fullmatch(aid)
            if m and m["prefix"] == "ach" and not m["version"] and \
                    not onto.POSITIONAL.search(aid) and cand not in taken:
                iri = cand
                plan.notices.append(f"{curie(cand)}: the id a resume.json gave these words")
        if iri is None:
            iri = mint_bullet(project, text, taken)
        if iri is None:
            found = words(text)
            two = f"{onto.K}ach_{project[len(onto.K) + 4:]}_{'_'.join(found[:2])}"
            iri = two if len(found) >= 2 and two not in taken else None
        if iri is None:
            plan.refuse(f"no id could be minted for the bullet {text[:50]!r} under "
                        f"{curie(project)}", "name it: add `  - id: ach_<project>_<words>` "
                                             "under the bullet")
            continue
        if iri in taken:
            plan.refuse(f"{curie(iri)} names two entries", "give one bullet another id")
            continue
        taken.add(iri)
        n = b.node(iri, "Achievement")
        subs = reader.sub_map(iri, pairs)             # a key written twice: the first, noted
        n.props["project"].add(project)
        n.props["rank"].add(rank)
        b.put(iri, "text", text)
        for m in re.split(r"[,\s]+", " ".join(str(subs.get(k) or "")
                                              for k in ("metric", "metrics"))):
            if m.strip():
                b.put(iri, "cites", kid(m.strip("[]`")), "metric")
        reader.status(iri, subs.get("status"))
        reader.retired(iri, subs)
        for k, v in subs.items():
            if k not in {"id", "metric", "metrics", "status", "retired", "reason",
                         "retired_reason"} and not empty(v):
                b.note(iri, k, v, "a bullet has no such field")


def default_provenance(plan):
    """An entry the Markdown gave no status is j:inferred: a migration never raises one."""
    onto = ontology()
    for iri, n in plan.nodes.items():
        if onto.BY_NAME[n.cls].claims and not n.props["provenance"]:
            n.props["provenance"].add("inferred")
            plan.defaulted += 1


def required(plan, nodes, file):
    onto = ontology()
    for iri, n in sorted(nodes.items()):
        for p in onto.BY_NAME[n.cls].preds.values():
            if p.card in "1+" and not n.props.get(p.name):
                plan.refuse(f"{file}: {curie(iri)} has no {p.name} - {p.doc}",
                            "add it in the Markdown (docs/legacy-kb-spec.md shows where), then run "
                            "`jsk migrate` again")
        if n.props.get("retired") and not n.props.get("reason"):
            plan.refuse(f"{curie(iri)} is retired with no reason", "add one")


# --- the graph, both ways -------------------------------------------------------------

def to_quads(nodes):
    import pyoxigraph as ox

    onto = ontology()
    out = []
    for iri, n in nodes.items():
        s = ox.NamedNode(iri)
        cls = onto.BY_NAME[n.cls]
        for pname, values in n.props.items():
            for v in values:
                if pname == "a":
                    out.append(ox.Quad(s, ox.NamedNode(onto.RDF_TYPE), ox.NamedNode(onto.J + v)))
                    continue
                p = cls.preds[pname]
                out.append(ox.Quad(s, ox.NamedNode(onto.J + pname), obj(p, v)))
    return out


def obj(p, v):
    import pyoxigraph as ox

    onto = ontology()
    if isinstance(p.obj, onto.Enum):
        return ox.NamedNode(onto.J + v)
    if isinstance(p.obj, (onto.Ref, onto.Concept)):
        return ox.NamedNode(v)

    def lit(text, dt):
        return ox.Literal(text, datatype=ox.NamedNode(onto.XSD + dt))
    if isinstance(v, bool):
        return lit("true" if v else "false", "boolean")
    if isinstance(v, Lex):
        return lit(str(v), v.dt)
    if isinstance(v, int):
        return lit(str(v), "integer")
    if isinstance(v, Decimal):
        return lit(str(v), "decimal")
    if isinstance(v, datetime.date):
        return lit(v.isoformat(), "date")
    return ox.Literal(str(v))


def project(quads):
    """Quads back into the entries dictionary - the other side of the round trip."""
    import pyoxigraph as ox

    onto = ontology()
    nodes = {}
    for q in quads:
        s = q.subject.value
        n = nodes.setdefault(s, Node(onto.class_of(s)))
        if q.predicate.value == onto.RDF_TYPE:
            n.props["a"].add(q.object.value[len(onto.J):])
            continue
        name = q.predicate.value[len(onto.J):]
        p = onto.BY_NAME[n.cls].preds.get(name)
        o = q.object
        if isinstance(o, ox.NamedNode):
            value = o.value[len(onto.J):] if p is not None and isinstance(p.obj, onto.Enum) \
                else o.value
        else:
            dt = o.datatype.value[len(onto.XSD):]
            value = {"integer": lambda t: Lex(t, "integer"), "decimal": lambda t: Lex(t, "decimal"),
                     "date": datetime.date.fromisoformat,
                     "boolean": lambda t: t == "true"}.get(dt, str)(o.value)
        n.props[name].add(value)
    return nodes


def frozen(nodes):
    return {iri: n.frozen() for iri, n in nodes.items()}


def differences(a, b, limit=8):
    out = []
    fa, fb = frozen(a), frozen(b)
    for iri in sorted(set(fa) | set(fb)):
        if fa.get(iri) != fb.get(iri):
            out.append(f"{curie(iri)}: read {fa.get(iri)!r}, wrote {fb.get(iri)!r}"[:300])
    return out[:limit]


def index_view(text, vocab, today):
    """What `jsk index`'s reader sees, normalised to the graph's names."""
    from .kbindex import entries_with_blocks, experience, projects_of, read_kb

    _, by, _ = read_kb(text)
    projects = {}
    for p in projects_of(by):
        b = p["block"]
        projects[kid(b["id"])] = (p["strength"], p["recency"], b["seniority"], p["retired"],
                                  frozenset(vocab.concept(t)[0] for t in p["domains"]),
                                  frozenset(vocab.concept(t)[0]
                                            for t in p["capabilities"] + p["technologies"]))
    roles = entries_with_blocks(by["Roles"], "role") if "Roles" in by else []
    positions = {kid(r["block"]["id"]): (str(r["block"].get("start") or "")[:7],
                                         str(r["block"].get("end") or "")[:7])
                 for r in roles}
    months, _ = experience(roles, today)
    ids = set()
    for title, prefix in (("Metrics", "met_"), ("Open questions", "q_")):
        if title in by:
            _, rows, _ = table(text.split("\n")[by[title]["start"]:by[title]["end"]])
            ids |= {kid(r["id"]) for r in rows if not empty(r.get("id"))}
    return {"projects": projects, "positions": positions, "months": months, "ids": ids}


def graph_view(nodes, today):
    """The same view, read off the graph."""
    from .kbindex import experience

    def one(n, p, default=None):
        v = n.props.get(p)
        return next(iter(v)) if v else default

    def whole(v):
        return int(v) if v is not None else None
    projects, positions, roles, ids = {}, {}, [], set()
    for iri, n in nodes.items():
        if n.cls == "Project":
            projects[iri] = (whole(one(n, "strength")), whole(one(n, "recency")),
                             one(n, "seniority"),
                             bool(n.props.get("retired")), frozenset(n.props.get("domain", ())),
                             frozenset(n.props.get("uses", ())))
        elif n.cls == "Position":
            positions[iri] = (one(n, "start", ""), one(n, "end", ""))
            block = {"id": iri, "start": one(n, "start"), "end": one(n, "end"),
                     "state": one(n, "state")}
            roles.append({"block": block, "start": 0})
        elif n.cls in ("Metric", "Question"):
            ids.add(iri)
    months, _ = experience(roles, today)
    return {"projects": projects, "positions": positions, "months": months, "ids": ids}


def coverage(plan, reader, kb_text):
    """[(line, text, why)] of what the Markdown held and the migration lost.

    The round trip proves the writer: the graph parses back as the entries it was
    written from. This proves the reader. Every YAML value must have been handed on -
    into a triple or a note - and must still be spelled out in kb.ttl, word for word
    by its words and numbers; every non-blank line outside the frontmatter and the
    parsed yaml blocks must have each of its words in kb.ttl or in log.ttl's note.
    Exempt, as layout: section headings, the template's title and fixed seniority list,
    HTML comments, the template's placeholders, and the words of STRUCTURE_WORDS.
    """
    from .graph import record as R
    from .graph.io import parse_text

    found = set(STRUCTURE_WORDS)
    for q in parse_text(kb_text, R.KB).quads:
        for term in (q.subject, q.predicate, q.object):
            found |= tokens(term.value)
            # A term that named a shipped concept by its label is spelled by that label.
            for label in reader.vocab.names.get(term.value, ()):
                found |= tokens(label)
    found |= tokens("\n".join(reader.log_text))
    lost = []
    for leaf in reader.leaves:
        if empty(leaf):
            continue
        if id(leaf) not in plan.used:
            lost.append((leaf.line, str(leaf), "was read and never put in the graph"))
        elif id(leaf) not in plan.unwritten and not tokens(leaf) <= found:
            lost.append((leaf.line, str(leaf), "is in no triple and no note"))
    text = COMMENT.sub(lambda m: "\n" * m.group().count("\n"), "\n".join(reader.lines))
    for n, line in enumerate(text.split("\n"), 1):
        if n in reader.structure or not line.strip() or PLACEHOLDER.fullmatch(line.strip()):
            continue
        if not tokens(line) <= found:
            lost.append((n, line.strip(), "is in no triple and no note"))
    return sorted(lost)


# --- applications ----------------------------------------------------------------------

def find_quote(advert, candidates, terms):
    """The advert's own words for a requirement: its label when the advert says it, else
    the first line of the advert naming the term. None when neither is there."""
    from .graph.rules import squash

    text = squash(advert)
    for c in candidates:
        if c and squash(c) and squash(c) in text:
            return c.strip()
    for line in advert.split("\n"):
        line = re.sub(r"^\s*(?:[-*+]|\d+[.)]|#+)\s+", "", line).strip()
        low = line.lower()
        if line and squash(line) in text and any(t and t.lower() in low for t in terms):
            return line
    return None


def application_stem(name, taken):
    m = DATED_DIR.match(name)
    stem = slug(m.group(2) if m else name, "_") or "application"
    if stem in taken and m:
        stem = f"{stem}_{m.group(1).replace('-', '_')}"
    base, n = stem, 2
    while stem in taken:
        stem, n = f"{base}_{n}", n + 1
    taken.add(stem)
    return stem


def advert_of(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    return "\n".join(lines[closing + 1:]).lstrip("\n") if closing is not None else text


def migrate_applications(plan, vocab, today):
    from .graph.io import normalise
    from .kbindex import KBError, frontmatter, read_posting

    onto = ontology()
    known = {iri: n for iri, n in plan.nodes.items() if n.cls == "Concept"}
    stems = set()
    for d in sorted(glob.glob(os.path.join(glob.escape(plan.root), "applications", "*", ""))):
        d = d.rstrip("/\\")
        name = os.path.basename(d)
        rel = f"applications/{name}"
        src = os.path.join(d, ORIG) if os.path.isfile(os.path.join(d, ORIG)) else \
            os.path.join(d, "posting.md")
        if not os.path.isfile(src):
            if os.path.isfile(os.path.join(d, "application.md")):
                plan.notices.append(f"{rel}: no posting.md, so application.md was not migrated")
            continue
        with open(src, encoding="utf-8") as fh:
            text = normalise(fh.read())
        try:
            front = read_posting(text)
        except KBError as e:
            # A posting still being tailored has no requirements yet, and one requirement
            # written wrongly should not cost the others: they are read one by one below.
            try:
                front, _ = frontmatter(text, f"{rel}/posting.md")
            except KBError as e2:
                plan.notices.append(f"{rel}: posting.md not migrated - {e2}")
                continue
            if front.get("requirements"):
                plan.notices.append(f"{rel}: posting.md - {e}; its requirements are read one "
                                    "by one")
        if not front or empty(front.get("company")) or empty(front.get("title")):
            plan.notices.append(f"{rel}: posting.md has no company: and title: in frontmatter, "
                                "so it was not migrated")
            continue
        stem = application_stem(name, stems)
        post = onto.K + "post_" + stem
        nodes = {}
        b = Builder(plan, nodes)
        b.node(post, "Posting")
        for key in ("company", "title", "url", "seniority"):
            b.put(post, key, front.get(key))
        captured = as_date(front.get("captured"))
        if captured is None:
            m = DATED_DIR.match(name)
            captured = as_date(m.group(1)) if m else \
                datetime.date.fromtimestamp(os.path.getmtime(src))
            plan.notices.append(f"{rel}: no captured: date - recorded as {captured}")
        nodes[post].props["captured"].add(captured)
        nodes[post].props["advert"].add("posting.md")
        for term in as_list(front.get("domains")):
            iri = vocab.concept(term)[0]
            cls = known[iri].props.get("a") if iri in known else {vocab.shipped.get(iri)}
            if cls and "Domain" in cls:
                b.put(post, "domain", iri, "domains")
            else:
                b.note(post, "domain", term, "no Domain concept of that name")
        advert = advert_of(text)
        reqs = front.get("requirements") or []
        if not isinstance(reqs, list):
            b.note(post, "requirements", reqs, "not a list")
            reqs = []
        rids = set()
        for r in reqs:
            if not isinstance(r, dict) or empty(r.get("value")):
                b.note(post, "requirement", r, "no value:")
                continue
            value = str(r["value"]).strip()
            iri = vocab.concept(value)[0]
            concept = iri if iri in known or iri in vocab.shipped else None
            terms = [str(r.get("label") or ""), value, value.replace("-", " ")]
            if concept in known:
                terms += sorted(known[concept].props.get("label", ()))
            quote = find_quote(advert, [str(r.get("label") or "")], terms)
            if quote is None:
                b.note(post, "requirement", r, "the advert says neither its label nor its term, "
                       "so it is not a requirement here")
                continue
            base = f"{onto.K}req_{stem}_{slug(value, '_')}"
            rid, n = base, 2
            while rid in rids:
                rid, n = f"{base}_{n}", n + 1
            rids.add(rid)
            b.node(rid, "Requirement")
            nodes[rid].props["posting"].add(post)
            b.put(rid, "asked", value)
            if not b.put(rid, "necessity", r.get("necessity")):
                nodes[rid].props["necessity"].add("implicit")
            b.put(rid, "quote", quote)
            if concept:
                nodes[rid].props["concept"].add(concept)
            if not empty(r.get("label")) and quote != str(r["label"]).strip():
                b.note(rid, "label", r["label"])
            for k, v in r.items():
                if k not in ("value", "necessity", "label", "kind") and not empty(v):
                    b.note(rid, k, v, "a requirement has no such field")
        for k, v in front.items():
            if k not in ("company", "title", "url", "seniority", "captured", "domains",
                         "requirements") and not empty(v):
                b.note(post, k, v, "a posting has no such field")
        files = {f"{rel}/posting.ttl": ("posting", nodes)}
        app = application(plan, d, rel, stem, post)
        if app is not None:
            files[f"{rel}/application.ttl"] = ("application", app)
        for file, (kind, ns) in files.items():
            required(plan, ns, file)
        if plan.refusals:
            continue
        from .graph.writer import write
        for file, (kind, ns) in files.items():
            plan.files[file] = write(to_quads(ns), kind)
        if src.endswith("posting.md"):
            plan.copies.append((f"{rel}/posting.md", f"{rel}/{ORIG}"))
        plan.files[f"{rel}/posting.md"] = advert if advert.endswith("\n") else advert + "\n"
        plan.apps += 1


def application(plan, d, rel, stem, post):
    """application.ttl's entries from application.md, with the links its resume.json
    carried; None when the application was never frozen."""
    from .kbindex import KBError, frontmatter

    onto = ontology()
    path = os.path.join(d, "application.md")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        text = fh.read().replace("\r\n", "\n")
    try:
        front, body = frontmatter(text, f"{rel}/application.md")
    except KBError as e:
        plan.notices.append(f"{rel}: application.md not migrated - {e}")
        return None
    submitted = front.get("submitted")
    if submitted is False or str(submitted).strip().lower() == "false":
        submitted = False
    else:
        submitted = as_date(submitted)
    if submitted is None:
        plan.notices.append(f"{rel}: application.md has no submitted: date or false, so it was "
                            "not migrated")
        return None
    app = onto.K + "app_" + stem
    nodes = {}
    b = Builder(plan, nodes)
    b.node(app, "Application")
    nodes[app].props["posting"].add(post)
    nodes[app].props["submitted"].add(submitted)
    b.put(app, "view", front.get("view"))
    b.put(app, "channel", front.get("channel"))
    for doc in as_list(front.get("documents")):
        b.put(app, "document", doc)
    record = os.path.join(d, "resume.json")
    if os.path.isfile(record):
        with open(record, "rb") as fh:
            nodes[app].props["recordSha256"].add(hashlib.sha256(fh.read()).hexdigest())
        for aid, _ in achievements(record):
            iri = onto.K + aid
            if iri in plan.nodes and plan.nodes[iri].cls == "Achievement":
                nodes[app].props["carried"].add(iri)
                for m in plan.nodes[iri].props.get("cites", ()):
                    if m + ".v1" in plan.nodes:
                        nodes[app].props["carriedVersion"].add(m + ".v1")
            else:
                plan.notices.append(f"{rel}: resume.json's {aid} is not a bullet of the "
                                    "knowledge base, so it is not carried")
    for k, v in front.items():
        if k not in ("company", "title", "view", "submitted", "channel", "documents") \
                and not empty(v):
            b.note(app, k, v, "an application has no such field")
    lines = body.split("\n")
    at = next((i for i, line in enumerate(lines) if re.match(r"^#+\s*Timeline\s*$", line)), None)
    rest = lines if at is None else lines[:at]
    header, rows, leftover = table(lines[at + 1:]) if at is not None else (None, [], [])
    rest = clean(rest + leftover)
    if rest:
        b.note(app, "text", "\n".join(rest))
    ids = set()
    for row in rows:
        when = row.get("date", "").strip()
        day = as_date(when)
        kind = row.get("event", "").strip()
        eid_kind = kind if kind in onto.ENUMS["eventKind"] else "note"
        base = (f"{onto.K}evt_{stem}_{day.isoformat().replace('-', '_') if day else 'unknown'}"
                f"_{eid_kind.replace('-', '_')}")
        eid, n = base, 2
        while eid in ids:
            eid, n = f"{base}_{n}", n + 1
        ids.add(eid)
        b.node(eid, "Event")
        nodes[eid].props["application"].add(app)
        nodes[eid].props["date"].add(day if day else "unknown")
        if when and not day and when != "unknown":
            b.note(eid, "date", when, "not YYYY-MM-DD or unknown")
        nodes[eid].props["kind"].add(eid_kind)
        if eid_kind != kind:
            b.note(eid, "event", kind, "not in the pipeline vocabulary")
        b.put(eid, "channel", row.get("channel"))
        b.put(eid, "due", row.get("due"))
        if not empty(row.get("note")):
            nodes[eid].props["note"].add(row["note"].strip())
        for k, v in row.items():
            if k not in EVENT_COLUMNS and not empty(v):
                b.note(eid, k, v, "a column the timeline has no field for")
    return nodes


# --- the migration ---------------------------------------------------------------------

def plan_migration(kb_path, today=None):
    """The whole migration, checked and written to memory; nothing touches disk."""
    from .graph import record as R
    from .graph import store as S
    from .graph.io import normalise, parse_text, sha256
    from .graph.rules import squash
    from .graph.writer import write
    from .kbindex import KBError

    onto = ontology()
    today = today or datetime.date.today()
    root = os.path.dirname(os.path.abspath(kb_path))
    plan = Plan(root)
    if os.path.exists(os.path.join(root, R.KB)):
        raise Refused([(f"{R.KB} already exists in {root}: this knowledge base was migrated",
                        "`jsk kb check` reads it; to migrate again, move career/kb.ttl and "
                        "career/log.ttl aside first")])
    with open(kb_path, encoding="utf-8") as fh:
        text = normalise(fh.read())
    vocab = Vocabulary()
    try:
        reader = Reader(plan, text, vocab, today)
        reader.read()
        mint_bullets(plan, reader, root)
        default_provenance(plan)
        required(plan, plan.nodes, R.KB)
        before = index_view(text, vocab, today)
    except KBError as e:
        raise Refused([(str(e), e.fix)]) from None
    if plan.refusals:
        raise Refused(plan.refusals)

    migrate_applications(plan, vocab, today)
    if plan.refusals:
        raise Refused(plan.refusals)

    # The round trip: written, parsed back, projected - and equal, datatype and exact
    # characters, to the entries the reader built. That proves the writer; coverage()
    # then proves the reader, against the Markdown itself.
    quads = R.stamp(to_quads(plan.nodes), 1, today)
    kb_text = write(quads, "kb")
    written = project(parse_text(kb_text, R.KB).quads)
    expected = {i: n for i, n in plan.nodes.items()}
    expected[onto.K + "kb"].props["revision"] = {1}
    wrong = differences(expected, written)
    after = graph_view(written, today)
    for part in ("projects", "positions", "months", "ids"):
        if before[part] != after[part]:
            wrong.append(f"jsk index reads {part} as {before[part]!r}, the graph as "
                         f"{after[part]!r}"[:300])
    reasons = [(f"the graph does not read back as the Markdown: {w}",
                "nothing was written; report this with the knowledge base's section")
               for w in wrong]
    lost = coverage(plan, reader, kb_text)
    reasons += [(f"line {n}: {line[:100]!r} {why}",
                 "a jsk bug - nothing was written; report it with that line")
                for n, line, why in lost[:COVERAGE_SHOWN]]
    if len(lost) > COVERAGE_SHOWN:
        reasons.append((f"... and {len(lost) - COVERAGE_SHOWN} more lines like these", None))
    if reasons:
        raise Refused(reasons)

    log_path = os.path.join(root, "log.md")
    history = []
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8") as fh:
            history.append(normalise(fh.read()).strip())
    if reader.log_text:
        history.append("## Log (from user-knowledgebase.md)\n" + "\n".join(reader.log_text))
    minted = sorted(i for i in plan.nodes if i.startswith(onto.K) or
                    plan.nodes[i].props.get("a"))
    log = R.entry(1, today, "migrate",
                  f"Migrated from {os.path.basename(kb_path)} (kb: {reader.front.get('kb')}) by "
                  f"jsk migrate: {len(plan.nodes)} entries, {plan.apps} application(s)."
                  + (" log.md's history is kept in this entry's note." if history else ""),
                  sha256(kb_text), minted=minted)
    if history:
        import pyoxigraph as ox
        log.append(ox.Quad(ox.NamedNode(onto.K + "rev_1"), ox.NamedNode(onto.J + "note"),
                           ox.Literal("\n\n".join(history))))
    plan.files[R.KB] = kb_text
    plan.files[R.LOG] = write(log, "log")

    # The quote check reads posting.md from disk, where the old one still is: so it is
    # made here against the advert as it will be written.
    for name, content in plan.files.items():
        if name.endswith("posting.ttl"):
            advert = squash(plan.files[name[:-len("posting.ttl")] + "posting.md"])
            for q in parse_text(content, name).quads:
                if q.predicate.value == onto.J + "quote" and squash(q.object.value) not in advert:
                    plan.refuse(f"{name}: {curie(q.subject.value)}'s quote is not in the advert",
                                "a jsk bug: report it")
    ttl = {n: t for n, t in plan.files.items() if n.endswith(".ttl")}
    store = S.load(root, texts=ttl)
    fails = store.fails()
    if fails:
        plan.refuse(f"the migrated record would not validate - {len(fails)} FAIL, each naming "
                    "the file it would write (--dry-run prints it)",
                    "fix each in the Markdown, then run `jsk migrate` again")
        plan.refusals += [(f.text(), None) for f in fails]
    if plan.refusals:
        raise Refused(plan.refusals)
    plan.records = records_of(root)
    plan.store = store
    return plan


def write_plan(plan):
    """Every file, kb.ttl and log.ttl last: a kb.ttl that exists is a migration that finished."""
    import shutil

    from .graph import record as R

    for src, dst in plan.copies:
        if not os.path.exists(os.path.join(plan.root, dst)):
            shutil.copy2(os.path.join(plan.root, src), os.path.join(plan.root, dst))
            print(f"kept   {dst} (the old posting.md, whole)")
    for name, text in sorted(plan.files.items()):
        if name in (R.KB, R.LOG):
            continue
        path = os.path.join(plan.root, name)
        R.replace(R.staged(path, text), path)
        print(f"wrote  {name}")
    os.makedirs(os.path.join(plan.root, "career"), exist_ok=True)
    R.commit(plan.root, plan.files[R.KB], plan.files[R.LOG])
    print(f"wrote  {R.KB}")
    print(f"wrote  {R.LOG} (r1, by migrate)")


def claims_gate(root, records):
    """The claims gate over every resume.json, when this install has it (P5)."""
    try:
        from .gates import claims
    except ImportError:
        print("claims   gate not available (jsk.gates.claims is not in this install) - "
              "no resume.json was checked against the new record")
        return 0
    from .graph import store as S

    store = S.load(root)                   # the record just written, as the gate reads it
    worst = 0
    for record in records:
        name = os.path.relpath(record, root).replace("\\", "/")
        try:
            report = claims.check(record, store)
        except Exception as e:                      # noqa: BLE001 - a verdict, not a traceback
            print(f"claims   did not run on {name}: {type(e).__name__}: {e}")
            worst = 1                               # a gate that did not run did not pass
            continue
        fails = report.fails
        print(f"claims   {name}: {len(fails)} FAIL")
        for f in fails:
            print(f"  {f}")
        worst = max(worst, 1 if fails else 0)
    return worst


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if wants_help(args):
        print(docstring_usage(__doc__))
        return 0
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: jsk migrate <user-knowledgebase.md> [--dry-run]")
        return 2
    path = args[0]
    if not os.path.isfile(path):
        print(f"not a file: {path}")
        print("fix:  pass the user-knowledgebase.md to migrate")
        return 2
    try:
        import pyoxigraph  # noqa: F401
        import yaml  # noqa: F401
        from markdown_it import MarkdownIt  # noqa: F401
    except ImportError as e:
        print(f"FAIL  jsk migrate needs markdown-it-py, pyyaml and pyoxigraph: {e}")
        print('fix:  python -m pip install "jsk-resume[migrate]"')
        return 1
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    try:
        plan = plan_migration(path)
    except Refused as e:
        for detail, fix in e.reasons:
            print(f"REFUSED  {detail}" + (f"\n        fix: {fix}" if fix else ""))
        print("nothing was written")
        return 1
    for note in plan.notices:
        print(f"note     {note}")
    if plan.defaulted:
        print(f"note     {plan.defaulted} entries had no status: and are j:inferred")
    print(f"round trip  ok: {len(plan.nodes)} entries read back as written, and every value "
          f"and line of the Markdown is in a triple or a note; {plan.apps} application(s)")
    if dry:
        for src, dst in plan.copies:
            print(f"\nwould copy {src} to {dst}")
        for name, text in sorted(plan.files.items()):
            print(f"\n--- would write {name} ({text.count(chr(10))} lines)")
            print(text, end="")
        print("\ndry run: nothing was written")
        return 0
    from .graph import record as R
    from .graph import store as S
    try:
        write_plan(plan)
    except (OSError, R.RecordError) as e:
        print(f"FAIL  {e}\n        fix: {getattr(e, 'fix', 'check the folder is writable')}")
        return 1
    store = S.load(plan.root)
    st = R.state(store)
    print(f"record   {st.kind} at r1 - {len(store.fails())} FAIL, {len(store.warns())} WARN "
          f"(`jsk kb check` lists them)")
    claims_gate(plan.root, plan.records)
    print("nothing was deleted: user-knowledgebase.md, log.md and every application.md stay "
          "where they are")
    return 0 if not store.fails() else 1


if __name__ == "__main__":
    sys.exit(main())
