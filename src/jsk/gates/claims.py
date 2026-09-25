#!/usr/bin/env python3
"""The claims gate: a URS record joined with the career record it was written from.

Usage: python -m jsk.gates.claims <resume.json> [--root DIR] [--max-findings N]
       --root DIR          the workspace (the folder holding career/kb.ttl); by default
                           the nearest one above the record
       --max-findings N    print at most N failures and N warnings (default 25; 0 all)

Exit 0 = every claim traces to the career. Exit 1 = do not render this - or the career
record could not be read, so nothing could be traced. Exit 2 = usage, or no career/kb.ttl.

The record gate (validate_urs) checks a record against itself: a numeral in a bullet has
to appear in one of that bullet's own metrics. But the record is written by hand for one
application, and so are its metrics - a rewritten clause and its rewritten metric agree
with each other and with nothing the person ever confirmed. This gate checks the record
against the career instead. Ids are shared between the two (`prj_`, `ach_`, `met_`, ...),
so each check is a join:

  FAIL  1  an entry of a kind kb.ttl holds (achievement, project, role, qualification,
           ...) that kb.ttl does not hold must be at most inferred in the record
  FAIL  2  no record provenance above the one kb.ttl holds for the same id
  FAIL  2a a bullet kb.ttl holds sits under the project kb.ttl's j:project names (or an
           engagement listing that project or holding its role)
  WARN  2b a bullet kb.ttl holds keeps at least half of kb.ttl's content words and adds
           no more than twice as many as it kept - wording is retuned per posting
  FAIL  3  every numeral in a bullet is in the current version of a metric it cites
           (kb.ttl's j:cites for a bullet kb.ttl holds; the record's metric ids only for
           one it does not), or in the words of the confirmed kb bullet it carries -
           else it is superseded (an older version's number) or untraced
  WARN  4  a vocabulary label in a bullet names a concept its project does not hold
  WARN  5  a skill's name or alias names a concept no project holds
  WARN  6  "N years of X" beyond what the roles behind the projects holding X cover

4-6 read prose, where a word can be a technology or not ("Go"), so they warn until they
have been measured at zero false positives on real records, and 2b reads it too. 1-3 read
ids and numbers.
"""
import datetime
import os
import re
import sys
from dataclasses import dataclass

from .validate_urs import SCALE, Report, covered, numerals, show, walk_achievements

MAX_FINDINGS = 25
RANK = {"confirmed": 3, "inferred": 2, "needs-verification": 1, "disputed": 0}

# "8 years of Kubernetes", "8+ yrs of hands-on K8s", "8 years' experience with Kafka".
YEARS = re.compile(r"(?<![\d.])(\d{1,2})\+?\s*(?:years?|yrs?)(?:'|’)?\s+"
                   r"(?:of\s+)?(?:(?:hands-on|professional|production|commercial)\s+)?"
                   r"(?:experience\s+(?:in|with)\s+)?", re.I)


@dataclass(frozen=True)
class Finding:
    check: str        # the rule's name, as the fix and the docs call it
    severity: str     # FAIL | WARN
    focus: str        # the record id it is about
    detail: str
    fix: str

    def text(self):
        return f"{self.check} {self.focus} - {self.detail}\n        fix: {self.fix}"


def find_workspace(record_path):
    """The workspace a record sits in: the nearest folder above it holding career/kb.ttl,
    or None - an old Markdown workspace, or a record outside any workspace."""
    from ..graph.kbcli import find_root

    return find_root(os.path.dirname(os.path.abspath(record_path)))


def load_record(record):
    import json

    if isinstance(record, dict):
        return record
    with open(record, encoding="utf-8") as fh:
        return json.load(fh)


# --- what the career says -----------------------------------------------------------

