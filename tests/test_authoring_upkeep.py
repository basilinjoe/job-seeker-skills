"""The bundle's housekeeping verbs: capability · question · log · reindex.

Every test pins a rule from
docs/superpowers/specs/2026-08-31-okf-write-cli-design.md or the catalogue plan
beside it. Two of the rules here are about not touching what the command was not
asked to touch - reindex must not reorder or retitle a row somebody wrote, and
must not read the root index's map table as a list of concepts - because a
repair that rewrites a person's file is a repair they stop running.
"""
import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from fixtures import (CONCEPT, INIT_BUNDLE, SCRIPTS, VALIDATE_BUNDLE,
                      authoring_module, run)

upkeep = authoring_module("authoring.upkeep")
commands = authoring_module("authoring.commands")
common = authoring_module("authoring.common")
concept = authoring_module("authoring.concept")
stage = authoring_module("authoring.stage")
OKF = SCRIPTS / "okf.py"


def _parser():
    """A parser holding only this module's nouns."""
    parser = argparse.ArgumentParser(prog="okf")
    nouns = parser.add_subparsers(dest="noun", metavar="<noun>")
    upkeep.register(nouns)
    return parser


def okf(*argv):
    """One command end to end, through the shipped dispatcher.

    Returns (exit code, everything it printed) - the whole of what a person or an
    agent gets back, since a refusal's message is not paraphrased downstream.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = commands.main([str(item) for item in argv])
    return code, buffer.getvalue()


def snapshot(root):
    """Every file under `root`, with its bytes and its mtime."""
    out = {}
    for directory, _, names in os.walk(str(root)):
        for name in names:
            path = os.path.join(directory, name)
            out[path] = (open(path, "rb").read(), os.stat(path).st_mtime_ns)
    return out


class BundleCase(unittest.TestCase):
    """A scaffolded bundle, and the four files these verbs write."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)
        self.vocabulary = self.root / "framework" / "capability-vocabulary.md"
        self.questions = self.root / "resume-generation" / "open-questions.md"
        self.log = self.root / "log.md"
        self.index = self.root / "projects" / "index.md"
        self.root_index = self.root / "index.md"

    def read(self, path):
        return Path(path).read_text(encoding="utf-8")

    def validates(self):
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)

    def project(self, stem="care-platform", text=CONCEPT):
        """One project concept on disk, and no index row for it."""
        path = self.root / "projects" / (stem + ".md")
        path.write_text(text, encoding="utf-8")
        return path

    def theme(self):
        return "Architecture & design"

    def capability(self, *terms, theme=None):
        return okf("capability", "add", "--bundle", self.root,
                   *[item for term in terms for item in ("--term", term)],
                   "--theme", theme or self.theme())

    def ask(self, text="What was p95 before the rewrite?", *extra):
        return okf("question", "add", "--bundle", self.root, "--text", text,
                   *extra)


# --- capability add -------------------------------------------------------------

