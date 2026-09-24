# Graph core (P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `src/jsk/graph/`, a package that parses, validates, canonically writes and loads the Turtle graph record. No command changes.

**Architecture:** `ontology.py` defines the format as data. `io.py` reads files, `writer.py` writes them canonically, `shapes.py` holds the per-file rules generated from the ontology, `rules.py` holds the SPARQL rules over the whole workspace, and `store.py` loads a workspace into one in-memory Oxigraph store. pyoxigraph is imported lazily inside functions, never at module top.

**Tech Stack:** Python 3.10+, pyoxigraph 0.5.x (Turtle parsing, SPARQL 1.1), unittest run by pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-24-graph-core-design.md`, which applies phase P1 of `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md`.

**This code has been run.** Every module and test below was built and run in a scratch copy of the package on 2026-09-24 (Windows 11, Python 3.13.1, pyoxigraph 0.5.11): 64 tests and 630 subtests pass, ruff is clean, and the Task 4 state (no tier 2 yet) passes on its own. Two tests were also broken on purpose to prove they catch real faults: the writer's trailing-quote escape (65 failures) and a one-directional `wall-crossed` query (caught by `test_a_wall_holds_whichever_side_declares_it`). Copy the code as written. If a step's result differs from the one stated, stop and report it; don't adjust the test to match.

## Global Constraints

- `requires-python = ">=3.10"`; `preflight.MIN_PYTHON = (3, 10)`.
- `dependencies = ["pyoxigraph>=0.5.11,<0.6"]`, the only hard dependency. Everything else stays optional.
- pyoxigraph is imported inside functions only. `jsk.graph.ontology` must import without pyoxigraph (a test checks this).
- `preflight.py` stays standard-library only; it probes pyoxigraph with `importlib.util.find_spec`.
- Namespaces: `j: <tag:jsk,2026:ns#>`, `k: <tag:jsk,2026:id/>`, `c: <tag:jsk,2026:concept/>`, `op: <tag:jsk,2026:op#>`. Never `https://jsk.dev/`.
- Written files are UTF-8 with no BOM, LF only, and end in exactly one newline. `*.ttl` and `*.trig` are `text eol=lf` in `.gitattributes`.
- Findings go through `jsk.gates.validate_urs.Report`; each one names `file:line id`, a detail and a fix.
- No CLI, `kbindex.py`, plugin or docs change in P1. The existing suite must pass unmodified.
- Add a module to `preflight.GRAPH_MODULES` only in the task that creates it; listing it earlier turns `jsk doctor` BLOCKED.
- Match the repo's test style: `unittest.TestCase` classes, run by pytest, with the test directory on the path (`from fixtures import …` already works; so will `from graphgen import …`).
- Line length is 100 (ruff).

## Review Focus

These inputs are ones the spec implies but no test would exercise without being told to. Each one has a pinning test in the task that owns the code:

- **An application folder named with a space or non-ASCII characters** (`applications/Acme Platform é/`): it must load, and findings name the path as written. A named graph is an IRI, so the path is percent-encoded. That bug was found while drafting. Tested in Task 4 by `test_a_folder_name_with_a_space_or_accent_loads`.
- **An empty or header-less `kb.ttl`, or a `posting.ttl` holding two postings:** each is a `cardinality` FAIL naming the file, not a clean load. Also found while drafting. Tested in Task 4 by `test_an_empty_kb_is_not_a_valid_one` and `test_one_posting_per_posting_file`.
- **A file saved by a Windows editor (CRLF, BOM, tab indentation):** it reads the same and rewrites to canonical bytes. Tested in Task 3 by `test_a_windows_editor_crlf_bom_and_tabs`.
- **The same subject written in two blocks of one file** (a hand edit appended further down): the writer merges them into one block. Tested in Task 3 by `test_a_subject_written_in_two_places_becomes_one_block`.
- **SPARQL-style `PREFIX`, full IRIs and a stray `@prefix ex:` in a hand edit:** the rewrite uses canonical CURIEs and drops the stray prefix. Tested in Task 3 by `test_sparql_style_prefixes_full_iris_and_stray_prefixes`.

## File structure

| File | Responsibility |
|---|---|
| `src/jsk/graph/__init__.py` | the package docstring: what each module is for |
| `src/jsk/graph/ontology.py` | the format as data: namespaces, enums, classes and their predicates, sections, id patterns (standard library only) |
| `src/jsk/graph/io.py` | reads a file: its quads, where each subject starts, and the hand comments a rewrite would drop; `GraphError` |
| `src/jsk/graph/writer.py` | the canonical Turtle writer |
| `src/jsk/graph/shapes.py` | `Finding`, and tier 1: the per-file rules generated from the ontology |
| `src/jsk/graph/rules.py` | tier 2: the SPARQL rules over the whole workspace |
| `src/jsk/graph/store.py` | finds and loads a workspace, derives types, runs both tiers, builds the counts-as closure |
| `src/jsk/data/vocabulary.ttl` | a seed of shipped Technology concepts (P2 fills it out) |
| `tests/graph_fixtures/…` | a valid workspace: `career/kb.ttl`, `career/log.ttl`, one application directory |
| `tests/graphgen.py` | seeded random valid graphs for the writer's property tests |
| `tests/test_graph_{ontology,io,writer,shapes,rules,store,budget}.py` | one test file per module, plus the budget |

---

### Task 1: Packaging, the Python floor, and the ontology

**Files:**
- Modify: `pyproject.toml` (`requires-python`, `dependencies` and the comment above it)
- Modify: `.gitattributes` (append)
- Modify: `src/jsk/preflight.py` (`MIN_PYTHON`, `GRAPH_MODULES`, `INSTALL`, two checks, `REQUIRED`)
- Create: `src/jsk/graph/__init__.py`, `src/jsk/graph/ontology.py`
- Test: `tests/test_graph_ontology.py`; Modify: `tests/test_preflight.py` (one new class)

**Interfaces:**
- Consumes: `jsk.kbindex.SENIORITY` and `jsk.urs.resolve.PROVENANCE_RANK`, read only by the tests.
- Produces, in `jsk.graph.ontology`:
  - constants `J, K, C, OP, XSD, RDF_TYPE, DERIVED, PREFIXES, CHANGESET_PREFIXES, FORMAT, OPS, OP_BASE`;
  - dataclasses `Lit(types, pattern, lo, hi)`, `Enum(name)`, `Ref(classes, may_dangle)`, `Concept(classes)`, `Pred(name, obj, card, doc, claim, section)`, `Class(name, prefix, kinds, section, lines, doc, claims)`, where `Class.preds` is a `{name: Pred}` dict that includes the common `retired`, `reason` and `note`, plus `provenance` when `claims`;
  - `STR, TEXT, DATE, INT, BOOL, NUM, YEARMONTH, ISO2, SHA256, URL`;
  - `ENUMS`, `ANY`, `CLASSES`, `BY_NAME`, `BY_PREFIX`, `SECTIONS`, `ALL_BANNERS`, `HEADS`, `FILE_KINDS`;
  - the regexes `ID`, `CONCEPT_SLUG`, `POSITIONAL`;
  - `kind_of(path) -> str | None`, `class_of(iri) -> str | None`, `norm(label) -> str`.

- [ ] **Step 1: Install pyoxigraph into your environment**

Run: `python -m pip install "pyoxigraph>=0.5.11,<0.6"`
Expected: `Successfully installed pyoxigraph-0.5.11` (or "already satisfied"). Later tasks need it. Once Step 9 edits `pyproject.toml`, `pip install -e ".[dev]"` installs it too.

- [ ] **Step 2: Write the failing ontology test**

Create `tests/test_graph_ontology.py`:

```python
"""The format's one definition is internally consistent."""
import re
import unittest

from jsk.graph import ontology as O


class OntologyTests(unittest.TestCase):
    def test_every_predicate_is_documented_and_typed(self):
        for cls in O.CLASSES:
            for p in cls.preds.values():
                with self.subTest(cls=cls.name, pred=p.name):
                    self.assertTrue(p.doc.strip())
                    self.assertIn(p.card, ("1", "?", "*", "+"))
                    self.assertIsInstance(p.obj, (O.Lit, O.Enum, O.Ref, O.Concept))
                    if isinstance(p.obj, O.Enum):
                        self.assertIn(p.obj.name, O.ENUMS)
                    if isinstance(p.obj, O.Ref) and p.obj.classes != O.ANY:
                        for target in p.obj.classes:
                            self.assertIn(target, O.BY_NAME)
                    if p.section:
                        self.assertIn(p.section, O.SECTIONS[cls.kinds[0]])

    def test_enums_are_nonempty_and_valid_local_names(self):
        for name, values in O.ENUMS.items():
            with self.subTest(enum=name):
                self.assertTrue(values)
                self.assertEqual(len(values), len(set(values)))
                for v in values:
                    self.assertRegex(v, r"^[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9]$")

    def test_prefixes_are_unique_and_every_class_has_a_home(self):
        prefixes = [c.prefix for c in O.CLASSES if c.prefix]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for cls in O.CLASSES:
            with self.subTest(cls=cls.name):
                self.assertTrue(cls.kinds)
                for kind in cls.kinds:
                    self.assertIn(kind, O.SECTIONS)
                    self.assertTrue(cls.section is None or cls.section in O.SECTIONS[kind])

    def test_each_head_class_lives_in_its_file_kind(self):
        for kind, name in O.HEADS.items():
            self.assertIn(kind, O.BY_NAME[name].kinds)

    def test_no_predicate_appears_twice_in_a_class(self):
        for cls in O.CLASSES:
            names = [p.name for line in cls.lines for p in line]
            self.assertEqual(len(names), len(set(names)), cls.name)

    def test_claim_classes_carry_provenance(self):
        for cls in O.CLASSES:
            has_claim = any(p.claim for p in cls.preds.values())
            with self.subTest(cls=cls.name):
                self.assertEqual("provenance" in cls.preds, cls.claims)
                if has_claim:
                    self.assertTrue(cls.claims, "a class with claim predicates needs provenance")

    def test_seniority_matches_the_markdown_reader(self):
        from jsk.kbindex import SENIORITY
        self.assertEqual(tuple(SENIORITY), O.ENUMS["seniority"])

    def test_provenance_matches_the_renderer(self):
        from jsk.urs.resolve import PROVENANCE_RANK
        self.assertEqual(set(PROVENANCE_RANK), set(O.ENUMS["provenance"]))

    def test_class_of(self):
        cases = {O.K + "kb": "KB", O.K + "person": "Person", O.K + "prj_clinical_events": "Project",
                 O.K + "met_team": "Metric", O.K + "met_team.v2": "MetricVersion",
                 O.K + "prj_x.v1": None, O.K + "zzz_x": None, O.K + "Prj_x": None,
                 O.C + "kafka": "Concept", "https://example.com/x": None}
        for iri, name in cases.items():
            with self.subTest(iri=iri):
                self.assertEqual(O.class_of(iri), name)

    def test_kind_of(self):
        self.assertEqual(O.kind_of("career/kb.ttl"), "kb")
        self.assertEqual(O.kind_of("applications\\a\\posting.ttl"), "posting")
        self.assertEqual(O.kind_of("change.trig"), "changeset")
        self.assertIsNone(O.kind_of("career/notes.ttl"))

    def test_norm(self):
        self.assertEqual(O.norm("  Azure  AI\tFoundry "), "azure-ai-foundry")

    def test_ontology_does_not_import_pyoxigraph(self):
        import subprocess
        import sys
        code = "import sys, jsk.graph.ontology; print('pyoxigraph' in sys.modules)"
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "False", out.stderr)

    def test_the_id_pattern_refuses_what_it_should(self):
        self.assertTrue(re.fullmatch(O.ID, "ach_clinical_events_led_migration"))
        self.assertTrue(O.POSITIONAL.search("ach_clinical_events_2"))
        self.assertFalse(O.CONCEPT_SLUG.fullmatch("SQL_server"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_ontology.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'jsk.graph'`.

- [ ] **Step 4: Create the package and the ontology**

Create `src/jsk/graph/__init__.py`:

```python
"""The graph record: the career and its applications as Turtle, loaded into Oxigraph.

ontology - the format as data     io     - reading a file
writer   - the canonical writer   shapes - the rules and their findings
store    - loading a workspace
"""
```

Create `src/jsk/graph/ontology.py`:

