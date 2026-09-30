"""The untraced-number check over a loaded career: its metrics read, then compared.

One function the record gate, `jsk kb check` and `jsk match` all call, so the three stopped
disagreeing about a number. They used to export a URS record and read these back out of
gate lines with regexes (match.py's RECORD_GATE/UNTRACED/SUPERSEDED).

claims.py let a confirmed bullet's own words trace a number, because it compared a copy
with the career. The words here are the career's own, so that exemption would pass every
confirmed bullet; the record gate refused those in any record selecting them (the
ElevenLabs run's six, "a 300-400 candidate drive" citing nothing), and this does too.
"""
from ...domain.gates.numbers import trace


def untraced(store, bullets, today=None):
    """[Fault] for the `bullets` whose words state a number the career's metrics do not hold.

    Args:
        store: a loaded workspace (store.load).
        bullets: achievement iris, in order.
        today: accepted so every caller passes one clock; a version's currency is whether
            it has a j:validUntil, not a date.

    Returns:
        domain.gates.numbers.trace over the store's metric facts. Runs two SELECTs.
    """
    return trace(facts(store), bullets)


def facts(store):
    """(text, cites, versions): each bullet's words, the metrics it cites, and each
    metric's versions as (version, {numbers}, closed day or None). One read of the store,
    shared by `untraced` and the letter check, so both trace a number the same way."""
    from ...graph.queries import PRE

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
    return text, cites, versions
