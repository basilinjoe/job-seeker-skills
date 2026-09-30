"""`jsk posting extract` and `jsk posting build`: code extracts the advert's lines, the model
decides in decisions.txt, code writes the posting - the application's posting graph in
career/store/.

Hand-writing posting.ttl cost the JumpCloud run 26.5k output tokens, most of them ids,
predicates and quotes copied character for character - exactly what the checks then
police. Here the quote is the extracted line itself, so quote-verbatim cannot fail, and
every qualification line must be used or dropped with a reason, so no ask is lost
silently. A responsibility may go unmentioned: its requirement would be implicit, which
the match does not assess, so a drop row for one bought nothing (tailor-cost Ruling 3).
"""
import datetime
import os
import re

from ..domain.posting.errors import POSTING, Refused
from ..domain import ontology as O
from .rules import FIRST_LINE, REQUIRED_WORDS, advert_lines, squash

DECISIONS = "decisions.txt"
SOFT_CAP = 20
DATED = re.compile(r"\A\d{4}-\d{2}-\d{2}-")
# Ruling 11: a title word, as a hint only - the analyst decides.
SENIORITY_HINTS = (
    (re.compile(r"\b(principal|staff|architect)\b", re.I), "architecture-ownership"),
    (re.compile(r"\b(lead|manager)\b", re.I), "team-leadership"),
    (re.compile(r"\bsenior\b", re.I), "hands-on-senior"),
    (re.compile(r"\b(junior|graduate)\b", re.I), "junior"),
)
SHORT = {"qualification": "qual", "responsibility": "resp", "other": "other"}


def seniority_hint(title):
    for pattern, level in SENIORITY_HINTS:
        found = pattern.search(title or "")
        if found:
            return found.group(0).lower(), level
    return None, None


def dir_stem(app_dir):
    """post_<this>: the directory's name without a leading date, `-` as `_`."""
    name = DATED.sub("", os.path.basename(os.path.abspath(app_dir))).lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def read_advert(app_dir):
    """posting.md's text. Raises Refused when there is none, or it is not UTF-8."""
    from ..infra.files import Missing, Unreadable, read_text

    path = os.path.join(app_dir, POSTING)
    try:
        return read_text(path)
    except Missing:
        raise Refused(f"no {POSTING} in {app_dir}",
                      f"fix:  jsk posting fetch <url> {app_dir}, or write the advert verbatim "
                      f"to {path}") from None
    except Unreadable as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None


def advert_header(advert):
    """(title, company, url) as posting.md states them: the `# ` heading, the first fact
    of the `a · b · c` line under it, and a URL on line 1. With no `# ` heading the title
    is the first line that is not the URL or `Source:`, and the company is blank - a guess extract
    prints for the analyst to correct, where a blank title only made them type it."""
    lines = advert.split("\n")
    first = next((x.strip() for x in lines if x.strip()), "")
    url = first if re.fullmatch(r"https?://\S+", first) else ""
    title = company = ""
    for i, line in enumerate(lines):
        heading = re.match(r"# (.+)", line)
        if heading:
            title = heading.group(1).strip()
            facts = next((x.strip() for x in lines[i + 1:] if x.strip()), "")
            if " · " in facts:
                company = facts.split(" · ", 1)[0].strip()
            return title, company, url
    body = re.sub(r"\A---\n.*?\n---\n", "", advert, flags=re.S).split("\n")    # frontmatter
    title = next((squash(x.strip().lstrip("#")) for x in body
                  if x.strip().lstrip("#").strip() and not FIRST_LINE.fullmatch(x.strip())), "")
    return title, company, url


def workspace(app_dir, vocabulary):
    """(root, store) for the workspace above the application, or (None, None)."""
    from . import store as S
    from ..infra.files import find_root

    root = find_root(app_dir)
    if root is None:
        return None, None
    return root, (S.load(root) if vocabulary is None else S.load(root, vocabulary=vocabulary))


def posting_stem(app_dir, root, store):
    """The stem of the Posting already in the posting graph - the application points at it - else
    the directory's."""
    if store is not None:
        from ..infra.files import file_name
        from .timeline import posting_of

        _, stem = posting_of(store, file_name(os.path.abspath(app_dir), root))
        if stem:
            return stem
    return dir_stem(app_dir)


