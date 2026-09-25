# Export from a match Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `jsk kb export --urs --from-match <posting.ttl>` writes a draft resume.json whose projects,
bullets, bullet order and skill order are computed from the match, and prints the gaps it could not
close.

**Architecture:** a new pure module `src/jsk/graph/select.py` turns the store plus a posting into a
`Selection` (projects, ordered bullets, ordered skills, gaps) using `queries.py` unchanged.
`export.urs()` takes an optional `selection=` and `view()` writes its order; `kbcli.cmd_export`
parses the flags and prints `GAP` lines.

**Tech Stack:** Python 3, pyoxigraph (SPARQL over the store), unittest.

**Spec:** `docs/superpowers/specs/2026-09-25-export-from-match-design.md`

## Global Constraints

- `jsk match` output and `tests/test_graph_match*.py` do not change.
- `src/jsk/urs/*` (including the uncommitted `resolve.py`) and the gates do not change.
- Evidence is `Q.evidence(...) == "confirmed"`; the view keeps `provenance_floor: confirmed`.
- At most 8 projects; `--cover` default `match.COVER` (3).
- Gap kinds, in sort order: `tag-only`, `unconfirmed`, `uncovered`, `unresolved`.
- Gaps never change the exit code.
- Same inputs, byte-identical JSON.
- Commit only the files a task names; never `git add -A` (the working tree holds the user's changes).

## Review Focus

1. A posting whose every requirement is missing or unresolved: the export still writes a record
   with no projects' bullets chosen by score, and prints only gaps - test in Task 1
   (`test_nothing_carried_selects_nothing_and_says_why`).
2. A requirement two projects carry, one with evidence and one by tag only: no `tag-only` line -
   test in Task 1 (`test_k8s_carried_with_evidence_is_no_gap`).
3. `--select` naming an id already selected: no duplicate project or bullet - Task 1.
4. `--from-match` with a posting from a different workspace than `--root`: usage error, not a
   silent match against the wrong career - Task 3.
5. `--cover 0` / `--today notadate`: usage error (exit 2), as in `jsk match` - Task 3.

---

## Fixture

Every test copies `tests/claims_fixtures/career` into a temp workspace and writes this posting to
`applications/contoso-select/posting.ttl` (constant `POSTING` in `tests/test_select.py`):

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

k:post_contoso_select j:company "Contoso" ; j:title "Platform Engineer" ;
    j:captured "2026-09-20"^^xsd:date ; j:advert "posting.md" .

k:req_sel_k8s j:posting k:post_contoso_select ; j:asked "K8s" ;
    j:necessity j:required ; j:quote "Production K8s required." .
k:req_sel_kafka j:posting k:post_contoso_select ; j:asked "Kafka" ;
    j:necessity j:required ; j:quote "Kafka is required." .
k:req_sel_python j:posting k:post_contoso_select ; j:asked "Python" ;
    j:necessity j:required ; j:quote "Python is required." .
k:req_sel_rust j:posting k:post_contoso_select ; j:asked "Rust" ;
    j:necessity j:required ; j:quote "Rust is required." .
k:req_sel_sqlserver j:posting k:post_contoso_select ; j:asked "SQL Server" ;
    j:necessity j:required ; j:quote "SQL Server is required." .
k:req_sel_team j:posting k:post_contoso_select ; j:asked "Team leadership" ;
    j:necessity j:preferred ; j:quote "Team leadership is a plus." .
k:req_sel_terraform j:posting k:post_contoso_select ; j:asked "Terraform" ;
    j:necessity j:required ; j:quote "Terraform is required." .
k:req_sel_widgets j:posting k:post_contoso_select ; j:asked "Quantum widgets" ;
    j:necessity j:required ; j:quote "Quantum widgets are required." .
```

Worked by hand from `tests/claims_fixtures/career/kb.ttl`:

| Requirement | Evidenced carriers | Gap |
|---|---|---|
| K8s | prj_events (ach_events_latency shows c:aks) | - (prj_data only tags it) |
| Kafka | prj_events, prj_identity | - |
| Python | none (ach_data_ingestion shows c:fastapi, inferred) | `unconfirmed` |
| Rust | none | `uncovered`, nothing carries it |
| SQL Server | none (prj_portal tags it) | `tag-only` |
| Team leadership | prj_events | - |
| Terraform | prj_events (prj_data only tags it) | - |
| Quantum widgets | - | `unresolved` |

Projects: `prj_events` (cover), `prj_identity` (carries Kafka). Not `prj_portal` (strength 3,
carries nothing with evidence), not `prj_data`, not `prj_game`.
Bullets: prj_events `[ach_events_latency (3+3+1), ach_events_terraform (3), ach_events_team (1+1)]`;
prj_identity `[ach_identity_events (3), ach_identity_sso (cites only, 1)]`.
Skills: `[skill_kubernetes (alias K8s), skill_dotnet]` - the reverse of the default order.

---

### Task 1: `select.py`

**Files:**
- Create: `src/jsk/graph/select.py`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: `queries.match`, `rank`, `cover`, `evidence`, `labels`, `PRE`; `scoring.WEIGHTS`;
  `shapes.curie`; `ontology.K`, `class_of`, `norm`.
- Produces:
  - `Gap(kind: str, requirement: str, necessity: str, detail: str, iri: str)`, with `line()` giving
    the report text `GAP   <kind padded to 11> <asked> (<necessity>): <detail>`.
  - `Selection(projects: list[iri], bullets: dict[iri, list[iri]], skills: list[iri],
    gaps: list[Gap])`.
  - `select(store, post, today, budget, extra=()) -> Selection`; `extra` is iris, in order.
  - `band(position) -> (cap, floor)`; `pick(candidates, assigned, cap, floor) -> list[iri]` where
    `candidates` is `[(bullet, score, reqs_shown: set)]` already in order.

- [ ] **Step 1: Write the failing tests** — `tests/test_select.py`:

```python
"""select.py: what a resume for one posting selects, worked by hand in the plan
(docs/superpowers/plans/2026-09-25-export-from-match.md, "Fixture")."""
import datetime
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from jsk.graph import select as SEL
from jsk.graph import store as S

FIXTURES = Path(__file__).parent / "claims_fixtures"
TODAY = datetime.date(2026, 9, 25)
POST = O.K + "post_contoso_select"
POSTING = """<the Fixture posting above, verbatim>"""


def workspace(test, posting=POSTING):
    root = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, root, True)
    shutil.copytree(FIXTURES / "career", os.path.join(root, "career"))
    app = os.path.join(root, "applications", "contoso-select")
    os.makedirs(app)
    Path(app, "posting.ttl").write_bytes(posting.encode())
    Path(app, "posting.md").write_bytes(b"# Contoso\n")
    return root


