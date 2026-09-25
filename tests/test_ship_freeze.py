"""`jsk ship` and `jsk freeze`, the two commands mode-ship.md used to spell out as a
procedure for an agent to follow by hand.

Neither owns a verdict. ship strings together three that already exist - the record
gate, the render, the mechanical gates - and freeze refuses to archive anything they
would not pass. What these tests pin is the order, the stopping, and the one gate
both of them have to say out loud that they did not run.
"""
import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import careerkit
from fixtures import CLI, CLEAN_RESUME, build_pdf, build_text, run

JSK = CLI
BAD = "Scaled the platform to [NUMBER] tenants."
MERIDIAN = ["ach_events_latency", "ach_events_team", "ach_identity_sso"]
# The summary is what the strict parse gate finds a summary heading by.
GOOD = {"resume": 2, "bullets": MERIDIAN,
        "summary": {"text": "Platform engineer with 5 years of Kubernetes, building event "
                            "platforms that other teams build on.", "status": "confirmed"}}
# A bullet the career does not hold: the record gate fails it, and nothing else does.
BROKEN = {"resume": 2, "bullets": ["ach_nothing_like_it"]}
# graphsim S8's d1, as the career's own words: '1 s' is met_latency.v1's number, replaced
# on 2026-03-01 - the record gate fails it as superseded.
# The fixture's person with an email and a phone, which the strict parse gate looks for
# on the plain text; no country, so the default profile's budget of 2 pages holds.
PERSON = 'k:person j:fullName "Test Person" ; j:headline "Platform Engineer" ;'
CONTACTED = (PERSON, PERSON + ' j:email "test.person@example.com" ; j:phone "+61 400 000 000" ;')
D1 = ("Cut p95 event latency from 5 s to 400 ms on AKS with Kafka.",
      "Cut p95 event latency from 5 minutes to under 1 s on EKS with Kafka.")
TEX_PREAMBLE = "\\documentclass{article}\n\\begin{document}\n"


def fake_compile(pages=1, fail=False):
    """A compile_pdf that writes a PDF without a TeX engine.

    The words are CLEAN_RESUME's, which is what the parse gate reads from it; the
    .tex and .txt the renderer really wrote are what the prose gate reads.
    """
    def compile_pdf(tex_path, out_dir):
        from jsk.urs import tex
        if fail:
            return None, "UNVERIFIED - fake produced no PDF"
        pdf = tex.pdf_path_for(tex_path, out_dir)
        build_pdf(pdf, CLEAN_RESUME)
        if pages > 1:
            import pymupdf
            with pymupdf.open(pdf) as doc:
                for _ in range(pages - 1):
                    doc.new_page()
                doc.save(pdf + ".tmp")
            Path(pdf + ".tmp").replace(pdf)
        return pdf, "compiled with fake"
    return compile_pdf


class ShipCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        # A general resume at the workspace root: no posting.ttl beside it, so the render
        # is named for the person alone.
        root, _ = careerkit.workspace(self.tmp / "ws", edits=[CONTACTED])
        self.record = Path(root) / "resume.json"
        self.write(GOOD)
        self.out = self.tmp / "out"

    def write(self, doc):
        self.record.write_text(json.dumps(doc), encoding="utf-8")

    def ship(self, *extra, compile_pdf=None):
        """cli.main() in this interpreter, with the TeX compile faked."""
        from jsk import cli
        from jsk.urs import render_resume
        args = ["jsk", "ship", str(self.record), "--out", str(self.out)]
        buf = io.StringIO()
        with mock.patch.object(render_resume, "compile_pdf",
                               compile_pdf or fake_compile()), \
                contextlib.redirect_stdout(buf):
            code = cli.main(args + [str(a) for a in extra])
        return code, buf.getvalue()

    def headings(self, out):
        return [line[4:].split(":")[0] for line in out.splitlines()
                if line.startswith("--- ")]


class ShipOrder(ShipCase):
    """Record gate, render, mechanical gates - in that order, one process."""

    def test_a_clean_ship_runs_every_step_and_exits_0(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.headings(out),
                         ["record gate", "render", "parse gate", "parse gate",
                          "prose gate", "prose gate", "render gate"], out)

    def test_every_gate_says_its_own_pass(self):
        """There is no claims gate: the record gate reads the career itself, and the
        copy the claims gate joined with the career went with the URS record."""
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertNotIn("claims gate", out)
        self.assertIn("PASS - safe to render", out)
        self.assertIn("PASS - safe to send", out)
        self.assertIn("PASS - prose rules satisfied", out)

    def test_the_record_gate_runs_once(self):
        """Step three is what `jsk gates` runs, less the record gate step one has
        just run on the same file and would have stopped at."""
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("--- record gate"), 1, out)

    def test_each_steps_output_is_verbatim(self):
        """The render's own lines, not a summary of them: the page report included,
        because ship reports the page count and never fails on it."""
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("  pages  Test_Person_Resume.pdf: 1 page against a budget of 2", out)
        self.assertIn("  note   compiled with fake", out)

    def test_flags_reach_the_render(self):
        code, out = self.ship("--ats-max", "--template", "ember")
        self.assertEqual(code, 0, out)
        self.assertIn("--pdf --ats-max --template ember", out)
        self.assertTrue((self.out / "Test_Person_Resume.pdf").exists())
        self.assertIn("template: ember", out)


