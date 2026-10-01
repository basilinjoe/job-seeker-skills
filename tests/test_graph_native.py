"""The graph-native application's record: what docs/superpowers/plans/
2026-10-01-graph-native-applications-mcp.md's Rulings 1-10 put in the graph, read back as
it went in.

Each structure a model's decisions become - the advert's lines, a posting's rows, the
analyst's review, the selection, a person's no - has one function to triples and one back,
and the round trip is the rule: what the graph holds is what was decided, nothing lost and
nothing added. The row checks are `jsk posting build`'s, one row at a time, each refusal
planted. A no answers a requirement only when confirmed and live (Rulings 8 and 9), and
answers one asking for anything that counts as its concept, never anything broader. And the
two new graph kinds load, validate and move with their application like the others.
"""
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

import pyoxigraph as ox

import careerkit
from jsk.domain import ontology as O
from jsk.domain.assessment import fold, review
from jsk.domain.assessment.derive import derive
from jsk.domain.assessment.overlay import Overlay, Row
from jsk.domain.posting import lines as L
from jsk.domain.posting.advert import advert_lines
from jsk.domain.posting.rows import Rows, coverage
from jsk.domain.record import absence as A
from jsk.domain.resume import selection
from jsk.domain.resume.short import KEYS, digest

ADVERT = """https://acme.example/jobs/42

# Platform Engineer
Acme Health · Melbourne

## What you'll do

- Run the clinical event platform for forty hospitals.

## What you'll bring

- Deep, hands-on K8s experience in production.
- Event-driven systems a plus.
- Australian work rights; hybrid in Melbourne.
"""
TODAY = datetime.date(2026, 10, 2)


def facts(triples):
    return {(t.subject, t.predicate, t.object) for t in triples}


class AdvertLines(unittest.TestCase):
    def test_the_lines_come_back_as_advert_lines_numbered_them_with_their_drops(self):
        lines = advert_lines(ADVERT)
        # Every flag is exercised: an optional line, an eligibility line, a responsibility.
        self.assertTrue(any(x.optional for x in lines) and any(x.elig for x in lines))
        self.assertIn("responsibility", {x.section for x in lines})
        drops = {lines[-1].n: "eligibility, in gaps"}
        back = L.from_triples(L.triples(O.K + "post_acme", "acme", lines, drops))
        self.assertEqual(back, (lines, drops))

    def test_a_line_id_is_derived_from_the_stem_and_number(self):
        self.assertEqual(L.line_id("acme", 3), "line_acme_3")
        self.assertEqual(O.class_of(O.K + L.line_id("acme", 3)), "AdvertLine")