def ids(iris):
    return [i[len(O.K):] for i in iris]


class Selected(unittest.TestCase):
    def setUp(self):
        self.store = S.load(workspace(self))
        self.sel = SEL.select(self.store, POST, TODAY, 3)

    def test_projects_are_the_cover_then_what_carries_evidence(self):
        self.assertEqual(ids(self.sel.projects), ["prj_events", "prj_identity"])

    def test_a_strong_project_carrying_nothing_is_not_selected(self):
        self.assertNotIn(O.K + "prj_portal", self.sel.projects)

    def test_bullets_by_score_then_rank(self):
        self.assertEqual(ids(self.sel.bullets[O.K + "prj_events"]),
                         ["ach_events_latency", "ach_events_terraform", "ach_events_team"])
        self.assertEqual(ids(self.sel.bullets[O.K + "prj_identity"]),
                         ["ach_identity_events", "ach_identity_sso"])

    def test_skills_the_posting_asks_for_first(self):
        self.assertEqual(ids(self.sel.skills), ["skill_kubernetes", "skill_dotnet"])

    def test_gaps(self):
        self.assertEqual([(g.kind, g.requirement) for g in self.sel.gaps],
                         [("tag-only", "SQL Server"), ("unconfirmed", "Python"),
                          ("uncovered", "Rust"), ("unresolved", "Quantum widgets")])
        lines = [g.line() for g in self.sel.gaps]
        self.assertIn("k:prj_portal tags c:sql-server", lines[0])
        self.assertIn("k:ach_data_ingestion", lines[1])
        self.assertIn("inferred", lines[1])
        self.assertIn("nothing carries it", lines[2])
        self.assertTrue(lines[0].startswith("GAP   tag-only    SQL Server (required): "))

    def test_k8s_carried_with_evidence_is_no_gap(self):
        self.assertNotIn("K8s", [g.requirement for g in self.sel.gaps])
        self.assertNotIn("Terraform", [g.requirement for g in self.sel.gaps])

    def test_deterministic(self):
        again = SEL.select(S.load(self.store.root), POST, TODAY, 3)
        self.assertEqual(again, self.sel)


