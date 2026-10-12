"""The career_check tool: every rule over the whole workspace, the career's hash against its log,
the record gate's number check asked of every live bullet, and the applications made from
files that are not sent.

That last is not a rule in domain/record/rules.py: the rules see the store, and an
application made from files may have nothing in it but a folder holding a resume.json
(application/timeline/unsent.py). Ruling 5 of
docs/superpowers/plans/2026-10-03-retire-file-pipeline.md has career_check name each one; the
adapter words them, with the CLI's version in the fix.
"""
import os
from dataclasses import dataclass

from ...domain.gates.report import Report
from ...domain.record.state import KB, LOG, State, unrecorded
from ...domain.record.store import Store


def untraced_lines(store, queries, bullets=None):
    """numbers.untraced over `bullets`, a line each: what the record gate would refuse in
    any resume selecting the bullet. Export asks it of the bullets it chose - on the
    Everforth run the author found four of these one gate at a time, three changesets deep.

    This exported the whole career as a URS record and ran the record and claims gates
    on it (export.gate_failures); the number check is now one function over the graph,
    so it is asked of the bullets directly. The wording is the old record gate's - it is
    what the Everforth and ElevenLabs runs taught people to read here.

    Args:
        store: the loaded workspace.
        queries: its ports.queries.RecordQueries.
        bullets: achievement iris; every live bullet when None.

    Returns:
        The lines, in the bullets' order.
    """
    from ...domain.gates.numbers import quoted
    from ...domain.record.career import Career
    from ...domain.record.shapes import curie
    from ..gates.numbers import untraced

    career = Career(store.graph(KB))
    out = []
    chosen = sorted(career.live("Achievement")) if bullets is None else bullets
    for f in untraced(queries, chosen):
        if f.numbers:
            one = len(f.numbers) == 1
            out.append(f"{curie(f.bullet)} - {quoted(f.numbers)} "
                       f"{'appears' if one else 'appear'} "
                       "in the text but in no metric it cites ("
                       + (", ".join(curie(m) for m in f.cites) or "it cites none") + ")")
        for s in f.superseded:
            out.append(f"{curie(f.bullet)} - '{s['number']}' is {curie(s['version'])}'s number, "
                       f"replaced on {s['until']}")
    return out


@dataclass(frozen=True)
class Checked:
    """What the career_check tool found: the findings as a Report, and where the record stands."""

    report: Report
    state: State
    unsent: tuple = ()          # stems of the applications made from files and not sent


def check(root, only, *, load, state, graph_name, queries, listing=None):
    """Validate the workspace and say where the career and its log stand.

    Args:
        root: the workspace.
        only: a graph name or a path to narrow the findings to (every FAIL stays), or None.
        load: loads the workspace (compose.record.load).
        state: where the career and its log stand (infra.oxigraph.record.state).
        graph_name: the graph a path holds (infra.files.graph_name).
        queries: makes the RecordQueries over a loaded workspace.
        listing: root -> {stem: the names in applications/<stem>/}
            (infra.files.application_listing); None leaves `unsent` empty.

    Returns:
        Checked. Reads the record, and hashes the career once.
    """
    store = load(root)
    if only is not None:
        here = os.path.abspath(only)
        only = (graph_name(here, store.root) if os.path.exists(here)
                else only.replace("\\", "/")).rstrip("/")

    def within(name):
        return only is None or name == only or name.startswith(only + "/")

    rep = Store(store.root, findings=[f for f in store.findings
                                      if f.severity == "FAIL" or within(f.file)]).report()
    if not rep.fails and KB in store.parsed and within(KB):
        for line in untraced_lines(store, queries(store)):
            rep.warn(f"a record selecting it fails a gate: {line}\n        fix: record the "
                     "number as a metric version and cite it (j:cites), or correct the words, "
                     "with the career_apply tool (jsk mcp) - every application selecting it pays this otherwise")
    st = state(store)
    # The one check of the career's hash: only jsk writes the store, and every write it
    # makes to the career logs the hash - so a mismatch is a write from outside. It costs a
    # full write of the career, so check asks it and a plain load does not.
    if st.kind == "clean" and unrecorded(store.graph(KB), store.graph(LOG)):
        rep.fail(f"kb - the career is not what its log last recorded - written outside jsk "
                 f"(r{st.log_revision})\n        fix: restore it from .jsk/backup.trig "
                 "(`jsk kb load .jsk/backup.trig` into a new workspace, --root), or `jsk kb "
                 "dump` to see what it holds")
    unsent = ()
    if listing is not None:
        from ..timeline.unsent import file_made_unsent

        unsent = tuple(stem for stem in file_made_unsent(
            {n: p.quads for n, p in store.parsed.items()}, listing(store.root))
            if within(f"applications/{stem}"))
    return Checked(rep, st, unsent)
