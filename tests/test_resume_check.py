"""`jsk resume check`, by target kind: a target's selection, a render, a directory. A
resume.json was the record kind until 6.0 read none (docs/superpowers/plans/
2026-10-03-retire-file-pipeline.md, P2): one named is told the target form.

It is a convenience layer over the gates, and its one job is to be transparent: the
same arguments, the same exit code, and the gate's own output. These tests pin that
transparency, because a dispatcher that quietly changes a verdict is worse than no
dispatcher at all.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import careerkit
from fixtures import (CLI, CLEAN_RESUME, example_short, SCRIPTS, build_pdf, build_text, gate,
                      load_script, resume_with, run)
from shipkit import CONTACTED, GraphCase
from shipkit import GOOD as SHIPPABLE


JSK = CLI


# The summary and, in GatesCase, the person's email and phone: the parse gate's strict pass
# reads the plain text this record's plan emits, in memory, and finds a summary heading and
# the contact details there - a fixture .txt can no longer stand in for it.
GOOD = {"resume": 2, "bullets": ["ach_events_latency", "ach_events_team", "ach_identity_sso"],
        "summary": SHIPPABLE["summary"]}


BODY = "Cut order-processing latency 62 percent by decomposing a monolithic service."


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

    def test_a_resume_json_is_told_the_target_form(self):
        code, out = run(JSK, "resume", "check", self.tmp / "nope.json")
        self.assertEqual(code, 2, out)
        self.assertIn("jsk resume check <resume.json> was retired in 6.0", out)
        self.assertIn("fix:  jsk resume check <stem>", out)

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
        self.assertIn("pass --record <stem>", out)

    def test_the_knowledge_base_is_refused_and_says_what_is_checked_instead(self):
        kb = self.tmp / "user-knowledgebase.md"
        kb.write_text("# Career knowledge base", encoding="utf-8")
        code, out = run(JSK, "resume", "check", kb)
        self.assertEqual(code, 2, out)
        self.assertIn("name the target", out)
        # The career is the record `jsk kb check` validates, not a Markdown file.
        self.assertNotIn("jsk migrate", out)
        self.assertIn("jsk kb check", out)

    def test_the_graph_record_is_refused_and_pointed_at_kb_check(self):
        kb = self.tmp / "kb.ttl"
        kb.write_text("k:kb j:format 3 .", encoding="utf-8")
        code, out = run(JSK, "resume", "check", kb)
        self.assertEqual(code, 2, out)
        self.assertIn("jsk kb check", out)
        self.assertIn("name the target", out)

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
        # It named `<record>.json` until 6.0, which reads no resume.json: the record is a
        # target's selection.
        self.assertIn("jsk resume check <stem>", out)
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
        # A selection is in its workspace's store, and the render directory sits in the
        # workspace beside its target, not inside it.
        root, record = careerkit.workspace(self.tmp / "ws", short=GOOD, edits=[CONTACTED])
        self.root, self.record = Path(root), Path(record)
        self.out = Path(root) / "out"
        self.out.mkdir()

    def break_record(self):
        """A record that fails the record gate and nothing else.

        A bullet the career does not hold is the failure worth using: it leaves every
        rendered document untouched, so a test using it pins that one failing gate
        does not disturb the four that passed.
        """
        careerkit.select(self.root, {**GOOD, "bullets": ["ach_nothing_like_it"]})

    def render(self, paragraphs=None, pages=1):
        """The two files render_resume.py leaves behind, without needing a TeX engine: the
        PDF and the .tex. No .txt - the gates emit the plain text from the record's plan
        in memory (Ruling 23 of the graph-native plan).

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
        (self.out / "Jane_Doe_Resume.tex").write_text(
            TEX_PREAMBLE + "\n".join("\\item " + l for l in lines) + "\n\\end{document}\n",
            encoding="utf-8")

    def gates(self, *args):
        return run(JSK, "resume", "check", self.out, *args)


