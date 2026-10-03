"""A graph-native application's use cases, without MCP: P3 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md.

The rules pinned: an advert captured from pasted text is stored as a draft posting's lines,
with no directory and no file (Rulings 1 and 12); rows are decided in batches, each checked
against the stored lines, and a FAIL writes nothing; `complete` refuses an uncovered
qualification line; the review is checked against the match - a raised verdict FAILs at
once - and survives a re-derivation and a re-decide (Ruling 4); a confirmed "no" settles a
requirement and is never asked (Ruling 9); a sent application refuses every change; and an
application is graph-native or legacy, never both, each side refusing the other by name
(Ruling 11). Then the queries across applications, over a two-application workspace.

From the 2026-10-02 review and replay: a derived gaps graph is validated before it is
written (Ruling 14); a slug to remove that is not there is a FAIL; an ask keeps the
requirement it is about, so it counts in `repeated`; a no covers what counts as its
concept; app_list names a file-built posting `built`; and `jsk tailor match` on an
application with no directory yet names the tool.
"""
import contextlib
import datetime
import io
import tempfile
import unittest
from pathlib import Path

import appkit
import careerkit
from jsk.adapters.cli.compose import native
from jsk.domain import ontology as O
from jsk.domain.posting.errors import Refused

ADVERT = """https://acme.example/jobs/42

# Platform Engineer
Acme Health · Melbourne

## What you'll do

- Run the clinical event platform for forty hospitals.

## What you'll bring

- Deep, hands-on Kubernetes experience in production.
- Kafka and event-driven systems.
- Rust experience required.
- Terraform a plus.
- Australian work rights; hybrid in Melbourne.
"""
# The lines advert_lines numbers ADVERT into, by what they say.
K8S, KAFKA, RUST, TERRAFORM = 3, 4, 5, 6
STEM = "acme-platform"
IDS = "acme_platform"
TODAY = datetime.date(2026, 10, 2)
ROWS = [{"n": K8S, "slug": "kubernetes", "asked": "Kubernetes", "concepts": ["c:kubernetes"]},
        {"n": KAFKA, "slug": "kafka", "asked": "Kafka", "concepts": ["c:kafka"]},
        {"n": RUST, "slug": "rust", "asked": "Rust", "concepts": ["c:rust"]}]
DROPS = [{"n": TERRAFORM, "reason": "a plus, and not for this resume"}]
OPEN = "# == Open questions\n"
RUST_NO = ('\nk:abs_rust j:concept c:rust ; j:said "2026-09-01"^^xsd:date ; '
           'j:answer "Never written Rust." ; j:provenance j:confirmed .\n')


def fails(findings):
    return [text for severity, text, _ in findings if severity == "FAIL"]


class Workspace(unittest.TestCase):
    """The claims fixture, stored, with ADVERT captured as applications/acme-platform."""

    EDITS = ()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", edits=self.EDITS)
        self.app = Path(self.root) / "applications" / STEM

    def graph(self, kind, stem=STEM):
        return appkit.triples(self.root, f"applications/{stem}/{kind}")

    def capture(self, stem=STEM, **kw):
        return native.capture(self.root, stem, text=kw.pop("text", ADVERT), today=TODAY, **kw)

    def decided(self, stem=STEM, rows=ROWS, drops=DROPS):
        """Captured, decided and completed: what the analyst's first three calls leave."""
        self.capture(stem)
        done = native.decide(self.root, stem, rows=rows, drops=drops, today=TODAY)
        self.assertEqual(fails(done.findings), [])
        done = native.complete_posting(self.root, stem, today=TODAY)
        self.assertEqual(fails(done.findings), [])

    def show(self, part, stem=STEM):
        return native.show(self.root, stem, part, today=TODAY)