```python
"""The graph record's format, as data: every class, predicate and enum, in one place.

Everything else reads these tables - the writer takes its section order, subject order and
line layout from them, and the tier-1 rules in shapes.py are generated from them - so the
format has exactly one definition. docs/superpowers/specs/2026-09-24-graph-core-design.md
is the prose version.

Standard library only: importing this must not import pyoxigraph.
"""
import re
from dataclasses import dataclass, field

J = "tag:jsk,2026:ns#"
K = "tag:jsk,2026:id/"
C = "tag:jsk,2026:concept/"
OP = "tag:jsk,2026:op#"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# Where derived triples live in the store. Never written to a file.
DERIVED = J + "derived"

# The writer's prefix block, in this order, always complete. `op` only in changesets.
PREFIXES = (("j", J), ("k", K), ("c", C), ("xsd", XSD))
CHANGESET_PREFIXES = PREFIXES + (("op", OP),)

FORMAT = 3

# The reserved graphs of a changeset (TriG). P1 names them; P3 gives them meaning.
OPS = ("set", "add", "retire", "delete")
OP_BASE = "base"


# --- object kinds ----------------------------------------------------------------------

@dataclass(frozen=True)
class Lit:
    """A literal. `types` are the xsd datatypes allowed; `pattern` must match the
    lexical form in full whatever the type; `lo`/`hi` bound a number."""
    types: tuple = ("string",)
    pattern: str = None
    lo: float = None
    hi: float = None


@dataclass(frozen=True)
class Enum:
    """One of ENUMS[name], written as a j: individual."""
    name: str


@dataclass(frozen=True)
class Ref:
    """A k: id of one of these classes; "*" is any class. `may_dangle` for the log,
    whose entries name ids that may since have been deleted."""
    classes: tuple
    may_dangle: bool = False


@dataclass(frozen=True)
class Concept:
    """A c: concept of one of these concept classes."""
    classes: tuple = ("Capability", "Domain", "Technology")


@dataclass(frozen=True)
class Pred:
    name: str
    obj: object
    card: str          # "1" required, "?" optional, "*" zero or more, "+" one or more
    doc: str
    claim: bool = False
    section: str = None   # only when the predicate is written in another section than its class


@dataclass(frozen=True)
class Class:
    name: str
    prefix: str        # "prj" for k:prj_x; "=kb" for the singleton k:kb; None for concepts
    kinds: tuple       # the file kinds it may be defined in
    section: str       # None: the file's header subject, written before the first banner
    lines: tuple       # tuples of Pred: each inner tuple is one line of the written subject
    doc: str
    claims: bool = False   # carries j:provenance
    preds: dict = field(init=False, compare=False)

    def __post_init__(self):
        common = [(Pred("retired", DATE, "?", "the day it stopped belonging on a resume"),
                   Pred("reason", STR, "?", "why it was retired; required with retired")),
                  (Pred("note", TEXT, "*", "free text: anything the ontology has no field for"),)]
        if self.claims:
            common.append((Pred("provenance", Enum("provenance"), "1",
                                "confirmed, inferred, needs-verification or disputed"),))
        lines = tuple(self.lines) + tuple(common)
        object.__setattr__(self, "lines", lines)
        object.__setattr__(self, "preds", {p.name: p for line in lines for p in line})


STR = Lit()
TEXT = Lit()                                   # may hold newlines; written """…"""
DATE = Lit(("date",))
INT = Lit(("integer",))
BOOL = Lit(("boolean",))
NUM = Lit(("integer", "decimal"))
YEARMONTH = Lit(("string",), r"\d{4}(-(0[1-9]|1[0-2]))?")
ISO2 = Lit(("string",), r"[A-Z]{2}")
SHA256 = Lit(("string",), r"[0-9a-f]{64}")
URL = Lit(("string",), r"\S+")

# URS values wherever URS defines the thing; kbindex.SENIORITY for seniority.
ENUMS = {
    "provenance": ("confirmed", "inferred", "needs-verification", "disputed"),
    "workMode": ("onsite", "hybrid", "remote"),
    "authKind": ("citizen", "permanent", "employment-visa", "residence", "student",
                 "working-holiday", "none"),
    "authorization": ("held", "expired", "eligible", "requires-sponsorship"),
    "languageScheme": ("cefr", "ilr", "jlpt", "ielts", "reported"),
    "conceptClass": ("Capability", "Domain", "Technology"),
    "relationship": ("employer", "prospect", "both"),
    "state": ("ended", "ongoing", "unknown"),
    "seniority": ("architecture-ownership", "product-ownership", "platform-design",
                  "team-leadership", "technical-ownership", "hands-on-senior", "hands-on",
                  "junior"),
    "change": ("hire", "promotion", "lateral", "title-change"),
    "engagementKind": ("employment", "contract", "freelance", "internship", "volunteer",
                       "break"),
    "direction": ("increase", "decrease"),
    "metricKind": ("absolute", "delta", "ratio", "duration", "rank", "count"),
    "confidence": ("measured", "estimated", "reported"),
    "educationLevel": ("isced-5", "isced-6", "isced-7", "isced-8"),
    "credentialState": ("active", "expired", "lapsed"),
    "openSourceRole": ("maintainer", "contributor", "author"),
    "necessity": ("required", "preferred", "implicit"),
    "eventKind": ("submitted", "acknowledged", "screen-scheduled", "screen-done",
                  "interview-scheduled", "interview-done", "onsite-scheduled", "onsite-done",
                  "offer", "offer-accepted", "rejected", "withdrawn", "no-response",
                  "offer-declined", "follow-up-sent", "note", "referral", "recruiter-contact"),
    "logBy": ("apply", "confirm", "adopt", "migrate", "fmt"),
}

ANY = ("*",)

CLASSES = (
    # --- kb.ttl ------------------------------------------------------------------------
    Class("KB", "=kb", ("kb",), None, (
        (Pred("format", Lit(("integer",), lo=FORMAT, hi=FORMAT), "1", "the format revision"),
         Pred("name", STR, "1", "whose career this is"),
         Pred("updated", DATE, "1", "the day the last change landed")),
    ), "the file's header"),
    Class("Person", "=person", ("kb",), "Identity", (
        (Pred("fullName", STR, "1", "the name as it heads a resume", claim=True),
         Pred("givenName", STR, "?", "given name"),
         Pred("familyName", STR, "?", "family name")),
        (Pred("headline", STR, "?", "the one-line professional title", claim=True),),
        (Pred("city", STR, "?", "city"), Pred("region", STR, "?", "state or region"),
         Pred("country", ISO2, "?", "ISO 3166-1 alpha-2"),
         Pred("workMode", Enum("workMode"), "?", "onsite, hybrid or remote")),
        (Pred("email", STR, "*", "an email address"),),
        (Pred("phone", STR, "*", "a phone number"),),
        (Pred("linkedin", STR, "*", "a LinkedIn profile"),),
        (Pred("github", STR, "*", "a GitHub profile"),),
        (Pred("website", STR, "*", "a personal site"),),
        (Pred("primary", STR, "?", "the contact value to lead with; one of those above"),),
        (Pred("positioning", TEXT, "?", "what they are for, in their own words",
              section="Positioning"),),
    ), "the person", claims=True),
    Class("WorkAuthorization", "auth", ("kb",), "Work authorization and languages", (
        (Pred("jurisdiction", STR, "1", "where it applies: a country code, or EU and so on"),
         Pred("kind", Enum("authKind"), "1", "the basis", claim=True),
         Pred("authorization", Enum("authorization"), "1", "its status", claim=True),
         Pred("validUntil", DATE, "?", "when it lapses")),
    ), "a right to work", claims=True),
    Class("Language", "lang", ("kb",), "Work authorization and languages", (
        (Pred("language", Lit(("string",), r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*"), "1",
              "a BCP 47 tag"),
         Pred("native", BOOL, "?", "a first language"),
         Pred("scheme", Enum("languageScheme"), "?", "the scale level is on"),
         Pred("level", STR, "?", "the level on that scale")),
    ), "a spoken language", claims=True),
    Class("Concept", None, ("kb", "vocabulary"), "Vocabulary", (
        (Pred("label", STR, "*", "a name it goes by; matched after normalising"),),
        (Pred("former", STR, "*", "a name it used to go by"),),
        (Pred("isA", Concept(), "*", "counts as this broader concept"),
         Pred("partOf", Concept(), "*", "counts as the whole it is part of"),
         Pred("implies", Concept(), "*", "suggests this; never satisfies a required one")),
        (Pred("distinct", Concept(), "*", "never the same thing, whatever the names say"),),
    ), "a matching term: capability, domain or technology"),
    Class("Organisation", "org", ("kb",), "Organisations", (
        (Pred("name", STR, "1", "the organisation's name", claim=True),),
        (Pred("relationship", Enum("relationship"), "1", "employer, prospect or both"),
         Pred("industry", Concept(("Domain",)), "*", "its industries"),
         Pred("size", STR, "?", "headcount band, e.g. 1001-5000")),
    ), "an employer or client", claims=True),
    Class("Position", "pos", ("kb",), "Roles", (
        (Pred("organisation", Ref(("Organisation",)), "1", "where"),),
        (Pred("title", STR, "1", "the title as the employer wrote it", claim=True),
         Pred("functionalTitle", STR, "?", "renders in parentheses; never replaces title")),
        (Pred("start", YEARMONTH, "1", "YYYY-MM or YYYY", claim=True),
         Pred("end", YEARMONTH, "?", "omitted while ongoing", claim=True),
         Pred("state", Enum("state"), "1", "ended, ongoing or unknown")),
        (Pred("seniority", Enum("seniority"), "1", "one of the closed eight", claim=True),
         Pred("change", Enum("change"), "?", "how they came into it"),
         Pred("engagementKind", Enum("engagementKind"), "?", "employment unless stated")),
    ), "a job title held", claims=True),
    Class("Project", "prj", ("kb",), "Projects", (
        (Pred("name", STR, "1", "the project's name", claim=True),),
        (Pred("position", Ref(("Position",)), "?", "the role it was done in"),),
        (Pred("strength", Lit(("integer",), lo=1, hi=5), "1", "evidence quality, 5 flagship"),
         Pred("recency", Lit(("integer",), lo=1950, hi=2100), "1", "the last year worked on"),
         Pred("seniority", Enum("seniority"), "?", "the level it shows", claim=True)),
        (Pred("domain", Concept(("Domain",)), "*", "the domains it was in"),),
        (Pred("uses", Concept(), "*", "tags: what it involved; not evidence"),),
        (Pred("headlineMetric", Ref(("Metric",)), "?", "the number it leads with"),
         Pred("noneQuantified", BOOL, "?", "true when no number exists")),
        (Pred("problem", TEXT, "?", "the problem, in prose"),),
        (Pred("decision", TEXT, "?", "what they decided, in prose"),),
        (Pred("outcome", TEXT, "?", "what changed, in prose"),),
    ), "an engagement or product: the evidence", claims=True),
    Class("Achievement", "ach", ("kb",), "Projects", (
        (Pred("project", Ref(("Project",)), "1", "the project it belongs to"),
         Pred("rank", Lit(("integer",), lo=1), "1", "its order under the project")),
        (Pred("text", TEXT, "1", "the bullet, written once and reused", claim=True),),
        (Pred("cites", Ref(("Metric",)), "*", "the metrics whose numbers it states"),
         Pred("shows", Concept(), "*", "what it is evidence of", claim=True)),
    ), "a bullet", claims=True),
    Class("Metric", "met", ("kb",), "Metrics", (
        (Pred("subject", STR, "1", "what is measured"),
         Pred("unit", STR, "?", "its unit"),
         Pred("direction", Enum("direction"), "?", "which way is better")),
    ), "a measured quantity; its numbers live on its versions"),
    Class("MetricVersion", "met.v", ("kb",), "Metrics", (
        (Pred("of", Ref(("Metric",)), "1", "the metric it is a version of"),),
        (Pred("baseline", NUM, "?", "the value before", claim=True),
         Pred("value", NUM, "1", "the value", claim=True),
         Pred("kind", Enum("metricKind"), "?", "absolute, delta, ratio and so on", claim=True)),
        (Pred("confidence", Enum("confidence"), "1", "measured, estimated or reported"),
         Pred("source", STR, "?", "where the number comes from")),
        (Pred("validFrom", DATE, "?", "when it became true"),
         Pred("validUntil", DATE, "?", "when a later version replaced it")),
    ), "one value of a metric over a period", claims=True),
    Class("Skill", "skill", ("kb",), "Skills", (
        (Pred("name", STR, "1", "the display name"),
         Pred("category", STR, "1", "the group it is shown under"),
         Pred("rank", Lit(("integer",), lo=1), "?", "display order in its category")),
        (Pred("alias", STR, "*", "other names an ATS may look for"),),
    ), "a display skill"),
    Class("Education", "edu", ("kb",), "Education", (
        (Pred("institution", STR, "1", "where", claim=True),),
        (Pred("qualification", STR, "1", "the award", claim=True),
         Pred("field", STR, "?", "the field of study"),
         Pred("level", Enum("educationLevel"), "?", "ISCED level")),
        (Pred("start", YEARMONTH, "?", "YYYY-MM or YYYY"),
         Pred("end", YEARMONTH, "?", "YYYY-MM or YYYY")),
        (Pred("gradeScheme", STR, "?", "the grading scheme"),
         Pred("gradeValue", Lit(("integer", "decimal", "string")), "?", "the grade")),
    ), "a qualification", claims=True),
    Class("Credential", "cred", ("kb",), "Certifications", (
        (Pred("name", STR, "1", "the credential", claim=True),),
        (Pred("issuer", STR, "1", "who issued it", claim=True),
         Pred("issued", YEARMONTH, "?", "YYYY-MM or YYYY", claim=True),
         Pred("expires", YEARMONTH, "?", "YYYY-MM or YYYY"),
         Pred("credentialState", Enum("credentialState"), "1", "active, expired or lapsed")),
        (Pred("url", URL, "?", "where it can be verified"),),
    ), "a certification actually earned", claims=True),
    Class("OpenSource", "os", ("kb",), "Open source", (
        (Pred("name", STR, "1", "the project"),),
        (Pred("url", URL, "1", "where the code is"),
         Pred("role", Enum("openSourceRole"), "1", "their part in it", claim=True)),
    ), "public code", claims=True),
    Class("Question", "q", ("kb",), "Open questions", (
        (Pred("about", Ref(ANY), "1", "the entry it is about"),),
        (Pred("question", STR, "1", "the question, ready to ask aloud"),),
        (Pred("asked", DATE, "1", "when it was raised"),
         Pred("answered", DATE, "?", "when it was answered")),
    ), "the gap queue"),
    # --- posting.ttl -------------------------------------------------------------------
    Class("Posting", "post", ("posting",), "Posting", (
        (Pred("company", STR, "1", "the employer advertising"),
         Pred("title", STR, "1", "the advertised title")),
        (Pred("url", URL, "?", "where it was advertised"),),
        (Pred("seniority", Enum("seniority"), "?", "the level it asks for"),
         Pred("domain", Concept(("Domain",)), "*", "its domains")),
        (Pred("captured", DATE, "1", "the day it was saved"),
         Pred("advert", Lit(("string",), r"posting\.md"), "1", "the verbatim advert beside it")),
    ), "a job advertisement"),
    Class("Requirement", "req", ("posting",), "Requirements", (
        (Pred("posting", Ref(("Posting",)), "1", "the posting asking"),),
        (Pred("asked", STR, "1", "the term as the advert wrote it"),
         Pred("necessity", Enum("necessity"), "1", "required, preferred or implicit"),
         Pred("concept", Concept(), "?", "the concept meant, when the label is ambiguous")),
        (Pred("quote", TEXT, "1", "the advert's own words"),),
    ), "one thing a posting asks for"),
    # --- application.ttl ---------------------------------------------------------------
    Class("Application", "app", ("application",), "Application", (
        (Pred("posting", Ref(("Posting",)), "1", "what it answered"),
         Pred("view", STR, "?", "the URS view it rendered")),
        (Pred("submitted", Lit(("date", "boolean"), r"\d{4}-\d{2}-\d{2}|false"), "1",
              "the day it was sent, or false when held back"),
         Pred("channel", STR, "?", "how it was sent")),
        (Pred("document", STR, "*", "a file that was sent"),),
        (Pred("recordSha256", SHA256, "?", "the frozen resume.json's hash"),),
        (Pred("carried", Ref(("Achievement",)), "*", "bullets it sent"),),
        (Pred("carriedVersion", Ref(("MetricVersion",)), "*", "metric versions it sent"),),
    ), "a submission"),
    Class("Event", "evt", ("application",), "Timeline", (
        (Pred("application", Ref(("Application",)), "1", "the application"),),
        (Pred("date", Lit(("date", "string"), r"\d{4}-\d{2}-\d{2}|unknown"), "1",
              "the day it happened, or unknown"),
         Pred("kind", Enum("eventKind"), "1", "the pipeline vocabulary"),
         Pred("channel", STR, "?", "how"),
         Pred("due", DATE, "?", "a date somebody committed to")),
    ), "something that happened to an application"),
    # --- log.ttl -----------------------------------------------------------------------
    Class("LogEntry", "rev", ("log",), "Log", (
        (Pred("revision", Lit(("integer",), lo=1), "1", "counts up from 1"),
         Pred("date", DATE, "1", "the day"),
         Pred("by", Enum("logBy"), "1", "the command that wrote it")),
        (Pred("summary", TEXT, "1", "what changed"),),
        (Pred("touched", Ref(ANY, may_dangle=True), "*", "ids changed"),),
        (Pred("minted", Ref(ANY, may_dangle=True), "*", "ids created"),),
        (Pred("answer", TEXT, "?", "the person's answer, for a confirm"),),
        (Pred("kbSha256", SHA256, "1", "kb.ttl's hash after the change"),),
    ), "one change to the career"),
)

BY_NAME = {c.name: c for c in CLASSES}
BY_PREFIX = {c.prefix: c for c in CLASSES if c.prefix}

# The sections of each file kind, in the order they are written.
SECTIONS = {
    "kb": ("Identity", "Positioning", "Work authorization and languages", "Vocabulary",
           "Organisations", "Roles", "Projects", "Metrics", "Skills", "Education",
           "Certifications", "Open source", "Open questions"),
    "vocabulary": ("Vocabulary",),
    "posting": ("Posting", "Requirements"),
    "application": ("Application", "Timeline"),
    "log": ("Log",),
}
# kb.ttl prints every banner, empty or not: the structure is the contract.
ALL_BANNERS = {"kb"}

# The class each file kind holds exactly one of: what makes the file that kind of file.
HEADS = {"kb": "KB", "posting": "Posting", "application": "Application"}

FILE_KINDS = {"kb.ttl": "kb", "log.ttl": "log", "posting.ttl": "posting",
              "application.ttl": "application", "vocabulary.ttl": "vocabulary"}

SLUG = r"[a-z0-9]+(?:_[a-z0-9]+)*"
ID = re.compile(rf"(?P<prefix>[a-z]+)_(?P<slug>{SLUG})(?:\.v(?P<version>[1-9][0-9]*))?")
CONCEPT_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
POSITIONAL = re.compile(r"_\d+$")


def kind_of(path):
    """The file kind a path holds, from its name; None when it is not a record file."""
    name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith(".trig"):
        return "changeset"
    return FILE_KINDS.get(name)


def class_of(iri):
    """The class a k: id names by its shape, or "Concept" for a c: iri; None when the
    iri is neither. A concept's own class (Capability, ...) is stated in the file."""
    if iri.startswith(C):
        return "Concept"
    if not iri.startswith(K):
        return None
    local = iri[len(K):]
    if local in ("kb", "person"):
        return BY_PREFIX["=" + local].name
    m = ID.fullmatch(local)
    if not m:
        return None
    if m["version"]:
        return "MetricVersion" if m["prefix"] == "met" else None
    cls = BY_PREFIX.get(m["prefix"])
    return cls.name if cls and cls.prefix != "met.v" else None


def norm(label):
    """A label as it is matched: lowercased, whitespace runs turned into `-`."""
    return re.sub(r"\s+", "-", label.strip().lower())
```

- [ ] **Step 5: Run the ontology test to verify it passes**

Run: `python -m pytest tests/test_graph_ontology.py -q`
Expected: `13 passed` (plus subtests).

- [ ] **Step 6: Write the failing preflight test**

In `tests/test_preflight.py`, add this class immediately above the final `if __name__ == "__main__":` block:

