"""Live projects that look like one another, or like what some words describe.

the career_query tool (jsk mcp) and `duplicates` (registered in application/record/queries.py): the
candidates a person judges when one project may have been told twice, scored on the content
words and the concepts the projects share.
"""
from ...domain import ontology as O
from ...domain.matching import resolve as matching
from ...domain.ontology import SPARQL_PREFIX as PRE
from ...domain.record.writer import curie
from .holdings import holdings


# Words any career sentence has; sharing them says nothing about sharing a project.
STOP = frozenset("""also about across after before being been both could each every from
have into made more most much onto only other over same some such than that their them
then there these they this those through under very were what when where which while
with within without would your""".split())
SIMILAR_TOP = 5
SIMILAR_MIN = 0.25               # of what the words ask, the share a project answers
# The pair's score. The fixture careers' closest unrelated pairs score 0.12-0.13 (a shared
# tag or two, a word or two); a planted re-telling of the graph fixture's clinical event
# pipeline in other words scored 0.38. Below the midpoint: a pair too many costs a read,
# a pair missed costs the evidence.
DUPLICATE_MIN = 0.25


def content_words(text):
    """`text`'s content words: kbcli.stems' words and five-letter stems ("onboarded" meets
    "onboarding"), less STOP and bare numbers - a year or a count shared by two projects is
    a coincidence, not a sign they are one.

    Args:
        text: free text.

    Returns:
        {stem: the first word with that stem}.
    """
    from ...domain.record.confirmation import WORD
    from ...domain.posting.advert import squash
    out = {}
    for w in WORD.findall(squash(text).lower()):
        if w not in STOP and not w.isdigit():
            out.setdefault(w[:5], w)
    return out


def project_profiles(store):
    """Every live project's words and concepts: the content words of its name, problem,
    decision, outcome and live bullets, and the concepts it names directly - tags, domains,
    what its bullets show. Direct, not closed upward: two projects that both touch
    something under c:cloud are not one project.

    Args:
        store: a loaded workspace.

    Returns:
        {project: {name, words, concepts, position, recency}}.
    """
    live = "FILTER NOT EXISTS { ?proj j:retired ?x }"
    out = {}
    for r in store.select(PRE + f"""SELECT ?proj ?name ?pos ?rec WHERE {{ ?proj a j:Project
            OPTIONAL {{ ?proj j:name ?name }} OPTIONAL {{ ?proj j:position ?pos }}
            OPTIONAL {{ ?proj j:recency ?rec }} {live} }}"""):
        out[r["proj"].value] = {"name": r["name"].value if "name" in r else "", "words": {},
                                "concepts": set(),
                                "position": r["pos"].value if "pos" in r else None,
                                "recency": int(r["rec"].value) if "rec" in r else None}
    for r in store.select(PRE + f"""SELECT ?proj ?o WHERE {{
            {{ ?proj j:name|j:problem|j:decision|j:outcome ?o }}
            UNION {{ ?b j:project ?proj ; j:text ?o FILTER NOT EXISTS {{ ?b j:retired ?r }} }}
            {live} }}"""):
        if r["proj"].value in out:
            words = out[r["proj"].value]["words"]
            for stem, w in content_words(r["o"].value).items():
                words.setdefault(stem, w)
    for r in store.select(PRE + f"""SELECT ?proj ?c WHERE {{
            {{ ?proj j:uses|j:domain ?c }}
            UNION {{ ?b j:project ?proj ; j:shows ?c FILTER NOT EXISTS {{ ?b j:retired ?r }}
                     FILTER NOT EXISTS {{ ?b j:provenance j:disputed }} }}
            {live} }}"""):
        if r["proj"].value in out:
            out[r["proj"].value]["concepts"].add(r["c"].value)
    return out


def named_concepts(text, store, queries):
    """The concepts `text` names: every run of one to three of its words that is a
    concept's id or label, as `evidence` resolves a term. All of an ambiguous label's
    concepts - this finds candidates, and a person judges them.

    Args:
        text: free text.
        store: a loaded workspace.
        queries: the record's feature reads over `store`.

    Returns:
        {concept iris}.
    """
    index, known = matching.labels(queries), queries.concepts()
    tokens = [t for t in (w.strip(",;:()\"'!?").rstrip(".") for w in text.split()) if t]
    found = set()
    for n in (1, 2, 3):
        for i in range(len(tokens) - n + 1):
            key = O.norm(" ".join(tokens[i:i + n]))
            found |= index.get(key, set()) | ({O.C + key} if O.C + key in known else set())
    return found


