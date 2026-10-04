"""The tailoring use cases' ports, bound: the short resume.json's form and the derived
assessment, with the region profiles and the engine's queries.

Each binding is built inside the call that needs it (Ruling 6 of the onion design): nothing
here reads the record or the disk at import. The folder `jsk tailor match` and `jsk tailor
prepare` read gaps.txt, decisions.txt and posting.md through went with those verbs in 6.0
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2): a graph-native
application's review and lines are in the store.
"""


def short_file(store, selection=None, select=None, notes=None):
    """The short resume.json for a selection (application.tailor.export.short_file), the
    region profiles that ship read from data/.

    Args:
        store: a loaded workspace.
        selection: the Selection for a posting or by rank, or None.
        select: the ids --select named, or None.
        notes: a list the NOTE lines are appended to, or None.

    Returns:
        The short file as a dict.

    Raises:
        ExportError: a `select` it cannot honour, or a selection holding no bullet.
    """
    from ...application.tailor.export import short_file as formed
    from ...infra.profiles import ships

    return formed(store, selection, select, notes, ships=ships)


def derive(r, store, today=None):
    """The Derived assessment for the match result `r` over `store`
    (domain.assessment.derive.derive over the engine's queries), with the career's
    absences: a confirmed "no" still standing on `today` answers what it denies (Ruling 9
    of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md).

    Args:
        r: match.result's plain data for one posting.
        store: the loaded workspace the match ran on.
        today: the day an absence's lapse is measured against; None takes no absence.

    Returns:
        domain.assessment.derive.derive's Derived. Reads the confirmed bullets' words.
    """
    from ...application.tailor.check_gaps import question_line
    from ...domain.assessment.derive import derive as derived
    from ...domain.record.absence import of_triples
    from ...domain.record.state import KB
    from ...infra.oxigraph.queries import OxigraphQueries

    absences = of_triples(store.graph(KB)) if today is not None and KB in store.parsed else []
    queries = OxigraphQueries(store)
    return derived(r, queries, question_line, absences=absences, today=today,
                   counts_as=queries.counts_as)
