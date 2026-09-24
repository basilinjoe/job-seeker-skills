# Vocabulary and matching (P2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `jsk match <posting.ttl>` joins a posting with the career through a shipped vocabulary, puts each requirement in a bucket, ranks the projects, finds a cover and derives the questions. It works over graph workspaces only.

**Architecture:** The ontology gains `unlabel` and `unlink`, which the loader applies to the shipped vocabulary in memory. `shapes.py` and `rules.py` gain the five new rules. `queries.py` ports the graph simulation's queries over P1's closure, and `match.py` is the command and its formatter, wired into `cli.py` like `jsk index`.

**Tech Stack:** Python 3.10+, pyoxigraph 0.5.x, unittest under pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-24-graph-match-design.md`. P1 (`docs/superpowers/plans/2026-09-24-graph-core.md`) is built on `feat/vocabulary-graph`.

**This code has been run.** It was built and run in a scratch copy of the branch on 2026-09-24 (Windows 11, Python 3.13.1, pyoxigraph 0.5.11): 526 passed, 2 skipped, and ruff is clean. Each task's end state was also rebuilt from the base commit and run on its own:

| After task | Result |
|---|---|
| 1 | 496 passed |
| 2 | 498 passed |
| 3 | 521 passed |
| 4 | 526 passed |

The matching mutation test found a real gap while this was drafted: no scenario in the simulation joins at two hops, so deleting the second hop went unnoticed. `test_two_hops_still_count` and the `no second hop` mutation close it.

Modified files are given as unified diffs against the branch's current code. Apply each with `git apply` from a file (the Write tool, not a heredoc: heredocs corrupt backslashes), or by hand. New files are given whole. If a step's result differs from the one stated, stop and report it; don't adjust the test to match.

## Global Constraints

- `jsk match` reads graph workspaces only: `career/kb.ttl` and `applications/<dir>/posting.ttl`. `jsk index --rank` and the analyst are unchanged.
- The shipped vocabulary holds `Technology` only, with no `implies`, `unlabel` or `unlink` (the `shipped-vocabulary` rule).
- Weights, recency and seniority come from `kbindex` (`WEIGHTS`, `recency_points`, `SENIORITY`), imported, never copied.
- The hop limit is P1's closure (0, 1 or 2 hops). No other code counts hops.
- Any FAIL in the workspace: `jsk match` prints the findings and exits 1. Otherwise it exits 0, gaps included; usage errors exit 2.
- No token ceiling in `tests/test_budget.py` moves. SKILL.md + mode-tailor + mode-ship must stay under 6,000 (measured 5,997 after this plan).
- Add a module to `preflight.GRAPH_MODULES` only in the task that creates it.
- Tests are `unittest.TestCase` classes run by pytest. Line length is 100.

## Review Focus

These are inputs the spec implies but its tests wouldn't reach unprompted. Each is pinned by a test in the owning task:

- **A label written messily** (`"  k8S  "`): it resolves as `K8s` would. Task 3, `test_a_label_as_messily_written_still_resolves`.
- **A person's own label that collides with a shipped one** (`"Apache Kafka"` on a capability): the label is asked about, not guessed and not crashed. An id (`Kafka` → `c:kafka`) still wins. Task 3, `test_a_persons_label_that_collides_is_asked_not_crashed`.
- **A posting with nothing required:** an empty cover, not an error. Task 3, `test_a_posting_with_nothing_required_has_an_empty_cover`.
- **An advert saved with CRLF, and a quote wrapped across its lines:** still verbatim, because whitespace is normalised. Task 2, `test_a_quote_wrapped_across_lines_of_a_crlf_advert_is_still_verbatim`.
- **`jsk match` given a relative path from inside the workspace:** the right workspace is found. Task 4, `test_a_relative_path_from_inside_the_workspace`.

## File structure

| File | Responsibility |
|---|---|
| `src/jsk/graph/ontology.py` | + `unlabel`, `unlink` on Concept |
| `src/jsk/graph/shapes.py` | + the `shipped-vocabulary` tier-1 rule |
| `src/jsk/graph/store.py` | + `graph_iri`, `narrow` (kb.ttl's removals, applied in memory), `Store.unmatched` |
| `src/jsk/graph/rules.py` | + `narrows-nothing`, `concept-reclassed`, `quote-verbatim`, `necessity-wording`; `concept-class` deduplicated |
| `src/jsk/graph/queries.py` | new: resolve, match, evidence, rank, cover, questions |
| `src/jsk/graph/match.py` | new: the `jsk match` command and its Markdown / JSON output |
| `src/jsk/data/vocabulary.ttl` | the shipped vocabulary, 63 technologies |
| `src/jsk/cli.py`, `src/jsk/preflight.py` | wiring |
| `tests/graph_fixtures/vocabulary.ttl` | P1's seed vocabulary, now test-only, so P1's answers don't move |
| `tests/match_fixtures/` | the graph simulation as Turtle: kb.ttl, 4 postings, a test-only vocabulary |
| `tests/test_graph_{vocabulary,match,match_mutations}.py` | new |
| `plugins/jsk/skills/jsk/SKILL.md`, `docs/SCRIPTS.md` | the `jsk match` row and section |

---

### Task 1: The shipped vocabulary, and narrowing it

**Files:**
- Modify: `src/jsk/graph/ontology.py`, `src/jsk/graph/shapes.py`, `src/jsk/graph/store.py`
- Replace: `src/jsk/data/vocabulary.ttl`
- Create: `tests/graph_fixtures/vocabulary.ttl` (P1's seed, moved), `tests/test_graph_vocabulary.py`
- Modify: `tests/test_graph_shapes.py`, `tests/test_graph_store.py`, `tests/test_graph_writer.py`

**Interfaces:**
- Consumes (P1): `store.load(root, vocabulary=…)`, `Store.parsed`, `Parsed.kind` and `Parsed.quads`, the ontology `Class`/`Pred`, and `shapes.tier1`'s `add(rule, sev, s, detail, fix)`.
- Produces:
  - `ontology`: the Concept predicates `unlabel` (STR, `*`) and `unlink` (Concept, `*`);
  - `store`: `graph_iri(name) -> str`, `NARROWS`, `narrow(store)`, and `Store.unmatched: list[Quad]` (the removals that matched nothing), which Task 2 consumes;
  - `shapes`: `"shipped-vocabulary"` in `TIER1`, and `shipped_vocabulary(add, s, preds)`;
  - tests: `test_graph_shapes.load(root)`, which loads against `root/vocabulary.ttl`. Tasks 2 and 3 use it.

- [ ] **Step 1: Move P1's seed vocabulary into the fixtures, and point P1's tests at it**

Copy the current `src/jsk/data/vocabulary.ttl` byte for byte to `tests/graph_fixtures/vocabulary.ttl`, which is the file below. P1's closure test counts its paths, so it must not see the shipped file grow.

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Vocabulary

c:azure a j:Technology ; j:label "Azure", "Microsoft Azure" .
c:azure-ai-foundry a j:Technology ; j:label "Azure AI Foundry" ; j:partOf c:azure .
c:bicep a j:Technology ; j:label "Bicep" ; j:partOf c:azure .
c:docker a j:Technology ; j:label "Docker" .
c:dotnet a j:Technology ; j:label ".NET", "dot net", "dotnet" .
c:kafka a j:Technology ; j:label "Apache Kafka", "Kafka" .
c:kubernetes a j:Technology ; j:label "Kubernetes", "k8s" .
c:python a j:Technology ; j:label "Python" .
c:sql-server a j:Technology ; j:label "MSSQL", "SQL Server" .
c:terraform a j:Technology ; j:label "Terraform" .
```

Apply to the P1 tests:

`tests/test_graph_shapes.py`:

```diff
diff --git a/tests/test_graph_shapes.py b/tests/test_graph_shapes.py
index 45193b0..c12b2ea 100644
--- a/tests/test_graph_shapes.py
+++ b/tests/test_graph_shapes.py
@@ -14,6 +14,13 @@ from pathlib import Path
 from jsk.graph import shapes, store
 
 FIXTURES = Path(__file__).parent / "graph_fixtures"
+
+
+def load(root):
+    """A workspace loaded against its own vocabulary.ttl, not the shipped one: the fixtures'
+    hand-worked answers must not move when the shipped vocabulary grows."""
+    return store.load(root, vocabulary=Path(root) / "vocabulary.ttl")
+
 KB = "career/kb.ttl"
 POSTING = "applications/acme-platform-engineer/posting.ttl"
 APPLICATION = "applications/acme-platform-engineer/application.ttl"
@@ -39,6 +46,9 @@ MUTATIONS = {
                        "k:prj_intranet_refresh", "add j:reason"),
     "comment": (KB, "# == Metrics", "# remember to ask about this\n# == Metrics", "",
                 "j:note"),
+    "shipped-vocabulary": ("vocabulary.ttl", 'c:docker a j:Technology ; j:label "Docker" .',
+                           'c:docker a j:Capability ; j:label "Docker" .', "c:docker",
+                           "move it into a person's kb.ttl"),
 }
 
 
@@ -58,7 +68,7 @@ def mutated(mutation):
         text = text.replace(old, new)
     path.write_text(text, encoding="utf-8", newline="\n")
     try:
-        return store.load(tmp), text
+        return load(tmp), text
     finally:
         shutil.rmtree(tmp)
 
@@ -83,7 +93,7 @@ def assert_fires(case, rule, mutation):
 
 class TheFixtureIsClean(unittest.TestCase):
     def test_no_findings(self):
-        s = store.load(FIXTURES)
+        s = load(FIXTURES)
         self.assertEqual([f.text() for f in s.findings], [])
 
 
```

`tests/test_graph_store.py`:

```diff
diff --git a/tests/test_graph_store.py b/tests/test_graph_store.py
index df7d26c..3853491 100644
--- a/tests/test_graph_store.py
+++ b/tests/test_graph_store.py
@@ -10,6 +10,8 @@ import unittest
 from pathlib import Path
 
 from jsk.graph import ontology as O
+from test_graph_shapes import load
+
 from jsk.graph import store
 
 FIXTURES = Path(__file__).parent / "graph_fixtures"
@@ -27,7 +29,7 @@ def paths(s, hops=None):
 class Loading(unittest.TestCase):
     @classmethod
     def setUpClass(cls):
-        cls.s = store.load(FIXTURES)
+        cls.s = load(FIXTURES)
 
     def test_every_file_is_its_own_graph(self):
         self.assertEqual(sorted(self.s.parsed), [
@@ -102,7 +104,7 @@ class Discovery(unittest.TestCase):
             shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
             apps = Path(tmp) / "applications"
             (apps / "acme-platform-engineer").rename(apps / "Acme Platform é")
-            s = store.load(tmp)
+            s = load(tmp)
             self.assertEqual([f.text() for f in s.findings], [])
             self.assertEqual(s.file_of(O.K + "app_acme_platform_engineer"),
                              "applications/Acme Platform é/application.ttl")
@@ -111,7 +113,7 @@ class Discovery(unittest.TestCase):
         with tempfile.TemporaryDirectory() as tmp:
             root = Path(tmp) / "jobs [2026]"
             shutil.copytree(FIXTURES, root)
-            s = store.load(root)
+            s = load(root)
             self.assertIn("applications/acme-platform-engineer/posting.ttl", s.parsed)
             self.assertEqual([f.text() for f in s.findings], [])
 
@@ -127,7 +129,7 @@ class Discovery(unittest.TestCase):
         """As parsed, not read back out of Oxigraph, which stores numbers by value:
         "8.40" would come back as 8.4 and the rewrite would change the person's file."""
         from jsk.graph import writer
-        s = store.load(FIXTURES)
+        s = load(FIXTURES)
         text = (FIXTURES / "career" / "kb.ttl").read_bytes().decode("utf-8")
         self.assertEqual(writer.write(s.graph("career/kb.ttl"), "kb"), text)
 
@@ -135,7 +137,7 @@ class Discovery(unittest.TestCase):
         with tempfile.TemporaryDirectory() as tmp:
             shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
             (Path(tmp) / "career" / "notes.ttl").write_text("not turtle at all", encoding="utf-8")
-            self.assertEqual(store.load(tmp).findings, [])
+            self.assertEqual(load(tmp).findings, [])
 
 
 if __name__ == "__main__":
```

`tests/test_graph_writer.py`:

```diff
diff --git a/tests/test_graph_writer.py b/tests/test_graph_writer.py
index 5734b6f..0101fac 100644
--- a/tests/test_graph_writer.py
+++ b/tests/test_graph_writer.py
@@ -26,7 +26,7 @@ def triples(parsed):
 
 class FixturesAreCanonical(unittest.TestCase):
     def test_every_fixture_rewrites_to_itself(self):
-        self.assertEqual(len(FILES), 4)
+        self.assertEqual(len(FILES), 5)
         for path in FILES:
             with self.subTest(file=path.name):
                 text = path.read_bytes().decode("utf-8")
```

Run: `python -m pytest tests/test_graph_shapes.py tests/test_graph_store.py tests/test_graph_writer.py -q`
Expected: `2 failed, 44 passed`. Both failures are in `EveryRuleFires`: the sweep now names `shipped-vocabulary`, which `shapes.TIER1` doesn't have yet (`test_every_rule_has_a_mutation`), and that mutation fires nothing (`test_each_mutation_fires_its_rule_at_the_right_line`).

