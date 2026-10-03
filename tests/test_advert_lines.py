"""advert_lines: every line of an advert a requirement could quote, by section - what
`jsk posting extract` numbers and `jsk posting build` quotes. asked_lines, which
advert-uncovered reads, is a filter over it and may only have gained lines."""
import re
import unittest
from pathlib import Path

import fixtures  # noqa: F401  (puts src/ on the path)

from jsk.domain.posting import advert as rules
from jsk.domain.posting.advert import BOLD_LINE, ELIGIBILITY, HEADING_ASKS, HEADING_NOT, LIST_ITEM, squash

REPO = Path(__file__).parent.parent


def asked_lines_before(advert):
    """asked_lines as it was before advert_lines (2026-09-27), kept to pin the refactor."""
    advert = re.sub(r"\A---\n.*?\n---\n", "", advert, flags=re.S)
    out, inside, wrapping = [], False, False
    for line in advert.split("\n"):
        text = line.strip()
        item = LIST_ITEM.fullmatch(line) if not BOLD_LINE.fullmatch(text) else None
        if wrapping and text and not item and line[:1].isspace():
            out[-1] = f"{out[-1]} {squash(text)}"
            continue
        wrapping = False
        if not item and (text.startswith("#") or BOLD_LINE.fullmatch(text)
                         or (text.endswith(":") and len(text.split()) <= 8)):
            words = squash(text)
            inside = bool(HEADING_ASKS.search(words)) and not HEADING_NOT.search(words)
        elif item and inside:
            out.append(squash(item.group(1)))
            wrapping = True
    return [x for x in out if len(x.split()) >= 4 and not ELIGIBILITY.search(x)]


ADVERT = """https://jobs.example.com/acme/123

# Staff Engineer

Acme · Engineering · Bangalore, India · Remote

We build identity software for
ten thousand companies.

## Responsibilities

- Own the end-to-end technical vision for
  the PAM product line.
- Mentor engineers across squads.

## What you'll bring

- Experience: 12+ years of software development.
- **Core Tech Stack:** Advanced C#, .NET and Go.
- Must hold Indian work authorisation.
- Terraform.

## Nice to have

- Exposure to CyberArk or BeyondTrust.

## Benefits

- Four weeks of paid leave every
  year, and a laptop.

To be considered you must be located in India.
"""


class Sections(unittest.TestCase):
    def setUp(self):
        self.lines = rules.advert_lines(ADVERT)

    def test_numbered_from_one_in_order(self):
        self.assertEqual([x.n for x in self.lines], list(range(1, len(self.lines) + 1)))

    def test_every_line_and_its_section(self):
        self.assertEqual([(x.section, x.text) for x in self.lines], [
            ("other", "Acme · Engineering · Bangalore, India · Remote"),
            ("other", "We build identity software for ten thousand companies."),
            ("responsibility", "Own the end-to-end technical vision for the PAM product line."),
            ("responsibility", "Mentor engineers across squads."),
            ("qualification", "Experience: 12+ years of software development."),
            ("qualification", "Core Tech Stack: Advanced C#, .NET and Go."),
            ("qualification", "Must hold Indian work authorisation."),
            ("qualification", "Terraform."),
            ("qualification", "Exposure to CyberArk or BeyondTrust."),
            # The last paragraph sits under Benefits, and a paragraph under an offered
            # heading is skipped now (2026-09-29-tailor-time Ruling 1).
        ])

    def test_the_url_line_and_the_benefits_are_left_out(self):
        texts = " ".join(x.text for x in self.lines)
        self.assertNotIn("https://", texts)
        self.assertNotIn("paid leave", texts)
        self.assertNotIn("laptop", texts)       # a benefit's wrapped line is not prose

    def test_optional_by_heading_or_by_wording(self):
        self.assertEqual([x.text for x in self.lines if x.optional],
                         ["Exposure to CyberArk or BeyondTrust."])
        [line] = rules.advert_lines("## Requirements\n\n- Kafka experience is a plus.\n")
        self.assertTrue(line.optional)

    def test_eligibility_is_flagged(self):
        # 10, "located in India", was under Benefits: skipped (2026-09-29-tailor-time Ruling 1).
        self.assertEqual([x.n for x in self.lines if x.elig], [1, 7])

    def test_in_this_role_opens_responsibilities(self):
        [line] = rules.advert_lines("In this role you will:\n\n- Run the platform on call.\n")
        self.assertEqual(line.section, "responsibility")

    def test_asked_lines_is_the_long_qualifications(self):
        self.assertEqual(rules.asked_lines(ADVERT), [
            "Experience: 12+ years of software development.",
            "Core Tech Stack: Advanced C#, .NET and Go.",
            "Exposure to CyberArk or BeyondTrust."])