class Career:
    """The facts of career/kb.ttl the checks join against, each read once."""

    def __init__(self, store):
        from ..graph import ontology as O
        from ..graph.named import holdings
        from ..graph.queries import PRE
        from ..graph.record import KB
        from ..graph.store import graph_iri

        self.store, self.O = store, O
        self.kb = {i for i, files in store.definitions.items() if KB in files}
        kb_graph = graph_iri(KB)
        self.provenance = {r["s"].value: r["pv"].value[len(O.J):] for r in store.select(
            PRE + f"SELECT ?s ?pv WHERE {{ GRAPH <{kb_graph}> {{ ?s j:provenance ?pv }} }}")}
        self.project, self.cites = {}, {}
        for r in store.select(PRE + """SELECT ?a ?proj ?m WHERE { ?a a j:Achievement ;
                                           j:project ?proj OPTIONAL { ?a j:cites ?m } }"""):
            self.project[r["a"].value] = r["proj"].value
            if "m" in r:
                self.cites.setdefault(r["a"].value, set()).add(r["m"].value)
        self.text = {r["a"].value: r["t"].value for r in store.select(
            PRE + "SELECT ?a ?t WHERE { ?a a j:Achievement ; j:text ?t }")}
        self.position = {r["p"].value: r["pos"].value for r in store.select(
            PRE + "SELECT ?p ?pos WHERE { ?p a j:Project ; j:position ?pos }")}
        self.versions = {}               # metric -> [(version, {numbers}, closed day or None)]
        for r in store.select(PRE + """SELECT ?m ?v ?val ?base ?until WHERE {
                ?v j:of ?m ; j:value ?val OPTIONAL { ?v j:baseline ?base }
                OPTIONAL { ?v j:validUntil ?until } }"""):
            nums = {float(r["val"].value)} | ({float(r["base"].value)} if "base" in r else set())
            self.versions.setdefault(r["m"].value, []).append(
                (r["v"].value, nums, r["until"].value if "until" in r else None))
        self.held = holdings(store)
        self.labels = {}                 # label as written -> {concepts}
        for r in store.select(PRE + "SELECT ?c ?l WHERE { ?c j:label|j:former ?l }"):
            self.labels.setdefault(r["l"].value, set()).add(r["c"].value)
        self.by_norm = {}
        for label, cs in self.labels.items():
            self.by_norm.setdefault(O.norm(label), set()).update(cs)
        # Longest first, so ".NET Framework" is read before ".NET" inside it.
        self.patterns = [(label, label_pattern(label))
                         for label in sorted(self.labels, key=lambda s: (-len(s), s))]

    def iri(self, ident):
        return self.O.K + ident

    def current(self, metric):
        return [v for v in self.versions.get(metric, []) if v[2] is None]


def label_pattern(label):
    """A label as it may appear in prose. Written as the vocabulary writes it, except
    that the first letter may change case at the start of a sentence - "Kafka" and
    "kafka", "Team leadership" and "team leadership". A label of three characters or
    fewer matches only as written: "Go" is the language, "go" is a verb."""
    body = re.escape(label)
    if len(label) > 3 and label[0].isalpha():
        body = f"[{label[0].lower()}{label[0].upper()}]" + re.escape(label[1:])
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])")


