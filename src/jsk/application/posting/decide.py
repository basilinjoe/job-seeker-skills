"""`posting_decide` and `posting_complete`: a graph-native posting's requirements decided in
batches, then settled.

`jsk posting build` took the whole decisions.txt at once and refused it whole. A
graph-native posting is decided in batches (Ruling 18's `posting_decide`): rows upserted by
slug, drops on the stored lines, slugs removed - and every requirement, stored and new,
checked again by domain/posting/rows.py against the stored lines, so a batch is judged with
the rows already decided and the two paths cannot disagree on a row. A FAIL anywhere writes
nothing and the findings come back per row. Otherwise the posting graph is rewritten whole
in one update and stays a draft: a draft is allowed to be half-decided, so the tier-2 advert
rules wait (domain/record/advert_rules.py). `complete` is where they run: every
qualification line that is not eligibility used or dropped (build's coverage check), then
the whole workspace validated with the posting as it would be, then `j:state complete`.

A re-decide puts a completed posting back to draft. It drops the assessment, which was
derived from the requirements it changes - `assessment_derive` writes it again - and keeps
the review (Ruling 4), less any row about a requirement it removes, which would dangle.

The FAILs `decide` can return: a line that is not the advert's; an `asked` its line does
not say; a slug not lowercase words, or used twice; two requirements asking one term; a
necessity that is none; a concept the workspace does not know, or retired; a domain that is
not a Domain; a header field that is not one; a line both dropped and quoted; a drop with
no reason; a slug to remove that is not there. Its WARNs: a responsibility made required
that its line does not call required; more requirements than the soft cap. `complete` adds
the coverage FAIL and whatever the workspace's rules find in the posting. Each use case
refuses (raises Refused) an application made from files, one with no posting, and a frozen
one, sent or held back. Nothing here prints.
"""
import datetime
import re
from dataclasses import dataclass

from ...domain import ontology as O
from . import native as N


@dataclass(frozen=True)
class Decided:
    """What one decide or complete did."""

    target: str | None          # the posting graph's name; None when nothing was written
    requirements: int           # the requirements the posting holds after it
    state: str                  # the posting's state after it
    findings: tuple             # (severity, text, fix), every row's
    written: tuple              # the graph names written


def decide(root, stem, header=None, rows=(), drops=(), remove=(), *, today, ports):
    """Merge a batch of decisions into `applications/<stem>`'s posting, checked whole. The
    caller holds the workspace's turn.

    Args:
        root: the workspace root.
        stem: the application's name.
        header: {company, title, url, seniority, domain, captured}, any of them, or None.
            `domain` is a list of `c:` curies (or one comma-separated string).
        rows: requirements, each {n, slug, asked, concepts, need} as a dict or an object;
            `concepts` `c:` curies (or bare ids), `need` optional. A slug already stored is
            replaced whole.
        drops: lines left out, each {n, reason}.
        remove: slugs of stored requirements to delete.
        today: unused by the rows; kept so every use case is called alike.
        ports: the bound ports (compose.native.Ports).

    Returns:
        The Decided; with a FAIL among its findings nothing was written.

    Raises:
        Refused: a legacy application, no posting, or a frozen one.
    """
    from ...domain.posting.decide import SOFT_CAP

    app = N.app_of(root, stem)
    store = N.loaded(app, ports)
    s = N.native(store, app, ports)
    N.refuse_if_frozen(app, store, ports)
    queries = ports.queries(store)
    known = queries.concepts() - queries.retired_concepts()
    retired, domains = queries.retired_concepts(), queries.domains()
    found = list(headed(s, header or {}, known, retired, domains))
    gone = set()
    for slug in remove or ():
        if slug in s.reqs:
            gone.add(slug)
        else:
            # A FAIL, not a WARN: a mistyped slug otherwise wrote the posting back as a
            # draft with nothing removed, and a completed posting lost its state for a typo
            # (the end-to-end replay, 2026-10-02).
            found.append(("FAIL", f"remove: no requirement {slug!r} to remove",
                          "fix:  the slug as app_show requirements names it"))
    kept = {slug: row for slug, row in s.reqs.items() if slug not in gone}
    batch, new_drops = [], {}
    for i, row in enumerate(rows or (), 1):
        parsed = parse_row(i, row, s, known, retired, found)
        if parsed:
            batch.append(parsed)
    for i, d in enumerate(drops or (), 1):
        n, reason = N.field(d, "n"), str(N.field(d, "reason") or "").strip()
        if not reason:
            found.append(("FAIL", f"drops[{i}]: line {n} is dropped with no reason",
                          "fix:  say why it is left out - eligibility, a benefit, a duplicate"))
        new_drops[i] = (n, reason)
    found += checked(s, kept, batch, new_drops)
    merged = {slug: row for slug, row in kept.items()
              if slug not in {slug for _, slug, _ in batch}}
    for _, slug, row in batch:
        merged[slug] = row
    if len(merged) > SOFT_CAP:
        found.append(("WARN", f"{len(merged)} requirements, past the soft cap of {SOFT_CAP}: "
                      "one per term the match can score", None))
    if N.fails(found):
        return Decided(None, len(s.reqs), s.state or "draft", N.clean(found), ())
    used = {row[4] for row in merged.values()}
    dropped = {n: why for n, why in s.drops.items() if n not in used}
    dropped.update({n: why for n, why in new_drops.values()})
    s.reqs, s.drops = merged, dropped
    graphs: dict = {"posting": N.triples(app, s, "draft")}
    if app.graph("gaps") in store.parsed:
        graphs["gaps"] = None
    pruned = pruned_review(store, app, set(merged))
    if pruned is not None:
        graphs["review"] = pruned
    names, broken = N.write(app, store, graphs, ports)
    if broken:
        return Decided(None, len(merged), s.state or "draft", N.clean(found + broken), ())
    return Decided(names[0], len(merged), "draft", N.clean(found), tuple(names))


