"""A selection as the resume graph holds it: resume.json's dict to triples and back.

Ruling 6 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: a
graph-native application keeps no resume.json; its selection is the graph
`applications/<stem>/resume` (or `resumes/<name>/resume` for a general resume). The file's
keys stay the interchange format - `doc_of` gives back the dict short.shape and short.ids
check and plan.build renders - so nothing downstream of the dict changes.

One `k:sel_<x>` holds the settings and the summary and headline blocks; one
`k:pck_<x>_<list>_<i>` per entry a list names, its place in `j:position`. A `names` entry is
the alias on its skill's pick; a skill renamed but not listed gets a pick of the `names`
list. An empty list is no list: plan.build reads both the same.

Ruling 7: a frozen graph-native application's recordSha256 is the SHA-256 of `canonical`.
Nothing here reads a file or the store.
"""
import hashlib
import json

from .short import KEYS, VERSION

# resume.json's settings, by their predicate (ontology.Selection).
SETTINGS = {"format": "format", "region": "region", "pages": "pages",
            "ats_pages": "atsPages", "floor": "floor"}
# A prose block's keys, by the suffix of their predicate: summaryText, headlineSha, ...
BLOCK = {"text": "Text", "status": "Status", "answer": "Answer", "text_sha256": "Sha"}
# The lists, in resume.json's order; `names` holds only the skills no list names.
LISTS = ("bullets", "roles", "skills", "names")


def triples_of(doc, sel_id):
    """The resume graph's triples for the resume.json dict `doc`.

    Args:
        doc: a resume.json dict, its shape already checked (short.shape).
        sel_id: the selection's local id: `sel_app_<stem>` or `sel_cv_<name>`.

    Returns:
        [Triple].
    """
    import pyoxigraph as ox

    from .. import ontology as O

    def j(name):
        return ox.NamedNode(O.J + name)

    def integer(n):
        return ox.Literal(str(n), datatype=ox.NamedNode(O.XSD + "integer"))

    sel = ox.NamedNode(O.K + sel_id)
    tail = sel_id.removeprefix("sel_")
    out = []
    for key, pred in SETTINGS.items():
        if doc.get(key) is not None:
            value = doc[key]
            out.append(ox.Triple(sel, j(pred), integer(value) if isinstance(value, int)
                                 else ox.Literal(value)))
    for block in ("summary", "headline"):
        for key, suffix in BLOCK.items():
            value = (doc.get(block) or {}).get(key)
            if value is not None:
                out.append(ox.Triple(sel, j(block + suffix), ox.Literal(value)))
    if not out:
        # The head must hold a triple to exist: a selection with every setting at its
        # default still says which selection it is.
        out.append(ox.Triple(sel, j("note"), ox.Literal("defaults throughout")))
    names = dict(doc.get("names") or {})
    lists = {key: list(doc.get(key) or []) for key in LISTS[:-1]}
    lists["names"] = [s for s in names if s not in lists["skills"]]
    for key in LISTS:
        for i, ident in enumerate(lists[key], 1):
            p = ox.NamedNode(f"{O.K}pck_{tail}_{key}_{i}")
            out += [ox.Triple(p, j("selection"), sel), ox.Triple(p, j("item"), ox.NamedNode(O.K + ident)),
                    ox.Triple(p, j("position"), integer(i))]
            if ident in names and key in ("skills", "names"):
                out.append(ox.Triple(p, j("alias"), ox.Literal(names[ident])))
    return out


def doc_of(triples):
    """The resume.json dict a resume graph holds: `"resume": 2` and only short.KEYS.

    Args:
        triples: the resume graph's triples or quads.

    Returns:
        The dict, as plan.build takes it.
    """
    from .. import ontology as O

    props, picks = {}, {key: [] for key in LISTS}
    for t in triples:
        if not t.predicate.value.startswith(O.J):
            continue
        props.setdefault(t.subject.value, {})[t.predicate.value[len(O.J):]] = t.object.value
    doc: dict = {"resume": VERSION}
    for s, p in props.items():
        cls = O.class_of(s)
        if cls == "Selection":
            for key, pred in SETTINGS.items():
                if pred in p:
                    doc[key] = int(p[pred]) if KEYS[key] is int else p[pred]
            for block in ("summary", "headline"):
                found = {key: p[block + suffix] for key, suffix in BLOCK.items()
                         if block + suffix in p}
                if found:
                    doc[block] = found
        elif cls == "Pick":
            # The list is in the id - k:pck_<x>_<list>_<i> - since an entry's class alone
            # cannot tell a listed skill from one that is only renamed.
            key = s.rsplit("_", 2)[-2]
            picks[key].append((int(p["position"]), p["item"][len(O.K):], p.get("alias")))
    names = {}
    for key in LISTS:
        items = sorted(picks[key])
        if key != "names" and items:
            doc[key] = [ident for _, ident, _ in items]
        names.update({ident: alias for _, ident, alias in items if alias is not None})
    if names:
        doc["names"] = names
    return doc


def canonical(doc):
    """The selection as one canonical text: what Ruling 7 hashes. Key order, whitespace and
    escaping are fixed, so the same selection always gives the same bytes."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(doc):
    """The SHA-256 hex of canonical(doc), UTF-8: a graph-native freeze's recordSha256."""
    return hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest()