class Extra(unittest.TestCase):
    def setUp(self):
        self.store = S.load(workspace(self))

    def test_a_project_added_brings_its_first_bullet(self):
        sel = SEL.select(self.store, POST, TODAY, 3, extra=[O.K + "prj_game"])
        self.assertEqual(ids(sel.projects)[-1], "prj_game")
        self.assertEqual(ids(sel.bullets[O.K + "prj_game"]), ["ach_game_players"])

    def test_a_bullet_added_brings_exactly_itself(self):
        sel = SEL.select(self.store, POST, TODAY, 3, extra=[O.K + "ach_portal_frontend"])
        self.assertEqual(ids(sel.bullets[O.K + "prj_portal"]), ["ach_portal_frontend"])

    def test_an_id_already_selected_is_not_duplicated(self):
        sel = SEL.select(self.store, POST, TODAY, 3,
                         extra=[O.K + "prj_events", O.K + "ach_events_team"])
        self.assertEqual(ids(sel.projects), ["prj_events", "prj_identity"])
        self.assertEqual(len(sel.bullets[O.K + "prj_events"]), 3)


class Nothing(unittest.TestCase):
    def test_nothing_carried_selects_nothing_and_says_why(self):
        posting = POSTING.split("k:req_sel_k8s")[0] + (
            'k:req_sel_rust j:posting k:post_contoso_select ; j:asked "Rust" ;\n'
            '    j:necessity j:required ; j:quote "Rust is required." .\n')
        sel = SEL.select(S.load(workspace(self, posting)), POST, TODAY, 3)
        self.assertEqual(sel.projects, [])
        self.assertEqual([g.kind for g in sel.gaps], ["uncovered"])


class Pick(unittest.TestCase):
    def test_bands(self):
        self.assertEqual([SEL.band(n) for n in (1, 2, 3, 5, 6, 8, 9)],
                         [(5, 3), (5, 3), (2, 1), (2, 1), (1, 1), (1, 1), (1, 1)])

    def test_the_cover_beats_the_band(self):
        cands = [("a", 3, {"r1"}), ("b", 3, {"r2"}), ("c", 1, set())]
        self.assertEqual(SEL.pick(cands, {"r1", "r2"}, 1, 1), ["a", "b"])

    def test_greedy_takes_the_bullet_showing_most(self):
        cands = [("a", 3, {"r1"}), ("b", 6, {"r1", "r2"})]
        self.assertEqual(SEL.pick(sorted(cands, key=lambda c: -c[1]), {"r1", "r2"}, 1, 1), ["b"])

    def test_fill_to_the_floor_with_non_scoring(self):
        cands = [("a", 3, {"r1"}), ("b", 0, set()), ("c", 0, set()), ("d", 0, set())]
        self.assertEqual(SEL.pick(cands, set(), 5, 3), ["a", "b", "c"])

    def test_cap_counts_the_cover(self):
        cands = [("a", 3, {"r1"}), ("b", 3, {"r2"}), ("c", 3, {"r3"})]
        self.assertEqual(SEL.pick(cands, {"r1", "r2"}, 2, 1), ["a", "b"])
```

- [ ] **Step 2: Run to verify they fail** — `python -m pytest tests/test_select.py -q`.
  Expected: `ModuleNotFoundError: jsk.graph.select`.

- [ ] **Step 3: Implement `src/jsk/graph/select.py`:**

```python
"""What a resume for one posting selects, decided from the match: the projects, the bullets
under each and their order, the order of the skills, and the gaps the selection cannot close.

docs/superpowers/specs/2026-09-25-export-from-match-design.md. These are the rules the resume
author applied by hand from `jsk match` and a table in its prose; here the same posting always
selects the same evidence, and the author is left the words.

A tag is not evidence, and here that decides the cover too: a project carries a requirement
only when a live, confirmed bullet shows it. `jsk match` still reports tags - they are leads
for the conversation - so the filtering happens here, on a copy of its matches.
"""
import copy
from dataclasses import dataclass

