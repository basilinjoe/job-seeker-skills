"""decisions.txt - the analyst's choices about an advert, which `jsk posting build` turns into
posting graph. The model writes only this; code writes the triples.

    company: JumpCloud
    title: Staff Software Engineer, PAM / PWM - India
    url: https://jobs.ashbyhq.com/jumpcloud/...
    seniority: architecture-ownership
    domain: c:identity-security
    captured: 2026-09-26

    # n | slug | asked | concepts | need
    17 | csharp | C# | c:csharp | required
    17 | grpc | gRPC | - |
    18 | pam_tools | CyberArk, BeyondTrust, Vault | c:cyberark, c:beyondtrust |
    12 | - | internal tooling - Origin CI, Kargo, WoK

`n` is the line number `jsk posting extract` printed. A requirement row has four or five
fields; `need` may be left off or blank to take the default for the line's section. A drop
has three: the line number, `-`, and the reason, which reaches the person in the assessment. The
header is `key: value` lines before the first row; `#` starts a comment line.

Fields are split on `|`, not whitespace: an `asked` is often several words.
"""
import re
from dataclasses import dataclass, field

from .. import ontology as O

HEADER_KEYS = ("company", "title", "url", "seniority", "domain", "captured")
NEEDS = ("required", "preferred", "implicit")
ROW = re.compile(r"\s*\d+\s*\|")


class DecisionsError(ValueError):
    """A line of decisions.txt that cannot be read: the message names it."""


@dataclass(frozen=True)
class Row:
    line: int               # the line of decisions.txt, for messages
    n: int                  # the advert line, as extract numbered it
    slug: str               # req_<posting stem>_<slug>
    asked: str
    concepts: tuple         # curies as written: ("c:csharp",), or ()
    need: str | None = None  # required | preferred | implicit, or None for the default


@dataclass(frozen=True)
class Drop:
    """An advert line decisions.txt leaves out, with the reason the assessment gives."""

    line: int
    n: int
    reason: str


@dataclass
class Decisions:
    """decisions.txt as read: its header, its requirement rows and its drops."""

    header: dict = field(default_factory=dict)
    rows: list = field(default_factory=list)
    drops: list = field(default_factory=list)


def parse(text):
    """Read decisions.txt's text into its header, requirement rows and drops.

    Args:
        text: the whole of decisions.txt, with either line ending.

    Returns:
        Decisions: the header as {key: value}, the Rows and the Drops in file order.

    Raises:
        DecisionsError: on the first line that cannot be read, naming it.
    """
    out = Decisions()
    for i, raw in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not ROW.match(line):
            key, sep, value = line.partition(":")
            key = key.strip().lower()
            if not sep or key not in HEADER_KEYS:
                raise DecisionsError(f"line {i}: {line!r} is neither a `key: value` header "
                                     f"({', '.join(HEADER_KEYS)}) nor a row starting with its "
                                     f"advert line number and `|`")
            if out.rows or out.drops:
                raise DecisionsError(f"line {i}: the header `{key}:` comes after the rows")
            if key in out.header:
                raise DecisionsError(f"line {i}: `{key}:` is given twice")
            out.header[key] = value.strip()
            continue
        cells = [c.strip() for c in line.split("|")]
        n = int(cells[0])
        if len(cells) > 3 and cells[1] == "-":
            raise DecisionsError(f"line {i}: a drop is `n | - | reason`, and this reason "
                                 f"holds a `|` - write it without one")
        if len(cells) == 3 and cells[1] == "-":
            if not cells[2]:
                raise DecisionsError(f"line {i}: a drop needs its reason")
            out.drops.append(Drop(i, n, cells[2]))
            continue
        if len(cells) not in (4, 5):
            raise DecisionsError(f"line {i}: a row is `n | slug | asked | concepts | need` "
                                 f"(need may be blank), a drop `n | - | reason`; this has "
                                 f"{len(cells)} fields")
        slug, asked, concepts = cells[1], cells[2], cells[3]
        need = (cells[4] if len(cells) == 5 else "") or None
        if not re.fullmatch(O.SLUG, slug):
            raise DecisionsError(f"line {i}: slug {slug!r} is not lowercase words joined by `_`")
        if not asked:
            raise DecisionsError(f"line {i}: `asked` is empty - the term as the advert writes it")
        if need is not None and need not in NEEDS:
            raise DecisionsError(f"line {i}: need {need!r} is not one of {', '.join(NEEDS)}")
        named = () if concepts in ("", "-") else tuple(c.strip() for c in concepts.split(","))
        for c in named:
            if not (c.startswith("c:") and O.CONCEPT_SLUG.fullmatch(c[2:])):
                raise DecisionsError(f"line {i}: {c!r} is not a concept - write it c:<slug>")
        out.rows.append(Row(i, n, slug, asked, named, need))
    return out