class CapabilityAdd(BundleCase):
    """`okf capability add` lists a term under an existing theme, standalone.

    Until now a term could only be added as a side effect of
    `okf project add --new-capability`, so extending the vocabulary ahead of the
    evidence meant hand-editing the one file whose job is to be canonical.
    """

    def test_a_term_is_listed_under_the_theme(self):
        code, out = self.capability("data-sovereignty")
        self.assertEqual(code, 0, out)
        text = self.read(self.vocabulary)
        self.assertIn("# Architecture & design\n\n- `data-sovereignty`", text)

    def test_the_gate_reads_the_term_back(self):
        # The whole point of the row: validate_bundle.py must extract it, or the
        # capability check stays off for a term the person believes is listed.
        self.capability("data-sovereignty")
        terms, path = common.existing_capabilities(str(self.root))
        self.assertEqual(str(path), str(self.vocabulary))
        self.assertIn("data-sovereignty", terms)

    def test_the_term_is_logged(self):
        # Capabilities are the primary matching axis and compare as exact
        # strings, so the day a term entered the vocabulary is the day the
        # ranking of everything naming it changed.
        self.capability("data-sovereignty")
        self.assertIn("Added capability `data-sovereignty` to "
                      "framework/capability-vocabulary.md under "
                      '"Architecture & design"', self.read(self.log))

    def test_several_terms_land_in_one_change(self):
        code, out = self.capability("data-sovereignty", "ai-platform-architecture")
        self.assertEqual(code, 0, out)
        terms, _ = common.existing_capabilities(str(self.root))
        self.assertEqual({"data-sovereignty", "ai-platform-architecture"}, terms)

    def test_a_repeated_term_is_listed_once(self):
        # `data-residency` rather than the scaffolder's own example values, which
        # sit inside a fence and would make every count in this class read 2.
        self.capability("data-residency", "data-residency")
        self.assertEqual(1, self.read(self.vocabulary).count("- `data-residency`"))

    def test_a_term_already_listed_is_refused(self):
        # The file is the canonical list, and a duplicate row in it is the one
        # thing it must not have.
        self.capability("data-residency")
        code, out = self.capability("data-residency")
        self.assertEqual(1, code)
        self.assertIn("already in framework/capability-vocabulary.md", out)
        self.assertIn("fix:", out)
        self.assertEqual(1, self.read(self.vocabulary).count("- `data-residency`"))

    def test_a_term_only_in_the_fenced_example_is_not_already_listed(self):
        # init_bundle.py puts its example values INSIDE a fence, so a fresh
        # bundle lists nothing - to this layer and to validate_bundle.py alike.
        # Refusing `data-sovereignty` here would refuse it on every new bundle.
        self.assertIn("- `data-sovereignty`", self.read(self.vocabulary))
        code, out = self.capability("data-sovereignty")
        self.assertEqual(code, 0, out)

    def test_a_term_the_gate_cannot_read_is_refused(self):
        # validate_bundle.py extracts a term with `([a-z0-9-]+)` inside
        # backticks, so each of these lands as a row the gate reads no term from.
        for term in ("Data_Sovereignty", "data_sovereignty", "DataSovereignty",
                     "data sovereignty", "data.sovereignty", "café"):
            with self.subTest(term=term):
                code, out = self.capability(term)
                self.assertEqual(1, code, out)
                self.assertIn("not the shape a capability takes", out)
                self.assertIn("fix:", out)
                self.assertNotIn(term, self.read(self.vocabulary))

    def test_a_theme_that_is_not_a_heading_is_refused_by_name(self):
        code, out = self.capability("data-sovereignty", theme="Architecture")
        self.assertEqual(1, code)
        self.assertIn("no heading named 'Architecture'", out)
        # It names the headings that are there, so the next attempt is informed.
        self.assertIn("Architecture & design", out)
        self.assertIn("Leadership & engagement", out)

    def test_a_set_key_is_refused_rather_than_dropped(self):
        code, out = okf("capability", "add", "--bundle", self.root,
                        "--term", "data-sovereignty", "--theme", self.theme(),
                        "--set", "owner=me")
        self.assertEqual(1, code)
        self.assertIn("writes no frontmatter", out)

    def test_json_names_the_files_and_the_terms(self):
        code, out = okf("capability", "add", "--bundle", self.root,
                        "--term", "data-sovereignty", "--term", "ai-ops",
                        "--theme", self.theme(), "--json")
        self.assertEqual(0, code, out)
        payload = json.loads(out)
        self.assertEqual("data-sovereignty, ai-ops", payload["ids"]["capability"])
        self.assertIn(str(self.vocabulary), payload["changed"])
        self.assertIn(str(self.log), payload["changed"])

    def test_the_vocabulary_publishes_before_the_log(self):
        # The vocabulary is the authored half in this one command: nothing
        # regenerates it from the tree, so it cannot publish after its own record.
        code, out = okf("capability", "add", "--bundle", self.root,
                        "--term", "data-sovereignty", "--theme", self.theme(),
                        "--json")
        self.assertEqual(0, code, out)
        changed = json.loads(out)["changed"]
        self.assertLess(changed.index(str(self.vocabulary)),
                        changed.index(str(self.log)))

    def test_dry_run_writes_nothing(self):
        before = snapshot(self.root)
        code, out = okf("capability", "add", "--bundle", self.root,
                        "--term", "data-sovereignty", "--theme", self.theme(),
                        "--dry-run")
        self.assertEqual(0, code, out)
        self.assertIn("would write", out)
        self.assertEqual(before, snapshot(self.root))

    def test_the_bundle_still_validates(self):
        self.capability("data-sovereignty")
        self.validates()


# --- question add ---------------------------------------------------------------