- [ ] **Step 2: Write the failing vocabulary test**

Create `tests/test_graph_vocabulary.py`:

```python
"""The shipped vocabulary: technologies only, clean, and honest about what is ambiguous.

It ships to every user, so a wrong edge in it is a wrong match for everybody. These tests
hold it to the rules on its own, with no knowledge base beside it.
"""
import tempfile
import unittest
from pathlib import Path

import jsk
from jsk.graph import io, store, writer
from jsk.graph import ontology as O

SHIPPED = Path(jsk.__file__).parent / "data" / "vocabulary.ttl"

# Words that really do name two shipped technologies, and so are asked about, never
# guessed. Empty today; a label added here needs a comment saying what the two are.
AMBIGUOUS = set()


class TheShippedVocabulary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            cls.s = store.load(tmp)          # an empty workspace: the shipped file alone

    def test_it_loads_with_no_findings_bar_the_allowed_clashes(self):
        left = [f.text() for f in self.s.findings
                if not (f.rule == "label-clash" and any(f"'{w}'" in f.detail for w in AMBIGUOUS))]
        self.assertEqual(left, [])

    def test_it_is_canonical(self):
        text = SHIPPED.read_bytes().decode("utf-8")
        self.assertEqual(writer.write(io.parse_text(text, "vocabulary.ttl").quads, "vocabulary"),
                         text)

    def test_it_is_big_enough_to_matter(self):
        concepts = {q.subject.value for q in io.parse(SHIPPED).quads}
        self.assertGreaterEqual(len(concepts), 60)

    def test_every_wall_holds(self):
        rows = self.s.select(f"""PREFIX j: <{O.J}>
            SELECT ?a ?b WHERE {{ ?a j:distinct ?b }}""")
        self.assertTrue(rows)
        for r in rows:
            a, b = r["a"].value, r["b"].value
            crossing = self.s.select(f"""PREFIX j: <{O.J}>
                SELECT ?p WHERE {{ GRAPH j:derived {{
                  {{ ?p j:from <{a}> ; j:to <{b}> }} UNION {{ ?p j:from <{b}> ; j:to <{a}> }} }} }}""")
            self.assertEqual(crossing, [], f"{a} and {b} are distinct, yet joined")

    def test_the_labels_people_write_resolve(self):
        index = {}
        for r in self.s.select(f"PREFIX j: <{O.J}> SELECT ?c ?l WHERE {{ ?c j:label|j:former ?l }}"):
            index.setdefault(O.norm(r["l"].value), set()).add(r["c"].value)
        for label, concept in (("K8s", "kubernetes"), ("Dot Net", "dotnet"),
                               ("Azure AD", "entra-id"), ("MSSQL", "sql-server"),
                               ("Postgres", "postgresql"), ("C#", "csharp")):
            with self.subTest(label=label):
                self.assertEqual(index[O.norm(label)], {O.C + concept})


if __name__ == "__main__":
    unittest.main()
```

Run: `python -m pytest tests/test_graph_vocabulary.py -q`
Expected: 3 failures:
- `test_it_is_big_enough_to_matter` (the seed holds 10 concepts);
- `test_every_wall_holds` (the seed has no `distinct` pair);
- `test_the_labels_people_write_resolve` (`KeyError: 'azure-ad'`).

- [ ] **Step 3: Implement**

Apply:

`src/jsk/graph/ontology.py`:

```diff
diff --git a/src/jsk/graph/ontology.py b/src/jsk/graph/ontology.py
index 9e26b9f..f7f3f1f 100644
--- a/src/jsk/graph/ontology.py
+++ b/src/jsk/graph/ontology.py
@@ -184,6 +184,8 @@ CLASSES = (
          Pred("partOf", Concept(), "*", "counts as the whole it is part of"),
          Pred("implies", Concept(), "*", "suggests this; never satisfies a required one")),
         (Pred("distinct", Concept(), "*", "never the same thing, whatever the names say"),),
+        (Pred("unlabel", STR, "*", "a shipped label or former label this person drops"),),
+        (Pred("unlink", Concept(), "*", "a shipped isA or partOf edge to that concept this person drops"),),
     ), "a matching term: capability, domain or technology"),
     Class("Organisation", "org", ("kb",), "Organisations", (
         (Pred("name", STR, "1", "the organisation's name", claim=True),),
```

`src/jsk/graph/shapes.py`:

```diff
diff --git a/src/jsk/graph/shapes.py b/src/jsk/graph/shapes.py
index 15898d4..17de516 100644
--- a/src/jsk/graph/shapes.py
+++ b/src/jsk/graph/shapes.py
@@ -16,7 +16,7 @@ FAIL, WARN = "FAIL", "WARN"
 # The tier-1 rule ids, and "syntax" for a file that does not parse. tests/test_graph_shapes.py
 # holds a mutation for every id here and in RULES; a rule with none fails the suite.
 TIER1 = ("syntax", "id-form", "id-home", "closed", "cardinality", "object", "no-blank-nodes",
-         "no-derived", "retired-reason", "comment")
+         "no-derived", "retired-reason", "comment", "shipped-vocabulary")
 XSD_TYPES = {O.XSD + t: t for t in ("string", "integer", "decimal", "boolean", "date")}
 
 
@@ -124,12 +124,32 @@ def tier1(parsed):
                 if t.value not in {O.J + c for c in O.ENUMS["conceptClass"]}:
                     add("object", FAIL, s, f"a concept is a Capability, Domain or Technology, "
                         f"not {curie(t.value)}", "a j:Capability, j:Domain or j:Technology")
+            if parsed.kind == "vocabulary":
+                shipped_vocabulary(add, s, preds)
         if O.J + "retired" in preds and O.J + "reason" not in preds:
             add("retired-reason", FAIL, s, "retired without a reason",
                 "add j:reason: why it no longer belongs on a resume")
     return out
 
 
+def shipped_vocabulary(add, s, preds):
+    """What the shipped vocabulary may hold: technologies and the edges among them.
+
+    Technology aliases are close to fact - K8s is Kubernetes. A capability edge is
+    judgement, and a judgement shipped to every user is how a graph starts overclaiming,
+    so capabilities, domains and `implies` live only in a person's own kb.ttl. Narrowing
+    is the person's too: a shipped file that unlabels itself is a file to fix.
+    """
+    for t in preds.get(O.RDF_TYPE, []):
+        if t.value != O.J + "Technology":
+            add("shipped-vocabulary", FAIL, s, f"the shipped vocabulary is technologies only, "
+                f"not {curie(t.value)}", "move it into a person's kb.ttl")
+    for name in ("implies", "unlabel", "unlink"):
+        if O.J + name in preds:
+            add("shipped-vocabulary", FAIL, s, f"j:{name} does not belong in the shipped vocabulary",
+                "implies is a person's claim, and narrowing is a person's choice: kb.ttl")
+
+
 HEAD_FIX = {
     "KB": 'start the file with k:kb j:format 3 ; j:name "…" ; j:updated "YYYY-MM-DD"^^xsd:date .',
     "Posting": "one k:post_<stem> per posting.ttl; another posting gets its own directory",
```

`src/jsk/graph/store.py`:

```diff
diff --git a/src/jsk/graph/store.py b/src/jsk/graph/store.py
index 8b6fcab..a4af57d 100644
--- a/src/jsk/graph/store.py
+++ b/src/jsk/graph/store.py
@@ -37,6 +37,7 @@ class Store:
     parsed: dict = field(default_factory=dict)      # file -> Parsed
     homes: dict = field(default_factory=dict)       # subject iri -> first file defining it
     definitions: dict = field(default_factory=dict)  # subject iri -> every file, load order
+    unmatched: list = field(default_factory=list)   # kb.ttl narrowing quads that removed nothing
     ox: object = None
 
     def select(self, sparql):
@@ -88,6 +89,12 @@ def file_name(path, root):
     return os.path.basename(path) if name.startswith("../") else name
 
 
+def graph_iri(name):
+    """The named graph a file's triples live in. Percent-encoded: a hand-made folder can
+    hold a space, and an IRI cannot."""
+    return "file:" + quote(name, safe="/-._~")
+
+
 def load(root, vocabulary=SHIPPED_VOCABULARY, files=None):
     """Load, derive, validate and close over a workspace. `files` overrides discovery."""
     import pyoxigraph as ox
@@ -110,20 +117,54 @@ def load(root, vocabulary=SHIPPED_VOCABULARY, files=None):
             raise GraphError(f"{name}: {e.strerror}", "check the path", name) from None
         parsed.file = name
         store.parsed[name] = parsed
-        # Percent-encoded: a hand-made folder can hold a space, and an IRI cannot.
-        graph = ox.NamedNode("file:" + quote(name, safe="/-._~"))
+        graph = ox.NamedNode(graph_iri(name))
         store.ox.extend(ox.Quad(q.subject, q.predicate, q.object, graph) for q in parsed.quads)
         store.findings += tier1(parsed)
         for iri in dict.fromkeys(q.subject.value for q in parsed.quads
                                  if isinstance(q.subject, ox.NamedNode)):
             store.homes.setdefault(iri, name)
             store.definitions.setdefault(iri, []).append(name)
+    narrow(store)
     derive_types(store, derived)
     store.findings += tier2(store)
     materialise_paths(store)
     return store
 
 
+# kb.ttl predicate -> the shipped predicates it removes
+NARROWS = {"unlabel": ("label", "former"), "unlink": ("isA", "partOf")}
+
+
+def narrow(store):
+    """kb.ttl's `unlabel` and `unlink`, applied to the shipped vocabulary - in memory only.
+
+    A shipped entry can be wrong for one person's field ("Go" is never the language in
+    theirs). The shipped file is not theirs to edit, and a copy of it would stop tracking
+    releases, so the removal is a statement in kb.ttl that the loader honours. One that
+    removes nothing is kept in `store.unmatched` for the narrows-nothing rule: a typo
+    there would otherwise change nothing, silently.
+    """
+    import pyoxigraph as ox
+
+    vocab = [ox.NamedNode(graph_iri(f)) for f, p in store.parsed.items() if p.kind == "vocabulary"]
+    for p in store.parsed.values():
+        if p.kind != "kb":
+            continue
+        for q in p.quads:
+            name = q.predicate.value[len(O.J):] if q.predicate.value.startswith(O.J) else None
+            if name not in NARROWS:
+                continue
+            removed = False
+            for g in vocab:
+                for target in NARROWS[name]:
+                    quad = ox.Quad(q.subject, ox.NamedNode(O.J + target), q.object, g)
+                    if quad in store.ox:
+                        store.ox.remove(quad)
+                        removed = True
+            if not removed:
+                store.unmatched.append(q)
+
+
 def derive_types(store, derived):
     """rdf:type from each k: id's prefix, into j:derived."""
     import pyoxigraph as ox
```

Replace `src/jsk/data/vocabulary.ttl` with:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Vocabulary

c:airflow a j:Technology ; j:label "Airflow", "Apache Airflow" .

c:aks a j:Technology ;
    j:label "AKS", "Azure Kubernetes Service" ;
    j:isA c:kubernetes ; j:partOf c:azure .

c:angular a j:Technology ; j:label "Angular" ; j:distinct c:angularjs .
c:angularjs a j:Technology ; j:label "Angular.js", "AngularJS" .
c:ansible a j:Technology ; j:label "Ansible" .
c:apache-spark a j:Technology ; j:label "Apache Spark", "Spark" .
c:aspnet-core a j:Technology ; j:label "ASP.NET Core" ; j:partOf c:dotnet .
c:aws a j:Technology ; j:label "AWS", "Amazon Web Services" .
c:aws-lambda a j:Technology ; j:label "AWS Lambda", "Lambda" ; j:partOf c:aws .
c:azure a j:Technology ; j:label "Azure", "MS Azure", "Microsoft Azure" .
c:azure-ai-foundry a j:Technology ; j:label "Azure AI Foundry" ; j:partOf c:azure .
c:azure-devops a j:Technology ; j:label "ADO", "Azure DevOps" ; j:former "VSTS" .
c:azure-functions a j:Technology ; j:label "Azure Functions" ; j:partOf c:azure .

c:azure-sql a j:Technology ;
    j:label "Azure SQL", "Azure SQL Database" ;
    j:isA c:sql-server ; j:partOf c:azure .

c:bicep a j:Technology ; j:label "Azure Bicep", "Bicep" ; j:partOf c:azure .
c:cloudformation a j:Technology ; j:label "AWS CloudFormation", "CloudFormation" ; j:partOf c:aws .
c:cosmos-db a j:Technology ; j:label "Azure Cosmos DB", "Cosmos DB", "CosmosDB" ; j:partOf c:azure .
c:csharp a j:Technology ; j:label "C Sharp", "C#" ; j:partOf c:dotnet .
c:databricks a j:Technology ; j:label "Azure Databricks", "Databricks" .
c:django a j:Technology ; j:label "Django" ; j:partOf c:python .
c:docker a j:Technology ; j:label "Docker" .

