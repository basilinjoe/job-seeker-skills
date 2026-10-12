"""Numbers in prose, and whether a career's metrics hold them.

`numerals`, `covered` and `SCALE` lived in validate_urs.py and moved unchanged when the
record gate became one check over the short resume.json (2026-09-25): check_prose borrows
the detector, and `trace` is its other caller. Reading the career's metrics is the
application's half (application.gates.numbers); what is here only compares.
"""
import re
from dataclasses import dataclass

SCALE = {"k": 1e3, "m": 1e6, "bn": 1e9, "b": 1e9}


NUMBER = re.compile(r"(?<![A-Za-z0-9.])(\d[\d,]*(?:\.\d+)?)\s*(bn|[kmb%])?(?![A-Za-z0-9])")
ACRONYM = re.compile(r"([A-Z]{2,})\s*$")


def numerals(text):
    """Standalone quantities in prose, with their multiplier suffix if any.

    Three classes of number are designators rather than claims, and counting
    them would make this check useless through noise:

      * glued to letters - p95, S3, H100, IPv6
      * a four-digit year
      * preceded by an all-caps acronym - ISO 27001, SOC 2, IEC 62304, RFC 7231

    The acronym rule costs a real detection: 'reduced MTTR 40' is skipped. That
    trade is deliberate, because this check *fails* a document. A missed number
    is a gap in coverage; a false accusation makes the gate something people
    learn to route around. A percentage keeps its suffix and is always counted,
    which is how most such claims are actually written.
    """
    found = []
    for m in NUMBER.finditer(text):
        raw, suffix = m.group(1), (m.group(2) or "").lower()
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix in ("", "%") and 1900 <= value <= 2100 and value == int(value) and "." not in raw:
            continue                      # a year, not a claim
        if suffix != "%" and ACRONYM.search(text[:m.start()]):
            continue                      # a standard's number, not a quantity
        found.append((value, suffix, m.group(0).strip()))
    return found


def covered(value, suffix, pool):
    candidates = {value}
    if suffix in SCALE:
        candidates.add(value * SCALE[suffix])
    for c in candidates:
        for p in pool:
            if abs(p - c) < 1e-9 or (c and abs(p - c) / max(abs(c), 1e-9) < 0.005):
                return True
            if p and abs(p * 60 - c) < 1e-9:          # minutes stated as seconds
                return True
            if c and abs(c * 60 - p) < 1e-9:
                return True
    return False


def quoted(numbers):
    """'300' and '400', as a finding says them."""
    shown = [f"'{n}'" for n in numbers]
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


@dataclass(frozen=True)
class Fault:
    """One bullet's numbers the career cannot back. `numbers` are the numerals as the
    bullet writes them, untraced; `superseded` each {number, version, until} a closed
    version holds; `cites` the metrics it cites. Iris throughout."""
    bullet: str
    numbers: list
    superseded: list
    cites: list


def trace(facts, bullets):
    """The bullets whose words state a number no current version of a metric they cite holds.

    A number only a closed version holds is superseded: the career did say it, and says
    when it stopped. A version is current while it has no j:validUntil, as metric-open
    requires exactly one to be. An iri with no text in `facts` is skipped - short.ids
    names it.

    Args:
        facts: (text, cites, versions) as application.gates.numbers.facts reads them.
        bullets: achievement iris, in order; a repeat is checked once.

    Returns:
        [Fault], one per bullet with an untraced or superseded number, in `bullets` order.
    """
    want = list(dict.fromkeys(bullets))
    text, cites, versions = facts
    out = []
    for b in want:
        if b not in text:
            continue
        cited = sorted(cites.get(b, ()))
        mine = [v for m in cited for v in versions.get(m, [])]
        now = set().union(*(nums for _, nums, until in mine if until is None))
        found, old = [], []
        for value, suffix, shown in numerals(text[b]):
            if covered(value, suffix, now):
                continue
            closed = sorted((until, v) for v, nums, until in mine
                            if until is not None and covered(value, suffix, nums))
            if closed:
                until, v = closed[-1]
                if shown not in [o["number"] for o in old]:
                    old.append({"number": shown, "version": v, "until": until})
            elif shown not in found:
                found.append(shown)
        if found or old:
            out.append(Fault(b, found, old, cited))
    return out
