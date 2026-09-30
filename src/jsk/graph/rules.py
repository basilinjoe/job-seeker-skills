"""Tier 2: the rules that need the whole workspace, as SPARQL over the union graph.

References across graphs, metric versions, the vocabulary's edges, applications and their
postings. Each rule is one row - id, severity, a SELECT naming ?focus, and a fix - so
adding one is adding a row, and tests/test_graph_rules.py proves each one fires.
"""
import difflib
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from ..domain import ontology as O
from ..domain.record.shapes import FAIL, WARN, Finding, curie
from ..domain.naming import graph_iri

# For the checker alone, as in store.py: `typing` costs a command ~3 ms it never uses.
TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

PREFIX = (f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
          f"PREFIX xsd: <{O.XSD}>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")
COUNTS_AS = "j:isA|j:partOf|j:implies"


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    sparql: str | None      # SELECT ?focus plus whatever `detail` reads; None: `post` alone
    detail: "Callable[[dict], str]"
    fix: "str | Callable[[dict, Any], str]"          # or (row, store) -> str
    # (rows, store) -> rows, for what SPARQL says badly
    post: "Callable[[list, Any], list] | None" = None


def v(row, name) -> "Any":
    """The lexical value of `name` in a SELECT row, or None when the row leaves it unbound.
    Any, not `str | None`: which variables a SELECT always binds is in its text, where the
    checker cannot read it."""
    t = row.get(name)
    return None if t is None else t.value


def dangling_fix(row, store):
    target = v(row, "o")
    ns = O.C if target.startswith(O.C) else O.K
    near = difflib.get_close_matches(target, [x for x in store.defined() if x.startswith(ns)], n=1)
    return f"did you mean {curie(near[0])}?" if near else "define it, or point at one that exists"


def version_gaps(rows, store):
    by = defaultdict(list)
    for r in rows:
        by[v(r, "focus")].append(int(v(r, "v").rsplit(".v", 1)[1]))
    return [{"focus": next(r["focus"] for r in rows if v(r, "focus") == m), "have": sorted(n)}
            for m, n in by.items() if sorted(n) != list(range(1, len(n) + 1))]


def label_clashes(rows, store):
    by = defaultdict(set)
    for r in rows:
        by[O.norm(v(r, "l"))].add((v(r, "focus"), r["focus"]))
    out = []
    for label, owners in sorted(by.items()):
        if len(owners) > 1:
            ordered = sorted(owners)
            for _, node in ordered[1:]:
                out.append({"focus": node, "label": label, "other": ordered[0][0]})
    return out


def misplaced_postings(rows, store):
    def folder(g):
        return g.rsplit("/", 1)[0]
    return [r for r in rows if not any(folder(v(r, "g")) == folder(v(x, "h")) for x in rows
                                       if v(x, "focus") == v(r, "focus"))]


def node(iri):
    import pyoxigraph as ox
    return ox.NamedNode(iri)


def duplicates(rows, store):
    """One row per extra graph a k: id is defined in, pointing at that graph: the edit
    that broke the rule is the second definition, not the first. The loader already knows
    where every subject is, so this is a lookup, not a query over every quad."""
    return [{"focus": node(iri), "file": file, "home": files[0]}
            for iri, files in store.definitions.items() if iri.startswith(O.K)
            for file in files[1:]]


def untyped(rows, store):
    typed = {v(r, "focus") for r in rows}
    return [{"focus": node(iri)} for iri in store.definitions
            if iri.startswith(O.C) and iri not in typed]


def unmatched_narrowing(rows, store):
    return [{"focus": q.subject, "p": q.predicate, "o": q.object} for q in store.unmatched]


def reclassed(rows, store):
    """A concept whose class in the career differs from its shipped class. Reported in kb."""
    kinds = {graph_iri(f): (f, p.kind) for f, p in store.parsed.items()}
    by = defaultdict(lambda: {"kb": set(), "vocabulary": set(), "file": None})
    for r in rows:
        file, kind = kinds.get(v(r, "g"), (None, None))
        if kind in ("kb", "vocabulary"):
            by[v(r, "focus")][kind].add(v(r, "t"))
            if kind == "kb":
                by[v(r, "focus")]["file"] = file
    return [{"focus": node(c), "file": e["file"], "kb": sorted(e["kb"]),
             "shipped": sorted(e["vocabulary"])}
            for c, e in sorted(by.items()) if e["kb"] and e["vocabulary"]
            and e["kb"] != e["vocabulary"]]