def extract(app_dir, vocabulary=None, today=None):
    """The decisions.txt header, ready to copy, then every advert line numbered with its
    section, its flag and the concepts its labels name. Raises Refused."""
    from .queries import labels_in

    advert = read_advert(app_dir)
    title, company, url = advert_header(advert)
    root, store = workspace(app_dir, vocabulary)
    named = labels_in(store) if store is not None else (lambda line: ())
    word, level = seniority_hint(title)
    out = []
    if root is None:
        out.append(f"# no workspace (career/store/) above {app_dir}: no concepts proposed")
    out += [f"# {title or '?'} at {company or '?'}",
            f"# posting id: post_{posting_stem(app_dir, root, store)}"]
    if word:
        out.append(f"# seniority hint: {word} -> {level}")
    out += [f"company: {company}", f"title: {title}", f"url: {url}",
            f"seniority: {level or ''}", "domain:",
            f"captured: {(today or datetime.date.today()).isoformat()}"]
    lines = advert_lines(advert)
    width = len(str(len(lines)))
    out.append("# every qual line is used or dropped; other and responsibility lines need no row")
    out.append(f"# {'n':<{width}} section flag line")
    for x in lines:
        flag = "elig" if x.elig else "opt" if x.optional else ""
        out.append(f"{x.n:<{width}} {SHORT[x.section]:<5} {flag:<4} {x.text}")
        found = named(x.text)
        if found:
            out.append(f"{'':<{width}} concepts: {', '.join('c:' + c[len(O.C):] for c in found)}")
    return "\n".join(out) + "\n"


def default_need(line):
    """Rulings 2 and 6. A qualification is preferred when optional-worded, else required;
    anything else is implicit - unless its own words say required, which is what the
    necessity-wording check would hold an implicit one to."""
    if line.section == "qualification":
        return "preferred" if line.optional else "required"
    return "required" if REQUIRED_WORDS.search(line.text) else "implicit"


def build(app_dir, decisions_path=None, replace=False, vocabulary=None, today=None):
    """(what was written, requirements, warnings): the posting graph's name. Raises
    Refused, and then
    writes nothing. Runs inside the workspace's turn, taken before anything is read."""
    from ..infra.oxigraph import record as R
    from ..infra.files import find_root

    root = find_root(app_dir)
    with R.turn(root, dry_run=root is None):
        return built(app_dir, decisions_path, replace, vocabulary, today)


