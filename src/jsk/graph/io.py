"""Reading a record file: its triples, where each subject is, and what a rewrite would lose.

pyoxigraph is imported inside the functions that need it, never at module top, so a
command that never reads the graph never pays for it (11-12 ms, measured in P0).
"""
import hashlib
import re
from dataclasses import dataclass

from .ontology import C, K, kind_of

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


@dataclass
class Parsed:
    file: str          # as reported: relative to the workspace root, forward slashes
    kind: str
    quads: list        # pyoxigraph Quads, all in the default graph
    lines: dict        # subject iri -> the first line it starts, 1-based
    comments: list     # (line, text): hand comments a rewrite would drop
    sha256: str = ""   # of the normalised text: what log.ttl records for kb.ttl
    text: str = ""     # the normalised text, for the canonical check and the diff


def normalise(text):
    """LF only, no BOM: what the writer writes, so what the reader compares against."""
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


class Unreadable(Exception):
    """A text file jsk could not read, with the fix. `Missing` and `NotUtf8` say which."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


class Missing(Unreadable):
    """No file there - the one failure a caller may treat as "nothing written yet"."""


class NotUtf8(Unreadable):
    """Bytes that are not UTF-8: a Windows editor's cp1252, most often."""


def read_text(path, what=None):
    """A text file a person or an agent wrote, as the writer would write it: UTF-8, no BOM,
    LF only. `what` names it in the message; the path does when it is not given. Every
    authored file is read here, so a BOM, a CRLF or a cp1252 save is handled once -
    tests/test_plugin_surface.py fails on a text read anywhere else."""
    name = what or str(path)
    try:
        with open(path, encoding="utf-8") as fh:
            return normalise(fh.read())
    except FileNotFoundError:
        raise Missing(f"no {name} at {path}", f"write {name} first") from None
    except UnicodeDecodeError as e:
        raise NotUtf8(f"{name}: not UTF-8 ({e.reason} at byte {e.start})",
                      "save the file as UTF-8") from None
    except OSError as e:
        raise Unreadable(f"{name}: {e.strerror or e}", "check the path and its permissions") \
            from None


def parse_text(text, file, kind=None):
    """Parse one file's text. Raises GraphError on a syntax error."""
    import pyoxigraph as ox

    kind = kind or kind_of(file)
    text = normalise(text)
    fmt = ox.RdfFormat.TRIG if kind == "changeset" else ox.RdfFormat.TURTLE
    try:
        # A set, as RDF means it: the parser keeps a line copied twice as two quads, which
        # would read as two values and write back as `"A", "A"`.
        quads = list(dict.fromkeys(ox.parse(text.encode("utf-8"), format=fmt)))
    except SyntaxError as e:
        raise GraphError(f"{file}:{e.lineno}:{e.offset}: {e.msg}",
                         "fix the syntax there; the rest of the file was not read",
                         file, e.lineno, e.offset) from None
    return Parsed(file, kind, quads, subject_lines(text), comments(text), sha256(text), text)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse(path, root=None):
    """Parse a file on disk; `root` makes the reported name relative to the workspace."""
    from .store import rel

    file = rel(path, root) if root else str(path).replace("\\", "/")
    try:
        text = read_text(path, file)
    except NotUtf8 as e:
        raise GraphError(str(e), e.fix, file) from None
    return parse_text(text, file)


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