c:dotnet a j:Technology ;
    j:label ".NET", ".NET Core", "Dot Net", "DotNet" ;
    j:distinct c:dotnet-framework .

c:dotnet-framework a j:Technology ; j:label ".NET Framework", "Dot Net Framework" .

c:eks a j:Technology ;
    j:label "Amazon EKS", "Amazon Elastic Kubernetes Service", "EKS" ;
    j:isA c:kubernetes ; j:partOf c:aws .

c:entity-framework a j:Technology ;
    j:label "EF Core", "Entity Framework", "Entity Framework Core" ;
    j:partOf c:dotnet .

c:entra-id a j:Technology ;
    j:label "Entra ID", "Microsoft Entra ID" ;
    j:former "Azure AD", "Azure Active Directory" ;
    j:partOf c:azure .

c:fastapi a j:Technology ; j:label "FastAPI" ; j:partOf c:python .
c:fsharp a j:Technology ; j:label "F Sharp", "F#" ; j:partOf c:dotnet .
c:gcp a j:Technology ; j:label "GCP", "Google Cloud", "Google Cloud Platform" .
c:github-actions a j:Technology ; j:label "GitHub Actions" .
c:gitlab-ci a j:Technology ; j:label "GitLab CI", "GitLab CI/CD" .

c:gke a j:Technology ;
    j:label "GKE", "Google Kubernetes Engine" ;
    j:isA c:kubernetes ; j:partOf c:gcp .

c:golang a j:Technology ; j:label "Go", "Golang" .
c:graphql a j:Technology ; j:label "GraphQL" .
c:helm a j:Technology ; j:label "Helm" ; j:partOf c:kubernetes .
c:java a j:Technology ; j:label "Java" ; j:distinct c:javascript .
c:javascript a j:Technology ; j:label "ECMAScript", "JS", "JavaScript" .
c:jenkins a j:Technology ; j:label "Jenkins" .
c:kafka a j:Technology ; j:label "Apache Kafka", "Kafka" .
c:kotlin a j:Technology ; j:label "Kotlin" .
c:kubernetes a j:Technology ; j:label "K8s", "Kubernetes" .
c:linq a j:Technology ; j:label "LINQ" ; j:partOf c:csharp .
c:mongodb a j:Technology ; j:label "Mongo", "MongoDB" .
c:mysql a j:Technology ; j:label "MySQL" .
c:nextjs a j:Technology ; j:label "Next.js", "NextJS" ; j:partOf c:react .
c:nodejs a j:Technology ; j:label "Node", "Node.js", "NodeJS" .
c:openshift a j:Technology ; j:label "OpenShift", "Red Hat OpenShift" ; j:isA c:kubernetes .
c:postgresql a j:Technology ; j:label "PostgreSQL", "Postgres" .
c:pyspark a j:Technology ; j:label "PySpark" ; j:partOf c:apache-spark .
c:python a j:Technology ; j:label "Python", "Python 3" .
c:pytorch a j:Technology ; j:label "PyTorch" .
c:rabbitmq a j:Technology ; j:label "RabbitMQ" .
c:react a j:Technology ; j:label "React", "React.js", "ReactJS" .
c:redis a j:Technology ; j:label "Redis" .
c:rust a j:Technology ; j:label "Rust" .
c:scikit-learn a j:Technology ; j:label "scikit-learn", "sklearn" .
c:snowflake a j:Technology ; j:label "Snowflake" .
c:spring-boot a j:Technology ; j:label "Spring Boot" ; j:partOf c:java .
c:sql-server a j:Technology ; j:label "MS SQL", "MSSQL", "Microsoft SQL Server", "SQL Server" .
c:tensorflow a j:Technology ; j:label "TensorFlow" .
c:terraform a j:Technology ; j:label "HashiCorp Terraform", "Terraform" .
c:typescript a j:Technology ; j:label "TS", "TypeScript" .
c:vue a j:Technology ; j:label "Vue", "Vue.js", "VueJS" .
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests -n auto -q -o addopts=`
Expected: `496 passed, 2 skipped`.

- [ ] **Step 5: Commit**

```bash
git add src/jsk/graph/ontology.py src/jsk/graph/shapes.py src/jsk/graph/store.py src/jsk/data/vocabulary.ttl tests/graph_fixtures/vocabulary.ttl tests/test_graph_vocabulary.py tests/test_graph_shapes.py tests/test_graph_store.py tests/test_graph_writer.py
git commit -m "feat(graph): the shipped vocabulary, technologies only, and narrowing it from kb.ttl"
```

---

### Task 2: The posting rules, and `concept-class` once

**Files:**
- Modify: `src/jsk/graph/rules.py`
- Modify: `tests/test_graph_rules.py`, `tests/test_graph_budget.py`

**Interfaces:**
- Consumes: `store.graph_iri`, `Store.unmatched`, `Store.parsed`, `Store.file_of`, `Store.root`, `io.normalise`; in the tests, `test_graph_shapes.mutated` and `assert_fires`.
- Produces: the `RULES` entries `narrows-nothing`, `concept-reclassed`, `quote-verbatim` and `necessity-wording`, plus the helpers `unmatched_narrowing`, `reclassed`, `unquoted`, `worded_otherwise`, `squash`, `term_text`, and the regexes `OPTIONAL_WORDS`, `REQUIRED_WORDS`.

- [ ] **Step 1: Write the failing tests**

`tests/test_graph_rules.py`:

```diff
diff --git a/tests/test_graph_rules.py b/tests/test_graph_rules.py
index 135624d..db568b5 100644
--- a/tests/test_graph_rules.py
+++ b/tests/test_graph_rules.py
@@ -61,10 +61,22 @@ MUTATIONS = {
                             "events follow"),
     "concept-class": (KB, "j:industry c:healthcare", "j:industry c:kafka", "k:org_meridian",
                       "of that class"),
+    "narrows-nothing": (KB, "c:kafka j:isA c:event-driven-architecture .",
+                        'c:kafka j:isA c:event-driven-architecture ; j:unlabel "Kafak" .',
+                        "c:kafka", "check the spelling"),
+    "concept-reclassed": (KB, "c:kafka j:isA c:event-driven-architecture .",
+                          "c:kafka a j:Capability ; j:isA c:event-driven-architecture .",
+                          "c:kafka", "keeps its class"),
+    "quote-verbatim": (POSTING, 'j:quote "Deep, hands-on K8s experience in production"',
+                       'j:quote "Ten years of K8s experience in production"',
+                       "k:req_acme_platform_engineer_kubernetes", "the advert's own words"),
+    "necessity-wording": (POSTING, 'j:asked "event-driven" ; j:necessity j:preferred ;',
+                          'j:asked "event-driven" ; j:necessity j:required ;',
+                          "k:req_acme_platform_engineer_eda", "check the necessity"),
 }
 
 WARNS = {"version-gap", "headline-cited", "label-clash", "inferred-unasked",
-         "retired-referenced", "event-before-submit"}
+         "retired-referenced", "event-before-submit", "necessity-wording"}
 
 
 class EveryRuleFires(unittest.TestCase):
@@ -110,6 +122,19 @@ class Findings(unittest.TestCase):
                         'j:provenance j:confirmed .\n', "", ""))
         self.assertEqual([f.text() for f in s.findings if f.rule == "rank-unique"], [])
 
+    def test_a_domain_shared_by_two_classes_is_one_rule(self):
+        # Project.domain and Posting.domain restrict the same predicate the same way; two
+        # rules reported every such fault twice.
+        assert_fires(self, "concept-class", (
+            KB, "j:domain c:aged-care, c:healthcare", "j:domain c:aged-care, c:kafka",
+            "k:prj_clinical_events", "of that class"))
+
+    def test_a_quote_wrapped_across_lines_of_a_crlf_advert_is_still_verbatim(self):
+        s, _ = mutated(("applications/acme-platform-engineer/posting.md",
+                        "Deep, hands-on K8s experience in production.",
+                        "Deep, hands-on K8s\r\n   experience in production.", "", ""))
+        self.assertEqual([f.text() for f in s.findings if f.rule == "quote-verbatim"], [])
+
     def test_the_log_may_name_ids_that_no_longer_exist(self):
         s, _ = mutated(("career/log.ttl", "j:touched k:met_team.v1,", "j:touched k:met_gone.v1,",
                         "", ""))
```

`tests/test_graph_budget.py`:

```diff
diff --git a/tests/test_graph_budget.py b/tests/test_graph_budget.py
index d957c28..0aa8195 100644
--- a/tests/test_graph_budget.py
+++ b/tests/test_graph_budget.py
@@ -35,6 +35,7 @@ def big_workspace(root, projects=300, applications=100):
     for a in range(applications):
         d = root / "applications" / f"a{a}"
         d.mkdir(parents=True)