def bare_capabilities(store):
    """{concept iri: kb graph} for each live capability the career defines that nothing
    labels or places: no j:label, no isA or partOf, in any graph. Such a concept matches a
    posting only by its exact id, so "system design" never reaches c:systems-design. A kb
    that adds only an edge to one has placed it. The `bare` query lists the same set."""
    kinds = {graph_iri(f): (f, p.kind) for f, p in store.parsed.items()}
    rows = store.select(PREFIX + """SELECT DISTINCT ?g ?c WHERE { GRAPH ?g { ?c a j:Capability }
        FILTER(?g != j:derived)
        FILTER NOT EXISTS { ?c j:label ?l } FILTER NOT EXISTS { ?c j:isA|j:partOf ?b }
        FILTER NOT EXISTS { ?c j:retired ?r } }""")
    out = {}
    for r in rows:
        file, kind = kinds.get(v(r, "g"), (None, None))
        if kind == "kb":
            out[v(r, "c")] = file
    return out


def bare(rows, store):
    """One row for the lot, at k:kb: a finding per concept would bury the rest, and the
    `bare` query already lists them, most-held first."""
    found = bare_capabilities(store)
    if not found:
        return []
    return [{"focus": node(O.K + "kb"), "file": next(iter(found.values())), "n": len(found)}]


# Typography an advert carries and a quote typed from it does not: curly quotes, the
# dashes, the non-breaking hyphen. Folded on both sides, so neither form is wrong.
TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "‛": "'", "“": '"',
                            "”": '"', "‐": "-", "‑": "-", "‒": "-",
                            "–": "-", "—": "-", "―": "-", "−": "-"})
# Markdown emphasis and code marks: `**K8s**` in posting.md says what `K8s` says.
EMPHASIS = re.compile(r"[*_`]+")


def squash(text):
    """Text as the quote check compares it: the words, not their typesetting."""
    text = unicodedata.normalize("NFKC", text).translate(TYPOGRAPHY)
    return re.sub(r"\s+", " ", EMPHASIS.sub("", text)).strip()


def unquoted(rows, store):
    """A requirement whose quote is not in the advert beside it, word for word."""
    import os

    from ..infra.files import Missing, NotUtf8, Unreadable, read_text

    out, adverts = [], {}
    for r in rows:
        file = store.file_of(v(r, "focus"))
        if not file:
            continue
        advert = os.path.join(store.root, os.path.dirname(file), "posting.md")
        if advert not in adverts:
            # (text, None), or (None, why it could not be read) - the finding says which.
            try:
                adverts[advert] = (squash(read_text(advert)), None)
            except Missing:
                adverts[advert] = (None, "posting.md is missing beside it")
            except NotUtf8:
                adverts[advert] = (None, "posting.md beside it is not UTF-8 - save it as UTF-8")
            except Unreadable as e:
                adverts[advert] = (None, f"posting.md beside it could not be read: {e}")
        text, unread = adverts[advert]
        if not squash(v(r, "q")):
            out.append({**r, "why": "the quote is empty"})     # "" is in every advert
        elif unread:
            out.append({**r, "why": unread})
        elif squash(v(r, "q")) not in text:
            out.append({**r, "why": "posting.md does not say it"})
    return out


OPTIONAL_WORDS = re.compile(r"\b(a plus|nice to have|bonus|desirable)\b", re.I)
REQUIRED_WORDS = re.compile(r"\b(must|required|essential)\b", re.I)


def worded_otherwise(rows, store):
    out = []
    for r in rows:
        quote, need = v(r, "q"), v(r, "n")[len(O.J):]
        if need == "required" and (said := OPTIONAL_WORDS.search(quote)):
            out.append({**r, "said": said.group(0), "need": need})
        elif need in ("preferred", "implicit") and (said := REQUIRED_WORDS.search(quote)):
            out.append({**r, "said": said.group(0), "need": need})
    return out


# The advert's lines a requirement should quote: list items under a heading that names
# requirements. Deliberately narrow - a responsibilities or benefits list is not asked of
# the person, and a warning on every line of one would teach the analyst to ignore this.
HEADING_ASKS = re.compile(
    r"\b(requirements?|qualifications?|must|needs?|you have|you('ll| will)? bring|looking for|"
    r"about you|who you are|skills|experience|nice to have|bonus|preferred|desirable)\b", re.I)
