"""Reading career/kb.ttl for a resume: the subjects, their values, and the employers a
set of roles comes to.

These lived in graph/export.py while the resume was a URS record copied out of the
career; the builder reads the same graph the same way, so they moved here rather than
being written twice.
"""
from dataclasses import dataclass, field

from ..graph import ontology as O
from ..graph.writer import Subjects

CONTACTS = ("email", "phone", "linkedin", "github", "website")


def local(iri):
    return iri[len(O.K):]


def enum(value):
    return value[len(O.J):] if value and value.startswith(O.J) else value


def number(term):
    text = term.value
    if term.datatype.value == O.XSD + "integer":
        return int(text)
    n = float(text)
    return int(n) if n.is_integer() else n


def instant(value):
    if not value:
        return None
    precision = {4: "year", 7: "month", 10: "day"}.get(len(value), "day")
    return {"value": value, "precision": precision}


def period(start, end, state):
    """A span as the date formatters take it."""
    out = {}
    if start:
        out["start"] = instant(start)
    if end:
        out["end"] = instant(end)
    out["state"] = state
    return out


class Career:
    def __init__(self, triples):
        self.sub = Subjects(triples)

    def live(self, name):
        """Subjects of a class, retired ones left out."""
        return [s for s in self.sub.of(name) if not self.sub.get(s, "retired")]

    def get(self, s, pred, default=None):
        return self.sub.get(s, pred, default)

    def all(self, s, pred):
        return self.sub.props.get(s, {}).get(pred, [])

    def status(self, s):
        """Its provenance as a word - confirmed, inferred, ..."""
        return enum(self.get(s, "provenance")) or "confirmed"

    def role_period(self, r):
        return period(self.get(r, "start"), self.get(r, "end"), enum(self.get(r, "state")))


@dataclass
class Employer:
    """One employer and kind of work, with the roles held there: what a resume shows as
    one block. kb.ttl has no engagement - a role names its organisation and its kind -
    so this is where the block comes from."""
    org: str
    kind: str
    roles: list = field(default_factory=list)      # iris, latest first
    span: dict = field(default_factory=dict)       # a `period`


def employers(career, roles):
    """[Employer] for the organisations `roles` were held at: every live role there, one
    block per kind of work - a promotion history is never cut in half - latest first."""
    orgs = {career.get(r, "organisation") for r in roles}
    groups = {}
    for r in career.live("Position"):
        if career.get(r, "organisation") in orgs:
            kind = enum(career.get(r, "engagementKind")) or "employment"
            groups.setdefault((career.get(r, "organisation"), kind), []).append(r)
    # By start date, newest first - the resolver's order, kept: sorting ongoing-first
    # moved an open-source project begun Feb 2026 from the top of the ElevenLabs
    # experience section to its foot, below roles begun years earlier.
    def started(p):
        return (p.get("start") or {}).get("value", "0000")

    out = []
    for (org, kind), rs in groups.items():
        rs.sort(key=lambda r: started(career.role_period(r)), reverse=True)
        periods = [career.role_period(r) for r in rs]
        ongoing = any(p["state"] == "ongoing" for p in periods)
        ends = [p["end"]["value"] for p in periods if "end" in p]
        known = all(p["state"] != "unknown" for p in periods)
        starts = [p["start"]["value"] for p in periods if "start" in p]
        state = "ongoing" if ongoing else ("ended" if known and ends else "unknown")
        span = period(min(starts) if starts else None,
                      max(ends) if state == "ended" else None, state)
        out.append(Employer(org, kind, rs, span))
    out.sort(key=lambda e: started(e.span), reverse=True)
    return out