from . import ontology as O
from . import queries as Q
from .scoring import WEIGHTS
from .shapes import curie

MOST = 8
KINDS = ("tag-only", "unconfirmed", "uncovered", "unresolved")
NEEDS = ("required", "preferred")


@dataclass(frozen=True)
class Gap:
    kind: str
    requirement: str             # the label as the posting wrote it
    necessity: str
    detail: str
    iri: str                     # the requirement, for the order

    def line(self):
        return f"GAP   {self.kind:<11} {self.requirement} ({self.necessity}): {self.detail}"


@dataclass
class Selection:
    projects: list               # iris, in position order, additions last
    bullets: dict                # project iri -> bullet iris, in render order
    skills: list                 # skill iris, the posting's first
    gaps: list                   # Gap, sorted


def band(position):
    """(cap, floor) for a project at this 1-based position among the selected."""
    if position <= 2:
        return 5, 3
    if position <= 5:
        return 2, 1
    return 1, 1


def pick(candidates, assigned, cap, floor):
    """The bullets a project shows, from `candidates` - (bullet, score, requirements shown),
    best first. First, greedily, until every requirement in `assigned` is shown (the cover
    beats the cap); then scoring bullets up to `cap`; then any, up to `floor`. Returned in
    the candidates' order."""
    chosen, unshown = set(), set(assigned)
    while unshown:
        best = None
        for i, (b, _, reqs) in enumerate(candidates):
            gain = len(reqs & unshown)
            if b not in chosen and gain and (best is None or gain > best[0]):
                best = (gain, i)
        if best is None:
            break
        b, _, reqs = candidates[best[1]]
        chosen.add(b)
        unshown -= reqs
    for b, score, _ in candidates:
        if len(chosen) >= cap:
            break
        if score > 0:
            chosen.add(b)
    for b, _, _ in candidates:
        if len(chosen) >= floor:
            break
        chosen.add(b)
    return [b for b, _, _ in candidates if b in chosen]


def bullets(store):
    """{bullet: (project, rank, provenance local name)} for every live bullet."""
    rows = store.select(Q.PRE + """
        SELECT ?b ?p ?rank ?pv WHERE { ?b j:project ?p ; j:rank ?rank ; j:provenance ?pv .
                                       FILTER NOT EXISTS { ?b j:retired ?x } }""")
    return {r["b"].value: (r["p"].value, int(r["rank"].value), Q.local(r["pv"].value))
            for r in rows}


def shows(store):
    """{bullet: concepts it shows or counts as, without an implies edge}."""
    rows = store.select(Q.PRE + """
        SELECT ?b ?to WHERE { ?b j:project ?p ; j:shows ?m .
          GRAPH j:derived { ?x j:from ?m ; j:to ?to ; j:implied false } }""")
    out = {}
    for r in rows:
        out.setdefault(r["b"].value, set()).add(r["to"].value)
    return out


def cites_current(store):
    """Bullets citing a metric that has a current version - the ones export keeps."""
    rows = store.select(Q.PRE + """
        SELECT DISTINCT ?b WHERE { ?b j:project ?p ; j:cites ?m . ?v j:of ?m .
                                   FILTER NOT EXISTS { ?v j:validUntil ?u } }""")
    return {r["b"].value for r in rows}


def evidenced(store, matches, held, shown):
    """(matches with carriers cut to confirmed evidence, the gaps the cut left)."""
    kept, gaps = {}, []
    for iri, m in matches.items():
        req = m.requirement
        if req.necessity not in NEEDS:
            kept[iri] = m
            continue
        if m.state in ("ambiguous", "candidate"):
            detail = (f"ambiguous - {' or '.join(curie(c) for c in m.resolution.concepts)}"
                      if m.state == "ambiguous" else "no concept has this label")
            gaps.append(Gap("unresolved", req.asked, req.necessity, detail, iri))
            kept[iri] = m
            continue
        if m.state != "matched":
            kept[iri] = m
            continue
        n = copy.copy(m)
        n.carriers, tags, loose = {}, [], []
        for proj, (h, hops, imp) in sorted(m.carriers.items()):
            level = Q.evidence(store, proj, m.concept)
            if level == "confirmed":
                n.carriers[proj] = (h, hops, imp)
            elif level == "unconfirmed":
                loose += sorted(b for b, (p, _, pv) in held.items() if p == proj
                                and pv not in ("confirmed", "disputed")
                                and m.concept in shown.get(b, ()))
            else:
                tags.append(f"{curie(proj)} tags {curie(h)}")
        if not n.carriers:
            n.state = "missing"
            if tags:
                gaps.append(Gap("tag-only", req.asked, req.necessity,
                                "; ".join(tags) + "; no bullet shows it", iri))
            if loose:
                named = ", ".join(f"{curie(b)} ({held[b][2]})" for b in loose)
                gaps.append(Gap("unconfirmed", req.asked, req.necessity,
                                f"{named} shows it - confirm it" if len(loose) == 1
                                else f"{named} show it - confirm one", iri))
        kept[iri] = n
    return kept, gaps