HEADING_NOT = re.compile(r"\b(benefits?|perks|we offer|responsibilit\w*|what you('ll| will) do|"
                         r"compensation|salary)\b", re.I)
# Eligibility is gaps.md's `# Eligibility`, never a requirement, so it can never be quoted:
# excluded by its words, or it would warn for the life of the application.
ELIGIBILITY = re.compile(r"authori[sz]\w*|\bvisa|sponsor|clearance|citizen|right to work|"
                         r"work permit|relocat|on-?site|hybrid|remote|located in|based in|"
                         r"time ?zone|background check|export control|security check", re.I)
LIST_ITEM = re.compile(r"\s*(?:[-*•]|\d+[.)])\s+(.*)")
BOLD_LINE = re.compile(r"(\*\*|__)[^*_]+\1:?")
# What `jsk posting extract` sorts the rest of an advert by. A responsibility is listed, not
# asked of the person: its requirement defaults to implicit. A benefits list asks nothing.
HEADING_DOES = re.compile(r"\b(responsibilit\w*|what you('ll| will) (do|work on)|in this role|"
                          r"day[- ]to[- ]day)\b|\byou('ll| will):?\Z", re.I)
HEADING_OFFERS = re.compile(r"\b(benefits?|perks|we offer|compensation|salary)\b", re.I)
HEADING_OPTIONAL = re.compile(r"\b(nice to have|bonus|preferred|desirable|a plus)\b", re.I)
# Headings that offer, beyond HEADING_OFFERS: "What's in it for you?" is a benefits list.
OFFERS_MORE = re.compile(r"(?i)what'?s in it for|\brewards?\b|why join|\bour (values|culture)\b|"
                         r"\babout us\b|\bperks\b")
# A sentence's end. A closing `?` is allowed: "What's in it for me?" is a heading.
TERMINAL = re.compile(r"[.!;,]\Z")
# Headings about the company or the role as a whole: they end a section, never sit in one.
ABOUT = re.compile(r"(?i)about\b|(job description|(role |job )?overview|the role)\s*:?\Z")
# posting.md's first line: the URL, or `Source: <file>` when it was fetched from a file.
FIRST_LINE = re.compile(r"https?://\S+|Source: .+")


def bare_heading(text):
    """A heading without markup: short, no sentence end, and either in capitals (`HOW WE
    WORK`, not `AWS`) or worded as a heading. Words are letter-initial, so `&` is not one."""
    words = re.findall(r"[A-Za-z][\w'/-]*", text)
    if not words or len(words) > 6 or TERMINAL.search(text):
        return False
    letters = re.sub(r"[^A-Za-z]", "", text)
    if len(words) >= 2 and len(letters) >= 3 and letters.isupper():
        return True
    return bool(HEADING_ASKS.search(text) or HEADING_DOES.search(text)
                or HEADING_OFFERS.search(text) or HEADING_NOT.search(text) or OFFERS_MORE.search(text)
                or ABOUT.match(text))


def sub_heading(text):
    """A marked heading that names no section: under qualifications or responsibilities it
    keeps theirs. The Arrow .docx put "Technical Expertise" and "Team Collaboration and
    Coordination" under "Key Responsibilities", and all 21 items read as `other`.

    Not a bare heading - `S,T,O` in capitals opened Allianz's 96-line skills grid - nor a
    `#LI-Remote` hashtag, which in the corpus comes before the boilerplate: both end the
    section as before."""
    if re.match(r"#[^#\s]", text) or not (text.startswith("#") or BOLD_LINE.fullmatch(text)
                                          or text.endswith(":")):
        return False
    words = squash(text).lstrip("#").strip()
    return not (HEADING_ASKS.search(words) or HEADING_DOES.search(words)
                or HEADING_OFFERS.search(words) or HEADING_NOT.search(words)
                or OFFERS_MORE.search(words) or ABOUT.match(words)
                or re.match(r"(?i)the position\b", words))


@dataclass(frozen=True)
class AdvertLine:
    n: int              # from 1, in the advert's order
    section: str        # qualification | responsibility | other
    text: str           # squashed: what a requirement built from it quotes
    optional: bool      # under an optional heading, or worded optionally itself
    elig: bool          # eligibility's words: gaps.md's `# Eligibility`, never a requirement