+        (d / "posting.md").write_text("We use Kafka.", encoding="utf-8")
         (d / "posting.ttl").write_text(
             pfx + f'k:post_a{a} j:company "C" ; j:title "T" ; j:captured "2026-09-01"^^xsd:date ;'
             f' j:advert "posting.md" .\n'
```

Run: `python -m pytest tests/test_graph_rules.py -q`
Expected: `test_every_rule_has_a_mutation` fails, because the four new ids are missing from `RULES`; so does `test_each_mutation_fires_its_rule_at_the_right_line`. `test_a_domain_shared_by_two_classes_is_one_rule` fails because `concept-class` fires twice.

- [ ] **Step 2: Implement**

`src/jsk/graph/rules.py`:

```diff
diff --git a/src/jsk/graph/rules.py b/src/jsk/graph/rules.py
index 0abf764..e28ab2d 100644
--- a/src/jsk/graph/rules.py
+++ b/src/jsk/graph/rules.py
@@ -5,11 +5,13 @@ postings. Each rule is one row - id, severity, a SELECT naming ?focus, and a fix
 adding one is adding a row, and tests/test_graph_rules.py proves each one fires.
 """
 import difflib
+import re
 from collections import defaultdict
 from dataclasses import dataclass
 
 from . import ontology as O
 from .shapes import FAIL, WARN, Finding, curie
+from .store import graph_iri
 
 PREFIX = (f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
           f"PREFIX xsd: <{O.XSD}>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")
@@ -86,15 +88,85 @@ def untyped(rows, store):
             if iri.startswith(O.C) and iri not in typed]
 
 
+def unmatched_narrowing(rows, store):
+    return [{"focus": q.subject, "p": q.predicate, "o": q.object} for q in store.unmatched]
+
+
+def reclassed(rows, store):
+    """A concept whose kb.ttl class differs from its shipped class. Reported in kb.ttl."""
+    kinds = {graph_iri(f): (f, p.kind) for f, p in store.parsed.items()}
+    by = defaultdict(lambda: {"kb": set(), "vocabulary": set(), "file": None})
+    for r in rows:
+        file, kind = kinds.get(v(r, "g"), (None, None))
+        if kind in ("kb", "vocabulary"):
+            by[v(r, "focus")][kind].add(v(r, "t"))
+            if kind == "kb":
+                by[v(r, "focus")]["file"] = file
+    return [{"focus": node(c), "file": e["file"], "kb": sorted(e["kb"]),
+             "shipped": sorted(e["vocabulary"])}
+            for c, e in sorted(by.items()) if e["kb"] and e["vocabulary"]
+            and e["kb"] != e["vocabulary"]]
+
+
+def squash(text):
+    return re.sub(r"\s+", " ", text).strip()
+
+
+def unquoted(rows, store):
+    """A requirement whose quote is not in the advert beside it, word for word."""
+    import os
+
+    from .io import normalise
+
+    out, adverts = [], {}
+    for r in rows:
+        file = store.file_of(v(r, "focus"))
+        if not file:
+            continue
+        advert = os.path.join(store.root, os.path.dirname(file), "posting.md")
+        if advert not in adverts:
+            try:
+                with open(advert, encoding="utf-8") as fh:
+                    adverts[advert] = squash(normalise(fh.read()))
+            except OSError:
+                adverts[advert] = None
+        text = adverts[advert]
+        if text is None:
+            out.append({**r, "why": "posting.md is missing beside it"})
+        elif squash(v(r, "q")) not in text:
+            out.append({**r, "why": "posting.md does not say it"})
+    return out
+
+
+OPTIONAL_WORDS = re.compile(r"\b(a plus|nice to have|bonus|desirable)\b", re.I)
+REQUIRED_WORDS = re.compile(r"\b(must|required|essential)\b", re.I)
+
+
+def worded_otherwise(rows, store):
+    out = []
+    for r in rows:
+        quote, need = v(r, "q"), v(r, "n")[len(O.J):]
+        if need == "required" and OPTIONAL_WORDS.search(quote):
+            out.append({**r, "said": OPTIONAL_WORDS.search(quote).group(0), "need": need})
+        elif need in ("preferred", "implicit") and REQUIRED_WORDS.search(quote):
+            out.append({**r, "said": REQUIRED_WORDS.search(quote).group(0), "need": need})
+    return out
+
+
 def concept_class_rules():
     """One rule per predicate that restricts the class of the concept it points at."""
-    rules = []
+    rules, seen = [], set()
     for cls in O.CLASSES:
         for p in cls.preds.values():
             if isinstance(p.obj, O.Concept) and set(p.obj.classes) != set(O.ENUMS["conceptClass"]):
+                # Project.domain and Posting.domain are one predicate with one restriction:
+                # one rule, or every such fault is reported twice.
+                if (p.name, p.obj.classes) in seen:
+                    continue
+                seen.add((p.name, p.obj.classes))
                 allowed = ", ".join(f"j:{c}" for c in p.obj.classes)
                 rules.append(Rule(
-                    f"concept-class", FAIL,
+                    "concept-class", FAIL,
                     f"""SELECT ?focus ?o ?t WHERE {{ GRAPH ?g {{ ?focus j:{p.name} ?o }}
                         ?o a ?t . FILTER(STRSTARTS(STR(?o), STR(c:)))
                         FILTER(?t NOT IN ({allowed}))
@@ -207,9 +279,35 @@ RULES = [
               FILTER(datatype(?d) = xsd:date && datatype(?s) = xsd:date && ?d < ?s) }""",
          lambda r: f"dated {v(r, 'd')}, before the application was submitted on {v(r, 's')}",
          "check the date: events follow the submission"),
+    Rule("narrows-nothing", FAIL, None,
+         lambda r: f"{curie(v(r, 'p'))} {term_text(r['o'])}: the shipped vocabulary has no such "
+                   f"{'label' if v(r, 'p').endswith('unlabel') else 'edge'} on it",
+         "check the spelling against vocabulary.ttl; a removal that removes nothing does nothing",
+         unmatched_narrowing),
+    Rule("concept-reclassed", FAIL,
+         """SELECT ?focus ?g ?t WHERE { GRAPH ?g { ?focus a ?t }
+              FILTER(?g != j:derived && STRSTARTS(STR(?focus), STR(c:))) }""",
+         lambda r: (f"kb.ttl makes it {', '.join(curie(t) for t in r['kb'])}; the shipped "
+                    f"vocabulary has it as {', '.join(curie(t) for t in r['shipped'])}"),
+         "a shipped concept keeps its class: add a capability of your own and relate them",
+         reclassed),
+    Rule("quote-verbatim", FAIL,
+         """SELECT ?focus ?q WHERE { ?focus a j:Requirement ; j:quote ?q }""",
+         lambda r: f"its quote {v(r, 'q')[:50]!r} - {r['why']}",
+         "quote the advert's own words, from posting.md; a requirement it does not state is "
+         "invented", unquoted),
+    Rule("necessity-wording", WARN,
+         """SELECT ?focus ?q ?n WHERE { ?focus a j:Requirement ; j:quote ?q ; j:necessity ?n }""",
+         lambda r: f"the advert says {r['said']!r} but it is j:{r['need']}",
+         "check the necessity against the advert's wording", worded_otherwise),
 ] + concept_class_rules()
 
 
+def term_text(t):
+    import pyoxigraph as ox
+    return curie(t.value) if isinstance(t, ox.NamedNode) else repr(t.value)
+
+
 def tier2(store):
     """Findings for the whole loaded workspace."""
     out = []
```

- [ ] **Step 3: Run the tests**

Run: `python -m pytest tests -n auto -q -o addopts=`
Expected: `498 passed, 2 skipped`.

- [ ] **Step 4: Commit**

```bash
git add src/jsk/graph/rules.py tests/test_graph_rules.py tests/test_graph_budget.py
git commit -m "feat(graph): posting rules - quotes are verbatim, necessity matches its wording"
```

---

### Task 3: The matching queries

**Files:**
- Create: `src/jsk/graph/queries.py`
- Create: `tests/match_fixtures/vocabulary.ttl`, `tests/match_fixtures/career/kb.ttl`, and for each of `contoso`, `fabrikam`, `northwind`, `tailspin`: `tests/match_fixtures/applications/<name>/{posting.ttl,posting.md}`
- Create: `tests/test_graph_match.py`, `tests/test_graph_match_mutations.py`
- Modify: `src/jsk/preflight.py` (`GRAPH_MODULES`)

**Interfaces:**
- Consumes: `store.load`, `Store.select`, the closure's Path nodes (`j:from j:to j:hops j:implied j:via` in `j:derived`), `ontology.norm`, `shapes.curie`, and `kbindex.SENIORITY/WEIGHTS/recency_points`.
- Produces (`jsk.graph.queries`), which Task 4 consumes:
  - `PRE`;
  - the dataclasses `Requirement(iri, asked, quote, necessity, concept=None)`, `Resolution(state, concepts, via)`, `Match(requirement, resolution, state, carriers, near)` (with the property `.concept`), `Row(project, score, required, preferred)` and `Question(kind, requirement, detail)`;
  - the functions `requirements(store, post)`, `labels(store)`, `concepts(store)`, `resolve(req, index, known)`, `paths_to`, `broader_held`, `match(store, post) -> {iri: Match}`, `evidence(store, project, concept) -> str`, `projects`, `posting_seniority`, `rank(store, post, matches, today) -> [Row]`, `cover(matches, budget) -> (list | None, list)` and `questions(store, matches) -> [Question]`.

- [ ] **Step 1: Write the fixtures**

These files are canonical writer output. Create them exactly as shown, with LF line endings.

Create `tests/match_fixtures/vocabulary.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Vocabulary

c:aks a j:Technology ;
    j:label "AKS", "Azure Kubernetes Service" ;
    j:isA c:kubernetes ; j:partOf c:azure .

c:angular a j:Technology ; j:label "Angular" ; j:distinct c:angularjs .
c:angularjs a j:Technology ; j:label "AngularJS" .
c:aws a j:Technology ; j:label "AWS" ; j:isA c:cloud-platform .
c:azure a j:Technology ; j:label "Azure", "Microsoft Azure" ; j:isA c:cloud-platform .
c:bicep a j:Technology ; j:label "Bicep" ; j:partOf c:azure .
c:cloud-platform a j:Technology ; j:label "Cloud platform" ; j:isA c:computing .
c:computing a j:Technology ; j:label "Computing" .
c:csharp a j:Technology ; j:label "C#" ; j:partOf c:dotnet .
c:dotnet a j:Technology ; j:label ".NET", "Dot Net" ; j:distinct c:dotnet-framework .
c:dotnet-framework a j:Technology ; j:label ".NET Framework" .
c:eks a j:Technology ; j:label "Amazon EKS", "EKS" ; j:isA c:kubernetes ; j:partOf c:aws .
c:entra-id a j:Technology ; j:label "Entra ID" ; j:former "Azure AD" ; j:partOf c:azure .
c:fastapi a j:Technology ; j:label "FastAPI" ; j:partOf c:python .
c:golang a j:Technology ; j:label "Go", "Golang" .
c:java a j:Technology ; j:label "Java" ; j:distinct c:javascript .
c:javascript a j:Technology ; j:label "JS", "JavaScript" .
c:kafka a j:Technology ; j:label "Apache Kafka", "Kafka" .
c:kubernetes a j:Technology ; j:label "K8s", "Kubernetes" .
c:python a j:Technology ; j:label "Python" .
c:sql-server a j:Technology ; j:label "MSSQL", "SQL Server" .
c:terraform a j:Technology ; j:label "Terraform" .
```

Create `tests/match_fixtures/career/kb.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

k:kb j:format 3 ; j:name "Graph Simulation" ; j:updated "2026-09-24"^^xsd:date .

# == Identity

k:person j:fullName "Graph Simulation" ; j:provenance j:confirmed .

# == Positioning

# == Work authorization and languages

# == Vocabulary

c:event-driven-architecture a j:Capability ; j:label "Event-driven architecture" .
c:infrastructure-as-code a j:Capability ; j:label "IaC", "Infrastructure as Code" .
c:mentoring a j:Capability ; j:label "Mentoring" ; j:partOf c:team-leadership .
c:team-leadership a j:Capability ; j:label "Team leadership" .
c:go-game a j:Domain ; j:label "Go", "Go (board game)" .
c:bicep j:implies c:infrastructure-as-code .
c:kafka j:implies c:event-driven-architecture .
c:terraform j:implies c:infrastructure-as-code .

# == Organisations

# == Roles

# == Projects

k:prj_events j:name "Event platform" ;
    j:strength 5 ; j:recency 2026 ;
    j:uses c:aks, c:csharp, c:kafka, c:team-leadership, c:terraform ;
    j:provenance j:confirmed .

k:ach_events_latency j:project k:prj_events ; j:rank 1 ;
    j:text "Cut p95 event latency from 5 s to 400 ms on AKS with Kafka." ;
    j:cites k:met_latency ; j:shows c:aks, c:kafka ;
    j:provenance j:confirmed .

k:ach_events_team j:project k:prj_events ; j:rank 2 ;
    j:text "Led a team of 6 engineers." ;
    j:cites k:met_team ; j:shows c:team-leadership ;
    j:provenance j:confirmed .

k:ach_events_terraform j:project k:prj_events ; j:rank 3 ;
    j:text "Wrote the platform's Terraform." ;
    j:shows c:terraform ;
    j:provenance j:confirmed .

k:prj_identity j:name "Identity" ;
    j:strength 4 ; j:recency 2022 ;
    j:uses c:bicep, c:dotnet, c:entra-id, c:kafka ;
    j:provenance j:confirmed .

k:ach_identity_sso j:project k:prj_identity ; j:rank 1 ;
    j:text "Moved 40 applications to Entra ID single sign-on." ;
    j:cites k:met_apps ; j:shows c:entra-id ;
    j:provenance j:confirmed .

k:ach_identity_events j:project k:prj_identity ; j:rank 2 ;
    j:text "Published sign-in events to Kafka." ;
    j:shows c:kafka ;
    j:provenance j:confirmed .

k:prj_portal j:name "Portal" ;
    j:strength 3 ; j:recency 2021 ;
    j:uses c:angularjs, c:java, c:sql-server ;
    j:provenance j:confirmed .

k:ach_portal_frontend j:project k:prj_portal ; j:rank 1 ;
    j:text "Built the AngularJS front end." ;
    j:shows c:angularjs ;
    j:provenance j:confirmed .

k:prj_data j:name "Data" ;
    j:strength 2 ; j:recency 2020 ;
    j:uses c:fastapi, c:kubernetes, c:python, c:terraform ;
    j:provenance j:confirmed .

k:ach_data_ingestion j:project k:prj_data ; j:rank 1 ;
    j:text "Built a FastAPI ingestion service." ;
    j:shows c:fastapi ;
    j:provenance j:inferred .

k:prj_game j:name "Game" ;
    j:strength 2 ; j:recency 2016 ;
    j:uses c:go-game, c:javascript ;
    j:provenance j:confirmed .

k:ach_game_players j:project k:prj_game ; j:rank 1 ;
    j:text "Grew a Go server to 100,000 players." ;
    j:cites k:met_players ; j:shows c:go-game ;
    j:provenance j:confirmed .

# == Metrics

k:met_apps j:subject "applications migrated" .
k:met_apps.v1 j:of k:met_apps ; j:value 40 ; j:confidence j:measured ; j:provenance j:confirmed .
k:met_latency j:subject "p95 event latency" .

k:met_latency.v1 j:of k:met_latency ;
    j:baseline 5 ; j:value 1 ;
    j:confidence j:measured ;
    j:validUntil "2026-03-01"^^xsd:date ;
    j:provenance j:confirmed .

k:met_latency.v2 j:of k:met_latency ;
    j:baseline 5000 ; j:value 400 ;
    j:confidence j:measured ;
    j:validFrom "2026-03-01"^^xsd:date ;
    j:provenance j:confirmed .

k:met_players j:subject "players" .

k:met_players.v1 j:of k:met_players ;
    j:value 100000 ;
    j:confidence j:measured ;
    j:provenance j:confirmed .

k:met_team j:subject "engineers led" .
k:met_team.v1 j:of k:met_team ; j:value 6 ; j:confidence j:measured ; j:provenance j:confirmed .

# == Skills

# == Education

# == Certifications

# == Open source

# == Open questions

k:q_data_ingestion j:about k:ach_data_ingestion ;
    j:question "Did you build the FastAPI service, or maintain it?" ;
    j:asked "2026-09-20"^^xsd:date .
```

Create `tests/match_fixtures/applications/contoso/posting.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Posting

k:post_contoso j:company "Contoso" ; j:title "Platform Engineer" ;
    j:captured "2026-09-01"^^xsd:date ; j:advert "posting.md" .

# == Requirements

k:req_contoso_azure_ad j:posting k:post_contoso ;
    j:asked "Azure AD" ; j:necessity j:preferred ;
    j:quote "Azure AD experience helps" .

k:req_contoso_dotnet j:posting k:post_contoso ;
    j:asked ".NET" ; j:necessity j:required ;
    j:quote "Our services are .NET" .

k:req_contoso_eks j:posting k:post_contoso ;
    j:asked "EKS" ; j:necessity j:preferred ;
    j:quote "EKS exposure helps" .

k:req_contoso_go j:posting k:post_contoso ;
    j:asked "Go" ; j:necessity j:preferred ;
    j:quote "Some Go would help" .

k:req_contoso_iac j:posting k:post_contoso ;
    j:asked "Infrastructure as Code" ; j:necessity j:required ;
    j:quote "Infrastructure as Code throughout" .

k:req_contoso_k3s j:posting k:post_contoso ;
    j:asked "K3s" ; j:necessity j:preferred ;
    j:quote "K3s at the edge helps" .

k:req_contoso_k8s j:posting k:post_contoso ;
    j:asked "K8s" ; j:necessity j:required ;
    j:quote "Hands-on K8s in production" .

k:req_contoso_mentoring j:posting k:post_contoso ;
    j:asked "Mentoring" ; j:necessity j:implicit ;
    j:quote "You will mentor juniors" .

k:req_contoso_team_leadership j:posting k:post_contoso ;
    j:asked "Team leadership" ; j:necessity j:required ;
    j:quote "Team leadership of four engineers" .

k:req_contoso_terraform j:posting k:post_contoso ;
    j:asked "Terraform" ; j:necessity j:required ;
    j:quote "Everything is written in Terraform" .
```

Create `tests/match_fixtures/applications/contoso/posting.md`:

```markdown
Platform Engineer at Contoso

- Hands-on K8s in production.
- Everything is written in Terraform.
- Infrastructure as Code throughout.
- Azure AD experience helps.
- Some Go would help.
- Our services are .NET.
- EKS exposure helps.
- K3s at the edge helps.
- Team leadership of four engineers.
- You will mentor juniors.
```

Create `tests/match_fixtures/applications/fabrikam/posting.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Posting

k:post_fabrikam j:company "Fabrikam" ; j:title "Senior Developer" ;
    j:captured "2026-09-01"^^xsd:date ; j:advert "posting.md" .

# == Requirements

k:req_fabrikam_angular j:posting k:post_fabrikam ;
    j:asked "Angular" ; j:necessity j:preferred ;
    j:quote "Angular helps" .

k:req_fabrikam_dotnet_framework j:posting k:post_fabrikam ;
    j:asked ".NET Framework" ; j:necessity j:required ;
    j:quote "Years of .NET Framework" .

k:req_fabrikam_sql_server j:posting k:post_fabrikam ;
    j:asked "SQL Server" ; j:necessity j:required ;
    j:quote "SQL Server daily" .

k:req_fabrikam_terraform j:posting k:post_fabrikam ;
    j:asked "Terraform" ; j:necessity j:required ;
    j:quote "Terraform for our infrastructure" .
```

Create `tests/match_fixtures/applications/fabrikam/posting.md`:

```markdown
Senior Developer at Fabrikam

- Years of .NET Framework.
- SQL Server daily.
- Angular helps.
- Terraform for our infrastructure.
```

Create `tests/match_fixtures/applications/northwind/posting.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Posting

k:post_northwind j:company "Northwind" ; j:title "Data Engineer" ;
    j:captured "2026-09-01"^^xsd:date ; j:advert "posting.md" .

# == Requirements

k:req_northwind_computing j:posting k:post_northwind ;
    j:asked "Computing" ; j:necessity j:preferred ;
    j:quote "General computing background" .

k:req_northwind_eda j:posting k:post_northwind ;
    j:asked "Event-driven architecture" ; j:necessity j:preferred ;
    j:quote "Event-driven architecture helps" .

k:req_northwind_javascript j:posting k:post_northwind ;
    j:asked "JavaScript" ; j:necessity j:preferred ;
    j:quote "Some JavaScript helps" .

k:req_northwind_kafka j:posting k:post_northwind ;
    j:asked "Kafka" ; j:necessity j:required ;
    j:quote "Kafka pipelines" .

k:req_northwind_python j:posting k:post_northwind ;
    j:asked "Python" ; j:necessity j:required ;
    j:quote "Python every day" .

k:req_northwind_terraform j:posting k:post_northwind ;
    j:asked "Terraform" ; j:necessity j:required ;
    j:quote "Terraform for the platform" .
```

Create `tests/match_fixtures/applications/northwind/posting.md`:

```markdown
Data Engineer at Northwind

- Python every day.
- Kafka pipelines.
- Terraform for the platform.
- Event-driven architecture helps.
- General computing background.
- Some JavaScript helps.
```

Create `tests/match_fixtures/applications/tailspin/posting.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Posting

k:post_tailspin j:company "Tailspin" ; j:title "Cloud Engineer" ;
    j:captured "2026-09-01"^^xsd:date ; j:advert "posting.md" .

# == Requirements

k:req_tailspin_aws j:posting k:post_tailspin ;
    j:asked "AWS" ; j:necessity j:preferred ;
    j:quote "AWS helps" .

k:req_tailspin_azure_kubernetes j:posting k:post_tailspin ;
    j:asked "Azure Kubernetes" ; j:necessity j:preferred ;
    j:quote "Azure Kubernetes helps" .

k:req_tailspin_kubernetes j:posting k:post_tailspin ;
    j:asked "Kubernetes" ; j:necessity j:required ;
    j:quote "Kubernetes in production" .

k:req_tailspin_terraform j:posting k:post_tailspin ;
    j:asked "Terraform" ; j:necessity j:required ;
    j:quote "Terraform for everything" .
```

Create `tests/match_fixtures/applications/tailspin/posting.md`:

```markdown
Cloud Engineer at Tailspin

- Terraform for everything.
- Kubernetes in production.
- AWS helps.
- Azure Kubernetes helps.
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_graph_match.py`:

```python
"""The graph simulation's scenarios, through `jsk match`'s queries.

tests/match_fixtures/ is the simulation's career and four postings written as Turtle, with
the simulation's vocabulary as a test-only vocabulary.ttl so the answers below - worked
by hand in docs/superpowers/experiments/2026-09-24-graph-simulation/ - do not move when
the shipped vocabulary grows. One deliberate difference: the simulation called a
requirement with only near carriers `missing`; the P2 spec gives it its own bucket,
`near`, because "you hold something close" is a different conversation from "you do not".
"""
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from jsk.graph import queries as Q
from jsk.graph import store

FIXTURES = Path(__file__).parent / "match_fixtures"
TODAY = datetime.date(2026, 9, 24)

# Which projects honestly carry each requirement - the simulation's TRUTH, by hand.
TRUTH = {
    ("contoso", "K8s"): {"events", "data"}, ("contoso", "Terraform"): {"events", "data"},
    ("contoso", "Infrastructure as Code"): set(), ("contoso", "Azure AD"): {"identity"},
    ("contoso", "Go"): set(), ("contoso", ".NET"): {"events", "identity"}, ("contoso", "EKS"): set(),
    ("contoso", "K3s"): set(), ("contoso", "Team leadership"): {"events"},
    ("fabrikam", ".NET Framework"): set(), ("fabrikam", "SQL Server"): {"portal"},
    ("fabrikam", "Angular"): set(), ("fabrikam", "Terraform"): {"events", "data"},
    ("northwind", "Python"): {"data"}, ("northwind", "Kafka"): {"events", "identity"},
    ("northwind", "Terraform"): {"events", "data"},
    ("northwind", "Event-driven architecture"): {"events", "identity"},
    ("northwind", "Computing"): set(), ("northwind", "JavaScript"): {"game"},
    ("tailspin", "Terraform"): {"events", "data"}, ("tailspin", "Kubernetes"): {"events", "data"},
    ("tailspin", "AWS"): set(),
    ("tailspin", "Azure Kubernetes"): {"events"},   # a true synonym nobody declared
}


def load(root=FIXTURES):
    return store.load(root, vocabulary=Path(root) / "vocabulary.ttl")


def post(name):
    return O.K + "post_" + name


def short(iri):
    return iri.rsplit("/", 1)[-1].replace("prj_", "")


def by_label(matches):
    return {m.requirement.asked: m for m in matches.values()}


def carriers(m):
    return {short(p): (short(h), hops, imp) for p, (h, hops, imp) in m.carriers.items()}


class Scenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load()
        cls.m = {p: by_label(Q.match(cls.s, post(p)))
                 for p in ("contoso", "fabrikam", "northwind", "tailspin")}

    def test_s0_the_fixture_validates(self):
        # One warning, and it is the point: "Go" is the language and the board game.
        self.assertEqual([f.text() for f in self.s.fails()], [])
        self.assertEqual([(f.rule, f.focus) for f in self.s.warns()],
                         [("label-clash", "c:golang")])

    def test_s1_labels_resolve_ambiguity_and_unknowns_are_named(self):
        c = self.m["contoso"]
        got = {t: (c[t].resolution.state, [short(x) for x in c[t].resolution.concepts])
               for t in ("K8s", ".NET", "Azure AD", "Go", "K3s")}
        self.assertEqual(got, {"K8s": ("resolved", ["kubernetes"]),
                               ".NET": ("resolved", ["dotnet"]),
                               "Azure AD": ("resolved", ["entra-id"]),       # a former label
                               "Go": ("ambiguous", ["go-game", "golang"]),
                               "K3s": ("candidate", [])})

    def test_s2_narrower_counts_as_broader_one_way_only(self):
        c = self.m["contoso"]
        self.assertEqual(carriers(c["K8s"])["events"], ("aks", 1, False))
        self.assertEqual((c["EKS"].state, {short(p): w for p, w in c["EKS"].near.items()}),
                         ("near", {"data": "holds broader c:kubernetes"}))

    def test_s3_the_hop_limit(self):
        # aks -> azure -> cloud-platform -> computing is three hops.
        n = self.m["northwind"]["Computing"]
        self.assertEqual((n.state, n.carriers), ("missing", {}))

    def test_two_hops_still_count(self):
        # Not one of the simulation's: every scenario there joins at 0 or 1 hop, or fails
        # at 3, so nothing pinned the second hop. aks -> azure -> cloud-platform is two.
        s = edited("# == Requirements\n",
                   '# == Requirements\n\nk:req_tailspin_cloud j:posting k:post_tailspin ;\n'
                   '    j:asked "Cloud platform" ; j:necessity j:preferred ;\n'
                   '    j:quote "AWS helps" .\n', "applications/tailspin/posting.ttl")
        cloud = by_label(Q.match(s, post("tailspin")))["Cloud platform"]
        self.assertEqual(carriers(cloud), {"events": ("aks", 2, False),
                                           "identity": ("bicep", 2, False)})

    def test_s4_distinct_walls(self):
        f = self.m["fabrikam"]
        self.assertEqual((f[".NET Framework"].carriers, f["Angular"].carriers), ({}, {}))

    def test_s5_implies_never_carries_a_required_requirement(self):
        iac = self.m["contoso"]["Infrastructure as Code"]
        eda = self.m["northwind"]["Event-driven architecture"]
        self.assertEqual((iac.state, sorted(short(p) for p in iac.near)),
                         ("near", ["data", "events", "identity"]))
        self.assertEqual(sorted(carriers(eda)), ["events", "identity"])    # preferred: carries

    def test_s6_precision_and_recall_against_the_truth(self):
        pairs = {(p, t, short(proj)) for p, ms in self.m.items() for t, m in ms.items()
                 for proj in m.carriers}
        truth = {(p, t, proj) for (p, t), projs in TRUTH.items() for proj in projs}
        tp = len(pairs & truth)
        self.assertEqual((round(tp / len(pairs), 3), round(tp / len(truth), 3)), (1.0, 0.958))
        self.assertEqual(truth - pairs, {("tailspin", "Azure Kubernetes", "events")})

    def test_s7_cover_the_posting_not_just_the_top_scores(self):
        n = Q.match(self.s, post("northwind"))
        top = [short(r.project) for r in Q.rank(self.s, post("northwind"), n, TODAY)][:2]
        chosen, uncovered = Q.cover(n, 2)
        self.assertEqual(top, ["events", "identity"])        # these two leave Python uncovered
        self.assertEqual(([short(p) for p in chosen], uncovered), (["data", "events"], []))

    def test_s11_the_questions_a_tailoring_round_should_ask(self):
        qs = Q.questions(self.s, Q.match(self.s, post("contoso")))
        self.assertEqual([(q.requirement, q.kind, [short(d) for d in q.detail]) for q in qs], [
            (".NET", "tag-only", ["events", "identity"]),
            ("EKS", "broader-held", ["data"]),
            ("Go", "ambiguous", ["go-game", "golang"]),
            ("Infrastructure as Code", "implied", ["data", "events", "identity"]),
            ("K3s", "unknown-term", []),
        ])


class Ranking(unittest.TestCase):
    def test_scores_worked_by_hand(self):
        # northwind: events carries Kafka, Terraform (required, x3) and EDA (preferred, x1):
        # 6 + 1 + strength 5 x2 + recency 2026 (+1) = 18. identity: Kafka 3 + EDA 1 + 8 +
        # 2022, four years (+0.5) = 12.5. data: Python, Terraform 6 + 4 + 2020, six years
        # (+0.5) = 10.5. portal 6 + 0.5. game: JavaScript 1 + 4 + 2016, ten years (0) = 5.
        s = load()
        rows = Q.rank(s, post("northwind"), Q.match(s, post("northwind")), TODAY)
        self.assertEqual([(short(r.project), r.score) for r in rows],
                         [("events", 18), ("identity", 12.5), ("data", 10.5), ("portal", 6.5),
                          ("game", 5)])


def edited(old, new, file="career/kb.ttl"):
    """The fixture with one edit, loaded."""
    tmp = tempfile.mkdtemp()
    shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
    path = Path(tmp) / file
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    try:
        return load(tmp)
    finally:
        shutil.rmtree(tmp)


class Resolution(unittest.TestCase):
    def test_the_analysts_concept_settles_an_ambiguity(self):
        s = edited('j:asked "Go" ; j:necessity j:preferred ;',
                   'j:asked "Go" ; j:necessity j:preferred ; j:concept c:golang ;',
                   "applications/contoso/posting.ttl")
        go = by_label(Q.match(s, post("contoso")))["Go"]
        self.assertEqual((go.resolution.via, go.state), ("concept", "missing"))

    def test_an_id_beats_a_label_clash(self):
        # "Go-game" normalises to the id c:go-game, which "Go" never would.
        s = edited('j:asked "Go" ;', 'j:asked "Go-game" ;', "applications/contoso/posting.ttl")
        go = by_label(Q.match(s, post("contoso")))["Go-game"]
        self.assertEqual((go.resolution.via, [short(c) for c in go.resolution.concepts]),
                         ("id", ["go-game"]))


    def test_a_label_as_messily_written_still_resolves(self):
        s = edited('j:asked "K8s" ;', 'j:asked "  k8S  " ;', "applications/contoso/posting.ttl")
        k8s = by_label(Q.match(s, post("contoso")))["  k8S  "]
        self.assertEqual((k8s.state, [short(c) for c in k8s.resolution.concepts]),
                         ("matched", ["kubernetes"]))

    def test_a_persons_label_that_collides_is_asked_not_crashed(self):
        # "Apache Kafka" is a shipped label, not an id; "Kafka" would stay resolved, since
        # it is the id c:kafka and an id beats any clash.
        s = edited('c:team-leadership a j:Capability ; j:label "Team leadership" .',
                   'c:team-leadership a j:Capability ; j:label "Apache Kafka", "Team leadership" .')
        req = Q.Requirement(O.K + "req_x", "Apache Kafka", "Apache Kafka", "required")
        got = Q.resolve(req, Q.labels(s), Q.concepts(s))
        self.assertEqual((got.state, [short(c) for c in got.concepts]),
                         ("ambiguous", ["kafka", "team-leadership"]))
        self.assertEqual([f.text() for f in s.fails()], [])

    def test_a_posting_with_nothing_required_has_an_empty_cover(self):
        self.assertEqual(Q.cover({}, 3), ([], []))


class Retired(unittest.TestCase):
    def test_a_retired_project_carries_nothing(self):
        s = edited('k:prj_data j:name "Data" ;',
                   'k:prj_data j:name "Data" ; j:retired "2026-01-01"^^xsd:date ; '
                   'j:reason "Folded into events." ;')
        k8s = by_label(Q.match(s, post("contoso")))["K8s"]
        self.assertEqual(sorted(carriers(k8s)), ["events"])

    def test_a_retired_bullet_is_not_evidence(self):
        s = edited('j:shows c:terraform ;',
                   'j:shows c:terraform ; j:retired "2026-01-01"^^xsd:date ; '
                   'j:reason "Superseded." ;')
        self.assertEqual(Q.evidence(s, O.K + "prj_events", O.C + "terraform"), "tag")


class Narrowing(unittest.TestCase):
    def test_unlabel_takes_a_shipped_label_away(self):
        s = edited("c:go-game a j:Domain ;", 'c:golang j:unlabel "Go" .\n\nc:go-game a j:Domain ;')
        go = by_label(Q.match(s, post("contoso")))["Go"]
        self.assertEqual([short(c) for c in go.resolution.concepts], ["go-game"])
        self.assertEqual([f.text() for f in s.findings], [])     # and the clash is gone

    def test_unlink_takes_a_shipped_edge_away(self):
        s = edited("c:go-game a j:Domain ;", "c:aks j:unlink c:kubernetes .\n\nc:go-game a j:Domain ;")
        k8s = by_label(Q.match(s, post("contoso")))["K8s"]
        self.assertEqual(sorted(carriers(k8s)), ["data"])       # events held only AKS

    def test_the_file_is_not_touched(self):
        before = (FIXTURES / "vocabulary.ttl").read_bytes()
        edited("c:go-game a j:Domain ;", 'c:golang j:unlabel "Go" .\n\nc:go-game a j:Domain ;')
        self.assertEqual((FIXTURES / "vocabulary.ttl").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_graph_match_mutations.py`:

```python
"""Break each matching rule and watch the scenarios catch it.

tests/test_graph_match.py passing proves the rules hold on its fixture; it does not prove
the tests would notice if a rule stopped holding. So each mutation below breaks one rule
in a throwaway copy of the package - the kind of break a well-meant refactor makes - and
the scenarios must then fail. A control copy with no mutation must pass, or a harness
that fails for any reason would look like every mutation being caught.

Ported from the graph simulation's mutate.py.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).parent
SRC = TESTS.parent / "src"

# name: (file under the copy, text, replacement)
MUTATIONS = {
    "counts-as runs both ways": (
        "src/jsk/graph/queries.py",
        'm.near.setdefault(proj, f"holds broader {curie(held)}")',
        "m.carriers.setdefault(proj, (held, 1, False))"),
    "a third hop": (
        # The two-hop insert, made to join three edges: every "2-hop" path is now three.
        "src/jsk/graph/store.py",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?m }} GRAPH ?h3 {{ ?m ?k3 ?b }} "
        "FILTER(?k3 IN ({kinds}))"),
    "no second hop": (
        "src/jsk/graph/store.py",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }} FILTER(false)"),
    "implies carries a required requirement": (
        "src/jsk/graph/queries.py",
        'if implied and req.necessity == "required":',
        "if False:"),
    "the wall is ignored": (
        "tests/match_fixtures/vocabulary.ttl",
        'c:dotnet a j:Technology ; j:label ".NET", "Dot Net" ; j:distinct c:dotnet-framework .',
        'c:dotnet a j:Technology ; j:label ".NET", "Dot Net" ; j:isA c:dotnet-framework .'),
    "a tag counts as evidence": (
        "src/jsk/graph/queries.py",
        'return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "tag"',
        'return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "confirmed"'),
    "ambiguity is guessed": (
        "src/jsk/graph/queries.py",
        "    if len(found) == 1:",
        "    if len(found) >= 1:"),
}