class RowChecks(unittest.TestCase):
    """domain/posting/rows.py: build's checks, a row at a time - each refusal planted."""

    def setUp(self):
        self.lines = {x.n: x for x in advert_lines(ADVERT)}
        self.k8s = next(x.n for x in self.lines.values() if "K8s" in x.text)
        self.resp = next(x.n for x in self.lines.values() if x.section == "responsibility")
        self.rows = Rows(self.lines, at=lambda label: f"row {label}", listed="a line",
                         refetch="fix:  read the lines")

    def fails(self, found):
        return [message for severity, message, _ in found if severity == "FAIL"]

    def test_a_good_row_passes_and_counts_its_line(self):
        self.assertEqual(self.rows.row(1, self.k8s, "k8s", "K8s"), [])
        self.assertIn(self.k8s, self.rows.used)

    def test_a_line_that_is_not_the_adverts(self):
        [msg] = self.fails(self.rows.row(1, 99, "x", "x"))
        self.assertEqual(msg, f"row 1: line 99 is not one a line (1-{len(self.lines)})")

    def test_an_asked_term_its_line_does_not_say(self):
        [msg] = self.fails(self.rows.row(1, self.k8s, "kafka", "Kafka"))
        self.assertIn("'Kafka' is not in line", msg)

    def test_asked_is_matched_whatever_its_case_and_typography(self):
        self.assertEqual(self.rows.row(1, self.k8s, "k8s", "hands‑on  k8s"), [])

    def test_a_slug_used_twice(self):
        self.rows.row(1, self.k8s, "k8s", "K8s")
        [msg] = self.fails(self.rows.row(2, self.k8s, "k8s", "production"))
        self.assertEqual(msg, "row 2: slug 'k8s' is used on line 1 too")

    def test_one_term_asked_twice(self):
        self.rows.row(1, self.k8s, "k8s", "K8s")
        [msg] = self.fails(self.rows.row(2, self.k8s, "kube", "k8s"))
        self.assertEqual(msg, "row 1 and line 2: two requirements ask 'k8s'")

    def test_a_quote_that_is_not_its_line(self):
        [msg] = self.fails(self.rows.row(1, self.k8s, "k8s", "K8s", quote="K8s experience"))
        self.assertIn("the quote is not line", msg)
        self.assertEqual(self.rows.row(2, self.k8s, "k8s2", "production",
                                       quote=self.lines[self.k8s].text), [])

    def test_a_necessity_that_is_none(self):
        [msg] = self.fails(self.rows.row(1, self.k8s, "k8s", "K8s", need="essential"))
        self.assertIn("need 'essential' is not one of", msg)

    def test_a_responsibility_made_required_without_saying_so_warns(self):
        [(severity, msg, _)] = self.rows.necessity(1, self.resp, "events", "required")
        self.assertEqual(severity, "WARN")
        self.assertIn("makes responsibility line", msg)
        self.assertEqual(self.rows.necessity(1, self.k8s, "k8s", "required"), [])

    def test_a_drop_of_a_line_that_is_not_the_adverts(self):
        [msg] = self.fails(self.rows.drop(1, 99))
        self.assertIn("line 99 is not one a line", msg)

    def test_every_qualification_line_must_be_used_or_dropped_but_eligibility(self):
        quals = [x.n for x in self.lines.values()
                 if x.section == "qualification" and not x.elig]
        self.assertEqual(self.rows.uncovered(), quals)
        self.rows.row(1, self.k8s, "k8s", "K8s")
        for n in quals:
            if n != self.k8s:
                self.rows.drop(2, n)
        self.assertEqual(self.rows.uncovered(), [])

    def test_the_coverage_finding_names_every_line(self):
        self.assertEqual(coverage([3, 4], "decisions.txt"),
                         ("FAIL", "decisions.txt: advert lines 3, 4 neither used nor dropped",
                          "fix:  a row for what it asks, or `n | - | <reason>`"))


class Review(unittest.TestCase):
    def test_an_overlay_comes_back_as_it_went_in(self):
        # Rows by slug, numbered from 1: the order the review graph reads them back in.
        overlay = Overlay(fit="partial", eligibility="Australian, hybrid is fine",
                          rows=[Row(1, "eda", "partial", "Kafka only, no Pulsar"),
                                Row(2, "k8s", "keep")],
                          short=["vector databases | the products the advert names", "Go"],
                          surplus=["clinical domain"],
                          ask=["Have you used Pinecone?", "Which cloud?"],
                          about={"Which cloud?": "cloud"})
        self.assertEqual(review.overlay_of(review.triples(overlay, "acme", "draft")), overlay)
        # The ask's requirement is the item's j:about (Ruling 4).
        abouts = [t.object.value for t in review.triples(overlay, "acme")
                  if t.predicate.value == O.J + "about"]
        self.assertEqual(abouts, [O.K + "req_acme_cloud"])

    def test_an_empty_review_is_an_empty_overlay(self):
        self.assertEqual(review.overlay_of(review.triples(Overlay(), "acme")), Overlay())


DOC = {"resume": 2, "bullets": ["ach_events_latency", "ach_identity_sso"],
       "roles": ["pos_meridian_lead"], "skills": ["skill_kubernetes", "skill_dotnet"],
       "format": "ats-maximal", "region": "au", "pages": 2, "ats_pages": 3, "floor": "inferred",
       "summary": {"text": "Platform engineer.\nTwelve years.", "status": "confirmed",
                   "answer": "Yes, that is how I would put it.",
                   "text_sha256": digest("Platform engineer.\nTwelve years.")},
       "headline": {"text": "Platform Engineer", "status": "inferred"},
       "names": {"skill_kubernetes": "K8s", "skill_dotnet": "C#"}}