def _heading(line, text, item):
    return not item and (text.startswith("#") or BOLD_LINE.fullmatch(text)
                         or (text.endswith(":") and len(text.split()) <= 8)
                         or bare_heading(text))


def advert_lines(advert):
    """Every line of the advert a requirement could quote, numbered, with its section. Under
    a qualifications or a responsibilities heading each line is its own item, listed or not:
    a posting.md is written one item per line, and joining them made one quote of a section.
    A heading naming no section is a sub-heading there, and keeps it. Elsewhere a list item
    is `other`, and so is a prose paragraph, its lines joined. What an offered (benefits)
    heading lists is left out; so are posting.md's first line (the URL, or `Source: <file>`)
    and headings, which name sections and ask nothing."""
    advert = re.sub(r"\A---\n.*?\n---\n", "", advert, flags=re.S)    # frontmatter
    found = []          # [section, text, optional heading, is an item]
    section, opt_heading, wrapping, prose = "other", False, None, False
    for line in advert.split("\n"):
        text = line.strip()
        item = LIST_ITEM.fullmatch(line) if not BOLD_LINE.fullmatch(text) else None
        # A wrapped item's continuation - unless an item outside the qualifications is
        # followed by what reads as a heading: asked_lines never joined those, so it is one.
        if wrapping and text and not item and line[:1].isspace() and not (
                section != "qualification" and _heading(line, text, item)):
            if wrapping == "join":
                found[-1][1] = f"{found[-1][1]} {squash(text)}"
            continue
        wrapping = None
        if not text:
            prose = False
        elif not found and not prose and not item and FIRST_LINE.fullmatch(text):
            continue                                # posting.md's first line: where it came from
        elif _heading(line, text, item):
            words = squash(text)
            prose = False
            if HEADING_ASKS.search(words) and not HEADING_NOT.search(words):
                section, opt_heading = "qualification", bool(HEADING_OPTIONAL.search(words))
            elif HEADING_DOES.search(words):
                section, opt_heading = "responsibility", False
            elif (HEADING_OFFERS.search(words) or HEADING_NOT.search(words)
                  or OFFERS_MORE.search(words)):
                section, opt_heading = "offered", False
            elif not (section in ("qualification", "responsibility") and sub_heading(text)):
                section, opt_heading = "other", False
        elif item:
            prose, wrapping = False, "skip"
            if section != "offered":
                found.append([section, squash(item.group(1)), opt_heading, True])
                wrapping = "join"
        elif section == "offered":
            continue                                # a benefits paragraph asks nothing
        elif section in ("qualification", "responsibility"):
            found.append([section, squash(text), opt_heading, False])   # never joined
            prose = True
        elif prose:
            found[-1][1] = f"{found[-1][1]} {squash(text)}"
        else:
            found.append(["other", squash(text), False, False])
            prose = True
    return [AdvertLine(n, sec, text, opt or bool(OPTIONAL_WORDS.search(text)),
                       bool(ELIGIBILITY.search(text)))
            for n, (sec, text, opt, _) in enumerate(found, 1)]


def asked_lines(advert):
    """The advert's requirement-like list items, squashed, in order: what advert-uncovered
    reads back against the quotes."""
    return [x.text for x in advert_lines(advert)
            if x.section == "qualification" and len(x.text.split()) >= 4 and not x.elig]


def dropped_lines(folder, advert):
    """The advert lines decisions.txt beside posting.md drops with a reason: answered, not
    skipped, so not uncovered. A decisions.txt that does not parse drops nothing - `jsk
    posting build` refuses it long before this reads it."""
    import os

    from .decisions import DecisionsError, read
    from ..infra.files import Unreadable

    try:
        drops = read(os.path.join(folder, "decisions.txt")).drops
    except (Unreadable, DecisionsError):
        return set()
    lines = {x.n: x.text for x in advert_lines(advert)}
    return {lines[d.n] for d in drops if d.n in lines}