class GatesAgreement(GatesCase):
    """The one test the whole subcommand rests on: same record, same files, same
    verdicts and same exit code as running the commands by hand.

    A faster gate that disagrees with the slow one is worse than no change at all,
    so the comparison is against the checkers' literal output rather than against a
    remembered snapshot of it.
    """

    def commands_by_hand(self):
        # Four now, not five: there is no .txt for the parse and prose gates to read a
        # second time. The parse gate judges the record's plain text in memory, --strict,
        # and holds the PDF to its reading order (Ruling 23 of the graph-native plan).
        pdf = self.out / "Jane_Doe_Resume.pdf"
        tex = self.out / "Jane_Doe_Resume.tex"
        return [
            ("record.py", [self.record]),
            ("check_ats.py", [pdf, "--record", self.record]),
            ("check_ats.py", [self.record, "--strict"]),
            ("check_prose.py", [tex]),
        ]

    def assertAgrees(self):
        worst, outputs = 0, []
        for script, args in self.commands_by_hand():
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
        # The parse gate twice - the PDF, and the plain text in memory - and the prose gate
        # once, over the .tex: there is no .txt for it to read a second time.
        self.assertEqual(out.count("--- parse gate"), 2, out)
        self.assertEqual(out.count("--- prose gate"), 1, out)


class GatesReadingOrder(GatesCase):
    """The parse gate's reading-order rule reads the plain text the record's plan emits, in
    memory. It once read the `_ATS.txt` beside the PDF and skipped itself silently when
    there was none (Ruling 23 of the graph-native plan): with no file to miss, a PDF whose
    bullets extract out of the plan's order fails whenever the record is given."""

    def bullets(self):
        """The plan's own text, its bullets in the order they render."""
        from jsk.adapters.cli.compose.gates import plan_text

        lines = [l for l in plan_text(str(self.record)).split("\n") if l.strip()]
        return lines, [i for i, l in enumerate(lines) if l.strip().startswith("- ")]

    def render_in(self, lines):
        build_pdf(self.out / "Jane_Doe_Resume.pdf", lines)
        (self.out / "Jane_Doe_Resume.tex").write_text(
            TEX_PREAMBLE + "\n".join("\\item " + l for l in lines) + "\n\\end{document}\n",
            encoding="utf-8")

    def test_a_pdf_out_of_the_plans_order_fails_with_no_txt_on_disk(self):
        lines, at = self.bullets()
        self.assertGreater(len(at), 1, lines)
        swapped = list(lines)
        # The first and last bullets traded places: every word on the page, out of order.
        swapped[at[0]], swapped[at[-1]] = lines[at[-1]], lines[at[0]]
        self.render_in(swapped)
        self.assertEqual(list(self.out.glob("*.txt")), [])
        code, out = self.gates("--record", self.record)
        self.assertEqual(code, 1, out)
        pdf_section = out.split("--- parse gate: check_ats.py Jane_Doe_Resume.pdf")[1]
        self.assertRegex(pdf_section.split("--- ")[0],
                         r"FAIL  reading order: \d+ bullet\(s\) extract out of the order they "
                         r"render in")

    def test_the_same_pdf_in_the_plans_order_has_no_reading_order_finding(self):
        """The control: the planted swap above is the only thing that fails it."""
        lines, _ = self.bullets()
        self.render_in(lines)
        _, out = self.gates("--record", self.record)
        self.assertNotIn("reading order", out)


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

    def test_a_target_s_own_directory_needs_no_record_named(self):
        """A target renders into its own directory, so the ordinary call has nothing to
        point at its record with: the directory's target's selection is the record. It was
        a resume.json written beside the render until 6.0."""
        self.out = self.record.parent
        self.out.mkdir(parents=True)
        self.render()
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
        """The same rule render_resume.py prints after a render: the text aimed at a
        parser is the one checked with --strict. It is the plan's plain text, emitted in
        memory, held strict by the run rather than by `_ATS` in a file name."""
        self.render()
        code, out = self.gates("--record", self.record)
        del code
        self.assertIn("check_ats.py resume --strict", out)
        self.assertIn("plain text of resumes/test/resume (in memory)   mode: ATS-maximal "
                      "(strict)", out)
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


class Gates(GraphCase):
    def test_jsk_gates_runs_the_record_gate_and_no_claims_gate(self):
        code, out = self.jsk("resume", "check", self.app)
        heads = [line[4:].split(":")[0] for line in out.splitlines() if line.startswith("--- ")]
        self.assertEqual(heads[0], "record gate", out)
        self.assertNotIn("claims gate", heads)
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