class Selection(unittest.TestCase):
    def test_every_key_of_resume_json_comes_back_as_it_went_in(self):
        self.assertEqual(set(DOC), set(KEYS))      # the test covers the whole format
        self.assertEqual(selection.doc_of(selection.triples_of(DOC, "sel_app_acme")), DOC)

    def test_a_skill_renamed_but_not_listed_keeps_its_name(self):
        doc = {"resume": 2, "bullets": ["ach_events_latency"],
               "names": {"skill_kubernetes": "K8s"}}
        self.assertEqual(selection.doc_of(selection.triples_of(doc, "sel_cv_general")), doc)

    def test_a_selection_at_every_default_still_names_itself(self):
        doc = {"resume": 2, "bullets": ["ach_events_latency"]}
        triples = selection.triples_of(doc, "sel_app_acme")
        self.assertIn(O.K + "sel_app_acme", {t.subject.value for t in triples})
        self.assertEqual(selection.doc_of(triples), doc)

    def test_canonical_text_is_the_same_whatever_the_key_order(self):
        shuffled = dict(reversed(list(DOC.items())))
        shuffled["summary"] = dict(reversed(list(DOC["summary"].items())))
        self.assertEqual(selection.canonical(shuffled), selection.canonical(DOC))
        self.assertEqual(selection.sha256(shuffled), selection.sha256(DOC))
        self.assertRegex(selection.sha256(DOC), r"\A[0-9a-f]{64}\Z")
        # Ruling 7: what the doc says, nothing about how a dict happened to be built.
        self.assertTrue(selection.canonical(DOC).startswith('{"ats_pages":3,"bullets":'))


def no(concept, said="2026-09-01", provenance="confirmed", answer="Never used it."):
    return A.Absence(O.K + "abs_" + concept.replace("-", "_"), O.C + concept,
                     datetime.date.fromisoformat(said), answer, provenance)


class Absences(unittest.TestCase):
    def test_a_no_lapses_a_year_after_it_was_said(self):
        said = datetime.date(2025, 10, 2)
        self.assertTrue(A.live(said, said + datetime.timedelta(days=A.LAPSE_DAYS - 1)))
        self.assertFalse(A.live(said, said + datetime.timedelta(days=A.LAPSE_DAYS)))
        self.assertTrue(A.live("2026-09-01", "2026-10-02"))

    def test_only_a_confirmed_live_unretired_no_stands(self):
        lapsed, inferred = no("go", said="2025-09-01"), no("rust", provenance="inferred")
        retired = A.Absence(O.K + "abs_x", O.C + "x", TODAY, "no", "confirmed", retired=True)
        self.assertEqual(set(A.standing([no("kafka"), lapsed, inferred, retired], TODAY)),
                         {O.C + "kafka"})
        self.assertEqual(A.due([no("kafka"), lapsed, inferred], TODAY), [lapsed])

    def test_absences_are_read_from_the_career(self):
        k, j = (lambda x: ox.NamedNode(O.K + x)), (lambda x: ox.NamedNode(O.J + x))
        s = k("abs_kafka")
        graph = [ox.Triple(s, j("concept"), ox.NamedNode(O.C + "kafka")),
                 ox.Triple(s, j("said"), ox.Literal("2026-09-01",
                                                    datatype=ox.NamedNode(O.XSD + "date"))),
                 ox.Triple(s, j("answer"), ox.Literal("Never used Kafka.")),
                 ox.Triple(s, j("provenance"), j("confirmed"))]
        self.assertEqual(A.of_triples(graph), [no("kafka", answer="Never used Kafka.")])


def result():
    """A match result for two requirements: Kafka, required and missing, and one listing
    alternatives - with the questions the match asks of them."""
    return {"posting": "k:post_acme", "requirements": [
        {"id": "k:req_acme_kafka", "asked": "Kafka", "necessity": "required", "state": "missing",
         "verdict": "unsatisfied", "concepts": ["c:kafka"], "carriers": [], "near": []},
        {"id": "k:req_acme_cloud", "asked": "AWS or GCP", "necessity": "preferred",
         "state": "ambiguous", "verdict": "indeterminate", "concepts": ["c:aws", "c:gcp"],
         "carriers": [], "near": []}],
        "questions": [{"kind": "ambiguous", "requirement": "AWS or GCP",
                       "detail": ["c:aws", "c:gcp"]}]}