class Capture(Workspace):
    def test_a_pasted_advert_is_stored_as_a_draft_posting_and_writes_no_file(self):
        done = self.capture()
        self.assertEqual((done.target, done.company, done.title, done.lines),
                         (f"applications/{STEM}/posting", "Acme Health", "Platform Engineer", 7))
        posting = self.show("posting")
        self.assertEqual((posting["state"], posting["requirements"]), ("draft", 0))
        lines = {x["n"]: x for x in self.show("lines")}
        # Concepts are found on read, through the vocabulary as it stands (Ruling 1).
        self.assertEqual(lines[K8S]["concepts"], ["c:kubernetes"])
        self.assertTrue(lines[7]["eligibility"] and lines[TERRAFORM]["optional"])
        # Ruling 12: the directory is the first render's.
        self.assertFalse(self.app.exists())

    def test_an_advert_in_a_file_is_read_through_the_fetch_machinery(self):
        path = Path(self.root) / "advert.txt"
        path.write_text(ADVERT.split("\n", 2)[2], encoding="utf-8")
        done = native.capture(self.root, STEM, url=str(path), company="Acme Health",
                              today=TODAY)
        self.assertEqual(done.title, "Platform Engineer")

    def test_a_header_the_advert_does_not_give_is_refused_naming_the_argument(self):
        bare = "- Kubernetes in production.\n- Kafka.\n"
        with self.assertRaises(Refused) as caught:
            self.capture(text=bare)
        self.assertIn("company", str(caught.exception))
        self.assertIn("pass company", caught.exception.fix)
        self.assertIsNone(self.graph("posting"), "a refusal writes nothing")
        self.capture(text=bare, company="Acme", title="Engineer")
        self.assertIsNotNone(self.graph("posting"))

    def test_neither_url_nor_text_is_refused(self):
        with self.assertRaises(Refused):
            native.capture(self.root, STEM, today=TODAY)

    def test_a_second_capture_is_refused_and_replace_drops_the_review_and_assessment(self):
        self.capture()
        with self.assertRaises(Refused) as caught:
            self.capture()
        self.assertIn("replace", caught.exception.fix)
        appkit.put(self.root, f"applications/{STEM}/review",
                   f"k:rvw_{IDS} j:posting k:post_{IDS} .\n")
        done = self.capture(replace=True)
        self.assertEqual(done.replaced, (f"applications/{STEM}/review",))
        self.assertIsNone(self.graph("review"))


class Decide(Workspace):
    def setUp(self):
        super().setUp()
        self.capture()

    def decide(self, **kw):
        return native.decide(self.root, STEM, today=TODAY, **kw)

    def refused(self, says, **kw):
        before = appkit.facts(self.root, f"applications/{STEM}/posting")
        done = self.decide(**kw)
        self.assertTrue(any(says in text for text in fails(done.findings)), done.findings)
        self.assertIsNone(done.target)
        self.assertEqual(appkit.facts(self.root, f"applications/{STEM}/posting"), before,
                         "a FAIL writes nothing")
        return done

    def test_an_asked_term_its_line_does_not_say_fails(self):
        self.refused("'Go' is not in line", rows=[{**ROWS[0], "asked": "Go"}])

    def test_a_slug_used_twice_in_a_batch_fails(self):
        self.refused("slug 'kubernetes' is used",
                     rows=[ROWS[0], {**ROWS[1], "slug": "kubernetes"}])

    def test_a_concept_the_workspace_does_not_know_fails(self):
        self.refused("c:no-such-thing is not a concept of this workspace",
                     rows=[{**ROWS[0], "concepts": ["c:no-such-thing"]}])

    def test_a_line_dropped_and_quoted_in_one_batch_fails(self):
        self.refused("is dropped and quoted", rows=[ROWS[0]], drops=[{"n": K8S, "reason": "x"}])

    def test_rows_are_upserted_by_slug_and_removed_by_slug(self):
        self.decide(rows=ROWS)
        self.decide(rows=[{**ROWS[1], "asked": "event-driven systems"}], remove=["rust"])
        reqs = {r["slug"]: r for r in self.show("requirements")["requirements"]}
        self.assertEqual(set(reqs), {"kubernetes", "kafka"})
        self.assertEqual(reqs["kafka"]["asked"], "event-driven systems")
        # The quote is the line itself (Ruling 2).
        self.assertEqual(reqs["kafka"]["quote"], "Kafka and event-driven systems.")

    def test_a_drop_clears_when_a_row_now_uses_its_line(self):
        self.decide(drops=DROPS)
        self.assertEqual(self.show("requirements")["drops"][0]["n"], TERRAFORM)
        self.decide(rows=[{"n": TERRAFORM, "slug": "terraform", "asked": "Terraform"}])
        self.assertEqual(self.show("requirements")["drops"], [])

    def test_an_uncovered_qualification_line_fails_complete(self):
        self.decide(rows=ROWS)
        done = native.complete_posting(self.root, STEM, today=TODAY)
        self.assertEqual(fails(done.findings),
                         [f"applications/{STEM}/posting: advert line {TERRAFORM} neither used "
                          "nor dropped"])
        self.assertEqual(self.show("posting")["state"], "draft")
        self.decide(drops=DROPS)
        self.assertEqual(native.complete_posting(self.root, STEM, today=TODAY).state, "complete")

    def test_a_slug_to_remove_that_is_not_there_fails_and_writes_nothing(self):
        # A WARN let a typo write the posting back as a draft with nothing removed
        # (2026-10-02): a completed posting lost its state for a misspelt slug.
        self.decide(rows=ROWS, drops=DROPS)
        native.complete_posting(self.root, STEM, today=TODAY)
        done = self.refused("remove: no requirement 'no_such_slug' to remove",
                            remove=["no_such_slug"])
        self.assertEqual(done.state, "complete")
        self.assertEqual(self.show("posting")["state"], "complete")

    def test_a_completed_posting_decided_again_is_a_draft(self):
        self.decide(rows=ROWS, drops=DROPS)
        native.complete_posting(self.root, STEM, today=TODAY)
        self.decide(rows=[{**ROWS[0], "need": "preferred"}])
        self.assertEqual(self.show("posting")["state"], "draft")