class ShipGatesOnlyItsOwnRender(ShipCase):
    """A directory keeps every earlier render. `--ats-max` after a default ship left
    both PDFs side by side, and gating the directory failed the second ship on a
    file it never made - then told the person to open that one.

    Both variants now share one name, so the second ship replaces the first; what it
    must get right is holding the replacement to the ATS rules, which it reads from
    the render rather than from a suffix."""

    def test_a_second_ship_gates_what_it_wrote_as_the_variant_it_holds(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("check_ats.py Test_Person_Resume.pdf\n", out)      # not strict
        code, out = self.ship("--ats-max")
        self.assertEqual(code, 0, out)
        self.assertIn("check_ats.py Test_Person_Resume.pdf --strict", out)
        self.assertIn("open Test_Person_Resume.pdf", out)
        self.assertEqual(len(list(self.out.glob("*.pdf"))), 1)


class ShipStops(ShipCase):
    """A step that fails stops the ones after it. A record that fails its gate is
    never rendered: the PDF it would make looks sendable and is not."""

    def test_a_failing_record_renders_nothing(self):
        self.write(BROKEN)
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT RENDER", out)
        self.assertEqual(self.headings(out), ["record gate", "render gate"], out)
        self.assertFalse(self.out.exists() and any(self.out.iterdir()),
                         "a record that failed its gate was rendered")

    def test_a_stale_pdf_is_not_offered_for_reading_after_a_stop(self):
        """render_section() names the PDF in the directory. After a stop that PDF is
        an earlier run's, and telling somebody to read it is telling them to check a
        document this ship never made."""
        self.out.mkdir()
        build_pdf(self.out / "Old_Resume.pdf", CLEAN_RESUME)
        self.write(BROKEN)
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertNotIn("Old_Resume.pdf", out)
        self.assertIn("UNVERIFIED", out)

    def test_a_failed_render_stops_before_the_gates(self):
        code, out = self.ship(compile_pdf=fake_compile(fail=True))
        self.assertEqual(code, 1, out)
        self.assertIn("UNVERIFIED - --pdf was requested and no PDF was produced", out)
        self.assertNotIn("--- parse gate", out)
        self.assertEqual(self.headings(out)[-1], "render gate", out)

    def test_a_failing_document_gate_fails_the_ship(self):
        from jsk.urs import emit_text
        real = emit_text.emit
        with mock.patch.object(emit_text, "emit",
                               lambda rendered: real(rendered) + BAD + "\n"):
            code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)


