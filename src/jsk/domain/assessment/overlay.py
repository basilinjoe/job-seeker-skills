"""gaps.txt - the analyst's overlay on the assessment the match already derived. The model
writes only this; code folds it in, writes the assessment's graph and prints the assessment.

    fit: partial
    eligibility: India-based, authorised to work there; the role is India remote
    # names Pinecone, Weaviate, Milvus; the evidence never does
    vector_dbs | unevidenced | pgvector only - none of the three products
    mentoring | partial | mentors juniors, not seniors
    short: vector databases | the products the advert names
    ask: Have you used Pinecone or Weaviate, even in a spike?

A keyed line is `fit`, `eligibility`, `short`, `surplus` or `ask`, then `:`. `fit` and
`eligibility` appear at most once; the others repeat, in file order. Every other line is a
row, `slug | verdict | reason`, split on its first two `|` so the reason may hold one. Rows
pair with requirements by slug, never by text. `#` starts a comment line.

Only what can be refused from the text alone is refused here. Whether a verdict lowers the
match, or `keep` sits on a flagged row, needs the match, and gapsbuild checks it.
"""
import re
from dataclasses import dataclass, field

from .. import ontology as O

KEYED = re.compile(r"(fit|eligibility|short|surplus|ask):[ \t]*(.*)")
ONCE = ("fit", "eligibility")
MARK = "<!-- jsk:"          # an unfilled slot: accepted here, FAILed by gapsbuild


class AssessmentError(ValueError):
    """A line of gaps.txt that cannot be read: the message names it."""


@dataclass(frozen=True)
class Row:
    line: int               # the line of gaps.txt, for messages
    slug: str               # req_<posting stem>_<slug>
    verdict: str            # keep, or a verdict name
    reason: str = ""        # becomes j:shortfall; "" when absent


@dataclass
class Overlay:
    """gaps.txt as read: the keyed lines and the rows, each in file order."""

    fit: str | None = None
    eligibility: str | None = None
    rows: list = field(default_factory=list)
    short: list = field(default_factory=list)
    surplus: list = field(default_factory=list)
    ask: list = field(default_factory=list)


def parse(text):
    """Read gaps.txt's text into the analyst's overlay on the assessment.

    Args:
        text: the whole of gaps.txt, with either line ending.

    Returns:
        Overlay: fit and eligibility, the rows, and the short, surplus and ask lines in
        file order.

    Raises:
        AssessmentError: on the first line that cannot be read, naming it.
    """
    out, seen, keyed = Overlay(), {}, {}
    verdicts = ("keep", *O.ENUMS["verdict"])
    for i, raw in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = KEYED.fullmatch(line)
        if m:
            key, value = m[1], m[2].strip()
            if key in ONCE:
                if key in keyed:
                    raise AssessmentError(f"line {i}: `{key}:` is given twice, first on line "
                                          f"{keyed[key]}")
                keyed[key] = i
                if not value:
                    continue
                if key == "fit" and MARK not in value and value not in O.ENUMS["fit"]:
                    raise AssessmentError(f"line {i}: fit {value!r} is not one of "
                                          f"{', '.join(O.ENUMS['fit'])}")
                setattr(out, key, value)
            elif value:
                getattr(out, key).append(value)
            continue
        cells = [c.strip() for c in line.split("|", 2)]
        if len(cells) < 2:
            raise AssessmentError(f"line {i}: {line!r} is neither a `key: value` line "
                                  f"(fit, eligibility, short, surplus, ask) nor a row "
                                  f"`slug | verdict | reason`")
        slug, verdict = cells[0], cells[1]
        reason = cells[2] if len(cells) == 3 else ""
        if not re.fullmatch(O.SLUG, slug):
            raise AssessmentError(f"line {i}: slug {slug!r} is not lowercase words joined by "
                                  f"`_` - the requirement's, as in decisions.txt")
        if slug in seen:
            raise AssessmentError(f"line {i}: `{slug}` already has a row on line {seen[slug]}")
        if MARK not in verdict and verdict not in verdicts:
            raise AssessmentError(f"line {i}: verdict {verdict!r} is not one of "
                                  f"{', '.join(verdicts)}")
        seen[slug] = i
        out.rows.append(Row(i, slug, verdict, reason))
    return out
