"""`jsk tailor prepare`'s digest: everything an assessment reads, gathered in one pass.

The check, scoped to this application plus any FAIL anywhere; the match as `jsk tailor match`
prints it; what the record holds for every missing and candidate term; the person, for
eligibility; the cover's projects with their bullets; what those projects hold
unconfirmed; and the assessment - the gaps graph - written on every run and printed (there
is no gaps.md), with gaps.txt drafted when asked for. Every section has a size cap and says
when it was cut.
It prints nothing: adapters/cli/tailor.py prints the sections in order.
"""
import os
from dataclasses import dataclass

PROJECTS = 3        # the cover's projects whose bullets are printed
CAP = {"check": 30, "match": 200, "evidence": 40, "person": 20, "bullets": 120,
       "unconfirmed": 30, "assessment": 200}


@dataclass(frozen=True)
class Digest:
    """The digest: its sections in order, and why it stopped when it did."""

    sections: tuple             # (title, lines), in the order they print
    stop: str | None            # printed after the sections when the digest stopped early
    code: int                   # the exit code


def capped(lines, what):
    """At most CAP[what] lines, then how many were cut: a cut section says so.

    Args:
        lines: the section's lines.
        what: the section's key in CAP.

    Returns:
        The lines, cut to the cap with a last line saying how many more there were.
    """
    cap = CAP[what]
    if len(lines) <= cap:
        return lines
    return lines[:cap] + [f"… {len(lines) - cap} more cut"]


def prepare(root, app, named_as, budget, today, draft, *, load, queries, select, name_of,
            reads, folder):
    """The digest for the application `app`, and its assessment written.

    Args:
        root: the workspace root; the caller holds its turn.
        app: the application's absolute directory.
        named_as: the application as the caller named it, for the fix.
        budget: the most projects the cover may use.
        today: the date recency is measured from, and the assessment dated.
        draft: also draft gaps.txt when there is none.
        load: root -> the loaded, validated workspace.
        queries: store -> its feature reads (ports.queries.RecordQueries).
        select: (store, post, today, budget) -> the posting's Selection.
        name_of: (path, root) -> the path as findings name it.
        reads: the named reads the digest shows (compose.tailor.Reads).
        folder: the application's folder and record (compose.tailor.Folder).

    Returns:
        The Digest. Writes the gaps graph, and gaps.txt when drafted.
    """
    from ...domain.matching.report import blocks
    from ...domain.record.store import Store
    from .match_posting import posting_in, result
    from .match_text import markdown

    store = load(root)
    rel = name_of(app, store.root)
    here = rel + "/"
    sections = []

    # 1. The check, scoped: this application's findings and every FAIL, since a FAIL
    # anywhere may still stop the match.
    mine = [f for f in store.findings if f.severity == "FAIL" or f.file.startswith(here)]
    rep = Store(store.root, findings=mine).report()
    lines = [f"FAIL  {x}" for x in rep.fails] + [f"WARN  {x}" for x in rep.warns]
    sections.append((f"check - {here.rstrip('/')}, and any FAIL anywhere: "
                     f"{len(rep.fails)} FAIL, {len(rep.warns)} WARN", capped(lines, "check")))
    blocking = [f for f in store.fails() if blocks(f, here)]
    if blocking:
        return Digest(tuple(sections), f"\nFAIL  {len(blocking)} of them stop the match - fix "
                      f"them, then run this again", 1)

    post = posting_in(store, rel)
    if post is None:
        return Digest(tuple(sections), f"\n{rel}: holds no posting\n"
                      f"      fix: `jsk posting build {named_as}` writes it from posting.md", 1)

    # 2. The match, as `jsk tailor match` prints it.
    r = result(store, queries(store), post, today, budget, len(store.fails()) - len(blocking),
               select)
    sections.append(("match", capped(markdown(r).rstrip("\n").split("\n"), "match")))
    sections += evidence_sections(store, r, reads)
    projects, lines, held = bullet_lines(store, r)
    sections.append((f"bullets - {', '.join(projects) or 'no project carries a requirement'}",
                     capped(lines, "bullets")))
    sections.append(unconfirmed_section(store, held, reads))
    lines, assessment = gaps_lines(store, r, app, rel, today, draft, folder)
    sections.append(("gaps", lines))
    if assessment:
        # Printed, never written: no gaps.md (Ruling 24 of the graph-native plan).
        sections.append(("assessment", capped(assessment.rstrip("\n").split("\n"),
                                              "assessment")))
    return Digest(tuple(sections), None, 0)


