"""cli.py is a convenience layer over the render and gate scripts, and its one job is
to be transparent: the same arguments, the same exit code, and the underlying script's
own output. These tests pin that transparency, because a dispatcher that quietly
changes a verdict is worse than no dispatcher at all.
"""
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import careerkit
from fixtures import (CLI, CLEAN_RESUME, example_short, SCRIPTS,
                      build_pdf, build_text, gate, load_script, resume_with, run)

from jsk import cli

JSK = CLI
GOOD = {"resume": 2, "bullets": ["ach_events_latency", "ach_events_team", "ach_identity_sso"]}
BODY = "Cut order-processing latency 62 percent by decomposing a monolithic service."

SUBCOMMANDS = ["doctor", "kb", "posting", "tailor", "resume", "letter", "app"]


class Usage(unittest.TestCase):
    """Called with nothing useful, it must say what it can do.

    The exit code splits on whether the caller asked. `--help` is a question that
    got its answer, so it exits 0; a bare invocation is a call with nothing in it,
    so it stays 2, the documented code for "you called it wrong".

    Both used to return 2, so an agent or a script checking exit codes saw a failure
    for reading the documentation SKILL.md tells it to read.
    """

    def test_help_lists_every_subcommand(self):
        code, out = run(JSK, "--help")
        self.assertEqual(code, 0, out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)

    def test_help_stops_at_its_marker(self):
        """The cut was a literal buried in usage(); it is a named constant now, and the
        docstring is held to it so that rewording the last paragraph cannot silently
        print it as help."""
        from jsk.adapters.cli import main
        self.assertIn(main.HELP_ENDS_BEFORE, main.__doc__)
        code, out = run(JSK, "--help")
        self.assertEqual(code, 0, out)
        self.assertNotIn("markdown-it-py", out)
        self.assertIn("jsk resume check", out)

    def test_bare_invocation_is_help(self):
        code, out = run(JSK)
        self.assertEqual(code, 2, out)
        self.assertIn("jsk resume check", out)

    def test_every_subcommand_answers_help_the_same_way(self):
        """One contract across the surface, whichever kind of command you reached.

        The hand-rolled entry points printed their usage and returned 2, so an agent
        or script checking exit codes saw a failure for reading the documentation
        SKILL.md tells it to read.
        """
        for sub in SUBCOMMANDS:
            with self.subTest(subcommand=sub):
                code, out = run(JSK, sub, "--help")
                self.assertEqual(code, 0, f"jsk {sub} --help exited {code}: {out}")
                self.assertTrue(out.strip(), f"jsk {sub} --help printed nothing")

    def test_render_help_names_its_flags(self):
        """`jsk render --help` printed the two-line invocation and stopped, so the
        flags SKILL.md sends a reader here to look up were documented nowhere the
        command itself would show them."""
        code, out = run(JSK, "resume", "render", "--help")
        self.assertEqual(code, 0, out)
        for flag in ("--pdf", "--ats-max", "--template"):
            self.assertIn(flag, out)

    def test_jsk_index_is_retired_and_says_what_replaced_it(self):
        """It read user-knowledgebase.md. The career is career/kb.ttl now: `jsk match`
        ranks it against a posting, `jsk kb view` reads it. A bare "unknown command" would
        read as a broken install."""
        code, out = run(JSK, "index", "user-knowledgebase.md")
        self.assertEqual(code, 2, out)
        for pointer in ("jsk tailor match", "jsk kb view"):
            self.assertIn(pointer, out)
        from jsk import cli
        self.assertNotIn("index", cli.NOUNS)

    def test_jsk_migrate_is_retired_and_says_what_replaced_it(self):
        """It moved a user-knowledgebase.md to career/kb.ttl. The Markdown format is not
        read any more: `jsk new` starts a record, `jsk kb export` writes a resume.json."""
        code, out = run(JSK, "migrate", "user-knowledgebase.md")
        self.assertEqual(code, 2, out)
        self.assertIn("jsk migrate was retired", out)
        for pointer in ("jsk kb new", "jsk kb export"):
            self.assertIn(pointer, out)
        from jsk import cli
        self.assertNotIn("migrate", cli.NOUNS)

    def test_unknown_subcommand_names_the_real_ones(self):
        code, out = run(JSK, "frobnicate")
        self.assertEqual(code, 2, out)
        self.assertIn("unknown command: frobnicate", out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)


