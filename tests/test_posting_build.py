"""`jsk posting extract` and `jsk posting build`: code extracts, the model decides, code
writes the posting - the application's posting graph in career/store/.

The JumpCloud run spent 26.5k output tokens hand-writing posting.ttl, most of it ids and
quotes copied character for character. These tests pin that the build's quotes cannot
drift from the advert, that no qualification or responsibility line goes unanswered,
that every bad decision is refused before anything is written, and that a rebuild writes
the same graph.
"""
import contextlib
import datetime
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import appkit
import fixtures  # noqa: F401 - puts the worktree's src first on sys.path
from appkit import seed

from jsk import posting
from jsk.graph import postingbuild, rules, store

FIXTURES = Path(__file__).parent / "graph_fixtures"
STEM = "acme-staff-platform"
TODAY = datetime.date(2026, 9, 27)

ADVERT = """https://jobs.example.com/acme/staff-platform

# Staff Platform Engineer

Acme Health · Engineering · Melbourne · Hybrid

Acme Health runs clinical software for forty hospitals.

## What you'll do

- Own the Kubernetes platform that runs the clinical event pipeline.
- Mentor engineers across three squads.

## Requirements

- 8+ years building distributed systems in production.
- **Core stack:** Python, Terraform and Kafka on Microsoft Azure.
- You must have run Docker in production.

## Nice to have

- Experience with Azure AI Foundry.

## Benefits

- Four weeks of paid leave.

Candidates must be based in Australia; visa sponsorship is not available.
"""

# The lines extract numbers for ADVERT, by n.
HEADER = """company: Acme Health
title: Staff Platform Engineer
url: https://jobs.example.com/acme/staff-platform
seniority: architecture-ownership
domain: c:healthcare
"""
ROWS = """# n | slug | asked | concepts | need
3 | kubernetes_platform | Kubernetes platform | c:kubernetes |
4 | - | mentoring, asked again in the qualifications
5 | distributed_systems | distributed systems | - |
6 | python | Python | c:python |
6 | terraform | Terraform | c:terraform |
6 | kafka | Kafka | c:kafka |
7 | docker | Docker | c:docker |
8 | azure_ai_foundry | Azure AI Foundry | c:azure-ai-foundry |
"""