def evidence_sections(store, r, reads):
    """3 and 4: what the record holds for each term the match could not place, and the
    person, for eligibility.

    Args:
        store: the loaded workspace.
        r: the match's plain data.
        reads: the named reads (compose.tailor.Reads).

    Returns:
        The two (title, lines) sections.
    """
    terms = [q["asked"] for q in r["requirements"] if q["state"] in ("missing", "candidate")]
    if terms:
        cols, rows = reads.evidence_for(store, *terms)
        lines = reads.table(cols, rows).split("\n")
        evidence = ("evidence - the missing and candidate terms",
                    lines[:2] + capped(lines[2:], "evidence"))
    else:
        evidence = ("evidence - the missing and candidate terms", ["None: nothing is missing."])
    cols, rows = reads.person(store)
    lines = reads.table(cols, rows).split("\n")
    return [evidence, ("person", lines[:2] + capped(lines[2:], "person"))]


def bullet_lines(store, r):
    """5: the cover's projects, bullets only - what citing them as evidence needs.

    Args:
        store: the loaded workspace.
        r: the match's plain data.

    Returns:
        (the projects shown, the section's lines, the curies of those projects and their
        bullets).
    """
    from ...domain import ontology as O
    from ...domain.record.shapes import curie
    from ...domain.record.writer import entry_text, with_children

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
    return projects, lines, held


def unconfirmed_section(store, held, reads):
    """6: what those projects hold unconfirmed - the questions a draft would otherwise raise.

    Args:
        store: the loaded workspace.
        held: the curies of the projects shown and their bullets.
        reads: the named reads (compose.tailor.Reads).

    Returns:
        The (title, lines) section.
    """
    cols, rows = reads.unconfirmed(store)
    rows = [row for row in rows if row["entry"] in held]
    lines = reads.table(cols, rows).split("\n") if rows else ["None."]
    return ("unconfirmed - in those projects", lines[:2] + capped(lines[2:], "unconfirmed")
            if rows else lines)


def gaps_lines(store, r, app, rel, today, draft, folder):
    """7: the assessment, derived - with gaps.txt folded in when there is one - and the
    draft of gaps.txt when asked for.

    Args:
        store: the loaded workspace.
        r: the match's plain data.
        app: the application's directory.
        rel: the application's folder relative to the workspace.
        today: the day the assessment is dated.
        draft: also draft gaps.txt when there is none.
        folder: the application's folder and record (compose.tailor.Folder).

    Returns:
        (the gaps section's lines, the assessment rendered or None when none was written).
        Writes the assessment's graph, and gaps.txt when drafted.
    """
    from .check_gaps import build, shown

    derived = folder.derive(r, store, today)
    target = os.path.join(app, "gaps.txt")
    written, found, assessment = build(app, store, r, today, derived, folder=folder)
    lines = [f"{s}  {t}\n      fix: {f}" for s, t, f in found]
    if written:
        counts = {}
        for row in derived.rows:
            counts[row.matched or "implicit"] = counts.get(row.matched or "implicit", 0) + 1
        lines.append("wrote " + " and ".join(shown(w) for w in written)
                     + f" - fit {derived.fit} by default; "
                     + ", ".join(f"{n} {v}" for v, n in counts.items()))
    lines += [f"flagged {row.slug}: {row.flag_text}" for row in derived.rows if row.flags]
    if draft:
        lines += drafted(store, derived, app, rel, target, folder)
    return lines, assessment


def drafted(store, derived, app, rel, target, folder):
    """--draft-gaps: gaps.txt drafted when the application is unsent and has none.

    Args:
        store: the loaded workspace.
        derived: the Derived assessment.
        app: the application's directory.
        rel: the application's folder relative to the workspace.
        target: the gaps.txt to write.
        folder: the application's folder and record (compose.tailor.Folder).

    Returns:
        The line saying what was drafted, or why not. Writes `target`.
    """
    from ...domain.assessment.draft import slot_count
    from ...domain.record.parsed import GraphError, Unreadable
    from .draft_gaps import draft_gaps

    try:
        held = folder.sent_day(app, store) and "the application is sent, and its assessment with it"
    except GraphError as e:         # an application record that says neither way
        held = f"{e}\n      fix: {e.fix}"
    if held:
        return [f"no gaps.txt drafted: {held}"]
    if os.path.exists(target):
        return [f"{target} already exists - left as it is; `jsk tailor match {rel} "
                f"--gaps {target}` checks it, rewrites the assessment and prints it"]
    try:
        text = draft_gaps(derived, store, os.path.join(app, "posting.md"), folder=folder)
    except Unreadable as e:       # build() FAILed on the same file above
        return [f"no gaps.txt drafted: {e}\n      fix: {e.fix}"]
    folder.create(target, text)
    return [f"wrote {target}: {slot_count(text)} slots to fill"]
