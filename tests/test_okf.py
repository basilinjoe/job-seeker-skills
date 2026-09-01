"""okf.py is a convenience layer over the nine scripts, and its one job is to be
transparent: the same arguments, the same exit code, and the underlying script's own
output. These tests pin that transparency, because a dispatcher that quietly changes
a verdict is worse than no dispatcher at all.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import (CLI, CLEAN_RESUME, EXAMPLE_URS, INIT_BUNDLE, SCRIPTS,
                      build_pdf, build_text, load_script, resume_with, run,
                      write_concept)

OKF = CLI
EXAMPLE = EXAMPLE_URS
BODY = "Cut order-processing latency 62 percent by decomposing a monolithic service."

SUBCOMMANDS = ["doctor", "new", "validate", "render", "check", "gates", "score", "fit",
               "project"]


class Usage(unittest.TestCase):
    """Called with nothing useful, it must say what it can do - and exit 2, the
    documented code for "you called it wrong"."""

    def test_help_lists_every_subcommand(self):
        code, out = run(OKF, "--help")
        self.assertEqual(code, 2, out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)

    def test_bare_invocation_is_help(self):
        code, out = run(OKF)
        self.assertEqual(code, 2, out)
        self.assertIn("okf check", out)

    def test_unknown_subcommand_names_the_real_ones(self):
        code, out = run(OKF, "frobnicate")
        self.assertEqual(code, 2, out)
        self.assertIn("unknown command: frobnicate", out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)


class ValidateRouting(unittest.TestCase):
    """`okf validate` dispatches on what the target actually is, because a record and
    a bundle are checked by different scripts and people should not have to know
    which."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_json_routes_to_the_record_validator(self):
        code, out = run(OKF, "validate", EXAMPLE, "--level", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)

    def test_flags_are_forwarded_unchanged(self):
        """--strict is the underlying script's flag; the dispatcher must not eat it."""
        code, out = run(OKF, "validate", EXAMPLE, "--strict")
        self.assertIn("checking:", out)
        code2, out2 = run(OKF, "validate", EXAMPLE, "--nonsense-flag")
        self.assertIn("checking:", out2)

    def test_missing_target_is_a_usage_error(self):
        code, out = run(OKF, "validate", self.tmp / "nope.json")
        self.assertEqual(code, 2, out)
        self.assertIn("file not found", out)

    def test_unvalidatable_target_says_what_it_wanted(self):
        stray = self.tmp / "notes.txt"
        stray.write_text("not a record", encoding="utf-8")
        code, out = run(OKF, "validate", stray)
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_validate_with_no_target(self):
        code, out = run(OKF, "validate")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)