def run(mutation=None):
    """The scenarios' exit code over a copy of the package, with `mutation` applied."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(SRC, tmp / "src", ignore=shutil.ignore_patterns("__pycache__"))
        (tmp / "tests").mkdir()
        shutil.copy(TESTS / "test_graph_match.py", tmp / "tests")
        shutil.copytree(TESTS / "match_fixtures", tmp / "tests" / "match_fixtures")
        if mutation:
            file, old, new = mutation
            path = tmp / file
            text = path.read_text(encoding="utf-8")
            assert text.count(old) == 1, f"{old!r} is not once in {file}"
            path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        env = dict(os.environ, PYTHONPATH=str(tmp / "src"))
        done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                               str(tmp / "tests" / "test_graph_match.py")],
                              capture_output=True, text=True, env=env, cwd=tmp)
        return done.returncode, done.stdout[-2000:]


class EveryMutationIsCaught(unittest.TestCase):
    def test_the_control_passes(self):
        code, out = run()
        self.assertEqual(code, 0, out)

    def test_each_mutation_fails_the_scenarios(self):
        for name, mutation in MUTATIONS.items():
            with self.subTest(mutation=name):
                code, out = run(mutation)
                self.assertEqual(code, 1, f"{name} was not caught:\n{out}")


if __name__ == "__main__":
    unittest.main()
```

Run: `python -m pytest tests/test_graph_match.py -q`
Expected: `ImportError: cannot import name 'queries' from 'jsk.graph'`.

- [ ] **Step 3: Implement**

Create `src/jsk/graph/queries.py`:

```python
"""A posting matched against the career, through the vocabulary: what `jsk match` prints.