def ask(q):
    return f"- **{q['kind']}** {q['requirement']}"


class DeriveWithAbsences(unittest.TestCase):
    """Ruling 9: a confirmed, unlapsed no answers the requirement it covers, once."""

    def derived(self, *absences):
        return derive(result(), None, ask, absences=list(absences), today=TODAY)

    def row(self, d, slug):
        return next(r for r in d.rows if r.slug == slug)

    def test_with_no_absence_both_are_asked(self):
        d = derive(result(), None, ask)
        self.assertEqual(len(d.questions), 2)
        self.assertEqual([req for _, req in d.asks], ["k:req_acme_kafka", "k:req_acme_cloud"])

    def test_a_confirmed_no_settles_the_requirement_with_its_words_and_asks_nothing(self):
        d = self.derived(no("kafka", answer="Never used Kafka."))
        kafka = self.row(d, "kafka")
        self.assertEqual((kafka.state, kafka.matched, kafka.basis),
                         ("missing", "unsatisfied", "said on 2026-09-01: Never used Kafka."))
        self.assertEqual(d.questions, ("**ambiguous** AWS or GCP",))

    def test_an_inferred_no_does_nothing(self):
        self.assertEqual(self.derived(no("kafka", provenance="inferred")),
                         derive(result(), None, ask))

    def test_a_lapsed_no_does_nothing_and_is_due(self):
        lapsed = no("kafka", said="2025-09-01")
        self.assertEqual(self.derived(lapsed), derive(result(), None, ask))
        self.assertEqual(A.due([lapsed], TODAY), [lapsed])

    def test_one_alternative_denied_still_asks(self):
        d = self.derived(no("aws"))
        self.assertEqual(self.row(d, "cloud").basis, derive(result(), None, ask).rows[1].basis)
        self.assertIn("**ambiguous** AWS or GCP", d.questions)

    def test_every_alternative_denied_settles_it(self):
        d = self.derived(no("aws", answer="No AWS."), no("gcp", answer="No GCP."))
        self.assertEqual(self.row(d, "cloud").basis,
                         "said on 2026-09-01: No AWS. / said on 2026-09-01: No GCP.")
        self.assertNotIn("**ambiguous** AWS or GCP", d.questions)


def layered():
    """A match result asking for EKS (which counts as Kubernetes), for Kubernetes itself,
    and for EKS or GKE - any of them."""
    def req(slug, concepts):
        return {"id": f"k:req_acme_{slug}", "asked": slug.upper(), "necessity": "required",
                "state": "missing", "verdict": "unsatisfied", "concepts": concepts,
                "carriers": [], "near": []}
    return {"posting": "k:post_acme", "questions": [], "requirements": [
        req("eks", ["c:eks"]), req("k8s", ["c:kubernetes"]), req("managed", ["c:eks", "c:gke"])]}


# The vocabulary's own: EKS and GKE are each a Kubernetes (data/vocabulary.ttl).
COUNTS_AS = {O.C + "eks": {O.C + "kubernetes"}, O.C + "gke": {O.C + "kubernetes"}}