```python
class TheGraphRecord(unittest.TestCase):
    """P1 of the graph rewrite: a package of its own, and the engine it runs on."""

    def test_the_graph_package_is_required_like_the_other_packages(self):
        checks, _ = preflight.gather()
        graph = next(c for c in checks if c.name == "graph record package")
        self.assertTrue(preflight.is_required(graph))
        self.assertTrue(graph.ok, graph.disables)

    def test_the_engine_is_a_capability_not_a_blocker(self):
        """Nothing on the render path reads the graph yet, so a machine without the
        engine still renders a resume - it loses the graph record, and says so."""
        checks, _ = preflight.gather()
        engine = next(c for c in checks if c.name == "pyoxigraph")
        self.assertFalse(preflight.is_required(engine))
        self.assertIn("kb.ttl", engine.disables)
        line, note = preflight.hint("pyoxigraph")
        self.assertIn("-m pip install pyoxigraph", line)
        self.assertTrue(note)

    def test_the_floor_is_python_3_10(self):
        self.assertEqual(preflight.MIN_PYTHON, (3, 10))
```

Run: `python -m pytest tests/test_preflight.py -q -k TheGraphRecord`
Expected: 3 failed (`StopIteration` twice, then `(3, 8) != (3, 10)`).

- [ ] **Step 7: Edit `src/jsk/preflight.py`**

Make each of these replacements exactly.

(a) The floor:
```python
MIN_PYTHON = (3, 8)
```
becomes
```python
MIN_PYTHON = (3, 10)
```

(b) Directly below the line `MODULES = ["cli", "cliutil", "kb", "kbindex", "paths"]`, add:
```python
# The graph record (docs/superpowers/specs/2026-09-24-graph-core-design.md). None of
# these imports pyoxigraph at module top, so find_spec answers "is the code here" even on
# a machine without the engine - the engine is its own check below.
GRAPH_MODULES = ["graph", "graph.ontology"]
```

(c) In `INSTALL`, directly above the `"index": {"pip": "markdown-it-py pyyaml",` entry, add:
```python
    "pyoxigraph": {"pip": "pyoxigraph",
                   "note": "The graph engine: reads, validates and queries kb.ttl and the "
                           "applications. A dependency of jsk-resume, so a missing one "
                           "means the install skipped dependencies."},
```

(d) In `gather()`, directly above the line `    missing_gates = present(GATE_MODULES)`, add:
```python
    missing_graph = present(GRAPH_MODULES)
    checks.append(Check(
        "graph record package", not missing_graph,
        disables=f"missing: {', '.join(missing_graph)}" if missing_graph
                 else "", detail=os.path.join(HERE, "graph")))

```

(e) In `gather()`, directly above the comment `    # Optional: a machine without them still renders and gates a resume. What it`, add:
```python
    # Not REQUIRED while nothing on the render path reads the graph: a machine without
    # it still renders and gates a resume from a hand-written record. find_spec, not an
    # import - this module stays standard-library only.
    checks.append(Check(
        "pyoxigraph", importlib.util.find_spec("pyoxigraph") is not None, key="pyoxigraph",
        disables="cannot read or validate the graph record (kb.ttl) - matching and "
                 "career writes are unavailable"))

```

(f) `REQUIRED`:
```python
REQUIRED = {"Python", "modules", "urs renderer package", "gates package",
```
becomes
```python
REQUIRED = {"Python", "modules", "urs renderer package", "gates package", "graph record package",
```

- [ ] **Step 8: Run the preflight tests to verify they pass**

Run: `python -m pytest tests/test_preflight.py -q`
Expected: all pass, the 3 new ones included. `test_the_shipped_install_is_intact` also passes, because the graph package check is `ok`.

- [ ] **Step 9: Edit `pyproject.toml` and `.gitattributes`**

In `pyproject.toml`, change `requires-python = ">=3.8"` to `requires-python = ">=3.10"`, then replace the whole comment block and the line `dependencies = []` beneath it (from `# Deliberately empty. Every dependency this toolchain has is optional and imported at` down to `dependencies = []`) with:

```toml
# One dependency, and only one. Everything else this toolchain uses is optional and
# imported at the point of use, so a bare install still gives a working record gate,
# prose gate and .txt parse gate, and `jsk doctor` still reports on a machine before
# anything optional is installed - preflight.py stays standard-library only.
#
# pyoxigraph is the exception because the graph record (kb.ttl and the applications) is
# the career itself, not a capability layered on top. It ships abi3 wheels for every
# platform jsk supports and has no dependencies of its own (the P0 spike,
# docs/superpowers/experiments/2026-09-24-p0-spike/). The pin is one minor: raising it
# means rerunning the Windows and Linux CI jobs - the lesson LadybugDB taught, whose
# Windows wheels were broken for five releases while Linux passed.
dependencies = ["pyoxigraph>=0.5.11,<0.6"]
```

Append to `.gitattributes`:

```
# The graph record is compared byte for byte - the writer is canonical, and the tests
# check that the fixtures rewrite to themselves. A CRLF checkout would fail those tests
# on Windows only, and would hand a person a file the writer then rewrites in full.
*.ttl text eol=lf
*.trig text eol=lf
```

Run: `python -m pip install -e ".[dev]"` then `jsk doctor --quick`
Expected: the install succeeds, and doctor lists `ok    graph record package` and `ok    pyoxigraph`.

- [ ] **Step 10: Run the whole suite and lint**

Run: `python -m pytest tests -q -n auto` and `python -m ruff check src tests`
Expected: everything passes, and ruff prints `All checks passed!`.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml .gitattributes src/jsk/preflight.py src/jsk/graph/__init__.py src/jsk/graph/ontology.py tests/test_graph_ontology.py tests/test_preflight.py
git commit -m "feat(graph): the ontology, pyoxigraph as the one dependency, Python 3.10 floor"
```

---

### Task 2: Reading a record file

**Files:**
- Create: `src/jsk/graph/io.py`
- Modify: `src/jsk/preflight.py` (`GRAPH_MODULES`)
- Test: `tests/test_graph_io.py`

**Interfaces:**
- Consumes: `ontology.C`, `ontology.K`, `ontology.kind_of`.
- Produces, in `jsk.graph.io`:
  - `GraphError(message, fix, file, line=None, col=None)`, with attributes `.fix .file .line .col`;
  - the dataclass `Parsed(file: str, kind: str, quads: list[pyoxigraph.Quad], lines: dict[str, int], comments: list[tuple[int, str]])`;
  - `normalise(text) -> str` and `parse_text(text, file, kind=None) -> Parsed`, which raises `GraphError` on a syntax error;
  - `parse(path, root=None) -> Parsed`, where `root` makes `file` relative;
  - `subject_lines(text) -> dict` and `comments(text) -> list`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_graph_io.py`:

```python
"""Reading a record file: its triples, where each subject starts, and what a rewrite
would lose. Errors name file:line:column, because a person fixes a hand edit by going
to that line.
"""
import tempfile
import unittest
from pathlib import Path

from jsk.graph import io
from jsk.graph import ontology as O

PFX = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES)


class Reading(unittest.TestCase):
    def test_syntax_error_names_file_line_and_column(self):
        with self.assertRaises(io.GraphError) as cm:
            io.parse_text(PFX + "k:org_x j:name \"A\" ;\n    j:size ,, .\n", "career/kb.ttl")
        e = cm.exception
        self.assertEqual((e.file, e.line), ("career/kb.ttl", 6))
        self.assertIsNotNone(e.col)
        self.assertIn("career/kb.ttl:6:", str(e))

    def test_crlf_and_bom_read_as_lf(self):
        text = "﻿" + (PFX + 'k:org_x j:name """two\r\nlines""" .\r\n')
        parsed = io.parse_text(text, "kb.ttl")
        self.assertEqual(parsed.quads[0].object.value, "two\nlines")

    def test_the_kind_comes_from_the_file_name(self):
        self.assertEqual(io.parse_text(PFX, "applications/a/posting.ttl").kind, "posting")

    def test_subject_lines_point_at_the_first_line_of_each_subject(self):
        text = (PFX + '\nk:met_team j:subject "engineers led" .\n'
                "k:met_team.v1 j:of k:met_team ;\n    j:value 6 .\n\n"
                "c:kafka j:isA c:event-driven-architecture .\n")
        lines = io.parse_text(text, "kb.ttl").lines
        self.assertEqual((lines[O.K + "met_team"], lines[O.K + "met_team.v1"],
                          lines[O.C + "kafka"]), (6, 7, 10))

    def test_comments_are_found_but_banners_and_hashes_in_strings_are_not(self):
        text = (PFX + "# == Skills\n\n# my own note\n"
                'k:skill_dotnet j:name "C# / .NET" ; j:category "language" .  # trailing\n'
                'k:os_x j:name "x" ; j:url <https://x/#frag> .\n'
                'k:prj_x j:problem """A # in prose\nis prose.""" .\n')
        found = io.parse_text(text, "kb.ttl").comments
        self.assertEqual(found, [(7, "# my own note"), (8, "# trailing")])

    def test_a_file_with_no_hash_has_no_comments(self):
        self.assertEqual(io.comments('k:x j:name "y" .\n'), [])

    def test_a_non_utf8_file_is_an_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kb.ttl"
            path.write_bytes(b'k:org_x j:name "caf\xe9" .')
            with self.assertRaises(io.GraphError) as cm:
                io.parse(path)
            self.assertIn("not UTF-8", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_io.py -q`
Expected: `ImportError: cannot import name 'io' from 'jsk.graph'`.

- [ ] **Step 3: Write the reader**

Create `src/jsk/graph/io.py`:

```python
"""Reading a record file: its triples, where each subject is, and what a rewrite would lose.

pyoxigraph is imported inside the functions that need it, never at module top, so a
command that never reads the graph never pays for it (11-12 ms, measured in P0).
"""
import re
from dataclasses import dataclass

from .ontology import C, K, kind_of

# A subject line starts in column 0 with a CURIE; a banner is `# == Section`.
SUBJECT = re.compile(r"^([kc]):([A-Za-z0-9_.\-]+)")
BANNER = re.compile(r"^# == \S.*$")


class GraphError(Exception):
    """A file that could not be read. Carries where, and the fix."""

    def __init__(self, message, fix, file, line=None, col=None):
        super().__init__(message)
        self.fix = fix
        self.file = file
        self.line = line
        self.col = col


@dataclass
class Parsed:
    file: str          # as reported: relative to the workspace root, forward slashes
    kind: str
    quads: list        # pyoxigraph Quads, all in the default graph
    lines: dict        # subject iri -> the first line it starts, 1-based
    comments: list     # (line, text): hand comments a rewrite would drop


def normalise(text):
    """LF only, no BOM: what the writer writes, so what the reader compares against."""
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_text(text, file, kind=None):
    """Parse one file's text. Raises GraphError on a syntax error."""
    import pyoxigraph as ox

    kind = kind or kind_of(file)
    text = normalise(text)
    fmt = ox.RdfFormat.TRIG if kind == "changeset" else ox.RdfFormat.TURTLE
    try:
        quads = list(ox.parse(text.encode("utf-8"), format=fmt))
    except SyntaxError as e:
        raise GraphError(f"{file}:{e.lineno}:{e.offset}: {e.msg}",
                         "fix the syntax there; the rest of the file was not read",
                         file, e.lineno, e.offset) from None
    return Parsed(file, kind, quads, subject_lines(text), comments(text))


def parse(path, root=None):
    """Parse a file on disk; `root` makes the reported name relative to the workspace."""
    import os

    file = os.path.relpath(path, root) if root else str(path)
    file = file.replace("\\", "/")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError as e:
        raise GraphError(f"{file}: not UTF-8 ({e.reason} at byte {e.start})",
                         "save the file as UTF-8", file) from None
    return parse_text(text, file)


def subject_lines(text):
    """{iri: first line} for every subject that starts a line - where a finding points."""
    out = {}
    for n, line in enumerate(text.split("\n"), 1):
        m = SUBJECT.match(line)
        if m:
            local = m.group(2).rstrip(".")
            iri = (K if m.group(1) == "k" else C) + local
            out.setdefault(iri, n)
    return out


# The tokens a `#` can hide in, then a comment. Strings follow Turtle's grammar: a long
# string holds at most two quotes in a row; a short one never spans a line.
TOKENS = re.compile(
    r'"""(?:[^"\\]|\\.|"(?!""))*"""'
    r"|'''(?:[^'\\]|\\.|'(?!''))*'''"
    r'|"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
    r"|<[^>\s]*>"
    r"|(?P<comment>#[^\n]*)", re.S)


def comments(text):
    """(line, text) of every comment that is not a banner.

    Tokenised rather than searched, because `#` inside a string or an IRI is not a
    comment: "C# / .NET" is a skill name, and <https://x/#frag> is an IRI.
    """
    if "#" not in text:
        return []
    found = []
    line, pos = 1, 0
    for m in TOKENS.finditer(text):
        if m.group("comment") is None:
            continue
        line += text.count("\n", pos, m.start())
        pos = m.start()
        at_start = m.start() == 0 or text[m.start() - 1] == "\n"
        if not (at_start and BANNER.match(m.group("comment"))):
            found.append((line, m.group("comment")))
    return found