def complete(root, stem, *, today, ports):
    """Settle `applications/<stem>`'s posting: every qualification line answered, the
    workspace's rules clean on it, then `j:state complete`. The caller holds the turn.

    Args:
        root: the workspace root.
        stem: the application's name.
        today: unused; kept so every use case is called alike.
        ports: the bound ports (compose.native.Ports).

    Returns:
        The Decided; with a FAIL among its findings nothing was written.

    Raises:
        Refused: a legacy application, no posting, or a frozen one.
    """
    from ...domain.posting.rows import coverage, uncovered

    app = N.app_of(root, stem)
    store = N.loaded(app, ports)
    s = N.native(store, app, ports)
    N.refuse_if_frozen(app, store, ports)
    used = {row[4] for row in s.reqs.values()} | set(s.drops)
    missing = uncovered({x.n: x for x in s.lines}, used)
    if missing:
        found = [coverage(missing, app.graph("posting"),
                          "fix:  a requirement for what it asks, or a drop with its reason "
                          f"(posting_decide on {app.stem})")]
        return Decided(None, len(s.reqs), s.state or "draft", N.clean(found), ())
    names, broken = N.write(app, store, {"posting": N.triples(app, s, "complete")}, ports)
    if broken:
        return Decided(None, len(s.reqs), s.state or "draft", N.clean(broken), ())
    return Decided(names[0], len(s.reqs), "complete", (), tuple(names))


def near(term):
    """The fix for a concept that is not one: how to find the nearest."""
    return (f"fix:  `career_query` concepts --near \"{term}\" names the nearest; or leave "
            "the concepts out and let the match report the term")


def concept_iri(curie, where, known, retired, found, domains=None):
    """The iri of the concept `curie` (`c:x` or bare `x`), or None and a FAIL in `found`.

    Args:
        curie: the concept as written.
        where: where it was written, for the message.
        known: the live concepts.
        retired: the retired ones.
        found: the findings, appended to.
        domains: the Domains, when it must be one; else None.
    """
    bare = str(curie).strip().removeprefix("c:")
    iri = O.C + bare
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", bare):
        found.append(("FAIL", f"{where}: {curie!r} is not a concept id", near(bare)))
        return None
    if iri not in known:
        why = "is retired" if iri in retired else "is not a concept of this workspace"
        found.append(("FAIL", f"{where}: c:{bare} {why}", near(bare)))
        return None
    if domains is not None and iri not in domains:
        found.append(("FAIL", f"{where}: c:{bare} is not a Domain",
                      "fix:  name a domain, or none"))
        return None
    return iri


def headed(s, header, known, retired, domains):
    """The header's findings, its fields applied to the Stored `s` when there are none.

    Args:
        s: the Stored posting, changed in place.
        header: the fields given.
        known, retired, domains: the concepts it may name.

    Returns:
        [(severity, text, fix)].
    """
    found = []
    for key in header:
        if key not in ("company", "title", "url", "seniority", "domain", "captured"):
            found.append(("FAIL", f"header: {key!r} is not a header field",
                          "fix:  company, title, url, seniority, domain or captured"))
    for key in ("company", "title", "url"):
        if key in header:
            value = str(header[key] or "").strip()
            if key != "url" and not value:
                found.append(("FAIL", f"header: {key} is empty",
                              f"fix:  give the {key} as the advert states it"))
            s.head[key] = value
    if "seniority" in header:
        level = str(header["seniority"] or "").removeprefix("j:")
        if level and level not in O.ENUMS["seniority"]:
            found.append(("FAIL", f"header: seniority {level!r} is not a level",
                          f"fix:  one of {', '.join(O.ENUMS['seniority'])}, or none"))
        s.seniority = level
    if "domain" in header:
        given = header["domain"] or []
        if isinstance(given, str):
            given = [c for c in given.split(",") if c.strip() not in ("", "-")]
        s.domains = [iri for c in given
                     if (iri := concept_iri(c, "header: domain", known, retired, found,
                                            domains))]
    if "captured" in header:
        try:
            s.captured = datetime.date.fromisoformat(str(header["captured"])).isoformat()
        except ValueError:
            found.append(("FAIL", f"header: captured {header['captured']!r} is not a day",
                          "fix:  YYYY-MM-DD"))
    return found


