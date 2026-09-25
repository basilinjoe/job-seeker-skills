"""The numbers `jsk match` ranks by and `jsk kb query experience` adds up.

They lived in kbindex.py, the Markdown reader, because `jsk index` computed them first.
The graph kept using them after `jsk index` was retired, which left the career's ranking
importing a module that release N+1 deletes with `jsk migrate`. They are here now, and
kbindex imports them from here for as long as it exists.

Standard library only, like ontology.py: importing this must not import pyoxigraph.
"""
import re

from . import ontology as O

# Most senior first. The order is the ranking: a project at or above the posting's
# level earns the seniority point, so a lower index is more senior.
SENIORITY = O.ENUMS["seniority"]

# What one requirement a project carries is worth, by the posting's necessity.
WEIGHTS = {"required": 3, "preferred": 1, "implicit": 0}


def recency_points(year, today):
    """1 within three years of `today`, 0.5 at four to six, nothing after that."""
    age = today.year - year
    return 1.0 if age <= 3 else 0.5 if age <= 6 else 0.0


def month(value, where, end=False):
    """`YYYY-MM` (or `YYYY`) as a month count; an end of `YYYY` is its December.

    A value that is not a date raises ValueError naming `where`, so the caller can say
    which entry holds it.
    """
    match = re.match(r"^(\d{4})(?:-(\d{2}))?", str(value or ""))
    if not match:
        raise ValueError(f"{where}: {value!r} is not a YYYY-MM date")
    return int(match.group(1)) * 12 + int(match.group(2) or (12 if end else 1)) - 1


def experience(roles, today):
    """(months, notes): the months covered by the union of every role's dates, overlaps
    counted once, and a note for each role that could not be counted.

    Each role is `{"block": {"id", "start", "end", "state"}, "start": line}` - the shape
    the Markdown reader hands over, which the graph builds to match. Only `ongoing`
    runs to `today`: a role of `unknown` state with no end date is not counted, because
    running it to today would inflate the one number an eligibility gate compares.
    """
    spans, notes = [], []
    now = today.year * 12 + today.month - 1
    for r in roles:
        b, where = r["block"], f"{r['block']['id']} (line {r['start']})"
        if not b.get("start"):
            notes.append(f"{b['id']} has no start date and is not counted")
            continue
        first = month(b["start"], where)
        if b.get("end"):
            last = month(b["end"], where, end=True)
        elif b.get("state") == "ongoing":
            last = now
        else:
            notes.append(f"{b['id']} has no end date and state {b.get('state')!r}, "
                         f"so it is not counted")
            continue
        spans.append((first, last))
    covered, cursor = 0, None
    for first, last in sorted(spans):
        if cursor is not None and first <= cursor:
            if last > cursor:
                covered += last - cursor
                cursor = last
            continue
        covered += last - first + 1
        cursor = last
    return covered, notes
