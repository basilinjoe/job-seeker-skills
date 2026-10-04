"""`jsk kb check`: the verb that validates the record and says where it stands.

It parses its arguments, runs its use case (application/record/check.py) with the real record
bound in, and prints what it returns. 6.0 retired `show`, `view`, `query`, `log` and `path`
with it (docs/superpowers/plans/2026-10-04-retire-duplicated-cli.md): the career_show,
career_view, career_query and career_log tools read the record, and `jsk doctor` names the
workspace.
"""
from ..presenters import usage


def cmd_check(args, flags, root, today):
    """jsk kb check [--only <path>]

    Validates the whole workspace - every rule, every graph - and says where the career
    and its log stand. Exit 1 on any FAIL; a WARN is printed and passes.

    It also asks the record gate's number check of every live bullet: a bullet it
    refuses fails every resume that selects it, so it is warned of here, once, rather
    than found by each resume run.

    --only <graph or path>  the findings in that graph or under that application (`kb`,
                    `applications/acme`, or the application's folder), plus every FAIL
                    anywhere, since a FAIL still stops the match. The JumpCloud run's
                    full check printed 40 KB of other applications' warnings to find its
                    own five.

    An application made from files and not sent is a WARN `file-made-unsent`: jsk 6.0 no
    longer finishes one, so it is sent with jsk 5.1.0, or dropped.
    """
    from ....application.record.check import check
    from ..cliutil import show
    from ..compose.record import load
    from ....application.timeline.unsent import warning as unsent_warning
    from ....infra import files
    from ....infra.oxigraph import record as R
    from ....infra.oxigraph.queries import OxigraphQueries

    if args:
        return usage("jsk kb check takes no arguments but --only <path>")
    checked = check(root, flags.get("--only"), load=load, state=R.state,
                    graph_name=files.graph_name, queries=OxigraphQueries,
                    listing=files.application_listing)
    rep, st = checked.report, checked.state
    for stem in checked.unsent:
        rep.warn(unsent_warning(stem))
    print(f"record   {st.kind}" + (f" at r{st.log_revision}" if st.log_revision else "")
          + (f" - {st.detail}" if st.detail else ""))
    print(f"{len(rep.fails)} FAIL, {len(rep.warns)} WARN")
    show(rep.fails, "FAIL", 0)
    show(rep.warns, "WARN", 0)
    return 1 if rep.fails else 0