def parse_row(i, row, s, known, retired, found):
    """(label, slug, (asked, need, iris, quote, n)) for the batch's row `i`, or None when it
    cannot be placed; its field FAILs appended to `found`.

    Args:
        i: its place in the batch, from 1.
        row: {n, slug, asked, concepts, need}.
        s: the Stored posting.
        known, retired: the concepts it may name.
        found: the findings, appended to.
    """
    from ...domain.posting.decide import default_need

    label = f"requirements[{i}]"
    slug, asked = str(N.field(row, "slug") or ""), str(N.field(row, "asked") or "").strip()
    try:
        n = int(str(N.field(row, "n")))
    except (TypeError, ValueError):
        found.append(("FAIL", f"{label}: n {N.field(row, 'n')!r} is not a line number",
                      "fix:  the line's number, as app_show lines prints it"))
        return None
    if not re.fullmatch(O.SLUG, slug):
        found.append(("FAIL", f"{label}: slug {slug!r} is not lowercase words joined by `_`",
                      "fix:  e.g. event_driven"))
        return None
    if not asked:
        found.append(("FAIL", f"{label}: {slug} asks nothing",
                      "fix:  `asked` is the term as the line writes it"))
        return None
    concepts = N.field(row, "concepts") or []
    if isinstance(concepts, str):
        concepts = [c for c in concepts.split(",") if c.strip() not in ("", "-")]
    iris = tuple(sorted(iri for c in concepts
                        if (iri := concept_iri(c, f"{label} ({slug})", known, retired,
                                               found))))
    line = next((x for x in s.lines if x.n == n), None)
    need = N.field(row, "need") or (default_need(line) if line else "")
    return label, slug, (asked, str(need).removeprefix("j:"), iris,
                         line.text if line else "", n)


def checked(s, kept, batch, drops):
    """rows.py's findings for every requirement the posting will hold and every new drop.

    The kept ones are checked first, so a clash is reported on the batch's row; one the
    batch replaces is not checked as it was.

    Args:
        s: the Stored posting.
        kept: {slug: row} of the stored requirements not removed.
        batch: [(label, slug, row)] of the batch.
        drops: {i: (n, reason)} of the batch's drops.

    Returns:
        [(severity, text, fix)].
    """
    from ...domain.posting.rows import Rows

    lines = {x.n: x for x in s.lines}
    rows = Rows(lines, at=str, listed="of the advert's lines",
                refetch="fix:  `app_show` with part lines numbers them")
    replaced = {slug for _, slug, _ in batch}
    order = [(f"stored {slug}", slug, row) for slug, row in kept.items()
             if slug not in replaced] + batch
    found = []
    for label, slug, (asked, need, _, _, n) in order:
        found += rows.row(label, n, slug, asked, need=need)
        if n in lines and need in O.ENUMS["necessity"]:
            found += [(sev, text, fix) for sev, text, fix in rows.necessity(label, n, slug, need)]
    quoted = {row[4]: slug for _, slug, row in order}
    for i, (n, _) in drops.items():
        found += rows.drop(f"drops[{i}]", n)
        if n in quoted:
            found.append(("FAIL", f"drops[{i}]: line {n} is dropped and quoted by "
                                  f"{quoted[n]}", "fix:  drop it, or decide it - not both"))
    return found


def pruned_review(store, app, slugs):
    """The review graph less its rows (and its asks' j:about) on requirements no longer in
    `slugs`, and back to draft - it reviewed requirements that have changed - or None when
    there is no review, or it is a draft with no such row.

    Args:
        store: the loaded workspace.
        app: the App.
        slugs: the requirements the posting will hold.
    """
    from ...domain.assessment.review import overlay_of, triples

    name = app.graph("review")
    if name not in store.parsed:
        return None
    quads = store.graph(name)
    overlay = overlay_of(quads)
    keep = [row for row in overlay.rows if row.slug in slugs]
    # An ask about a removed requirement keeps its question and loses its j:about, which
    # would point at nothing.
    about = {q: slug for q, slug in overlay.about.items() if slug in slugs}
    done = any(q.predicate.value == O.J + "state" and q.object.value == O.J + "complete"
               for q in quads)
    if len(keep) == len(overlay.rows) and len(about) == len(overlay.about) and not done:
        return None
    overlay.rows, overlay.about = keep, about
    return triples(overlay, app.ids, "draft")