class NarrowerDenied(unittest.TestCase):
    """Ruling 9's amendment (2026-10-02): a no to X also denies whatever counts as X, by
    the match's own closure - never the reverse."""

    def derived(self, *absences):
        return derive(layered(), None, ask, absences=list(absences), today=TODAY,
                      counts_as=lambda c: COUNTS_AS.get(c, set()))

    def basis(self, d, slug):
        return next(r for r in d.rows if r.slug == slug).basis

    def test_a_no_to_a_concept_covers_one_that_counts_as_it(self):
        d = self.derived(no("kubernetes", answer="Never run Kubernetes."))
        self.assertEqual(self.basis(d, "eks"), "said on 2026-09-01: Never run Kubernetes.")
        # Every alternative counts as Kubernetes, so the any-of is settled too.
        self.assertEqual(self.basis(d, "managed"), "said on 2026-09-01: Never run Kubernetes.")

    def test_a_no_to_a_narrower_concept_does_not_cover_a_broader_one(self):
        d = self.derived(no("eks", answer="No EKS."))
        self.assertEqual(self.basis(d, "eks"), "said on 2026-09-01: No EKS.")
        self.assertEqual(self.basis(d, "k8s"), "nothing in the record holds c:kubernetes")

    def test_any_of_is_still_settled_only_when_every_alternative_is_denied(self):
        d = self.derived(no("eks"))
        self.assertEqual(self.basis(d, "managed"), "nothing in the record holds c:eks, c:gke")
        d = self.derived(no("eks", answer="No EKS."), no("gke", answer="No GKE."))
        self.assertEqual(self.basis(d, "managed"),
                         "said on 2026-09-01: No EKS. / said on 2026-09-01: No GKE.")

    def test_the_store_closure_says_eks_counts_as_kubernetes(self):
        from jsk.adapters.cli.compose import record
        from jsk.infra.oxigraph.queries import OxigraphQueries

        with tempfile.TemporaryDirectory() as tmp:
            root, _ = careerkit.workspace(Path(tmp) / "ws")
            queries = OxigraphQueries(record.load(root))
            self.assertIn(O.C + "kubernetes", queries.counts_as(O.C + "eks"))
            self.assertNotIn(O.C + "eks", queries.counts_as(O.C + "kubernetes"))


class Asks(unittest.TestCase):
    """Ruling 5: a graph-native assessment's questions are j:Ask nodes; a file-built
    application's assessment keeps its j:questions text."""

    def assessment(self):
        return fold.fold(derive(result(), None, ask), Overlay())

    def preds(self, triples, subject_prefix):
        return [t for t in triples if t.subject.value.startswith(O.K + subject_prefix)]

    def test_each_question_is_a_node_with_its_requirement_and_concepts(self):
        triples = fold.triples(self.assessment(), TODAY, native=True)
        self.assertFalse([t for t in triples if t.predicate.value == O.J + "questions"])
        asks = self.preds(triples, "ask_acme_")
        by = {}
        for t in asks:
            by.setdefault(t.subject.value[len(O.K):], {}).setdefault(
                t.predicate.value[len(O.J):], set()).add(t.object.value)
        self.assertEqual(by["ask_acme_2"]["requirement"], {O.K + "req_acme_cloud"})
        self.assertEqual(by["ask_acme_2"]["concept"], {O.C + "aws", O.C + "gcp"})
        self.assertEqual(by["ask_acme_1"]["position"], {"1"})

    def test_a_file_built_assessment_is_written_as_it_was(self):
        triples = fold.triples(self.assessment(), TODAY)
        self.assertEqual(self.preds(triples, "ask_"), [])
        [text] = [t.object.value for t in triples if t.predicate.value == O.J + "questions"]
        self.assertEqual(text.count("\n"), 1)