def built(app_dir, decisions_path, replace, vocabulary, today):
    from . import decisions as D
    from .changeset import numbers_as_kept
    from .io import GraphError, Missing, Unreadable
    from ..infra.oxigraph.queries import OxigraphQueries
    from ..domain.record.shapes import tier1
    from .store import app_graph, parsed_graph
    from .timeline import (Frozen, Unwritable, app_graphs, has_record, refuse_if_sent,
                           remove_app_file, workspace_of_app, write_app_graphs)

    # Ruling 6 of the 2026-09-28 review: a sent posting is what the application answered,
    # so it is not rebuilt - and the assessment derived from it is not removed. Asked
    # first, so the refusal writes nothing; the writes below ask again.
    try:
        refuse_if_sent(app_dir, app_graph(workspace_of_app(app_dir)[1] or app_dir, "posting"),
                       graph=True)
    except Frozen as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None
    if has_record(app_dir, "posting") and not replace:
        raise Refused(f"{app_dir} already holds its posting",
                      "fix:  pass --replace to rebuild it from the decisions file - a "
                      "hand-reviewed posting is replaced whole")
    advert = read_advert(app_dir)
    decisions_path = decisions_path or os.path.join(app_dir, DECISIONS)
    try:
        dec = D.read(decisions_path)
    except Missing:
        raise Refused(f"no decisions file at {decisions_path}",
                      f"fix:  `jsk posting extract {app_dir}` lists the lines; write your "
                      f"choices to {decisions_path}") from None
    except Unreadable as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None
    except D.DecisionsError as e:
        raise Refused(f"{decisions_path}: {e}", "fix:  correct that line") from None
    root, store = workspace(app_dir, vocabulary)
    if root is None or store is None:
        raise Refused(f"no workspace (career/store/) above {app_dir}",
                      "fix:  an application lives at <workspace>/applications/<stem>")

    def at(line):
        return f"{decisions_path}:{line}"

    home, rel = workspace_of_app(app_dir)
    if rel is None or home is None or os.path.normcase(home) != os.path.normcase(root):
        raise Refused(f"{app_dir} is not in {os.path.join(root, 'applications')}",
                      "fix:  an application lives at <workspace>/applications/<dir>, "
                      "and its record goes into the workspace's store under that name")

    # Tailor-cost Ruling 6: every problem the decisions file has, in one pass. A build that
    # stopped at the first cost Schneider's run six builds, each a turn.
    problems = []

    def refuse(message, fix):
        problems.append((message, fix))

    head = dec.header
    for key in ("company", "title"):
        if not head.get(key):
            refuse(f"{decisions_path}: the header has no `{key}:`",
                   f"fix:  add `{key}: ...` above the rows, as extract printed it")
    seniority = (head.get("seniority") or "").removeprefix("j:")
    if seniority and seniority not in O.ENUMS["seniority"]:
        refuse(f"{decisions_path}: seniority {seniority!r} is not a level",
               f"fix:  one of {', '.join(O.ENUMS['seniority'])}, or leave it blank")

    lines = {x.n: x for x in advert_lines(advert)}
    queries = OxigraphQueries(store)
    retired, domains = queries.retired_concepts(), queries.domains()
    known = queries.concepts() - retired

    def near(term):
        return (f"`jsk kb query concepts --near \"{term}\"` names the nearest; or write `-` "
                f"and let the match report the term")

    def concept(curie, where, domain=False):
        """The concept's iri, or None and a problem. A header domain is not parsed as a row's
        concepts are, so `enterprise software` arrives here - and its hint cut it to
        `terprise software`, by taking off a `c:` it never had."""
        if not curie.startswith("c:"):
            refuse(f"{where}: domain {curie!r} is not a concept - write `c:…` or leave it "
                   f"blank", f"fix:  {near(curie)}")
            return None
        iri = O.C + curie[2:]
        if iri not in known:
            why = "is retired" if iri in retired else "is not a concept of this workspace"
            refuse(f"{where}: {curie} {why}", f"fix:  {near(curie[2:])}")
            return None
        if domain and iri not in domains:
            refuse(f"{where}: {curie} is not a Domain", "fix:  name a domain, or none")
            return None
        return iri

    stem = posting_stem(app_dir, root, store)
    post = f"{O.K}post_{stem}"
    if not re.fullmatch(O.SLUG, stem):
        refuse(f"{app_dir}: the directory name gives no usable posting id ({stem!r})",
               "fix:  name the directory with lowercase words, e.g. acme-staff-engineer")
        captured = None         # the refusal is raised below; no id to ask the store with
    else:
        captured = head.get("captured") or existing_captured(store, post) \
            or (today or datetime.date.today()).isoformat()
    domain_iris = [iri for c in (head.get("domain") or "").split(",")
                   if c.strip() not in ("", "-")
                   and (iri := concept(c.strip(), at("header"), domain=True))]

    used, slugs, asked, reqs, warnings = set(), {}, {}, [], []
    for row in dec.rows:
        line = lines.get(row.n)
        if line is None:
            refuse(f"{at(row.line)}: line {row.n} is not one extract printed (1-{len(lines)})",
                   f"fix:  re-run `jsk posting extract {app_dir}`")
            continue
        used.add(row.n)         # answered, even when wrongly: not also "neither used"
        if squash(row.asked).casefold() not in line.text.casefold():
            refuse(f"{at(row.line)}: {row.asked!r} is not in line {row.n}: {line.text!r}",
                   "fix:  write `asked` as the line writes it, or use the line that says it")
        if row.slug in slugs:
            refuse(f"{at(row.line)}: slug {row.slug!r} is used on line {slugs[row.slug]} too",
                   "fix:  one slug per requirement")
        slugs.setdefault(row.slug, row.line)
        # `jsk match --gaps` pairs gaps.md's rows to requirements by this, so two with one
        # `asked` could never pair and would warn on even a perfect draft.
        term = O.norm(row.asked)
        if term in asked:
            refuse(f"{at(asked[term])} and line {row.line}: two requirements ask "
                   f"{row.asked!r}",
                   "fix:  merge them into one requirement, or name each as the advert writes it")
        asked.setdefault(term, row.line)
        iris = [iri for c in row.concepts if (iri := concept(c, at(row.line)))]
        need = row.need or default_need(line)
        if need == "required" and line.section == "responsibility" \
                and not REQUIRED_WORDS.search(line.text):
            warnings.append(f"{at(row.line)}: {row.slug} makes responsibility line {row.n} "
                            f"required, and the line does not say so")
        reqs.append((row.slug, row.asked, need, iris, line.text))
    for drop in dec.drops:
        if drop.n not in lines:
            refuse(f"{at(drop.line)}: line {drop.n} is not one extract printed "
                   f"(1-{len(lines)})", f"fix:  re-run `jsk posting extract {app_dir}`")
        used.add(drop.n)
    missing = [x.n for x in lines.values()
               if x.section == "qualification" and not x.elig and x.n not in used]
    if missing:
        refuse(f"{decisions_path}: advert line{'s' if len(missing) > 1 else ''} "
               f"{', '.join(map(str, missing))} neither used nor dropped",
               "fix:  a row for what it asks, or `n | - | <reason>`")
    if problems:
        raise Refused.every(problems)
    if len(reqs) > SOFT_CAP:
        warnings.append(f"{len(reqs)} requirements, past the soft cap of {SOFT_CAP}: one per "
                        f"term the match can score - or the posting really is that long")

    # What the posting built would fail, once the decisions hold: every one of them too.
    built_triples = triples(post, stem, head, seniority, domain_iris, captured, reqs)
    name = app_graph(rel, "posting")
    candidate = parsed_graph(name, built_triples)
    # Ruling 4: a number the store would keep in another form is refused, as a changeset's
    # is - the posting has no text left to show `8.40` once it is stored as `8.4`.
    numbers_as_kept(candidate.quads, lambda focus, detail, fix: refuse(
        f"the posting built would not pass: {focus} {detail}", f"fix:  {fix}"))
    # Validated before it is written, as `jsk kb apply` does: a bad url or date is the
    # header's, and is refused here rather than found by the next check.
    try:
        fails = [f.text() for f in tier1(candidate) if f.severity == "FAIL"]
    except GraphError as e:
        fails = [str(e)]
    for fail in fails:
        refuse(f"the posting built would not pass: {fail}",
               "fix:  correct the header or row it names in the decisions file")
    if problems:
        raise Refused.every(problems)
    # The assessment and gaps.md are derived from the posting just replaced: a requirement
    # it dropped would leave the assessment dangling, and that FAIL would block prepare
    # here. gaps.txt is the analyst's, keyed by slug, and survives any rebuild that keeps
    # the slugs.
    try:
        had_gaps = "gaps" in app_graphs(app_dir, store)
        # One update: the new posting and the old assessment's removal land together.
        target = write_app_graphs(app_dir, {"posting": built_triples, "gaps": None},
                                  store)[0]
        removed = [app_graph(rel, "gaps")] if had_gaps else []
        removed += [n for n in ("gaps.md",) if remove_app_file(app_dir, n, store)]
    except Unwritable as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None
    if removed:
        warnings.append(f"removed {' and '.join(removed)}, derived from the posting this "
                        f"replaces; `jsk tailor prepare` writes them again"
                        + (", with gaps.txt folded in" if os.path.isfile(
                            os.path.join(app_dir, "gaps.txt")) else ""))
    return target, len(reqs), warnings