class Workspace(unittest.TestCase):
    """The graph fixtures, plus one application holding ADVERT."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.app = self.root / "applications" / STEM
        self.app.mkdir(parents=True)
        (self.app / "posting.md").write_text(ADVERT, encoding="utf-8", newline="\n")
        seed(self.root)
        self.target = f"applications/{STEM}/posting"
        self.gaps = f"applications/{STEM}/gaps"

    def decide(self, rows=ROWS, header=HEADER, name="decisions.txt"):
        path = self.app / name
        path.write_text(header + "\n" + rows, encoding="utf-8", newline="\n")
        return path

    def build(self, rows=ROWS, header=HEADER, replace=False):
        return postingbuild.build(str(self.app), str(self.decide(rows, header)), replace=replace,
                                  vocabulary=self.root / "vocabulary.ttl", today=TODAY)

    def refused(self, rows=ROWS, header=HEADER, says=""):
        with self.assertRaises(posting.Refused) as caught:
            self.build(rows, header)
        self.assertIn(says, str(caught.exception))
        self.assertTrue(caught.exception.fix.startswith("fix:"))
        self.assertFalse(appkit.has(self.root, self.target), "a refusal writes nothing")
        return caught.exception

    def loaded(self):
        return store.load(self.root, vocabulary=self.root / "vocabulary.ttl")

    def text(self):
        return appkit.text(self.root, self.target)

    def put_posting(self, turtle):
        appkit.put(self.root, self.target, turtle, prefixes=False)


class Lines(unittest.TestCase):
    def test_the_numbering_this_file_relies_on(self):
        lines = rules.advert_lines(ADVERT)
        self.assertEqual([(x.n, x.section) for x in lines], [
            (1, "other"), (2, "other"), (3, "responsibility"), (4, "responsibility"),
            (5, "qualification"), (6, "qualification"), (7, "qualification"),
            (8, "qualification"), (9, "other")])
        self.assertTrue(lines[0].elig and lines[8].elig)
        self.assertTrue(lines[7].optional)


class Extract(Workspace):
    def extract(self):
        return postingbuild.extract(str(self.app), vocabulary=self.root / "vocabulary.ttl",
                                    today=TODAY)

    def test_the_header_is_ready_to_copy(self):
        out = self.extract()
        for line in ("# Staff Platform Engineer at Acme Health",
                     "# posting id: post_acme_staff_platform",
                     "# seniority hint: staff -> architecture-ownership",
                     "company: Acme Health", "title: Staff Platform Engineer",
                     "url: https://jobs.example.com/acme/staff-platform",
                     "seniority: architecture-ownership", "captured: 2026-09-27"):
            self.assertIn(line + "\n", out)
        # What extract prints as the header, decisions.parse reads back.
        from jsk.graph import decisions
        head = decisions.parse(out.split("\n# n ", 1)[0]).header
        self.assertEqual(head["company"], "Acme Health")
        self.assertEqual(head["seniority"], "architecture-ownership")

    def test_each_line_numbered_with_section_flag_and_concepts(self):
        out = self.extract().splitlines()
        self.assertIn("1 other elig Acme Health · Engineering · Melbourne · Hybrid", out)
        self.assertIn("3 resp       Own the Kubernetes platform that runs the clinical event "
                      "pipeline.", out)
        at = out.index("6 qual       Core stack: Python, Terraform and Kafka on Microsoft Azure.")
        self.assertEqual(out[at + 1],
                         "  concepts: c:python, c:terraform, c:kafka, c:azure")
        self.assertIn("8 qual  opt  Experience with Azure AI Foundry.", out)
        self.assertEqual(out[out.index("8 qual  opt  Experience with Azure AI Foundry.") + 1],
                         "  concepts: c:azure-ai-foundry")
        self.assertNotIn("Four weeks", "\n".join(out), "a benefits list asks nothing")
        self.assertFalse(any(x.startswith("  concepts:") for x in out[out.index(
            "4 resp       Mentor engineers across three squads."):][1:2]))

    def test_the_directory_date_is_not_part_of_the_id(self):
        dated = self.app.parent / f"2026-09-27-{STEM}"
        self.app.rename(dated)
        self.app = dated
        self.assertIn("# posting id: post_acme_staff_platform\n", self.extract())

    def test_outside_a_workspace_the_lines_still_print(self):
        loose = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, loose, True)
        (loose / "posting.md").write_text(ADVERT, encoding="utf-8")
        out = postingbuild.extract(str(loose), today=TODAY)
        self.assertIn("no workspace", out.splitlines()[0])
        self.assertIn("6 qual       Core stack:", out)
        self.assertNotIn("concepts:", out)

    def test_no_posting_md_is_refused(self):
        (self.app / "posting.md").unlink()
        with self.assertRaises(posting.Refused) as caught:
            self.extract()
        self.assertIn("jsk posting fetch", caught.exception.fix)


class Build(Workspace):
    def test_the_built_posting_passes_the_quote_and_coverage_checks(self):
        path, count, warnings = self.build()
        self.assertEqual((path, count, warnings), (self.target, 7, []))
        s = self.loaded()
        mine = [f for f in s.findings if f.file == self.target]
        self.assertEqual([f.text() for f in mine if f.rule in
                          ("quote-verbatim", "advert-uncovered", "necessity-wording")], [])
        self.assertEqual([f.text() for f in mine if f.severity == "FAIL"], [])
        text = self.text()
        self.assertIn("k:post_acme_staff_platform j:company", text)
        self.assertIn('j:captured "2026-09-27"^^xsd:date', text)
        self.assertIn("j:seniority j:architecture-ownership ; j:domain c:healthcare", text)

    def test_one_line_split_three_ways_quotes_that_line_three_times(self):
        self.build()
        line = '"Core stack: Python, Terraform and Kafka on Microsoft Azure."'
        self.assertEqual(self.text().count(f"j:quote {line}"), 3)
        for slug in ("python", "terraform", "kafka"):
            self.assertIn(f"k:req_acme_staff_platform_{slug} ", self.text())

    def test_the_default_need_follows_the_section(self):
        self.build()
        s = self.loaded()
        from jsk.graph import ontology as O
        need = {r["r"].value[len(O.K):]: r["n"].value[len(O.J):] for r in s.select(
            f"PREFIX j: <{O.J}> SELECT ?r ?n WHERE {{ ?r j:necessity ?n }}")
            if "acme_staff" in r["r"].value}
        self.assertEqual(need["req_acme_staff_platform_kubernetes_platform"], "implicit")
        self.assertEqual(need["req_acme_staff_platform_python"], "required")
        self.assertEqual(need["req_acme_staff_platform_docker"], "required")
        self.assertEqual(need["req_acme_staff_platform_azure_ai_foundry"], "preferred")

    def test_a_responsibility_made_required_warns(self):
        rows = ROWS.replace("c:kubernetes |", "c:kubernetes | required")
        _, _, warnings = self.build(rows)
        self.assertEqual(len(warnings), 1)
        self.assertIn("kubernetes_platform makes responsibility line 3 required", warnings[0])
        self.assertIn("j:necessity j:required", self.text())

    @staticmethod
    def extra(count):
        """`count` more rows off line 5, each asking a different run of its words."""
        words = "8+ years building distributed systems in production.".split()
        runs = [" ".join(words[a:b]) for a in range(len(words))
                for b in range(a + 1, len(words) + 1)]
        runs.remove("distributed systems")          # ROWS asks that one already
        return "".join(f"5 | term_{i} | {run} | - |\n" for i, run in enumerate(runs[:count]))

    def test_past_twenty_requirements_warns(self):
        _, count, warnings = self.build(ROWS + self.extra(14))
        self.assertEqual(count, 21)
        self.assertEqual(len(warnings), 1)
        self.assertIn("21 requirements, past the soft cap of 20", warnings[0])

    def test_twenty_is_not_past_the_cap(self):
        self.assertEqual(self.build(ROWS + self.extra(13))[2], [])

    def test_captured_defaults_to_today(self):
        self.build()
        self.assertIn('"2026-09-27"^^xsd:date', self.text())

    def test_a_rebuild_writes_the_same_graph(self):
        self.build()
        first = appkit.facts(self.root, self.target)
        self.build(replace=True)
        self.assertEqual(appkit.facts(self.root, self.target), first)

    def test_the_posting_is_a_graph_in_the_store_and_no_file(self):
        self.build()
        self.assertTrue(appkit.has(self.root, self.target))
        self.assertFalse((self.app / "posting.ttl").exists())

    def put_gaps(self):
        appkit.put(self.root, self.gaps, "k:gap_acme_staff_platform j:fit j:partial .\n")

    def test_a_rebuild_removes_the_derived_assessment_and_keeps_gaps_txt(self):
        """A rebuild can drop a requirement the assessment names, and that dangling ref would
        block prepare in this directory; gaps.txt is the analyst's, keyed by slug."""
        self.build()
        self.put_gaps()
        for name in ("gaps.md", "gaps.txt"):
            (self.app / name).write_text(name + "\n", encoding="utf-8")
        _, _, warnings = self.build(replace=True)
        self.assertFalse(appkit.has(self.root, self.gaps))
        self.assertEqual([n for n in ("gaps.md", "gaps.txt") if (self.app / n).exists()],
                         ["gaps.txt"])
        self.assertEqual(warnings, [f"removed {self.gaps} and gaps.md, derived from the "
                                    "posting this replaces; `jsk tailor prepare` writes them "
                                    "again, with gaps.txt folded in"])

    def test_replace_writes_the_posting_and_drops_the_assessment_in_one_update(self):
        """P4: the two change together or not at all - a posting rebuilt beside the old
        assessment would leave it naming requirements that may be gone."""
        from jsk.graph import record as R
        self.build()
        self.put_gaps()
        calls = []
        real = R.write_graphs

        def spy(root, graphs, create=False):
            calls.append(sorted(graphs))
            return real(root, graphs, create)
        with mock.patch.object(R, "write_graphs", spy):
            self.build(ROWS.replace("c:docker |", "c:docker | preferred"), replace=True)
        self.assertEqual(calls, [sorted([self.target, self.gaps])])
        self.assertIn("j:necessity j:preferred", self.text())

    def test_a_replace_the_store_refuses_changes_neither(self):
        self.build()
        self.put_gaps()
        before = (appkit.facts(self.root, self.target), appkit.facts(self.root, self.gaps))
        with appkit.refusing_store():
            with self.assertRaises(posting.Refused) as caught:
                self.build(ROWS.replace("c:docker |", "c:docker | preferred"), replace=True)
        self.assertIn("nothing was changed", str(caught.exception))
        self.assertEqual((appkit.facts(self.root, self.target),
                          appkit.facts(self.root, self.gaps)), before)

    def send(self, submitted='"2026-09-20"^^xsd:date'):
        appkit.put(self.root, f"applications/{STEM}/application",
                   f"k:app_acme_staff_platform j:submitted {submitted} .\n")

    def test_a_sent_posting_is_not_rebuilt_and_its_assessment_is_left_alone(self):
        """Ruling 6: a sent posting is what the application answered - the posting, and the
        assessment derived from it, stay as they are, and the refusal writes nothing."""
        self.build()
        self.put_gaps()
        (self.app / "gaps.md").write_text("gaps.md\n", encoding="utf-8")
        self.send()
        before = (appkit.graphs(self.root), (self.app / "gaps.md").read_bytes())
        with self.assertRaises(posting.Refused) as caught:
            self.build(ROWS.replace("c:docker |", "c:docker | preferred"), replace=True)
        self.assertIn("sent on 2026-09-20", str(caught.exception))
        self.assertTrue(caught.exception.fix.startswith("fix:  "), caught.exception.fix)
        self.assertEqual((appkit.graphs(self.root), (self.app / "gaps.md").read_bytes()), before)

    def test_a_stray_application_ttl_file_does_not_freeze_a_stored_application(self):
        """`jsk kb load` leaves the old files where they were; the store alone says sent."""
        self.build()
        (self.app / "application.ttl").write_text(
            appkit.PREFIXES + 'k:app_acme_staff_platform j:submitted "2026-09-20"^^xsd:date .\n',
            encoding="utf-8")
        self.build(ROWS.replace("c:docker |", "c:docker | preferred"), replace=True)
        self.assertIn("j:necessity j:preferred", self.text())

    def test_an_application_held_back_is_rebuilt(self):
        """`submitted false`: frozen for the documents, but not sent - the posting may move."""
        self.build()
        self.send("false")
        self.build(replace=True)
        self.assertIn("k:post_acme_staff_platform", self.text())

    def test_an_existing_posting_needs_replace(self):
        kept = 'k:post_hand j:company "Hand reviewed" .\n'
        appkit.put(self.root, self.target, kept)
        before = appkit.facts(self.root, self.target)
        with self.assertRaises(posting.Refused) as caught:
            self.build()
        self.assertIn("--replace", caught.exception.fix)
        self.assertEqual(appkit.facts(self.root, self.target), before)
        self.build(replace=True)
        self.assertIn('j:company "Acme Health"', self.text())       # whole, under its id

    def test_a_rebuild_keeps_the_posting_id_and_capture_day_already_there(self):
        """The application record points at the posting id already written, and the advert
        was saved on the day the posting says, not on the day of the rebuild."""
        self.build(header=HEADER + "captured: 2026-09-01\n")
        legacy = self.text().replace("post_acme_staff_platform", "post_acme_staff") \
            .replace("req_acme_staff_platform_", "req_acme_staff_")
        self.put_posting(legacy)
        self.build(replace=True)
        self.assertIn("k:post_acme_staff j:company", self.text())
        self.assertIn("k:req_acme_staff_python ", self.text())
        self.assertIn('"2026-09-01"^^xsd:date', self.text())