class QuestionAdd(BundleCase):
    """`okf question add` appends one row under one of the file's own sections."""

    def test_the_row_lands_under_blocking_by_default(self):
        code, out = self.ask()
        self.assertEqual(code, 0, out)
        self.assertIn("# Blocking\n\n- What was p95 before the rewrite?",
                      self.read(self.questions))

    def test_a_named_section_is_used(self):
        code, out = self.ask("How many providers by June?",
                             "--section", "Missing metrics")
        self.assertEqual(code, 0, out)
        text = self.read(self.questions)
        self.assertIn("# Missing metrics\n\n- How many providers by June?", text)
        # The other sections are left exactly as they were.
        self.assertIn("# Blocking\n\n# Missing metrics", text)

    def test_the_section_match_is_case_insensitive(self):
        code, out = self.ask("Anything?", "--section", "missing METRICS")
        self.assertEqual(code, 0, out)
        self.assertIn("# Missing metrics\n\n- Anything?",
                      self.read(self.questions))

    def test_a_second_question_joins_the_list(self):
        self.ask("First one?")
        self.ask("Second one?")
        self.assertIn("- First one?\n- Second one?", self.read(self.questions))

    def test_a_section_that_is_not_there_is_refused_by_name(self):
        code, out = self.ask("Anything?", "--section", "Blockers")
        self.assertEqual(1, code)
        self.assertIn("no section named 'Blockers'", out)
        self.assertIn("'Blocking'", out)
        self.assertIn("'Not yet explored'", out)
        self.assertIn("fix:", out)

    def test_an_empty_question_is_refused(self):
        code, out = self.ask("   ")
        self.assertEqual(1, code)
        self.assertIn("--text is empty", out)

    def test_a_newline_in_the_question_stays_on_one_row(self):
        # A markdown list row has no escape for a newline, so the second half
        # would sit outside the list as loose prose.
        self.ask("What was p95\nbefore the rewrite?")
        self.assertIn("- What was p95 before the rewrite?",
                      self.read(self.questions))

    def test_the_question_is_logged(self):
        self.ask("What was p95 before the rewrite?")
        self.assertIn("- Added an open question under Blocking - What was p95 "
                      "before the rewrite?", self.read(self.log))

    def test_a_link_typed_into_the_question_stays_out_of_the_log(self):
        # The row keeps it - it resolves from resume-generation/ - but log.md is
        # at the root, where the same text is a broken link.
        self.project()
        self.ask("See [care-platform](../projects/care-platform.md) - what was "
                 "p95?")
        self.assertIn("../projects/care-platform.md", self.read(self.questions))
        self.assertNotIn("../projects/", self.read(self.log))
        self.assertIn("See care-platform - what was p95?", self.read(self.log))
        self.validates()

    def test_json_reports_the_row_as_the_questions_handle(self):
        code, out = okf("question", "add", "--bundle", self.root,
                        "--text", "What was p95?", "--json")
        self.assertEqual(0, code, out)
        self.assertEqual("What was p95?", json.loads(out)["ids"]["question"])

    def test_dry_run_writes_nothing(self):
        before = snapshot(self.root)
        code, out = okf("question", "add", "--bundle", self.root,
                        "--text", "What was p95?", "--dry-run")
        self.assertEqual(0, code, out)
        self.assertEqual(before, snapshot(self.root))

    def test_the_bundle_still_validates(self):
        self.ask()
        self.validates()


class QuestionAbout(BundleCase):
    """`--about` writes a link, and a link that does not resolve is a hard error.

    validate_bundle.py reports a BROKEN LINK as an error rather than a warning,
    so a wrong `../` fails the whole bundle at the next gate - run by somebody
    other than whoever typed the stem.
    """

    def test_the_link_points_at_the_concept(self):
        self.project()
        code, out = self.ask("What was p95?", "--about", "care-platform")
        self.assertEqual(code, 0, out)
        self.assertIn("- What was p95? - "
                      "[care-platform](../projects/care-platform.md)",
                      self.read(self.questions))

    def test_the_link_resolves_for_the_gate(self):
        # The test that catches a wrong `../`: the questions file lives in
        # resume-generation/, so one level up and into projects/.
        self.project()
        self.ask("What was p95?", "--about", "care-platform")
        self.validates()

    def test_a_stem_with_no_concept_is_refused(self):
        code, out = self.ask("What was p95?", "--about", "care-platform")
        self.assertEqual(1, code)
        self.assertIn("no concept named care-platform.md", out)
        self.assertIn("projects/", out)
        self.assertIn("fix:", out)

    def test_a_path_is_not_a_stem(self):
        # "" included: it was given, and it names no concept, so it is refused
        # rather than quietly writing a row with no link.
        for value in ("../../etc/passwd", "projects/care-platform", "..", ".",
                      "", "  "):
            with self.subTest(value=value):
                code, out = self.ask("What was p95?", "--about", value)
                self.assertEqual(1, code, out)
                self.assertIn("not a path", out)

    def test_a_stem_in_two_directories_is_refused(self):
        # Nothing here can know which concept the question is about, and a link
        # to the wrong one sends the answer to the wrong file.
        self.project("shared")
        (self.root / "roles" / "shared.md").write_text(
            CONCEPT.replace("type: Project", "type: Role"), encoding="utf-8")
        code, out = self.ask("What was p95?", "--about", "shared")
        self.assertEqual(1, code)
        self.assertIn("projects/ and roles/", out)