class Kinds(unittest.TestCase):
    """The review and resume graphs are record kinds: written through the application's
    write gate, loaded, validated - and refused once the application is sent."""

    APP = "applications/contoso-platform"
    STEM = "contoso_platform"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws")
        self.app = Path(self.root) / self.APP

    def write(self, graphs):
        from jsk.adapters.cli.compose import timeline

        return timeline.write_app_graphs(self.app, graphs)

    def overlay(self):
        return Overlay(fit="partial", rows=[Row(1, "kubernetes", "partial", "AKS only")],
                       ask=["Which cluster?"])

    def test_kinds_sections_and_heads(self):
        self.assertEqual(O.kind_of(f"{self.APP}/review"), "review")
        self.assertEqual(O.kind_of("resumes/general/resume"), "resume")
        self.assertEqual((O.HEADS["review"], O.HEADS["resume"]), ("Review", "Selection"))
        for local, cls in (("rvw_x", "Review"), ("rvr_x_y", "ReviewRow"), ("rvi_x_ask_1",
                                                                         "ReviewItem"),
                           ("sel_app_x", "Selection"), ("pck_app_x_bullets_1", "Pick"),
                           ("ask_x_1", "Ask"), ("abs_kafka", "Absence"), ("rev_1", "LogEntry")):
            self.assertEqual(O.class_of(O.K + local), cls)

    def test_a_review_and_a_selection_written_load_clean_and_read_back(self):
        from jsk.adapters.cli.compose import record

        doc = careerkit.short(roles=["pos_meridian_lead"], skills=["skill_kubernetes"],
                              names={"skill_kubernetes": "K8s"},
                              headline={"text": "Platform Engineer", "status": "inferred"})
        written = self.write({"review": review.triples(self.overlay(), self.STEM, "complete"),
                              "resume": selection.triples_of(doc, f"sel_app_{self.STEM}")})
        self.assertEqual(written, [f"{self.APP}/review", f"{self.APP}/resume"])
        s = record.load(self.root)
        mine = [f.text() for f in s.findings if f.file in written]
        self.assertEqual(mine, [])
        self.assertEqual(review.overlay_of(s.graph(f"{self.APP}/review")), self.overlay())
        self.assertEqual(selection.doc_of(s.graph(f"{self.APP}/resume")), doc)

    def test_a_general_resume_is_its_own_graph(self):
        from jsk.adapters.cli.compose import record
        from jsk.domain.naming import resume_graph
        from jsk.infra.oxigraph import record as R

        name = resume_graph("general")
        doc = careerkit.short()
        R.write_graphs(self.root, {name: selection.triples_of(doc, "sel_cv_general")})
        s = record.load(self.root)
        self.assertEqual([f.text() for f in s.findings if f.file == name], [])
        self.assertEqual(selection.doc_of(s.graph(name)), doc)

    def test_a_fault_in_a_selection_is_that_selections_not_the_careers(self):
        # A pick of a bullet the career lacks dangles in the selection, and stops no write
        # to the career: is_own counts resumes/ as applications/ is.
        from jsk.adapters.cli.compose import record
        from jsk.domain.record.state import new_failures
        from jsk.infra.oxigraph import record as R

        before = record.load(self.root)
        bad = selection.triples_of(careerkit.short(["ach_gone"]), "sel_cv_general")
        R.write_graphs(self.root, {"resumes/general/resume": bad})
        after = record.load(self.root)
        [f] = [f for f in after.fails() if f.file == "resumes/general/resume"]
        self.assertEqual(f.rule, "dangling")
        self.assertEqual(new_failures(after, after), [])
        self.assertTrue(new_failures(before, after))

    def test_a_sent_application_refuses_its_review_and_selection(self):
        import appkit
        from jsk.domain.timeline import errors

        appkit.put(self.root, f"{self.APP}/application",
                   f'k:app_{self.STEM} j:posting k:post_{self.STEM} ; '
                   'j:submitted "2026-09-30"^^xsd:date .\n')
        for kind in ("review", "resume"):
            with self.subTest(kind=kind), self.assertRaises(errors.Frozen) as cm:
                self.write({kind: None})
            self.assertIn(f"{self.APP}/{kind}: the application was sent on 2026-09-30",
                          str(cm.exception))

    def test_a_freeze_that_renames_the_directory_moves_the_review_and_the_selection(self):
        from jsk.adapters.cli.compose import record, timeline
        from jsk.application.timeline import records as T
        from jsk.infra.oxigraph import db
        from jsk.infra.oxigraph.applications import StoredApplications

        doc = careerkit.short()
        self.write({"review": review.triples(self.overlay(), self.STEM),
                    "resume": selection.triples_of(doc, f"sel_app_{self.STEM}")})
        sealed, why = T.write_application(
            self.root, str(self.app), "resume", "2026-09-30", "email", ["x.pdf"], b"{}",
            lambda store: ([], []), load=record.load, records=StoredApplications())
        self.assertIsNone(why)
        self.assertEqual(set(sealed.moves), {"posting", "review", "resume"})
        final = self.app.with_name("2026-09-30-contoso-platform")
        shutil.move(str(self.app), str(final))
        timeline.write_frozen(self.root, sealed, str(final))
        names = set(db.read(self.root))
        new = "applications/2026-09-30-contoso-platform"
        self.assertTrue({f"{new}/review", f"{new}/resume", f"{new}/posting"} <= names)
        self.assertFalse({f"{self.APP}/review", f"{self.APP}/resume"} & names)


if __name__ == "__main__":
    unittest.main()