```

In `src/jsk/preflight.py`, change the `GRAPH_MODULES` line to `GRAPH_MODULES = ["graph", "graph.ontology", "graph.io"]`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_graph_io.py tests/test_preflight.py -q`
Expected: all pass (`test_graph_io`: 7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/jsk/graph/io.py src/jsk/preflight.py tests/test_graph_io.py
git commit -m "feat(graph): read a record file - quads, subject lines, comments a rewrite would drop"
```

---

### Task 3: The canonical writer, the fixtures and the seed vocabulary

**Files:**
- Create: `src/jsk/graph/writer.py`, `src/jsk/data/vocabulary.ttl`
- Create: `tests/graph_fixtures/career/kb.ttl`, `tests/graph_fixtures/career/log.ttl`, `tests/graph_fixtures/applications/acme-platform-engineer/{posting.ttl,posting.md,application.ttl}`
- Create: `tests/graphgen.py`
- Modify: `src/jsk/preflight.py` (`GRAPH_MODULES`)
- Test: `tests/test_graph_writer.py`

**Interfaces:**
- Consumes: `ontology.*`, and `io.parse_text` / `io.parse` in the tests.
- Produces, in `jsk.graph.writer`:
  - `write(triples, kind) -> str`, which takes any iterable of objects with `.subject .predicate .object` (pyoxigraph `Quad` or `Triple`) and raises `WriteError(ValueError)` for anything it can't lay out: a blank node, a non-`j:` predicate, an `rdf:type` on a `k:` id, a class outside the file kind, or an unknown predicate;
  - `curie(iri) -> str`, which later tasks use to print ids;
  - `short_string`, `long_string` and `literal`.
- Produces in the tests: `graphgen.graph(seed, kind) -> (triples, ids)`. Also produces the fixture workspace, which Tasks 4 and 5 use as their valid starting point, and which loads with zero findings once Task 5 is done.

**The fixture files are canonical: `write(parse(f)) == f`, byte for byte.** Create them exactly as shown, with LF line endings. If an editor adds a BOM, CRLF or a trailing blank line, `test_every_fixture_rewrites_to_itself` fails.

- [ ] **Step 1: Write the fixtures and the generator**

Create `tests/graph_fixtures/career/kb.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

k:kb j:format 3 ; j:name "Priya Raman" ; j:updated "2026-09-20"^^xsd:date .

# == Identity

k:person j:fullName "Priya Raman" ;
    j:headline "Principal Solution Architect" ;
    j:city "Sydney" ; j:country "AU" ; j:workMode j:hybrid ;
    j:email "priya@example.com" ;
    j:linkedin "linkedin.com/in/priyaraman" ;
    j:primary "priya@example.com" ;
    j:provenance j:confirmed .

# == Positioning

k:person j:positioning """Architect who turns regulated, legacy-heavy estates into event-driven platforms without a big-bang
rewrite. Strongest in healthcare and aged care.""" .

# == Work authorization and languages

k:auth_au j:jurisdiction "AU" ; j:kind j:citizen ; j:authorization j:held ;
    j:provenance j:confirmed .

k:lang_en j:language "en" ; j:native true ; j:provenance j:confirmed .

# == Vocabulary

c:ai-platform-architecture a j:Capability .
c:data-sovereignty a j:Capability .
c:event-driven-architecture a j:Capability ; j:label "EDA", "event-driven" .
c:team-leadership a j:Capability ; j:label "people leadership" .
c:aged-care a j:Domain ; j:partOf c:healthcare .
c:healthcare a j:Domain .
c:kafka j:isA c:event-driven-architecture .

# == Organisations

k:org_meridian j:name "Meridian Health" ;
    j:relationship j:employer ; j:industry c:healthcare ; j:size "1001-5000" ;
    j:provenance j:confirmed .

k:org_northbridge j:name "Northbridge Digital" ;
    j:relationship j:employer ;
    j:provenance j:confirmed .

# == Roles

k:pos_meridian_principal j:organisation k:org_meridian ;
    j:title "Principal Solution Architect" ;
    j:start "2023-07" ; j:state j:ongoing ;
    j:seniority j:architecture-ownership ; j:change j:promotion ;
    j:provenance j:confirmed .

k:pos_meridian_senior j:organisation k:org_meridian ;
    j:title "Senior Engineer" ;
    j:start "2020-02" ; j:end "2023-06" ; j:state j:ended ;
    j:seniority j:hands-on-senior ; j:change j:hire ;
    j:provenance j:confirmed .

k:pos_northbridge_architect j:organisation k:org_northbridge ;
    j:title "Solution Architect" ;
    j:start "2016-08" ; j:end "2020-01" ; j:state j:ended ;
    j:seniority j:platform-design ; j:change j:hire ;
    j:provenance j:confirmed .

# == Projects

k:prj_clinical_events j:name "Clinical event pipeline" ;
    j:position k:pos_meridian_principal ;
    j:strength 5 ; j:recency 2026 ; j:seniority j:architecture-ownership ;
    j:domain c:aged-care, c:healthcare ;
    j:uses c:ai-platform-architecture, c:azure-ai-foundry, c:bicep, c:data-sovereignty, c:kafka ;
    j:headlineMetric k:met_event_latency ;
    j:problem """The legacy scheduler could not express care-plan constraints, so every site
maintained its own spreadsheet beside it.""" ;
    j:decision """Event-sourced the schedule rather than versioning the table, on the argument
that the audit requirement was the real constraint.""" ;
    j:outcome """Propagation fell from five minutes to under a second across 15 integrated
applications.""" ;
    j:provenance j:confirmed .

k:ach_clinical_events_event_latency j:project k:prj_clinical_events ; j:rank 1 ;
    j:text "Cut p95 clinical event latency from 5 minutes to under 1 second across 40,000 daily ingestion jobs." ;
    j:cites k:met_event_latency ;
    j:provenance j:confirmed .

k:ach_clinical_events_led_migration j:project k:prj_clinical_events ; j:rank 2 ;
    j:text "Led a team of 6 engineers through the migration with no unplanned downtime." ;
    j:cites k:met_team ; j:shows c:team-leadership ;
    j:provenance j:confirmed .

k:prj_site_onboarding j:name "Care-site onboarding" ;
    j:position k:pos_meridian_senior ;
    j:strength 3 ; j:recency 2022 ; j:seniority j:hands-on-senior ;
    j:domain c:aged-care ;
    j:uses c:dotnet, c:sql-server, c:team-leadership ;
    j:headlineMetric k:met_sites ;
    j:problem "Each new residential care site took a quarter to onboard by hand." ;
    j:decision "Templated the site configuration and moved the checks into the pipeline." ;
    j:outcome "Onboarding fell to two weeks; 42 sites now run on it." ;
    j:provenance j:inferred .

k:ach_site_onboarding_sites_one_platform j:project k:prj_site_onboarding ; j:rank 1 ;
    j:text "Brought 42 residential care sites onto one platform, cutting onboarding from a quarter to two weeks." ;
    j:cites k:met_sites ;
    j:provenance j:inferred .

k:prj_intranet_refresh j:name "Intranet refresh" ;
    j:position k:pos_northbridge_architect ;
    j:strength 1 ; j:recency 2017 ;
    j:noneQuantified true ;
    j:retired "2026-01-10"^^xsd:date ; j:reason "Too old and too small to earn a line." ;
    j:provenance j:confirmed .

# == Metrics

k:met_event_latency j:subject "p95 clinical event latency" ; j:unit "min→s" ; j:direction j:decrease .

k:met_event_latency.v1 j:of k:met_event_latency ;
    j:baseline 5 ; j:value 2 ;
    j:confidence j:estimated ; j:source "load test" ;
    j:validUntil "2026-03-01"^^xsd:date ;
    j:provenance j:confirmed .

k:met_event_latency.v2 j:of k:met_event_latency ;
    j:baseline 5 ; j:value 1 ;
    j:confidence j:measured ; j:source "Grafana dashboard" ;
    j:validFrom "2026-03-01"^^xsd:date ;
    j:provenance j:confirmed .

k:met_sites j:subject "residential care sites served" ; j:unit "sites" .

k:met_sites.v1 j:of k:met_sites ;
    j:value 42 ;
    j:confidence j:measured ; j:source "platform admin console" ;
    j:provenance j:confirmed .

k:met_team j:subject "engineers led" ; j:unit "engineers" .

k:met_team.v1 j:of k:met_team ;
    j:value 6 ;
    j:confidence j:measured ; j:source "org chart" ;
    j:provenance j:confirmed .

# == Skills

k:skill_azure j:name "Azure" ; j:category "cloud-platform" ;
    j:alias "Azure AI Foundry", "Bicep", "Microsoft Azure" .

k:skill_dotnet j:name "C# / .NET" ; j:category "language" ; j:alias ".NET", "ASP.NET Core", "C#" .

# == Education

k:edu_meng j:institution "Anna University" ;
    j:qualification "Master of Engineering" ; j:field "Computer Science" ; j:level j:isced-7 ;
    j:start "2010" ; j:end "2012" ;
    j:gradeScheme "in-cgpa-10" ; j:gradeValue 8.4 ;
    j:provenance j:confirmed .

# == Certifications

k:cred_az305 j:name "Azure Solutions Architect Expert" ;
    j:issuer "Microsoft" ; j:issued "2024-03" ; j:credentialState j:active ;
    j:provenance j:confirmed .

# == Open source

k:os_carbon_scheduler j:name "carbon-aware-scheduler" ;
    j:url "https://github.com/example/carbon-aware-scheduler" ; j:role j:maintainer ;
    j:provenance j:confirmed .

# == Open questions

k:q_team_size j:about k:prj_clinical_events ;
    j:question "Was the team 6 throughout, or at peak?" ;
    j:asked "2026-08-12"^^xsd:date ; j:answered "2026-08-14"^^xsd:date .

k:q_sites_bullet j:about k:ach_site_onboarding_sites_one_platform ;
    j:question "Was onboarding a quarter before, or longer at the first sites?" ;
    j:asked "2026-09-01"^^xsd:date .

k:q_sites_confirm j:about k:prj_site_onboarding ;
    j:question "Is 42 the current site count, or the count at hand-over?" ;
    j:asked "2026-09-01"^^xsd:date .
```

Create `tests/graph_fixtures/career/log.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Log

k:rev_1 j:revision 1 ; j:date "2026-09-20"^^xsd:date ; j:by j:migrate ;
    j:summary "Migrated from user-knowledgebase.md (kb: 2)." ;
    j:kbSha256 "0000000000000000000000000000000000000000000000000000000000000000" .

k:rev_2 j:revision 2 ; j:date "2026-09-21"^^xsd:date ; j:by j:confirm ;
    j:summary "Confirmed the team size." ;
    j:touched k:met_team.v1, k:q_team_size ;
    j:answer "Six throughout; two joined in the second month and two left." ;
    j:kbSha256 "1111111111111111111111111111111111111111111111111111111111111111" .
```

Create `tests/graph_fixtures/applications/acme-platform-engineer/posting.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Posting

k:post_acme_platform_engineer j:company "Acme Health" ; j:title "Platform Engineer" ;
    j:url "https://acme.example/jobs/42" ;
    j:seniority j:platform-design ; j:domain c:healthcare ;
    j:captured "2026-09-08"^^xsd:date ; j:advert "posting.md" .

# == Requirements

k:req_acme_platform_engineer_eda j:posting k:post_acme_platform_engineer ;
    j:asked "event-driven" ; j:necessity j:preferred ;
    j:quote "Event-driven systems a plus" .

k:req_acme_platform_engineer_kubernetes j:posting k:post_acme_platform_engineer ;
    j:asked "K8s" ; j:necessity j:required ;
    j:quote "Deep, hands-on K8s experience in production" .
```

Create `tests/graph_fixtures/applications/acme-platform-engineer/posting.md`:

```markdown
Platform Engineer at Acme Health

Deep, hands-on K8s experience in production.
Event-driven systems a plus.
```

Create `tests/graph_fixtures/applications/acme-platform-engineer/application.ttl`:

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# == Application

k:app_acme_platform_engineer j:posting k:post_acme_platform_engineer ; j:view "view_default" ;
    j:submitted "2026-09-10"^^xsd:date ; j:channel "company site" ;
    j:document "Priya_Raman_Resume.pdf" ;
    j:carried k:ach_clinical_events_event_latency, k:ach_clinical_events_led_migration ;
    j:carriedVersion k:met_event_latency.v2, k:met_team.v1 .

# == Timeline

k:evt_acme_platform_engineer_2026_09_10_submitted j:application k:app_acme_platform_engineer ;
    j:date "2026-09-10"^^xsd:date ; j:kind j:submitted ; j:channel "company site" .

k:evt_acme_platform_engineer_2026_09_15_screen_scheduled j:application k:app_acme_platform_engineer ;
    j:date "2026-09-15"^^xsd:date ; j:kind j:screen-scheduled ; j:due "2026-09-18"^^xsd:date ;
    j:note "Phone screen, 30 min" .
```

Create `src/jsk/data/vocabulary.ttl`:

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

Create `tests/graphgen.py`:

```python
"""Random valid graphs drawn from the ontology, for the writer's property tests.

Seeded, so a failure names its seed and reproduces. Values are chosen to be hard for the
writer rather than realistic: runs of quotes, backslashes, newlines, tabs, non-ASCII.
"""
import random

import pyoxigraph as ox

from jsk.graph import ontology as O

NASTY = ['"', '""', '"""', '""""', '\\', '\\"', "\n", "\n\n", "\t", "→", "é", "#", "'", "'''",
         " ", "a", "Bb", "0", "p95", "C# / .NET", "<x>", "\r"]
XSD = {t: ox.NamedNode(O.XSD + t) for t in ("string", "integer", "decimal", "boolean", "date")}


def text(rnd, multiline):
    parts = [rnd.choice(NASTY) for _ in range(rnd.randint(1, 8))]
    value = "".join(parts)
    if not multiline:
        value = value.replace("\n", " ")
    return value or "x"


def value(rnd, pred, ids):
    kind = pred.obj
    if isinstance(kind, O.Enum):
        return ox.NamedNode(O.J + rnd.choice(O.ENUMS[kind.name]))
    if isinstance(kind, O.Concept):
        return ox.NamedNode(O.C + rnd.choice(["kafka", "sql-server", "a", "b-c"]))
    if isinstance(kind, O.Ref):
        pool = [i for i, c in ids if kind.classes == O.ANY or c in kind.classes]
        return ox.NamedNode(rnd.choice(pool) if pool else O.K + "org_x")
    t = rnd.choice(kind.types)
    if kind.pattern == r"\d{4}(-(0[1-9]|1[0-2]))?":
        return ox.Literal(f"{rnd.randint(1990, 2030)}-{rnd.randint(1, 12):02d}")
    if kind.pattern == r"\d{4}-\d{2}-\d{2}|false":
        return ox.Literal("false", datatype=XSD["boolean"]) if t == "boolean" else \
            ox.Literal("2026-09-10", datatype=XSD["date"])
    if kind.pattern == r"\d{4}-\d{2}-\d{2}|unknown":
        return ox.Literal("unknown") if t == "string" else \
            ox.Literal(f"2026-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}", datatype=XSD["date"])
    if kind.pattern:
        return ox.Literal({r"[A-Z]{2}": "AU", r"[0-9a-f]{64}": "a" * 64, r"\S+": "https://x/y",
                           r"posting\.md": "posting.md"}.get(kind.pattern, "en"))
    if t == "integer":
        lo = int(kind.lo) if kind.lo is not None else 0
        hi = int(kind.hi) if kind.hi is not None else lo + 50
        return ox.Literal(str(rnd.randint(lo, hi)), datatype=XSD["integer"])
    if t == "decimal":
        return ox.Literal(f"{rnd.randint(0, 99)}.{rnd.randint(0, 9)}", datatype=XSD["decimal"])
    if t == "boolean":
        return ox.Literal(rnd.choice(["true", "false"]), datatype=XSD["boolean"])
    if t == "date":
        return ox.Literal(f"2026-0{rnd.randint(1, 9)}-2{rnd.randint(0, 8)}", datatype=XSD["date"])
    return ox.Literal(text(rnd, pred.obj is O.TEXT))


def graph(seed, kind):
    """(triples, ids) for one random file of `kind`."""
    rnd = random.Random(seed)
    ids = []
    for cls in O.CLASSES:
        if kind not in cls.kinds:
            continue
        if cls.prefix and cls.prefix.startswith("="):
            ids.append((O.K + cls.prefix[1:], cls.name))
            continue
        for n in range(rnd.randint(0, 3)):
            if cls.name == "Concept":
                ids.append((O.C + f"con-{n}-{rnd.randint(0, 9)}", cls.name))
            elif cls.name == "MetricVersion":
                ids.append((O.K + f"met_m{n % 2}.v{n + 1}", cls.name))
            else:
                ids.append((O.K + f"{cls.prefix}_s{n}_{rnd.choice(['a', 'b', 'cc'])}", cls.name))
    triples = []
    for iri, name in dict(ids).items():
        cls = O.BY_NAME[name]
        s = ox.NamedNode(iri)
        if name == "Concept":
            triples.append(ox.Triple(s, ox.NamedNode(O.RDF_TYPE),
                                     ox.NamedNode(O.J + rnd.choice(O.ENUMS["conceptClass"]))))
        for pred in cls.preds.values():
            if pred.card in "1+" or rnd.random() < 0.5:
                count = rnd.randint(1, 3) if pred.card in "*+" else 1
                for _ in range(count):
                    triples.append(ox.Triple(s, ox.NamedNode(O.J + pred.name),
                                             value(rnd, pred, ids)))
    return list({str(t): t for t in triples}.values()), ids
```

- [ ] **Step 2: Write the failing writer test**

Create `tests/test_graph_writer.py`:

```python
"""Writing the graph record: gofmt's contract.

The writer's promise is that the file is a function of the triples. These tests hold it
to that from three sides: the committed fixtures are already canonical (so rewriting them
changes nothing), random graphs survive write -> parse -> write, and input order never
reaches the output.
"""
import random
import unittest
from pathlib import Path

import pyoxigraph as ox

from graphgen import graph
from jsk.graph import io, writer
from jsk.graph import ontology as O

FIXTURES = Path(__file__).parent / "graph_fixtures"
FILES = sorted(FIXTURES.rglob("*.ttl"))
PFX = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES)


def triples(parsed):
    return {(str(q.subject), str(q.predicate), str(q.object)) for q in parsed.quads}


class FixturesAreCanonical(unittest.TestCase):
    def test_every_fixture_rewrites_to_itself(self):
        self.assertEqual(len(FILES), 4)
        for path in FILES:
            with self.subTest(file=path.name):
                text = path.read_bytes().decode("utf-8")
                parsed = io.parse_text(text, path.name)
                self.assertEqual(writer.write(parsed.quads, parsed.kind), text)

    def test_the_shipped_vocabulary_is_canonical(self):
        import jsk
        text = (Path(jsk.__file__).parent / "data" / "vocabulary.ttl").read_bytes().decode()
        parsed = io.parse_text(text, "vocabulary.ttl")
        self.assertEqual(writer.write(parsed.quads, "vocabulary"), text)


class RandomGraphsRoundTrip(unittest.TestCase):
    SEEDS = range(60)

    def test_write_parse_write(self):
        for kind in ("kb", "posting", "application", "log", "vocabulary"):
            for seed in self.SEEDS:
                with self.subTest(kind=kind, seed=seed):
                    ts, _ = graph(seed, kind)
                    out = writer.write(ts, kind)
                    back = io.parse_text(out, f"{kind}.ttl", kind)
                    self.assertEqual(triples(back), {(str(t.subject), str(t.predicate),
                                                      str(t.object)) for t in ts})
                    self.assertEqual(writer.write(back.quads, kind), out)

    def test_input_order_never_reaches_the_output(self):
        for seed in range(20):
            ts, _ = graph(seed, "kb")
            shuffled = list(ts)
            random.Random(seed + 1000).shuffle(shuffled)
            self.assertEqual(writer.write(shuffled, "kb"), writer.write(ts, "kb"), seed)


class Literals(unittest.TestCase):
    CASES = ['He said """hi""" and left', 'ends with a quote"', 'ends with two""',
             'five """"" quotes', 'back\\slash', 'back\\slash then quote\\"', 'tab\there',
             'line\nbreak', 'ends in newline\n', '\nstarts with one', 'arrow → and é',
             'a # is not a comment', "'''single'''", 'carriage\rreturn', '"', '""', '"""',
             '\\', '\\"', '"\n"']

    def test_every_awkward_string_round_trips(self):
        for value in self.CASES:
            with self.subTest(value=value):
                t = ox.Triple(ox.NamedNode(O.K + "met_x"), ox.NamedNode(O.J + "subject"),
                              ox.Literal(value))
                out = writer.write([t], "kb")
                back = io.parse_text(out, "kb.ttl")
                self.assertEqual([q.object.value for q in back.quads], [value])

    def test_multiline_prose_stays_readable(self):
        t = ox.Triple(ox.NamedNode(O.K + "prj_x"), ox.NamedNode(O.J + "problem"),
                      ox.Literal('It said "no".\nSo we did.'))
        out = writer.write([t], "kb")
        self.assertIn('j:problem """It said "no".\nSo we did.""" .', out)

    def test_numbers_and_dates_are_bare_or_typed(self):
        out = writer.write(io.parse_text(PFX + 'k:met_x.v1 j:value 42 ; j:baseline 8.5 ; '
                                         'j:validFrom "2026-09-01"^^xsd:date .', "kb.ttl").quads,
                           "kb")
        self.assertIn("j:baseline 8.5 ; j:value 42", out)
        self.assertIn('j:validFrom "2026-09-01"^^xsd:date', out)


class Layout(unittest.TestCase):
    def test_kb_prints_every_banner_even_when_empty(self):
        out = writer.write([], "kb")
        for section in O.SECTIONS["kb"]:
            self.assertIn(f"# == {section}\n", out)

    def test_other_kinds_omit_empty_sections(self):
        self.assertNotIn("# ==", writer.write([], "posting"))

    def test_lf_only_one_final_newline(self):
        for path in FILES:
            text = path.read_bytes().decode("utf-8")
            self.assertNotIn("\r", text)
            self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))

    def test_roles_newest_first_and_bullets_under_their_project(self):
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8")
        order = [text.index(x) for x in ("k:pos_meridian_principal", "k:pos_meridian_senior",
                                         "k:pos_northbridge_architect")]
        self.assertEqual(order, sorted(order))
        order = [text.index(x) for x in ("k:prj_clinical_events j:",
                                         "k:ach_clinical_events_event_latency j:",
                                         "k:ach_clinical_events_led_migration j:",
                                         "k:prj_site_onboarding j:")]
        self.assertEqual(order, sorted(order))

    def test_types_are_never_written_for_ids(self):
        t = ox.Triple(ox.NamedNode(O.K + "org_x"), ox.NamedNode(O.RDF_TYPE),
                      ox.NamedNode(O.J + "Organisation"))
        with self.assertRaises(writer.WriteError):
            writer.write([t], "kb")

    def test_a_class_outside_its_file_kind_is_refused(self):
        t = ox.Triple(ox.NamedNode(O.K + "pos_x"), ox.NamedNode(O.J + "title"), ox.Literal("x"))
        with self.assertRaises(writer.WriteError):
            writer.write([t], "posting")


class HandEdits(unittest.TestCase):
    """What a person's editor does to the file, undone by one rewrite."""

    KB_TEXT = (FIXTURES / "career" / "kb.ttl").read_bytes().decode("utf-8")

    def rewrite(self, text):
        parsed = io.parse_text(text, "career/kb.ttl")
        return writer.write(parsed.quads, "kb")

    def test_a_windows_editor_crlf_bom_and_tabs(self):
        edited = "﻿" + self.KB_TEXT.replace("\n    ", "\n\t").replace("\n", "\r\n")
        self.assertEqual(self.rewrite(edited), self.KB_TEXT)

    def test_a_subject_written_in_two_places_becomes_one_block(self):
        text = PFX + ('k:met_team j:subject "engineers led" .\n\n'
                      'k:met_team.v1 j:of k:met_team ; j:value 6 ; j:confidence j:measured ; '
                      'j:provenance j:confirmed .\n\nk:met_team j:unit "engineers" .\n')
        out = self.rewrite(text)
        self.assertIn('k:met_team j:subject "engineers led" ; j:unit "engineers" .', out)
        self.assertEqual(out.count("k:met_team j:"), 1)

    def test_sparql_style_prefixes_full_iris_and_stray_prefixes(self):
        text = ('PREFIX j: <tag:jsk,2026:ns#>\n@prefix ex: <http://example.com/> .\n'
                '<tag:jsk,2026:id/met_team> j:subject "engineers led" ; '
                '<tag:jsk,2026:ns#unit> "engineers" .\n')
        out = self.rewrite(text)
        self.assertIn('k:met_team j:subject "engineers led" ; j:unit "engineers" .', out)
        self.assertNotIn("example.com", out)
        self.assertTrue(out.startswith(PFX))


class SubjectLines(unittest.TestCase):
    def test_findings_can_point_into_the_fixture(self):
        parsed = io.parse(FIXTURES / "career" / "kb.ttl")
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8").split("\n")
        line = parsed.lines[O.K + "met_team.v1"]
        self.assertTrue(text[line - 1].startswith("k:met_team.v1 "))
        self.assertEqual(parsed.lines[O.C + "kafka"],
                         text.index("c:kafka j:isA c:event-driven-architecture .") + 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_writer.py -q`
Expected: `ImportError: cannot import name 'writer' from 'jsk.graph'`.

- [ ] **Step 4: Write the writer**

Create `src/jsk/graph/writer.py`:

```python
"""The canonical Turtle writer: the same triples always give the same bytes.

gofmt's contract. `write` is a pure function of the triple set - input order, the
parser's order and hash seeds change nothing - and its output parses back to exactly the
triples it was given. pyoxigraph's own serializer is neither (P0), so it is used only to
parse and query.

Layout comes from ontology.py: sections in SECTIONS order, subjects by their natural key,
predicates in the class's line order, one line per `lines` entry.
"""
import re
from collections import defaultdict

from . import ontology as O

WIDTH = 100
INDENT = "    "
PN_LOCAL = re.compile(r"[A-Za-z0-9_](?:[A-Za-z0-9_.\-]*[A-Za-z0-9_\-])?")
BARE_DECIMAL = re.compile(r"[+-]?[0-9]*\.[0-9]+")
BARE_INTEGER = re.compile(r"[+-]?[0-9]+")


class WriteError(ValueError):
    """The triples cannot be written in this file kind's layout. Validation catches
    every such graph first; reaching this means a caller skipped validation."""


# --- terms -----------------------------------------------------------------------------

def curie(iri):
    for name, ns in O.CHANGESET_PREFIXES:
        if iri.startswith(ns) and PN_LOCAL.fullmatch(iri[len(ns):]):
            return f"{name}:{iri[len(ns):]}"
    return f"<{iri}>"


def short_string(value):
    return '"' + (value.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\t", "\\t").replace("\r", "\\r")) + '"'


def long_string(value):
    """Triple-quoted, escaping only what the grammar needs: `\\`, a run of three quotes,
    a final quote (it would merge with the closing three) and a carriage return."""
    esc = value.replace("\\", "\\\\").replace("\r", "\\r").replace('"""', '\\"\\"\\"')
    if esc.endswith('"') and (len(esc) - len(esc[:-1].rstrip("\\")) - 1) % 2 == 0:
        esc = esc[:-1] + '\\"'      # a raw final quote, not the tail of an escape
    return '"""' + esc + '"""'


def literal(lit):
    dt = lit.datatype.value
    value = lit.value
    if lit.language:
        return f"{short_string(value)}@{lit.language}"
    if dt == O.XSD + "string":
        return long_string(value) if "\n" in value else short_string(value)
    if dt == O.XSD + "integer" and BARE_INTEGER.fullmatch(value):
        return value
    if dt == O.XSD + "decimal" and BARE_DECIMAL.fullmatch(value):
        return value
    if dt == O.XSD + "boolean" and value in ("true", "false"):
        return value
    return f"{short_string(value)}^^{curie(dt)}"


def term(t):
    import pyoxigraph as ox

    if isinstance(t, ox.NamedNode):
        return curie(t.value)
    if isinstance(t, ox.Literal):
        return literal(t)
    raise WriteError(f"cannot write {t!r}: blank nodes are not part of the format")


def sort_key(t):
    import pyoxigraph as ox

    # References by id, literals by value; references first so a mixed list is stable.
    return (0, t.value, "") if isinstance(t, ox.NamedNode) else (1, t.value, t.datatype.value)


# --- the graph, by subject -------------------------------------------------------------

class Subjects:
    """{subject iri: {predicate name or "a": [objects]}} plus each subject's class."""

    def __init__(self, triples):
        import pyoxigraph as ox

        self.props = defaultdict(lambda: defaultdict(list))
        for t in triples:
            if not isinstance(t.subject, ox.NamedNode):
                raise WriteError("cannot write a blank-node subject")
            p = t.predicate.value
            if p == O.RDF_TYPE:
                name = "a"
            elif p.startswith(O.J):
                name = p[len(O.J):]
            else:
                raise WriteError(f"{curie(t.subject.value)}: predicate <{p}> is not in the format")
            self.props[t.subject.value][name].append(t.object)
        self.cls = {}
        for s in self.props:
            name = O.class_of(s)
            if name is None:
                raise WriteError(f"<{s}> is not a jsk id")
            self.cls[s] = O.BY_NAME[name]

    def of(self, name):
        return sorted(s for s, c in self.cls.items() if c.name == name)

    def get(self, s, pred, default=None):
        values = self.props.get(s, {}).get(pred)
        return values[0].value if values else default


# --- subject order ---------------------------------------------------------------------

def desc(items, key):
    """Sorted by key descending, missing keys last, id ascending within a tie."""
    have = sorted((x for x in items if key(x) is not None), key=lambda x: x)
    have.sort(key=key, reverse=True)
    return have + sorted(x for x in items if key(x) is None)


def order(sub, section):
    """The subjects written in one section, in order; each is (iri, part) where part
    names which of the subject's predicates this block holds ("main" or a section)."""
    g = sub.get
    if section == "Identity":
        return [(s, "main") for s in sub.of("Person")]
    if section == "Positioning":
        return [(s, section) for s in sub.of("Person") if "positioning" in sub.props[s]]
    if section == "Work authorization and languages":
        return [(s, "main") for s in sub.of("WorkAuthorization") + sub.of("Language")]
    if section == "Vocabulary":
        rank = {c: n for n, c in enumerate(O.ENUMS["conceptClass"])}

        def concept_key(s):
            types = sorted(rank.get(t.value[len(O.J):], 9) for t in sub.props[s].get("a", []))
            return (types[0] if types else 9, s)
        return [(s, "main") for s in sorted(sub.of("Concept"), key=concept_key)]
    if section == "Roles":
        return [(s, "main") for s in desc(sub.of("Position"), lambda s: g(s, "start"))]
    if section == "Organisations":
        newest = {}
        for p in sub.of("Position"):
            org, start = g(p, "organisation"), g(p, "start")
            if org and start and start > newest.get(org, ""):
                newest[org] = start
        return [(s, "main") for s in desc(sub.of("Organisation"), newest.get)]
    if section == "Projects":
        roles = [s for s, _ in order(sub, "Roles")]
        at = {r: n for n, r in enumerate(roles)}
        projects = sorted(sub.of("Project"),
                          key=lambda s: (at.get(g(s, "position"), len(roles)),
                                         -int(g(s, "recency", 0)), s))
        bullets = defaultdict(list)
        for a in sub.of("Achievement"):
            bullets[g(a, "project")].append(a)
        out = []
        for p in projects:
            out.append((p, "main"))
            out += [(a, "main") for a in sorted(bullets.pop(p, []),
                                                key=lambda a: (int(g(a, "rank", 0)), a))]
        out += [(a, "main") for rest in sorted(bullets) for a in bullets[rest]]
        return out
    if section == "Metrics":
        versions = defaultdict(list)
        for v in sub.of("MetricVersion"):
            versions[v.rsplit(".v", 1)[0]].append(v)
        out = []
        for m in sub.of("Metric"):
            out.append((m, "main"))
            out += [(v, "main") for v in sorted(versions.pop(m, []), key=version_number)]
        out += [(v, "main") for rest in sorted(versions)
                for v in sorted(versions[rest], key=version_number)]
        return out
    if section == "Skills":
        return [(s, "main") for s in sorted(
            sub.of("Skill"), key=lambda s: (g(s, "category", ""), rank_or_last(g(s, "rank")),
                                            g(s, "name", ""), s))]
    if section == "Education":
        return [(s, "main") for s in desc(sub.of("Education"),
                                          lambda s: g(s, "end") or g(s, "start"))]
    if section == "Certifications":
        return [(s, "main") for s in desc(sub.of("Credential"), lambda s: g(s, "issued"))]
    if section == "Open questions":
        return [(s, "main") for s in sorted(sub.of("Question"), key=lambda s: (g(s, "asked", ""), s))]
    if section == "Timeline":
        return [(s, "main") for s in sorted(
            sub.of("Event"), key=lambda s: (g(s, "date") == "unknown", g(s, "date", ""), s))]
    if section == "Log":
        return [(s, "main") for s in sorted(sub.of("LogEntry"),
                                            key=lambda s: (int(g(s, "revision", 0)), s))]
    names = [c.name for c in O.CLASSES if c.section == section]
    return [(s, "main") for name in names for s in sub.of(name)]


def version_number(v):
    return int(v.rsplit(".v", 1)[1])


def rank_or_last(value):
    return int(value) if value is not None else 1 << 30


# --- one subject -----------------------------------------------------------------------

def block(sub, s, part):
    """One subject's text: (text, one_line)."""
    cls = sub.cls[s]
    props = sub.props[s]
    lines = []
    if "a" in props:
        if cls.name != "Concept":
            raise WriteError(f"{curie(s)}: rdf:type is derived from the id, never written")
        lines.append([f"a {', '.join(term(t) for t in sorted(props['a'], key=sort_key))}"])
    known = set(cls.preds) | {"a"}
    unknown = sorted(set(props) - known)
    if unknown:
        raise WriteError(f"{curie(s)}: j:{unknown[0]} is not a {cls.name} predicate")
    for line in cls.lines:
        frags = []
        for p in line:
            if p.name not in props or (p.section or "main") != part:
                continue
            objs = sorted(props[p.name], key=sort_key)
            frags.append(f"j:{p.name} {', '.join(term(t) for t in objs)}")
        if frags:
            lines.append(frags)
    if not lines:
        return None
    head = curie(s)
    flat = f"{head} {' ; '.join(f for line in lines for f in line)} ."
    if len(flat) <= WIDTH and "\n" not in flat:
        return flat, True
    body = f" ;\n{INDENT}".join(" ; ".join(line) for line in lines)
    return f"{head} {body} .", False


# --- the file --------------------------------------------------------------------------

def write(triples, kind):
    """The canonical text of one file of kind `kind`."""
    if kind not in O.SECTIONS:
        raise WriteError(f"no layout for file kind {kind!r}")
    sub = Subjects(triples)
    allowed = {c.name for c in O.CLASSES if kind in c.kinds}
    for s, cls in sub.cls.items():
        if cls.name not in allowed:
            raise WriteError(f"{curie(s)}: a {cls.name} does not belong in a {kind} file")

    out = [f"@prefix {name}: <{ns}> ." for name, ns in O.PREFIXES]
    out.append("")
    for cls in O.CLASSES:
        if cls.section is None and kind in cls.kinds:
            for s in sub.of(cls.name):
                out += [block(sub, s, "main")[0], ""] if block(sub, s, "main") else []
    for section in O.SECTIONS[kind]:
        blocks = [b for b in (block(sub, s, part) for s, part in order(sub, section)) if b]
        if not blocks and kind not in O.ALL_BANNERS:
            continue
        out += [f"# == {section}", ""]
        prev_one = False
        for n, (text, one) in enumerate(blocks):
            if n and not (one and prev_one):
                out.append("")
            out.append(text)
            prev_one = one
        if blocks:
            out.append("")
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"
```

In `src/jsk/preflight.py`, change the `GRAPH_MODULES` line to `GRAPH_MODULES = ["graph", "graph.ontology", "graph.io", "graph.writer"]`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_graph_writer.py tests/test_graph_io.py -q`
Expected: all pass, with about 330 subtests (300 random graphs, 20 literals and so on). If a fixture test fails, diff the file against the writer's output before changing either one: `python -c "from jsk.graph import io, writer; p = io.parse('tests/graph_fixtures/career/kb.ttl'); print(writer.write(p.quads, p.kind), end='')" | diff - tests/graph_fixtures/career/kb.ttl`.

- [ ] **Step 6: Commit**

```bash
git add src/jsk/graph/writer.py src/jsk/data/vocabulary.ttl src/jsk/preflight.py tests/graphgen.py tests/test_graph_writer.py tests/graph_fixtures
git commit -m "feat(graph): the canonical writer - the same triples always give the same bytes"
```

---

### Task 4: Loading a workspace, and the per-file rules

**Files:**
- Create: `src/jsk/graph/shapes.py`, `src/jsk/graph/store.py`
- Modify: `src/jsk/preflight.py` (`GRAPH_MODULES`)
- Test: `tests/test_graph_shapes.py`, `tests/test_graph_store.py`

**Interfaces:**
- Consumes: `ontology.*`, `io.parse` / `io.GraphError`, `writer.curie`, and `jsk.gates.validate_urs.Report`.
- Produces, in `jsk.graph.shapes`:
  - `FAIL`, `WARN`, and `TIER1` (the tuple of rule ids, `"syntax"` included);
  - the frozen dataclass `Finding(rule, severity, file, line, focus, detail, fix)` with `.text() -> str`;
  - `curie(iri)`, `tier1(parsed) -> list[Finding]`, `check_object(pred, term) -> str | None`, and `HEAD_FIX`.
- Produces, in `jsk.graph.store`:
  - `SHIPPED_VOCABULARY` and `workspace_files(root, vocabulary=...) -> list[str]`;
  - the dataclass `Store`, with `.root`, `.findings`, `.parsed` (file → Parsed), `.homes` (iri → first file), `.definitions` (iri → [files]) and `.ox`, plus the methods `.select(sparql) -> list[dict[str, Term]]` (over the union graph), `.file_of(iri)`, `.line_of(iri, file=None)`, `.defined()`, `.fails()`, `.warns()` and `.report() -> Report`;
  - `load(root, vocabulary=SHIPPED_VOCABULARY, files=None) -> Store`, `derive_types(store, derived)` and `materialise_paths(store)`.
- Produces in the tests: `test_graph_shapes.mutated(mutation) -> (Store, text)`, `assert_fires(case, rule, mutation)`, and the constants `KB`, `POSTING` and `APPLICATION`. Task 5 imports these.

In this task `store.load` runs tier 1 only. Task 5 adds the tier-2 call.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_shapes.py`:

```python
"""Tier 1: every per-file rule fires, at the right place, on the one edit that breaks it.

The fixture workspace is valid. Each mutation below is one edit a person or an agent
could plausibly make; the test copies the workspace, makes the edit, loads it and
asserts that the named rule reports the named id at that id's line. A rule with no
mutation fails `test_every_rule_has_a_mutation` - no rule exists without proof that it
fires. tests/test_graph_rules.py does the same for tier 2.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import shapes, store

FIXTURES = Path(__file__).parent / "graph_fixtures"
KB = "career/kb.ttl"
POSTING = "applications/acme-platform-engineer/posting.ttl"
APPLICATION = "applications/acme-platform-engineer/application.ttl"

# rule: (file, old text, new text, focus id, the fix contains). old=None appends new.
MUTATIONS = {
    "syntax": (KB, 'j:rank 2 ;', 'j:rank 2 ,;', "", "fix the syntax"),
    "id-form": (KB, "k:ach_clinical_events_led_migration", "k:ach_clinical_events_2",
                "k:ach_clinical_events_2", "name it after its content"),
    "id-home": (POSTING, None, '\nk:pos_stray j:organisation k:org_meridian .\n',
                "k:pos_stray", "move it to kb.ttl"),
    "closed": (KB, 'j:size "1001-5000"', 'j:sise "1001-5000"', "k:org_meridian",
               "did you mean j:size?"),
    "cardinality": (KB, 'j:start "2020-02" ; j:end "2023-06" ; j:state j:ended ;',
                    'j:start "2020-02" ; j:end "2023-06" ;', "k:pos_meridian_senior",
                    "add j:state"),
    "object": (KB, "j:workMode j:hybrid", "j:workMode j:hybird", "k:person", "j:onsite"),
    "no-blank-nodes": (KB, None, "\nk:met_team j:note _:b1 .\n", "k:met_team",
                       "give the node an id"),
    "no-derived": (KB, "k:org_northbridge j:name", "k:org_northbridge a j:Organisation ; j:name",
                   "k:org_northbridge", "delete the `a"),
    "retired-reason": (KB, ' j:reason "Too old and too small to earn a line." ;', "",
                       "k:prj_intranet_refresh", "add j:reason"),
    "comment": (KB, "# == Metrics", "# remember to ask about this\n# == Metrics", "",
                "j:note"),
}


