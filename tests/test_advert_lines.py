"""advert_lines: every line of an advert a requirement could quote, by section - what
`jsk posting extract` numbers and `jsk posting build` quotes. asked_lines, which
advert-uncovered reads, is now a filter over it and must not have moved."""
import re
import unittest
from pathlib import Path

import fixtures  # noqa: F401  (puts src/ on the path)

from jsk.graph import rules
from jsk.graph.rules import BOLD_LINE, ELIGIBILITY, HEADING_ASKS, HEADING_NOT, LIST_ITEM, squash

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
            ("other", "To be considered you must be located in India."),
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
        self.assertEqual([x.n for x in self.lines if x.elig], [1, 7, 10])

    def test_in_this_role_opens_responsibilities(self):
        [line] = rules.advert_lines("In this role you will:\n\n- Run the platform on call.\n")
        self.assertEqual(line.section, "responsibility")

    def test_asked_lines_is_the_long_qualifications(self):
        self.assertEqual(rules.asked_lines(ADVERT), [
            "Experience: 12+ years of software development.",
            "Core Tech Stack: Advanced C#, .NET and Go.",
            "Exposure to CyberArk or BeyondTrust."])


class LabelsIn(unittest.TestCase):
    """queries.labels_in: the concepts whose whole label a line holds, proposed beside it."""

    @classmethod
    def setUpClass(cls):
        from appkit import stored_copy
        from test_graph_shapes import FIXTURES

        from jsk.graph import queries
        from jsk.graph import store as S
        cls.named = staticmethod(queries.labels_in(S.load(str(stored_copy(FIXTURES)))))

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


class AskedLinesUnchanged(unittest.TestCase):
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
                self.assertEqual(rules.asked_lines(advert), asked_lines_before(advert))


if __name__ == "__main__":
    unittest.main()