# --- question resolve -----------------------------------------------------------

class QuestionResolve(BundleCase):
    """`okf question resolve` strikes the row and records it in log.md.

    The row is removed rather than marked: log.md is the bundle's record of what
    changed, and a resolved question kept in the file is a second place for the
    same fact to be wrong - in the file whose whole job is to list what is open.
    """

    def resolve(self, match, *extra):
        return okf("question", "resolve", "--bundle", self.root,
                   "--match", match, *extra)

    def test_the_row_is_gone_and_the_log_says_so(self):
        self.ask("What was p95 before the rewrite?")
        code, out = self.resolve("p95")
        self.assertEqual(code, 0, out)
        self.assertNotIn("p95", self.read(self.questions))
        self.assertIn("- Resolved an open question under Blocking - What was p95 "
                      "before the rewrite?", self.read(self.log))

    def test_the_answer_goes_into_the_log_row(self):
        # How it was resolved is the part worth keeping: the question is leaving
        # the file, and the log row is where the answer stays.
        self.ask("What was p95 before the rewrite?")
        code, out = self.resolve("p95", "--answer", "5 minutes, per the dashboard")
        self.assertEqual(code, 0, out)
        self.assertIn("answer: 5 minutes, per the dashboard", self.read(self.log))

    def test_the_match_is_case_insensitive(self):
        self.ask("What was P95 before the rewrite?")
        code, out = self.resolve("p95")
        self.assertEqual(code, 0, out)

    def test_the_match_is_on_a_substring_of_the_row(self):
        self.ask("How many providers by June?", "--section", "Missing metrics")
        code, out = self.resolve("providers by june")
        self.assertEqual(code, 0, out)
        self.assertIn("Resolved an open question under Missing metrics",
                      self.read(self.log))

    def test_nothing_matched_is_refused(self):
        self.ask("What was p95 before the rewrite?")
        code, out = self.resolve("latency")
        self.assertEqual(1, code)
        self.assertIn("no open question says that", out)
        self.assertIn("lists 1", out)
        self.assertIn("fix:", out)
        self.assertIn("p95", self.read(self.questions))

    def test_more_than_one_match_is_refused_and_they_are_listed(self):
        self.ask("What was p95 before the rewrite?")
        self.ask("What was p95 after the rewrite?")
        code, out = self.resolve("p95")
        self.assertEqual(1, code)
        self.assertIn("matches 2 open questions", out)
        self.assertIn("- What was p95 before the rewrite?", out)
        self.assertIn("- What was p95 after the rewrite?", out)
        self.assertIn("fix:", out)
        # Neither row was struck.
        self.assertEqual(2, self.read(self.questions).count("p95"))

    def test_an_empty_match_is_refused(self):
        self.ask("What was p95?")
        code, out = self.resolve("  ")
        self.assertEqual(1, code)
        self.assertIn("--match is empty", out)

    def test_a_fenced_example_is_not_a_question(self):
        # mode-gaps.md shows the shape a question takes, so a fenced list item in
        # this file is ordinary rather than exotic.
        text = self.read(self.questions).replace(
            "# Not yet explored\n",
            "# Not yet explored\n\n```\n- What was p95 before the rewrite?\n```\n")
        self.questions.write_text(text, encoding="utf-8")
        code, out = self.resolve("p95")
        self.assertEqual(1, code)
        self.assertIn("no open question says that", out)
        self.assertIn("lists 0", out)

    def test_add_then_resolve_leaves_the_file_as_it_was(self):
        # The blank line above a struck row is the one `question add` inserted,
        # so the round trip must not leave a line nobody typed.
        before = self.read(self.questions)
        self.ask("What was p95 before the rewrite?")
        code, out = self.resolve("p95")
        self.assertEqual(code, 0, out)
        self.assertEqual(before, self.read(self.questions))

    def test_a_question_beside_another_is_struck_alone(self):
        self.ask("First one?")
        self.ask("Second one?")
        code, out = self.resolve("first")
        self.assertEqual(code, 0, out)
        text = self.read(self.questions)
        self.assertIn("# Blocking\n\n- Second one?", text)
        self.assertNotIn("First one?", text)

    def test_json_names_the_files_and_the_struck_row(self):
        self.ask("What was p95?")
        code, out = self.resolve("p95", "--json")
        self.assertEqual(0, code, out)
        payload = json.loads(out)
        self.assertEqual("What was p95?", payload["ids"]["question"])
        self.assertEqual([str(self.questions), str(self.log)], payload["changed"])

    def test_dry_run_writes_nothing(self):
        self.ask("What was p95?")
        before = snapshot(self.root)
        code, out = self.resolve("p95", "--dry-run")
        self.assertEqual(0, code, out)
        self.assertEqual(before, snapshot(self.root))

    def test_the_log_row_carries_no_relative_link(self):
        # A relative link resolves from the file holding it and nowhere else.
        # Copying an --about row verbatim into log.md, which sits at the bundle
        # root, produced `log.md: BROKEN LINK -> ../projects/care-platform.md` -
        # a hard error from the gate, over the file the resolve had just tidied.
        self.project()
        self.ask("What was p95?", "--about", "care-platform")
        code, out = self.resolve("p95")
        self.assertEqual(code, 0, out)
        text = self.read(self.log)
        self.assertIn("Resolved an open question under Blocking - What was p95? "
                      "- care-platform", text)
        self.assertNotIn("../projects/", text)

    def test_the_bundle_still_validates(self):
        self.project()
        self.ask("What was p95?", "--about", "care-platform")
        code, out = self.resolve("p95")
        self.assertEqual(code, 0, out)
        self.validates()