def skill_order(store, matches):
    """Every live skill: those matching a required requirement, then a preferred one, then
    the rest; within each by the first requirement matched, then export's own order."""
    from .export import Career, skills
    from . import record as R

    career = Career(store.graph(R.KB))
    names = {}
    for label, concepts in Q.labels(store).items():
        for c in concepts:
            names.setdefault(c, set()).add(label)
    wanted = []                  # (group, index, normalised labels)
    for i, m in enumerate(matches.values()):
        need = m.requirement.necessity
        if need not in NEEDS:
            continue
        labels = {O.norm(m.requirement.asked)}
        if m.concept:
            labels |= names.get(m.concept, set())
        wanted.append((NEEDS.index(need), i, labels))
    order = []
    for at, item in enumerate(skills(career)):
        iri = O.K + item["id"]
        own = {O.norm(item["name"])} | {O.norm(a) for a in item.get("aliases", [])}
        key = min(((g, i) for g, i, labels in wanted if own & labels), default=(2, 0))
        order.append((key, at, iri))
    return [iri for *_, iri in sorted(order)]


def select(store, post, today, budget, extra=()):
    matches = Q.match(store, post)
    held, shown, citing = bullets(store), shows(store), cites_current(store)
    kept, gaps = evidenced(store, matches, held, shown)
    ranked = Q.rank(store, post, kept, today)
    cover = Q.cover(kept, budget, ranked)[0] or []
    position = {r.project: i for i, r in enumerate(ranked)}
    carrying = {p for m in kept.values() if m.requirement.necessity in NEEDS
                for p in m.carriers}
    projects = list(cover)
    for row in ranked:
        if len(projects) >= max(MOST, len(cover)):
            break
        if row.project in carrying and row.project not in projects:
            projects.append(row.project)
    projects.sort(key=position.get)

    # What each bullet is worth: the requirements it shows, then a number it can stand on.
    reqs = [(iri, m) for iri, m in kept.items()
            if m.requirement.necessity in NEEDS and m.concept]

    def candidates(proj):
        rows = []
        for b, (p, rank, pv) in held.items():
            if p != proj or pv != "confirmed":
                continue
            mine = {iri for iri, m in reqs if m.concept in shown.get(b, ())}
            score = sum(WEIGHTS[kept[iri].requirement.necessity] for iri in mine)
            score += 1 if b in citing else 0
            rows.append((b, score, mine, rank))
        rows.sort(key=lambda r: (-r[1], r[3], r[0]))
        return [(b, s, mine) for b, s, mine, _ in rows]

    owner = {}                   # a required requirement in the cover -> its cover project
    for iri, m in kept.items():
        if m.requirement.necessity == "required":
            mine = [p for p in cover if p in m.carriers]
            if mine:
                owner[iri] = min(mine, key=position.get)
    chosen = {}
    for n, proj in enumerate(projects, 1):
        cap, floor = band(n)
        chosen[proj] = pick(candidates(proj), {i for i, p in owner.items() if p == proj},
                            cap, floor)

    for iri in extra:
        cls = O.class_of(iri)
        if cls == "Project" and iri not in chosen:
            first = sorted((rank, b) for b, (p, rank, pv) in held.items()
                           if p == iri and pv == "confirmed")
            projects.append(iri)
            chosen[iri] = [b for _, b in first[:1]]
        elif cls == "Achievement" and iri in held:
            proj = held[iri][0]
            if proj not in chosen:
                projects.append(proj)
                chosen[proj] = []
            if iri not in chosen[proj]:
                chosen[proj].append(iri)

    carried = {p for p in projects for m in kept.values() if p in m.carriers}
    said = {g.iri for g in gaps}
    for iri, m in kept.items():
        req = m.requirement
        if req.necessity != "required" or iri in said:
            continue
        if not any(p in m.carriers for p in projects):
            detail = ("nothing carries it" if not m.carriers else
                      "its carriers were not selected: "
                      + ", ".join(curie(p) for p in sorted(m.carriers)))
            if m.near and not m.carriers:
                detail = "only near - " + "; ".join(f"{curie(p)} {why}"
                                                    for p, why in sorted(m.near.items()))
            gaps.append(Gap("uncovered", req.asked, req.necessity, detail, iri))
    del carried
    gaps.sort(key=lambda g: (NEEDS.index(g.necessity), KINDS.index(g.kind), g.iri))
    return Selection(projects, chosen, skill_order(store, kept), gaps)