class Refusals(Workspace):
    def test_a_decisions_file_that_does_not_parse(self):
        self.refused(ROWS + "5 | Bad Slug | systems | - |\n", says="is not lowercase words")

    def test_no_decisions_file(self):
        with self.assertRaises(posting.Refused) as caught:
            postingbuild.build(str(self.app), vocabulary=self.root / "vocabulary.ttl")
        self.assertIn("no decisions file", str(caught.exception))

    def test_an_unknown_line(self):
        self.refused(ROWS + "42 | nowhere | systems | - |\n", says="line 42 is not one")

    def test_an_unknown_line_dropped(self):
        self.refused(ROWS + "42 | - | no such line\n", says="line 42 is not one")

    def test_asked_not_in_its_line(self):
        self.refused(ROWS.replace("5 | distributed_systems | distributed systems",
                                  "5 | distributed_systems | microservices"),
                     says="'microservices' is not in line 5")

    def test_asked_is_matched_whatever_its_case_and_spacing(self):
        self.build(ROWS.replace("| distributed systems |", "| Distributed   SYSTEMS |"))
        self.assertIn('j:asked "Distributed   SYSTEMS"', self.text())

    def test_a_concept_that_does_not_exist(self):
        self.refused(ROWS.replace("c:docker", "c:dockerr"), says="c:dockerr is not a concept")

    def test_a_retired_concept(self):
        vocab = self.root / "vocabulary.ttl"
        vocab.write_text(vocab.read_text(encoding="utf-8").replace(
            'c:docker a j:Technology ; j:label "Docker" .',
            'c:docker a j:Technology ; j:label "Docker" ; j:retired "2026-01-01"^^xsd:date ; '
            'j:reason "Replaced." .'), encoding="utf-8")
        self.assertTrue(any(r for r in self.loaded().select(
            "PREFIX j: <tag:jsk,2026:ns#> SELECT ?c WHERE { ?c j:retired ?x }")),
            "the fixture edit must retire c:docker")
        self.refused(says="c:docker is retired")

    def test_a_domain_that_is_not_a_domain(self):
        self.refused(header=HEADER.replace("c:healthcare", "c:docker"), says="not a Domain")

    def test_a_duplicate_slug(self):
        self.refused(ROWS + "7 | docker | Docker | c:docker |\n", says="slug 'docker' is used")

    def test_two_requirements_asking_the_same_term(self):
        """`jsk match --gaps` pairs gaps.md rows by the normalised `asked`: a second
        requirement asking it could never pair."""
        e = self.refused(ROWS + "5 | systems_again | Distributed  Systems | - |\n",
                         says="two requirements ask 'Distributed  Systems'")
        self.assertIn("decisions.txt:10 and line 16", str(e))
        self.assertIn("merge them into one requirement", e.fix)

    def test_a_missing_company(self):
        self.refused(header=HEADER.replace("company: Acme Health\n", ""), says="no `company:`")

    def test_a_blank_title(self):
        self.refused(header=HEADER.replace("title: Staff Platform Engineer", "title:"),
                     says="no `title:`")

    def test_a_bad_seniority(self):
        self.refused(header=HEADER.replace("architecture-ownership", "staff"),
                     says="seniority 'staff' is not a level")

    def test_a_bad_capture_day(self):
        self.refused(header=HEADER + "captured: last week\n", says="would not pass")

    def test_a_qualification_line_neither_used_nor_dropped(self):
        self.refused(ROWS.replace("7 | docker | Docker | c:docker |\n", ""),
                     says="advert line 7 neither used nor dropped")

    def test_a_responsibility_line_neither_used_nor_dropped(self):
        self.refused(ROWS.replace("4 | - | mentoring, asked again in the qualifications\n", ""),
                     says="advert line 4 neither used nor dropped")

    def test_other_and_eligibility_lines_may_go_unmentioned(self):
        self.assertEqual(self.build()[1], 7)     # lines 1, 2 and 9 are in no row

    def test_a_dropped_line_counts_as_answered(self):
        self.build(ROWS.replace("7 | docker | Docker | c:docker |\n",
                                "7 | - | the person has never used it\n"))
        self.assertNotIn("Docker", self.text())