def labels_in(text, career):
    """[(label, {concepts})] named in `text`, longest first, never overlapping."""
    taken, found = [], []
    for label, pattern in career.patterns:
        for m in pattern.finditer(text):
            if any(m.start() < b and a < m.end() for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((label, career.labels[label]))
    return found


# --- the checks ---------------------------------------------------------------------

def curie(iri):
    from ..graph.writer import curie as c
    return c(iri)


def ids_with_provenance(node, out=None):
    """Every object in the record carrying both an `id` and a provenance status."""
    out = [] if out is None else out
    if isinstance(node, dict):
        status = (node.get("provenance") or {}).get("status") \
            if isinstance(node.get("provenance"), dict) else None
        if isinstance(node.get("id"), str) and status:
            out.append((node["id"], status))
        for value in node.values():
            ids_with_provenance(value, out)
    elif isinstance(node, list):
        for value in node:
            ids_with_provenance(value, out)
    return out


def kb_could_hold(ident, career):
    """True when `ident` names a class kb.ttl defines - an achievement, a project, a
    role, a qualification, ... - so its absence from kb.ttl means nobody confirmed it.
    A narrative, a view, an engagement or a referee has no kb.ttl class: it is written
    per application, and there is nothing to join it with."""
    cls = career.O.class_of(career.iri(ident))
    return cls is not None and "kb" in career.O.BY_NAME[cls].kinds


def provenance(doc, career, found):
    """Checks 1 and 2: a record never says more than the career does."""
    for ident, status in ids_with_provenance(doc):
        iri = career.iri(ident)
        if status not in RANK:
            continue                       # validate_urs's to report
        if iri not in career.kb and kb_could_hold(ident, career):
            if RANK[status] > RANK["inferred"]:
                found.append(Finding(
                    "absent-confirmed", "FAIL", ident,
                    f"is {status} in the record, and kb.ttl holds no such entry",
                    "an entry written for this application is inferred until the person "
                    "confirms it: add it to kb.ttl with `jsk kb apply`, then `jsk kb confirm`"))
            continue
        held = career.provenance.get(iri)
        if held in RANK and RANK[status] > RANK[held]:
            found.append(Finding(
                "provenance-raised", "FAIL", ident,
                f"is {status} in the record and {held} in kb.ttl",
                f"write it as {held}, or confirm it with the person: "
                f"`jsk kb confirm {ident} --answer \"...\"`"))


def confirmed_numbers(iri, career):
    """The numbers in a kb bullet's own words, when the person confirmed those words.

    A confirmed bullet may state a number no metric records ("that 3 state regulators
    accepted"): `jsk kb check` passes it, so carrying it word for word must too. An
    unconfirmed bullet's words are nobody's evidence, so they trace nothing."""
    if career.provenance.get(iri) != "confirmed":
        return set()
    pool = set()
    for value, suffix, _ in numerals(career.text.get(iri, "")):
        pool.add(value * SCALE.get(suffix, 1))
    return pool


def numbers(doc, career, found):
    """Check 3: every numeral in a bullet is a number the career holds now - in the
    current version of a metric it cites, or in the confirmed words of the kb bullet it
    carries. A number an older version holds is superseded even when the kb bullet's
    words still say it: those words are stale, and the version history says when."""
    for a, where in walk_achievements(doc):
        ident, text = a.get("id"), a.get("text") or ""
        if not ident or not isinstance(text, str):
            continue
        iri = career.iri(ident)
        held = iri in career.kb
        cited = set(career.cites.get(iri, ()))
        for m in a.get("metrics") or []:
            mid = m.get("id") if isinstance(m, dict) else None
            if isinstance(mid, str) and mid.startswith("met_"):
                if career.iri(mid) not in career.versions:
                    found.append(Finding("number-untraced", "FAIL", ident,
                                         f"names metric {mid}, which kb.ttl does not hold",
                                         "name a metric kb.ttl holds: `jsk kb view --section Metrics`"))
                # A bullet kb.ttl holds cites what kb.ttl says it cites: a metric the
                # record names beside it would let any kb number stand in any bullet.
                if not held:
                    cited.add(career.iri(mid))
        worded = confirmed_numbers(iri, career)
        now = set().union(*(nums for m in cited for _, nums, _ in career.current(m)))
        for value, suffix, shown in numerals(text):
            if covered(value, suffix, now):
                continue
            old = sorted((v, until) for m in cited for v, nums, until in career.versions.get(m, [])
                         if until is not None and covered(value, suffix, nums))
            if not old and covered(value, suffix, worded):
                continue
            if old:
                v, until = old[-1]
                metric = v.rsplit(".v", 1)[0]
                current = ", ".join(curie(c[0]) for c in career.current(metric)) or "none"
                found.append(Finding(
                    "number-superseded", "FAIL", ident,
                    f"{shown!r} is {curie(v)}'s number, replaced on {until} (current: {current})",
                    f"state the current number - `jsk kb show {curie(metric)}` - or, if the "
                    f"old one is still true, record that in kb.ttl first"))
            else:
                names = ", ".join(sorted(curie(m) for m in cited)) or "no metric"
                found.append(Finding(
                    "number-untraced", "FAIL", ident,
                    f"{shown!r} is in no current version of what it cites ({names})",
                    "use a number kb.ttl holds, or record this one there with `jsk kb apply` "
                    "and cite it (j:cites) from the bullet"))


def moved(doc, career, found):
    """A kb bullet sits where kb.ttl's j:project puts it.

    Its id carries kb.ttl's confirmation, and the confirmation was of the work on that
    project: the same words under another employer are a claim nobody confirmed. Under
    a project, the record's project id must be kb.ttl's; under an engagement, kb.ttl's
    project must be one the engagement lists, or its role one the engagement holds."""
    engagements = {e.get("id"): e for e in doc.get("engagements") or []
                   if isinstance(e, dict)}
    for a, where in walk_achievements(doc):
        ident = a.get("id")
        project = career.project.get(career.iri(ident or ""))
        if project is None or career.iri(ident) not in career.kb:
            continue
        kind, _, parent = where.partition(" ")
        if kind == "project":
            if career.iri(parent) == project:
                continue
        else:
            e = engagements.get(parent) or {}
            listed = {career.iri(p) for p in e.get("projects") or [] if isinstance(p, str)}
            roles = {career.iri(p.get("id")) for p in e.get("positions") or []
                     if isinstance(p, dict) and isinstance(p.get("id"), str)}
            if project in listed or career.position.get(project) in roles:
                continue
        found.append(Finding(
            "project-moved", "FAIL", ident,
            f"kb.ttl holds it under {curie(project)}; the record puts it under {where}",
            f"move it back under {curie(project)}, or write a new bullet for {where} - "
            "inferred until the person confirms it"))


# Words too common to say whether two bullets make the same claim.
STOPWORDS = frozenset(
    "the and for with from into onto over under that this these those its their our was "
    "were has had have than then across through per via also while who which all each "
    "whom".split())


def words(text):
    """A bullet's content words: lower case, no numbers (check 3 reads those), no
    possessive, a plural's s dropped, nothing shorter than three letters."""
    text = re.sub(r"['’]s\b", "", text.lower())
    out = set()
    for w in re.findall(r"[a-z][a-z0-9]*", text):
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if len(w) >= 3 and w not in STOPWORDS:
            out.add(w)
    return out


def retold(doc, career, found):
    """A kb bullet's words are still kb.ttl's words.

    The author retunes wording for each posting, so this warns rather than fails. It
    warns when the record keeps fewer than half of kb.ttl's content words (the id is
    carrying a different claim), or adds more than twice as many new ones as it kept
    (a claim appended to confirmed words)."""
    for a, _ in walk_achievements(doc):
        ident, text = a.get("id"), a.get("text")
        held = career.text.get(career.iri(ident or ""))
        if held is None or not isinstance(text, str):
            continue
        kb, rec = words(held), words(text)
        if not kb:
            continue
        kept, added = kb & rec, rec - kb
        if len(kept) * 2 < len(kb) or len(added) > 2 * len(kept):
            found.append(Finding(
                "text-changed", "WARN", ident,
                f"keeps {len(kept)} of kb.ttl's {len(kb)} content words and adds "
                f"{len(added)} ({', '.join(sorted(added)[:6]) or 'none'}); kb.ttl says "
                f"{held!r}", "say what kb.ttl says - retuned, not replaced - or record the new "
                "claim with `jsk kb apply` and confirm it with the person"))


def source_project(a, owner, career):
    """The project a record bullet is evidence from: kb.ttl's, or the record's own."""
    iri = career.iri(a.get("id") or "")
    if iri in career.project:
        return career.project[iri]
    if owner and owner.startswith("project prj_"):
        return career.iri(owner.split(" ", 1)[1])
    return None


def vocabulary(doc, career, found):
    """Check 4: a technology named in a bullet is one its project holds."""
    for a, where in walk_achievements(doc):
        project = source_project(a, where, career)
        text = a.get("text")
        if project is None or not isinstance(text, str):
            continue
        held = career.held.get(project, set())
        for label, concepts in labels_in(text, career):
            if not concepts & held:
                names = ", ".join(sorted(curie(c) for c in concepts))
                found.append(Finding(
                    "label-unheld", "WARN", a.get("id"),
                    f"names {label!r} ({names}), which {curie(project)} does not hold",
                    f"drop it from the bullet, or add it to {curie(project)} in kb.ttl if the "
                    "work really used it"))


def skills(doc, career, found):
    """Check 5: a skill's name and aliases name concepts some project holds."""
    anywhere = set().union(*career.held.values()) if career.held else set()
    for s in doc.get("skills") or []:
        if not isinstance(s, dict):
            continue
        names = [s.get("name")] + list(s.get("aliases") or [])
        for name in names:
            if not isinstance(name, str):
                continue
            concepts = career.by_norm.get(career.O.norm(name), set())
            if concepts and not concepts & anywhere:
                found.append(Finding(
                    "alias-unheld", "WARN", s.get("id"),
                    f"{name!r} ({', '.join(sorted(curie(c) for c in concepts))}) is held by "
                    f"no project in kb.ttl",
                    "drop the alias - an ATS reads it as a claim of that experience"))


def prose(doc):
    """(where, text) of every string a years claim may be made in."""
    person = doc.get("person") or {}
    if isinstance(person.get("headline"), str):
        yield "person.headline", person["headline"]
    for n in doc.get("narratives") or []:
        if isinstance(n, dict) and isinstance(n.get("text"), str):
            yield n.get("id") or "narrative", n["text"]
    for a, _ in walk_achievements(doc):
        if isinstance(a.get("text"), str):
            yield a.get("id") or "achievement", a["text"]


def years(doc, career, found, today):
    """Check 6: "N years of X" against the roles behind the projects holding X."""
    from ..graph.named import experience_of

    for where, text in prose(doc):
        for m in YEARS.finditer(text):
            rest = text[m.end():]
            label = next((lab for lab, pat in career.patterns if pat.match(rest)), None)
            if label is None:
                continue
            claimed = int(m.group(1))
            months = max(experience_of(career.store, c, today, career.held)[0]
                         for c in career.labels[label])
            if claimed * 12 > months:
                found.append(Finding(
                    "years-overstated", "WARN", where,
                    f"claims {claimed} years of {label}; the roles behind the projects holding "
                    f"it cover {months // 12}y{months % 12}m",
                    f"state what the roles cover (`jsk kb query experience "
                    f"{curie(sorted(career.labels[label])[0])}`), or add the work that makes up "
                    "the rest to kb.ttl"))


def career_refusal(store):
    """A Finding when the career itself cannot be trusted to check against, else None."""
    from ..graph import record as R

    broken = [f for f in store.fails() if f.rule != "log-sync"
              and not f.file.startswith("applications/")]
    if broken:
        return Finding("career-invalid", "FAIL", "career/kb.ttl",
                       f"the career record has {len(broken)} failures, so no claim can be "
                       f"checked against it", "`jsk kb check` lists them")
    st = R.state(store)
    if st.kind != "clean":
        return Finding("career-unlogged", "FAIL", "career/kb.ttl",
                       f"kb.ttl is not what log.ttl last recorded ({st.kind}"
                       + (f": {st.detail}" if st.detail else "") + ") - a provenance raised by "
                       "hand would pass here unseen",
                       "run `jsk kb adopt`: it logs the edit and lists every provenance it raised")
    return None


def findings(record, store, today=None):
    """Every Finding for one record against a loaded workspace, FAILs first."""
    today = today or datetime.date.today()
    doc = load_record(record)
    refusal = career_refusal(store)
    if refusal:
        return [refusal]
    career = Career(store)
    found = []
    provenance(doc, career, found)
    moved(doc, career, found)
    numbers(doc, career, found)
    retold(doc, career, found)
    vocabulary(doc, career, found)
    skills(doc, career, found)
    years(doc, career, found, today)
    return sorted(found, key=lambda f: f.severity != "FAIL")


def check(record, store, today=None):
    """The claims gate as a validate_urs.Report: `record` a resume.json path or its
    parsed dict, `store` the workspace loaded by jsk.graph.store.load. What jsk ship,
    jsk gates, jsk freeze and jsk migrate call."""
    rep = Report()
    for f in findings(record, store, today):
        (rep.fail if f.severity == "FAIL" else rep.warn)(f.text())
    return rep


def main(argv):
    from ..cliutil import wants_help

    args = list(argv[1:])
    if wants_help(args):
        print(__doc__.split("\n\n")[1])
        return 0
    root, limit, positional = None, MAX_FINDINGS, []
    while args:
        token = args.pop(0)
        if token in ("--root", "--max-findings"):
            if not args:
                print(f"{token} needs a value")
                return 2
            value = args.pop(0)
            if token == "--root":
                root = value
            elif not value.isdigit():
                print(f"--max-findings needs a whole number, got {value!r}")
                return 2
            else:
                limit = int(value) or None
        elif token.startswith("-"):
            print(f"unknown flag: {token}")
            print(__doc__.split("\n\n")[1])
            return 2
        else:
            positional.append(token)
    if len(positional) != 1:
        print(__doc__.split("\n\n")[1])
        return 2
    path = positional[0]
    if not os.path.isfile(path):
        print(f"file not found: {path}")
        return 2
    root = root or find_workspace(path)
    if root is None or not os.path.isfile(os.path.join(root, "career", "kb.ttl")):
        print(f"no career/kb.ttl above {path}")
        print("fix:  the claims gate reads the graph record; pass --root DIR, or migrate a "
              "Markdown knowledge base with `jsk migrate`")
        return 2
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  the claims gate needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ..graph import record as R
    from ..graph import store as S

    try:
        doc = load_record(path)
    except ValueError as e:
        print(f"checking: {os.path.basename(path)}\n\nFAIL 1   WARN 0")
        print(f"  FAIL  not valid JSON: {e}")
        print("\nDO NOT RENDER - fix the failures above")
        return 1
    store = S.load(root)
    rep = check(doc, store)
    st = R.state(store)
    at = f" r{st.log_revision}" if st.log_revision else ""
    print(f"checking: {os.path.basename(path)}   against: career/kb.ttl{at}")
    print(f"\nFAIL {len(rep.fails)}   WARN {len(rep.warns)}")
    show(rep.fails, "FAIL", limit)
    show(rep.warns, "warn", limit)
    if rep.fails:
        print("\nDO NOT RENDER - a claim above is not what the career record holds")
    else:
        print("\nPASS - every id, provenance and number traces to the career record")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
