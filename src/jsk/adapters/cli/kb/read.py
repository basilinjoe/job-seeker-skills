"""`jsk kb show`, `view`, `query`, `check`, `path` and `log`: the verbs that read the record.

Each parses its arguments, runs its use case (application/record/read.py, check.py,
store_status.py) with the real record bound in, and prints what it returns.
"""
import os

from ..presenters import GUIDE, refuse, usage


def cmd_show(args, flags, root, today):
    """jsk kb show <id>... [--bullets]

    The entries as Turtle, each under the name of the graph that holds it (`kb`, the
    shipped `vocabulary`, an application's): a project with its bullets, a metric with its
    versions - the shape a changeset is drafted in. The first line is the revision to put
    in a changeset's op:base, so a change drafted from what was shown is checked against it.

    --bullets prints a project as its name and its bullets only - what citing it as
    evidence needs - without the problem, decisions and notes, which run to thousands of
    characters a project.
    """
    from ....application.record.read import show
    from ..compose.record import load
    from ....infra.oxigraph import record as R

    if not args:
        return usage("jsk kb show takes one or more ids")
    shown = show(root, args, "--bullets" in flags, load=load, state=R.state)
    revision = shown.log_revision
    print(f"# r{revision} - op:base {revision}" if revision else
          "# not logged yet - `jsk kb check` says why")
    code = 0
    for entry in shown.entries:
        if entry.missing:
            detail, fix = entry.missing
            print(f"\nREFUSED  {detail}\n        fix: {fix}")
            code = 1
            continue
        for name, heading, text in entry.graphs:
            print(f"\n# {name}")
            if heading:
                print(heading)
            print(text)
    return code


def cmd_view(args, flags, root, today):
    """jsk kb view [--section NAME]

    The whole career as Markdown, in the career's section order, to read end to end and
    correct - stdout only; it is never written to a file, so it cannot drift. Entries not
    confirmed, and retired ones, say so beside their names.
    """
    from ....application.record.read import view
    from ....application.record.refusals import Unclean
    from ..compose.record import load
    from ....infra.oxigraph import record as R

    if args:
        return usage("jsk kb view takes only --section NAME")
    try:
        text = view(root, flags.get("--section"), load=load, state=R.state)
    except Unclean as err:
        return refuse([GUIDE[err.state.kind][0]], GUIDE[err.state.kind][1])
    print(text, end="")
    return 0


def cmd_query(args, flags, root, today):
    """jsk kb query <name> [arguments] [--json]

      open                questions not yet answered, oldest first
      unconfirmed         live entries not confirmed, with the question open about each
      holds <concept>     projects holding a concept, or one that counts as it
      stale               applications that sent a metric version since replaced
      experience <concept>  months the roles behind the projects holding it cover
      pipeline            each application's stage: its latest event, and how long ago
      evidence <term>...  per term: projects holding its concept, then entries whose text
                          names it (whole words; an all-capitals term matches as written)
      person              location, work mode, rights to work, and the roles held now
      similar <words>...  the live projects closest to the words (a name, technologies,
                          a sentence), best five, each with the words and concepts shared
      duplicates          pairs of live projects that look like one project told twice
      concepts [--near <term>...]  the vocabulary; with --near, per term, only what it
                          names and the few concepts closest to it - one table each,
                          `== <term>` above it (quote a term of several words)
      bare                capabilities with no label and no isA/partOf, most-held first
      demand              each concept the postings ask for: postings, required, my verdicts
      shortfalls          concepts the assessments leave short, with any "no" standing
      drops               why advert lines were left out, by reason, with the postings
      outcomes            applications by assessed fit and the stage they reached
      repeated            concepts asked about in more than one application
      absences            each "no" the person gave: live, due to ask again, unconfirmed

    A table by default; --json for the same rows, structured.
    """
    import json

    from ....application.record.queries import QUERIES
    from ..compose.record import load
    from ....infra.oxigraph.queries import OxigraphQueries
    from ..presenters import table

    as_json, near = "--json" in flags, flags.get("--near")
    if not args or args[0] not in QUERIES:
        return usage(f"jsk kb query takes one of: {', '.join(QUERIES)}")
    name, rest = args[0], args[1:]
    want, _, fn, reads, dated = QUERIES[name]
    if want.endswith("...") and not rest or not want.endswith("...") and len(rest) != len(want.split()):
        return usage(f"jsk kb query {name} {want}".rstrip())
    if near is not None and name != "concepts":
        return usage("--near is for `jsk kb query concepts --near <term>...` only")
    if near is None:
        store = load(root)
        extra = {"queries": OxigraphQueries(store)} if reads else {}
        columns, rows = fn(store, *rest, **extra, **({"today": today} if dated else {}))
        print(json.dumps(rows, indent=2, ensure_ascii=False) if as_json else table(columns, rows))
        return 0
    if not near:
        return usage("jsk kb query concepts --near <term>... - one or more terms")
    # Several terms from one load: the analyst ran this 21 times in a shell loop, 15-25 s.
    store = load(root)
    found = {term: fn(store, near=term, queries=OxigraphQueries(store)) for term in near}
    if as_json:
        print(json.dumps({t: rows for t, (_, rows) in found.items()}, indent=2,
                         ensure_ascii=False))
    else:
        print("\n\n".join(f"== {t}\n{table(columns, rows)}" for t, (columns, rows) in found.items()))
    return 0


