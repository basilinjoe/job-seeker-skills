"""The terms gate over one render: the posting's words, looked for on the page.

The rules are domain/gates/terms_rules.py's. This reads the render's plain text - the
stream every variant shares, emitted in memory from the resume.json's plan, or a .txt passed
by hand - and asks for the posting the resume.json answers: the application directory it sits
in. A resume.json with no posting beside it, a general rebuild, has nothing to be covered
against, and the gate says so and passes. It prints nothing: adapters/cli/gates/terms.py does.

Every finding is a warning (terms_rules), so this gate never stops a ship.
"""
from dataclasses import dataclass

from ...domain.gates.terms_rules import judge
from .result import GateResult


@dataclass(frozen=True)
class TermsResult(GateResult):
    """The terms gate's verdict, with what its heading reports."""

    name: str
    posting: str | None     # the posting's title, or None when there is no posting
    counts: dict            # {necessity: (on the page, asked)}


def check_terms(text, name, record, *, terms):
    """The posting's words against a render's plain text.

    Args:
        text: the render's plain text (the plan's, emitted in memory, or a .txt's).
        name: what the heading calls it.
        record: the resume.json the render came from.
        terms: record -> (title, [(asked, necessity, other names)]) for the posting in the
            record's application directory, or None when it holds none
            (compose.gates.posting_terms).

    Returns:
        A TermsResult.
    """
    found = terms(record)
    if found is None:
        return TermsResult(fails=(), warns=(), name=name, posting=None, counts={})
    title, requirements = found
    counts, report = judge(text, title, requirements)
    return TermsResult(fails=tuple(report.fails), warns=tuple(report.warns), name=name,
                       posting=title, counts=counts)
