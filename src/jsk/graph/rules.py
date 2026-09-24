"""Tier 2: the rules that need the whole workspace, as SPARQL over the union graph.

References across files, metric versions, the vocabulary's edges, applications and their
postings. Each rule is one row - id, severity, a SELECT naming ?focus, and a fix - so
adding one is adding a row, and tests/test_graph_rules.py proves each one fires.
"""
import difflib
from collections import defaultdict
from dataclasses import dataclass

from . import ontology as O
from .shapes import FAIL, WARN, Finding, curie

PREFIX = (f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
          f"PREFIX xsd: <{O.XSD}>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")
COUNTS_AS = "j:isA|j:partOf|j:implies"


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    sparql: str        # SELECT ?focus plus whatever `detail` reads; None: `post` alone
    detail: object     # row dict -> str
    fix: object        # str, or (row, store) -> str
    post: object = None   # optional (rows, store) -> rows, for what SPARQL says badly


def v(row, name):
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
            for iri, node in ordered[1:]:
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
    """One row per extra file a k: id is defined in, pointing at that file: the edit that
    broke the rule is the second definition, not the first. The loader already knows
    where every subject is, so this is a lookup, not a query over every quad."""
    return [{"focus": node(iri), "file": file, "home": files[0]}
            for iri, files in store.definitions.items() if iri.startswith(O.K)
            for file in files[1:]]


def untyped(rows, store):
    typed = {v(r, "focus") for r in rows}
    return [{"focus": node(iri)} for iri in store.definitions
            if iri.startswith(O.C) and iri not in typed]


def concept_class_rules():
    """One rule per predicate that restricts the class of the concept it points at."""
    rules = []
    for cls in O.CLASSES:
        for p in cls.preds.values():
            if isinstance(p.obj, O.Concept) and set(p.obj.classes) != set(O.ENUMS["conceptClass"]):
                allowed = ", ".join(f"j:{c}" for c in p.obj.classes)
                rules.append(Rule(
                    f"concept-class", FAIL,
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
              FILTER(?p NOT IN (j:touched, j:minted, j:carried, j:carriedVersion, j:about))
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
         "an application answers the posting.ttl beside it", misplaced_postings),
    Rule("event-before-submit", WARN,
         """SELECT ?focus ?d ?s WHERE { ?focus j:application ?a ; j:date ?d .
              ?a j:submitted ?s
              FILTER(datatype(?d) = xsd:date && datatype(?s) = xsd:date && ?d < ?s) }""",
         lambda r: f"dated {v(r, 'd')}, before the application was submitted on {v(r, 's')}",
         "check the date: events follow the submission"),
] + concept_class_rules()


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