def mutated(mutation):
    """A loaded copy of the fixture workspace with one (file, old, new, ...) edit applied;
    returns the store and the edited file's text."""
    file, old, new = mutation[:3]
    tmp = tempfile.mkdtemp()
    shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
    path = Path(tmp) / file
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if old is None:
        text += new
    else:
        assert old in text, f"{old!r} is not in {file}"
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")
    try:
        return store.load(tmp), text
    finally:
        shutil.rmtree(tmp)


def assert_fires(case, rule, mutation):
    """`rule` reports `focus` at the line that id starts on, with the expected fix."""
    _, _, _, focus, fix = mutation
    s, text = mutated(mutation)
    hits = [f for f in s.findings if f.rule == rule and f.focus == focus]
    case.assertTrue(hits, f"{rule} did not fire on {focus!r}: {[f.text() for f in s.findings]}")
    hit = hits[0]
    if focus:
        line = text.split("\n")[hit.line - 1]
        case.assertTrue(line.startswith(focus + " "), f"{rule}: line {hit.line} is {line!r}")
    case.assertIn(fix, hit.fix)
    return hit


class TheFixtureIsClean(unittest.TestCase):
    def test_no_findings(self):
        s = store.load(FIXTURES)
        self.assertEqual([f.text() for f in s.findings], [])