class Check(unittest.TestCase):
    """`okf check` runs both document gates on one file. It must run both even when
    the first fails - a document with parse problems can have prose problems too, and
    seeing them in one pass is the whole point."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def document(self, paragraphs=None, name="resume.txt"):
        """The .txt: the one artefact both gates read, so `okf check` can still
        run them in a single pass now that check_ats.py reads the PDF and
        check_prose.py reads the .tex."""
        return build_text(self.tmp / name,
                          CLEAN_RESUME if paragraphs is None else paragraphs)

    def test_clean_resume_passes_both_gates(self):
        code, out = run(OKF, "check", self.document())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to send", out)
        self.assertIn("PASS - prose rules satisfied", out)

    def test_both_gates_are_labelled(self):
        code, out = run(OKF, "check", self.document())
        del code
        self.assertIn("parse gate", out)
        self.assertIn("prose gate", out)

    def test_a_failing_gate_propagates_its_exit_code(self):
        bad = self.document(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = run(OKF, "check", bad)
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)

    def test_the_second_gate_still_runs_after_the_first_fails(self):
        bad = self.document(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = run(OKF, "check", bad)
        del code
        self.assertIn("prose gate", out)

    def test_passing_both_does_not_imply_the_other_two_gates(self):
        """SKILL.md: "passing one says nothing about the others". A clean parse and
        prose result must not read as a finished resume."""
        code, out = run(OKF, "check", self.document())
        del code
        self.assertIn("okf validate", out)
        self.assertIn("PDF", out)

    def test_strict_reaches_the_parse_gate(self):
        code, out = run(OKF, "check", self.document(), "--strict")
        del code
        self.assertIn("--strict", out)

    def test_check_with_no_target(self):
        code, out = run(OKF, "check")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)


class CheckOnly(unittest.TestCase):
    """`--only` runs one document gate by name.

    mode-resume.md calls a single gate when one file has been repaired and only that
    gate needs re-running - "the right thing for re-checking one file after one
    repair". Without this flag those lines had to reach past okf.py to check_ats.py
    and check_prose.py directly, which is exactly the coupling okf.py exists to remove.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def document(self, paragraphs=None, name="resume.txt"):
        return build_text(self.tmp / name,
                          CLEAN_RESUME if paragraphs is None else paragraphs)

    def test_only_prose_does_not_run_the_parse_gate(self):
        code, out = run(OKF, "check", self.document(), "--only", "prose")
        self.assertEqual(code, 0, out)
        self.assertIn("prose gate", out)
        self.assertNotIn("parse gate", out)

    def test_only_parse_does_not_run_the_prose_gate(self):
        code, out = run(OKF, "check", self.document(), "--only", "parse")
        del code
        self.assertIn("parse gate", out)
        self.assertNotIn("prose gate", out)

    def test_only_parse_still_forwards_strict(self):
        code, out = run(OKF, "check", self.document(), "--only", "parse", "--strict")
        del code
        self.assertIn("--strict", out)

    def test_one_gate_passing_never_reads_as_both(self):
        """The load-bearing assertion. `okf check` closes with "Both document gates
        passed", and printing that after running one would be the false green the
        wording exists to prevent."""
        code, out = run(OKF, "check", self.document(), "--only", "prose")
        self.assertEqual(code, 0, out)
        self.assertNotIn("Both document gates passed", out)
        self.assertIn("Three gates did not run", out)
        self.assertIn("the other document gate", out)

    def test_an_unknown_gate_is_refused_by_name(self):
        code, out = run(OKF, "check", self.document(), "--only", "bogus")
        self.assertEqual(code, 2, out)
        self.assertIn("bogus", out)
        self.assertIn("parse, prose", out)

    def test_only_with_no_value_is_refused(self):
        code, out = run(OKF, "check", self.document(), "--only")
        self.assertEqual(code, 2, out)
        self.assertIn("--only needs a value", out)

    def test_the_flag_may_precede_the_file(self):
        """`--only prose resume.txt` has to work: the target is found after the flag
        and its value are removed, not by position in the raw argv."""
        code, out = run(OKF, "check", "--only", "prose", self.document())
        self.assertEqual(code, 0, out)
        self.assertIn("prose gate", out)

    def test_the_help_names_the_flag(self):
        """A flag the skill cannot discover is a flag the skill will not use - the
        mode files read `okf --help` for the surface."""
        code, out = run(OKF, "--help")
        del code
        self.assertIn("--only parse|prose", out)


TEX_PREAMBLE = "\\documentclass{article}\n\\begin{document}\n"


class GatesCase(unittest.TestCase):
    """A bundle and a directory of rendered files, the two things `okf gates` reads."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.bundle = self.tmp / "bundle"
        code, out = run(INIT_BUNDLE, self.bundle, "--name", "Jane Doe")
        self.assertEqual(code, 0, out)
        self.out = self.tmp / "out"
        self.out.mkdir()

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
        return run(OKF, "gates", self.out, "--view", "view_default", *args)


class GatesAgreement(GatesCase):
    """The one test the whole subcommand rests on: same bundle, same files, same
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
            ("jsk_okf.validate_urs", [self.bundle]),
            ("jsk_okf.check_ats", [pdf]),
            ("jsk_okf.check_ats", [txt, "--strict"]),
            ("jsk_okf.check_prose", [tex]),
            ("jsk_okf.check_prose", [txt]),
        ]

    def assertAgrees(self):
        worst, outputs = 0, []
        for script, args in self.five_commands():
            code, out = run(script, *args)
            worst = max(worst, code)
            outputs.append((script, out))
        code, combined = self.gates("--bundle", self.bundle)
        self.assertEqual(code, worst, combined)
        for name, out in outputs:
            self.assertIn(out.strip(), combined,
                          f"{name} said something okf gates did not repeat:\n{out}")
        return combined

    def test_a_clean_render_agrees(self):
        self.render()
        self.assertAgrees()

    def test_a_failing_record_gate_agrees(self):
        """A strength-5 project with nothing to quote fails the record gate and
        nothing else, so this pins that one failing gate does not disturb the four
        that passed."""
        write_concept(self.bundle)
        self.render()
        combined = self.assertAgrees()
        self.assertIn("DO NOT RENDER", combined)

    def test_a_failing_document_gate_agrees(self):
        self.render(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        combined = self.assertAgrees()
        self.assertIn("DO NOT SEND", combined)

    def test_every_gate_still_runs_after_an_earlier_one_fails(self):
        """`okf check`'s rule, applied to five gates instead of two: a document with
        a record defect can have prose defects too, and one pass should show them
        all."""
        write_concept(self.bundle)
        self.render(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = self.gates("--bundle", self.bundle)
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("--- parse gate"), 2, out)
        self.assertEqual(out.count("--- prose gate"), 2, out)


class GatesMissingInput(GatesCase):
    """A gate that did not run is not a gate that passed. Every one of these must
    leave a non-zero exit behind, because SKIPPED printed above an exit 0 is how a
    resume goes out unchecked."""

    def test_no_bundle_skips_the_record_gate_and_fails(self):
        self.render()
        code, out = self.gates()
        self.assertEqual(code, 1, out)
        self.assertIn("SKIPPED", out)
        self.assertIn("A gate that did not run is not a gate that passed.", out)

    def test_an_empty_directory_skips_both_document_gates_and_fails(self):
        code, out = self.gates("--bundle", self.bundle)
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("SKIPPED"), 2, out)
        self.assertIn("--- parse gate", out)
        self.assertIn("--- prose gate", out)

    def test_a_bundle_path_that_is_wrong_is_a_call_error(self):
        """Given-and-wrong is a different mistake from not-given, and reporting the
        two the same way hides one of them."""
        self.render()
        code, out = self.gates("--bundle", self.tmp / "nope")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