Ported from the graph simulation (docs/superpowers/experiments/2026-09-24-graph-simulation/),
where every rule here was proven by a scenario and then by a mutation that broke it. The
rules, from docs/superpowers/specs/2026-09-24-graph-match-design.md:

- counts-as runs one way, from what a project holds up to what the posting asks for;
- within the closure P1 builds - 0, 1 or 2 hops, never more;
- a path through `implies` never carries a required requirement;
- a label that names two concepts is asked about, never guessed;
- a tag is not evidence: only a bullet that shows the concept is.

SPARQL finds the paths; Python assembles the answer, because the answer is a decision
over several rows (the best path, the evidence level), not a row.
"""
import itertools
from dataclasses import dataclass, field

from ..kbindex import SENIORITY, WEIGHTS, recency_points
from . import ontology as O
from .shapes import curie

PRE = (f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
       f"PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")


@dataclass(frozen=True)
class Requirement:
    iri: str
    asked: str
    quote: str
    necessity: str
    concept: str = None          # the analyst's answer to an ambiguity


@dataclass(frozen=True)
class Resolution:
    state: str                   # resolved | ambiguous | candidate
    concepts: tuple              # iris, sorted
    via: str = None              # concept | id | label


@dataclass
class Match:
    requirement: Requirement
    resolution: Resolution
    state: str = None            # matched | near | missing | ambiguous | candidate | implicit
    carriers: dict = field(default_factory=dict)   # project -> (held, hops, implied)
    near: dict = field(default_factory=dict)       # project -> why

    @property
    def concept(self):
        return self.resolution.concepts[0] if self.resolution.state == "resolved" else None


@dataclass(frozen=True)
class Row:
    project: str
    score: float
    required: tuple
    preferred: tuple


@dataclass(frozen=True)
class Question:
    kind: str                    # ambiguous | unknown-term | implied | broader-held | tag-only
    requirement: str             # the label as the posting wrote it
    detail: tuple


def local(iri):
    return iri[len(O.J):] if iri.startswith(O.J) else iri


def requirements(store, post):
    rows = store.select(PRE + f"""
        SELECT ?r ?asked ?quote ?need ?concept WHERE {{
          ?r j:posting <{post}> ; j:asked ?asked ; j:quote ?quote ; j:necessity ?need .
          OPTIONAL {{ ?r j:concept ?concept }} }} ORDER BY ?r""")
    return [Requirement(r["r"].value, r["asked"].value, r["quote"].value, local(r["need"].value),
                        r["concept"].value if "concept" in r else None) for r in rows]


def labels(store):
    """{normalised label: {concept iris}} over labels and former labels, shipped and the
    person's own - after kb.ttl's unlabels, which the loader has already applied."""
    out = {}
    for r in store.select(PRE + """SELECT ?c ?l WHERE { ?c j:label|j:former ?l }"""):
        out.setdefault(O.norm(r["l"].value), set()).add(r["c"].value)
    return out


def concepts(store):
    return {r["c"].value for r in store.select(PRE + """
        SELECT DISTINCT ?c WHERE { GRAPH ?g { ?c ?p ?o }
                                   FILTER(STRSTARTS(STR(?c), STR(c:))) }""")}


def resolve(req, index, known):
    """The concept a requirement asks for: the analyst's choice, then an id, then labels."""
    if req.concept:
        return Resolution("resolved", (req.concept,), "concept")
    key = O.norm(req.asked)
    if O.C + key in known:
        return Resolution("resolved", (O.C + key,), "id")
    found = tuple(sorted(index.get(key, ())))
    if len(found) == 1:
        return Resolution("resolved", found, "label")
    return Resolution("ambiguous" if found else "candidate", found, "label" if found else None)


def paths_to(store, concept):
    """(project, held, hops, implied) for every live project holding something that counts
    as `concept` - the closure's paths run from the held concept up to the asked one."""
    rows = store.select(PRE + f"""
        SELECT ?proj ?held ?hops ?implied WHERE {{
          ?proj j:uses ?held .
          GRAPH j:derived {{ ?p j:from ?held ; j:to <{concept}> ; j:hops ?hops ;
                                j:implied ?implied }}
          FILTER NOT EXISTS {{ ?proj j:retired ?x }} }}""")
    return [(r["proj"].value, r["held"].value, int(r["hops"].value), r["implied"].value == "true")
            for r in rows]


def broader_held(store, concept):
    """(project, held) where the project holds only something `concept` counts as - the
    reverse direction, which never matches: Kubernetes work is not EKS work."""
    rows = store.select(PRE + f"""
        SELECT ?proj ?held WHERE {{
          ?proj j:uses ?held .
          GRAPH j:derived {{ ?p j:from <{concept}> ; j:to ?held ; j:hops ?h ; j:implied false }}
          FILTER(?h > 0) FILTER NOT EXISTS {{ ?proj j:retired ?x }} }}""")
    return [(r["proj"].value, r["held"].value) for r in rows]