class EveryRuleFires(unittest.TestCase):
    def test_every_rule_has_a_mutation(self):
        self.assertEqual(set(shapes.TIER1), set(MUTATIONS))

    def test_each_mutation_fires_its_rule_at_the_right_line(self):
        for rule, mutation in MUTATIONS.items():
            with self.subTest(rule=rule):
                assert_fires(self, rule, mutation)

    def test_the_comment_finding_points_at_the_comment(self):
        hit = assert_fires(self, "comment", MUTATIONS["comment"])
        _, text = mutated(MUTATIONS["comment"])
        self.assertEqual(text.split("\n")[hit.line - 1], "# remember to ask about this")
        self.assertEqual(hit.severity, "WARN")


class Findings(unittest.TestCase):
    def test_a_syntax_error_stops_only_its_own_file(self):
        s, _ = mutated(MUTATIONS["syntax"])
        self.assertEqual([f.file for f in s.findings if f.rule == "syntax"], [KB])
        self.assertIn(POSTING, s.parsed)

    def test_an_unknown_predicate_names_the_nearest(self):
        s, _ = mutated(MUTATIONS["closed"])
        [f] = [f for f in s.findings if f.rule == "closed"]
        self.assertRegex(f.text(), r"^career/kb\.ttl:\d+ k:org_meridian - j:sise is not an? "
                                   r"Organisation predicate\n        fix: did you mean j:size\?$")

    def test_an_empty_kb_is_not_a_valid_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "career").mkdir()
            (Path(tmp) / "career" / "kb.ttl").write_text("", encoding="utf-8")
            s = store.load(tmp)
        [f] = [f for f in s.findings if f.rule == "cardinality"]
        self.assertEqual((f.file, f.line), (KB, 0))
        self.assertIn("exactly one KB; this one holds 0", f.detail)

    def test_one_posting_per_posting_file(self):
        s, _ = mutated((POSTING, None, '\nk:post_other j:company "B" ; j:title "T" ; '
                        'j:captured "2026-09-01"^^xsd:date ; j:advert "posting.md" .\n', "", ""))
        self.assertTrue([f for f in s.findings if f.rule == "cardinality" and f.file == POSTING
                         and "holds 2" in f.detail])

    def test_report_is_a_validate_urs_report(self):
        s, _ = mutated(MUTATIONS["object"])
        rep = s.report()
        self.assertEqual((len(rep.fails), len(rep.warns)), (len(s.fails()), len(s.warns())))
        self.assertTrue(rep.fails)


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_graph_store.py`:

```python
"""Loading a workspace: every file its own graph, types derived, the closure built.

The closure numbers are worked by hand from the fixture's edges, not read back from the
code: 16 concepts give 16 zero-hop paths, and the 4 isA/partOf edges give 4 one-hop
paths; nothing chains, so there are no two-hop paths.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from jsk.graph import store

FIXTURES = Path(__file__).parent / "graph_fixtures"
PRE = f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"


def paths(s, hops=None):
    where = f"FILTER(?h = {hops})" if hops is not None else ""
    rows = s.select(PRE + f"SELECT ?a ?b ?h ?i WHERE {{ GRAPH j:derived {{ ?p a j:Path ; "
                          f"j:from ?a ; j:to ?b ; j:hops ?h ; j:implied ?i }} {where} }}")
    return sorted((r["a"].value.rsplit("/", 1)[-1], r["b"].value.rsplit("/", 1)[-1],
                   int(r["h"].value), r["i"].value == "true") for r in rows)


class Loading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = store.load(FIXTURES)

    def test_every_file_is_its_own_graph(self):
        self.assertEqual(sorted(self.s.parsed), [
            "applications/acme-platform-engineer/application.ttl",
            "applications/acme-platform-engineer/posting.ttl",
            "career/kb.ttl", "career/log.ttl", "vocabulary.ttl"])
        self.assertEqual(self.s.file_of(O.K + "req_acme_platform_engineer_kubernetes"),
                         "applications/acme-platform-engineer/posting.ttl")

    def test_types_are_derived_from_the_prefix(self):
        rows = self.s.select(PRE + "SELECT ?t WHERE { GRAPH j:derived { "
                                   "k:met_event_latency.v2 a ?t } }")
        self.assertEqual([r["t"].value for r in rows], [O.J + "MetricVersion"])

    def test_derived_triples_are_not_in_any_file_graph(self):
        rows = self.s.select(PRE + "SELECT ?g WHERE { GRAPH ?g { ?s a j:Path } "
                                   "FILTER(?g != j:derived) }")
        self.assertEqual(rows, [])

    def test_a_kb_concept_extends_a_shipped_one(self):
        # c:kafka is typed in the shipped vocabulary; kb.ttl adds an edge to it.
        self.assertIn(("kafka", "event-driven-architecture", 1, False), paths(self.s, 1))

    def test_the_closure(self):
        self.assertEqual(len(paths(self.s, 0)), 16)
        self.assertEqual(paths(self.s, 1), [
            ("aged-care", "healthcare", 1, False),
            ("azure-ai-foundry", "azure", 1, False),
            ("bicep", "azure", 1, False),
            ("kafka", "event-driven-architecture", 1, False)])
        self.assertEqual(paths(self.s, 2), [])


class Closure(unittest.TestCase):
    """Two hops and no more, one way, and an implies edge marks every path it is on."""

    def load(self, edges):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "career").mkdir()
        text = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES) + edges
        (tmp / "career" / "kb.ttl").write_text(text, encoding="utf-8")
        try:
            return store.load(tmp, vocabulary=None)
        finally:
            shutil.rmtree(tmp)

    def test_hop_limit_and_direction(self):
        s = self.load("c:a a j:Technology ; j:isA c:b .\nc:b a j:Capability ; j:partOf c:c .\n"
                      "c:c a j:Capability ; j:isA c:d .\nc:d a j:Capability .\n")
        got = [(a, b, h) for a, b, h, _ in paths(s) if h]
        self.assertEqual(got, [("a", "b", 1), ("a", "c", 2), ("b", "c", 1), ("b", "d", 2),
                               ("c", "d", 1)])      # a->d is three hops: not a path

    def test_implies_marks_the_path(self):
        s = self.load("c:a a j:Capability ; j:implies c:b .\nc:b a j:Capability ; j:isA c:c .\n"
                      "c:c a j:Capability .\n")
        self.assertEqual([p for p in paths(s) if p[2]],
                         [("a", "b", 1, True), ("a", "c", 2, True), ("b", "c", 1, False)])


class Discovery(unittest.TestCase):
    def test_a_missing_file_is_absent_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = store.load(tmp)
            self.assertEqual(sorted(s.parsed), ["vocabulary.ttl"])
            self.assertEqual(s.findings, [])

    def test_a_folder_name_with_a_space_or_accent_loads(self):
        """A hand-made application folder is named however its owner likes; a graph name
        is an IRI, which cannot hold a space - so the loader must encode it."""
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
            apps = Path(tmp) / "applications"
            (apps / "acme-platform-engineer").rename(apps / "Acme Platform é")
            s = store.load(tmp)
            self.assertEqual([f.text() for f in s.findings], [])
            self.assertEqual(s.file_of(O.K + "app_acme_platform_engineer"),
                             "applications/Acme Platform é/application.ttl")

    def test_files_outside_the_layout_are_not_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
            (Path(tmp) / "career" / "notes.ttl").write_text("not turtle at all", encoding="utf-8")
            self.assertEqual(store.load(tmp).findings, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_shapes.py tests/test_graph_store.py -q`
Expected: `ImportError: cannot import name 'shapes' from 'jsk.graph'`.

- [ ] **Step 3: Write the per-file rules**

Create `src/jsk/graph/shapes.py`:

```python
"""The rules a record must keep, and the findings that name where it does not.