def similar(store, *words, queries):
    """The projects a new telling might already be: each live project scored against
    free text - a name, technologies, a sentence - by the share of its content words the
    project's text holds, a concept it names counting double (the project holds it, or
    something that counts as it). People re-tell one project months apart in other words,
    and two entries split its evidence so neither ranks strong; the model judges these
    candidates instead of reading every project. Nothing close is an answer: say so.

    Args:
        store: a loaded workspace.
        *words: the free text, as words.
        queries: the record's feature reads over `store`.

    Returns:
        (columns, rows): the best SIMILAR_TOP projects, or one row saying none is close.
    """
    text = " ".join(words)
    asked, named = content_words(text), named_concepts(text, store, queries)
    held = holdings(store)
    scored = []
    for proj, p in project_profiles(store).items():
        shared = [w for stem, w in asked.items() if stem in p["words"]]
        common = sorted(c for c in named if c in held.get(proj, ()))
        whole = len(asked) + 2 * len(named)
        score = (len(shared) + 2 * len(common)) / whole if whole else 0
        if score >= SIMILAR_MIN and (common or len(shared) >= min(2, len(asked))):
            scored.append((-score, proj, p["name"], shared, common))
    out = [{"project": curie(proj), "name": name, "score": round(-neg, 2),
            "words": ", ".join(shared), "concepts": ", ".join(curie(c) for c in common)}
           for neg, proj, name, shared, common in sorted(scored)[:SIMILAR_TOP]]
    if not out:
        out = [{"project": "", "name": "nothing similar", "score": "", "words": "",
                "concepts": ""}]
    return (("project", "name", "score", "words", "concepts"), out)


def jaccard(a, b):
    """|a & b| / |a | b|, 0 when both are empty.

    Args:
        a, b: sets.

    Returns:
        The share of their union they have in common.
    """
    return len(a & b) / len(a | b) if a | b else 0.0


def duplicates(store):
    """Pairs of live projects that may be one project told twice, closest first: how
    much of their content words and of their concepts they share (Jaccard), and a bonus
    when they sit under the same role within a year of each other - the shape a re-telling
    takes. A candidate list for a reader, who decides by reading both.

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows): each pair and why, or one row saying none looks like a pair.
    """
    import itertools

    profiles = project_profiles(store)
    out = []
    for a, b in itertools.combinations(sorted(profiles), 2):
        pa, pb = profiles[a], profiles[b]
        words = sorted(pa["words"][s] for s in set(pa["words"]) & set(pb["words"]))
        common = sorted(pa["concepts"] & pb["concepts"])
        wj = jaccard(set(pa["words"]), set(pb["words"]))
        cj = jaccard(pa["concepts"], pb["concepts"])
        near = pa["position"] is not None and pa["position"] == pb["position"] and (
            pa["recency"] is None or pb["recency"] is None
            or abs(pa["recency"] - pb["recency"]) <= 1)
        score = 0.6 * wj + 0.4 * cj + (0.1 if near and common else 0)
        if score < DUPLICATE_MIN or len(words) < 3 and not common:
            continue
        why = [f"{len(words)} words shared ({', '.join(words[:8])}"
               + (", ..." if len(words) > 8 else "") + ")" if words else "no words shared"]
        if common:
            why.append("concepts " + ", ".join(curie(c) for c in common))
        if near:
            why.append("same role, " + (f"{pa['recency']} and {pb['recency']}"
                                        if pa["recency"] and pb["recency"] else "undated"))
        out.append({"a": curie(a), "b": curie(b), "score": round(score, 2),
                    "names": f"{pa['name']} / {pb['name']}", "why": "; ".join(why)})
    out.sort(key=lambda r: (-r["score"], r["a"], r["b"]))
    if not out:
        out = [{"a": "", "b": "", "score": "", "names": "nothing looks like one project twice",
                "why": ""}]
    return (("a", "b", "score", "names", "why"), out)