def cmd_check(args, flags, root, today):
    """jsk kb check [--only <path>]

    Validates the whole workspace - every rule, every graph - and says where the career
    and its log stand. Exit 1 on any FAIL; a WARN is printed and passes.

    It also asks the record gate's number check of every live bullet: a bullet it
    refuses fails every resume that selects it, so it is warned of here, once, rather
    than found by each resume run.

    --only <graph or path>  the findings in that graph or under that application (`kb`,
                    `applications/acme`, or the application's folder), plus every FAIL
                    anywhere, since a FAIL still stops `jsk tailor match`. The JumpCloud run's
                    full check printed 40 KB of other applications' warnings to find its
                    own five.

    An application made from files and not sent is a WARN `file-made-unsent`: jsk 6.0 no
    longer finishes one, so it is sent with this CLI first, or dropped.
    """
    from ....application.record.check import check
    from ..cliutil import show
    from ..compose.record import load
    from ..retiring import unsent_warning
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


def cmd_path(args, flags, root, today):
    """jsk kb path [--root DIR]

    Prints where the record is, as absolute paths: the workspace, career/store/ and
    applications/. Run it from anywhere inside the workspace - an application directory
    will do. The store is not a file to read: `jsk kb view`, `show` and `log` read it.

    The workspace is the folder holding career/. A workspace that is itself named
    `career` puts the store at career/career/store/, which is why the path is printed
    rather than worked out. Needs nothing but the folders; exit 1 when there is no
    career/store/ there.
    """
    from ....application.record.store_status import where
    from ....infra import legacy_import as legacy
    from ....infra.oxigraph import db

    if args:
        return usage("jsk kb path takes no arguments")
    found = where(root, db=db, legacy=legacy)
    if found.instead:
        print(f"no career/store/ under {root}")
        if found.instead == "files":
            print("        fix: this workspace is still laid out as .ttl files - "
                  "`jsk kb load .` moves the record into career/store/")
        elif found.instead == "career":
            print(f"        fix: that folder is career/ itself - the workspace is {os.path.dirname(root)}")
        return 1
    print(f"workspace     {found.workspace}")
    print(f"store         {found.store}")
    print(f"applications  {found.applications}")
    return 0


def cmd_log(args, flags, root, today):
    """jsk kb log [--last N]

    The record's history, newest first: each revision's date, what made it (apply, confirm,
    new, ...), its summary, and the ids it minted and touched. --last N, the newest N
    (default 10).
    """
    from ....application.record.read import log
    from ....application.record.refusals import Refused
    from ....domain.record.writer import curies
    from ..compose.record import load

    if args:
        return usage("jsk kb log takes no arguments - --last N")
    last = flags.get("--last", "10")
    if not last.isdigit() or int(last) < 1:
        return usage(f"--last {last}: a count, 1 or more")
    try:
        entries = log(root, int(last), load=load)
    except Refused as err:
        return refuse(err.lines, err.fix)
    for e in entries:
        print(f"r{e.revision}  {e.date}  {e.by:8} {e.summary}")
        for label, ids in (("minted", e.minted), ("touched", e.touched)):
            if ids:
                print(f"    {label:8} {curies(ids)}")
    return 0
