"""`jsk posting build`: decisions.txt to the application's posting graph in career/store/.

Hand-writing posting.ttl cost the JumpCloud run 26.5k output tokens, most of them ids,
predicates and quotes copied character for character - exactly what the checks then
police. Here the quote is the extracted line itself, so quote-verbatim cannot fail, and
every qualification line must be used or dropped with a reason, so no ask is lost
silently. A responsibility may go unmentioned: its requirement would be implicit, which
the match does not assess, so a drop row for one bought nothing (tailor-cost Ruling 3).

It prints nothing; adapters/cli/posting.py says what it wrote.
"""
import os
import re
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.posting.advert import REQUIRED_WORDS, advert_lines, squash
from ...domain.posting.decide import DECISIONS, SOFT_CAP, default_need
from ...domain.posting.errors import Refused
from .extract import posting_stem, read_advert, workspace


@dataclass(frozen=True)
class Built:
    """What one build wrote."""

    target: str                 # the posting graph's name
    count: int                  # the requirements written
    warnings: list              # each WARN, in the order raised


def build(app_dir, decisions_path, replace, vocabulary, today, *, folder, triples):
    """Write the posting graph from decisions.txt, every quote the advert's own line. The
    caller holds the workspace's turn, taken before anything is read.

    Args:
        app_dir: the application's directory.
        decisions_path: the decisions file, or None for `app_dir`/decisions.txt.
        replace: replace a posting the application already holds, and its assessment.
        vocabulary: the vocabulary file to load, or None for the shipped one.
        today: the `captured:` day when neither the header nor the posting says one.
        folder: the application's folder and record (compose.posting.PostingFolder).
        triples: the posting graph's triples (domain.posting.decide.triples's signature).

    Returns:
        The Built.

    Raises:
        Refused: every problem the decisions file has, and then nothing is written.
    """
    from ...domain.record.decisions import DecisionsError
    from ...domain.record.parsed import Missing, Unreadable
    from ...domain.timeline.errors import Frozen

    # Ruling 6 of the 2026-09-28 review: a sent posting is what the application answered,
    # so it is not rebuilt - and the assessment derived from it is not removed. Asked
    # first, so the refusal writes nothing; the writes below ask again.
    try:
        folder.refuse_if_sent(app_dir, posting_graph(app_dir, folder))
    except Frozen as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None
    if folder.has_record(app_dir, "posting") and not replace:
        raise Refused(f"{app_dir} already holds its posting",
                      "fix:  pass --replace to rebuild it from the decisions file - a "
                      "hand-reviewed posting is replaced whole")
    advert = read_advert(app_dir, folder=folder)
    decisions_path = decisions_path or os.path.join(app_dir, DECISIONS)
    try:
        dec = folder.read_decisions(decisions_path)
    except Missing:
        raise Refused(f"no decisions file at {decisions_path}",
                      f"fix:  `jsk posting extract {app_dir}` lists the lines; write your "
                      f"choices to {decisions_path}") from None
    except Unreadable as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None
    except DecisionsError as e:
        raise Refused(f"{decisions_path}: {e}", "fix:  correct that line") from None
    root, store = workspace(app_dir, vocabulary, folder=folder)
    if root is None or store is None:
        raise Refused(f"no workspace (career/store/) above {app_dir}",
                      "fix:  an application lives at <workspace>/applications/<stem>")
    home, rel = folder.workspace_of_app(app_dir)
    if rel is None or home is None or os.path.normcase(home) != os.path.normcase(root):
        raise Refused(f"{app_dir} is not in {os.path.join(root, 'applications')}",
                      "fix:  an application lives at <workspace>/applications/<dir>, "
                      "and its record goes into the workspace's store under that name")
    d = Decided(app_dir, decisions_path, dec, {x.n: x for x in advert_lines(advert)},
                folder.queries(store), [], [])
    stem = posting_stem(app_dir, root, store, folder=folder)
    post = f"{O.K}post_{stem}"
    seniority, captured, domains = header(d, stem, post, store, today, folder)
    reqs = requirements(d)
    if d.problems:
        raise Refused.every(d.problems)
    if len(reqs) > SOFT_CAP:
        d.warnings.append(f"{len(reqs)} requirements, past the soft cap of {SOFT_CAP}: one per "
                          f"term the match can score - or the posting really is that long")

    # What the posting built would fail, once the decisions hold: every one of them too.
    built_triples = triples(post, stem, dec.header, seniority, domains, captured, reqs)
    checked(d, built_triples, rel, folder)
    if d.problems:
        raise Refused.every(d.problems)
    return written(d, built_triples, rel, len(reqs), store, folder)


def posting_graph(app_dir, folder):
    """The posting graph's name for `app_dir`: its folder's, or the path as given outside
    a workspace."""
    from ...domain.naming import app_graph

    return app_graph(folder.workspace_of_app(app_dir)[1] or app_dir, "posting")