class Checks(Workspace):
    """What `jsk posting build` checked in decisions.txt, which tests/test_posting_build.py
    pinned until 6.0 retired the verb (docs/superpowers/plans/
    2026-10-03-retire-file-pipeline.md, P2): each still holds for a batch of decisions."""

    # A retired concept the career itself defines, so the fixture's vocabulary is untouched.
    EDITS = (('c:go-game a j:Domain ; j:label "Go (board game)" .\n',
              'c:go-game a j:Domain ; j:label "Go (board game)" .\n'
              'c:cobol a j:Technology ; j:label "COBOL" ; j:retired "2026-01-01"^^xsd:date ; '
              'j:reason "Replaced." .\n'),)

    def setUp(self):
        Workspace.setUp(self)
        self.capture()

    decide = Decide.decide
    refused = Decide.refused

    def requirements(self):
        return {r["slug"]: r for r in self.show("requirements")["requirements"]}

    def test_a_retired_concept_fails(self):
        self.refused("c:cobol is retired", rows=[{**ROWS[0], "concepts": ["c:cobol"]}])

    def test_a_domain_that_is_not_a_domain_fails(self):
        self.refused("not a Domain", header={"domain": ["c:kubernetes"]})
        done = self.decide(header={"domain": ["c:go-game"]})
        self.assertEqual(fails(done.findings), [])

    def test_a_bad_seniority_fails(self):
        self.refused("seniority 'staff' is not a level", header={"seniority": "staff"})

    def test_a_bad_capture_day_fails(self):
        self.refused("captured 'last week' is not a day", header={"captured": "last week"})

    def test_the_capture_day_defaults_to_today_and_a_header_day_holds(self):
        self.assertEqual(self.show("posting")["captured"], TODAY.isoformat())
        self.decide(header={"captured": "2026-09-01"})
        self.assertEqual(self.show("posting")["captured"], "2026-09-01")

    def test_the_default_need_follows_the_section(self):
        self.decide(rows=ROWS + [{"n": TERRAFORM, "slug": "terraform", "asked": "Terraform"},
                                 {"n": 2, "slug": "platform", "asked": "clinical event "
                                  "platform"}])
        need = {slug: r["need"] for slug, r in self.requirements().items()}
        self.assertEqual((need["kubernetes"], need["terraform"], need["platform"]),
                         ("required", "preferred", "implicit"))

    def test_one_line_split_three_ways_quotes_that_line_three_times(self):
        self.decide(rows=[{"n": KAFKA, "slug": "kafka", "asked": "Kafka"},
                          {"n": KAFKA, "slug": "events", "asked": "event-driven"},
                          {"n": KAFKA, "slug": "systems", "asked": "systems"}])
        quotes = {r["quote"] for r in self.requirements().values()}
        self.assertEqual(quotes, {"Kafka and event-driven systems."})
        self.assertEqual(len(self.requirements()), 3)

    def test_past_twenty_requirements_warns_and_twenty_does_not(self):
        words = "Deep, hands-on Kubernetes experience in production.".split()
        runs = [" ".join(words[a:b]) for a in range(len(words))
                for b in range(a + 1, len(words) + 1)]
        rows = [{"n": K8S, "slug": f"term_{i}", "asked": run} for i, run in enumerate(runs)]
        done = self.decide(rows=rows[:20])
        self.assertFalse([t for s, t, _ in done.findings if "soft cap" in t], done.findings)
        done = self.decide(rows=rows[20:21])
        self.assertIn("21 requirements, past the soft cap of 20",
                      " ".join(t for s, t, _ in done.findings if s == "WARN"))

    def test_a_dated_directory_name_is_not_part_of_the_ids(self):
        dated = "2026-10-01-globex-platform"
        native.capture(self.root, dated, text=ADVERT, today=TODAY)
        self.assertIn(f"{O.K}post_globex_platform",
                      {t.subject.value for t in self.graph("posting", stem=dated)})