# --- log ------------------------------------------------------------------------

class LogWrite(BundleCase):
    """`okf log` dates something the catalogue has no verb for.

    mode-refresh.md and mode-ship.md both instruct a log entry as a step of their
    own, and until now that meant hand-editing the file.
    """

    def test_the_row_lands_under_todays_heading(self):
        code, out = okf("log", "--bundle", self.root,
                        "--message", "Confirmed the p95 figure with the team")
        self.assertEqual(code, 0, out)
        text = self.read(self.log)
        # init_bundle.py opens the file with `# <today> - Bundle created` - a
        # level-one heading with a suffix - and that heading is today's. The row
        # joins the day rather than starting a second heading for it.
        self.assertIn("Skeleton generated. Concepts not yet populated.\n\n"
                      "- Confirmed the p95 figure with the team", text)
        self.assertNotIn("## " + common.today(), text)

    def test_a_date_files_the_row_under_another_day(self):
        code, out = okf("log", "--bundle", self.root, "--message", "Backfilled",
                        "--date", "2020-01-02")
        self.assertEqual(code, 0, out)
        self.assertIn("## 2020-01-02\n\n- Backfilled", self.read(self.log))

    def test_a_date_that_is_not_a_day_is_refused(self):
        for value in ("2026", "2026-08", "2026-8-1", "31-08-2026", "today",
                      "2026-08-31T00:00:00Z", ""):
            with self.subTest(value=value):
                code, out = okf("log", "--bundle", self.root,
                                "--message", "Backfilled", "--date", value)
                self.assertEqual(1, code, out)
                self.assertIn("not a date", out)
                self.assertIn("fix:", out)
                self.assertNotIn("Backfilled", self.read(self.log))

    def test_a_day_that_does_not_exist_is_refused(self):
        code, out = okf("log", "--bundle", self.root, "--message", "Backfilled",
                        "--date", "2026-02-31")
        self.assertEqual(1, code)
        self.assertIn("not a day that exists", out)

    def test_an_empty_message_is_refused(self):
        code, out = okf("log", "--bundle", self.root, "--message", "  ")
        self.assertEqual(1, code)
        self.assertIn("--message is empty", out)

    def test_an_absent_log_is_said_rather_than_silently_skipped(self):
        os.remove(str(self.log))
        code, out = okf("log", "--bundle", self.root, "--message", "Anything")
        self.assertEqual(1, code)
        self.assertIn("no such log.md", out)
        self.assertIn("fix:", out)

    def test_json_reports_the_day_it_was_filed_under(self):
        code, out = okf("log", "--bundle", self.root, "--message", "Backfilled",
                        "--date", "2020-01-02", "--json")
        self.assertEqual(0, code, out)
        payload = json.loads(out)
        self.assertEqual("2020-01-02", payload["ids"]["date"])
        self.assertEqual([str(self.log)], payload["changed"])

    def test_dry_run_writes_nothing(self):
        before = snapshot(self.root)
        code, out = okf("log", "--bundle", self.root, "--message", "Anything",
                        "--dry-run")
        self.assertEqual(0, code, out)
        self.assertEqual(before, snapshot(self.root))

    def test_the_noun_is_the_verb(self):
        # `okf log add` would be a level of grammar that says nothing, so the
        # noun carries the flags. argparse rejects the extra word.
        with self.assertRaises(SystemExit):
            _parser().parse_args(["log", "add", "--bundle", str(self.root),
                                  "--message", "Anything"])

    def test_the_bundle_still_validates(self):
        okf("log", "--bundle", self.root, "--message", "Anything")
        self.validates()


