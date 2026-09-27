"""The gap assessment the match already knows, derived without a model.

On the three tailoring runs made with the fast-tailor flow the analyst kept the match's
verdict on every row but seven, and each of the seven turned on meaning the triples do not
carry: whom a person mentored, one cloud or several, a product the advert named that no
bullet does. So everything else - the verdict, its evidence, why the match says it - comes
from `match.result`, in milliseconds, and gaps.txt carries only what the analyst changes.

This is pure: a function of the match result and the store, with no file I/O.
"""
import re
from dataclasses import dataclass

IMPLICIT = "implicit — the match does not assess it"
FLAG = "listed-names"
# The analyst's order: blocking, unmet, unconfirmed, missing metric, unexplored.
ORDER = {"implied": 1, "broader-held": 1, "tag-only": 2, "missing-metric": 3,
         "ambiguous": 4, "unknown-term": 4}
LIST_SPLIT = re.compile(r"\s*(?:,|/|\band\b|\bor\b)\s*", re.I)


@dataclass(frozen=True)
class Row:
    id: str                 # the requirement, as match gives it: "k:req_<stem>_<slug>"
    slug: str               # <slug>: what gaps.txt names the row by
    asked: str
    necessity: str          # required | preferred | implicit
    state: str              # the match's bucket: matched, near, missing, ambiguous, ...
    matched: str | None     # the match's verdict; None for implicit
    evidence: tuple         # "k:prj_x" curies behind the verdict, sorted
    basis: str              # why the match says what it says, one sentence
    flags: tuple            # ("listed-names",) when the review flag fires, else ()
    flag_text: str | None   # what the flag found: "names Pinecone, Milvus; the evidence never does"


@dataclass(frozen=True)
class Derived:
    posting: str            # "k:post_<stem>"
    stem: str
    rows: tuple             # Row, in the match's requirement order
    fit: str                # fit_default: strong | partial | poor
    questions: tuple        # str, ready to ask, in the analyst's order; no list markers


def derive(r, store):
    """Derived for the match result `r` (match.result) over `store`."""
    stem = r["posting"].removeprefix("k:post_")
    rows = []
    for q in r["requirements"]:
        flag_text = listed_names(q, _texts(store, q)) if q["verdict"] == "satisfied" else None
        rows.append(Row(id=q["id"], slug=slug_of(q["id"], stem),
                        asked=q["asked"], necessity=q["necessity"], state=q["state"],
                        matched=q["verdict"], evidence=_evidence(q), basis=_basis(q),
                        flags=(FLAG,) if flag_text else (), flag_text=flag_text))
    return Derived(posting=r["posting"], stem=stem, rows=tuple(rows), fit=fit_default(r),
                   questions=tuple(_questions(r)))


def slug_of(req, stem):
    """The row's name in gaps.txt: `k:req_<stem>_<slug>` -> `<slug>`, as `jsk posting build`
    mints them. A migrated posting's requirements need not carry its stem
    (`post_elevenlabs_creative_studio` asks `req_elevenlabs_api_design`); theirs is the whole
    id after `req_`, which is as unique as the id."""
    local = req.removeprefix("k:req_")
    return local.removeprefix(f"{stem}_") if local.startswith(f"{stem}_") else local


def fit_default(r):
    """poor when a required requirement is unsatisfied, strong when every required one is
    satisfied, otherwise partial."""
    required = [q["verdict"] for q in r["requirements"] if q["necessity"] == "required"]
    if "unsatisfied" in required:
        return "poor"
    if required and all(v == "satisfied" for v in required):
        return "strong"
    return "partial"


def listed_names(q, texts):
    """For a satisfied requirement `q` (a match.result requirement) and the confirmed
    evidence bullets' words: what the flag found, or None."""
    if q["verdict"] != "satisfied":
        return None
    items = _listed(q["asked"])
    if items is None:
        return None
    missing = [x for x in items if not _present(x, texts)]
    return f"names {', '.join(missing)}; the evidence never does" if missing else None


def _listed(asked):
    """The items an `asked` lists, or None: `(a, b)`, or `a, b and c` itself."""
    asked = re.sub(r"\A[^():,]+:\s*", "", asked)          # a leading `X:` heading
    m = re.search(r"\(([^)]*)\)", asked)
    inner = m.group(1) if m else (asked if "," in asked else None)
    if inner is None:
        return None
    items = (x.strip(" .") for x in LIST_SPLIT.split(inner))
    return [x for x in items if x and x.lower() not in ("and", "or", "etc")]


def _present(term, texts):
    body = r"[\s-]+".join(re.escape(w) for w in re.split(r"[\s-]+", term.strip()) if w)
    return any(re.search(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", t, re.I) for t in texts)


def _bare(curie):
    """`prj_x` for `k:prj_x`: the basis is read by people, and cites ids bare."""
    return curie.removeprefix("k:")


def _iri(curie):
    from .ontology import C, K

    return (K + curie[2:] if curie.startswith("k:") else C + curie[2:] if curie.startswith("c:")
            else curie)


def _confirmed(q):
    return [c for c in q["carriers"] if c["evidence"] == "confirmed"]


def _texts(store, q):
    """The words of the confirmed bullets behind a satisfied row: what the flag reads."""
    from .queries import confirmed_texts

    concepts = [_iri(c) for c in q["concepts"]]
    if not concepts:
        return []
    return [t for c in _confirmed(q) for t in confirmed_texts(store, _iri(c["project"]), concepts)]


def _evidence(q):
    """The projects the old gaps.md draft cited, as curies: what stands behind the verdict."""
    if q["verdict"] == "satisfied":
        found = [c["project"] for c in _confirmed(q)]
    elif q["verdict"] == "unevidenced":
        found = [c["project"] for c in q["carriers"]]
    elif q["verdict"] == "partial":
        found = [n["project"] for n in q["near"]]
    else:
        found = []
    return tuple(sorted(set(found)))


def _basis(q):
    """One mechanical sentence per bucket (Ruling 2): why the match says what it says."""
    state, verdict = q["state"], q["verdict"]
    if state == "implicit" or verdict is None:
        return IMPLICIT
    if state == "near":
        # ` / `, not `; `: a why already holds one ("implied by c:x; confirm").
        return " / ".join(f"{_bare(n['project'])}: {n['why']}" for n in q["near"])
    if state == "matched" and verdict == "satisfied":
        return "confirmed on " + ", ".join(_bare(c["project"]) for c in _confirmed(q))
    if state == "matched":
        return ("carried by " + ", ".join(f"{_bare(c['project'])} ({c['evidence']})"
                                          for c in q["carriers"]) + " only")
    if state == "missing":
        return "nothing in the record holds " + ", ".join(q["concepts"])
    if state == "ambiguous":
        return "names several concepts: " + ", ".join(q["concepts"])
    if state == "candidate":
        return "no concept holds it"
    raise ValueError(f"no basis for the match's bucket {state!r}")


def _questions(r):
    """The match's questions in the analyst's order, the unmet required ones first - the
    order the old gaps.md draft gave them, without its list markers or slots."""
    from .match import question_line

    unmet = [(1, f"**unsatisfied** {q['asked']}: required, and nothing in the record "
                 f"carries it - is there work that shows it?")
             for q in r["requirements"]
             if q["necessity"] == "required" and q["verdict"] == "unsatisfied"]
    asked = [(ORDER[q["kind"]], question_line(q).removeprefix("- ")) for q in r["questions"]]
    return [line for _, line in sorted(unmet + asked, key=lambda x: x[0])]