class Flow(Workspace):
    """capture, decide, complete, derive, review, complete - the analyst's calls in order."""

    def asks(self):
        return [t for t in self.graph("gaps") if O.class_of(t.subject.value) == "Ask"]

    def test_the_whole_run_lands_in_the_graph_and_nothing_on_disk(self):
        self.decided()
        a = native.derive_assessment(self.root, STEM, today=TODAY)
        rows = {r["slug"]: r for r in a.rows}
        self.assertEqual(rows["rust"]["verdict"], "unsatisfied")
        self.assertEqual(a.written, (f"applications/{STEM}/gaps",))
        # Ruling 5: the question about Rust is its own node, with Rust's concept on it.
        [question] = [q for q in a.questions if q["requirement"] == "rust"]
        self.assertIn("Rust", question["question"])
        self.assertIn(O.C + "rust", {t.object.value for t in self.asks()})
        self.assertFalse([t for t in self.graph("gaps") if t.predicate.value == O.J + "questions"])

        raised = native.review(self.root, STEM, verdicts=[{"slug": "rust", "verdict": "satisfied"}],
                               today=TODAY)
        self.assertEqual(fails(raised.findings),
                         ["the review: rust: satisfied, above the match's unsatisfied"])
        self.assertIsNone(self.graph("review"), "a raised verdict writes nothing")

        done = native.review(self.root, STEM, fit="partial", eligibility="Australian, hybrid",
                             verdicts=[{"slug": "kubernetes", "verdict": "partial",
                                        "reason": "AKS only"}], short=["Rust"], today=TODAY)
        self.assertEqual((done.state, done.fit), ("draft", "partial"))
        done = native.complete_review(self.root, STEM, today=TODAY)
        self.assertEqual(done.state, "complete")
        shown = self.show("assessment")
        rows = {r["slug"]: r for r in shown["rows"]}
        self.assertEqual((rows["kubernetes"]["verdict"], rows["kubernetes"]["shortfall"]),
                         ("partial", "AKS only"))
        self.assertEqual((shown["fit"], shown["short"]), ("partial", ["Rust"]))
        self.assertIn("| Kubernetes | required | partial (match: satisfied) |", shown["markdown"])
        self.assertEqual(self.show("review")["state"], "complete")
        self.assertFalse(self.app.exists(), "no posting.md, gaps.txt or gaps.md anywhere")

    def test_a_derivation_whose_gaps_graph_breaks_a_rule_is_refused_with_nothing_written(self):
        """Ruling 14: the gaps graph is validated with the workspace before it is written,
        as every other graph-native write is. assessment_derive wrote it unchecked through
        check_gaps.build until 2026-10-02."""
        import pyoxigraph as ox
        from unittest import mock

        from jsk.application.tailor import check_gaps

        made = check_gaps.native_triples

        def broken(store, app_rel, a, today):
            # A question with no assessment, position or words: a cardinality FAIL.
            stray = ox.NamedNode(f"{O.K}ask_{IDS}_99")
            return made(store, app_rel, a, today) + [
                ox.Triple(stray, ox.NamedNode(O.J + "concept"), ox.NamedNode(O.C + "rust"))]

        self.decided()
        with mock.patch.object(check_gaps, "native_triples", broken):
            a = native.derive_assessment(self.root, STEM, today=TODAY)
        self.assertTrue(any("does not validate" in t for t in fails(a.findings)), a.findings)
        self.assertEqual(a.written, ())
        self.assertIsNone(self.graph("gaps"), "nothing was written")

    def test_a_review_before_the_posting_is_complete_is_refused(self):
        self.capture()
        with self.assertRaises(Refused) as caught:
            native.review(self.root, STEM, fit="partial", today=TODAY)
        self.assertIn("posting_complete", caught.exception.fix)
        with self.assertRaises(Refused):
            native.derive_assessment(self.root, STEM, today=TODAY)

    def test_complete_settles_a_review_with_nothing_to_answer(self):
        # No flag fires on this posting, so a review holding nothing at all completes.
        self.decided()
        native.derive_assessment(self.root, STEM, today=TODAY)
        done = native.complete_review(self.root, STEM, today=TODAY)
        self.assertEqual((fails(done.findings), done.state), ([], "complete"))

    def test_complete_refuses_a_flag_the_review_has_not_answered(self):
        # The advert names two platforms where the evidence names one: the match says
        # satisfied, and the flag asks the analyst whether that reads too generously.
        listed = "Container platforms (AKS, Nomad)"
        self.capture(text=ADVERT.replace("Deep, hands-on Kubernetes experience", listed))
        rows = [dict(ROWS[0], asked=listed), *ROWS[1:]]
        self.assertEqual(fails(native.decide(self.root, STEM, rows=rows, drops=DROPS,
                                             today=TODAY).findings), [])
        native.complete_posting(self.root, STEM, today=TODAY)
        derived = native.derive_assessment(self.root, STEM, today=TODAY)
        flagged = {r["slug"]: r["flags"] for r in derived.rows}
        self.assertEqual(list(flagged["kubernetes"]), ["listed-names"])

        done = native.complete_review(self.root, STEM, today=TODAY)
        self.assertTrue(fails(done.findings), "an unanswered flag cannot complete")
        self.assertNotEqual(done.state, "complete")

        native.review(self.root, STEM, verdicts=[{"slug": "kubernetes", "verdict": "keep"}],
                      today=TODAY)
        done = native.complete_review(self.root, STEM, today=TODAY)
        self.assertEqual((fails(done.findings), done.state), ([], "complete"))

    def test_the_review_survives_a_rederivation_and_a_redecide(self):
        self.decided()
        native.review(self.root, STEM, verdicts=[{"slug": "kubernetes", "verdict": "partial",
                                                  "reason": "AKS only"}], today=TODAY)
        before = appkit.facts(self.root, f"applications/{STEM}/review")
        native.derive_assessment(self.root, STEM, today=TODAY)
        self.assertEqual(appkit.facts(self.root, f"applications/{STEM}/review"), before)
        native.decide(self.root, STEM, rows=[{**ROWS[1], "asked": "event-driven systems"}],
                      today=TODAY)
        self.assertIsNone(self.graph("gaps"), "derived from requirements that changed")
        self.assertEqual(self.show("review")["verdicts"],
                         [{"slug": "kubernetes", "verdict": "partial", "reason": "AKS only"}])
        native.complete_posting(self.root, STEM, today=TODAY)
        a = native.derive_assessment(self.root, STEM, today=TODAY)
        self.assertEqual({r["slug"]: r["verdict"] for r in a.rows}["kubernetes"], "partial")

    def test_a_requirement_removed_takes_its_review_row_with_it(self):
        self.decided()
        native.review(self.root, STEM, verdicts=[{"slug": "kubernetes", "verdict": "partial",
                                                  "reason": "AKS only"}], today=TODAY)
        done = native.decide(self.root, STEM, remove=["kubernetes"],
                             drops=[{"n": K8S, "reason": "not asked of this resume"}],
                             today=TODAY)
        self.assertEqual(fails(done.findings), [])
        self.assertEqual(self.show("review")["verdicts"], [])

    def test_a_sent_application_refuses_every_change(self):
        self.decided()
        appkit.put(self.root, f"applications/{STEM}/application",
                   f'k:app_{IDS} j:posting k:post_{IDS} ; j:submitted "2026-09-30"^^xsd:date .\n')
        calls = (lambda: native.decide(self.root, STEM, rows=ROWS[:1], today=TODAY),
                 lambda: native.complete_posting(self.root, STEM, today=TODAY),
                 lambda: native.derive_assessment(self.root, STEM, today=TODAY),
                 lambda: native.review(self.root, STEM, fit="poor", today=TODAY),
                 lambda: self.capture(replace=True))
        for call in calls:
            with self.subTest(call=call), self.assertRaises(Refused) as caught:
                call()
            self.assertIn("was sent on 2026-09-30", str(caught.exception))


