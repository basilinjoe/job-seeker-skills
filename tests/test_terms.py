"""The terms gate: the posting's own words, matched as strings on the rendered page.

ats-rules.md: recruiters search the ATS by the posting's words, so the title and each
required term should be on the page as the posting wrote them - and every finding is a
warning, because a missing term is often a gap, never a word to add. And `jsk kb export
--from-match` retunes the file to the posting: its title as an inferred headline, and a
skill it names by an alias shown under that alias."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import careerkit
from careerkit import APP, short
from jsk.domain.gates.terms_rules import STUFFED, judge, occurrences

PAGE = """Test Person
Platform Engineer

SKILLS
Platforms: Kubernetes, Terraform

PROFESSIONAL EXPERIENCE
- Cut event latency 40 percent on the Kubernetes platform.
"""


class Occurrences(unittest.TestCase):
    def test_a_term_counts_only_whole(self):
        # "Go" inside "Google" is not Go, and "Java" inside "JavaScript" is not Java.
        self.assertEqual(occurrences("Go", "worked at google"), 0)
        self.assertEqual(occurrences("Java", "javascript and java"), 1)

    def test_a_term_ending_in_punctuation_still_counts(self):
        # \\b falls nowhere after "#", so a word-boundary match would never find C#.
        self.assertEqual(occurrences("C#", "c#, .net and node.js"), 1)
        self.assertEqual(occurrences(".NET", "c#, .net and node.js"), 1)


class Judge(unittest.TestCase):
    def warns(self, requirements, title="Platform Engineer", page=PAGE):
        return judge(page, title, requirements)[1].warns

    def test_a_page_carrying_every_term_has_no_findings(self):
        counts, report = judge(PAGE, "Platform Engineer", [("Kubernetes", "required", [])])
        self.assertEqual((report.fails, report.warns), ([], []))
        self.assertEqual(counts["required"], (1, 1))

    def test_the_title_missing_is_said(self):
        warns = self.warns([], title="Senior Product Manager")
        self.assertTrue(any("'Senior Product Manager' is not on the page" in w
                            and "--headline" in w for w in warns), warns)

    def test_a_required_term_missing_is_a_warning_not_a_failure(self):
        counts, report = judge(PAGE, "Platform Engineer", [("Kafka", "required", [])])
        self.assertEqual(report.fails, [])
        self.assertTrue(any("required 'Kafka' is not on the page" in w for w in report.warns))
        self.assertEqual(counts["required"], (0, 1))

    def test_another_name_of_the_concept_is_pointed_at(self):
        # The evidence is there under the career's word; a search for the posting's misses.
        warns = self.warns([("K8s", "required", ["Kubernetes", "K8s"])])
        self.assertTrue(any("'K8s' is not on the page, but 'Kubernetes' is" in w
                            and "`names`" in w for w in warns), warns)

    def test_preferred_terms_missing_are_one_line(self):
        warns = self.warns([("Kafka", "preferred", []), ("Go", "preferred", [])])
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("2 preferred term(s) not on the page: 'Kafka', 'Go'", warns[0])

    def test_a_term_repeated_past_the_limit_is_stuffing(self):
        page = PAGE + "\n".join(f"- Ran Kubernetes job {n}." for n in range(STUFFED))
        warns = self.warns([("Kubernetes", "required", [])], page=page)
        self.assertTrue(any("keyword stuffing" in w for w in warns), warns)

    def test_a_graph_native_application_is_told_the_tools_not_the_files(self):
        # Its headline is a selection's and its gaps a review's: no resume.json, no
        # gaps.txt to edit (2026-10-02).
        warns = judge(PAGE, "Senior Product Manager", [("Kafka", "required", [])],
                      target="acme-platform")[1].warns
        said = " ".join(warns)
        self.assertIn('`career_confirm`, target "acme-platform", block "headline"', said)
        self.assertIn("`assessment_review` short", said)
        self.assertNotIn("resume.json", said)
        self.assertNotIn("gaps.txt", said)

    def test_an_implicit_requirement_is_not_searched(self):
        counts, report = judge(PAGE, "Platform Engineer", [("Kafka", "implicit", [])])
        self.assertEqual(report.warns, [])
        self.assertEqual(counts, {"required": (0, 0), "preferred": (0, 0)})


class Gate(unittest.TestCase):
    """The gate over a workspace: the posting found from the resume.json's directory, and the
    page the plain text the record's plan emits in memory - no render writes a .txt (Ruling
    23 of the graph-native plan) - or a .txt passed by hand."""

    def run_gate(self, root, record, page=None):
        from jsk.adapters.cli.gates import terms

        args = ["--record", str(record)]
        if page is not None:
            txt = Path(root, "pasted.txt")
            txt.write_text(page, encoding="utf-8")
            args = [str(txt)] + args
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code, result = terms.gate(args)
        return code, out.getvalue(), result

    def test_the_posting_beside_the_record_is_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(tmp, short=short())
            code, out, result = self.run_gate(root, path)
        # The fixture's posting asks for "K8s"; the plan's text says Kubernetes.
        self.assertEqual(code, 0, out)
        self.assertEqual(result.posting, "Platform Engineer")
        self.assertIn("checking: plain text of resume.json (in memory)", out)
        self.assertIn("required: 0/1", out)
        self.assertIn("'K8s' is not on the page, but 'Kubernetes' is", out)
        self.assertIn("PASS - terms reported", out)

    def test_a_txt_passed_by_hand_is_still_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(tmp, short=short())
            code, out, result = self.run_gate(root, path, page=PAGE)
        self.assertEqual(code, 0, out)
        self.assertEqual(result.name, "pasted.txt")
        self.assertIn("'K8s' is not on the page, but 'Kubernetes' is", out)

    def test_a_record_with_no_posting_has_nothing_to_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = careerkit.workspace(tmp)
            general = Path(root, "resume.json")
            general.write_text('{"resume": 2, "bullets": ["ach_events_latency"]}\n',
                               encoding="utf-8")
            code, out, result = self.run_gate(root, general)
        self.assertEqual(code, 0, out)
        self.assertIsNone(result.posting)

    def test_a_general_resume_gets_no_terms_step(self):
        """run_gates leaves the step out rather than print a pass that measured nothing:
        a general rebuild ships with exactly the steps it had."""
        from jsk.application.gates.run_gates import run_gates
        from jsk.adapters.cli.gates.check import contained

        with tempfile.TemporaryDirectory() as tmp:
            root, _ = careerkit.workspace(tmp)
            general = Path(root, "resume.json")
            general.write_text('{"resume": 2, "bullets": ["ach_events_latency"]}\n',
                               encoding="utf-8")
            # No .txt on disk either way: the terms gate reads the plan's text in memory.
            steps = run_gates(root, str(general), record_gate=False, run=contained,
                              strict=lambda p: False, measure=lambda p: (None, None))
            tailored = Path(root, APP)
            Path(tailored, "resume.json").write_text(json.dumps(short()), encoding="utf-8")
            with_posting = run_gates(str(tailored), str(tailored / "resume.json"),
                                     record_gate=False, run=contained,
                                     strict=lambda p: False, measure=lambda p: (None, None))
        self.assertNotIn("terms gate", [s.gate for s in steps])
        [terms] = [s for s in with_posting if s.gate == "terms gate"]
        self.assertEqual(terms.status, "PASS", terms.output)


class Retuned(unittest.TestCase):
    """export --from-match puts the posting's strings in the file where the career has them."""

    def retune(self, title, requirements, edits=(), target=None):
        from jsk.application.tailor.export import retuned
        from jsk.domain.matching.model import Requirement
        from jsk.domain.record.career import Career
        from jsk.domain.record.state import KB

        with tempfile.TemporaryDirectory() as tmp:
            root, _ = careerkit.workspace(tmp, edits=list(edits))
            career = Career(careerkit.store(root).graph(KB))
            notes = []
            reqs = [Requirement(f"req_{n}", asked, asked, need)
                    for n, (asked, need) in enumerate(requirements)]
            doc = retuned(short(skills=["skill_kubernetes", "skill_dotnet"]), career, title,
                          reqs, notes, target)
        return doc, notes

    def test_a_graph_native_selection_s_headline_note_names_career_confirm(self):
        _, notes = self.retune("Senior Platform Engineer", [], target="acme-platform")
        [note] = [n for n in notes if "headline" in n]
        self.assertIn('`career_confirm` (target "acme-platform", block "headline")', note)
        self.assertNotIn("resume.json", note)

    def test_the_posting_s_title_arrives_as_an_inferred_headline(self):
        doc, notes = self.retune("Senior Platform Engineer", [])
        self.assertEqual(doc["headline"], {"text": "Senior Platform Engineer",
                                           "status": "inferred"})
        self.assertTrue(any("--headline" in n for n in notes), notes)

    def test_a_title_the_career_already_holds_sets_no_headline(self):
        doc, _ = self.retune("platform engineer", [])
        self.assertNotIn("headline", doc)

    def test_a_skill_asked_by_its_alias_renders_under_it(self):
        doc, notes = self.retune("Platform Engineer", [("K8s", "required"), ("C#", "preferred")])
        self.assertEqual(doc["names"], {"skill_kubernetes": "K8s", "skill_dotnet": "C#"})
        self.assertTrue(any("'K8s', the posting's word for 'Kubernetes'" in n for n in notes))

    def test_a_skill_asked_by_its_own_name_is_left_alone(self):
        doc, _ = self.retune("Platform Engineer", [("Kubernetes", "required"), ("K8s", "required")])
        self.assertNotIn("names", doc)


if __name__ == "__main__":
    unittest.main()
