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


def untraced(queries, bullets, today=None):
    """[Fault] for the `bullets` whose words state a number the career's metrics do not hold.

    Args:
        queries: a RecordQueries over a loaded workspace.
        bullets: achievement iris, in order.
        today: accepted so every caller passes one clock; a version's currency is whether
            it has a j:validUntil, not a date.

    Returns:
        domain.gates.numbers.trace over the career's metric facts. Reads them once.
    """
    return trace(facts(queries), bullets)


def facts(queries):
    """(text, cites, versions): each bullet's words, the metrics it cites, and each
    metric's versions as (version, {numbers}, closed day or None). One read of the career,
    shared by `untraced` and the letter check, so both trace a number the same way.

    Args:
        queries: a RecordQueries over a loaded workspace.

    Returns:
        queries.metric_facts(), unchanged.
    """
    return queries.metric_facts()
