"""The gap assessment the match already knows, derived without a model.

On the three tailoring runs made with the fast-tailor flow the analyst kept the match's
verdict on every row but seven, and each of the seven turned on meaning the triples do not
carry: whom a person mentored, one cloud or several, a product the advert named that no
bullet does. So everything else - the verdict, its evidence, why the match says it - comes
from `match.result`, in milliseconds, and gaps.txt carries only what the analyst changes.

This is pure: a function of the match result and the career's queries, with no file I/O.
adapters/cli/compose/tailor.py binds it to a loaded Store.
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
    concepts: tuple = ()    # "c:x" curies the requirement resolved to: what its j:Ask copies


@dataclass(frozen=True)
class Derived:
    posting: str            # "k:post_<stem>"
    stem: str
    rows: tuple             # Row, in the match's requirement order
    fit: str                # fit_default: strong | partial | poor
    questions: tuple        # str, ready to ask, in the analyst's order; no list markers
    # (question, the requirement's "k:req_..." or None) for each of `questions`: what a
    # graph-native assessment's j:Ask points at (fold.triples).
    asks: tuple = ()


def derive(r, queries, ask, absences=(), today=None, counts_as=None):
    """Derived for the match result `r` over the career `queries` reads.

    Args:
        r: match.result's plain data for one posting.
        queries: a RecordQueries over the workspace the match ran on.
        ask: a match question (a dict of match.result's) -> its markdown list item, as
            application.tailor.check_gaps.question_line writes it.
        absences: the career's [domain.record.absence.Absence]. Those the person confirmed
            and that have not lapsed by `today` answer a requirement whose every concept
            they deny (Ruling 9).
        today: the day an absence's lapse is measured against; needed with `absences`.
        counts_as: concept iri -> the iris it counts as without an implies edge (the
            match's own closure, ports.queries.RecordQueries.counts_as), so a no to a
            concept also denies every narrower one; None denies only the concept itself.

    Returns:
        Derived: a row per requirement, the fit, and the questions in the analyst's order.
    """
    stem = r["posting"].removeprefix("k:post_")
    r, said = answered(r, absences, today, counts_as)
    rows = []
    for q in r["requirements"]:
        flag_text = listed_names(q, _texts(queries, q)) if q["verdict"] == "satisfied" else None
        rows.append(Row(id=q["id"], slug=slug_of(q["id"], stem),
                        asked=q["asked"], necessity=q["necessity"], state=q["state"],
                        matched=q["verdict"], evidence=_evidence(q),
                        basis=said.get(q["id"]) or _basis(q),
                        flags=(FLAG,) if flag_text else (), flag_text=flag_text,
                        concepts=tuple(q["concepts"])))
    asks = _questions(r, ask, settled=said)
    return Derived(posting=r["posting"], stem=stem, rows=tuple(rows), fit=fit_default(r),
                   questions=tuple(text for text, _ in asks), asks=tuple(asks))


def answered(r, absences, today, counts_as=None):
    """(the match result with what the person has already said no to settled, {requirement
    id: its basis}).

    Ruling 9: a requirement every one of whose concepts a standing absence denies is
    `missing` - nothing in the record holds it, by the person's own word - with no carriers
    and no question, so the same no is never asked twice. A requirement listing
    alternatives is settled only when every alternative is denied: one denied leaves the
    others to ask about. An implicit requirement stays unassessed; only its question goes.

    Ruling 9's amendment (2026-10-02): a no to X also denies every concept that counts as
    X - "never worked in financial services" answers insurance, which counts as it. Never
    the reverse: a no to EKS says nothing of Kubernetes, as EKS work is Kubernetes work but
    not the other way round. The closure is the match's (`counts_as`), not a second one.

    Args:
        r: match.result's plain data.
        absences: [domain.record.absence.Absence].
        today: the day lapses are measured against.
        counts_as: concept iri -> the iris it counts as, or None (derive's).

    Returns:
        (r, or a copy with the settled requirements and questions changed; {id: basis}).
    """
    from ..record.absence import standing

    if not absences:
        return r, {}
    denied = standing(absences, today)

    def denial(c):
        if c in denied:
            return denied[c]
        broader = sorted(b for b in (counts_as(c) if counts_as else ()) if b in denied)
        return denied[broader[0]] if broader else None

    said, asked = {}, set()
    reqs = []
    for q in r["requirements"]:
        concepts = [_iri(c) for c in q["concepts"]]
        nos_of = [denial(c) for c in concepts]
        if concepts and all(nos_of):
            nos = dict.fromkeys(f"said on {a.said.isoformat()}: {a.answer}"
                                for a in nos_of if a)
            said[q["id"]] = " / ".join(nos)
            asked.add(q["asked"])
            q = {**q, "state": "missing", "carriers": [], "near": [],
                 "verdict": None if q["necessity"] == "implicit" else "unsatisfied"}
        reqs.append(q)
    if not said:
        return r, {}
    # A match question names its requirement by `asked` (matching/questions.py), which
    # build keeps unique within a posting.
    questions = [x for x in r["questions"] if x.get("requirement") not in asked]
    return {**r, "requirements": reqs, "questions": questions}, said


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
    from ..ontology import C, K

    return (K + curie[2:] if curie.startswith("k:") else C + curie[2:] if curie.startswith("c:")
            else curie)


def _confirmed(q):
    return [c for c in q["carriers"] if c["evidence"] == "confirmed"]


def _texts(queries, q):
    """The words of the confirmed bullets behind a satisfied row: what the flag reads."""
    concepts = [_iri(c) for c in q["concepts"]]
    if not concepts:
        return []
    return [t for c in _confirmed(q) for t in queries.confirmed_texts(_iri(c["project"]), concepts)]


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


def _questions(r, ask, settled=()):
    """The match's questions in the analyst's order, the unmet required ones first - the
    order the old gaps.md draft gave them, without its list markers or slots. `ask` writes
    one question as a list item. Each comes with the requirement it is about, or None (a
    missing metric is a bullet's); `settled` names the requirements an absence answered,
    which are asked nothing.

    Returns:
        [(question, "k:req_..." or None)].
    """
    by_asked = {q["asked"]: q["id"] for q in r["requirements"]}
    unmet = [(1, f"**unsatisfied** {q['asked']}: required, and nothing in the record "
                 f"carries it - is there work that shows it?", q["id"])
             for q in r["requirements"]
             if q["necessity"] == "required" and q["verdict"] == "unsatisfied"
             and q["id"] not in settled]
    asked = [(ORDER[q["kind"]], ask(q).removeprefix("- "), by_asked.get(q.get("requirement")))
             for q in r["questions"]]
    return [(line, req) for _, line, req in sorted(unmet + asked, key=lambda x: x[0])]