def match(store, post):
    """{requirement iri: Match} for one posting."""
    index, known = labels(store), concepts(store)
    out = {}
    for req in requirements(store, post):
        m = Match(req, resolve(req, index, known))
        out[req.iri] = m
        if req.necessity == "implicit":
            m.state = "implicit"
            continue
        if m.resolution.state != "resolved":
            m.state = m.resolution.state
            continue
        for proj, held, hops, implied in paths_to(store, m.concept):
            if implied and req.necessity == "required":
                m.near.setdefault(proj, f"implied by {curie(held)}; confirm")
                continue
            best = m.carriers.get(proj)
            if best is None or (hops, implied, held) < (best[1], best[2], best[0]):
                m.carriers[proj] = (held, hops, implied)
        for proj, held in broader_held(store, m.concept):
            if proj not in m.carriers:
                m.near.setdefault(proj, f"holds broader {curie(held)}")
        for proj in m.carriers:
            m.near.pop(proj, None)
        m.state = "matched" if m.carriers else "near" if m.near else "missing"
    return out


def evidence(store, project, concept):
    """confirmed: a live, confirmed bullet shows the concept or something that counts as it
    without an implies edge. unconfirmed: only an inferred or unverified bullet does.
    tag: only the project's `uses` does - which is a claim, not evidence."""
    rows = store.select(PRE + f"""
        SELECT DISTINCT ?pv WHERE {{
          ?b j:project <{project}> ; j:shows ?m ; j:provenance ?pv .
          GRAPH j:derived {{ ?p j:from ?m ; j:to <{concept}> ; j:implied false }}
          FILTER NOT EXISTS {{ ?b j:retired ?x }} }}""")
    levels = {local(r["pv"].value) for r in rows}
    return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "tag"


def projects(store):
    """{project: (strength, recency, seniority)} for every live project."""
    rows = store.select(PRE + """
        SELECT ?p ?s ?r ?sen WHERE { ?p a j:Project ; j:strength ?s ; j:recency ?r .
                                     OPTIONAL { ?p j:seniority ?sen }
                                     FILTER NOT EXISTS { ?p j:retired ?x } }""")
    return {r["p"].value: (int(r["s"].value), int(r["r"].value),
                           local(r["sen"].value) if "sen" in r else None) for r in rows}


def posting_seniority(store, post):
    rows = store.select(PRE + f"SELECT ?s WHERE {{ <{post}> j:seniority ?s }}")
    return local(rows[0]["s"].value) if rows else None


def rank(store, post, matches, today):
    """Every live project scored as `jsk index --rank` scores it, over the graph's matches:
    required x3, preferred x1, strength x2, recency, and a seniority point at or above the
    posting's. SENIORITY runs from most senior to least, so a lower index is higher."""
    level = posting_seniority(store, post)
    level_at = SENIORITY.index(level) if level in SENIORITY else None
    rows = []
    live = projects(store)
    for proj, (strength, recency, seniority) in live.items():
        req = tuple(m.requirement.asked for m in matches.values()
                    if proj in m.carriers and m.requirement.necessity == "required")
        pref = tuple(m.requirement.asked for m in matches.values()
                     if proj in m.carriers and m.requirement.necessity == "preferred")
        score = (WEIGHTS["required"] * len(req) + WEIGHTS["preferred"] * len(pref)
                 + 2 * strength + recency_points(recency, today))
        if level_at is not None and seniority in SENIORITY and SENIORITY.index(seniority) <= level_at:
            score += 1
        rows.append(Row(proj, score, req, pref))
    # kbindex.rank's tie-break: strength, then recency, then id.
    return sorted(rows, key=lambda r: (-r.score, -live[r.project][0], -live[r.project][1],
                                       r.project))


def cover(matches, budget):
    """(projects, uncovered): the smallest set of at most `budget` projects that carries
    every required requirement any project can carry - the top scores need not.
    `uncovered` is what nothing carries. None for projects when no set within the budget
    does it."""
    required = [m for m in matches.values() if m.requirement.necessity == "required"
                and m.state == "matched"]
    carries = {}
    for m in required:
        for proj in m.carriers:
            carries.setdefault(proj, set()).add(m.requirement.iri)
    reachable = set().union(*carries.values()) if carries else set()
    uncovered = sorted(m.requirement.asked for m in matches.values()
                       if m.requirement.necessity == "required" and m.state != "matched")
    for size in range(0 if not reachable else 1, budget + 1):
        for combo in itertools.combinations(sorted(carries), size):
            if set().union(set(), *(carries[p] for p in combo)) >= reachable:
                return list(combo), uncovered
    return None, uncovered


def questions(store, matches):
    """The questions a tailoring round should ask - each one a named gap in the join."""
    out = []
    for m in matches.values():
        asked = m.requirement.asked
        if m.state == "ambiguous":
            out.append(Question("ambiguous", asked, m.resolution.concepts))
        elif m.state == "candidate":
            out.append(Question("unknown-term", asked, ()))
        elif m.state == "near":
            kind = "implied" if any("implied" in why for why in m.near.values()) else "broader-held"
            out.append(Question(kind, asked, tuple(sorted(m.near))))
        elif m.state == "matched":
            levels = {p: evidence(store, p, m.concept) for p in m.carriers}
            if "confirmed" not in levels.values():
                out.append(Question("tag-only", asked, tuple(sorted(levels))))
    return sorted(out, key=lambda q: (q.requirement, q.kind))
```

In `src/jsk/preflight.py`, change the end of `GRAPH_MODULES` from `"graph.rules", "graph.store"]` to `"graph.rules", "graph.store", "graph.queries"]`.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_graph_match.py tests/test_graph_match_mutations.py -q -o addopts=`
Expected: `23 passed`. The mutations test copies the package seven times and runs the scenarios in each copy, so it takes about 15 s.

Run: `python -m pytest tests -n auto -q -o addopts=`
Expected: `521 passed, 2 skipped`.

- [ ] **Step 5: Commit**

```bash
git add src/jsk/graph/queries.py src/jsk/preflight.py tests/match_fixtures tests/test_graph_match.py tests/test_graph_match_mutations.py
git commit -m "feat(graph): the matching queries - one way, two hops, implies never carries required"
```

---

### Task 4: `jsk match`, and the plugin surface

**Files:**
- Create: `src/jsk/graph/match.py`
- Modify: `src/jsk/cli.py`, `src/jsk/preflight.py`, `plugins/jsk/skills/jsk/SKILL.md`, `docs/SCRIPTS.md`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything in `queries` (Task 3), plus `store.load`, `store.file_name`, `Store.fails/warns/report`, `validate_urs.show`, `cliutil.docstring_usage` and `cliutil.wants_help`.
- Produces: `jsk.graph.match` with `COVER`, `workspace_of(posting) -> str | None`, `result(store, post, today, budget) -> dict`, `markdown(result) -> str` and `main(argv=None) -> int`. It also adds `SIMPLE["match"]` and `SUBPACKAGE["match.py"] = "graph"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```diff
diff --git a/tests/test_cli.py b/tests/test_cli.py
index f027b8b..877cb86 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -20,8 +20,8 @@ JSK = CLI
 EXAMPLE = EXAMPLE_URS
 BODY = "Cut order-processing latency 62 percent by decomposing a monolithic service."
 
-SUBCOMMANDS = ["doctor", "new", "index", "validate", "render", "preview", "check", "gates",
-               "fit", "ship", "freeze"]
+SUBCOMMANDS = ["doctor", "new", "index", "match", "validate", "render", "preview", "check",
+               "gates", "fit", "ship", "freeze"]
 
 
 class Usage(unittest.TestCase):
@@ -713,5 +713,56 @@ class PreviewInProcess(unittest.TestCase):
         self.assertIn("! Missing $", out)
 
 
+class Match(unittest.TestCase):
+    """`jsk match`: an assessment, so it exits 0 with gaps; 1 only for a broken record."""
+
+    FIX = Path(__file__).parent / "match_fixtures"
+    CONTOSO = FIX / "applications" / "contoso" / "posting.ttl"
+
+    def test_it_prints_the_four_sections(self):
+        code, out = run(JSK, "match", self.CONTOSO, "--today", "2026-09-24")
+        self.assertEqual(code, 0, out)
+        for heading in ("# Match - Platform Engineer at Contoso (k:post_contoso)",
+                        "## Requirements", "## Ranking", "## Cover", "## Questions"):
+            self.assertIn(heading, out)
+        self.assertIn("| K8s | required | matched | k:prj_data; k:prj_events (via c:aks, 1 hop) |",
+                      out)
+
+    def test_json_is_the_same_result_structured(self):
+        code, out = run(JSK, "match", self.CONTOSO, "--json", "--today", "2026-09-24")
+        self.assertEqual(code, 0, out)
+        r = json.loads(out)
+        self.assertEqual(r["posting"], "k:post_contoso")
+        self.assertEqual({q["asked"]: q["state"] for q in r["requirements"]}["Go"], "ambiguous")
+
+    def test_a_broken_record_is_not_matched(self):
+        with tempfile.TemporaryDirectory() as tmp:
+            import shutil
+            shutil.copytree(self.FIX, tmp, dirs_exist_ok=True)
+            kb = Path(tmp) / "career" / "kb.ttl"
+            kb.write_text(kb.read_text(encoding="utf-8").replace("j:uses c:aks,", "j:uses c:akss,"),
+                          encoding="utf-8")
+            code, out = run(JSK, "match", Path(tmp) / "applications" / "contoso" / "posting.ttl")
+        self.assertEqual(code, 1, out)
+        self.assertIn("fix them before matching", out)
+        self.assertIn("c:akss: nothing defines it", out)
+
+    def test_a_relative_path_from_inside_the_workspace(self):
+        from jsk.graph.match import workspace_of
+        here = os.getcwd()
+        try:
+            os.chdir(self.FIX)
+            self.assertEqual(workspace_of(os.path.join("applications", "contoso", "posting.ttl")),
+                             str(self.FIX))
+        finally:
+            os.chdir(here)
+
+    def test_outside_the_layout_is_a_usage_error(self):
+        code, out = run(JSK, "match", self.FIX / "career" / "kb.ttl")
+        self.assertEqual(code, 2, out)
+        code, out = run(JSK, "match", self.CONTOSO, "--cover", "none")
+        self.assertEqual(code, 2, out)
+
+
 if __name__ == "__main__":
     unittest.main()
```

Run: `python -m pytest tests/test_cli.py -q -o addopts= -k "Match or help or subcommand"`
Expected: `7 failed, 5 passed`. `jsk match` is an unknown subcommand, so these fail:
- the four `Match` tests that run the command;
- `test_a_relative_path_from_inside_the_workspace` (no `jsk.graph.match`);
- the three `Usage` tests that list every subcommand.

- [ ] **Step 2: Implement**

Create `src/jsk/graph/match.py`:

```python
"""jsk match - a posting's requirements joined with the career, through the vocabulary.

Usage: jsk match <applications/<dir>/posting.ttl> [--cover N] [--json] [--today YYYY-MM-DD]

  --cover N   the most projects the cover may use (default 3)
  --json      the same result, structured
  --today     the date recency is measured from (default: today)

Reads the whole graph workspace the posting belongs to - career/kb.ttl, the applications,
the shipped vocabulary - and validates it first: a record with a FAIL is not matched,
because a match over a broken record would be a guess.

Exit 0 matched (missing requirements included: this is an assessment, not a gate),
1 the workspace has FAIL findings, 2 called wrong.

Each requirement lands in one bucket. `matched`: a project holds the concept, or one that
counts as it. `near`: only through an implies edge, for a required requirement, or the
project holds something broader. `missing`, `ambiguous` (the label names more than one
concept - the analyst answers with j:concept), `candidate` (it names none), `implicit`.
"""
import datetime
import json
import os
import sys

from ..cliutil import docstring_usage, wants_help

COVER = 3


def workspace_of(posting):
    """The directory holding applications/, or None when the posting is not in that layout."""
    folder = os.path.dirname(os.path.abspath(posting))
    apps = os.path.dirname(folder)
    if os.path.basename(apps) != "applications" or os.path.basename(posting) != "posting.ttl":
        return None
    return os.path.dirname(apps)


def result(store, post, today, budget):
    """Everything `jsk match` reports, as plain data."""
    from . import queries as Q
    from .shapes import curie

    matches = Q.match(store, post)
    ranked = Q.rank(store, post, matches, today)
    chosen, uncovered = Q.cover(matches, budget)
    head = store.select(Q.PRE + f"""SELECT ?company ?title WHERE {{
        <{post}> j:company ?company ; j:title ?title }}""")[0]
    reqs = []
    for m in matches.values():
        reqs.append({
            "id": curie(m.requirement.iri), "asked": m.requirement.asked,
            "necessity": m.requirement.necessity, "state": m.state,
            "concepts": [curie(c) for c in m.resolution.concepts],
            "carriers": [{"project": curie(p), "held": curie(h), "hops": hops, "implied": imp,
                          "evidence": Q.evidence(store, p, m.concept)}
                         for p, (h, hops, imp) in sorted(m.carriers.items())],
            "near": [{"project": curie(p), "why": why} for p, why in sorted(m.near.items())],
        })
    return {
        "posting": curie(post), "company": head["company"].value, "title": head["title"].value,
        "requirements": reqs,
        "ranking": [{"project": curie(r.project), "score": r.score, "required": list(r.required),
                     "preferred": list(r.preferred)} for r in ranked],
        "cover": {"budget": budget, "projects": None if chosen is None else
                  [curie(p) for p in chosen], "uncovered": uncovered},
        "questions": [{"kind": q.kind, "requirement": q.requirement,
                       "detail": [curie(d) for d in q.detail]}
                      for q in Q.questions(store, matches)],
        "warnings": len(store.warns()),
    }