@dataclass
class Decided:
    """One build's decisions file, read: what it is checked against, and what it found."""

    app_dir: str
    path: str                   # the decisions file, as its problems name it
    dec: object                 # domain.record.decisions.Decisions
    lines: dict                 # advert line number -> its AdvertLine
    queries: object             # the feature reads (ports.queries.RecordQueries)
    problems: list              # (message, fix), every one in one pass (tailor-cost Ruling 6)
    warnings: list

    def at(self, line):
        """`path:line`, as a problem names a row."""
        return f"{self.path}:{line}"

    def refuse(self, message, fix):
        """Note a problem; the build refuses with all of them once each pass is done."""
        self.problems.append((message, fix))


def near(term):
    """The fix for a concept that is not one: how to find the nearest."""
    return (f"`jsk kb query concepts --near \"{term}\"` names the nearest; or write `-` "
            f"and let the match report the term")


def concept(d, curie, where, known, retired, domains, domain=False):
    """The concept's iri, or None and a problem. A header domain is not parsed as a row's
    concepts are, so `enterprise software` arrives here - and its hint cut it to
    `terprise software`, by taking off a `c:` it never had.

    Args:
        d: the Decided, which holds the problems.
        curie: the concept as written.
        where: where it was written, for the problem.
        known: the workspace's live concepts.
        retired: its retired concepts.
        domains: its Domains.
        domain: it must be a Domain.

    Returns:
        The iri, or None when it is not one the posting may name.
    """
    if not curie.startswith("c:"):
        d.refuse(f"{where}: domain {curie!r} is not a concept - write `c:…` or leave it "
                 f"blank", f"fix:  {near(curie)}")
        return None
    iri = O.C + curie[2:]
    if iri not in known:
        why = "is retired" if iri in retired else "is not a concept of this workspace"
        d.refuse(f"{where}: {curie} {why}", f"fix:  {near(curie[2:])}")
        return None
    if domain and iri not in domains:
        d.refuse(f"{where}: {curie} is not a Domain", "fix:  name a domain, or none")
        return None
    return iri


def concepts_of(d):
    """(known, retired, domains): the concepts a decisions file may name."""
    retired, domains = d.queries.retired_concepts(), d.queries.domains()
    return d.queries.concepts() - retired, retired, domains


def header(d, stem, post, store, today, folder):
    """The header's problems noted, and what it says.

    Args:
        d: the Decided.
        stem: the posting's stem.
        post: the posting's iri.
        store: the loaded workspace.
        today: the `captured:` day when nothing else says one.
        folder: the application's folder and record.

    Returns:
        (seniority, captured, domain iris).
    """
    head = d.dec.header
    for key in ("company", "title"):
        if not head.get(key):
            d.refuse(f"{d.path}: the header has no `{key}:`",
                     f"fix:  add `{key}: ...` above the rows, as extract printed it")
    seniority = (head.get("seniority") or "").removeprefix("j:")
    if seniority and seniority not in O.ENUMS["seniority"]:
        d.refuse(f"{d.path}: seniority {seniority!r} is not a level",
                 f"fix:  one of {', '.join(O.ENUMS['seniority'])}, or leave it blank")
    known, retired, domains = concepts_of(d)
    if not re.fullmatch(O.SLUG, stem):
        d.refuse(f"{d.app_dir}: the directory name gives no usable posting id ({stem!r})",
                 "fix:  name the directory with lowercase words, e.g. acme-staff-engineer")
        captured = None         # the refusal is raised below; no id to ask the store with
    else:
        captured = head.get("captured") or d.queries.posting_captured(post) \
            or today.isoformat()
    domain_iris = [iri for c in (head.get("domain") or "").split(",")
                   if c.strip() not in ("", "-")
                   and (iri := concept(d, c.strip(), d.at("header"), known, retired, domains,
                                       domain=True))]
    return seniority, captured, domain_iris


