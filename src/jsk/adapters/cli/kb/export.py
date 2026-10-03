"""`jsk kb export`: its flags, the bullets chosen (application/tailor/export.py), what the
choice left out and the checks it fails said, and the short resume.json printed.

`--out` wrote the file until 6.0, which reads no resume.json path any more
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2): it exits 2 naming
`resume_select`, which stores a target's selection in the graph, and so does `--replace`."""
import os
import sys

from ....application.guards import resume_json_refusal
from ..presenters import refuse, show_findings, unclean, usage


def cmd_export(args, flags, root, today):
    """jsk kb export [--select <id>...] [--from-match <app-dir> [--cover N] | --ranked]
                     [--today YYYY-MM-DD]

    The short resume.json an application starts from: the bullets it shows, in order,
    and its settings - `"resume": 2`, the region when a profile ships for the person's
    country, `"pages": 2`. Nothing the career holds is copied: the render reads the
    words, numbers and dates from the career as it stands, so a changeset applied or a
    bullet confirmed afterwards is in the next ship with nothing to update.

    --select names what to show: prj_ brings a project and its bullets, ach_ one bullet
    (and narrows its project to the bullets named), pos_ a role shown with no bullet.
    Retired entries never come. With none of --select, --from-match or --ranked, the
    whole career.

    --from-match chooses the bullets from `jsk tailor match` of the application (its directory,
    applications/<dir>): the projects that carry the posting with confirmed evidence,
    their bullets by what they show, the skills the posting asks for first - each skills
    row cut to the most a row renders, and a NOTE naming what each cut left out. What it
    cannot close prints as GAP lines - tag-only, unconfirmed, uncovered, unresolved - for
    the assessment. --select adds to it; --cover and --today are jsk tailor match's. It also sets
    `headline` to the posting's title, inferred until `jsk kb confirm --headline`, and
    `names` for a skill the posting asks for by one of its aliases - each said in a NOTE.

    --ranked is the same with no posting, for a general rebuild: the projects by strength
    and recency, their confirmed bullets by the same bands, a bullet citing a current
    number first. The scorer chooses rather than the model, as it does for a posting.
    --select adds to it.

    The file is printed: no command reads a resume.json path since 6.0. --out and
    --replace, which wrote it, exit 2 naming the resume_select tool (jsk mcp), which keeps
    a target's selection in the graph.

    A number in a chosen bullet that no current metric version holds is printed as a
    WARN: it is in the career, not in anything authored, so it is a question for the
    person before any word is retuned.

    --urs and --refresh are gone with the full record: the short file is the one format,
    and there is nothing in it to refresh.
    """
    options = export_options(args, flags, today)
    if isinstance(options, int):
        return options
    select, today, budget = options
    return exported(root, flags, select, today, budget)


def export_options(args, flags, today):
    """Check export's flags and read --cover and --today as the tailoring commands do.

    Args:
        args: the arguments left after the flags.
        flags: the parsed flags.
        today: the day the command read, used when --today is not given.

    Returns:
        (the --select ids or None, the day, the cover budget), or the exit code of a call
        made wrongly, its usage printed.
    """
    from ..options import BadOption, tailor_options

    # Said by name rather than as an unknown flag - so they are switches it takes: an
    # agent file or a shell history written before the short file still has them.
    if "--urs" in flags:
        return usage("--urs is gone: export writes the short resume.json, the one format "
                     "there is - drop --urs")
    if "--refresh" in flags:
        return usage("--refresh is gone: a short resume.json holds ids, and every render "
                     "builds from the career as it stands, so there is nothing to refresh")
    for flag in ("--out", "--replace"):
        if flag in flags:
            print("\n".join(resume_json_refusal(
                f"jsk kb export {flag}", "the resume_select tool (jsk mcp) stores a target's "
                "selection - mode from_match or ranked; `jsk kb export` without it prints the "
                "short file")))
            return 2
    posting, cover_text, today_text = (flags.get(f) for f in
                                       ("--from-match", "--cover", "--today"))
    by_rank = "--ranked" in flags
    select = None
    if "--select" in flags:
        select = [i for token in flags["--select"] for i in token.split(",") if i]
        if not select:
            return usage("--select needs one or more ids")
    if args:
        return usage("jsk kb export [--select <id>...] [--from-match <app-dir> | --ranked] "
                     "- the short resume.json is the one format it prints")
    if posting and by_rank:
        return usage("--ranked is the selection with no posting, --from-match the one for a "
                     "posting - give one")
    if cover_text and not posting:
        return usage("--cover goes with --from-match")
    if today_text and not (posting or by_rank):
        return usage("--today goes with --from-match or --ranked")
    try:
        chosen = tailor_options(cover_text or None, today_text or None, lambda: today)
    except BadOption as e:
        return usage(str(e))
    return select, chosen.today, chosen.budget


def exported(root, flags, select, today, budget):
    """Choose the bullets and print the short file. Returns the exit code."""
    import json

    from ....application.record.refusals import Failing, Refused, Unclean
    from ....application.tailor import export as E
    from ....application.tailor.match_posting import application
    from ....domain.matching.report import blocks
    from ....infra import files, profiles
    from ....infra.oxigraph import record as R
    from ....infra.oxigraph.queries import OxigraphQueries
    from ..compose import match as selector
    from ..compose.match import posting_in
    from ..compose.record import load

    posting = flags.get("--from-match")
    app = None
    if posting:
        home, app = application(posting, "jsk kb export --from-match")
        if home is None:
            print("\n".join(app))
            return 2
        if os.path.normcase(os.path.realpath(home)) != os.path.normcase(os.path.realpath(root)):
            return usage(f"{posting}: not an application of this workspace ({root})")
    report = sys.stderr
    try:
        store = E.opened(root, app, posting, load=load, state=R.state,
                         file_name=files.file_name, blocks=blocks)
        chosen = E.selection(store, app, posting, select, "--ranked" in flags, today, budget,
                             selector=selector, posting_in=posting_in)
        if chosen is not None:
            # The gaps first: when nothing is selected they are the reason, and a refusal
            # printed without them would leave the author to run jsk tailor match to find out why.
            said(chosen, report)
        doc = E.short(store, chosen, select, today, ships=profiles.ships,
                      queries=OxigraphQueries(store),
                      post=posting_in(store, app) if posting else None)
    except Unclean as err:
        return unclean(err.state)
    except Failing as err:
        show_findings(err.findings, err.title)
        return 1
    except Refused as err:
        return refuse(err.lines, err.fix)
    for note in doc.notes:
        print(note, file=report)
    if doc.faults:
        print(f"WARN  {len(doc.faults)} check(s) fail on the chosen bullets as the career holds "
              "them - a question for the person, answered in the career (`jsk kb apply`) "
              "before any word is retuned:", file=report)
        for line in doc.faults:
            print(f"        {line}", file=report)
    sys.stdout.write(json.dumps(doc.doc, indent=2, ensure_ascii=False) + "\n")
    return 0


def said(chosen, report):
    """Print a selection's projects that come with no bullet, then its gaps, to `report`."""
    from ....domain.record.writer import curie

    for p in chosen.projects:
        if not chosen.bullets.get(p):
            print(f"NOTE  {curie(p)} has no confirmed bullet, so it comes with none - "
                  "name the bullet with --select, or confirm one", file=report)
    for gap in chosen.gaps:
        print(gap.line(), file=report)