class BareHeadings(unittest.TestCase):
    """2026-09-29-tailor-time Ruling 1: a heading with no markup. Both of that day's runs had
    well-formed posting.md files, and extract still classed every line `other`."""

    def test_headings(self):
        for text in ("HOW WE WORK", "Key Responsibilities", "What's in it for me?",
                     "Experiences & Exposure : Nice to have", "Job description"):
            with self.subTest(text=text):
                self.assertTrue(rules.bare_heading(text))
                self.assertTrue(rules._heading(text, text, None))

    def test_not_headings(self):
        for text in ("AWS", "Position Overview", "Technical Expertise", "Big picture thinking."):
            with self.subTest(text=text):
                self.assertFalse(rules.bare_heading(text))
                self.assertFalse(rules._heading(text, text, None))

    def test_what_s_in_it_for_you_is_offered(self):
        self.assertEqual(rules.advert_lines("What's in it for you?\n\nA gym on site.\n"), [])


class QuestionHeadings(unittest.TestCase):
    """A heading asked as a question may run past the six-word cap. The P3 replay
    (2026-10-04): "What makes you perfect for the role?" is seven words, and every line
    under it read as a responsibility of the heading before."""

    def lines_under(self, heading):
        advert = (f"Key Responsibilities\nDesign the platform.\n\n{heading}\n"
                  "Ten years of software engineering.\nDeep experience with Kafka.\n")
        return [(x.section, x.text) for x in rules.advert_lines(advert)]

    def test_a_question_heading_opens_the_qualifications(self):
        for heading in ("What makes you perfect for the role?", "What you'll need to succeed",
                        "Who you are", "What we are looking for in our ideal candidate?"):
            with self.subTest(heading=heading):
                self.assertEqual(self.lines_under(heading), [
                    ("responsibility", "Design the platform."),
                    ("qualification", "Ten years of software engineering."),
                    ("qualification", "Deep experience with Kafka.")])

    def test_a_long_line_that_is_no_wh_question_stays_a_line(self):
        # Seven words naming `experience`: under the cap's old reading, still a line.
        for text in ("Experience building distributed systems at large scale",
                     "Do you have experience with Kubernetes and Terraform?",
                     "Who you are matters to us more than where you studied?"):
            with self.subTest(text=text):
                self.assertFalse(rules.bare_heading(text))
                lines = self.lines_under("Requirements\n" + text)
                self.assertIn(("qualification", squash(text)), lines)


class OneItemPerLine(unittest.TestCase):
    """Under a qualification or responsibility heading each line is its own item: joining
    them made one 600-character `asked` of Schneider's whole section."""

    ADVERT = """Key Responsibilities
Design the platform's architecture.
Review designs across four teams.

Requirements
Ten years of software engineering.
Deep experience with Kafka.
Hands-on Kubernetes.

What's in it for me?
Paid leave, a laptop and
a pension plan.

We are an equal opportunity employer
and welcome everyone.
"""

    def setUp(self):
        self.lines = rules.advert_lines(self.ADVERT)

    def test_each_line_under_a_heading_is_its_own_item(self):
        self.assertEqual([(x.section, x.text) for x in self.lines if x.section != "other"], [
            ("responsibility", "Design the platform's architecture."),
            ("responsibility", "Review designs across four teams."),
            ("qualification", "Ten years of software engineering."),
            ("qualification", "Deep experience with Kafka."),
            ("qualification", "Hands-on Kubernetes."),
        ])

    def test_a_benefits_paragraph_is_skipped(self):
        texts = " ".join(x.text for x in self.lines)
        self.assertNotIn("laptop", texts)
        self.assertNotIn("pension", texts)

    def test_elsewhere_a_paragraph_is_still_one_line(self):
        # Under no heading of its own it stays with the benefits: skipped too.
        self.assertEqual([x for x in self.lines if x.section == "other"], [])
        [line] = rules.advert_lines("Acme builds software\nfor hospitals.\n")
        self.assertEqual((line.section, line.text), ("other", "Acme builds software for hospitals."))


