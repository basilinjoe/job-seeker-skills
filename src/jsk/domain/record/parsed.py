"""A Turtle or TriG text as parsed: its quads, where each subject starts, the comments
storing it would lose, and the normalised text they were read from."""
import hashlib
import re
from dataclasses import dataclass

from ..ontology import C, K

# A subject line starts in column 0 with a CURIE; a banner is `# == Section`.
SUBJECT = re.compile(r"^([kc]):([A-Za-z0-9_.\-]+)")
BANNER = re.compile(r"^# == \S.*$")


class GraphError(Exception):
    """A file that could not be read. Carries where, and the fix."""

    def __init__(self, message, fix, file, line=None, col=None):
        super().__init__(message)
        self.fix = fix
        self.file = file
        self.line = line
        self.col = col


class Unreadable(Exception):
    """A text file jsk could not read, with the fix. `Missing` and `NotUtf8` say which."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


class Missing(Unreadable):
    """No file there - the one failure a caller may treat as "nothing written yet"."""


class NotUtf8(Unreadable):
    """Bytes that are not UTF-8: a Windows editor's cp1252, most often."""


@dataclass
class Parsed:
    file: str          # as reported: the graph's name once loaded (`kb`), else the file's
    kind: str | None   # None: a name no record kind is named like, as kind_of reads it
    quads: list        # pyoxigraph Quads, all in the default graph
    lines: dict        # subject iri -> the first line it starts, 1-based; {} when stored
    comments: list     # (line, text): hand comments the store would not keep
    sha256: str = ""   # of the normalised text: what the import checks against the log
    text: str = ""     # the normalised text; "" for a graph out of the store


def normalise(text):
    """LF only, no BOM: what the writer writes, so what the reader compares against."""
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256(text):
    """The hex SHA-256 of `text` as UTF-8: what a log entry records of the career."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


NUMERIC = frozenset(f"http://www.w3.org/2001/XMLSchema#{t}" for t in (
    "integer", "decimal", "double", "float", "long", "int", "short", "byte",
    "nonNegativeInteger", "positiveInteger", "nonPositiveInteger", "negativeInteger",
    "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte"))


def subject_lines(text):
    """{iri: first line} for every subject that starts a line - where a finding points."""
    out = {}
    for n, line in enumerate(text.split("\n"), 1):
        m = SUBJECT.match(line)
        if m:
            local = m.group(2).rstrip(".")
            iri = (K if m.group(1) == "k" else C) + local
            out.setdefault(iri, n)
    return out


# The tokens a `#` can hide in, then a comment. Strings follow Turtle's grammar: a long
# string holds at most two quotes in a row; a short one never spans a line.
TOKENS = re.compile(
    r'"""(?:[^"\\]|\\.|"(?!""))*"""'
    r"|'''(?:[^'\\]|\\.|'(?!''))*'''"
    r'|"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
    r"|<[^>\s]*>"
    r"|(?P<comment>#[^\n]*)", re.S)


def comments(text):
    """(line, text) of every comment that is not a banner.

    Tokenised rather than searched, because `#` inside a string or an IRI is not a
    comment: "C# / .NET" is a skill name, and <https://x/#frag> is an IRI.
    """
    if "#" not in text:
        return []
    found = []
    line, pos = 1, 0
    for m in TOKENS.finditer(text):
        if m.group("comment") is None:
            continue
        line += text.count("\n", pos, m.start())
        pos = m.start()
        at_start = m.start() == 0 or text[m.start() - 1] == "\n"
        if not (at_start and BANNER.match(m.group("comment"))):
            found.append((line, m.group("comment")))
    return found