class ValidateRouting(unittest.TestCase):
    """`jsk validate` checks one thing - the short resume.json - and every other target
    it is handed has to be refused by name.

    It used to dispatch between a bundle and a record. There is no bundle now, so the
    interesting cases are the two things somebody will pass instead: the directory the
    old call took, and the knowledge base, which looks like the source of truth
    because it is one and is nevertheless not what this gate reads."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_json_routes_to_the_record_validator(self):
        code, out = run(JSK, "resume", "check", example_short())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)

    def test_an_unknown_flag_is_refused_not_ignored(self):
        """`--level` went with the bundle format. Ignoring it exited 0, which read as
        "level 2 confirmed"; placed first, its value was taken for the file."""
        for argv in ([example_short(), "--level", "2"], ["--level", "2", example_short()]):
            with self.subTest(argv=argv):
                code, out = run(JSK, "resume", "check", *argv)
                self.assertEqual(code, 2, out)
                self.assertIn("--level", out)

    def test_flags_are_forwarded_unchanged(self):
        """--strict is the underlying script's flag; the dispatcher must not eat it."""
        code, out = run(JSK, "resume", "check", example_short(), "--strict")
        self.assertIn("checking:", out)
        # The script's own refusal, naming the flag: it reached the record gate
        # rather than being dropped on the way.
        code2, out2 = run(JSK, "resume", "check", example_short(), "--nonsense-flag")
        self.assertEqual(code2, 2, out2)
        self.assertIn("unknown flag: --nonsense-flag", out2)

    def test_missing_target_is_a_usage_error(self):
        code, out = run(JSK, "resume", "check", self.tmp / "nope.json")
        self.assertEqual(code, 2, out)
        self.assertIn("file not found", out)

    def test_unvalidatable_target_says_what_it_wanted(self):
        stray = self.tmp / "notes.json"
        stray.write_text("not a record", encoding="utf-8")
        code, out = run(JSK, "resume", "check", stray)
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_a_directory_is_a_render_s_directory(self):
        """`jsk resume check` picks its gates from its target: a directory gets all four
        (today's `jsk gates`), and an empty one says that none of them ran."""
        code, out = run(JSK, "resume", "check", self.tmp)
        self.assertEqual(code, 1, out)
        self.assertIn("--- record gate", out)
        self.assertIn("resume.json", out)

    def test_the_knowledge_base_is_refused_and_says_what_is_checked_instead(self):
        kb = self.tmp / "user-knowledgebase.md"
        kb.write_text("# Career knowledge base", encoding="utf-8")
        code, out = run(JSK, "resume", "check", kb)
        self.assertEqual(code, 2, out)
        self.assertIn("resume.json", out)
        # The career is the record `jsk kb check` validates, not a Markdown file.
        self.assertNotIn("jsk migrate", out)
        self.assertIn("jsk kb check", out)

    def test_the_graph_record_is_refused_and_pointed_at_kb_check(self):
        kb = self.tmp / "kb.ttl"
        kb.write_text("k:kb j:format 3 .", encoding="utf-8")
        code, out = run(JSK, "resume", "check", kb)
        self.assertEqual(code, 2, out)
        self.assertIn("jsk kb check", out)
        self.assertIn("resume.json", out)

    def test_validate_with_no_target(self):
        code, out = run(JSK, "resume", "check")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)


class Check(unittest.TestCase):
    """`jsk check` runs both document gates on one file. It must run both even when
    the first fails - a document with parse problems can have prose problems too, and
    seeing them in one pass is the whole point."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def document(self, paragraphs=None, name="resume.txt"):
        """The .txt: the one artefact both gates read, so `jsk check` can still
        run them in a single pass now that check_ats.py reads the PDF and
        check_prose.py reads the .tex."""
        return build_text(self.tmp / name,
                          CLEAN_RESUME if paragraphs is None else paragraphs)

    def test_clean_resume_passes_both_gates(self):
        code, out = run(JSK, "resume", "check", self.document())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to send", out)
        self.assertIn("PASS - prose rules satisfied", out)

    def test_both_gates_are_labelled(self):
        code, out = run(JSK, "resume", "check", self.document())
        del code
        self.assertIn("parse gate", out)
        self.assertIn("prose gate", out)

    def test_a_failing_gate_propagates_its_exit_code(self):
        bad = self.document(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = run(JSK, "resume", "check", bad)
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)

    def test_the_second_gate_still_runs_after_the_first_fails(self):
        bad = self.document(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = run(JSK, "resume", "check", bad)
        del code
        self.assertIn("prose gate", out)

    def test_passing_both_does_not_imply_the_other_two_gates(self):
        """SKILL.md: "passing one says nothing about the others". A clean parse and
        prose result must not read as a finished resume."""
        code, out = run(JSK, "resume", "check", self.document())
        del code
        self.assertIn("jsk resume check <record>.json", out)
        self.assertIn("PDF", out)

    def test_strict_reaches_the_parse_gate(self):
        code, out = run(JSK, "resume", "check", self.document(), "--strict")
        del code
        self.assertIn("--strict", out)

    def test_check_with_no_target(self):
        code, out = run(JSK, "resume", "check")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)


class CheckOnly(unittest.TestCase):
    """`--only` runs one document gate by name.

    mode-resume.md calls a single gate when one file has been repaired and only that
    gate needs re-running - "the right thing for re-checking one file after one
    repair". Without this flag those lines had to reach past cli.py to check_ats.py
    and check_prose.py directly, which is exactly the coupling cli.py exists to remove.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def document(self, paragraphs=None, name="resume.txt"):
        return build_text(self.tmp / name,
                          CLEAN_RESUME if paragraphs is None else paragraphs)

    def test_only_prose_does_not_run_the_parse_gate(self):
        code, out = run(JSK, "resume", "check", self.document(), "--only", "prose")
        self.assertEqual(code, 0, out)
        self.assertIn("prose gate", out)
        self.assertNotIn("parse gate", out)

    def test_only_parse_does_not_run_the_prose_gate(self):
        code, out = run(JSK, "resume", "check", self.document(), "--only", "parse")
        del code
        self.assertIn("parse gate", out)
        self.assertNotIn("prose gate", out)

    def test_only_parse_still_forwards_strict(self):
        code, out = run(JSK, "resume", "check", self.document(), "--only", "parse", "--strict")
        del code
        self.assertIn("--strict", out)

    def test_one_gate_passing_never_reads_as_both(self):
        """The load-bearing assertion. `jsk check` closes with "Both document gates
        passed", and printing that after running one would be the false green the
        wording exists to prevent."""
        code, out = run(JSK, "resume", "check", self.document(), "--only", "prose")
        self.assertEqual(code, 0, out)
        self.assertNotIn("Both document gates passed", out)
        self.assertIn("Three gates did not run", out)
        self.assertIn("the other document gate", out)

    def test_an_unknown_gate_is_refused_by_name(self):
        code, out = run(JSK, "resume", "check", self.document(), "--only", "bogus")
        self.assertEqual(code, 2, out)
        self.assertIn("bogus", out)
        self.assertIn("parse, prose", out)

    def test_only_with_no_value_is_refused(self):
        code, out = run(JSK, "resume", "check", self.document(), "--only")
        self.assertEqual(code, 2, out)
        self.assertIn("--only needs a value", out)

    def test_the_flag_may_precede_the_file(self):
        """`--only prose resume.txt` has to work: the target is found after the flag
        and its value are removed, not by position in the raw argv."""
        code, out = run(JSK, "resume", "check", "--only", "prose", self.document())
        self.assertEqual(code, 0, out)
        self.assertIn("prose gate", out)

    def test_the_help_names_the_flag(self):
        """A flag the skill cannot discover is a flag the skill will not use - the
        mode files read `jsk --help` for the surface."""
        code, out = run(JSK, "--help")
        del code
        self.assertIn("--only parse|prose", out)