def existing_captured(store, post):
    """The day the posting already says it was saved: a rebuild is not a new capture."""
    from ..infra.oxigraph.queries import OxigraphQueries

    return OxigraphQueries(store).posting_captured(post)


def triples(post, stem, head, seniority, domains, captured, reqs):
    import pyoxigraph as ox

    def j(name):
        return ox.NamedNode(O.J + name)

    s = ox.NamedNode(post)
    out = [ox.Triple(s, j("company"), ox.Literal(head["company"])),
           ox.Triple(s, j("title"), ox.Literal(head["title"])),
           ox.Triple(s, j("captured"), ox.Literal(captured, datatype=ox.NamedNode(O.XSD + "date"))),
           ox.Triple(s, j("advert"), ox.Literal(POSTING))]
    if head.get("url"):
        out.append(ox.Triple(s, j("url"), ox.Literal(head["url"])))
    if seniority:
        out.append(ox.Triple(s, j("seniority"), j(seniority)))
    out += [ox.Triple(s, j("domain"), ox.NamedNode(c)) for c in domains]
    for slug, asked, need, iris, quote in reqs:
        r = ox.NamedNode(f"{O.K}req_{stem}_{slug}")
        out += [ox.Triple(r, j("posting"), s), ox.Triple(r, j("asked"), ox.Literal(asked)),
                ox.Triple(r, j("necessity"), j(need)), ox.Triple(r, j("quote"), ox.Literal(quote))]
        out += [ox.Triple(r, j("concept"), ox.NamedNode(c)) for c in iris]
    return out