Tier 1 is generated from ontology.py and runs on one file at a time: shape, ids, values.
Tier 2 is SPARQL over the whole workspace: references, versions, the vocabulary's edges.
Every rule has an id, a severity and a fix, and every finding names file:line and the id
it is about - a finding that says only "invalid" is one nobody can act on.
"""
import difflib
import re
from collections import defaultdict
from dataclasses import dataclass

from . import ontology as O

FAIL, WARN = "FAIL", "WARN"
# The tier-1 rule ids, and "syntax" for a file that does not parse. tests/test_graph_shapes.py
# holds a mutation for every id here and in RULES; a rule with none fails the suite.
TIER1 = ("syntax", "id-form", "id-home", "closed", "cardinality", "object", "no-blank-nodes",
         "no-derived", "retired-reason", "comment")
XSD_TYPES = {O.XSD + t: t for t in ("string", "integer", "decimal", "boolean", "date")}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    focus: str       # the id as a CURIE, "" for a whole-file finding
    detail: str
    fix: str

    def text(self):
        where = f"{self.file}:{self.line}" if self.line else self.file
        focus = f" {self.focus}" if self.focus else ""
        return f"{where}{focus} - {self.detail}\n        fix: {self.fix}"


def curie(iri):
    from .writer import curie as c
    return c(iri)


# --- tier 1: one file, generated from the ontology --------------------------------------

def tier1(parsed):
    """Findings for one parsed file."""
    import pyoxigraph as ox

    out = []

    def add(rule, sev, s, detail, fix):
        out.append(Finding(rule, sev, parsed.file, parsed.lines.get(s, 0) if s else 0,
                           curie(s) if s else "", detail, fix))

    for line, text in parsed.comments:
        out.append(Finding("comment", WARN, parsed.file, line, "",
                           f"comment {text[:40]!r} will be lost on the next write",
                           "move it into a j:note on the entry it is about"))

    props = defaultdict(lambda: defaultdict(list))
    for q in parsed.quads:
        if any(isinstance(t, ox.BlankNode) for t in (q.subject, q.object)):
            s = q.subject.value if isinstance(q.subject, ox.NamedNode) else None
            add("no-blank-nodes", FAIL, s, "a blank node ([ ] or _:)",
                "give the node an id of its own and point at it")
            continue
        props[q.subject.value][q.predicate.value].append(q.object)

    head = O.HEADS.get(parsed.kind)
    if head:
        count = sum(1 for s in props if O.class_of(s) == head)
        if count != 1:
            add("cardinality", FAIL, None,
                f"a {parsed.kind} file holds exactly one {head}; this one holds {count}",
                HEAD_FIX[head])

    for s, preds in props.items():
        name = O.class_of(s)
        if name is None:
            add("id-form", FAIL, s, "not a jsk id", id_fix(s))
            continue
        cls = O.BY_NAME[name]
        local = s[len(O.K):] if s.startswith(O.K) else s[len(O.C):]
        if name == "Concept" and not O.CONCEPT_SLUG.fullmatch(local):
            add("id-form", FAIL, s, "a concept slug is lowercase words joined by -",
                "rename it, e.g. c:sql-server")
            continue
        if name == "Achievement" and O.POSITIONAL.search(local):
            add("id-form", FAIL, s, "a numbered bullet id says where it sits, not what it is",
                "name it after its content: ach_<project>_<two to four words>")
        if parsed.kind not in cls.kinds:
            add("id-home", FAIL, s, f"a {name} does not belong in a {parsed.kind} file",
                f"move it to {' or '.join(k + '.ttl' for k in cls.kinds)}")
            continue
        for p, objs in preds.items():
            if p == O.RDF_TYPE:
                if name != "Concept":
                    add("no-derived", FAIL, s, "rdf:type is derived from the id prefix",
                        "delete the `a …` - the prefix already says what it is")
                continue
            pname = p[len(O.J):] if p.startswith(O.J) else None
            pred = cls.preds.get(pname)
            if pred is None:
                near = difflib.get_close_matches(pname or p, list(cls.preds), n=1)
                add("closed", FAIL, s, f"{curie(p)} is not a {name} predicate",
                    f"did you mean j:{near[0]}?" if near else
                    f"a {name} takes {', '.join('j:' + x for x in cls.preds)}")
                continue
            if pred.card in "1?" and len(objs) > 1:
                add("cardinality", FAIL, s, f"j:{pname} holds {len(objs)} values; one allowed",
                    "keep the one that is true")
            for o in objs:
                problem = check_object(pred, o)
                if problem:
                    add("object", FAIL, s, f"j:{pname} {problem}", object_fix(pred))
        for pred in cls.preds.values():
            if pred.card in "1+" and O.J + pred.name not in preds:
                add("cardinality", FAIL, s, f"j:{pred.name} is required",
                    f"add j:{pred.name} ({pred.doc})")
        if name == "Concept":
            types = preds.get(O.RDF_TYPE, [])
            for t in types:
                if t.value not in {O.J + c for c in O.ENUMS["conceptClass"]}:
                    add("object", FAIL, s, f"a concept is a Capability, Domain or Technology, "
                        f"not {curie(t.value)}", "a j:Capability, j:Domain or j:Technology")
        if O.J + "retired" in preds and O.J + "reason" not in preds:
            add("retired-reason", FAIL, s, "retired without a reason",
                "add j:reason: why it no longer belongs on a resume")
    return out


HEAD_FIX = {
    "KB": 'start the file with k:kb j:format 3 ; j:name "…" ; j:updated "YYYY-MM-DD"^^xsd:date .',
    "Posting": "one k:post_<stem> per posting.ttl; another posting gets its own directory",
    "Application": "one k:app_<stem> per application.ttl; another gets its own directory",
}


def check_object(pred, o):
    """None when `o` is a valid object for `pred`, else what is wrong with it."""
    import pyoxigraph as ox

    kind = pred.obj
    if isinstance(kind, O.Lit):
        if not isinstance(o, ox.Literal):
            return "must be a value, not a reference"
        dt = XSD_TYPES.get(o.datatype.value)
        if dt not in kind.types or o.language:
            return f"is {curie(o.datatype.value)}; expected {' or '.join(kind.types)}"
        if kind.pattern and not re.fullmatch(kind.pattern, o.value):
            return f"{o.value!r} does not have the expected form"
        if kind.lo is not None or kind.hi is not None:
            try:
                n = float(o.value)
            except ValueError:
                return f"{o.value!r} is not a number"
            if (kind.lo is not None and n < kind.lo) or (kind.hi is not None and n > kind.hi):
                return f"{o.value} is out of range"
        if dt == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", o.value):
            return f"{o.value!r} is not YYYY-MM-DD"
        return None
    if not isinstance(o, ox.NamedNode):
        return "must be a reference, not a value"
    if isinstance(kind, O.Enum):
        values = O.ENUMS[kind.name]
        if not (o.value.startswith(O.J) and o.value[len(O.J):] in values):
            return f"{curie(o.value)} is not one of {', '.join(values)}"
        return None
    if isinstance(kind, O.Concept):
        return None if o.value.startswith(O.C) else f"{curie(o.value)} is not a c: concept"
    if isinstance(kind, O.Ref):
        target = O.class_of(o.value)
        if target is None or target == "Concept":
            return f"{curie(o.value)} is not a k: id"
        if kind.classes != O.ANY and target not in kind.classes:
            return f"{curie(o.value)} is a {target}; expected {' or '.join(kind.classes)}"
    return None


def object_fix(pred):
    kind = pred.obj
    if isinstance(kind, O.Enum):
        return "one of " + ", ".join(f"j:{v}" for v in O.ENUMS[kind.name])
    if isinstance(kind, O.Ref):
        return "a k: id" + ("" if kind.classes == O.ANY else f" of a {' or '.join(kind.classes)}")
    if isinstance(kind, O.Concept):
        return "a c: concept (" + ", ".join(kind.classes) + ")"
    return pred.doc


def id_fix(iri):
    prefixes = sorted(p for p in O.BY_PREFIX if not p.startswith("=") and "." not in p)
    return ("ids are k:<prefix>_<words> with prefix one of " + ", ".join(prefixes)
            + "; concepts are c:<words-with-dashes>")
```

- [ ] **Step 4: Write the loader (tier 1 only for now)**

Create `src/jsk/graph/store.py`:

```python
"""The workspace in memory: every record file loaded, types derived, rules run.

Each file is its own named graph, so a finding can say which file it is in; derived
triples go in j:derived, which is never written; queries run over the union. Loading
never raises on bad content - it reports, and the caller decides what a FAIL stops.
"""
import glob
import os
from dataclasses import dataclass, field
from urllib.parse import quote

from . import ontology as O
from .io import GraphError, parse

SHIPPED_VOCABULARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "vocabulary.ttl")


def workspace_files(root, vocabulary=SHIPPED_VOCABULARY):
    """The record files under a workspace root, in a fixed order. Missing ones are absent."""
    found = [os.path.join(root, "career", "kb.ttl"), os.path.join(root, "career", "log.ttl")]
    for pattern in ("posting.ttl", "application.ttl"):
        found += sorted(glob.glob(os.path.join(root, "applications", "*", pattern)))
    found = [f for f in found if os.path.isfile(f)]
    if vocabulary and os.path.isfile(vocabulary):
        found.append(vocabulary)
    return found


@dataclass
class Store:
    root: str
    findings: list = field(default_factory=list)
    parsed: dict = field(default_factory=dict)      # file -> Parsed
    homes: dict = field(default_factory=dict)       # subject iri -> first file defining it
    definitions: dict = field(default_factory=dict)  # subject iri -> every file, load order
    ox: object = None

    def select(self, sparql):
        """Rows of a SELECT over the union graph, as {variable: term}."""
        result = self.ox.query(sparql, use_default_graph_as_union=True)
        names = [var.value for var in result.variables]
        return [{n: sol[n] for n in names if sol[n] is not None} for sol in result]

    def file_of(self, iri):
        return self.homes.get(iri)

    def line_of(self, iri, file=None):
        file = file or self.homes.get(iri)
        return self.parsed[file].lines.get(iri, 0) if file in self.parsed else 0

    def defined(self):
        return self.homes.keys()

    def fails(self):
        return [f for f in self.findings if f.severity == "FAIL"]

    def warns(self):
        return [f for f in self.findings if f.severity == "WARN"]

    def report(self):
        """The findings as a validate_urs.Report, for show() and the gates' output."""
        from ..gates.validate_urs import Report

        rep = Report()
        for f in sorted(self.findings, key=lambda f: (f.file, f.line, f.rule)):
            (rep.fail if f.severity == "FAIL" else rep.warn)(f.text())
        return rep


def load(root, vocabulary=SHIPPED_VOCABULARY, files=None):
    """Load, derive, validate and close over a workspace. `files` overrides discovery."""
    import pyoxigraph as ox

    from .shapes import Finding, tier1

    store = Store(os.path.abspath(root), ox=ox.Store())
    paths = files if files is not None else workspace_files(root, vocabulary)
    derived = ox.NamedNode(O.DERIVED)
    for path in paths:
        name = os.path.relpath(path, store.root).replace("\\", "/")
        if name.startswith("../"):
            name = os.path.basename(path)    # the shipped vocabulary lives outside the root
        try:
            parsed = parse(path)
        except GraphError as e:
            store.findings.append(Finding("syntax", "FAIL", name, e.line or 0, "",
                                          str(e).split(": ", 1)[-1], e.fix))
            continue
        except OSError as e:
            raise GraphError(f"{name}: {e.strerror}", "check the path", name) from None
        parsed.file = name
        store.parsed[name] = parsed
        # Percent-encoded: a hand-made folder can hold a space, and an IRI cannot.
        graph = ox.NamedNode("file:" + quote(name, safe="/-._~"))
        store.ox.extend(ox.Quad(q.subject, q.predicate, q.object, graph) for q in parsed.quads)
        store.findings += tier1(parsed)
        for iri in dict.fromkeys(q.subject.value for q in parsed.quads
                                 if isinstance(q.subject, ox.NamedNode)):
            store.homes.setdefault(iri, name)
            store.definitions.setdefault(iri, []).append(name)
    derive_types(store, derived)
    materialise_paths(store)
    return store


def derive_types(store, derived):
    """rdf:type from each k: id's prefix, into j:derived."""
    import pyoxigraph as ox

    rdf_type = ox.NamedNode(O.RDF_TYPE)
    quads = []
    for iri in store.homes:
        name = O.class_of(iri)
        if name and name != "Concept":
            quads.append(ox.Quad(ox.NamedNode(iri), rdf_type, ox.NamedNode(O.J + name), derived))
    store.ox.extend(quads)


def materialise_paths(store):
    """The counts-as closure within the hop limit, as Path nodes in j:derived.

    One way, narrower to broader: `a isA b` gives a path from a to b, never back. Paths
    of 0, 1 and 2 hops; `implied` when an implies edge is on it, since an implied match
    never satisfies a required requirement (P2's rule). Ported from the graph
    simulation's materialise_paths, S0-S7.
    """
    pre = f"PREFIX j: <{O.J}>\nPREFIX c: <{O.C}>\n"
    kinds = "j:isA, j:partOf, j:implies"
    # A path's id is minted from its ends and its hop count, so one found twice is one node.
    pid = ('BIND(IRI(CONCAT("{derived}/path/", MD5(CONCAT(STR(?a), " ", STR(?via), " ", '
           'STR(?b), " ", STR(?hops))))) AS ?p)').format(derived=O.DERIVED)
    head = ("INSERT { GRAPH j:derived { ?p a j:Path ; j:from ?a ; j:to ?b ; j:hops ?hops ; "
            "j:implied ?imp ; j:via ?via } }")
    for where in (
        """{ SELECT DISTINCT ?a WHERE { GRAPH ?g { ?a a ?t }
               FILTER(?g != j:derived && STRSTARTS(STR(?a), STR(c:))) } }
           BIND(?a AS ?b) BIND(?a AS ?via) BIND(0 AS ?hops) BIND(false AS ?imp)""",
        f"""GRAPH ?g {{ ?a ?k ?b }} FILTER(?g != j:derived && ?k IN ({kinds}))
            BIND(?a AS ?via) BIND(1 AS ?hops) BIND(?k = j:implies AS ?imp)""",
        f"""GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}
            FILTER(?g != j:derived && ?h != j:derived && ?a != ?b)
            FILTER(?k1 IN ({kinds}) && ?k2 IN ({kinds}))
            BIND(2 AS ?hops) BIND(?k1 = j:implies || ?k2 = j:implies AS ?imp)""",
    ):
        store.ox.update(f"{pre}{head} WHERE {{ {where} {pid} }}")
