"""The shapes of what an agent sends the MCP tools in a batch, so the JSON schema each tool
publishes names the fields (Ruling 18 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: batches are JSON arrays,
and nothing an agent sends needs shell quoting).

TypedDicts, not models: the use cases read a row as a dict or an object
(application/posting/native.field), so what the SDK validates is handed on as it came.
They come from typing_extensions, which pydantic requires below Python 3.12 and which the
`mcp` extra always brings. Field names are the use cases' own; a schema with a field the
use case ignores would be a promise the tool does not keep.

The results are not typed here: a tool returns a dict, which arrives as JSON text (P0
results, item 6), and a typed result would add an output schema to every definition the
session carries (tests/test_budget.py caps them).
"""
from typing_extensions import NotRequired, TypedDict


class Header(TypedDict, total=False):
    """A posting's header fields for posting_decide, any of them: `domain` is `c:` ids of
    Domains, `seniority` a level, `captured` the day the advert was saved."""

    company: str
    title: str
    url: str
    seniority: str
    domain: list[str]
    captured: str


class Requirement(TypedDict):
    """One requirement row for posting_decide: the advert line it answers (`n`, as app_show
    lines numbers it), its slug, the term as the line writes it, its concepts (`c:` ids) and
    its necessity - required or preferred, by default what the line says."""

    n: int
    slug: str
    asked: str
    concepts: NotRequired[list[str]]
    need: NotRequired[str]


class Drop(TypedDict):
    """An advert line left out of the requirements, and why."""

    n: int
    reason: str


class Verdict(TypedDict):
    """A requirement's verdict in the review: `keep` for a flag that stands, a verdict no
    higher than the match's, or empty to clear the row; a lowered one needs its reason."""

    slug: str
    verdict: str
    reason: NotRequired[str]


class Ask(TypedDict):
    """A question for the person, replacing the match's. `about` names the requirement's
    slug; the review graph does not keep it yet, and the tool says so when it is given."""

    question: str
    about: NotRequired[str]
