"""The terms gate over one render: the posting's words, looked for on the page.

The rules are domain/gates/terms_rules.py's. This reads the .txt render - the plain
stream every variant shares, and the text a paste-in box receives - and asks for the
posting the resume.json answers: the application directory it sits in. A resume.json
with no posting beside it, a general rebuild, has nothing to be covered against, and the
gate says so and passes. It prints nothing: adapters/cli/gates/terms.py does.

Every finding is a warning (terms_rules), so this gate never stops a ship.
"""
import os
from dataclasses import dataclass

from ...domain.gates.terms_rules import judge
from .result import GateResult, unreadable


@dataclass(frozen=True)
class TermsResult(GateResult):
    """The terms gate's verdict, with what its heading reports."""

    name: str
    posting: str | None     # the posting's title, or None when there is no posting
    counts: dict            # {necessity: (on the page, asked)}


def check_terms(path, record, *, read_txt, terms):
    """The posting's words against the render at `path`.

    Args:
        path: the .txt render; it exists.
        record: the resume.json the render came from.
        read_txt: path -> (text, fonts); raises OSError when the file will not read.
        terms: record -> (title, [(asked, necessity, other names)]) for the posting in the
            record's application directory, or None when it holds none
            (compose.gates.posting_terms).

    Returns:
        A TermsResult, or an Unreadable when the render would not open.
    """
    name = os.path.basename(path)
    try:
        text, _ = read_txt(path)
    except OSError as e:
        return unreadable(name, f"unreadable: {e}")
    found = terms(record)
    if found is None:
        return TermsResult(fails=(), warns=(), name=name, posting=None, counts={})
    title, requirements = found
    counts, report = judge(text, title, requirements)
    return TermsResult(fails=tuple(report.fails), warns=tuple(report.warns), name=name,
                          posting=title, counts=counts)