def requirements(d):
    """The rows' requirements, every row's and drop's problems noted, and every qual line
    neither used nor dropped.

    Args:
        d: the Decided.

    Returns:
        [(slug, asked, need, concept iris, quote)], in the rows' order.
    """
    known, retired, domains = concepts_of(d)
    lines = d.lines
    used, slugs, asked, reqs = set(), {}, {}, []
    for row in d.dec.rows:
        line = lines.get(row.n)
        if line is None:
            d.refuse(f"{d.at(row.line)}: line {row.n} is not one extract printed "
                     f"(1-{len(lines)})", f"fix:  re-run `jsk posting extract {d.app_dir}`")
            continue
        used.add(row.n)         # answered, even when wrongly: not also "neither used"
        if squash(row.asked).casefold() not in line.text.casefold():
            d.refuse(f"{d.at(row.line)}: {row.asked!r} is not in line {row.n}: {line.text!r}",
                     "fix:  write `asked` as the line writes it, or use the line that says it")
        if row.slug in slugs:
            d.refuse(f"{d.at(row.line)}: slug {row.slug!r} is used on line {slugs[row.slug]} "
                     f"too", "fix:  one slug per requirement")
        slugs.setdefault(row.slug, row.line)
        # `jsk tailor match --gaps` pairs gaps.md's rows to requirements by this, so two with one
        # `asked` could never pair and would warn on even a perfect draft.
        term = O.norm(row.asked)
        if term in asked:
            d.refuse(f"{d.at(asked[term])} and line {row.line}: two requirements ask "
                     f"{row.asked!r}",
                     "fix:  merge them into one requirement, or name each as the advert writes it")
        asked.setdefault(term, row.line)
        iris = [iri for c in row.concepts
                if (iri := concept(d, c, d.at(row.line), known, retired, domains))]
        need = row.need or default_need(line)
        if need == "required" and line.section == "responsibility" \
                and not REQUIRED_WORDS.search(line.text):
            d.warnings.append(f"{d.at(row.line)}: {row.slug} makes responsibility line "
                              f"{row.n} required, and the line does not say so")
        reqs.append((row.slug, row.asked, need, iris, line.text))
    for drop in d.dec.drops:
        if drop.n not in lines:
            d.refuse(f"{d.at(drop.line)}: line {drop.n} is not one extract printed "
                     f"(1-{len(lines)})", f"fix:  re-run `jsk posting extract {d.app_dir}`")
        used.add(drop.n)
    missing = [x.n for x in lines.values()
               if x.section == "qualification" and not x.elig and x.n not in used]
    if missing:
        d.refuse(f"{d.path}: advert line{'s' if len(missing) > 1 else ''} "
                 f"{', '.join(map(str, missing))} neither used nor dropped",
                 "fix:  a row for what it asks, or `n | - | <reason>`")
    return reqs


def checked(d, built_triples, rel, folder):
    """Note what the posting built would fail: a number the store would keep in another
    form, and every tier-1 FAIL.

    Args:
        d: the Decided.
        built_triples: the posting graph's triples.
        rel: the application's folder relative to the workspace.
        folder: the application's folder and record.
    """
    from ...domain.naming import app_graph
    from ...domain.record.parsed import GraphError
    from ...domain.record.shapes import tier1
    from ...domain.record.store import parsed_graph

    candidate = parsed_graph(app_graph(rel, "posting"), built_triples)
    # Ruling 4: a number the store would keep in another form is refused, as a changeset's
    # is - the posting has no text left to show `8.40` once it is stored as `8.4`.
    folder.numbers_as_kept(candidate.quads, lambda focus, detail, fix: d.refuse(
        f"the posting built would not pass: {focus} {detail}", f"fix:  {fix}"))
    # Validated before it is written, as `jsk kb apply` does: a bad url or date is the
    # header's, and is refused here rather than found by the next check.
    try:
        fails = [f.text() for f in tier1(candidate) if f.severity == "FAIL"]
    except GraphError as e:
        fails = [str(e)]
    for fail in fails:
        d.refuse(f"the posting built would not pass: {fail}",
                 "fix:  correct the header or row it names in the decisions file")


def written(d, built_triples, rel, count, store, folder):
    """Write the posting, and remove the assessment derived from the one it replaces.

    The assessment and gaps.md are derived from the posting just replaced: a requirement
    it dropped would leave the assessment dangling, and that FAIL would block prepare
    here. gaps.txt is the analyst's, keyed by slug, and survives any rebuild that keeps
    the slugs.

    Args:
        d: the Decided, whose warnings the removal adds to.
        built_triples: the posting graph's triples.
        rel: the application's folder relative to the workspace.
        count: the requirements written.
        store: the loaded workspace.
        folder: the application's folder and record.

    Returns:
        The Built.

    Raises:
        Refused: the store refused the write; nothing was written.
    """
    from ...domain.naming import app_graph
    from ...domain.timeline.errors import Unwritable

    app_dir = d.app_dir
    try:
        had_gaps = "gaps" in folder.app_graphs(app_dir, store)
        # One update: the new posting and the old assessment's removal land together.
        target = folder.write_graphs(app_dir, {"posting": built_triples, "gaps": None},
                                     store)[0]
        removed = [app_graph(rel, "gaps")] if had_gaps else []
        removed += [n for n in ("gaps.md",) if folder.remove_file(app_dir, n, store)]
    except Unwritable as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None
    if removed:
        d.warnings.append(f"removed {' and '.join(removed)}, derived from the posting this "
                          f"replaces; `jsk tailor prepare` writes them again"
                          + (", with gaps.txt folded in" if folder.is_file(
                              os.path.join(app_dir, "gaps.txt")) else ""))
    return Built(target, count, d.warnings)