class Command(Workspace):
    """posting.main, as `jsk posting` runs it - against the shipped vocabulary, so these
    rows name only concepts the fixture's kb.ttl defines."""

    MAIN_ROWS = """3 | kubernetes_platform | Kubernetes platform | - |
4 | - | mentoring
5 | distributed_systems | distributed systems | - |
6 | core_stack | Python | - |
7 | docker | Docker | - |
8 | azure_ai_foundry | Azure AI Foundry | - |
"""

    def main(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = posting.main(list(args))
        return code, buf.getvalue()

    def test_extract(self):
        code, out = self.main("extract", str(self.app))
        self.assertEqual(code, 0)
        self.assertIn("company: Acme Health\n", out)
        self.assertIn("5 qual       8+ years building", out)

    def test_build_writes_and_says_how_many(self):
        self.decide(self.MAIN_ROWS)
        code, out = self.main("build", str(self.app))
        self.assertEqual(code, 0, out)
        self.assertEqual(out, f"wrote {self.target}  5 requirements\n")

    def test_build_with_a_named_file_prints_its_warnings(self):
        path = self.decide(self.MAIN_ROWS.replace("Kubernetes platform | - |",
                                                  "Kubernetes platform | - | required"),
                           name="mine.txt")
        code, out = self.main("build", str(self.app), str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("\nWARN - ", out)

    def test_a_refusal_exits_1_and_says_why(self):
        self.decide(self.MAIN_ROWS)
        appkit.put(self.root, self.target, 'k:post_kept j:company "Kept" .\n')
        code, out = self.main("build", str(self.app))
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("REFUSED - "), out)
        self.assertIn("\nfix:", out)
        code, out = self.main("build", str(self.app), "--replace")
        self.assertEqual(code, 0, out)

    def test_extract_refused_exits_1(self):
        (self.app / "posting.md").unlink()
        self.assertEqual(self.main("extract", str(self.app))[0], 1)

    # A Windows editor's cp1252 save: `\x93` is its opening curly quote, and not UTF-8.
    CP1252 = b"\x93quoted\x94 in a Windows editor\n"

    def assert_refused_naming(self, args, name):
        code, out = self.main(*args)
        self.assertEqual(code, 1, out)
        self.assertTrue(out.startswith("REFUSED - "), out)
        self.assertIn(name, out.splitlines()[0])
        self.assertIn("UTF-8", out)
        self.assertIn("\nfix:  ", out)
        self.assertNotIn("Traceback", out)

    def test_a_posting_md_that_is_not_utf8_is_refused(self):
        (self.app / "posting.md").write_bytes(ADVERT.encode("utf-8") + self.CP1252)
        self.decide(self.MAIN_ROWS)
        self.assert_refused_naming(["extract", str(self.app)], "posting.md")
        self.assert_refused_naming(["build", str(self.app)], "posting.md")
        self.assertFalse(appkit.has(self.root, self.target))

    def test_a_decisions_file_that_is_not_utf8_is_refused(self):
        path = self.decide(self.MAIN_ROWS)
        path.write_bytes(path.read_bytes() + b"# " + self.CP1252)
        self.assert_refused_naming(["build", str(self.app)], "decisions.txt")
        self.assertFalse(appkit.has(self.root, self.target))

    def test_called_wrong_exits_2(self):
        for args in (["extract"], ["extract", "a", "b"], ["build"], ["build", "a", "b", "c"],
                     ["extract", str(self.app), "--replace"], ["build", "a", "--force"], []):
            code, out = self.main(*args)
            self.assertEqual(code, 2, args)
            self.assertIn("jsk posting build <application-dir>", out)


if __name__ == "__main__":
    unittest.main()
