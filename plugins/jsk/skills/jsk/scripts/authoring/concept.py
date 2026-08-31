"""One concept file: emit a new one, or change one key of an existing one.

This module formats and does not judge. Whether a value is *allowed* is
schema.py's question; whether it needs quoting is this one's.

The emitter used to live in init_bundle.py. It moved here rather than being
copied, because the spec this implements forbids a second definition of the
format - and two emitters disagreeing about quoting is exactly how a bundle
acquires a file that reads differently from every other file in it.

This module emits LF. `okf_compile.read_frontmatter` handles CRLF, so CRLF
bundles exist in the wild; the caller owns the file's line convention.
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