TEX_PREAMBLE = "\\documentclass{article}\n\\begin{document}\n"


class GatesCase(unittest.TestCase):
    """A record and a directory of rendered files, the two things `jsk gates` reads.

    The record is written OUTSIDE the render directory here, and named with --record,
    so that every test below is explicit about which one it is checking. The
    convenience of finding `resume.json` beside the documents is its own test.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        # A short resume.json reads its career, so both it and the render directory sit
        # in a workspace - the render directory beside the application, not inside it.
        root, record = careerkit.workspace(self.tmp / "ws", short=GOOD)
        self.record = Path(record)
        self.out = Path(root) / "out"
        self.out.mkdir()

    def break_record(self):
        """A record that fails the record gate and nothing else.

        A bullet the career does not hold is the failure worth using: it leaves every
        rendered document untouched, so a test using it pins that one failing gate
        does not disturb the four that passed.
        """
        self.record.write_text(json.dumps({**GOOD, "bullets": ["ach_nothing_like_it"]}),
                               encoding="utf-8")

    def render(self, paragraphs=None, pages=1):
        """The three files render_resume.py leaves behind, without needing a TeX engine.

        The names are the ones jsk-verifier.md globs for, because that is what
        decides which gate reads which file.
        """
        lines = CLEAN_RESUME if paragraphs is None else paragraphs
        pdf = build_pdf(self.out / "Jane_Doe_Resume.pdf", lines)
        if pages > 1:
            import pymupdf
            with pymupdf.open(pdf) as doc:
                for _ in range(pages - 1):
                    doc.new_page()
                doc.save(str(self.out / "tmp.pdf"))
            (self.out / "tmp.pdf").replace(self.out / "Jane_Doe_Resume.pdf")
        build_text(self.out / "Jane_Doe_Resume_ATS.txt", lines)
        (self.out / "Jane_Doe_Resume.tex").write_text(
            TEX_PREAMBLE + "\n".join("\\item " + l for l in lines) + "\n\\end{document}\n",
            encoding="utf-8")

    def gates(self, *args):
        return run(JSK, "resume", "check", self.out, *args)


class GatesAgreement(GatesCase):
    """The one test the whole subcommand rests on: same record, same files, same
    verdicts and same exit code as running the five commands by hand.

    A faster gate that disagrees with the slow one is worse than no change at all,
    so the comparison is against the checkers' literal output rather than against a
    remembered snapshot of it.
    """

    def five_commands(self):
        pdf = self.out / "Jane_Doe_Resume.pdf"
        tex = self.out / "Jane_Doe_Resume.tex"
        txt = self.out / "Jane_Doe_Resume_ATS.txt"
        return [
            ("record.py", [self.record]),
            ("check_ats.py", [pdf]),
            ("check_ats.py", [txt, "--strict"]),
            ("check_prose.py", [tex]),
            ("check_prose.py", [txt]),
        ]

    def assertAgrees(self):
        worst, outputs = 0, []
        for script, args in self.five_commands():
            code, out = gate(script, *args)
            worst = max(worst, code)
            outputs.append((script, out))
        code, combined = self.gates("--record", self.record)
        self.assertEqual(code, worst, combined)
        for name, out in outputs:
            self.assertIn(out.strip(), combined,
                          f"{name} said something jsk gates did not repeat:\n{out}")
        return combined

    def test_a_clean_render_agrees(self):
        self.render()
        self.assertAgrees()

    def test_a_failing_record_gate_agrees(self):
        self.break_record()
        self.render()
        combined = self.assertAgrees()
        self.assertIn("DO NOT RENDER", combined)

    def test_a_failing_document_gate_agrees(self):
        self.render(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        combined = self.assertAgrees()
        self.assertIn("DO NOT SEND", combined)

    def test_every_gate_still_runs_after_an_earlier_one_fails(self):
        """`jsk check`'s rule, applied to five gates instead of two: a document with
        a record defect can have prose defects too, and one pass should show them
        all."""
        self.break_record()
        self.render(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = self.gates("--record", self.record)
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("--- parse gate"), 2, out)
        self.assertEqual(out.count("--- prose gate"), 2, out)


class GatesMissingInput(GatesCase):
    """A gate that did not run is not a gate that passed. Every one of these must
    leave a non-zero exit behind, because SKIPPED printed above an exit 0 is how a
    resume goes out unchecked."""

    def test_no_record_skips_the_record_gate_and_fails(self):
        self.render()
        code, out = self.gates()
        self.assertEqual(code, 1, out)
        self.assertIn("SKIPPED", out)
        self.assertIn("A gate that did not run is not a gate that passed.", out)

    def test_a_record_beside_the_render_is_found_without_being_named(self):
        """The skill writes resume.json into the application directory it renders
        into, so the ordinary call has nothing to point at it with."""
        self.render()
        (self.out / "resume.json").write_text(json.dumps(GOOD), encoding="utf-8")
        code, out = self.gates()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)

    def test_an_empty_directory_skips_every_document_gate_and_fails(self):
        code, out = self.gates("--record", self.record)
        self.assertEqual(code, 1, out)
        sections, summary = out.split("=== summary")
        self.assertEqual(sections.count("SKIPPED"), 3, out)
        self.assertEqual(summary.count("SKIPPED"), 3, out)
        self.assertIn("--- parse gate", out)
        self.assertIn("--- prose gate", out)
        self.assertIn("--- layout gate", out)

    def test_a_record_path_that_is_wrong_is_a_call_error(self):
        """Given-and-wrong is a different mistake from not-given, and reporting the
        two the same way hides one of them."""
        self.render()
        code, out = self.gates("--record", self.tmp / "nope.json")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


class GatesRenderGate(GatesCase):
    """The gate jsk gates never runs. A command that exited 0 having quietly left it
    out would be the most dangerous thing in this file."""

    def test_a_clean_run_still_says_the_pdf_is_unread(self):
        self.render()
        code, out = self.gates("--record", self.record)
        self.assertEqual(code, 0, out)
        self.assertIn("UNVERIFIED", out)
        self.assertIn("read every page", out)

    def test_the_render_gate_is_never_reported_as_passed(self):
        self.render()
        code, out = self.gates("--record", self.record)
        del code
        # The section, not the summary under it - which says PASS for the gates above.
        render = out.split("--- render gate")[1].split("=== summary")[0]
        self.assertNotIn("PASS", render)
        self.assertIn("render gate  UNVERIFIED", out.split("=== summary")[1])

    def test_it_says_so_when_there_is_no_pdf_at_all(self):
        self.render()
        (self.out / "Jane_Doe_Resume.pdf").unlink()
        code, out = self.gates("--record", self.record)
        del code
        self.assertIn("there is no PDF", out)

    def test_the_json_form_carries_the_render_gate_too(self):
        """--json is the form an agent parses, and it is the form most likely to be
        read by machine and reported as a list of passes."""
        self.render()
        code, out = self.gates("--record", self.record, "--json")
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        render = [g for g in report["gates"] if g["gate"] == "render gate"]
        self.assertEqual(len(render), 1, out)
        self.assertEqual(render[0]["status"], "UNVERIFIED")


class GatesOutput(GatesCase):
    def test_json_carries_each_gates_output_whole(self):
        """The evidence rule survives the machine-readable form: --json embeds what
        each checker printed rather than a verdict word standing in for it."""
        self.render()
        code, out = self.gates("--record", self.record, "--json")
        del code
        report = json.loads(out)
        record = [g for g in report["gates"] if g["gate"] == "record gate"][0]
        self.assertIn("checking:", record["output"])
        self.assertIn("PASS - safe to render", record["output"])

    def test_the_ats_variant_is_held_to_the_ats_maximal_rules(self):
        """The same rule render_resume.py prints after a render: the file aimed at a
        parser is the one checked with --strict."""
        self.render()
        code, out = self.gates("--record", self.record)
        del code
        self.assertIn("check_ats.py Jane_Doe_Resume_ATS.txt --strict", out)
        self.assertIn("mode: ATS-maximal (strict)", out)
        self.assertIn("mode: presentation", out)

    def test_max_findings_reaches_the_record_gate(self):
        self.break_record()
        self.render()
        code, out = self.gates("--record", self.record, "--max-findings", "0")
        self.assertEqual(code, 1, out)
        self.assertNotIn("... and", out)


class GatesPageBudget(GatesCase):
    """--pages measures the PDF that exists. Over budget is reported and not failed,
    because fit_pages.py owns that verdict and is the only thing that can act on it -
    render_resume.py's page_report() already says it in those words."""

    def test_it_prints_the_measured_count_against_the_budget(self):
        self.render()
        code, out = self.gates("--record", self.record, "--pages", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("1 page against a budget of 2", out)

    def test_over_budget_is_reported_and_does_not_change_the_exit_code(self):
        self.render(pages=3)
        code, out = self.gates("--record", self.record, "--pages", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("OVER BUDGET", out)

    def test_a_budget_with_no_pdf_says_it_was_not_measured(self):
        self.render()
        (self.out / "Jane_Doe_Resume.pdf").unlink()
        code, out = self.gates("--record", self.record, "--pages", "2")
        del code
        self.assertIn("not measured", out)


class GatesUsage(GatesCase):
    def test_a_view_is_a_usage_error_naming_one_resume(self):
        """It labelled the report with the view a full record rendered. A resume.json
        is one resume, so there is nothing left for it to name."""
        self.render()
        code, out = self.gates("--record", self.record, "--view", "view_default")
        self.assertEqual(code, 2, out)
        self.assertIn("a resume.json is one resume", out)

    def test_the_help_no_longer_offers_a_view(self):
        code, out = run(JSK, "resume", "check", "--help")
        self.assertEqual(code, 0, out)
        self.assertNotIn("--view", out)

    def test_an_out_directory_that_does_not_exist_is_a_call_error(self):
        code, out = run(JSK, "resume", "check", self.tmp / "nowhere")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_an_unknown_flag_is_a_call_error(self):
        code, out = self.gates("--recheck")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)

    def test_a_flag_left_without_its_value_is_a_call_error(self):
        code, out = run(JSK, "resume", "check", self.out, "--pages")
        self.assertEqual(code, 2, out)
        self.assertIn("needs a value", out)

    def test_pages_must_be_a_number(self):
        code, out = self.gates("--pages", "two")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


class GatesEntryPoints(unittest.TestCase):
    """jsk gates imports the checkers instead of spawning them, so their in-process
    entry points are part of the contract now, not an implementation detail."""

    def test_both_document_gates_take_their_arguments_and_return_a_code(self):
        for name in ("check_ats", "check_prose"):
            module = load_script(SCRIPTS / f"{name}.py")
            with tempfile.TemporaryDirectory() as tmp:
                path = build_text(Path(tmp) / "resume.txt", CLEAN_RESUME)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = module.main([path])
            self.assertEqual(code, 0, f"{name}: {buf.getvalue()}")
            self.assertIn("checking:", buf.getvalue())


def in_process(*argv):
    """(exit code, stdout) of cli.main() called in this interpreter.

    The dispatch is in-process now, so the tests that pin it call it the same way -
    which is also the only way a patched compile_pdf can reach the renderer.
    """
    from jsk import cli
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(["jsk"] + [str(a) for a in argv])
    return code, buf.getvalue()


class InProcessDispatch(unittest.TestCase):
    """Every subcommand calls its script in this interpreter.

    Each one used to spawn a child, and `jsk check` spawned two: a Python start-up
    and a fresh import of the package per gate, for work that takes a fraction of
    that. What has to survive the change is what the child gave for free - the exit
    code, and every heading landing above the output it introduces.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_cli_spawns_nothing(self):
        """The one exception, preflight's end-to-end run, lives in preflight.py and
        says why there. cli.py itself has no reason left to import subprocess."""
        source = (SCRIPTS / "cli.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("def run(", source)

    def test_check_spawns_no_child(self):
        doc = build_text(self.tmp / "resume.txt", CLEAN_RESUME)
        with mock.patch("subprocess.Popen", side_effect=AssertionError("spawned")):
            code, out = in_process("resume", "check", doc)
        self.assertEqual(code, 0, out)

    def test_each_heading_is_above_the_output_it_introduces(self):
        """The ordering a child interpreter needed a flush for. A heading printed
        after its gate's output would put every verdict under the wrong section."""
        code, out = run(JSK, "resume", "check", build_text(self.tmp / "resume.txt", CLEAN_RESUME))
        self.assertEqual(code, 0, out)
        parse = out.index("--- parse gate")
        prose = out.index("--- prose gate")
        self.assertLess(parse, out.index("mode: presentation"))
        self.assertLess(out.index("mode: presentation"), prose)
        self.assertLess(prose, out.index("PASS - prose rules satisfied"))

    def test_a_failing_gate_keeps_its_exit_code_in_process(self):
        bad = build_text(self.tmp / "resume.txt",
                         resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = in_process("resume", "check", bad)
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)

    def test_a_bare_sys_exit_is_a_clean_exit(self):
        """argparse's --help exits by raising SystemExit(0), and a bare sys.exit()
        raises it with None. Both are exit 0 from a child interpreter, and reading
        None as a failure would turn `jsk fit --help` into one."""
        from jsk import cli
        fake = mock.Mock(main=mock.Mock(side_effect=SystemExit(None)))
        with mock.patch("importlib.import_module", return_value=fake):
            code, _ = cli.call_gate("kb.py", [])
        self.assertEqual(code, 0)

    def test_fit_help_still_names_its_own_program(self):
        """In process, sys.argv[0] is jsk's, and argparse would have printed that as
        the program name in fit_pages.py's usage line."""
        code, out = run(JSK, "resume", "fit", "--help")
        self.assertEqual(code, 0, out)
        self.assertIn("usage: jsk resume fit", out)

    def test_a_script_that_raises_is_reported_not_propagated(self):
        fake = mock.Mock(main=mock.Mock(side_effect=RuntimeError("boom")))
        with mock.patch("importlib.import_module", return_value=fake):
            code, out = in_process("resume", "render", "x.json")
        self.assertEqual(code, 2, out)
        self.assertIn("render_resume.py raised RuntimeError: boom", out)
        self.assertIn("jsk resume render x.json", out)


class PreviewInProcess(unittest.TestCase):
    """`jsk preview` renders every template in this interpreter and compiles them
    at once. The compile is faked here, so none of this needs a TeX engine: what is
    pinned is the plumbing - separate stages, and a report in template order however
    the compiles happen to finish."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _, self.record = careerkit.workspace(self.tmp / "ws", short=GOOD)
        self.out = self.tmp / "looks"

    def preview(self, compile_pdf):
        from jsk.render import preview_templates
        with mock.patch.object(preview_templates, "available_engine",
                               return_value="fake"), \
                mock.patch.object(preview_templates, "compile_pdf", compile_pdf), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("spawned")):
            return in_process("resume", "preview", self.record, "--out", self.out)

    def test_the_report_is_in_template_order_whatever_finishes_first(self):
        """The first template is made the slowest to compile. A report that followed
        completion order would list it last."""
        import threading
        import time
        from jsk.render import tex, themes
        names = themes.names()
        stages, lock = set(), threading.Lock()

        def slow_first(tex_path, out_dir):
            with lock:
                stages.add(out_dir)
            if os.path.basename(tex_path).startswith(names[0] + "_"):
                time.sleep(0.3)
            return build_pdf(tex.pdf_path_for(tex_path, out_dir), CLEAN_RESUME), "fake"

        code, out = self.preview(slow_first)
        self.assertEqual(code, 0, out)
        listed = [line.split()[0] for line in out.splitlines()
                  if line.startswith("  ") and line.split()[0] in names]
        self.assertEqual(listed, names, out)
        self.assertEqual(len(stages), len(names), "two templates shared a stage")
        for name in names:
            self.assertTrue((self.out / f"{name}.pdf").exists(), name)
            self.assertTrue((self.out / f"{name}.tex").exists(), name)

    def test_a_template_that_does_not_compile_fails_the_preview(self):
        from jsk.render import tex, themes
        broken = themes.names()[1]

        def one_broken(tex_path, out_dir):
            if os.path.basename(tex_path).startswith(broken + "_"):
                return None, "UNVERIFIED - fake produced no PDF:\n    ! Missing $"
            return build_pdf(tex.pdf_path_for(tex_path, out_dir), CLEAN_RESUME), "fake"

        code, out = self.preview(one_broken)
        self.assertEqual(code, 1, out)
        self.assertIn(f"FAILED: {broken}", out)
        self.assertIn("! Missing $", out)

    def test_a_file_that_does_not_load_is_said_once_not_blamed_on_the_templates(self):
        """A legacy record fails the same way in every template; five FAILED blocks and
        "a template that does not build" sent the reader after the templates."""
        Path(self.record).write_text(json.dumps({"urs": "1.0"}), encoding="utf-8")

        def never(tex_path, out_dir):
            raise AssertionError("compiled a file that does not load")

        code, out = self.preview(never)
        self.assertEqual(code, 2, out)
        self.assertEqual(out.count("full URS record"), 1, out)
        self.assertIn("jsk kb export", out)
        self.assertNotIn("FAILED", out)
        self.assertNotIn("template that does not build", out)


def match_workspace(tmp, edit=None):
    """tests/match_fixtures copied to `tmp`, `edit(root)` applied to its files, then put
    into its store. Returns the root."""
    import shutil

    from appkit import seed
    shutil.copytree(Path(__file__).parent / "match_fixtures", tmp, dirs_exist_ok=True)
    if edit:
        edit(Path(tmp))
    seed(tmp)
    return Path(tmp)


class Match(unittest.TestCase):
    """`jsk match APP`: an assessment, so it exits 0 with gaps; 1 only for a broken record."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.FIX = match_workspace(cls._tmp.name)
        cls.CONTOSO = cls.FIX / "applications" / "contoso"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_it_prints_the_four_sections(self):
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--today", "2026-09-24")
        self.assertEqual(code, 0, out)
        for heading in ("# Match - Platform Engineer at Contoso (k:post_contoso)",
                        "## Requirements", "## Ranking", "## Cover", "## Questions"):
            self.assertIn(heading, out)
        self.assertIn("| K8s | required | matched | satisfied | k:prj_data; k:prj_events "
                      "(via c:aks, 1 hop) |", out)

    def test_json_is_the_same_result_structured(self):
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--json", "--today", "2026-09-24")
        self.assertEqual(code, 0, out)
        r = json.loads(out)
        self.assertEqual(r["posting"], "k:post_contoso")
        self.assertEqual({q["asked"]: q["state"] for q in r["requirements"]}["Go"], "ambiguous")

    def test_a_broken_record_is_not_matched(self):
        def broken(root):
            kb = root / "career" / "kb.ttl"
            kb.write_text(kb.read_text(encoding="utf-8").replace("j:uses c:aks,", "j:uses c:akss,"),
                          encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = match_workspace(tmp, broken)
            code, out = run(JSK, "tailor", "match", root / "applications" / "contoso")
        self.assertEqual(code, 1, out)
        self.assertIn("fix them before matching", out)
        self.assertIn("c:akss: nothing defines it", out)

    def test_another_postings_fault_does_not_stop_this_one(self):
        """A FAIL in the career, the vocabulary or this application's own directory stops
        the match; one in an unrelated application only gets mentioned - an old advert
        that no longer quotes cleanly must not block every new one."""
        with tempfile.TemporaryDirectory() as tmp:
            root = match_workspace(tmp)
            md = root / "applications" / "fabrikam" / "posting.md"
            md.write_text("Senior Developer at Fabrikam\n", encoding="utf-8")
            code, out = run(JSK, "tailor", "match", root / "applications" / "contoso")
            self.assertEqual(code, 0, out)
            self.assertIn("4 failures elsewhere in the workspace", out)
            code, out = run(JSK, "tailor", "match", root / "applications" / "fabrikam")
            self.assertEqual(code, 1, out)

    def test_the_warnings_are_named_not_waved_away(self):
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--today", "2026-09-24")
        self.assertIn("1 warning (label-clash)", out)
        self.assertNotIn("none changes the match", out)

    def test_an_implied_carrier_says_so(self):
        code, out = run(JSK, "tailor", "match", self.FIX / "applications" / "northwind",
                        "--today", "2026-09-24")
        self.assertIn("k:prj_events (via c:kafka, 1 hop, implied)", out)

    def test_a_relative_path_from_inside_the_workspace(self):
        from jsk.graph.match import application
        here = os.getcwd()
        try:
            os.chdir(self.FIX)
            root, app = application(os.path.join("applications", "contoso"))
            self.assertEqual((root, app), (str(self.FIX), str(self.CONTOSO)))
        finally:
            os.chdir(here)

    def test_the_posting_ttl_form_is_refused_with_the_new_one(self):
        """Ruling 11: the posting is a graph now, not a file to point at."""
        code, out = run(JSK, "tailor", "match", self.CONTOSO / "posting.ttl")
        self.assertEqual(code, 2, out)
        self.assertIn("takes the application now, not its posting.ttl", out)
        self.assertIn(f"fix:  jsk tailor match {self.CONTOSO}", out)

    def test_gaps_txt_that_raises_a_verdict_fails(self):
        """--gaps checks the analyst's gaps.txt against the match: .NET is carried only by
        tags, so `satisfied` is a raise; `unsatisfied`, with its reason, is a lowering."""
        with tempfile.TemporaryDirectory() as tmp:
            app = match_workspace(tmp) / "applications" / "contoso"
            gaps = app / "gaps.txt"
            gaps.write_text("dotnet | satisfied | it is on the projects\n", encoding="utf-8")
            args = (JSK, "tailor", "match", app, "--gaps", gaps, "--today", "2026-09-24")
            code, out = run(*args)
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL  gaps.txt line 1: dotnet: satisfied, above the match's "
                          "unevidenced", out)
            self.assertIn("the career needs the tag or the confirmation", out)
            gaps.write_text("dotnet | unsatisfied | the tags are all there is\n",
                            encoding="utf-8")
            code, out = run(*args)
            self.assertEqual(code, 0, out)
            self.assertIn("0 FAIL, 0 WARN - wrote applications/contoso/gaps and gaps.md", out)

    def test_outside_the_layout_is_a_usage_error(self):
        code, out = run(JSK, "tailor", "match", self.FIX / "career")
        self.assertEqual(code, 2, out)
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--cover", "none")
        self.assertEqual(code, 2, out)


class UnloadedWorkspace(unittest.TestCase):
    """Plan P5: a workspace still laid out as files - career/kb.ttl, no career/store/ - is
    refused by every command, with the one fix that imports it."""

    def setUp(self):
        import shutil
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(Path(__file__).parent / "match_fixtures", self.root, dirs_exist_ok=True)

    def jsk(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["jsk", *map(str, args)])
        return code, buf.getvalue()

    def test_a_command_given_a_path_in_it_is_refused_with_kb_load(self):
        for args in (("tailor", "match", self.root / "applications" / "contoso"),
                     ("tailor", "prepare", self.root / "applications" / "contoso"),
                     ("posting", "build", self.root / "applications" / "contoso")):
            with self.subTest(args=args[0]):
                code, out = self.jsk(*args)
                self.assertEqual(code, 1, out)
                self.assertIn("the career is still career/kb.ttl", out)
                self.assertIn("fix:  jsk kb load .", out)

    def test_every_kb_verb_but_load_and_path_is_refused_with_kb_load(self):
        from jsk.graph import kbcli
        for verb in sorted(set(kbcli.VERBS) - {"load", "path"}):
            with self.subTest(verb=verb):
                code, out = self.jsk("kb", verb, "--root", self.root)
                self.assertEqual(code, 1, out)
                self.assertIn("the career is still career/kb.ttl", out)
                self.assertIn("fix:  jsk kb load .", out)
        self.assertFalse((self.root / "career" / "store").exists(), "nothing was imported")

    def test_a_command_run_inside_it_is_refused(self):
        here = os.getcwd()
        try:
            os.chdir(self.root / "applications")
            code, out = self.jsk("resume", "check", "resume.json")
        finally:
            os.chdir(here)
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb load .", out)

    def test_a_loaded_workspace_is_not(self):
        from appkit import seed
        seed(self.root)
        (self.root / "career" / "kb.ttl").write_text("# left by kb load\n", encoding="utf-8")
        code, out = self.jsk("tailor", "match", self.root / "applications" / "contoso")
        self.assertEqual(code, 0, out)

    def test_the_helper_the_kb_verbs_call(self):
        self.assertIsNotNone(cli.unloaded_refusal(str(self.root)))
        self.assertIsNone(cli.unloaded_refusal(None))
        from jsk import paths
        # The shipped example too: whatever reads it imports it first, as doctor does.
        self.assertIsNotNone(cli.unloaded_refusal(paths.EXAMPLE_WORKSPACE))


class DoctorStore(unittest.TestCase):
    """`jsk doctor`'s lines on the record: the store, its revision, the backup's."""

    def setUp(self):
        import shutil
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(Path(__file__).parent / "graph_fixtures", self.root, dirs_exist_ok=True)

    def test_a_store_its_revision_and_its_backup(self):
        from appkit import seed
        seed(self.root)
        lines, broken = cli.store_report(str(self.root))
        text = "\n".join(lines)
        self.assertFalse(broken, text)
        self.assertIn(f"ok    store    {self.root / 'career' / 'store'}", text)
        self.assertRegex(text, r"readable, at r\d+")
        self.assertIn("ok    backup", text)
        revision = re.search(r"readable, at (r\d+)", text).group(1)
        self.assertIn(f"at {revision}\n", text + "\n")

    def test_no_backup_is_a_gap(self):
        from appkit import seed
        seed(self.root)
        (self.root / ".jsk" / "backup.trig").unlink()
        lines, broken = cli.store_report(str(self.root))
        self.assertFalse(broken)
        self.assertIn("no .jsk/backup.trig yet", "\n".join(lines))

    def test_a_workspace_not_yet_loaded_fails_with_kb_load(self):
        lines, broken = cli.store_report(str(self.root))
        self.assertTrue(broken)
        self.assertIn("jsk kb load .", "\n".join(lines))

    def test_doctor_prints_them_after_the_preflight(self):
        from appkit import seed
        seed(self.root)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["jsk", "doctor", "--quick", "--kb", str(self.root)])
        out = buf.getvalue()
        self.assertIn("\nThe record:\n", out)
        self.assertIn("ok    store", out)


