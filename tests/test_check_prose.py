"""check_prose.py is the second gate: check_ats.py verifies a document parses,
this one verifies it reads. The case that motivated it — "the platform followed
him through his promotion" — passed check_ats.py with 0 failures, correctly.

These tests pin every rule the script claims, and pin that a well-written resume
still comes out clean. A gate that cries wolf gets switched off.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import CHECK_PROSE, load_script, run

cp = load_script(CHECK_PROSE)

# A resume whose prose satisfies every documented rule. The regression guard.
# Both bullets carry a number deliberately: quantification coverage is one of
# the rules now, and a fixture that models the clean case has to model that one
# too, or "WARN 0" stops meaning what it says.
CLEAN = [
    (False, "Jane Doe"),
    (False, "Phone: +61 400 123 456 | Email: jane.doe@example.com"),
    (False, "Professional Summary"),
    (False, "Solution architect who builds the platforms other teams build on."),
    (False, "Technical Skills"),
    (False, "Azure, Bicep, Kubernetes, Terraform, Python"),
    (False, "Professional Experience"),
    (False, "Senior Architect, Acme Corp | Jun 2025 - Present"),
    (True, "Owned the migration to event-driven services across six delivery teams, "
           "cutting release lead time from 21 days to 2 days."),
    (True, "Cut order-processing latency 62 percent by decomposing a monolithic "
           "service into six event-driven microservices."),
    (False, "Education"),
    (False, "BSc Computer Science, University of Melbourne, 2014"),
]


def with_lines(*extra, base=None):
    return list(base if base is not None else CLEAN) + list(extra)


class ProseCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def tex(self, paragraphs, name="resume.tex"):
        r"""The .tex the deliverable PDF is compiled from.

        A bullet is an \item here, which is why the prose gate reads this rather
        than the PDF: a text extractor may or may not have kept the glyph, and a
        rule about how a bullet opens needs to know which lines are bullets.
        """
        body = []
        for bullet, text in paragraphs:
            escaped = text.replace("&", "\\&").replace("%", "\\%")
            body.append(f"  \\item {escaped}" if bullet else f"{escaped}\\par")
        path = self.tmp / name
        doc = [r"\begin{document}"] + body + [r"\end{document}"]
        path.write_text(chr(10).join(doc) + chr(10), encoding="utf-8")
        return path

    def check(self, paragraphs=None, name="resume.tex"):
        return run(CHECK_PROSE, self.tex(CLEAN if paragraphs is None else paragraphs, name))

    def assertFails(self, code, out, needle=None):
        self.assertEqual(code, 1, f"expected FAIL, got exit {code}:\n{out}")
        self.assertIn("DO NOT SEND", out)
        if needle:
            self.assertIn(needle, out.lower())

    def assertWarnsOnly(self, code, out, needle):
        self.assertEqual(code, 0, f"expected PASS with a warning, got exit {code}:\n{out}")
        self.assertIn("PASS", out)
        self.assertIn(needle, out.lower())


class CleanResume(ProseCase):
    """A gate that fails good work is worse than no gate."""

    def test_clean_resume_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - prose rules satisfied", out)

    def test_clean_resume_raises_no_warnings(self):
        _, out = self.check()
        self.assertIn("WARN 0", out)

    def test_a_sentence_may_end_on_a_particle(self):
        # "the platforms other teams build on" is finished English, not a truncation.
        _, out = self.check()
        self.assertNotIn("mid-clause", out)


class ThirdPerson(ProseCase):
    """The defect from the issue, verbatim."""

    def test_the_reported_bullet_fails(self):
        code, out = self.check(with_lines(
            (True, "Architected the tenancy model, and the platform followed him "
                   "through his promotion into the architect role.")))
        self.assertFails(code, out, "third person")

    def test_every_gendered_pronoun_fails(self):
        for pronoun in ("he", "him", "his", "she", "her", "hers", "himself", "herself"):
            with self.subTest(pronoun=pronoun):
                code, out = self.check(with_lines(
                    (True, f"Built the platform that {pronoun} designed.")))
                self.assertFails(code, out, "third person")

    def test_pronouns_inside_words_are_not_matched(self):
        code, out = self.check(with_lines(
            (True, "Shipped the Hershey and Sheraton integrations on schedule.")))
        self.assertEqual(code, 0, out)

    def test_they_warns_rather_than_fails(self):
        # "migrated their estate" is ordinary and correct; the ambiguity is real.
        code, out = self.check(with_lines(
            (True, "Migrated their on-premise estate to Azure over nine months.")))
        self.assertWarnsOnly(code, out, "'their'")

    def test_each_distinct_pronoun_is_reported_once(self):
        _, out = self.check(with_lines(
            (True, "Built his platform."), (True, "Ran his migration.")))
        self.assertEqual(out.count("third person 'his'"), 1)


class Placeholders(ProseCase):
    def test_bracketed_placeholder_fails(self):
        code, out = self.check(with_lines(
            (True, "Cut deployment time by [X%] across the delivery estate.")))
        self.assertFails(code, out, "placeholder")

    def test_unmatched_open_bracket_fails(self):
        code, out = self.check(with_lines((True, "Delivered [TBD platform work.")))
        self.assertFails(code, out, "bracket")


class UnfinishedSentences(ProseCase):
    def test_the_repos_own_defect_fails(self):
        code, out = self.check(with_lines(
            (True, "Improved overall productivity of the organisation by.")))
        self.assertFails(code, out, "mid-clause")

    def test_trailing_conjunction_fails(self):
        code, out = self.check(with_lines((True, "Led the platform rebuild and")))
        self.assertFails(code, out, "mid-clause")

    def test_trailing_article_fails(self):
        code, out = self.check(with_lines((True, "Rebuilt the")))
        self.assertFails(code, out, "mid-clause")

    def test_ambiguous_particle_warns_rather_than_fails(self):
        code, out = self.check(with_lines(
            (True, "Owned the standard every delivery team builds to.")))
        self.assertWarnsOnly(code, out, "mid-clause")

    def test_headings_are_not_mistaken_for_truncated_sentences(self):
        code, out = self.check()
        self.assertNotIn("Education", out)


class BannedPhrases(ProseCase):
    def test_every_banned_phrase_warns(self):
        for phrase in ("Responsible for", "Worked on", "Involved in",
                       "Gained experience in", "Acquired knowledge of",
                       "Assisted with", "Helped with"):
            with self.subTest(phrase=phrase):
                code, out = self.check(with_lines((True, f"{phrase} the billing platform.")))
                self.assertEqual(code, 0, out)
                self.assertIn(phrase.lower(), out.lower())

    def test_banned_phrase_does_not_block_delivery(self):
        # writing-rules.md says cut on sight, but a warning is the right severity:
        # the phrase is a style defect, not a factual or parsing one.
        code, _ = self.check(with_lines((True, "Responsible for the billing platform.")))
        self.assertEqual(code, 0)


class Duplicates(ProseCase):
    def test_repeated_bullet_warns(self):
        line = "Conducted thorough code reviews across three delivery teams."
        code, out = self.check(with_lines((True, line), (True, line)))
        self.assertEqual(code, 0, out)
        self.assertIn("duplicate", out.lower())

    def test_high_overlap_warns(self):
        code, out = self.check(with_lines(
            (True, "Conducted thorough code reviews across three delivery teams."),
            (True, "Conducted thorough code reviews across four delivery teams.")))
        self.assertIn("overlap", out.lower())

    def test_distinct_bullets_do_not_warn(self):
        _, out = self.check()
        self.assertNotIn("overlap", out.lower())
        self.assertNotIn("duplicate", out.lower())


class ThroatClearing(ProseCase):
    def test_bullet_not_opening_on_a_verb_warns(self):
        code, out = self.check(with_lines(
            (True, "As part of a wider programme, the team shipped the portal.")))
        self.assertEqual(code, 0, out)
        self.assertIn("does not open on a verb", out)

    def test_irregular_verbs_are_recognised(self):
        for opener in ("Built", "Led", "Ran", "Cut", "Drove", "Wrote", "Rebuilt"):
            with self.subTest(opener=opener):
                _, out = self.check(with_lines(
                    (True, f"{opener} the multi-tenant billing platform end to end.")))
                self.assertNotIn("does not open on a verb", out)

    def test_only_bullets_are_held_to_the_rule(self):
        # A heading or a skills row is not a bullet and must not be judged as one.
        _, out = self.check(with_lines((False, "Languages: English, Malayalam")))
        self.assertNotIn("does not open on a verb", out)


class PlainTextVariant(ProseCase):
    """ats-rules.md ships a .txt for paste-in boxes, generated from the same content."""

    def write_txt(self, lines, name="resume.txt"):
        path = self.tmp / name
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_plain_text_is_accepted(self):
        code, out = run(CHECK_PROSE, self.write_txt(
            ["Jane Doe", "Professional Summary",
             "- Owned the migration to event-driven services."]))
        self.assertEqual(code, 0, out)

    def test_plain_text_defects_are_caught(self):
        code, out = run(CHECK_PROSE, self.write_txt(
            ["Jane Doe", "- Built the platform that followed him into the role."]))
        self.assertFails(code, out, "third person")

    def test_dash_prefix_marks_a_bullet(self):
        code, out = run(CHECK_PROSE, self.write_txt(
            ["Jane Doe", "- Meanwhile the team shipped the portal."]))
        self.assertIn("does not open on a verb", out)


class MalformedInput(ProseCase):
    def test_the_docx_is_no_longer_accepted(self):
        junk = self.tmp / "resume.docx"
        junk.write_text("not a zip", encoding="utf-8")
        code, out = run(CHECK_PROSE, junk)
        self.assertEqual(code, 2)
        self.assertIn("unsupported", out.lower())

    def test_missing_file_reports_a_verdict(self):
        code, out = run(CHECK_PROSE, self.tmp / "absent.tex")
        self.assertEqual(code, 2)
        self.assertIn("not found", out.lower())

    def test_unsupported_extension_is_rejected(self):
        pdf = self.tmp / "resume.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        code, out = run(CHECK_PROSE, pdf)
        self.assertEqual(code, 2)
        self.assertIn("unsupported", out.lower())

    def test_no_argument_is_a_usage_error(self):
        code, out = run(CHECK_PROSE)
        self.assertEqual(code, 2)
        self.assertIn("usage", out.lower())


class QuantificationCoverage(ProseCase):
    """writing-rules.md anchors every bullet on a measurable result. Nothing was
    measuring whether it happened: validate_urs.py checks that a number in prose
    traces to a metric, which says nothing about a bullet carrying no number.

    Reported, never enforced. A gate that demands a number is a gate that gets
    fed an invented one, and inventing numbers is the exact failure the whole
    provenance apparatus exists to prevent.
    """

    UNQUANTIFIED = "Architected the multi-tenant isolation layer for the platform."

    def test_the_coverage_line_is_reported(self):
        _, out = self.check()
        self.assertIn("quantified: 2/2 (100%)", out)

    def test_an_unquantified_bullet_is_counted_and_named(self):
        code, out = self.check(with_lines((True, self.UNQUANTIFIED)))
        self.assertEqual(code, 0, out)
        self.assertIn("quantified: 2/3 (66%)", out)
        self.assertIn("no metric in bullet", out)
        self.assertIn("isolation layer", out)

    def test_no_number_anywhere_still_passes(self):
        code, out = self.check([
            (False, "Professional Experience"),
            (True, "Owned the payments rewrite end to end."),
            (True, "Architected the tenancy model for the platform."),
        ])
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)
        self.assertIn("quantified: 0/2 (0%)", out)

    def test_the_listing_is_capped(self):
        """A wholly unquantified draft must not bury every other finding."""
        _, out = self.check([(False, "Professional Experience")] +
                            [(True, f"Owned the {w} rewrite end to end.")
                             for w in ("billing", "payments", "search", "tenancy",
                                       "reporting", "identity")])
        self.assertEqual(out.count("no metric in bullet"), 4)
        self.assertIn("and 2 more bullets carry no number", out)

    def test_a_year_does_not_count_as_a_metric(self):
        """The exclusions are why validate_urs.numerals() is reused rather than
        reimplemented - a bullet mentioning 2019 is not a quantified bullet."""
        _, out = self.check([
            (False, "Professional Experience"),
            (True, "Owned the payments rewrite through the 2019 reorganisation."),
        ])
        self.assertIn("quantified: 0/1 (0%)", out)


class OutputShape(ProseCase):
    """Same shape as check_ats.py, so it drops into the verification step without
    new conventions for a reader to learn."""

    def test_counts_line_matches_check_ats(self):
        _, out = self.check()
        self.assertRegex(out, r"FAIL \d+   WARN \d+")

    def test_failures_are_listed_under_the_counts(self):
        _, out = self.check(with_lines((True, "Built his platform.")))
        self.assertIn("  FAIL  ", out)


if __name__ == "__main__":
    unittest.main()