def uncovered(rows, store):
    """An advert line that asks something no requirement of its posting quotes."""
    import os

    from ..infra.files import Unreadable, read_text

    quotes = defaultdict(list)
    for r in rows:
        # Stripped as the line is below: a quote ending in its line's full stop is not
        # in the line once the line has lost it.
        quotes[v(r, "focus")].append(squash(v(r, "q") or "").casefold().rstrip(".;, "))
    out = []
    for post, said in quotes.items():
        file = store.file_of(post)
        if not file:
            continue
        folder = os.path.join(store.root, os.path.dirname(file))
        try:
            advert = read_text(os.path.join(folder, "posting.md"))
        except Unreadable:
            continue                        # quote-verbatim says why it could not be read
        said = [q for q in said if q]
        dropped = dropped_lines(folder, advert)
        for line in asked_lines(advert):
            if line in dropped:
                continue                    # dropped with a reason, which gaps.md shows
            low = line.casefold().rstrip(".;, ")
            if not any(q in low or low in q for q in said):
                out.append({"focus": node(post), "line": line})
    return out


def out_of_step(kinds):
    """Rows for the record state kinds a rule reports, at k:kb in kb - for a workspace
    still laid out as files, which the import reads. A stored record has none of these
    states: every write puts the career and its log entry in one update, and the store
    keeps no text for a hand to edit."""
    def post(rows, store):
        from .record import state
        if store.stored:
            return []
        st = state(store)
        return [{"focus": node(O.K + "kb"), "state": st}] if st.kind in kinds else []
    return post


def log_sync_fix(row, store):
    rev = row["state"].log_revision
    if row["state"].kind == "torn" and rev is not None:
        return (f"set kb.ttl's k:kb j:revision back to {rev}, then run `jsk kb load .` again: "
                "it imports kb.ttl as it is, and names each provenance the unlogged write "
                "raised")
    return "restore the file that went back on its own, then `jsk kb load .`"


# What an answer is not: a word that agrees without saying what was agreed to.
PLACEHOLDER = re.compile(r"\s*(|y|yes|ok|okay|sure|fine|right|correct|true|done|confirm(ed)?|"
                         r"n/?a|none|tbd|todo|\?+|\.+|-+|<[^>]*>)\s*[.!]?\s*", re.I)


# What an answer to confirm is not, either: the person saying it is wrong.
DENIAL = re.compile(r"\s*(no|nope|nah|never|wrong|incorrect|false|not (true|right|correct))"
                    r"\s*[.!]?\s*", re.I)


def placeholder_answers(rows, store):
    out = []
    for r in rows:
        answer = v(r, "a")
        if answer is None or PLACEHOLDER.fullmatch(answer) or DENIAL.fullmatch(answer):
            out.append({**r, "said": answer})
    return out


def bad_periods(rows, store):
    """A role's dates that cannot all be true - what the URS record gate checked of the
    periods copied into it (validate_urs.check_periods), until the resume was built from
    kb.ttl and the copy went (2026-09-25). A year against a month compares the year:
    "2016" does not end before "2016-08" starts."""
    out = []
    for r in rows:
        start, end, state = v(r, "start"), v(r, "end"), v(r, "state")
        state = state[len(O.J):] if state else None
        common = min(len(start or ""), len(end or ""))
        if state == "ongoing" and end:
            said = f"ongoing, but it ends {end}"
        elif state == "ended" and not end:
            said = "ended, with no j:end"
        elif start and end and end[:common] < start[:common]:
            said = f"ends {end}, before it starts {start}"
        else:
            continue
        out.append({**r, "said": said})
    return out


def concept_class_rules():
    """One rule per predicate that restricts the class of the concept it points at."""
    rules, seen = [], set()
    for cls in O.CLASSES:
        for p in cls.preds.values():
            if isinstance(p.obj, O.Concept) and set(p.obj.classes) != set(O.ENUMS["conceptClass"]):
                # Project.domain and Posting.domain are one predicate with one restriction:
                # one rule, or every such fault is reported twice.
                if (p.name, p.obj.classes) in seen:
                    continue
                seen.add((p.name, p.obj.classes))
                allowed = ", ".join(f"j:{c}" for c in p.obj.classes)
                rules.append(Rule(
                    "concept-class", FAIL,
                    f"""SELECT ?focus ?o ?t WHERE {{ GRAPH ?g {{ ?focus j:{p.name} ?o }}
                        ?o a ?t . FILTER(STRSTARTS(STR(?o), STR(c:)))
                        FILTER(?t NOT IN ({allowed}))
                        FILTER NOT EXISTS {{ ?o a ?ok FILTER(?ok IN ({allowed})) }} }}""",
                    lambda r, name=p.name, cl=p.obj.classes:
                        f"j:{name} {curie(v(r, 'o'))} is a {curie(v(r, 't'))}; "
                        f"expected {' or '.join(cl)}",
                    "point at a concept of that class"))
    # Several predicates share a rule id; the rule is the same, only the predicate differs.
    return rules