class ShipRenderGate(ShipCase):
    """The trailer `jsk gates` ends with, and for the same reason."""

    def test_a_clean_ship_still_says_the_pdf_is_unread(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        # The section, not the summary under it - which says PASS for the gates above.
        render = out.split("--- render gate")[1].split("=== summary")[0]
        self.assertIn("UNVERIFIED", render)
        self.assertIn("read every page", render)
        self.assertNotIn("PASS", render)

    def test_over_budget_is_reported_and_never_failed(self):
        """`jsk fit` owns the page verdict. ship names an overrun and exits 0."""
        code, out = self.ship("--pages", "1", compile_pdf=fake_compile(pages=3))
        self.assertEqual(code, 0, out)
        self.assertIn("OVER BUDGET", out)

    def test_the_json_form_carries_every_step_and_the_render_gate(self):
        code, out = self.ship("--json")
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        self.assertEqual(report["exit"], 0)
        gates = [step["gate"] for step in report["steps"]]
        self.assertEqual(gates[:2], ["record gate", "render"])
        self.assertEqual(report["steps"][-1]["status"], "UNVERIFIED")
        self.assertIn("wrote  Test_Person_Resume.pdf", report["steps"][1]["output"])


class ShipSummary(ShipCase):
    """The block the output ends with. The ElevenLabs ship (2026-09-25) was read
    through `tail -60`, which cut the record gate off the top."""

    def summary(self, out):
        self.assertIn("=== summary", out)
        return out.split("=== summary\n")[1].splitlines()

    def step(self, line):
        """The gate a summary line is for: the name before its two-space column."""
        return line.strip().split("  ")[0]

    def test_it_is_last_with_one_line_a_step_and_a_verdict(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        lines = self.summary(out)
        self.assertEqual([self.step(line) for line in lines[:-1]], self.headings(out), out)
        self.assertTrue(lines[-1].startswith("verdict: PASS"), out)
        self.assertTrue(out.rstrip().endswith(lines[-1]), out)

    def test_the_counts_are_the_gates_own(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        lines = self.summary(out)
        sections = out.split("=== summary")[0].split("\n--- ")[1:]
        for section, line in zip(sections, lines):
            counts = re.findall(r"^FAIL (\d+)\s+WARN (\d+)\s*$", section, re.M)
            with self.subTest(step=line):
                if counts:
                    self.assertIn(f"FAIL {counts[-1][0]}   WARN {counts[-1][1]}", line)
        self.assertIn("record gate  PASS   FAIL 0   WARN 0", out)
        self.assertIn("Test_Person_Resume.pdf 1 of 2 pages", lines[1])
        self.assertIn("render gate  UNVERIFIED", out)

    def test_it_counts_the_lines_the_render_withheld_once_each(self):
        """build.py warns once per variant rendered; the line held back is one.
        ach_data_ingestion is j:inferred in the fixture, under the default floor."""
        self.write(dict(GOOD, bullets=MERIDIAN + ["ach_data_ingestion"]))
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertGreater(out.count("withheld bullet ach_data_ingestion"), 1, out)
        [render] = [line for line in self.summary(out) if self.step(line) == "render"]
        self.assertIn("withheld 1 below the view floor", render)

    def test_a_stop_names_the_step_that_failed(self):
        self.write(BROKEN)
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        lines = self.summary(out)
        self.assertEqual(len(lines), 3, out)
        self.assertTrue(lines[0].split()[2] == "FAIL", out)
        self.assertEqual(lines[-1].split(";")[0], "verdict: FAIL - record gate", out)

    def test_jsk_gates_ends_with_it_too(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        code, out = run(JSK, "gates", self.out, "--record", self.record)
        self.assertEqual(code, 0, out)
        lines = self.summary(out)
        self.assertEqual([self.step(line) for line in lines[:-1]], self.headings(out), out)
        self.assertTrue(lines[-1].startswith("verdict: PASS"), out)

    def test_the_json_form_has_no_summary(self):
        code, out = self.ship("--json")
        self.assertEqual(code, 0, out)
        self.assertNotIn("=== summary", out)


class ShipUsage(ShipCase):
    def test_a_view_is_a_usage_error_naming_one_resume(self):
        code, out = self.ship("--view", "view_default")
        self.assertEqual(code, 2, out)
        self.assertIn("a resume.json is one resume", out)
        self.assertNotIn("--- record gate", out)

    def test_the_out_directory_is_required(self):
        code, out = run(JSK, "ship", self.record)
        self.assertEqual(code, 2, out)
        self.assertIn("--out is required", out)

    def test_an_unknown_template_is_a_call_error_before_anything_runs(self):
        code, out = self.ship("--template", "nope")
        self.assertEqual(code, 2, out)
        self.assertNotIn("--- record gate", out)

    def test_an_unknown_flag_is_a_call_error(self):
        code, out = self.ship("--recheck")
        self.assertEqual(code, 2, out)
        self.assertIn("usage: jsk ship", out)

    def test_the_knowledge_base_is_refused_as_validate_refuses_it(self):
        kb = self.tmp / "user-knowledgebase.md"
        kb.write_text("# Career knowledge base", encoding="utf-8")
        code, out = run(JSK, "ship", kb, "--out", self.out)
        self.assertEqual(code, 2, out)
        self.assertIn("pass resume.json", out)

    def test_pages_must_be_a_number(self):
        code, out = self.ship("--pages", "two")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


# --- the graph record: career/kb.ttl ---------------------------------------------------

class GraphCase(unittest.TestCase):
    """graphsim's career (tests/claims_fixtures) with the Contoso application rendered and
    ready to freeze - built without a TeX engine."""

    def setUp(self):
        import shutil

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        shutil.copytree(careerkit.FIXTURES, self.root, dirs_exist_ok=True)
        self.app = self.root / "applications" / "contoso-platform"
        self.render()

    def render(self, lines=None):
        lines = CLEAN_RESUME if lines is None else lines
        build_pdf(self.app / "Jane_Doe_Resume.pdf", lines)
        build_text(self.app / "Jane_Doe_Resume_ATS.txt", lines)
        (self.app / "Jane_Doe_Resume.tex").write_text(
            TEX_PREAMBLE + "\n".join("\\item " + l for l in lines) + "\n\\end{document}\n",
            encoding="utf-8")

    def record(self, doc):
        (self.app / "resume.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def edit_career(self, old, new):
        """kb.ttl changed as `jsk kb apply` would have: log.ttl agrees with it."""
        from jsk.graph import record as R
        from jsk.graph.io import sha256

        kb = self.root / "career" / "kb.ttl"
        text = kb.read_text(encoding="utf-8")
        assert text.count(old) == 1, old
        kb.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        # From this text's hash, not the fixture's: a second edit follows a first.
        log = self.root / R.LOG
        log.write_text(log.read_text(encoding="utf-8").replace(
            sha256(text), sha256(kb.read_text(encoding="utf-8"))),
            encoding="utf-8", newline="\n")

    def jsk(self, *args):
        from jsk import cli

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["jsk", *map(str, args)])
        return code, buf.getvalue()

    def freeze(self, *args, submitted="2026-09-24", channel="Workday portal"):
        return self.jsk("freeze", self.app, "--submitted", submitted, "--channel", channel,
                        *args)

    @property
    def sent(self):
        return self.root / "applications" / "2026-09-24-contoso-platform"

    def application(self, where=None):
        """{predicate: sorted values} of the frozen application, and its events."""
        from jsk.graph import ontology as O
        from jsk.graph.io import parse

        parsed = parse(str((where or self.sent) / "application.ttl"))
        app, events = {}, {}
        for q in parsed.quads:
            name, value = q.predicate.value[len(O.J):], q.object.value
            if O.class_of(q.subject.value) == "Application":
                app.setdefault(name, []).append(value)
            else:
                events.setdefault(q.subject.value[len(O.K):], {})[name] = value
        return {k: sorted(v) for k, v in app.items()}, events

    def store(self):
        from jsk.graph import store as S
        return S.load(self.root)


def k(*ids):
    from jsk.graph import ontology as O
    return sorted(O.K + i for i in ids)


class FreezeGraph(GraphCase):
    def test_it_writes_application_ttl_with_what_it_carried(self):
        import hashlib

        raw = (self.app / "resume.json").read_bytes()
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertFalse((self.sent / "application.md").exists())
        app, events = self.application()
        self.assertEqual(app["posting"], k("post_contoso_platform"))
        self.assertEqual((app["view"], app["submitted"], app["channel"]),
                         (["resume"], ["2026-09-24"], ["Workday portal"]))
        self.assertEqual(app["document"], ["Jane_Doe_Resume.pdf", "Jane_Doe_Resume_ATS.txt"])
        self.assertEqual(app["recordSha256"], [hashlib.sha256(raw).hexdigest()])
        # The inferred ingestion bullet is under the file's floor: it was not sent.
        self.assertEqual(app["carried"], k("ach_events_latency", "ach_events_team",
                                           "ach_identity_sso"))
        self.assertEqual(app["carriedVersion"], k("met_apps.v1", "met_latency.v2", "met_team.v1"))
        self.assertEqual(events["evt_contoso_platform_2026_09_24_submitted"]["kind"],
                         "tag:jsk,2026:ns#submitted")

    def test_what_it_writes_is_canonical_and_the_workspace_validates(self):
        from jsk.graph.writer import write

        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        s = self.store()
        self.assertEqual([f.text() for f in s.fails()], [])
        name = "applications/2026-09-24-contoso-platform/application.ttl"
        self.assertEqual(write(s.graph(name), "application"), s.parsed[name].text)

    def test_the_record_gate_runs_and_its_output_is_shown(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("--- record gate: record.py", out)
        self.assertIn("checking: resume.json   against: career/kb.ttl", out)
        self.assertNotIn("claims gate", out)

    def test_the_career_is_never_touched(self):
        before = [(self.root / "career" / f).read_bytes() for f in ("kb.ttl", "log.ttl")]
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertEqual([(self.root / "career" / f).read_bytes()
                          for f in ("kb.ttl", "log.ttl")], before)
        self.assertIn("jsk event", out)

    def test_held_back_has_no_submitted_event(self):
        code, out = self.freeze(submitted="false")
        self.assertEqual(code, 0, out)
        app, events = self.application(self.app)
        self.assertEqual(app["submitted"], ["false"])
        self.assertEqual(events, {})

    def test_a_record_that_fails_the_record_gate_is_never_frozen(self):
        self.edit_career(*D1)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("number-superseded", out)
        self.assertIn("never frozen", out)
        self.assertTrue(self.app.exists())
        self.assertFalse((self.app / "application.ttl").exists())
        self.assertFalse(self.sent.exists())

    def test_no_posting_ttl_is_refused(self):
        (self.app / "posting.ttl").unlink()
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("no posting.ttl", out)
        self.assertFalse(self.sent.exists())

    def test_a_frozen_application_is_never_refrozen(self):
        code, out = self.freeze(submitted="false")
        self.assertEqual(code, 0, out)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("never re-frozen", out)

    def test_it_says_what_is_true_afterwards(self):
        """It used to end, in a Markdown workspace, with "append the row to log.md" -
        a file nothing writes now. Later events are `jsk event`."""
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("jsk event", out)
        self.assertNotIn("log.md", out)


class FreezeWrites(GraphCase):
    def test_the_directory_is_renamed_to_the_day_it_was_sent(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertFalse(self.app.exists())
        self.assertTrue((self.sent / "posting.ttl").exists())
        self.assertIn(str(self.sent), out)

    def test_a_directory_already_named_for_the_day_stays_where_it_is(self):
        self.app.rename(self.sent)
        self.app = self.sent
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.sent / "application.ttl").exists())
        self.assertNotIn("moved", out)

    def test_a_named_document_is_the_only_one_gated_and_listed(self):
        """The render that was not sent is neither checked nor archived as sent."""
        build_pdf(self.app / "Jane_Doe_Resume_ATS.pdf", CLEAN_RESUME)
        (self.app / "Jane_Doe_Resume_ATS.tex").write_text(
            (self.app / "Jane_Doe_Resume.tex").read_text(encoding="utf-8"), encoding="utf-8")
        code, out = self.freeze("--doc", "Jane_Doe_Resume_ATS.pdf")
        self.assertEqual(code, 0, out)
        self.assertNotIn("check_ats.py Jane_Doe_Resume.pdf", out)
        app, _ = self.application()
        self.assertEqual(app["document"], ["Jane_Doe_Resume_ATS.pdf"])

    def test_the_gates_output_is_shown(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)
        self.assertIn("--- prose gate", out)


class FreezeRefuses(GraphCase):
    """Every refusal leaves the directory exactly as it was: no application.ttl, and
    no rename."""

    def assertUntouched(self):
        self.assertTrue(self.app.exists())
        self.assertFalse((self.app / "application.ttl").exists())
        self.assertFalse(self.sent.exists())

    def test_two_pdfs_and_no_doc_is_a_question_not_a_guess(self):
        """Only the person knows which render was sent; listing both archives one
        nobody submitted as though it was."""
        build_pdf(self.app / "Jane_Doe_Resume_ATS.pdf", CLEAN_RESUME)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("2 PDFs", out)
        self.assertIn("--doc", out)
        self.assertUntouched()

    def test_an_applications_folder_away_from_the_career_is_refused(self):
        """A session once wrote its applications relative to its working directory.
        The been-here-before check looks beside the career, so a round frozen anywhere
        else is one no later round can see."""
        (self.root / "career" / "kb.ttl").unlink()
        code, out = self.freeze()
        self.assertEqual(code, 2, out)
        self.assertIn("no career/kb.ttl beside", out)
        self.assertIn("fix:", out)
        self.assertUntouched()

    def test_an_application_md_is_as_frozen_as_an_application_ttl(self):
        (self.app / "application.md").write_text("original\n", encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("never re-frozen", out)
        self.assertEqual((self.app / "application.md").read_text(encoding="utf-8"),
                         "original\n")
        self.assertUntouched()

    def test_a_failing_document_is_never_frozen(self):
        self.render(CLEAN_RESUME + [BAD])
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)
        self.assertIn("never frozen", out)
        self.assertUntouched()

    def test_a_legacy_record_is_never_frozen_and_is_pointed_at_migrate(self):
        """Nothing but `jsk migrate` reads a full URS record now; an unfrozen one is
        converted once, and a frozen one is the archive and never rendered again."""
        legacy = Path(__file__).parent / "migrate_fixtures" / "contoso-resume.urs.json"
        (self.app / "resume.json").write_bytes(legacy.read_bytes())
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("jsk migrate", out)
        self.assertUntouched()

    def test_a_view_is_a_usage_error_naming_one_resume(self):
        code, out = self.freeze("--view", "view_nope")
        self.assertEqual(code, 2, out)
        self.assertIn("a resume.json is one resume", out)
        self.assertUntouched()

    def test_a_directory_with_nothing_sendable_is_refused(self):
        for name in ("Jane_Doe_Resume.pdf", "Jane_Doe_Resume_ATS.txt"):
            (self.app / name).unlink()
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("no .pdf or .txt", out)
        self.assertUntouched()

    def test_a_rename_target_that_exists_is_refused(self):
        self.sent.mkdir()
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("already exists", out)
        self.assertFalse((self.app / "application.ttl").exists())
        self.assertFalse((self.sent / "application.ttl").exists())

    def test_a_named_document_that_is_not_there_is_refused(self):
        code, out = self.freeze("--doc", "Cover_Letter.pdf")
        self.assertEqual(code, 1, out)
        self.assertIn("Cover_Letter.pdf", out)
        self.assertUntouched()


class FreezeMarkdownWorkspace(GraphCase):
    """Only `jsk migrate` reads a user-knowledgebase.md. freeze wrote an application.md
    for a workspace still on one; it refuses and says to migrate first."""

    def setUp(self):
        super().setUp()
        (self.root / "career" / "kb.ttl").unlink()
        self.markdown = self.root / "user-knowledgebase.md"
        self.markdown.write_text("# KB\n", encoding="utf-8")

    def test_it_is_refused_and_pointed_at_migrate(self):
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn(f"jsk migrate {self.markdown}", out)
        self.assertNotIn("log.md", out)
        self.assertTrue(self.app.exists())
        self.assertFalse(self.sent.exists())
        self.assertEqual(sorted(p.name for p in self.app.iterdir()
                                if p.name.startswith("application")), [])


class FreezeUsage(GraphCase):
    def test_submitted_is_required(self):
        code, out = self.jsk("freeze", self.app, "--channel", "email")
        self.assertEqual(code, 2, out)
        self.assertIn("--submitted is required", out)

    def test_submitted_must_be_a_date_or_false(self):
        for bad in ("yesterday", "2026-9-8", "2026-02-30", "no"):
            with self.subTest(submitted=bad):
                code, out = self.freeze(submitted=bad)
                self.assertEqual(code, 2, out)

    def test_channel_is_required(self):
        code, out = self.jsk("freeze", self.app, "--submitted", "false")
        self.assertEqual(code, 2, out)
        self.assertIn("--channel is required", out)

    def test_a_directory_that_does_not_exist_is_a_call_error(self):
        code, out = run(JSK, "freeze", self.root / "nowhere", "--submitted", "false",
                        "--channel", "email")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


class Stale(GraphCase):
    """graphsim S9: an application sent a metric's number; the number is revised; the
    application is named as having sent the old one."""

    def test_revising_a_carried_metric_makes_the_application_stale(self):
        from test_graph_changeset import PFX

        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        code, out = self.jsk("kb", "query", "stale", "--json", "--root", self.root)
        self.assertEqual((code, json.loads(out)), (0, []))
        change = self.root / "revise.trig"
        change.write_text(PFX + 'op:changeset op:base 1 ; op:summary "Re-measured." .\n'
                          'op:set { k:met_latency.v2 j:value 350 . }\n', encoding="utf-8")
        code, out = self.jsk("kb", "apply", change, "--root", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("the new number is k:met_latency.v3", out)
        code, out = self.jsk("kb", "query", "stale", "--json", "--root", self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out), [{
            "application": "k:app_contoso_platform", "sent": "k:met_latency.v2",
            "replaced": __import__("datetime").date.today().isoformat(),
            "current": "k:met_latency.v3"}])


class ShipGraph(GraphCase):
    def ship(self):
        from jsk.urs import render_resume

        out_dir = self.root / "out"
        with mock.patch.object(render_resume, "compile_pdf", fake_compile()):
            return self.jsk("ship", self.app / "resume.json", "--out", out_dir)

    def setUp(self):
        super().setUp()
        self.edit_career(*CONTACTED)

    def test_a_clean_record_ships_through_the_record_gate(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("--- record gate: record.py", out)
        self.assertIn("PASS - safe to render", out)
        self.assertNotIn("claims gate", out)

    def test_a_replaced_number_stops_at_the_record_gate_and_renders_nothing(self):
        self.edit_career(*D1)
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("number-superseded ach_events_latency", out)
        self.assertIn("the record gate did not pass", out)
        self.assertNotIn("--- render:", out)
        self.assertFalse((self.root / "out").exists())


class Gates(GraphCase):
    def test_jsk_gates_runs_the_record_gate_and_no_claims_gate(self):
        code, out = self.jsk("gates", self.app)
        heads = [line[4:].split(":")[0] for line in out.splitlines() if line.startswith("--- ")]
        self.assertEqual(heads[0], "record gate", out)
        self.assertNotIn("claims gate", heads)
        self.assertEqual(code, 0, out)


class Event(GraphCase):
    def setUp(self):
        super().setUp()
        code, out = self.freeze()
        self.assertEqual(code, 0, out)

    def event(self, *args):
        return self.jsk("event", self.sent, *args)

    def test_an_event_is_appended_and_the_stage_follows_it(self):
        before = (self.sent / "application.ttl").read_text(encoding="utf-8")
        code, out = self.event("screen-scheduled", "--date", "2026-09-26", "--channel", "email",
                               "--due", "2026-09-30", "--note", "Phone screen, 30 min")
        self.assertEqual(code, 0, out)
        self.assertIn("added    k:evt_contoso_platform_2026_09_26_screen_scheduled", out)
        after = (self.sent / "application.ttl").read_text(encoding="utf-8")
        self.assertTrue(after.startswith(before.split("# == Timeline")[0]), after)
        _, events = self.application()
        e = events["evt_contoso_platform_2026_09_26_screen_scheduled"]
        self.assertEqual((e["date"], e["channel"], e["due"], e["note"]),
                         ("2026-09-26", "email", "2026-09-30", "Phone screen, 30 min"))
        code, out = self.jsk("kb", "query", "pipeline", "--json", "--root", self.root)
        self.assertEqual(code, 0, out)
        [row] = json.loads(out)
        self.assertEqual((row["application"], row["stage"], row["since"], row["due"],
                          row["events"]),
                         ("k:app_contoso_platform", "screen-scheduled", "2026-09-26",
                          "2026-09-30", 2))

    def test_the_same_event_twice_is_refused(self):
        """Same kind, day, channel, note and due as one already there: a true duplicate."""
        before = (self.sent / "application.ttl").read_bytes()
        code, out = self.event("submitted", "--date", "2026-09-24", "--channel", "Workday portal")
        self.assertEqual(code, 1, out)
        self.assertIn("already recorded", out)
        self.assertIn("k:evt_contoso_platform_2026_09_24_submitted", out)
        self.assertEqual((self.sent / "application.ttl").read_bytes(), before)

    def test_a_second_event_of_a_kind_on_a_day_gets_the_next_suffix(self):
        """Two notes, two interview rounds, on one day: each is recorded, minted `_2`,
        `_3` as `jsk migrate` mints a timeline's repeats."""
        stem = "evt_contoso_platform_2026_09_26"
        for n, (kind, note, want) in enumerate([
                ("note", "Recruiter called", f"{stem}_note"),
                ("note", "Sent the portfolio link", f"{stem}_note_2"),
                ("note", "Recruiter called back", f"{stem}_note_3"),
                ("interview-done", "Round 1", f"{stem}_interview_done"),
                ("interview-done", "Round 2", f"{stem}_interview_done_2")]):
            with self.subTest(n=n):
                code, out = self.event(kind, "--date", "2026-09-26", "--note", note)
                self.assertEqual(code, 0, out)
                self.assertIn(f"added    k:{want}\n", out)
        _, events = self.application()
        self.assertEqual(events[f"{stem}_note_2"]["note"], "Sent the portfolio link")
        self.assertEqual(events[f"{stem}_interview_done_2"]["note"], "Round 2")
        self.assertEqual([f.text() for f in self.store().fails()], [])

    def test_a_repeat_of_a_suffixed_event_is_refused_too(self):
        for note in ("first", "second"):
            code, out = self.event("note", "--date", "2026-09-26", "--note", note)
            self.assertEqual(code, 0, out)
        code, out = self.event("note", "--date", "2026-09-26", "--note", "second")
        self.assertEqual(code, 1, out)
        self.assertIn("k:evt_contoso_platform_2026_09_26_note_2 is already recorded", out)

    def test_two_events_of_a_kind_with_unknown_dates_are_both_recorded(self):
        for note, want in (("LinkedIn", ""), ("Email", "_2")):
            code, out = self.event("recruiter-contact", "--date", "unknown", "--note", note)
            self.assertEqual(code, 0, out)
            self.assertIn(f"evt_contoso_platform_unknown_recruiter_contact{want}\n", out)

    def test_an_unknown_kind_is_refused_with_the_nearest(self):
        before = (self.sent / "application.ttl").read_bytes()
        code, out = self.event("interview-schedule", "--date", "2026-09-26")
        self.assertEqual(code, 2, out)
        self.assertIn("did you mean 'interview-scheduled'?", out)
        self.assertEqual((self.sent / "application.ttl").read_bytes(), before)

    def test_a_bad_date_is_a_call_error(self):
        for bad in ("26/09/2026", "2026-02-30", "soon"):
            with self.subTest(date=bad):
                code, out = self.event("note", "--date", bad)
                self.assertEqual(code, 2, out)

    def test_an_unknown_date_is_an_event_too(self):
        code, out = self.event("recruiter-contact", "--date", "unknown")
        self.assertEqual(code, 0, out)
        self.assertIn("evt_contoso_platform_unknown_recruiter_contact", out)

    def test_an_event_that_would_not_validate_is_never_written(self):
        """The workspace is loaded with the event in it before the file is replaced. The
        flags are checked first, so reaching this takes an event the command itself got
        wrong - which is what the check is for."""
        from jsk.graph import timeline

        real = timeline.event_quads

        def broken(*args, **kwargs):
            iri, quads = real(*args, **kwargs)
            return iri, quads + [timeline.quad(iri, "due", timeline.lit("soon"))]
        path = self.sent / "application.ttl"
        before = path.read_bytes()
        with mock.patch.object(timeline, "event_quads", broken):
            code, out = self.event("note", "--date", "2026-09-27")
        self.assertEqual(code, 1, out)
        self.assertIn("would leave", out)
        self.assertEqual(path.read_bytes(), before)

    def test_a_hand_formatted_file_is_refused_until_fmt(self):
        path = self.sent / "application.ttl"
        path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8",
                        newline="\n")
        code, out = self.event("note", "--date", "2026-09-27")
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb fmt", out)

    def test_a_directory_outside_applications_is_a_call_error(self):
        code, out = self.jsk("event", self.root / "career", "note", "--date", "2026-09-27")
        self.assertEqual(code, 2, out)
        self.assertIn("not in an applications/ folder", out)

    def test_a_markdown_application_is_pointed_at_its_timeline_table(self):
        md = self.root / "applications" / "old"
        md.mkdir()
        (md / "application.md").write_text("---\n---\n", encoding="utf-8")
        code, out = self.jsk("event", md, "note", "--date", "2026-09-27")
        self.assertEqual(code, 1, out)
        self.assertIn("# Timeline", out)


# --- the short resume.json ---------------------------------------------------------------

class ShortCase(GraphCase):
    """The Contoso application with a short resume.json: ids chosen, the career in kb.ttl.
    ach_data_ingestion is j:inferred in the fixture, under the default floor."""

    SHORT = {"resume": 2, "bullets": ["ach_events_latency", "ach_events_team",
                                      "ach_data_ingestion", "ach_identity_sso"]}

    def setUp(self):
        import careerkit

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root, path = careerkit.workspace(self._tmp.name, short=self.SHORT)
        self.root, self.short = Path(root), Path(path)
        self.app = self.short.parent
        self.render()


class FreezeShort(ShortCase):
    def test_it_carries_only_the_bullets_that_rendered(self):
        import hashlib

        raw = self.short.read_bytes()
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        app, _ = self.application()
        # The inferred ingestion bullet is listed in the file but withheld by the floor:
        # it was never sent, so the application does not claim it was.
        self.assertEqual(app["carried"], k("ach_events_latency", "ach_events_team",
                                           "ach_identity_sso"))
        self.assertEqual(app["carriedVersion"], k("met_apps.v1", "met_latency.v2",
                                                  "met_team.v1"))
        self.assertEqual(app["recordSha256"], [hashlib.sha256(raw).hexdigest()])
        self.assertEqual(app["view"], ["resume"])

    def test_the_workspace_validates_with_it(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertEqual([f.text() for f in self.store().fails()], [])

    def test_view_is_a_call_error(self):
        code, out = self.freeze("--view", "view_contoso")
        self.assertEqual(code, 2, out)
        self.assertIn("drop --view", out)
        self.assertFalse((self.app / "application.ttl").exists())

    def test_a_file_that_does_not_build_is_never_frozen(self):
        self.short.write_text(json.dumps({"resume": 2, "bullets": ["ach_nope"]}),
                              encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("ach_nope", out)
        self.assertFalse((self.app / "application.ttl").exists())
        self.assertFalse(self.sent.exists())


class ShipFrozen(ShortCase):
    """Review Focus 5: a frozen application is what was sent. Re-rendering into it would
    overwrite the PDF the application.ttl says went out."""

    def ship(self, *args):
        from jsk.urs import render_resume

        with mock.patch.object(render_resume, "compile_pdf", fake_compile()):
            return self.jsk("ship", *args)

    def test_it_refuses_to_render_into_a_frozen_directory(self):
        (self.app / "application.ttl").write_text("# frozen\n", encoding="utf-8")
        before = (self.app / "Jane_Doe_Resume.pdf").read_bytes()
        code, out = self.ship(self.short, "--out", self.app)
        self.assertEqual(code, 1, out)
        self.assertIn(f"frozen: {self.app / 'application.ttl'}", out)
        self.assertIn("re-rendering would overwrite what was sent", out)
        self.assertIn("fix:", out)
        self.assertIn("new dated directory", out)
        self.assertNotIn("--- ", out)                       # no step ran
        self.assertEqual((self.app / "Jane_Doe_Resume.pdf").read_bytes(), before)

    def test_it_refuses_a_record_from_a_frozen_directory_rendered_elsewhere(self):
        (self.app / "application.ttl").write_text("# frozen\n", encoding="utf-8")
        out_dir = self.root / "out"
        code, out = self.ship(self.short, "--out", out_dir)
        self.assertEqual(code, 1, out)
        self.assertIn("frozen:", out)
        self.assertFalse(out_dir.exists())

    def test_view_is_a_call_error(self):
        code, out = self.ship(self.short, "--out", self.root / "out", "--view", "view_x")
        self.assertEqual(code, 2, out)
        self.assertIn("drop --view", out)
        self.assertFalse((self.root / "out").exists())

    def test_a_short_file_needs_no_view(self):
        code, out = self.ship(self.short, "--out", self.root / "out")
        self.assertNotIn("--view is required", out)


if __name__ == "__main__":
    unittest.main()
