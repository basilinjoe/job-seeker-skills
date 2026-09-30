"""jsk tailor prepare - everything an assessment reads, in one call.

Usage: jsk tailor prepare <applications/<dir>> [--draft-gaps] [--cover N] [--today YYYY-MM-DD]

  --draft-gaps  also draft <dir>/gaps.txt, the analyst's overlay: a `<!-- jsk: -->` slot
                wherever judgement is needed (never over one there)
  --cover N     the most projects the cover may use (default 3)
  --today       the date recency is measured from (default: today)

One process, one digest, in this order: the check, scoped to this application plus any
FAIL anywhere; the match as `jsk match` prints it; what the record holds for every missing
and candidate term; the person, for eligibility; the cover's projects with their bullets;
what those projects hold unconfirmed; and the assessment - the gaps graph and gaps.md,
derived from the match with gaps.txt folded in when there is one, written on every run.
Every section has a size cap and says when it was cut.

Exit 0 digest printed; 1 a FAIL blocks the match, or the draft could not be written; 2
called wrong. A gaps.txt the check refuses is reported in the digest, not an exit 1: the
analyst may be halfway through filling it.

Written after the JumpCloud run (2026-09-26), where the analyst made about ten calls
between the posting and gaps.md - fmt, check, match, evidence, person, show, show,
unconfirmed - and each was a model turn carrying long silent reasoning (53s, 128s). The
tools took two seconds apiece; the turns took four minutes.
"""
import datetime
import os
import sys

from ..cliutil import docstring_usage, wants_help

USAGE = ("usage: jsk tailor prepare <applications/<dir>> [--draft-gaps] [--cover N] "
         "[--today YYYY-MM-DD]")
PROJECTS = 3        # the cover's projects whose bullets are printed
CAP = {"check": 30, "match": 200, "evidence": 40, "person": 20, "bullets": 120,
       "unconfirmed": 30}


def capped(lines, what):
    """At most CAP[what] lines, then how many were cut: a cut section says so."""
    cap = CAP[what]
    if len(lines) <= cap:
        return lines
    return lines[:cap] + [f"… {len(lines) - cap} more cut"]


def section(title, lines):
    print(f"\n== {title}\n")
    for line in lines:
        print(line)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv):
        print(docstring_usage(__doc__))
        return 0
    draft = "--draft-gaps" in argv
    argv = [a for a in argv if a != "--draft-gaps"]
    options = {}
    for flag in ("--cover", "--today"):
        if flag in argv:
            at = argv.index(flag)
            if at + 1 >= len(argv):
                print(f"{flag} needs a value")
                return 2
            options[flag] = argv[at + 1]
            del argv[at:at + 2]
    if len(argv) != 2 or argv[0] != "prepare":
        print(USAGE)
        return 2
    from .match import COVER, application
    try:
        budget = int(options.get("--cover", COVER))
        today = (datetime.date.fromisoformat(options["--today"]) if "--today" in options
                 else datetime.date.today())
    except ValueError:
        print("--cover takes a whole number and --today a YYYY-MM-DD date")
        return 2
    if budget < 1:
        print("--cover takes a whole number of at least 1")
        return 2
    root, app = application(argv[1], "jsk tailor prepare")
    if root is None:
        print("\n".join(app))
        return 2
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk tailor needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from . import record as R

    # It writes the assessment, so it takes its turn before it reads the record.
    with R.turn(root):
        return prepare(root, app, argv[1], budget, today, draft)