```

- [ ] **Step 4: Run the tests** — `python -m pytest tests/test_select.py -q`. Expected: all pass.
  Where a hand-worked expectation in the Fixture table disagrees with the code, find out which is
  wrong against the spec before changing either.

- [ ] **Step 5: Commit** — `git add src/jsk/graph/select.py tests/test_select.py` and commit
  `feat: select.py - projects, bullets, skills and gaps from a match`.

### Task 2: `export.urs(selection=)`

**Files:**
- Modify: `src/jsk/graph/export.py` (`urs`, `view`)
- Test: `tests/test_select.py` (class `Exported`)

**Interfaces:**
- Consumes: `Selection` from Task 1.
- Produces: `urs(store, select=None, today=None, selection=None) -> dict`. With a selection the
  experience is its projects and bullets, `select` supplies roles only (and is validated as
  today), and the view carries `include` achievements in the selection's order and `skills`.

- [ ] **Step 1: Failing tests** — add to `tests/test_select.py`:

```python
from jsk.gates import validate_urs
from jsk.graph import export


class Exported(unittest.TestCase):
    def setUp(self):
        self.store = S.load(workspace(self))
        self.doc = export.urs(self.store, today=TODAY,
                              selection=SEL.select(self.store, POST, TODAY, 3))
        self.view = self.doc["views"][0]

    def test_only_the_selected_projects(self):
        self.assertEqual(sorted(p["id"] for p in self.doc["projects"]),
                         ["prj_events", "prj_identity"])

    def test_the_view_orders_bullets_and_skills(self):
        inc = {i["ref"]: i.get("achievements") for i in self.view["include"]}
        self.assertEqual(inc["prj_events"],
                         ["ach_events_latency", "ach_events_terraform", "ach_events_team"])
        self.assertEqual(self.view["skills"], ["skill_kubernetes", "skill_dotnet"])

    def test_it_validates(self):
        self.assertEqual(list(validate_urs.check_doc(self.doc).fails), [])

    def test_byte_identical(self):
        again = export.urs(S.load(self.store.root), today=TODAY,
                           selection=SEL.select(S.load(self.store.root), POST, TODAY, 3))
        self.assertEqual(json.dumps(again), json.dumps(self.doc))
```

(add `import json` to the imports.)

- [ ] **Step 2: Run** — expect `TypeError: urs() got an unexpected keyword argument 'selection'`.

- [ ] **Step 3: Implement** — in `urs`, change the signature to
  `def urs(store, select=None, today=None, selection=None):` and replace the block from
  `projects = [p for p in career.live("Project")]` through the `else: roles = set()` with:

```python
    projects = [p for p in career.live("Project")]
    if selection is not None:
        # The match chose: its projects and its bullets, in its order. `select` adds roles.
        projects = list(selection.projects)
        bullets_of = {p: list(bs) for p, bs in selection.bullets.items()}
        roles = picked[2] if picked is not None else set()
    elif picked is not None:
        want, bullets, roles = picked
        with_bullets = {career.get(a, "project") for a in bullets}
        projects = [p for p in projects if p in want or p in with_bullets]
        for p in projects:
            mine = [a for a in bullets_of.get(p, []) if a in bullets]
            if mine:                                   # a bullet named narrows its project
                bullets_of[p] = mine
    else:
        roles = set()