class GatesRenderGate(GatesCase):
    """The gate okf gates never runs. A command that exited 0 having quietly left it
    out would be the most dangerous thing in this file."""

    def test_a_clean_run_still_says_the_pdf_is_unread(self):
        self.render()
        code, out = self.gates("--bundle", self.bundle)
        self.assertEqual(code, 0, out)
        self.assertIn("UNVERIFIED", out)
        self.assertIn("read every page", out)

    def test_the_render_gate_is_never_reported_as_passed(self):
        self.render()
        code, out = self.gates("--bundle", self.bundle)
        del code
        render = out.split("--- render gate")[1]
        self.assertNotIn("PASS", render)

    def test_it_says_so_when_there_is_no_pdf_at_all(self):
        self.render()
        (self.out / "Jane_Doe_Resume.pdf").unlink()
        code, out = self.gates("--bundle", self.bundle)
        del code
        self.assertIn("there is no PDF", out)

    def test_the_json_form_carries_the_render_gate_too(self):
        """--json is the form an agent parses, and it is the form most likely to be
        read by machine and reported as a list of passes."""
        self.render()
        code, out = self.gates("--bundle", self.bundle, "--json")
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
        code, out = self.gates("--bundle", self.bundle, "--json")
        del code
        report = json.loads(out)
        record = [g for g in report["gates"] if g["gate"] == "record gate"][0]
        self.assertIn("checking:", record["output"])
        self.assertIn("PASS - safe to render", record["output"])

    def test_the_ats_variant_is_held_to_the_ats_maximal_rules(self):
        """The same rule render_resume.py prints after a render: the file aimed at a
        parser is the one checked with --strict."""
        self.render()
        code, out = self.gates("--bundle", self.bundle)
        del code
        self.assertIn("check_ats.py Jane_Doe_Resume_ATS.txt --strict", out)
        self.assertIn("mode: ATS-maximal (strict)", out)
        self.assertIn("mode: presentation", out)

    def test_max_findings_reaches_the_record_gate(self):
        write_concept(self.bundle)
        self.render()
        code, out = self.gates("--bundle", self.bundle, "--max-findings", "0")
        self.assertEqual(code, 1, out)
        self.assertNotIn("... and", out)


class GatesPageBudget(GatesCase):
    """--pages measures the PDF that exists. Over budget is reported and not failed,
    because fit_pages.py owns that verdict and is the only thing that can act on it -
    render_resume.py's page_report() already says it in those words."""

    def test_it_prints_the_measured_count_against_the_budget(self):
        self.render()
        code, out = self.gates("--bundle", self.bundle, "--pages", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("1 page against a budget of 2", out)

    def test_over_budget_is_reported_and_does_not_change_the_exit_code(self):
        self.render(pages=3)
        code, out = self.gates("--bundle", self.bundle, "--pages", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("OVER BUDGET", out)

    def test_a_budget_with_no_pdf_says_it_was_not_measured(self):
        self.render()
        (self.out / "Jane_Doe_Resume.pdf").unlink()
        code, out = self.gates("--bundle", self.bundle, "--pages", "2")
        del code
        self.assertIn("not measured", out)


class GatesUsage(GatesCase):
    def test_the_view_is_required(self):
        code, out = run(OKF, "gates", self.out)
        self.assertEqual(code, 2, out)
        self.assertIn("--view", out)

    def test_an_out_directory_that_does_not_exist_is_a_call_error(self):
        code, out = run(OKF, "gates", self.tmp / "nowhere", "--view", "view_default")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_an_unknown_flag_is_a_call_error(self):
        code, out = self.gates("--recheck")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)

    def test_a_flag_left_without_its_value_is_a_call_error(self):
        code, out = run(OKF, "gates", self.out, "--view")
        self.assertEqual(code, 2, out)
        self.assertIn("needs a value", out)

    def test_pages_must_be_a_number(self):
        code, out = self.gates("--pages", "two")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


class GatesEntryPoints(unittest.TestCase):
    """okf gates imports the checkers instead of spawning them, so their in-process
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


if __name__ == "__main__":
    unittest.main()
