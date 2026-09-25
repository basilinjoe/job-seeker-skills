"""Numbers in prose, and whether the career holds them.

`numerals`, `covered` and `SCALE` lived in validate_urs.py and moved here unchanged when
the record gate became one check over the short resume.json (2026-09-25): check_prose
borrows the detector, and the number check below is its other caller.
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


def untraced(store, bullets, today=None):
    """[Fault] for the `bullets` (iris, in order) whose words state a number no current
    version of a metric they cite holds. A number only a closed version holds is
    superseded: the career did say it, and says when it stopped. An iri the store holds
    no text for is skipped - short.ids names it.

    This is claims.py's check 3 over the graph, and validate_urs's numeral check with it:
    one function the record gate, `jsk kb check` and `jsk match` all call, so the three
    stopped disagreeing about a number. They used to export a URS record and read these
    back out of gate lines with regexes (match.py's RECORD_GATE/UNTRACED/SUPERSEDED).

    claims.py let a confirmed bullet's own words trace a number, because it compared a
    copy with the career. The words here are the career's own, so that exemption would
    pass every confirmed bullet; the record gate refused those in any record selecting
    them (the ElevenLabs run's six, "a 300-400 candidate drive" citing nothing), and this
    does too. `today` is taken so every caller passes one clock; a version is current
    while it has no j:validUntil, as metric-open requires exactly one to be."""
    from ..graph.queries import PRE

    want = list(dict.fromkeys(bullets))
    text, cites = {}, {}
    for r in store.select(PRE + """SELECT ?a ?t ?m WHERE { ?a a j:Achievement ; j:text ?t
                                    OPTIONAL { ?a j:cites ?m } }"""):
        text[r["a"].value] = r["t"].value
        if "m" in r:
            cites.setdefault(r["a"].value, set()).add(r["m"].value)
    versions = {}                    # metric -> [(version, {numbers}, closed day or None)]
    for r in store.select(PRE + """SELECT ?m ?v ?val ?base ?upper ?until WHERE {
            ?v j:of ?m ; j:value ?val OPTIONAL { ?v j:baseline ?base }
            OPTIONAL { ?v j:upper ?upper } OPTIONAL { ?v j:validUntil ?until } }"""):
        # Either end of a range is the career's number: "15-20" states both.
        nums = {float(r[k].value) for k in ("val", "base", "upper") if k in r}
        versions.setdefault(r["m"].value, []).append(
            (r["v"].value, nums, r["until"].value if "until" in r else None))
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