```

  and the `orgs |= ...` line guard becomes `if picked is None and selection is None:`. Change the
  last line to `doc["views"] = [view(career, doc, engagements, narrative, selection)]` and `view`:

```python
def view(career, doc, engagements, narrative, selection=None):
    ...
    out["include"] = include
    if selection is not None:
        out["skills"] = [local(s) for s in selection.skills]
    return out
```

- [ ] **Step 4: Run** `python -m pytest tests/test_select.py tests/test_graph_export.py -q`. All pass.
- [ ] **Step 5: Commit** `src/jsk/graph/export.py tests/test_select.py` —
  `feat: export takes a selection - its bullets and skills in order`.

### Task 3: `jsk kb export --from-match`

**Files:**
- Modify: `src/jsk/graph/kbcli.py` (`cmd_export` and its docstring; the verb list line 15)
- Test: `tests/test_select.py` (class `Command`)

**Interfaces:**
- Consumes: `select.select`, `export.urs(selection=)`, `export.chosen`, `export.Career`,
  `match.workspace_of`, `match.blocks`, `match.COVER`.

- [ ] **Step 1: Failing tests:**

```python
import contextlib
import io

from jsk import cli


class Command(unittest.TestCase):
    def setUp(self):
        self.root = workspace(self)
        self.posting = os.path.join(self.root, "applications", "contoso-select", "posting.ttl")

    def kb(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue(), err.getvalue()

    def test_from_match_prints_the_record_and_the_gaps(self):
        code, out, err = self.kb("export", "--urs", "--from-match", self.posting,
                                 "--today", "2026-09-25")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["views"][0]["skills"][0], "skill_kubernetes")
        self.assertIn("GAP   tag-only    SQL Server (required)", err)

    def test_with_out_the_gaps_go_to_stdout(self):
        dest = os.path.join(self.root, "applications", "contoso-select", "resume.json")
        code, out, _ = self.kb("export", "--urs", "--from-match", self.posting, "--out", dest)
        self.assertEqual(code, 0)
        self.assertIn("GAP   uncovered   Rust (required): nothing carries it", out)
        self.assertTrue(os.path.isfile(dest))

    def test_a_posting_outside_applications_is_a_usage_error(self):
        stray = os.path.join(self.root, "posting.ttl")
        shutil.copy(self.posting, stray)
        self.assertEqual(self.kb("export", "--urs", "--from-match", stray)[0], 2)

    def test_a_posting_from_another_workspace_is_a_usage_error(self):
        other = workspace(self)
        theirs = os.path.join(other, "applications", "contoso-select", "posting.ttl")
        self.assertEqual(self.kb("export", "--urs", "--from-match", theirs)[0], 2)

    def test_cover_and_today_need_from_match(self):
        self.assertEqual(self.kb("export", "--urs", "--cover", "2")[0], 2)
        self.assertEqual(self.kb("export", "--urs", "--today", "2026-09-25")[0], 2)

    def test_bad_cover_and_today(self):
        for flag, value in (("--cover", "0"), ("--cover", "x"), ("--today", "soon")):
            self.assertEqual(self.kb("export", "--urs", "--from-match", self.posting,
                                     flag, value)[0], 2)

    def test_a_broken_posting_refuses(self):
        Path(self.posting).write_bytes(b"this is not turtle")
        self.assertEqual(self.kb("export", "--urs", "--from-match", self.posting)[0], 1)
```

- [ ] **Step 2: Run** — expect failures (`--from-match` is an unknown argument: usage, exit 2
  where 0 is expected).

- [ ] **Step 3: Implement** in `cmd_export`, after `fmt = take(args, "--urs")`:

```python
    posting = take(args, "--from-match", value=True)
    cover_text = take(args, "--cover", value=True)
    today_text = take(args, "--today", value=True)