class Absence(Workspace):
    """Ruling 9: the person's confirmed no answers the requirement, and is not asked again."""

    EDITS = ((OPEN, OPEN + RUST_NO),)

    def test_a_confirmed_absence_settles_a_requirement_with_no_ask(self):
        self.decided()
        a = native.derive_assessment(self.root, STEM, today=TODAY)
        rust = {r["slug"]: r for r in a.rows}["rust"]
        self.assertEqual((rust["state"], rust["verdict"], rust["basis"]),
                         ("missing", "unsatisfied", "said on 2026-09-01: Never written Rust."))
        self.assertNotIn("rust", [q["requirement"] for q in a.questions])
        asks = [t for t in self.graph("gaps") if O.class_of(t.subject.value) == "Ask"]
        self.assertNotIn(O.C + "rust", {t.object.value for t in asks})


class AskedAbout(Workspace):
    """Ruling 4: an ask names the requirement it is about, the review keeps it as the
    item's j:about, and the question's j:Ask carries that requirement and its concepts -
    so two applications asking about one concept show in `repeated`. Until 2026-10-02 the
    `about` was dropped, with a WARN."""

    OTHER = "initech-platform"

    def asked(self, stem, about="kubernetes"):
        return native.review(self.root, stem, asks=[
            {"question": "Has the Kubernetes work run on bare metal?", "about": about}],
            today=TODAY)

    def test_an_ask_about_a_requirement_counts_in_repeated_across_two_applications(self):
        from jsk.adapters.cli.compose import record
        from jsk.application.record.insights import repeated

        for stem in (STEM, self.OTHER):
            self.decided(stem)
            done = self.asked(stem)
            self.assertEqual(done.findings, (), done.findings)
        self.assertEqual(self.show("review")["asks"],
                         [{"question": "Has the Kubernetes work run on bare metal?",
                           "about": "kubernetes"}])
        [q] = self.show("assessment")["questions"]
        self.assertEqual((q["requirement"], q["concepts"]), ("kubernetes", ["c:kubernetes"]))
        rows = {r["concept"]: r for r in repeated(record.load(self.root))[1]}
        self.assertEqual(rows["c:kubernetes"]["applications"], 2)

    def test_an_ask_about_no_requirement_fails_and_writes_nothing(self):
        self.decided()
        done = self.asked(STEM, about="no_such_slug")
        self.assertEqual(fails(done.findings),
                         ["asks[1]: about 'no_such_slug' is not a requirement of this posting"])
        self.assertIsNone(self.graph("review"))

    def test_removing_the_requirement_keeps_the_question_and_drops_its_about(self):
        self.decided()
        self.asked(STEM)
        done = native.decide(self.root, STEM, remove=["kubernetes"],
                             drops=[{"n": K8S, "reason": "not asked of this resume"}],
                             today=TODAY)
        self.assertEqual(fails(done.findings), [])
        self.assertEqual(self.show("review")["asks"],
                         [{"question": "Has the Kubernetes work run on bare metal?",
                           "about": None}])


