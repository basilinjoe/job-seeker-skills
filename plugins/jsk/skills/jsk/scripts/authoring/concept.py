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


def frontmatter(type_name, keys):
    """The `---` block for a new concept. `type` leads; None values are dropped."""
    lines = ["---", f"type: {type_name}"]
    for key, value in keys.items():
        if value is None:
            continue
        lines.append(f"{key}: {scalar(value)}")
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


# Guarded, not unguarded: init_bundle.py imports this module and ARCHITECTURE.md
# lists it among the scripts that run on a bare Python. Emitting needs no YAML;
# only reading does, so the absence is reported by read() rather than by an
# ImportError at somebody else's import time.
try:
    import yaml
except ImportError:                                  # pragma: no cover
    yaml = None


SPLIT = re.compile(r"^---\n(.*?\n)---\n", re.S)


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
        block = "\n".join(self.lines if lines is None else lines)
        out = f"---\n{block}\n---\n{self.gap}{self.body}"
        return out if self.newline == "\n" else out.replace("\n", self.newline)


def read(path):
    """Parse one concept file, or refuse with a reason naming it.

    `newline=""` rather than text mode: universal newlines would hand back "\\n"
    for a CRLF file, and writing that out again would change every line ending in
    somebody's concept in order to rewrite one key. A bundle scaffolded on
    Windows is entirely CRLF, so this is the common case, not the exotic one.

    Known limit: CRLF wins if it appears at all, so a file mixing the two - a
    CRLF block over an LF body, which is what two tools disagreeing leaves
    behind - is rewritten wholly in CRLF. Every option rewrites something in a
    file that is already inconsistent, and this one at least leaves it
    consistent afterwards. Recorded as a decision, not an oversight.
    """
    if yaml is None:
        raise Unsplicable("reading a concept needs pyyaml, which is not installed\n"
                          "fix:  pip install pyyaml")
    with open(str(path), encoding="utf-8", newline="") as handle:
        raw = handle.read()
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
        raise Unsplicable(f"{path}: frontmatter is not a mapping\n"
                          f"fix:  a concept's block is `key: value` lines")
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
    node = yaml.compose(block, Loader=yaml.SafeLoader)
    if node is None:
        return {}
    if not isinstance(node, yaml.MappingNode):
        raise Unsplicable(f"{path}: frontmatter is not a mapping\n"
                          f"fix:  a concept's block is `key: value` lines")
    out = {}
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode):
            raise Unsplicable(
                f"{path}: a key here is written in explicit `? key` form\n"
                f"fix:  write it as `key: value` - this command places a value "
                f"beside a key it can name, and cannot name that one")
        out.setdefault(key_node.value, []).append((key_node, value_node))
    return out


def has_anchor(block):
    """An anchor or alias anywhere in the block.

    Splicing either end breaks the other - replacing `a: &x 1` leaves `b: *x`
    pointing at nothing, which is a file pyyaml will not read - and a bundle has
    no use for them, so the whole block is refused rather than the one key.
    """
    for event in yaml.parse(block, Loader=yaml.SafeLoader):
        if getattr(event, "anchor", None):
            return True
    return False


def locate(doc, key):
    """Where `key`'s value sits: (line, first column, column after it). Or None.

    Columns rather than a line index, so a splice can keep the key exactly as
    written and keep whatever follows the value - a trailing comment is the
    author's, and rewriting the whole line threw it away.
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
    key_node, value_node = found[0]
    kline = key_node.start_mark.line
    start, end = value_node.start_mark, value_node.end_mark
    if start.line == end.line and start.column == end.column:
        # An implicit null - `title:` with nothing after it. There is no value
        # text to replace, so the cut is the empty span just past the colon and
        # the tail is kept. Tested as zero width rather than as an empty
        # `value`, because `title: ""` is also an empty value and does have
        # text: cutting nothing there would have written `title: New""`.
        colon = doc.lines[kline].find(":", key_node.end_mark.column - 1)
        return kline, colon + 1, colon + 1
    if start.line != kline:
        raise Unsplicable(
            f"{doc.path}: `{key}` is written as a block, over several lines\n"
            f"fix:  this command writes flow style - [a, b] - and rewriting the "
            f"block would reflow lines nobody asked it to touch. Change it by hand.")
    # A value ending at a newline reports end_mark on the next line at column 0,
    # and nothing on that line belongs to it. Anything else on a later line is a
    # continuation, and cutting the first line of one orphans the rest.
    if end.line > kline and not (end.line == kline + 1 and end.column == 0):
        raise Unsplicable(
            f"{doc.path}: `{key}`'s value does not end on the line it starts on\n"
            f"fix:  this command writes flow style - [a, b] - on one line, and "
            f"replacing only the first line of a wrapped value would leave the "
            f"rest of it behind. Change it by hand.")
    cut_end = end.column if end.line == kline else len(doc.lines[kline])
    return kline, start.column, cut_end


def set_key(doc, key, value):
    """The file's text with `key` set, and every other byte where it was."""
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
        lines.insert(at, f"{key}: {rendered}")
        return doc.text(lines)
    index, cut_start, cut_end = location
    line = lines[index]
    if cut_start == cut_end:
        rendered = " " + rendered      # an implicit null: nothing to replace
    lines[index] = line[:cut_start] + rendered + line[cut_end:]
    return doc.text(lines)