```

  after the `if args or not fmt:` usage check:

```python
    if (cover_text or today_text) and not posting:
        return usage("--cover and --today go with --from-match")
    today = datetime.date.today()
    budget = COVER
    try:
        if today_text:
            today = datetime.date.fromisoformat(today_text)
        if cover_text:
            budget = int(cover_text)
    except ValueError:
        return usage("--cover takes a whole number and --today a YYYY-MM-DD date")
    if budget < 1:
        return usage("--cover takes a whole number of at least 1")
    if posting:
        home = workspace_of(posting)
        if (home is None or not os.path.isfile(posting)
                or os.path.normcase(os.path.abspath(home)) != os.path.normcase(os.path.abspath(root))):
            return usage(f"{posting}: not a posting.ttl inside this workspace's "
                         "applications/<dir>/ folder")
```

  (imports at the top of the function: `from .match import COVER, blocks, workspace_of`.) The
  blocking filter becomes:

```python
    here = (S.file_name(os.path.dirname(os.path.abspath(posting)), store.root) + "/"
            if posting else None)
    blocking = [f for f in store.fails() if f.rule != "log-sync"
                and (not f.file.startswith("applications/") or (here and blocks(f, here)))]
```

  and the `urs` call:

```python
    selection = None
    try:
        if posting:
            from . import select as SEL
            chosen(Career(store.graph(R.KB)), select)      # refuses a bad --select first
            posts = [iri for iri in store.homes if O.class_of(iri) == "Posting"
                     and store.file_of(iri) == S.file_name(posting, store.root)]
            if len(posts) != 1:
                return refuse([f"{posting} holds no posting"], "`jsk match` it first")
            extra = [O.K + t.removeprefix("k:") for t in select or []]
            selection = SEL.select(store, posts[0], today, budget, extra)
        doc = urs(store, select, today=today, selection=selection)
    except ExportError as err:
        return refuse([str(err)], err.fix)
```

  (`from .export import Career, ExportError, chosen, gate_failures, urs`; `from . import ontology
  as O`.) Replace the later `today=datetime.date.today()` in `gate_failures` with `today=today`.
  After the `NOTE` loop:

```python
    for gap in selection.gaps if selection else ():
        print(gap.line(), file=report)
```

  Docstring and verb list: add `[--from-match <posting.ttl> [--cover N] [--today YYYY-MM-DD]]`
  and one paragraph: "--from-match chooses the experience from `jsk match`: the projects that
  carry the posting with confirmed evidence, their bullets by what they show, the skills the
  posting asks for first. What it cannot close prints as GAP lines - tag-only, unconfirmed,
  uncovered, unresolved - for gaps.md. --select adds to it."

- [ ] **Step 4: Run** `python -m pytest tests/test_select.py tests/test_graph_export.py tests/test_graph_kbcli.py -q`.
- [ ] **Step 5: Commit** `src/jsk/graph/kbcli.py tests/test_select.py` —
  `feat: jsk kb export --from-match`.

### Task 4: the author, the docs, the budget

**Files:**
- Modify: `plugins/jsk/agents/jsk-resume-author.md`, `docs/SCRIPTS.md` (export section),
  `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md` (P8 note), `tests/test_budget.py`
  (author ceiling), and `jsk-eval-workspace/skill-snapshot` is NOT touched.

- [ ] **Step 1:** In `jsk-resume-author.md`, replace the `jsk kb export --urs --select ...` block
  with `jsk kb export --urs --from-match applications/<stem>/posting.ttl --out
  applications/<stem>/resume.json`; say it chooses the projects, bullets, their order and the skill
  order, and prints `GAP` lines, each copied into `gaps.md`'s "Where this falls short". Keep
  `--select` for a project kept for chronology. Delete the "Allocating the pages" table and the
  "order `include` ... list the view's `skills` ids" instruction; keep "Chronology governs order"
  as the reason a reorder is stated. Keep the three guardrails verbatim.
- [ ] **Step 2:** Run `python -m pytest tests/test_budget.py tests/test_plugin_surface.py -q`;
  record the author's new token count, lower the ceiling it asserts under (line ~108) to the next
  hundred above the measured total, with a comment giving old and new counts.
- [ ] **Step 3:** `docs/SCRIPTS.md`: one paragraph and an example for `--from-match` beside
  `--select`. Roadmap P8: append "*Extended (2026-09-25): `--from-match`* -" and the spec path.
- [ ] **Step 4:** full suite, `python -m pytest -q`; expect only failures already present before
  this work (check against `git stash`-free baseline: run the suite on `ece7feb` first if any fail).
- [ ] **Step 5: Commit** the four files — `docs: the author drafts from the match`.