# --- reindex --------------------------------------------------------------------

class Reindex(BundleCase):
    """`okf reindex` is the repair for the one failure mode stage.py documents.

    A partial publish keeps the authored half and loses the derived one, by
    design - so what a torn write leaves is a concept its index.md does not list.
    That state is silent: validate_bundle.py checks that an index exists and that
    its links resolve, never that it lists every concept beside it.
    """

    def reindex(self, *extra):
        return okf("reindex", "--bundle", self.root, *extra)

    def test_a_deleted_index_row_comes_back(self):
        self.project()
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertIn("[Acme - care coordination platform](care-platform.md)",
                      self.read(self.index))
        # Torn again by hand, the way a crash between two replaces leaves it.
        rows = [line for line in self.read(self.index).split("\n")
                if "care-platform.md" not in line]
        self.index.write_text("\n".join(rows), encoding="utf-8")
        self.assertNotIn("care-platform.md", self.read(self.index))
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertIn("(care-platform.md)", self.read(self.index))
        self.validates()

    def test_the_row_carries_the_concepts_own_title_and_description(self):
        self.project()
        self.reindex()
        self.assertIn("- [Acme - care coordination platform](care-platform.md) - "
                      "Multi-tenant platform for aged-care providers.",
                      self.read(self.index))

    def test_a_broken_row_is_dropped(self):
        # The only line this command deletes: the row points at nothing, and
        # validate_bundle.py already reports it as a hard error.
        text = self.read(self.index) + "\n- [Gone](gone.md) - was here once\n"
        self.index.write_text(text, encoding="utf-8")
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(1, code, "a row pointing at nothing should fail the gate")
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertNotIn("gone.md", self.read(self.index))
        self.validates()

    def test_a_clean_bundle_is_left_alone_and_says_nothing(self):
        # init_bundle.py writes five concepts it never lists, so the first run
        # has work to do. The second must not: a repair that keeps finding
        # something to repair is one nobody can trust.
        self.project()
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        before = snapshot(self.root)
        code, out = self.reindex()
        self.assertEqual(0, code)
        self.assertEqual("", out)
        self.assertEqual(before, snapshot(self.root))

    def test_the_scaffolded_concepts_are_listed(self):
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertIn("(identity.md)", self.read(self.root / "profile" / "index.md"))
        self.assertIn("(metrics.md)",
                      self.read(self.root / "achievements" / "index.md"))
        framework = self.read(self.root / "framework" / "index.md")
        self.assertIn("(capability-vocabulary.md)", framework)
        self.assertIn("(pipeline-vocabulary.md)", framework)
        self.assertIn("(open-questions.md)",
                      self.read(self.root / "resume-generation" / "index.md"))
        self.validates()

    def test_the_placeholder_goes_when_the_first_row_arrives(self):
        # "Empty. Add concepts here." asserts something false once a row is there.
        self.project()
        self.reindex()
        self.assertNotIn("Empty. Add concepts here.", self.read(self.index))

    def test_the_root_index_map_table_is_left_alone(self):
        # index.md at the root links every directory in a table. Its rows are not
        # concept rows, and getting-started.md and log.md beside it are not
        # concepts - listing them would put them forward as evidence.
        before = self.root_index.read_bytes()
        self.project()
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertEqual(before, self.root_index.read_bytes())
        self.assertNotIn("getting-started.md", self.read(self.index))
        self.assertNotIn("(log.md)", self.read(self.index))

    def test_an_existing_row_is_not_reordered_or_retitled(self):
        # The row is the author's. index_entry declines to rewrite one for the
        # same reason, and a command that reorders an index has changed something
        # nobody asked it to.
        self.project()
        self.project("second", CONCEPT.replace(
            "Acme - care coordination platform", "Second project"))
        self.index.write_text(
            self.read(self.index).replace(
                "Empty. Add concepts here.\n",
                "- [My own words for it](care-platform.md) - and my own note\n"),
            encoding="utf-8")
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        text = self.read(self.index)
        self.assertIn("- [My own words for it](care-platform.md) - and my own "
                      "note\n", text)
        self.assertEqual(1, text.count("care-platform.md"))
        # The new one is appended below, not sorted above.
        self.assertLess(text.index("care-platform.md"), text.index("second.md"))

    def test_no_log_row_is_written(self):
        # Decided: the repair is its own record. A row here would be dated the
        # day of the repair, so the only surviving record of a concept whose real
        # `Added` row was lost in the same tear would carry the wrong date.
        self.project()
        before = self.log.read_bytes()
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertEqual(before, self.log.read_bytes())

    def test_a_directory_with_no_index_does_not_get_one(self):
        # That is validate_bundle.py's warning about a missing file - a different
        # fault - and writing one here would answer it without anybody deciding
        # what the file should say.
        index = self.root / "sources" / "index.md"
        os.remove(str(index))
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertFalse(index.exists())

    def test_a_file_with_no_frontmatter_gets_no_row(self):
        (self.root / "projects" / "notes.md").write_text(
            "Just some notes.\n", encoding="utf-8")
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertNotIn("notes.md", self.read(self.index))

    def test_directory_limits_the_repair_to_one_index(self):
        self.project()
        code, out = self.reindex("--directory", "projects")
        self.assertEqual(code, 0, out)
        self.assertIn("(care-platform.md)", self.read(self.index))
        self.assertNotIn("(identity.md)",
                         self.read(self.root / "profile" / "index.md"))

    def test_a_directory_with_no_index_in_the_layout_is_refused(self):
        for value in (".", "", "getting-started", "projects/nested",
                      "tailoring/applications/2026"):
            with self.subTest(value=value):
                code, out = self.reindex("--directory", value)
                self.assertEqual(1, code, out)
                self.assertIn("not a directory this bundle gives an index", out)
                self.assertIn("fix:", out)

    def test_a_year_directory_under_the_archive_is_in_scope(self):
        year = self.root / "tailoring" / "applications" / "2026"
        year.mkdir()
        (year / "index.md").write_text(
            concept.frontmatter("Index", {"title": "2026",
                                          "description": "This year's."})
            + "\nEmpty. Add concepts here.\n", encoding="utf-8")
        (year / "2026-03-04-acme-engineer.md").write_text(
            CONCEPT.replace("type: Project", "type: Application"),
            encoding="utf-8")
        code, out = self.reindex("--directory", "tailoring/applications/2026")
        self.assertEqual(code, 0, out)
        self.assertIn("(2026-03-04-acme-engineer.md)",
                      self.read(year / "index.md"))

    def test_json_says_what_it_added_and_dropped_per_directory(self):
        self.project()
        self.index.write_text(
            self.read(self.index) + "\n- [Gone](gone.md)\n", encoding="utf-8")
        code, out = self.reindex("--directory", "projects", "--json")
        self.assertEqual(0, code, out)
        ids = json.loads(out)["ids"]
        self.assertEqual("care-platform.md", ids["projects/index.md added"])
        self.assertEqual("gone.md", ids["projects/index.md dropped"])

    def test_the_report_names_every_directory_it_touched(self):
        self.project()
        code, out = self.reindex()
        self.assertEqual(code, 0, out)
        self.assertIn("projects/index.md added: care-platform.md", out)
        self.assertIn("profile/index.md added: identity.md", out)

    def test_dry_run_writes_nothing(self):
        self.project()
        before = snapshot(self.root)
        code, out = self.reindex("--dry-run")
        self.assertEqual(0, code, out)
        self.assertIn("would write", out)
        # A dry run still runs every decision, so it still reports the repair.
        self.assertIn("projects/index.md added: care-platform.md", out)
        self.assertEqual(before, snapshot(self.root))

    def test_the_noun_is_the_verb(self):
        with self.assertRaises(SystemExit):
            _parser().parse_args(["reindex", "run", "--bundle", str(self.root)])


