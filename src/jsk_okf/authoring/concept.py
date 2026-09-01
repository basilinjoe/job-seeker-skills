"""One concept file: emit a new one, or change one key of an existing one.

This module formats and does not judge. Whether a value is *allowed* is
schema.py's question; whether it needs quoting is this one's.

The emitter used to live in init_bundle.py. It moved here rather than being
copied, because the spec this implements forbids a second definition of the
format - and two emitters disagreeing about quoting is exactly how a bundle
acquires a file that reads differently from every other file in it.

`new()` emits LF and the caller owns the file's line convention. The splice path
does not have that luxury: it is handed a file that already exists, so read()
records the convention it found and text() writes it back. A bundle scaffolded
on Windows is entirely CRLF, and rewriting one key must not rewrite every line.
"""

import re

# Guarded, not unguarded: init_bundle.py imports this module and ARCHITECTURE.md
# lists it among the scripts that run on a bare Python. Emitting needs no YAML;
# only reading does, so the absence is reported by the readers rather than by an
# ImportError at somebody else's import time.
try:
    import yaml
except ImportError:                                  # pragma: no cover
    yaml = None

# A bare scalar is one YAML will read back as the string we wrote. Slugs, dates,
# years and enum values qualify; anything with a colon, a quote, leading or
# trailing space, or a leading indicator character does not. When in doubt this
# quotes, because an over-quoted slug is ugly and an under-quoted colon is a
# parse error in somebody's record.
#
# `\Z` rather than `$`: in Python `$` also matches immediately before a trailing
# newline, so "abc\n" matched BARE and was emitted bare, ending its own
# frontmatter line early.
BARE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*\Z")

# The three that have a short escape, plus the two that must be escaped for the
# value to survive at all.
SHORT_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}

# YAML 1.1 reads these bare words as booleans or null, and these shapes as
# numbers, so a string that looks like one stops being a string.
KEYWORDS = frozenset("y n yes no true false on off null".split())

# PyYAML's int resolver is [-+]?(?:0|[1-9][0-9_]*) and its float admits a
# trailing dot, so underscores and `5.` both have to be caught. BARE allows `_`,
# which is how "12_000" reached the file as the integer 12000.
NUMERIC = re.compile(r"^[-+]?(\d[\d_]*|[\d_]*\.[\d_]*)([eE][-+]?\d+)?\Z"
                     r"|^[-+]?0[xXbBoO][0-9a-fA-F_]+\Z")

# A year, a year-month or a full date, emitted bare on purpose. bundle-spec.md
# writes all three that way and reads precision from what was written, so
# quoting one of the three would make a hand-edited concept and a generated one
# disagree about the same field. What each reads back as differs - 2019 is an
# int, 2019-04 a string, 2019-04-01 a date - and okf_compile.loose_date
# normalises all three, which is why the inconsistency is tolerable here and
# nowhere else.
DATEISH = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?\Z")


def _must_escape(ch):
    """Characters YAML forbids, plus every one some splitter treats as a break.

    The first group makes the file unreadable to safe_load - a form feed out of
    an extracted PDF is the realistic way one arrives. The second ends a value
    early for anything using str.splitlines(), which is the defect \\Z was added
    to prevent wearing different bytes, and U+0085 does it silently: it reads
    back as a space rather than raising.
    """
    code = ord(ch)
    return code < 0x20 or code == 0x7F or code in (0x85, 0x2028, 0x2029)