def prepare(root, app, named_as, budget, today, draft):
    from . import named
    from . import ontology as O
    from . import store as S
    from .writer import entry_text, with_children
    from .match import blocks, markdown, posting_in, result
    from .shapes import curie

    store = S.load(root)
    rel = S.file_name(app, store.root)
    here = rel + "/"

    # 1. The check, scoped: this application's findings and every FAIL, since a FAIL
    # anywhere may still stop the match.
    mine = [f for f in store.findings if f.severity == "FAIL" or f.file.startswith(here)]
    rep = S.Store(store.root, findings=mine).report()
    lines = [f"FAIL  {x}" for x in rep.fails] + [f"WARN  {x}" for x in rep.warns]
    section(f"check - {here.rstrip('/')}, and any FAIL anywhere: "
            f"{len(rep.fails)} FAIL, {len(rep.warns)} WARN", capped(lines, "check"))
    blocking = [f for f in store.fails() if blocks(f, here)]
    if blocking:
        print(f"\nFAIL  {len(blocking)} of them stop the match - fix them, then run this again")
        return 1

    post = posting_in(store, app)
    if post is None:
        print(f"\n{rel}: holds no posting\n"
              f"      fix: `jsk posting build {named_as}` writes it from posting.md")
        return 1

    # 2. The match, as `jsk match` prints it.
    r = result(store, post, today, budget, len(store.fails()) - len(blocking))
    section("match", capped(markdown(r).rstrip("\n").split("\n"), "match"))

    # 3. What the record holds for each term the match could not place.
    terms = [q["asked"] for q in r["requirements"] if q["state"] in ("missing", "candidate")]
    if terms:
        cols, rows = named.evidence_for(store, *terms)
        lines = named.table(cols, rows).split("\n")
        section("evidence - the missing and candidate terms",
                lines[:2] + capped(lines[2:], "evidence"))
    else:
        section("evidence - the missing and candidate terms", ["None: nothing is missing."])

    # 4. The person, for eligibility.
    cols, rows = named.person(store)
    lines = named.table(cols, rows).split("\n")
    section("person", lines[:2] + capped(lines[2:], "person"))

    # 5. The cover's projects, bullets only - what citing them as evidence needs.
    projects = list(r["cover"]["projects"] or [])[:PROJECTS]
    if not projects:
        projects = [row["project"] for row in r["ranking"]
                    if row["required"] or row["preferred"]][:PROJECTS]
    lines, held = [], set()
    for project in projects:
        iri = O.K + project.split(":", 1)[1]
        home = store.file_of(iri)
        if not home:
            continue
        quads = store.graph(home)
        project_name = next((q.object.value for q in quads if q.subject.value == iri
                             and q.predicate.value == O.J + "name"), "")
        bullets = with_children(quads, iri)[1:]
        held |= {project} | {curie(b) for b in bullets}
        lines.append(f"# {project} - {project_name}")
        for b in bullets:
            lines += entry_text(quads, b).split("\n")
        lines.append("")
    section(f"bullets - {', '.join(projects) or 'no project carries a requirement'}",
            capped(lines, "bullets"))

    # 6. What those projects hold unconfirmed: the questions a draft would otherwise raise.
    cols, rows = named.unconfirmed(store)
    rows = [row for row in rows if row["entry"] in held]
    lines = named.table(cols, rows).split("\n") if rows else ["None."]
    section("unconfirmed - in those projects", lines[:2] + capped(lines[2:], "unconfirmed")
            if rows else lines)

    # 7. The assessment, derived - with gaps.txt folded in when there is one - and the draft
    # of gaps.txt when asked for.
    from .gapsbuild import build
    from .gapsderive import derive

    derived = derive(r, store)
    target = os.path.join(app, "gaps.txt")
    written, found = build(app, store, r, today, derived)
    lines = [f"{s}  {t}\n      fix: {f}" for s, t, f in found]
    if written:
        from .gapsbuild import shown

        counts = {}
        for row in derived.rows:
            counts[row.matched or "implicit"] = counts.get(row.matched or "implicit", 0) + 1
        lines.append("wrote " + " and ".join(shown(w) for w in written)
                     + f" - fit {derived.fit} by default; "
                     + ", ".join(f"{n} {v}" for v, n in counts.items()))
    lines += [f"flagged {row.slug}: {row.flag_text}" for row in derived.rows if row.flags]
    if draft:
        from .gapsdraft import MARK, draft_gaps
        from .io import GraphError, Unreadable
        from .timeline import sent_day

        try:
            held = sent_day(app, store) and "the application is sent, and its assessment with it"
        except GraphError as e:         # an application record that says neither way
            held = f"{e}\n      fix: {e.fix}"
        if held:
            lines.append(f"no gaps.txt drafted: {held}")
        elif os.path.exists(target):
            lines.append(f"{target} already exists - left as it is; `jsk match {rel} "
                         f"--gaps {target}` checks it and rewrites the assessment and gaps.md")
        else:
            try:
                text = draft_gaps(derived, store, os.path.join(app, "posting.md"))
            except Unreadable as e:       # build() FAILed on the same file above
                lines.append(f"no gaps.txt drafted: {e}\n      fix: {e.fix}")
            else:
                with open(target, "x", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                slots = sum(MARK in line for line in text.split("\n"))
                lines.append(f"wrote {target}: {slots} slots to fill")
    section("gaps", lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