```

In `src/jsk/preflight.py`, change the `GRAPH_MODULES` line to:
```python
GRAPH_MODULES = ["graph", "graph.ontology", "graph.io", "graph.writer", "graph.shapes",
                 "graph.store"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_graph_shapes.py tests/test_graph_store.py tests/test_preflight.py -q`
Expected: all pass. The ten tier-1 mutations each fire at the right line. The closure gives 16 zero-hop paths, the 4 one-hop paths listed, and no two-hop paths.

- [ ] **Step 6: Commit**

```bash
git add src/jsk/graph/shapes.py src/jsk/graph/store.py src/jsk/preflight.py tests/test_graph_shapes.py tests/test_graph_store.py
git commit -m "feat(graph): load a workspace - types derived, per-file rules, the counts-as closure"
```

---

### Task 5: The workspace rules, and the budget

**Files:**
- Create: `src/jsk/graph/rules.py`
- Modify: `src/jsk/graph/store.py` (two lines in `load`)
- Modify: `src/jsk/preflight.py` (`GRAPH_MODULES`)
- Test: `tests/test_graph_rules.py`, `tests/test_graph_budget.py`

**Interfaces:**
- Consumes: `shapes.FAIL/WARN/Finding/curie`, `ontology.*`, and the `Store` methods `.select`, `.file_of`, `.line_of`, `.defined`, `.definitions`; in the tests, `test_graph_shapes.mutated`, `assert_fires`, `KB`, `POSTING` and `APPLICATION`.
- Produces, in `jsk.graph.rules`:
  - `PREFIX`, `COUNTS_AS`, and the frozen dataclass `Rule(id, severity, sparql, detail, fix, post=None)`, where `sparql` may be `None`, in which case `post(rows, store)` produces the rows;
  - `RULES` (a list of `Rule`, with several `concept-class` entries);
  - `tier2(store) -> list[Finding]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_rules.py`:

```python
"""Tier 2: every workspace rule fires, at the right place, on the one edit that breaks it.

Same machinery as tests/test_graph_shapes.py: copy the valid fixture workspace, make one
edit, load, assert the rule names the id at its line with the expected fix.
"""
import unittest

from test_graph_shapes import APPLICATION, KB, POSTING, assert_fires, mutated

from jsk.graph import rules

# rule: (file, old text, new text, focus id, the fix contains). old=None appends new.
MUTATIONS = {
    "dangling": (KB, "j:cites k:met_team ;", "j:cites k:met_teem ;",
                 "k:ach_clinical_events_led_migration", "did you mean k:met_team?"),
    "duplicate-id": (POSTING, None, '\nk:met_team j:subject "engineers" .\n', "k:met_team",
                     "keep it in one file"),
    "concept-typed": (KB, "c:healthcare a j:Domain .",
                      'c:healthcare a j:Domain .\nc:graphql j:label "GraphQL" .', "c:graphql",
                      "a j:Technology"),
    "primary-contact": (KB, 'j:primary "priya@example.com"', 'j:primary "priya@example.org"',
                        "k:person", "one of the email"),
    "headline-xor": (KB, "j:headlineMetric k:met_event_latency ;",
                     "j:headlineMetric k:met_event_latency ; j:noneQuantified true ;",
                     "k:prj_clinical_events", "not both"),
    "metric-open": (KB, '    j:validUntil "2026-03-01"^^xsd:date ;\n', "",
                    "k:met_event_latency", "exactly one version is current"),
    "version-orphan": (KB, "k:met_team.v1 j:of k:met_team", "k:met_team.v1 j:of k:met_sites",
                       "k:met_team.v1", "k:met_x.vN"),
    "version-gap": (KB, "k:met_sites.v1", "k:met_sites.v2", "k:met_sites", "no gap"),
    "rank-unique": (KB, "j:rank 2 ;", "j:rank 1 ;", "k:ach_clinical_events_led_migration",
                    "its own rank"),
    "headline-cited": (KB, "j:cites k:met_sites ;", "j:cites k:met_team ;",
                       "k:prj_site_onboarding", "cite it"),
    "counts-as-cycle": (KB, "c:healthcare a j:Domain .",
                        "c:healthcare a j:Domain ; j:partOf c:aged-care .", "c:healthcare",
                        "one way"),
    "wall-crossed": (KB, "c:kafka j:isA c:event-driven-architecture .",
                     "c:kafka j:isA c:event-driven-architecture ; "
                     "j:distinct c:event-driven-architecture .", "c:kafka", "contradict"),
    "label-clash": (KB, 'j:label "people leadership"', 'j:label "Kafka", "people leadership"',
                    "c:team-leadership", "matching will ask"),
    "inferred-unasked": (KB, "k:q_sites_bullet j:about k:ach_site_onboarding_sites_one_platform",
                         "k:q_sites_bullet j:about k:prj_site_onboarding",
                         "k:ach_site_onboarding_sites_one_platform", "add a q_"),
    "retired-referenced": (KB, None,
                           '\nk:ach_intranet_refresh_pages j:project k:prj_intranet_refresh ; '
                           'j:rank 1 ; j:text "Rebuilt the intranet." ; '
                           'j:provenance j:confirmed .\n',
                           "k:ach_intranet_refresh_pages", "live entry"),
    "answered-before-asked": (KB, 'j:answered "2026-08-14"', 'j:answered "2026-08-10"',
                              "k:q_team_size", "correct one"),
    "application-posting": ("applications/other-role/application.ttl", None,
                            '@prefix j: <tag:jsk,2026:ns#> .\n@prefix k: <tag:jsk,2026:id/> .\n'
                            'k:app_other_role j:posting k:post_acme_platform_engineer ;\n'
                            '    j:submitted false .\n', "k:app_other_role", "beside it"),
    "event-before-submit": (APPLICATION, 'j:date "2026-09-15"^^xsd:date',
                            'j:date "2026-09-01"^^xsd:date',
                            "k:evt_acme_platform_engineer_2026_09_15_screen_scheduled",
                            "events follow"),
    "concept-class": (KB, "j:industry c:healthcare", "j:industry c:kafka", "k:org_meridian",
                      "of that class"),
}

WARNS = {"version-gap", "headline-cited", "label-clash", "inferred-unasked",
         "retired-referenced", "event-before-submit"}


class EveryRuleFires(unittest.TestCase):
    def test_every_rule_has_a_mutation(self):
        self.assertEqual({r.id for r in rules.RULES}, set(MUTATIONS))

    def test_each_mutation_fires_its_rule_at_the_right_line(self):
        for rule, mutation in MUTATIONS.items():
            with self.subTest(rule=rule):
                assert_fires(self, rule, mutation)

    def test_severity(self):
        for r in rules.RULES:
            self.assertEqual(r.severity, "WARN" if r.id in WARNS else "FAIL", r.id)


class Findings(unittest.TestCase):
    def test_a_finding_names_file_line_id_and_fix(self):
        s, _ = mutated(MUTATIONS["dangling"])
        [f] = [f for f in s.findings if f.rule == "dangling"]
        self.assertRegex(f.text(), r"^career/kb\.ttl:\d+ k:ach_clinical_events_led_migration - "
                                   r"j:cites k:met_teem: nothing defines it\n        fix: "
                                   r"did you mean k:met_team\?$")

    def test_a_duplicate_is_reported_where_it_was_added(self):
        s, _ = mutated(MUTATIONS["duplicate-id"])
        [f] = [f for f in s.findings if f.rule == "duplicate-id"]
        self.assertEqual(f.file, POSTING)
        self.assertIn("also defined in career/kb.ttl", f.detail)

    def test_a_wall_holds_whichever_side_declares_it(self):
        # distinct is symmetric: written on the broader concept, it still stops kafka.
        assert_fires(self, "wall-crossed", (
            KB, "c:event-driven-architecture a j:Capability ;",
            "c:event-driven-architecture a j:Capability ; j:distinct c:kafka ;",
            "c:event-driven-architecture", "contradict"))

    def test_the_log_may_name_ids_that_no_longer_exist(self):
        s, _ = mutated(("career/log.ttl", "j:touched k:met_team.v1,", "j:touched k:met_gone.v1,",
                        "", ""))
        self.assertEqual([f.text() for f in s.findings if f.rule == "dangling"], [])


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_graph_budget.py`:

```python
"""The cost of loading a realistic workspace - the price every graph command pays."""
import tempfile
import time
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from jsk.graph import store


def big_workspace(root, projects=300, applications=100):
    """A valid career of `projects` projects, 3 bullets each, and `applications`
    applications - about 10,000 quads, P0's measured size."""
    pfx = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES) + "\n"
    kb = [pfx, 'k:kb j:format 3 ; j:name "Big" ; j:updated "2026-09-20"^^xsd:date .\n',
          'k:person j:fullName "Big" ; j:provenance j:confirmed .\n',
          'k:org_o j:name "O" ; j:relationship j:employer ; j:provenance j:confirmed .\n',
          'k:pos_p j:organisation k:org_o ; j:title "T" ; j:start "2020-01" ; '
          'j:state j:ongoing ; j:seniority j:hands-on ; j:provenance j:confirmed .\n']
    for n in range(projects):
        kb.append(f'k:prj_p{n} j:name "Project {n}" ; j:position k:pos_p ; j:strength 3 ; '
                  f'j:recency 2024 ; j:domain c:healthcare ; j:uses c:kafka, c:python ; '
                  f'j:headlineMetric k:met_m{n} ; j:problem """Line one.\nLine two.""" ; '
                  f'j:provenance j:confirmed .\n'
                  f'k:met_m{n} j:subject "m{n}" .\n'
                  f'k:met_m{n}.v1 j:of k:met_m{n} ; j:value {n} ; j:confidence j:measured ; '
                  f'j:provenance j:confirmed .\n')
        for b in range(3):
            kb.append(f'k:ach_p{n}_bullet_{"abc"[b]} j:project k:prj_p{n} ; j:rank {b + 1} ; '
                      f'j:text "Did thing {b}." ; j:cites k:met_m{n} ; j:shows c:kafka ; '
                      f'j:provenance j:confirmed .\n')
    kb.append("c:healthcare a j:Domain .\n")
    (root / "career").mkdir()
    (root / "career" / "kb.ttl").write_text("".join(kb), encoding="utf-8")
    for a in range(applications):
        d = root / "applications" / f"a{a}"
        d.mkdir(parents=True)
        (d / "posting.ttl").write_text(
            pfx + f'k:post_a{a} j:company "C" ; j:title "T" ; j:captured "2026-09-01"^^xsd:date ;'
            f' j:advert "posting.md" .\n'
            + "".join(f'k:req_a{a}_r{r} j:posting k:post_a{a} ; j:asked "Kafka" ; '
                      f'j:necessity j:required ; j:quote "Kafka" .\n' for r in range(5)),
            encoding="utf-8")
        (d / "application.ttl").write_text(
            pfx + f'k:app_a{a} j:posting k:post_a{a} ; j:submitted "2026-09-02"^^xsd:date ; '
            f'j:carried k:ach_p{a}_bullet_a ; j:carriedVersion k:met_m{a}.v1 .\n'
            f'k:evt_a{a}_submitted j:application k:app_a{a} ; j:date "2026-09-02"^^xsd:date ; '
            f'j:kind j:submitted .\n', encoding="utf-8")


class Budget(unittest.TestCase):
    """Every command loads and validates the whole workspace, so it has to stay cheap.

    Target: under 400 ms for this workspace (P1 measured 250-390 ms on a Windows laptop,
    Python 3.13). Asserted at 3x, so a slow CI runner does not make it flaky; the figure
    is printed so a creeping cost shows in the log before it fails.
    """

    def test_ten_thousand_quads(self):
        with tempfile.TemporaryDirectory() as tmp:
            big_workspace(Path(tmp))
            store.load(tmp)                      # warm: the first query compiles caches
            start = time.perf_counter()
            s = store.load(tmp)
            ms = (time.perf_counter() - start) * 1000
            quads = len(s.ox)
            print(f"\n  budget: {quads} quads loaded and validated in {ms:.0f} ms")
            self.assertGreater(quads, 9000)
            self.assertEqual([f.text() for f in s.fails()], [])
            self.assertLess(ms, 1200)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_rules.py tests/test_graph_budget.py -q`
Expected: `test_graph_rules` fails to import (`cannot import name 'rules'`). `test_graph_budget` passes already, because tier 1 alone is cheaper; it guards the cost once tier 2 is added.

- [ ] **Step 3: Write the workspace rules**

Create `src/jsk/graph/rules.py`:

```python
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
              ?focus j:project ?p ; j:rank ?r . FILTER(STR(?a) < STR(?focus)) }""",
         lambda r: f"rank {v(r, 'r')} is also {curie(v(r, 'a'))}'s",
         "give each bullet of a project its own rank"),
    Rule("headline-cited", WARN,
         """SELECT ?focus ?m WHERE { ?focus j:headlineMetric ?m
              FILTER NOT EXISTS { ?a j:project ?focus ; j:cites ?m } }""",
         lambda r: f"headline {curie(v(r, 'm'))} is cited by none of its bullets",
         "cite it from the bullet that states it, or change the headline"),
    Rule("counts-as-cycle", FAIL,
         f"""SELECT DISTINCT ?focus WHERE {{ ?focus ({COUNTS_AS})+ ?focus }}""",
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
    for rule in RULES:
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
```

- [ ] **Step 4: Run tier 2 from the loader**

In `src/jsk/graph/store.py`, inside `load`, replace
```python
    from .shapes import Finding, tier1
```
with
```python
    from .rules import tier2
    from .shapes import Finding, tier1
```
and replace
```python
    derive_types(store, derived)
    materialise_paths(store)
```
with
```python
    derive_types(store, derived)
    store.findings += tier2(store)
    materialise_paths(store)
```

In `src/jsk/preflight.py`, change `GRAPH_MODULES` to:
```python
GRAPH_MODULES = ["graph", "graph.ontology", "graph.io", "graph.writer", "graph.shapes",
                 "graph.rules", "graph.store"]
```

- [ ] **Step 5: Run the graph tests to verify they pass**

Run: `python -m pytest tests/test_graph_ontology.py tests/test_graph_io.py tests/test_graph_writer.py tests/test_graph_shapes.py tests/test_graph_rules.py tests/test_graph_store.py tests/test_graph_budget.py -q -s`
Expected: 64 passed and about 630 subtests. `TheFixtureIsClean` still reports no findings now that tier 2 runs, and the budget line reads about `15725 quads loaded and validated in 250-400 ms`. If `TheFixtureIsClean` fails here, a tier-2 rule is wrong about the valid fixture. Fix the rule, not the fixture.

- [ ] **Step 6: Commit**

```bash
git add src/jsk/graph/rules.py src/jsk/graph/store.py src/jsk/preflight.py tests/test_graph_rules.py tests/test_graph_budget.py
git commit -m "feat(graph): the workspace rules - references, versions, walls, applications"
```

---

### Task 6: CI on the floor and on Windows, and the exit check

**Files:**
- Modify: `.github/workflows/test.yml`

The last CI runs (2026-09-01) all failed at **Preflight** in the no-engine job. Without a TeX engine, `jsk doctor --quick` is BLOCKED by design and exits 1. P1 adds two more no-engine jobs, so the step now checks that the TeX engine is the only FAIL.

- [ ] **Step 1: Replace the workflow**

Replace the whole of `.github/workflows/test.yml` with:

```yaml
name: tests

# The suite this guards was deleted once, in 7d42326, and five defects shipped in the
# release that followed - every one of them covered by an assertion that was sitting in
# the deleted files. A suite nobody runs is a suite that gets deleted again, so it runs
# here on every push rather than on somebody's machine when they remember.

on:
  push:
    branches: ["**"]
  pull_request:
  workflow_dispatch:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # With and without a TeX engine, because the suite deliberately covers both worlds.
  # Four tests are skipUnless(tex.available_engine()) and two more are the mirror image -
  # they run only when no engine is present, checking that the tooling says so rather than
  # pretending a resume was verified. The no-engine path is the one a new contributor hits.
  #
  # Python 3.10 because it is the floor pyproject.toml states, and a floor nobody runs is a
  # guess. Windows because the graph record is files a person edits: CRLF, paths and file
  # locks differ there, and pyoxigraph's wheel is a separate build (LadybugDB's Windows
  # wheels were broken for five releases while Linux passed).
  suite:
    name: ${{ matrix.name }}
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash
    strategy:
      fail-fast: false
      matrix:
        include:
          - name: with a TeX engine
            os: ubuntu-latest
            python: "3.13"
            tex: true
          - name: without a TeX engine
            os: ubuntu-latest
            python: "3.13"
            tex: false
          - name: Python 3.10, without a TeX engine
            os: ubuntu-latest
            python: "3.10"
            tex: false
          - name: Windows, without a TeX engine
            os: windows-latest
            python: "3.13"
            tex: false

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e '.[dev]'

      - name: Install tectonic
        if: matrix.tex
        run: |
          curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh
          sudo mv tectonic /usr/local/bin/

      # A silently failed install would turn this job into a duplicate of the other one,
      # and the four engine-gated tests would skip in both while the log still claimed
      # they ran. This repo's own rule: a gate that did not run is not a gate that passed.
      - name: Assert the engine is really there
        if: matrix.tex
        run: tectonic --version

      - name: Assert there is no engine
        if: ${{ !matrix.tex }}
        run: |
          for engine in tectonic xelatex pdflatex lualatex latexmk; do
            if command -v "$engine" >/dev/null; then
              echo "FAIL  $engine is on PATH - this job covers the no-engine path"
              exit 1
            fi
          done
          echo "ok    no TeX engine on PATH"

      # A linter that is not run is a linter that is switched off. Scoped in
      # pyproject.toml to the rules that pass clean today, so a new finding here is a
      # new problem rather than a pre-existing one.
      - name: Lint
        run: python -m ruff check src tests

      # `jsk doctor` is what tells a person what this machine can do. If it disagrees
      # with the machine, every gap it reports afterwards is untrustworthy - so it runs
      # before the tests and its output is the log's header. `--quick` because the
      # verifying run renders a PDF, which the no-engine job cannot do and the tests
      # cover anyway.
      #
      # Without an engine doctor is BLOCKED by design - the PDF is the deliverable - and
      # exits 1. That failed every no-engine run from 2026-09-01. Those jobs now assert
      # the verdict is BLOCKED for that reason and no other: the TeX engine is the only FAIL.
      - name: Preflight
        run: |
          set +e
          jsk doctor --quick | tee doctor.txt
          code=${PIPESTATUS[0]}
          set -e
          if [ "${{ matrix.tex }}" = "true" ]; then exit "$code"; fi
          fails=$(grep -c '^  FAIL' doctor.txt || true)
          if grep -q '^  FAIL  TeX engine' doctor.txt && [ "$fails" = "1" ]; then
            echo "ok    BLOCKED only by the missing TeX engine, as this job intends"
          else
            echo "FAIL  expected the TeX engine to be the only FAIL, found $fails"
            exit 1
          fi

      - name: Tests
        run: python -m pytest tests -q -rs -n auto

# The manifest surface - the two plugin versions agreeing, every subcommand `jsk`
# dispatches being named in SKILL.md and docs/SCRIPTS.md, the agent boundary still
# being written in the agent files - is pinned by tests/test_plugin_surface.py rather
# than by a job here. It belongs in the suite: a contributor gets the failure on their
# own machine, and there is only ever one copy of the rule to keep true.
```

- [ ] **Step 2: Check the workflow parses and the step logic holds**

Run: `python -c "import yaml; d = yaml.safe_load(open('.github/workflows/test.yml', encoding='utf-8')); print([m['name'] for m in d['jobs']['suite']['strategy']['matrix']['include']])"`
Expected: `['with a TeX engine', 'without a TeX engine', 'Python 3.10, without a TeX engine', 'Windows, without a TeX engine']`

- [ ] **Step 3: The exit check, locally**

Run each command and compare with the spec's exit criteria (`docs/superpowers/specs/2026-09-24-graph-core-design.md`, "Exit criteria"):
- `python -m pytest tests -q -n auto`: everything passes, the existing suite unmodified apart from `tests/test_preflight.py`'s new class (criteria 3 and 5).
- `python -m ruff check src tests`: `All checks passed!` (criterion 3).
- `jsk doctor --quick`: `ok    graph record package`, `ok    pyoxigraph`, and a verdict no worse than before this branch (criterion 4).
- `python -m pytest tests/test_graph_shapes.py::TheFixtureIsClean tests/test_graph_writer.py::FixturesAreCanonical -q`: pass (criterion 1).
- `python -m pytest tests/test_graph_shapes.py::EveryRuleFires tests/test_graph_rules.py::EveryRuleFires -q`: pass (criterion 2).

If Docker is available, also run the suite on the floor: `docker run --rm -v "$PWD":/w -w /w python:3.10-slim sh -c "pip install -q -e '.[dev]' && python -m pytest tests -q -n auto"`. Expected: it passes (tests that need TeX skip).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: run the floor (3.10) and Windows, and let no-engine jobs pass preflight honestly"
```

- [ ] **Step 5: CI**

Push the branch **only if your human partner asks**. After a push, all four jobs must be green. A red Windows job is the platform-gap risk the roadmap names, so report it; don't skip it.