class VerbFunctions(BundleCase):
    """A verb function returns a changeset and writes nothing itself.

    That is what makes --dry-run a dry run of the whole command rather than half
    of one: every decision is taken while the changeset is being built, and
    commit() is the only step a dry run skips.
    """

    def build(self, *argv):
        args = _parser().parse_args([str(item) for item in argv])
        return args.build(args)

    def test_every_verb_returns_a_changeset_and_touches_nothing(self):
        self.project()
        cases = (
            ("capability", "add", "--bundle", self.root,
             "--term", "data-residency", "--theme", self.theme()),
            ("question", "add", "--bundle", self.root, "--text", "What was p95?"),
            ("log", "--bundle", self.root, "--message", "Anything"),
            ("reindex", "--bundle", self.root),
        )
        for argv in cases:
            with self.subTest(argv=argv[:2]):
                before = snapshot(self.root)
                change = self.build(*argv)
                self.assertIsInstance(change, stage.Changeset)
                self.assertTrue(change.ordered())
                self.assertEqual(before, snapshot(self.root))

    def test_resolve_returns_a_changeset_and_touches_nothing(self):
        self.ask("What was p95?")
        before = snapshot(self.root)
        change = self.build("question", "resolve", "--bundle", self.root,
                            "--match", "p95")
        self.assertIsInstance(change, stage.Changeset)
        self.assertEqual(before, snapshot(self.root))


