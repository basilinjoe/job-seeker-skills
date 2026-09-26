"""The letter check: a cover letter's length, prose and numbers, against its resume.json.

mode-tailor.md had the model write a letter nothing checked, beside a resume whose every
number traces to a current metric version. These are the cases that asked it the same
question: over the claims fixture (tests/careerkit.py), whose contoso-platform resume
renders the latency, team and SSO bullets and withholds the inferred ingestion one.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import careerkit
from jsk import cli
from jsk.gates import letter

BULLETS = ["ach_events_latency", "ach_events_team", "ach_identity_sso", "ach_data_ingestion"]

CLEAN = """Dear Hiring Manager,

I build event platforms that other teams build on. At Meridian Health I cut p95 event
latency from 5 s to 400 ms on AKS with Kafka, and led a team of 6 engineers while doing it.

I moved 40 applications to Entra ID single sign-on, and have run Kafka since 2021. Her
team's platform is the kind I have built. The gap: I have not run Kubernetes outside AKS.

Sincerely,
Test Person
"""


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = letter.main(list(argv))
    return code, out.getvalue()


class LetterCase(unittest.TestCase):
    def workspace(self, edits=(), posting=None):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        _, record = careerkit.workspace(Path(tmp, "ws"), edits=list(edits),
                                        short={"resume": 2, "bullets": BULLETS})
        if posting is not None:
            Path(record).with_name("posting.md").write_text(posting, encoding="utf-8")
        return record

    def check(self, text, edits=(), posting=None, name="cover-letter.txt", record=True):
        path = self.workspace(edits, posting)
        target = Path(path).with_name(name)
        target.write_text(text, encoding="utf-8")
        return run(str(target), *(["--record", path] if record else []))

    def swap(self, old, new):
        self.assertIn(old, CLEAN)
        return CLEAN.replace(old, new)


class Numbers(LetterCase):
    def test_a_clean_letter_passes(self):
        """400 and 5 are met_latency.v2's, 6 met_team's, 40 met_apps' - each a current
        version a rendered bullet cites. 2021 is a year."""
        code, out = self.check(CLEAN)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - fit to send", out)

    def test_a_number_the_career_does_not_hold_fails(self):
        code, out = self.check(self.swap("40 applications", "55 applications"))
        self.assertEqual(code, 1, out)
        self.assertIn("number-untraced letter - '55'", out)
        self.assertIn("ask the person for the figure and its source", out)

    def test_a_superseded_number_fails_naming_the_version(self):
        """met_latency.v1 said 1 ms and was replaced on 2026-03-01."""
        code, out = self.check(self.swap("to 400 ms", "to 1 ms"))
        self.assertEqual(code, 1, out)
        self.assertIn("number-superseded letter - '1' is k:met_latency.v1's number", out)

    def test_a_withheld_bullets_number_is_an_unconfirmed_claim(self):
        """ach_data_ingestion is inferred, below the file's confirmed floor: selected, never
        rendered. Its number is not one the application stands on."""
        edits = [('"Built a FastAPI ingestion service."',
                  '"Built a FastAPI ingestion service for 900 sources."')]
        code, out = self.check(self.swap("40 applications", "40 applications and 900 sources"),
                               edits)
        self.assertEqual(code, 1, out)
        self.assertIn("number-unconfirmed letter - '900' is only in ach_data_ingestion", out)

    def test_a_confirmed_bullet_the_resume_does_not_select_does_not_trace(self):
        code, out = self.check(self.swap("40 applications", "100,000 players"))
        self.assertEqual(code, 1, out)
        self.assertIn("number-untraced letter - '100,000'", out)

    def test_a_year_is_a_date_not_a_claim(self):
        code, out = self.check(self.swap("since 2021", "since 2019"))
        self.assertEqual(code, 0, out)

    def test_a_number_quoted_verbatim_from_the_posting_is_its_words(self):
        text = self.swap("The gap:", 'You ask for "3 on-call rotations a year". The gap:')
        code, out = self.check(text, posting="We need 3 on-call rotations a year.\n")
        self.assertEqual(code, 0, out)
        code, out = self.check(text, posting="Nothing about rotations.\n")
        self.assertIn("number-untraced letter - '3'", out)

    def test_years_of_a_label_are_asked_of_the_roles(self):
        """Kafka: the event and identity projects, 2021-09 to 2026-06."""
        code, out = self.check(self.swap("since 2021", "for 4 years of Kafka"))
        self.assertEqual(code, 0, out)
        code, out = self.check(self.swap("since 2021", "for 9 years of Kafka"))
        self.assertIn("years-overstated letter - claims 9 years of Kafka", out)

    def test_without_a_record_the_number_check_is_skipped_and_a_failure(self):
        code, out = self.check(CLEAN, record=False)
        self.assertEqual(code, 1, out)
        self.assertIn("numbers-skipped letter - SKIPPED", out)
        self.assertIn("against: nothing - no --record", out)


class Length(LetterCase):
    def test_the_body_over_250_words_fails(self):
        filler = " ".join(["Platforms"] * 251) + "."
        code, out = self.check(self.swap("The gap:", filler + " The gap:"))
        self.assertEqual(code, 1, out)
        self.assertIn("too-long letter", out)

    def test_the_salutation_and_closing_are_not_counted(self):
        text = "Dear Hiring Manager,\n\nOne two three.\n\nBest regards,\nTest Person\n"
        self.assertEqual(letter.length_lines(text)[1], 3)
        self.assertEqual(letter.length_lines("One two three.\n")[1], 3)

    def test_a_reader_counts_hyphenated_and_suffixed_words_once(self):
        self.assertEqual(letter.length_lines("Event-driven, 40K users, 62% faster.")[1], 5)


class Prose(LetterCase):
    def test_enthusiasm_padding_fails(self):
        code, out = self.check(self.swap("I build event", "I am passionate about building event"))
        self.assertEqual(code, 1, out)
        self.assertIn("padding letter - 'passionate'", out)

    def test_first_and_third_person_are_a_letters_voice(self):
        """check_prose fails "her" in a resume; a letter speaks of the reader's team."""
        code, out = self.check(CLEAN)
        self.assertNotIn("third person", out)
        self.assertNotIn("verb", out)

    def test_a_placeholder_fails(self):
        code, out = self.check(self.swap("40 applications", "[N] applications"))
        self.assertEqual(code, 1, out)
        self.assertIn("unresolved placeholder", out)

    def test_a_sentence_stopping_on_its_article_fails(self):
        code, out = self.check(self.swap("outside AKS.", "outside the"))
        self.assertEqual(code, 1, out)
        self.assertIn("unfinished letter - a sentence stops on 'the'", out)

    def test_cut_on_sight_phrases_warn(self):
        code, out = self.check(self.swap("I build event", "I was responsible for event"))
        self.assertEqual(code, 0, out)
        self.assertIn("warn  cut-on-sight letter - 'responsible for'", out)


class Files(LetterCase):
    def test_md_and_txt_both_read(self):
        for name in ("cover-letter.txt", "cover-letter.md"):
            with self.subTest(name):
                code, out = self.check(CLEAN, name=name)
                self.assertEqual(code, 0, out)
                self.assertIn(f"checking: {name}", out)

    def test_another_format_is_called_wrong(self):
        code, out = self.check(CLEAN, name="cover-letter.pdf")
        self.assertEqual(code, 2, out)

    def test_a_missing_letter_is_called_wrong(self):
        self.assertEqual(run("nowhere.txt")[0], 2)

    def test_jsk_check_only_letter_runs_it(self):
        record = self.workspace()
        target = Path(record).with_name("cover-letter.txt")
        target.write_text(CLEAN, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "check", str(target), "--only", "letter",
                             "--record", record])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("PASS - fit to send", out.getvalue())

    def test_the_default_check_never_runs_it(self):
        self.assertNotIn("letter", [gate[0] for gate in cli.CHECK_GATES])


if __name__ == "__main__":
    unittest.main()