class ParseFlags(unittest.TestCase):
    """The one argument parser every hand-written entry point shares."""

    def parse(self, *args, **kinds):
        from jsk.cliutil import parse_flags
        return parse_flags(list(args), kinds.pop("values", ()), **kinds)

    def test_an_unknown_flag_is_refused_by_name(self):
        self.assertEqual(self.parse("x", "--nope"), (None, "unknown flag: --nope"))

    def test_a_value_may_start_with_a_dash(self):
        self.assertEqual(self.parse("--quote", "-40% cost", values=("--quote",)),
                         (([], {"--quote": "-40% cost"}), None))

    def test_a_lone_dash_is_positional_only_where_asked(self):
        """kb apply answers `-` (stdin is refused); jsk gates or ship reading `-` as a
        path would fail further in, on a file that is not there."""
        self.assertEqual(self.parse("-", dash=True), ((["-"], {}), None))
        self.assertEqual(self.parse("-"), (None, "unknown flag: -"))

    def test_a_value_flag_given_twice_is_refused(self):
        """Keeping the last dropped the first without a word: `--answer A --answer B`
        logged B as what the person said."""
        parsed, problem = self.parse("--answer", "A", "--answer", "B", values=("--answer",))
        self.assertIsNone(parsed)
        self.assertEqual((problem, problem.kind, problem.flag),
                         ("--answer given twice - pass it once", "repeated", "--answer"))

    def test_after_a_double_dash_everything_is_positional(self):
        """So `jsk kb query similar -- -40% cost cut` can say what it means."""
        self.assertEqual(self.parse("similar", "--", "-40%", "--json"),
                         ((["similar", "-40%", "--json"], {}), None))

    def test_a_problem_names_its_kind_and_flag(self):
        _, problem = self.parse("--out", values=("--out",))
        self.assertEqual((problem.kind, problem.flag), ("missing", "--out"))

    def test_a_list_runs_to_the_next_flag(self):
        self.assertEqual(self.parse("--select", "a", "b,c", "--out", "f", "d",
                                    values=("--out",), lists=("--select",)),
                         ((["d"], {"--select": ["a", "b,c"], "--out": "f"}), None))
        self.assertEqual(self.parse("--select", lists=("--select",)),
                         (([], {"--select": []}), None))


if __name__ == "__main__":
    unittest.main()