def _quoted(text):
    """A double-quoted scalar: escaped, and always one physical line.

    Per character rather than by table replacement, because the set that has to
    be escaped is a range - every C0 control, DEL, and the three Unicode breaks
    - and a replace() chain over a range would be a table nobody could check.
    """
    out = []
    for ch in text:
        if ch in SHORT_ESCAPES:
            out.append(SHORT_ESCAPES[ch])
            continue
        code = ord(ch)
        if _must_escape(ch):
            out.append(f"\\x{code:02x}" if code < 0x100 else f"\\u{code:04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _coerced(text):
    """True where YAML would read the bare form back as a non-string.

    Date shapes are exempt and deliberately so - see DATEISH.
    """
    if DATEISH.match(text):
        return False
    return text.lower() in KEYWORDS or bool(NUMERIC.match(text))


def scalar(value):
    """One frontmatter value, as it should be written.

    Lists are flow style - `[a, b]` - because that is what every concept in a
    real bundle uses and a block list here would make one file look hand-made.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(scalar(v) for v in value) + "]"
    if not isinstance(value, str):
        # Not a judgement about whether the value is allowed - that is
        # schema.py's. This is the formatter declining to invent a format, after
        # str() silently turned None into the word "None" inside a list and a
        # float into a quoted string.
        raise ValueError(
            f"scalar({value!r}): a str, int, float, bool or list of them")
    if BARE.match(value) and not _coerced(value):
        return value
    return _quoted(value)


# A key needs the same guarantee as a value - that YAML reads back what was
# written - but not the same rule. Underscores are ordinary in a key
# (`headline_metric`, `okf_bundle`) and DATEISH does not apply: a value of 2019
# is meant to read as a year, a key of "2019" is meant to stay a string. Keys
# used to be interpolated raw, so `{"yes": 3}` was emitted `yes: 3` and read
# back as `{True: 3}`, and a key containing a colon ended its own line early.
BARE_KEY = re.compile(r"^[A-Za-z_][\w./-]*\Z")


def key_text(key):
    """One frontmatter key, as it should be written."""
    if (BARE_KEY.match(key) and key.lower() not in KEYWORDS
            and not NUMERIC.match(key)):
        return key
    # _quoted rather than scalar: the DATEISH exemption is a concession made for
    # values, and a key that looks like a date is still just a key.
    return _quoted(key)


def frontmatter(type_name, keys):
    """The `---` block for a new concept. `type` leads; None values are dropped.

    A mapping, or a list of mappings, goes through structured() - so a posting's
    `requirements` and a view's `include` can be written by the same call that
    writes a title. Defined after structured() would read better and cannot be:
    new() is called by init_bundle.py, and Python resolves the name at call time,
    so the order here is only about which definition a reader meets first.
    """
    lines = ["---", f"type: {type_name}"]
    for key, value in keys.items():
        if value is None:
            continue
        if isinstance(value, dict) or (
                isinstance(value, (list, tuple))
                and any(isinstance(item, dict) for item in value)):
            lines.extend(structured(key, value))
            continue
        lines.append(f"{key_text(key)}: {scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def new(type_name, keys, body):
    """A whole concept file: frontmatter, a blank line, then the body."""
    body = body or ""
    if body and not body.endswith("\n"):
        body += "\n"
    return frontmatter(type_name, keys) + "\n" + body


class Unsplicable(Exception):
    """This file cannot be changed safely, and saying so beats guessing.

    Carries the `fix:` line the rest of the tooling prints, because a refusal a
    person cannot act on is only marginally better than a mangled file.
    """


SPLIT = re.compile(r"^---\n(.*?\n)---\n", re.S)

# read() and survey() raise the same words for the same defect, so the text
# lives once rather than in two copies that can drift apart.
NOT_A_MAPPING = ("frontmatter is not a mapping\n"
                 "fix:  a concept's block is `key: value` lines")


def _need_yaml():
    """The one place the missing dependency is reported.

    Every reader calls it, rather than only read(): locate() reaches yaml too,
    through a Concept a caller built by hand, and on a bare Python that used to
    surface as an AttributeError on None instead of a line saying what to
    install.
    """
    if yaml is None:
        raise Unsplicable("reading a concept needs pyyaml, which is not installed\n"
                          "fix:  pip install pyyaml")


class Concept:
    """One concept file, split into the parts a command needs.

    `lines` is the frontmatter as written, so a splice can put a line back where
    it found it. `meta` is the same block parsed, for anything that needs to read
    a value rather than rewrite one. `newline` is the file's own convention,
    carried so that rewriting one key does not rewrite every line ending.

    `gap` is whatever separated the closing `---` from the body, carried for the
    same reason. Hardcoding one blank line invented one in a concept written
    without it and swallowed the extras in a concept written with three - a byte
    nobody asked about, on every splice, which is the defect this module exists
    to avoid. It defaults to one blank line, which is the shape new() emits.
    """

    def __init__(self, path, lines, meta, body, newline="\n", gap="\n"):
        self.path = path
        self.lines = lines
        self.meta = meta
        self.body = body
        self.newline = newline
        self.gap = gap

    def text(self, lines=None):
        """The whole file, in the line ending it arrived in."""
        lines = self.lines if lines is None else lines
        if lines:
            out = f"---\n" + "\n".join(lines) + f"\n---\n{self.gap}{self.body}"
        else:
            # No keys left at all - every one deleted. The general form would
            # emit `---\n\n---\n`, inventing a blank line where the block was.
            out = f"---\n---\n{self.gap}{self.body}"
        return out if self.newline == "\n" else out.replace("\n", self.newline)


def read(path):
    """Open one concept file and parse it, or refuse with a reason naming it.

    `newline=""` rather than text mode: universal newlines would hand back "\\n"
    for a CRLF file, and writing that out again would change every line ending in
    somebody's concept in order to rewrite one key. A bundle scaffolded on
    Windows is entirely CRLF, so this is the common case, not the exotic one.
    """
    _need_yaml()
    with open(str(path), encoding="utf-8", newline="") as handle:
        return parse(handle.read(), path)


def parse(raw, path):
    """One concept's text, split into the parts a command needs.

    Separate from read() so a caller that already has the text - a dry run, or a
    command holding an edit it has not written yet - gets the same refusals
    instead of building a Concept by hand and meeting a raw YAMLError.

    Known limit: CRLF wins if it appears at all, so a file mixing the two - a
    CRLF block over an LF body, which is what two tools disagreeing leaves
    behind - is rewritten wholly in CRLF. Every option rewrites something in a
    file that is already inconsistent, and this one at least leaves it
    consistent afterwards. Recorded as a decision, not an oversight.
    """
    _need_yaml()
    newline = "\r\n" if "\r\n" in raw else "\n"
    raw = raw.replace("\r\n", "\n")
    # Named rather than folded into "no frontmatter", which is visibly untrue of
    # a file whose first visible characters are --- and sends the reader looking
    # at the wrong line. Notepad and PowerShell redirection both write one.
    if raw.startswith("\ufeff"):
        raise Unsplicable(
            f"{path}: starts with a byte-order mark, so the --- is not the "
            f"first thing in the file\n"
            f"fix:  re-save it as UTF-8 without a BOM - the compiler skips a "
            f"concept with one too, silently")
    match = SPLIT.match(raw)
    if not match:
        raise Unsplicable(f"{path}: no frontmatter\n"
                          f"fix:  a concept opens with a --- block naming its type")
    # Exactly the one newline SPLIT captured, not rstrip("\n"): a blank line at
    # the end of the block is the author's, and rstrip deleted it on every
    # splice - the same defect as the gap below, one line further up.
    block = match.group(1)[:-1]
    tail = raw[match.end():]
    gap = tail[:len(tail) - len(tail.lstrip("\n"))]
    body = tail.lstrip("\n")
    try:
        meta = yaml.safe_load(block) or {}
    except yaml.YAMLError as exc:
        raise Unsplicable(f"{path}: frontmatter is not valid YAML: {exc}\n"
                          f"fix:  open it and correct the block by hand")
    if not isinstance(meta, dict):
        raise Unsplicable(f"{path}: {NOT_A_MAPPING}")
    return Concept(path, block.split("\n"), meta, body, newline, gap)


def survey(block, path):
    """Every top-level key, with the node that defines its value.

    Asked of the parser rather than worked out from the text, because no rule
    written about one line can answer it. Reading the line after the key could
    not tell a top-level key from a column-0 continuation of a flow scalar, so
    `title: "a` over `b: c"` spliced into a file that still parsed and had
    silently gained a key; and it could not tell a comment from a block
    scalar's first content line. Neither fact is in the adjacent line. It is in
    the parser, which is the thing that read them.
    """
    _need_yaml()
    node = yaml.compose(block, Loader=yaml.SafeLoader)
    if node is None:
        return {}
    if not isinstance(node, yaml.MappingNode):
        raise Unsplicable(f"{path}: {NOT_A_MAPPING}")
    out = {}
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode):
            # Unreachable through read(): a mapping or sequence key is
            # unhashable, so safe_load refuses the block first. Kept as the
            # guard for a caller that composes its own, and noted so nobody
            # writes a test they cannot make fire.
            raise Unsplicable(
                f"{path}: a key here is written in explicit `? key` form\n"
                f"fix:  write it as `key: value` - this command places a value "
                f"beside a key it can name, and cannot name that one")
        out.setdefault(key_node.value, []).append((key_node, value_node))
    return out


def has_anchor(block):
    """An anchor or alias anywhere in the block.

    Necessity rather than caution, so the reasoning survives a maintainer who
    wants to handle one key at a time: a merge key folds the merged mapping's
    keys into what safe_load constructs, and survey() cannot see them at all -
    `<<: *defaults` leaves `s` in meta with no line anywhere defining it, so a
    partial handler asked to set `s` appends a second definition. The weaker
    argument, true as well, is that splicing either end of an anchor breaks the
    other: replacing `a: &x 1` leaves `b: *x` pointing at nothing.

    A bundle has no use for either, so the whole block is refused.
    """
    _need_yaml()
    for event in yaml.parse(block, Loader=yaml.SafeLoader):
        if getattr(event, "anchor", None):
            return True
    return False


def _nodes(doc, key):
    """`key`'s (key node, value node), or None. Refuses what cannot be spliced.

    Shared by locate() and extent(), which want the same two guards - no anchor
    anywhere in the block, and this key written exactly once - and then disagree
    about multi-line values: locate() refuses one, extent() is the function that
    exists to measure one.
    """
    block = "\n".join(doc.lines)
    if has_anchor(block):
        raise Unsplicable(
            f"{doc.path}: the block uses a YAML anchor or alias\n"
            f"fix:  write the value out in full - replacing one end of an anchor "
            f"leaves the other pointing at nothing, so this command will not "
            f"touch the block at all")
    found = survey(block, doc.path).get(key)
    if not found:
        return None
    if len(found) > 1:
        # +2: the --- above the block, and 1-indexing.
        rows = ", ".join(str(k.start_mark.line + 2) for k, _ in found)
        # Counted rather than always "twice": "appears twice, at lines 3, 4, 5"
        # reads like a bug in the tool, which undermines a message whose whole
        # job is to be trusted. "twice" is kept where it is true, because it is
        # the word a person would use for the case that actually happens.
        times = "twice" if len(found) == 2 else f"{len(found)} times"
        raise Unsplicable(
            f"{doc.path}: `{key}` appears {times}, at lines {rows}\n"
            f"fix:  delete the wrong one by hand - which is right is not "
            f"something this command can know")
    return found[0]


def locate(doc, key):
    """Where `key`'s value sits: (line, first column, column after it). Or None.

    Columns rather than a line index, so a splice can keep the key exactly as
    written and keep whatever follows the value - a trailing comment is the
    author's, and rewriting the whole line threw it away.

    `key` is matched as the text written in the file, not as the key `meta`
    holds: safe_load constructs `yes` into True and `2019` into an int, and a
    caller passing one of those back would not match the line that produced it.
    """
    nodes = _nodes(doc, key)
    if nodes is None:
        return None
    key_node, value_node = nodes
    kline = key_node.start_mark.line
    start, end = value_node.start_mark, value_node.end_mark
    if start.line == end.line and start.column == end.column:
        # An implicit null - `title:` with nothing after it. There is no value
        # text to cut, so both edges sit where the value would have begun, which
        # pyyaml puts immediately after the colon. Tested as zero width rather
        # than as an empty `value`, because `title: ""` is also an empty value
        # and does have text: cutting nothing there would have written
        # `title: New""`. Searching the line for the colon instead used to find
        # one inside a key that contained one, and wrote `a: New:` for `a::`.
        return kline, start.column, start.column
    if start.line != kline:
        raise Unsplicable(
            f"{doc.path}: `{key}` is written as a block, over several lines\n"
            f"fix:  this command writes a value on one line, and rewriting the "
            f"block would reflow lines nobody asked it to touch. Change it by "
            f"hand.")
    # Any value crossing the newline is a continuation, and cutting its first
    # line orphans the rest. There is deliberately no exemption for a value
    # ending exactly at column 0 of the next line: 1140 shape-by-context
    # combinations produced no such node - a block scalar lands two lines down
    # or further, and plain and flow scalars never cross at all - so the
    # allowance that used to be here described nothing, and a node that did
    # reach it would be a wrapped value this must refuse.
    if end.line > kline:
        raise Unsplicable(
            f"{doc.path}: `{key}`'s value does not end on the line it starts on\n"
            f"fix:  this command writes a value on one line, and replacing only "
            f"the first line of a wrapped value would leave the rest of it "
            f"behind. Change it by hand.")
    return kline, start.column, end.column


def set_key(doc, key, value):
    """The file's text with `key` set, and every other byte where it was.

    `value=None` deletes the key's whole line, including any comment trailing on
    it - the comment annotates the key that is going, so it goes too. Deleting a
    key that is not there changes nothing. Everything else replaces just the
    value, or appends `key: value` if the block does not define it yet.
    """
    if not isinstance(key, str):
        # `doc.meta`'s keys are what safe_load *constructed*: `yes` arrives as
        # True and `2019` as an int. Passing one of those back matched no line,
        # so set_key appended a second definition beside the first - the
        # duplicate locate() then refuses to touch forever.
        raise Unsplicable(
            f"{doc.path}: `{key!r}` is a {type(key).__name__}, not a key\n"
            f"fix:  pass the key as it is written in the file - a key read out "
            f"of meta may have been constructed into something else")
    lines = list(doc.lines)
    location = locate(doc, key)
    if value is None:
        if location is not None:
            del lines[location[0]]
        return doc.text(lines)
    rendered = scalar(value)
    if location is None:
        # Above any trailing blank line rather than after it: the blank line is
        # the author's, and a key appended below it reads as a second stanza.
        at = len(lines)
        while at and not lines[at - 1].strip():
            at -= 1
        lines.insert(at, f"{key_text(key)}: {rendered}")
        return doc.text(lines)
    index, cut_start, cut_end = location
    line = lines[index]
    if cut_start == cut_end:
        rendered = " " + rendered      # an implicit null: nothing to replace
    lines[index] = line[:cut_start] + rendered + line[cut_end:]
    return doc.text(lines)


# --- structured values ----------------------------------------------------------
#
# Two keys in the format hold something scalar() cannot write: a posting's
# `requirements` is a list of mappings, and a view's `target`, `include` and
# `budget` are a mapping, a list of mappings and a mapping. urs/view-format.md
# defines all four, and until this existed the write layer could not express a
# posting or a view at all.
#
# Block style rather than flow, and that decision is about who reads them. A view
# with six includes of four achievements each is one 300-character line in flow
# style - valid YAML that no person will ever edit by hand, in a format sold on
# any editor opening it. So these keys are the one place a value spans lines, and
# set_structured() below is what makes a multi-line value amendable: it replaces
# the key's whole extent, which is measured rather than guessed.
#
# `location` stays unwritable. It is a URS mapping validate_urs.py checks nowhere,
# so writing one would be wrong shape that nothing catches - see schema.py.


def structured(key, value, indent=0):
    """One key whose value is a mapping, or a list of mappings, as lines.

    Nested one level and no further, which is the whole of what the format uses.
    A deeper structure raises rather than emitting something plausible: every
    consumer of these keys - validate_urs.py's VIEW_KEYS, okf_compile.posting() -
    reads exactly this shape, and inventing a third level would write a document
    only this module understands.
    """
    pad = " " * indent
    if isinstance(value, dict):
        lines = [f"{pad}{key_text(key)}:"]
        for name, item in value.items():
            if item is None:
                continue
            lines.extend(_nested(name, item, indent + 2))
        if len(lines) == 1:
            # Every value was None, so the mapping is empty. `key:` alone reads
            # back as null rather than as {}, which is a different document.
            return [f"{pad}{key_text(key)}: {{}}"]
        return lines
    if isinstance(value, (list, tuple)):
        if not value:
            return [f"{pad}{key_text(key)}: []"]
        lines = [f"{pad}{key_text(key)}:"]
        for entry in value:
            if not isinstance(entry, dict):
                # A flat list belongs in scalar(), which writes it in flow style
                # like every other list in a bundle. Reaching here means a caller
                # chose the wrong function, and guessing which it meant would put
                # two shapes of list in one file.
                raise ValueError(
                    f"structured({key!r}): a list here holds mappings - a list of "
                    f"scalars is scalar()'s, and flow style")
            first = True
            for name, item in entry.items():
                if item is None:
                    continue
                rendered = _nested(name, item, indent + 4)
                if first:
                    rendered[0] = f"{pad}  - " + rendered[0].lstrip()
                    first = False
                lines.extend(rendered)
            if first:
                lines.append(f"{pad}  - {{}}")
        return lines
    return [f"{pad}{key_text(key)}: {scalar(value)}"]


def _nested(key, value, indent):
    """One key inside a structured value. Scalars and flat lists only."""
    pad = " " * indent
    if isinstance(value, dict) or (isinstance(value, (list, tuple))
                                   and any(isinstance(v, dict) for v in value)):
        raise ValueError(
            f"structured: {key!r} nests a third level, which the format does not "
            f"use - a posting's requirements and a view's include are one level deep")
    return [f"{pad}{key_text(key)}: {scalar(value)}"]


def extent(doc, key):
    """(first line, last line) of `key` and its whole value, or None.

    Where locate() refuses a value that does not end on the line it starts on,
    this measures one. The measurement is the parser's rather than a rule about
    indentation: pyyaml's end_mark for a block collection points at column 0 of
    the line *after* it, so the last line is one above - and for a value that
    ends mid-line it is that line itself.
    """
    nodes = _nodes(doc, key)
    if nodes is None:
        return None
    key_node, value_node = nodes
    first = key_node.start_mark.line
    end = value_node.end_mark
    last = end.line - 1 if end.column == 0 and end.line > first else end.line
    return first, max(first, last)


def set_structured(doc, key, value):
    """The file's text with `key` set to a mapping or list of mappings.

    The key's whole extent is replaced, so this reflows that key and no other. A
    key being deliberately rewritten is the one place reflowing is not a liberty:
    its value is new text either way.
    """
    lines = list(doc.lines)
    rendered = structured(key, value)
    span = extent(doc, key)
    if span is None:
        at = len(lines)
        while at and not lines[at - 1].strip():
            at -= 1
        lines[at:at] = rendered
        return doc.text(lines)
    first, last = span
    lines[first:last + 1] = rendered
    return doc.text(lines)