class SubHeadings(unittest.TestCase):
    """A marked heading naming no section keeps the section it is under: the Arrow .docx,
    fetched, gives `## Key Responsibilities` and then sub-headings under it."""

    ARROW = """Source: AI Enterprise Architect.docx

## Key Responsibilities

## Technical Expertise

- Design the enterprise AI architecture.

## Team Collaboration and Coordination

- Work with the delivery teams.

**Stakeholders**

- Brief the steering committee.

## Requirements

- Ten years of architecture.

Education:

- A degree in computer science.

## About Arrow

Arrow distributes technology.
"""

    def test_sub_headings_keep_the_section(self):
        self.assertEqual([(x.section, x.text) for x in rules.advert_lines(self.ARROW)], [
            ("responsibility", "Design the enterprise AI architecture."),
            ("responsibility", "Work with the delivery teams."),
            ("responsibility", "Brief the steering committee."),
            ("qualification", "Ten years of architecture."),
            ("qualification", "A degree in computer science."),
            ("other", "Arrow distributes technology."),      # `About …` ends the section
        ])

    def test_a_hashtag_or_a_bare_heading_still_ends_it(self):
        # `#LI-Remote` comes before the boilerplate; `S,T,O` opened Allianz's skills grid.
        for heading in ("#LI-Remote", "S,T,O"):
            with self.subTest(heading=heading):
                lines = rules.advert_lines(f"## Requirements\n\n- Kafka.\n\n{heading}\n\n"
                                           "We are an equal opportunity employer.\n")
                self.assertEqual([x.section for x in lines], ["qualification", "other"])

    def test_the_source_line_is_left_out_like_the_url(self):
        lines = rules.advert_lines("Source: Requirements.docx\n\n## Requirements\n\n- Kafka.\n")
        self.assertEqual([(x.section, x.text) for x in lines], [("qualification", "Kafka.")])
        # Only as the first line: later, it is the advert's own words.
        later = rules.advert_lines("Acme builds software.\n\nSource: our own survey\n")
        self.assertEqual(len(later), 2)


class LabelsIn(unittest.TestCase):
    """queries.labels_in: the concepts whose whole label a line holds, proposed beside it."""

    @classmethod
    def setUpClass(cls):
        from appkit import stored_copy
        from test_graph_shapes import FIXTURES

        from jsk.adapters.cli.compose import match
        from jsk.adapters.cli.compose import record
        cls.named = staticmethod(match.labels_in(record.load(str(stored_copy(FIXTURES)))))

    def ids(self, line):
        return [c.rsplit("/", 1)[1] for c in self.named(line)]

    def test_in_the_order_the_line_names_them(self):
        self.assertEqual(self.ids("MSSQL, Terraform and hands-on K8s"),
                         ["sql-server", "terraform", "kubernetes"])

    def test_the_longest_label_wins(self):
        self.assertEqual(self.ids("Azure AI Foundry"), ["azure-ai-foundry"])
        self.assertEqual(self.ids("Azure AI Foundry on Azure"), ["azure-ai-foundry", "azure"])

    def test_a_space_or_a_hyphen_either_way(self):
        self.assertEqual(self.ids("event driven systems"), ["event-driven-architecture"])
        self.assertEqual(self.ids("SQL-Server"), ["sql-server"])

    def test_whole_words_only(self):
        self.assertEqual(self.ids("Pythonic code and ASP.NET"), [])

    def test_nothing_named(self):
        self.assertEqual(self.ids("a strong sense of ownership"), [])


class AskedLinesLoseNothing(unittest.TestCase):
    """asked_lines moved on purpose with bare headings and one item per line
    (2026-09-29-tailor-time Ruling 1, tailor-cost Ruling 4): more lines read as asked. What
    must not move is a line asked before going unasked now."""
    TRICKY = [
        ADVERT,
        "---\ntitle: x\n---\n## Requirements\n- Five years of Go in production\n",
        "## Requirements\n- Deep Kafka experience with\n  streaming at scale\n- Four words long here\n",
        "## What you'll do\n- Run the thing every day\n  Requirements:\n- Must know Terraform well\n",
        "## Benefits\n- Paid leave for everyone here\n  You have:\n- Must know Terraform well\n",
        "**Requirements**\n\n* Must have Terraform in production\n\n## Benefits\n- x y z w\n",
        "You have:\n1. Strong Python for data work\n2) Five years of SQL\n",
        "## Requirements\n- Must hold a visa to work here\n- ok\n",
    ]

    def test_every_posting_md_in_the_repo_and_the_tricky_ones(self):
        adverts = [p.read_text(encoding="utf-8") for p in REPO.rglob("posting.md")
                   if ".git" not in p.parts]
        self.assertTrue(adverts)
        for advert in adverts + self.TRICKY:
            with self.subTest(advert=advert[:60]):
                now = rules.asked_lines(advert)
                self.assertEqual([x for x in asked_lines_before(advert) if x not in now], [])


if __name__ == "__main__":
    unittest.main()