class LineEndings(BundleCase):
    """A bundle scaffolded on Windows is entirely CRLF, and these commands must
    not rewrite every line of a file in order to add one line to it."""

    def convert(self, newline):
        for path in self.root.rglob("*.md"):
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            path.write_bytes(raw.replace(b"\n", newline))

    def exercise(self):
        # The project's own two capabilities, because listing any term at all
        # switches validate_bundle.py's capability check on for the whole bundle.
        self.capability("ai-platform-architecture", "data-sovereignty")
        self.ask("What was p95?", "--about", "care-platform")
        okf("question", "resolve", "--bundle", self.root, "--match", "p95")
        okf("log", "--bundle", self.root, "--message", "Anything")
        okf("reindex", "--bundle", self.root)

    def touched(self):
        return (self.vocabulary, self.questions, self.log, self.index,
                self.root / "profile" / "index.md")

    def test_a_crlf_bundle_stays_crlf(self):
        self.project()
        self.convert(b"\r\n")
        self.exercise()
        for path in self.touched():
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                # Every LF is half of a CRLF, so nothing was written in the
                # other convention beside it.
                self.assertEqual(0, raw.replace(b"\r\n", b"").count(b"\n"))
        self.validates()

    def test_an_lf_bundle_stays_lf(self):
        self.project()
        self.convert(b"\n")
        self.exercise()
        for path in self.touched():
            with self.subTest(path=path.name):
                self.assertNotIn(b"\r", path.read_bytes())
        self.validates()


class OkfWiring(BundleCase):
    """Every one of these nouns is reachable through okf.py, which is what a
    person actually runs. Driven as a subprocess, so the wiring is covered by the
    same tests that cover the behaviour."""

    def test_every_noun_is_reachable(self):
        self.project()
        for argv in (("capability", "add", "--term", "ai-platform-architecture",
                      "--term", "data-sovereignty", "--theme", self.theme()),
                     ("question", "add", "--text", "What was p95?"),
                     ("question", "resolve", "--match", "p95"),
                     ("log", "--message", "Anything"),
                     ("reindex",)):
            with self.subTest(argv=argv):
                code, out = run(OKF, *argv, "--bundle", self.root)
                self.assertEqual(0, code, out)
        self.assertIn("(care-platform.md)", self.read(self.index))
        self.validates()


class BundleRoot(BundleCase):
    """--bundle is checked the same way by every one of these verbs."""

    def test_every_verb_refuses_a_path_that_is_not_a_bundle(self):
        outside = Path(self._tmp.name) / "not-a-bundle"
        outside.mkdir()
        for argv in (("capability", "add", "--term", "x", "--theme", "y"),
                     ("question", "add", "--text", "x"),
                     ("question", "resolve", "--match", "x"),
                     ("log", "--message", "x"),
                     ("reindex",)):
            with self.subTest(argv=argv):
                code, out = okf(argv[0], *argv[1:], "--bundle", outside)
                self.assertEqual(1, code, out)
                self.assertIn("not a bundle", out)
                self.assertIn("fix:", out)


if __name__ == "__main__":
    unittest.main()