RULES = [
    Rule("dangling", FAIL,
         """SELECT ?focus ?p ?o WHERE { GRAPH ?g { ?focus ?p ?o }
              FILTER(?g != j:derived && isIRI(?o))
              FILTER(STRSTARTS(STR(?o), STR(k:)) || STRSTARTS(STR(?o), STR(c:)))
              FILTER(?p NOT IN (j:touched, j:minted))
              FILTER NOT EXISTS { GRAPH ?h { ?o ?q ?x } FILTER(?h != j:derived) } }""",
         lambda r: f"{curie(v(r, 'p'))} {curie(v(r, 'o'))}: nothing defines it",
         dangling_fix),
    Rule("duplicate-id", FAIL, None,
         lambda r: f"also defined in {r['home']}",
         "keep it in one file; an id names one thing", duplicates),
    Rule("concept-typed", FAIL,
         """SELECT DISTINCT ?focus WHERE { GRAPH ?g { ?focus a ?t }
              FILTER(?g != j:derived && STRSTARTS(STR(?focus), STR(c:))) }""",
         lambda r: "a concept with no class",
         "add `a j:Capability`, `a j:Domain` or `a j:Technology`", untyped),
    Rule("primary-contact", FAIL,
         """SELECT ?focus ?x WHERE { ?focus j:primary ?x
              FILTER NOT EXISTS { ?focus ?p ?x
                FILTER(?p IN (j:email, j:phone, j:linkedin, j:github, j:website)) } }""",
         lambda r: f"j:primary {v(r, 'x')!r} is none of the contact values",
         "set it to one of the email, phone or profile values exactly"),
    Rule("headline-xor", FAIL,
         """SELECT ?focus WHERE { ?focus j:headlineMetric ?m ; j:noneQuantified true }""",
         lambda r: "a headline metric and noneQuantified true",
         "keep j:headlineMetric, or keep j:noneQuantified - not both"),
    Rule("metric-open", FAIL,
         """SELECT ?focus (COUNT(?x) AS ?open) WHERE { ?focus a j:Metric
              OPTIONAL { ?x j:of ?focus FILTER NOT EXISTS { ?x j:validUntil ?u } } }
            GROUP BY ?focus HAVING (COUNT(?x) != 1)""",
         lambda r: ("no current version" if v(r, "open") == "0"
                    else f"{v(r, 'open')} versions with no validUntil"),
         "exactly one version is current: close the older ones with j:validUntil"),
    Rule("range-upper", FAIL,
         """SELECT ?focus ?value ?upper WHERE { ?focus j:value ?value ; j:upper ?upper
              FILTER(?upper <= ?value) }""",
         lambda r: f"j:upper {v(r, 'upper')} is not above j:value {v(r, 'value')}",
         "a range is j:value (its bottom) to j:upper, above its value; one number needs no upper"),
    Rule("period", FAIL,
         """SELECT ?focus ?start ?end ?state WHERE { ?focus j:start ?start
              OPTIONAL { ?focus j:end ?end } OPTIONAL { ?focus j:state ?state } }""",
         lambda r: r["said"],
         "correct the dates, or the state: an ongoing role has no j:end, an ended one has "
         "one, and it is not before j:start", bad_periods),
    Rule("version-orphan", FAIL,
         """SELECT ?focus ?m WHERE { ?focus a j:MetricVersion ; j:of ?m
              FILTER(!STRSTARTS(STR(?focus), CONCAT(STR(?m), ".v"))) }""",
         lambda r: f"j:of {curie(v(r, 'm'))}, but the id says another metric",
         "a version of k:met_x is k:met_x.vN"),
    Rule("version-gap", WARN,
         """SELECT ?focus ?v WHERE { ?v a j:MetricVersion ; j:of ?focus }""",
         lambda r: "versions " + ", ".join(f"v{n}" for n in r["have"]) + " - not v1 upward",
         "number versions v1, v2, … with no gap", version_gaps),
    Rule("rank-unique", FAIL,
         """SELECT ?focus ?a ?r WHERE { ?a j:project ?p ; j:rank ?r .
              ?focus j:project ?p ; j:rank ?r . FILTER(STR(?a) < STR(?focus))
              FILTER NOT EXISTS { ?a j:retired ?x } FILTER NOT EXISTS { ?focus j:retired ?y } }""",
         lambda r: f"rank {v(r, 'r')} is also {curie(v(r, 'a'))}'s",
         "give each bullet of a project its own rank"),
    Rule("headline-cited", WARN,
         """SELECT ?focus ?m WHERE { ?focus j:headlineMetric ?m
              FILTER NOT EXISTS { ?a j:project ?focus ; j:cites ?m } }""",
         lambda r: f"headline {curie(v(r, 'm'))} is cited by none of its bullets",
         "cite it from the bullet that states it, or change the headline"),
    Rule("counts-as-cycle", FAIL,
         # Once per cycle, at its lowest id: every node on a cycle counts as itself, and
         # one bad edge reported at each of them reads as several faults.
         f"""SELECT DISTINCT ?focus WHERE {{ ?focus ({COUNTS_AS})+ ?focus
              FILTER NOT EXISTS {{ ?other ({COUNTS_AS})+ ?focus . ?focus ({COUNTS_AS})+ ?other
                                   FILTER(STR(?other) < STR(?focus)) }} }}""",
         lambda r: "counts as itself through isA / partOf / implies",
         "remove the edge that points back; counts-as runs one way, narrower to broader"),
    Rule("wall-crossed", FAIL,
         f"""SELECT DISTINCT ?focus ?b WHERE {{ ?focus j:distinct ?b .
              {{ ?focus ({COUNTS_AS})+ ?b }} UNION {{ ?b ({COUNTS_AS})+ ?focus }} }}""",
         lambda r: f"declared distinct from {curie(v(r, 'b'))}, yet one counts as the other",
         "remove the edge, or the distinct - they contradict"),
    Rule("label-clash", WARN,
         """SELECT ?focus ?l WHERE { ?focus j:label ?l }""",
         lambda r: f"label {r['label']!r} is also {curie(r['other'])}'s",
         "fine if the word is ambiguous - matching will ask; otherwise drop one",
         label_clashes),
    Rule("inferred-unasked", WARN,
         """SELECT ?focus ?pv WHERE { ?focus j:provenance ?pv
              FILTER(?pv IN (j:inferred, j:needs-verification))
              FILTER NOT EXISTS { ?q j:about ?focus FILTER NOT EXISTS { ?q j:answered ?d } } }""",
         lambda r: f"{curie(v(r, 'pv'))} with no open question about it",
         "add a q_ asking what would confirm it"),
    Rule("retired-referenced", WARN,
         """SELECT ?focus ?p ?o WHERE { GRAPH ?g { ?focus ?p ?o } FILTER(?g != j:derived)
              ?o j:retired ?d
              FILTER(?p NOT IN (j:touched, j:minted, j:carried, j:carriedVersion, j:about,
                                j:evidence))
              FILTER NOT EXISTS { ?focus j:retired ?e } }""",
         lambda r: f"{curie(v(r, 'p'))} {curie(v(r, 'o'))}, which is retired",
         "point at a live entry, or retire this one too"),
    Rule("answered-before-asked", FAIL,
         """SELECT ?focus WHERE { ?focus j:asked ?a ; j:answered ?b FILTER(?b < ?a) }""",
         lambda r: "answered before it was asked",
         "correct one of the two dates"),
    Rule("application-posting", FAIL,
         """SELECT ?focus ?g ?h WHERE { ?focus a j:Application .
              GRAPH ?g { ?focus j:posting ?p } GRAPH ?h { ?p j:captured ?c } }""",
         lambda r: "its posting is defined in another application's directory",
         "an application answers the posting beside it, in its own directory", misplaced_postings),
    Rule("event-before-submit", WARN,
         """SELECT ?focus ?d ?s WHERE { ?focus j:application ?a ; j:date ?d .
              ?a j:submitted ?s
              FILTER(datatype(?d) = xsd:date && datatype(?s) = xsd:date && ?d < ?s) }""",
         lambda r: f"dated {v(r, 'd')}, before the application was submitted on {v(r, 's')}",
         "check the date: events follow the submission"),
    Rule("narrows-nothing", FAIL, None,
         lambda r: f"{curie(v(r, 'p'))} {term_text(r['o'])}: the shipped vocabulary has no such "
                   f"{'label' if v(r, 'p').endswith('unlabel') else 'edge'} on it",
         "check the spelling against vocabulary.ttl; a removal that removes nothing does nothing",
         unmatched_narrowing),
    Rule("concept-reclassed", FAIL,
         """SELECT ?focus ?g ?t WHERE { GRAPH ?g { ?focus a ?t }
              FILTER(?g != j:derived && STRSTARTS(STR(?focus), STR(c:))) }""",
         lambda r: (f"the career makes it {', '.join(curie(t) for t in r['kb'])}; the shipped "
                    f"vocabulary has it as {', '.join(curie(t) for t in r['shipped'])}"),
         "a shipped concept keeps its class: add a capability of your own and relate them",
         reclassed),
    Rule("concepts-bare", WARN, None,
         lambda r: (f"1 capability in the career has no label and no isA/partOf - it matches "
                    f"only its exact id" if r["n"] == 1 else
                    f"{r['n']} capabilities in the career have no label and no isA/partOf - "
                    f"they match only their exact id"),
         "see `jsk kb query bare`; label the most-held first, or adopt "
         "`jsk kb pack capabilities`", bare),
    Rule("quote-verbatim", FAIL,
         """SELECT ?focus ?q WHERE { ?focus a j:Requirement ; j:quote ?q }""",
         lambda r: f"its quote {v(r, 'q')[:50]!r} - {r['why']}",
         "quote the advert's own words, from posting.md; a requirement it does not state is "
         "invented", unquoted),
    Rule("necessity-wording", WARN,
         """SELECT ?focus ?q ?n WHERE { ?focus a j:Requirement ; j:quote ?q ; j:necessity ?n }""",
         lambda r: f"the advert says {r['said']!r} but it is j:{r['need']}",
         "check the necessity against the advert's wording", worded_otherwise),
    Rule("advert-uncovered", WARN,
         """SELECT ?focus ?q WHERE { ?focus a j:Posting
              OPTIONAL { ?r j:posting ?focus ; j:quote ?q } }""",
         lambda r: "the advert asks " + repr(r["line"] if len(r["line"]) <= 70
                                             else r["line"][:67].rstrip() + "…")
                   + " and no requirement quotes it",
         "write a requirement quoting it in the posting, or - if it is eligibility (work "
         "rights, clearance, location) - it belongs in gaps.md's # Eligibility and can stay "
         "unquoted", uncovered),
    Rule("log-sync", FAIL, None,
         lambda r: r["state"].detail, log_sync_fix, out_of_step(("torn", "out-of-sync"))),
    Rule("hand-edited", WARN, None,
         lambda r: r["state"].detail + " - legal, and not yet logged",
         "`jsk kb load .` imports kb.ttl as it is, the edit with it: check every "
         "provenance the edit raised first, since the log will not show it",
         out_of_step(("hand-edited",))),
    Rule("answer-placeholder", WARN,
         """SELECT ?focus ?a WHERE { ?focus j:by j:confirm OPTIONAL { ?focus j:answer ?a } }""",
         lambda r: ("a confirm with no answer" if r["said"] is None
                    else f"a confirm whose answer is {r['said']!r}"),
         "the answer is the audit trail: record what the person said, in their words",
         placeholder_answers),
] + concept_class_rules()


def term_text(t):
    import pyoxigraph as ox
    return curie(t.value) if isinstance(t, ox.NamedNode) else repr(t.value)


def tier2(store):
    """Findings for the whole loaded workspace."""
    out = []
    # A file that did not parse hides every id in it, so every reference to one would be
    # `dangling` - each with a confident "did you mean". Until it parses they cannot be
    # judged, and the syntax error is the finding.
    unreadable = any(f.rule == "syntax" for f in store.findings)
    for rule in RULES:
        if unreadable and rule.id == "dangling":
            continue
        rows = store.select(PREFIX + rule.sparql) if rule.sparql else []
        if rule.post:
            rows = rule.post(rows, store)
        for row in rows:
            focus = row["focus"].value
            file = row.get("file") or store.file_of(focus) or ""
            fix = rule.fix(row, store) if callable(rule.fix) else rule.fix
            out.append(Finding(rule.id, rule.severity, file, store.line_of(focus, file),
                               curie(focus), rule.detail(row), fix))
    return out