def number(x):
    return str(int(x)) if float(x).is_integer() else str(x)


def markdown(r):
    reqs = r["requirements"]
    count = {s: sum(q["state"] == s for q in reqs) for s in
             ("matched", "near", "missing", "ambiguous", "candidate", "implicit")}
    need = {n: sum(q["necessity"] == n for q in reqs) for n in ("required", "preferred", "implicit")}
    out = [f"# Match - {r['title']} at {r['company']} ({r['posting']})", "",
           f"{need['required']} required, {need['preferred']} preferred, {need['implicit']} implicit. "
           + ", ".join(f"{n} {s}" for s, n in count.items() if n) + "."]
    if r["warnings"]:
        n = r["warnings"]
        out.append(f"The workspace has {n} warning{'s' if n > 1 else ''}; none changes the match.")
    out += ["", "## Requirements", "", "| Requirement | Need | State | Carried by | Evidence |",
            "|---|---|---|---|---|"]
    for q in reqs:
        if q["carriers"]:
            carried = "; ".join(c["project"] + ("" if c["hops"] == 0 else
                                                f" (via {c['held']}, {c['hops']} hop"
                                                f"{'s' if c['hops'] > 1 else ''})")
                                for c in q["carriers"])
            ev = "; ".join(c["evidence"] for c in q["carriers"])
        elif q["near"]:
            carried, ev = "; ".join(f"{n['project']}: {n['why']}" for n in q["near"]), ""
        elif q["state"] == "ambiguous":
            carried, ev = " or ".join(q["concepts"]) + "?", ""
        else:
            carried, ev = "", ""
        out.append(f"| {q['asked']} | {q['necessity']} | {q['state']} | {carried} | {ev} |")
    out += ["", "## Ranking", "",
            "Required ×3 · preferred ×1 · strength ×2 · recency +1 within 3 years, +0.5 at 4-6 · "
            "seniority +1 at or above the posting's.", "",
            "| Project | Score | Required | Preferred |", "|---|---|---|---|"]
    for row in r["ranking"]:
        out.append(f"| {row['project']} | {number(row['score'])} | {', '.join(row['required'])} | "
                   f"{', '.join(row['preferred'])} |")
    cov = r["cover"]
    out += ["", "## Cover", ""]
    if cov["projects"] is None:
        out.append(f"No {cov['budget']} projects carry every required requirement that can be "
                   f"carried; raise --cover or read the Ranking.")
    elif cov["projects"]:
        verb = "carries" if len(cov["projects"]) == 1 else "carry"
        out.append(f"{', '.join(cov['projects'])} {verb} every required requirement that can be "
                   f"carried.")
    if cov["uncovered"]:
        out.append(f"Nothing carries: {', '.join(cov['uncovered'])}.")
    if not cov["projects"] and not cov["uncovered"]:
        out.append("The posting has no required requirements.")
    out += ["", "## Questions", ""]
    ask = {"ambiguous": "which concept does it mean: {}?",
           "unknown-term": "no concept has this label - add it to the vocabulary?",
           "implied": "only implied, on {} - does the work really count?",
           "broader-held": "only something broader is held, on {} - is there narrower work?",
           "tag-only": "tagged on {}, but no confirmed bullet shows it"}
    for q in r["questions"]:
        out.append(f"- **{q['kind']}** {q['requirement']}: "
                   + ask[q["kind"]].format(" or ".join(q["detail"]) if q["kind"] == "ambiguous"
                                           else ", ".join(q["detail"])))
    if not r["questions"]:
        out.append("None: every requirement is matched with confirmed evidence, or missing.")
    return "\n".join(out) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2
    options = {}
    for flag in ("--cover", "--today"):
        if flag in argv:
            at = argv.index(flag)
            if at + 1 >= len(argv):
                print(f"{flag} needs a value")
                return 2
            options[flag] = argv[at + 1]
            del argv[at:at + 2]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if len(argv) != 1:
        print("usage: jsk match <applications/<dir>/posting.ttl> [--cover N] [--json] "
              "[--today YYYY-MM-DD]")
        return 2
    try:
        budget = int(options.get("--cover", COVER))
        today = (datetime.date.fromisoformat(options["--today"]) if "--today" in options
                 else datetime.date.today())
    except ValueError:
        print("--cover takes a whole number and --today a YYYY-MM-DD date")
        return 2
    if budget < 1:
        print("--cover takes a whole number of at least 1")
        return 2
    posting = argv[0]
    root = workspace_of(posting)
    if root is None or not os.path.isfile(posting):
        print(f"{posting}: not a posting.ttl inside an applications/<dir>/ folder of a workspace")
        return 2

    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk match needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ..gates.validate_urs import show
    from . import ontology as O
    from . import store as S

    store = S.load(root)
    if store.fails():
        rep = store.report()
        print(f"FAIL  the workspace has {len(rep.fails)} failures - fix them before matching:")
        show(rep.fails, "FAIL", 25)
        return 1
    posts = [iri for iri in store.homes if O.class_of(iri) == "Posting"
             and store.file_of(iri) == S.file_name(posting, store.root)]
    if len(posts) != 1:
        print(f"{posting}: holds no posting")          # the cardinality rule makes this rare
        return 1
    r = result(store, posts[0], today, budget)
    print(json.dumps(r, indent=2, ensure_ascii=False) if as_json else markdown(r), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`src/jsk/cli.py`:

```diff
diff --git a/src/jsk/cli.py b/src/jsk/cli.py
index 55c2b4c..2c8e4ea 100644
--- a/src/jsk/cli.py
+++ b/src/jsk/cli.py
@@ -14,6 +14,7 @@ will be. This exists so that nobody has to remember every name to get started.
     jsk doctor                  what works on this machine
     jsk new PATH --name NAME    scaffold user-knowledgebase.md and applications/
     jsk index KB [--rank POST]  a line-pointing overview of the knowledge base, ranked
+    jsk match POSTING.ttl       a posting against the graph record, through the vocabulary
     jsk validate RECORD.json    the record gate, before anything renders
     jsk render RECORD [...]     one record to a PDF and plain text
     jsk preview RECORD --out D  the same record in every template, to pick a look
@@ -50,6 +51,7 @@ from .cliutil import wants_help
 SIMPLE = {
     "new": ("kb.py", "scaffold an empty knowledge base"),
     "index": ("kbindex.py", "overview the knowledge base; rank it against a posting"),
+    "match": ("match.py", "a posting matched against the graph record, through the vocabulary"),
     "render": ("render_resume.py", "one record to .tex/PDF plus .txt"),
     "preview": ("preview_templates.py", "one record in every template, side by side"),
     "fit": ("fit_pages.py", "fit a render to a page budget"),
@@ -101,6 +103,7 @@ SUBPACKAGE = {
     "check_ats.py": "gates",
     "check_prose.py": "gates",
     "validate_urs.py": "gates",
+    "match.py": "graph",
 }
 
 
```

In `src/jsk/preflight.py`, change the end of `GRAPH_MODULES` to `"graph.rules", "graph.store", "graph.queries", "graph.match"]`.

- [ ] **Step 3: The plugin surface**

`tests/test_plugin_surface.py` requires `match` in SKILL.md and `docs/SCRIPTS.md`. The SKILL.md row costs about 17 tokens. Two phrases elsewhere give the room back with no content lost, so the 6,000 ceiling holds (5,997):

`plugins/jsk/skills/jsk/SKILL.md`:

```diff
diff --git a/plugins/jsk/skills/jsk/SKILL.md b/plugins/jsk/skills/jsk/SKILL.md
index 451c4f2..7213c43 100644
--- a/plugins/jsk/skills/jsk/SKILL.md
+++ b/plugins/jsk/skills/jsk/SKILL.md
@@ -88,12 +88,13 @@ It reads records and rendered files, never `user-knowledgebase.md`. `jsk --help`
 | `jsk doctor [--quick]` | what this machine can do and what each gap disables |
 | `jsk new <path> --name "Name"` | an empty `user-knowledgebase.md` and `applications/` |
 | `jsk index <kb> [--rank <posting.md>]` | every section and entry with its lines; the ranking, computed |
+| `jsk match <posting.ttl>` | a posting matched through the vocabulary |
 | `jsk validate <resume.json>` | the record gate |
 | `jsk render <resume.json> --out DIR --view ID --pdf [--ats-max] [--template N]` | record to `.tex`/PDF and `.txt` |
 | `jsk preview <resume.json> --out DIR` | every template, with page counts |
 | `jsk check <file> [--strict] [--only parse\|prose]` | the parse and prose gates on one file |
 | `jsk gates <out-dir> [--record R] [--pages N]` | record, parse and prose gates together |
-| `jsk ship <resume.json> --out DIR --view ID [--pages N]` | validate, render and gates in one run; stops at the first failure |
+| `jsk ship <resume.json> --out DIR --view ID [--pages N]` | validate, render and gates; stops at the first failure |
 | `jsk fit <resume.tex> --target-pages 2` | fits the render to a page budget |
 | `jsk freeze <app-dir> --submitted DATE\|false --channel TEXT` | refuses unless the gates pass, then writes `application.md` |
 
@@ -150,7 +151,7 @@ Every claim carries `status`: `confirmed` (they said it, or a source document do
 - **Say why**, flag every inference, and offer options with a recommendation.
 - **Tell them where they fall short.** Being flattered costs interviews.
 - **Append a dated row to `log.md`**, beside the knowledge base, at the end of every session. Record your own earlier mistakes as
-  corrections rather than editing them away.
+  corrections, never as edits.
 
 Save deliverables beside the knowledge base (Claude Code) or in the outputs folder (Cowork), and
 tell them the path.
```

`docs/SCRIPTS.md`:

````diff
diff --git a/docs/SCRIPTS.md b/docs/SCRIPTS.md
index 3b57cda..5a7c206 100644
--- a/docs/SCRIPTS.md
+++ b/docs/SCRIPTS.md
@@ -19,6 +19,7 @@ document somebody can send.
 jsk doctor                       # what works on this machine
 jsk new ./my-career --name "Your Name"
 jsk index user-knowledgebase.md --rank applications/<dir>/posting.md
+jsk match applications/<dir>/posting.ttl   # the same question, over the graph record
 jsk validate resume.json         # the record gate
 jsk render resume.json --out . --view view_default --pdf
 jsk check resume.pdf             # both document gates, one pass
@@ -121,6 +122,34 @@ parse quietly would score as absent evidence on every posting.
 
 ## The record
 
+### `jsk match`
+
+The `jsk.graph.match` module, over the queries in `jsk.graph.queries`.
+
+```bash
+jsk match applications/<dir>/posting.ttl                 # the four sections, as Markdown
+jsk match applications/<dir>/posting.ttl --cover 2       # a cover of at most two projects
+jsk match applications/<dir>/posting.ttl --json --today 2026-09-24
+```
+
+The graph record's `jsk index --rank`: a posting's requirements joined with the career through the
+vocabulary - the shipped `jsk/data/vocabulary.ttl` and the knowledge base's own additions. Reads the
+whole workspace the posting sits in (`career/kb.ttl`, `applications/*/`) and validates it first;
+any FAIL is printed and nothing is matched. Needs pyoxigraph, a dependency of the package.
+
+**Requirements** puts each one in a bucket: `matched` (a project holds the concept, or a narrower
+one within two hops - `via c:aks, 1 hop`), `near` (only an `implies` path, for a required one, or
+only something broader), `missing`, `ambiguous` (the label names several concepts; the analyst
+answers with `j:concept`), `candidate` (it names none), `implicit`. Evidence per project is
+`confirmed` (a confirmed bullet shows it), `unconfirmed` or `tag` (only the project's tags say so).
+**Ranking** scores exactly as `jsk index --rank` does. **Cover** is the smallest set of projects,
+at most `--cover` (default 3), carrying every required requirement anything carries. **Questions**
+are derived from the gaps, never invented.
+
+Exit 0 with the result - missing requirements included, since this is an assessment, not a gate;
+1 when the workspace has a FAIL; 2 called wrong, or a path that is not
+`applications/<dir>/posting.ttl`.
+
 ### `jsk validate`
 
 The `jsk.gates.validate_urs` module.
````

- [ ] **Step 4: Run everything**

Run: `python -m pytest tests -n auto -q -o addopts=` and `python -m ruff check src tests`
Expected: `526 passed, 2 skipped`, and `All checks passed!`.

Run: `jsk match tests/match_fixtures/applications/contoso/posting.ttl --today 2026-09-24`
Expected: exit 0, with the four sections. It opens:
```
# Match - Platform Engineer at Contoso (k:post_contoso)

5 required, 4 preferred, 1 implicit. 5 matched, 2 near, 1 ambiguous, 1 candidate, 1 implicit.
The workspace has 1 warning; none changes the match.
```

- [ ] **Step 5: Commit**

```bash
git add src/jsk/graph/match.py src/jsk/cli.py src/jsk/preflight.py plugins/jsk/skills/jsk/SKILL.md docs/SCRIPTS.md tests/test_cli.py
git commit -m "feat: jsk match - a posting against the graph record, through the vocabulary"
```