class NarrowerAbsence(Workspace):
    """Ruling 9's amendment: a confirmed no to Kubernetes answers a requirement for EKS,
    which counts as Kubernetes, through the store's closure."""

    EDITS = ((OPEN, OPEN + '\nk:abs_kubernetes j:concept c:kubernetes ; j:said '
              '"2026-09-01"^^xsd:date ; j:answer "Never run Kubernetes." ; '
              'j:provenance j:confirmed .\n'),)

    def test_a_no_to_kubernetes_answers_a_requirement_for_eks(self):
        self.decided(rows=[{**ROWS[0], "concepts": ["c:eks"]}, *ROWS[1:]])
        a = native.derive_assessment(self.root, STEM, today=TODAY)
        k8s = {r["slug"]: r for r in a.rows}["kubernetes"]
        self.assertEqual((k8s["verdict"], k8s["basis"]),
                         ("unsatisfied", "said on 2026-09-01: Never run Kubernetes."))


class Legacy(Workspace):
    """Ruling 11: no application is both; each side refuses the other by name."""

    def test_the_use_cases_refuse_an_application_made_from_files(self):
        legacy = "contoso-platform"
        calls = (lambda: native.decide(self.root, legacy, rows=ROWS, today=TODAY),
                 lambda: native.complete_posting(self.root, legacy, today=TODAY),
                 lambda: native.derive_assessment(self.root, legacy, today=TODAY),
                 lambda: native.review(self.root, legacy, fit="poor", today=TODAY),
                 lambda: native.show(self.root, legacy, "lines", today=TODAY),
                 lambda: native.capture(self.root, legacy, text=ADVERT, today=TODAY))
        for call in calls:
            with self.subTest(call=call), self.assertRaises(Refused) as caught:
                call()
            # Ruling 5 of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md: the
            # fix named `jsk posting build` until 6.0 retired it.
            self.assertIn("jsk 5.1.0", caught.exception.fix)

    def run_cli(self, main, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def native_app(self):
        self.capture()
        self.app.mkdir(parents=True)         # as the first render would leave it
        return str(self.app)

    def test_tailor_match_gaps_and_draft_gaps_refuse_a_graph_native_application(self):
        from jsk.adapters.cli import match

        app = self.native_app()
        for flag, tool in (("--gaps", "assessment_review"), ("--draft-gaps", "assessment_derive")):
            with self.subTest(flag=flag):
                code, out = self.run_cli(match.main, [app, flag, str(self.app / "gaps.txt")])
                self.assertEqual(code, 1, out)
                self.assertIn(f"`{tool}`", out)
        self.assertFalse((self.app / "gaps.txt").exists())

    def test_tailor_prepare_draft_gaps_refuses_a_graph_native_application(self):
        from jsk.adapters.cli import tailor

        app = self.native_app()
        code, out = self.run_cli(tailor.main, ["prepare", app, "--draft-gaps"])
        self.assertEqual(code, 1, out)
        self.assertIn("`assessment_derive`", out)

    def test_app_list_names_both_kinds(self):
        self.capture()
        apps = {a["app"]: a for a in native.list_apps(self.root, today=TODAY)["applications"]}
        self.assertEqual((apps[STEM]["kind"], apps[STEM]["posting"]), ("native", "draft"))
        # Made from files, its posting built: `posting: null` read as "no posting yet"
        # (the end-to-end replay, 2026-10-02).
        self.assertEqual((apps["contoso-platform"]["kind"], apps["contoso-platform"]["posting"]),
                         ("files", "built"))

    def test_tailor_match_on_a_graph_native_application_with_no_directory_names_the_tool(self):
        from jsk.adapters.cli import match

        self.capture()
        self.assertFalse(self.app.exists())
        code, out = self.run_cli(match.main, [str(self.app)])
        self.assertEqual(code, 1, out)
        self.assertIn("is graph-native", out)
        self.assertIn("`assessment_derive`", out)
        self.assertNotIn("posting.md", out)


OTHER = ADVERT.replace("Acme Health", "Globex").replace("Kubernetes", "Kafka Streams")
LAPSED_NO = ('\nk:abs_fastapi j:concept c:fastapi ; j:said "2025-01-01"^^xsd:date ; '
             'j:answer "Never used FastAPI." ; j:provenance j:confirmed .\n'
             'k:abs_java j:concept c:java ; j:said "2026-09-01"^^xsd:date ; '
             'j:answer "No Java." ; j:provenance j:inferred .\n')


class Queries(Workspace):
    """The insights across applications, over two graph-native applications: both ask Rust
    (and neither career holds it), one drops a line, one was sent."""

    EDITS = ((OPEN, OPEN + LAPSED_NO),)

    def setUp(self):
        super().setUp()
        self.decided()
        native.derive_assessment(self.root, STEM, today=TODAY)
        native.capture(self.root, "globex-platform", text=OTHER, today=TODAY)
        native.decide(self.root, "globex-platform", rows=[
            {"n": K8S, "slug": "kafka_streams", "asked": "Kafka Streams", "concepts": ["c:kafka"]},
            ROWS[2], {"n": TERRAFORM, "slug": "terraform", "asked": "Terraform",
                      "concepts": ["c:terraform"]}],
            drops=[{"n": KAFKA, "reason": "a plus, and not for this resume"}], today=TODAY)
        native.complete_posting(self.root, "globex-platform", today=TODAY)
        native.derive_assessment(self.root, "globex-platform", today=TODAY)
        appkit.put(self.root, f"applications/{STEM}/application",
                   f'k:app_{IDS} j:posting k:post_{IDS} ; j:submitted "2026-09-30"^^xsd:date .\n')

    def query(self, name):
        from jsk.adapters.cli.compose import record
        from jsk.application.record.queries import QUERIES

        _, _, fn, _, dated = QUERIES[name]
        return fn(record.load(self.root), **({"today": TODAY} if dated else {}))[1]

    def test_demand_counts_the_postings_asking_for_each_concept(self):
        rows = {r["concept"]: r for r in self.query("demand")}
        self.assertEqual((rows["c:rust"]["postings"], rows["c:rust"]["required"]), (2, 2))
        self.assertEqual(rows["c:rust"]["verdicts"], "unsatisfied 2")
        self.assertEqual(rows["c:kafka"]["postings"], 2)

    def test_shortfalls_lists_what_the_assessments_leave_short(self):
        rows = {r["concept"]: r for r in self.query("shortfalls")}
        self.assertEqual(rows["c:rust"]["applications"], 2)
        self.assertNotIn("c:kubernetes", rows)

    def test_drops_groups_the_reasons(self):
        [row] = [r for r in self.query("drops") if r["reason"].startswith("a plus")]
        self.assertEqual(row["lines"], 2)
        self.assertEqual(row["postings"], "k:post_acme_platform, k:post_globex_platform")

    def test_outcomes_groups_applications_by_fit_and_stage(self):
        self.assertEqual(self.query("outcomes"),
                         [{"fit": "poor", "stage": "no event", "applications": 1,
                           "which": f"k:app_{IDS}"}])

    def test_repeated_names_a_concept_asked_in_two_applications(self):
        rows = {r["concept"]: r for r in self.query("repeated")}
        self.assertEqual(rows["c:rust"]["applications"], 2)
        self.assertNotIn("c:kubernetes", rows)

    def test_absences_says_which_stand_which_are_due_and_which_are_unconfirmed(self):
        rows = {r["concept"]: r for r in self.query("absences")}
        self.assertEqual(rows["c:fastapi"]["status"], "due")
        self.assertEqual(rows["c:fastapi"]["lapses"], "2026-01-01")
        self.assertEqual(rows["c:java"]["status"], "unconfirmed")
        self.assertEqual(self.query("absences")[0]["concept"], "c:fastapi", "due first")


if __name__ == "__main__":
    unittest.main()
