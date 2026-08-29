"""The pipeline: one URS record, many renderings, no divergence between them.

These tests pin the three claims the JSON-first pipeline is built to make:

  * the PDF and the plain text say the same things, because one resolver
    decided what they say and the emitters only chose markup
  * a region profile changes what is emitted, so the same record is lawful in
    Sydney and conventional in Dubai
  * a rendered document still has to pass check_ats.py - generating a file is
    not the same as checking one
"""
import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path

from fixtures import (CHECK_ATS, EXAMPLE_URS, RENDER_RESUME, achievement,
                      load_script, run, urs_doc, urs_module, urs_package,
                      write_urs)

planner = urs_package()
emit_latex = urs_module("urs.emit_latex")
tex = urs_module("urs.tex")


class PlanCase(unittest.TestCase):
    def plan(self, doc=None, **kwargs):
        return planner.build(doc if doc is not None else urs_doc(), **kwargs)

    def flat(self, plan):
        """Every rendered string in the plan, for presence assertions."""
        out = list(plan["header_lines"]) + [plan["name"]]
        for section in plan["sections"]:
            out.append(section.get("heading") or "")
            out.extend(section.get("paragraphs") or [])
            out.extend(section.get("lines") or [])
            for row in section.get("rows") or []:
                out.append(row["label"] + ": " + ", ".join(row["items"]))
            for entry in section.get("entries") or []:
                out.append(entry.get("org_line") or "")
                out.append(entry.get("org_right") or "")
                for role in entry["roles"]:
                    out.append(f"{role['left']} {role.get('right') or ''}")
                out.extend(entry["lines"])
                out.extend(entry["bullets"])
        return "\n".join(o for o in out if o)


class RegionProfilesGate(PlanCase):
    """One record. What a market must not see, it does not see."""

    def test_australia_omits_demographics_entirely(self):
        text = self.flat(self.plan(region="AU"))
        self.assertNotIn("Date of birth", text)
        self.assertNotIn("Marital status", text)
        self.assertNotIn("Nationality", text)

    def test_india_emits_demographics_and_a_declaration(self):
        text = self.flat(self.plan(region="IN"))
        self.assertIn("Date of birth", text)
        self.assertIn("Marital status", text)
        self.assertIn("I hereby declare", text)

    def test_gulf_emits_nationality_because_the_profile_requires_it(self):
        text = self.flat(self.plan(region="AE"))
        self.assertIn("Nationality: Indian", text)

    def test_nationality_renders_as_a_demonym_not_a_country_code(self):
        text = self.flat(self.plan(region="AE"))
        self.assertNotIn("Nationality: IN", text)

    def test_australia_forbids_compensation_where_the_gulf_expects_it(self):
        doc = urs_doc()
        doc["compensation"] = {
            "expected": {"amount": {"value": 240000, "currency": "AUD"},
                         "basis": "total-cash", "period": "year"}}
        self.assertNotIn("240,000", self.flat(self.plan(doc, region="AU")))
        self.assertIn("240,000", self.flat(self.plan(doc, region="AE")))

    def test_a_view_redaction_beats_the_profile(self):
        doc = urs_doc()
        doc["views"][0]["redact"] = ["person.contacts.phone"]
        self.assertNotIn("+61 400 000 000", self.flat(self.plan(doc)))

    def test_missing_required_field_warns_rather_than_passing_quietly(self):
        doc = urs_doc()
        del doc["work_authorization"]
        warnings = " ".join(self.plan(doc, region="AU")["warnings"])
        self.assertIn("work_authorization", warnings)


class SelectionNeverInvention(PlanCase):
    def test_a_view_selects_a_subset_of_bullets(self):
        doc = urs_doc()
        doc["views"][0]["include"] = [
            {"ref": "eng_acme", "achievements": ["ach_latency"]}]
        text = self.flat(self.plan(doc))
        self.assertIn("Cut p95 latency", text)
        self.assertNotIn("Rebuilt the ingestion pipeline", text)

    def test_include_order_is_honoured(self):
        doc = urs_doc()
        doc["views"][0]["include"] = [
            {"ref": "eng_acme", "achievements": ["ach_pipeline", "ach_latency"]}]
        bullets = self.plan(doc)["sections"][2]["entries"][0]["bullets"]
        self.assertTrue(bullets[0].startswith("Rebuilt"), bullets)

    def test_provenance_floor_withholds_unconfirmed_evidence(self):
        doc = urs_doc()
        doc["engagements"][0]["achievements"].append(
            achievement("Drove the platform strategy.", aid="ach_guess",
                        status="inferred"))
        plan = self.plan(doc)
        self.assertNotIn("Drove the platform strategy", self.flat(plan))
        self.assertIn("below the view floor", " ".join(plan["warnings"]))

    def test_lowering_the_floor_lets_inferred_content_through(self):
        doc = urs_doc()
        doc["engagements"][0]["achievements"].append(
            achievement("Drove the platform strategy.", aid="ach_guess",
                        status="inferred"))
        doc["views"][0]["provenance_floor"] = "inferred"
        self.assertIn("Drove the platform strategy", self.flat(self.plan(doc)))


class Chronology(PlanCase):
    def test_current_role_is_listed_first(self):
        roles = self.plan()["sections"][2]["entries"][0]["roles"]
        self.assertEqual(roles[0]["left"], "Principal Engineer")

    def test_a_promotion_is_a_sentence_never_an_arrow_chain(self):
        doc = urs_doc()
        doc["engagements"][0]["positions"].append(
            {"id": "pos_c", "title": "Distinguished Engineer",
             "period": {"start": {"value": "2025-01", "precision": "month"},
                        "state": "unknown"},
             "change": "promotion"})
        text = self.flat(self.plan(doc))
        self.assertIn("Promoted through 3 roles", text)
        self.assertNotIn("→", text)
        # Stated in the direction a promotion actually runs.
        self.assertIn("Senior Engineer, Principal Engineer", text)

    def test_ongoing_periods_read_as_present(self):
        self.assertIn("Present", self.flat(self.plan()))


class FunctionalTitles(PlanCase):
    """A title that is internal-only or niche - "Member of Technical Staff" -
    tells a reader outside that employer nothing, and the reader is spending six
    seconds. The gloss rides beside the official title, never in place of it:
    the official one is what a reference check confirms.
    """

    def gloss(self, functional="Full-Stack Engineer", title="Member of Technical Staff"):
        doc = urs_doc()
        position = doc["engagements"][0]["positions"][0]
        position["title"] = title
        if functional is not None:
            position["functional_title"] = functional
        return doc

    def first_role(self, doc, **kwargs):
        return self.plan(doc, **kwargs)["sections"][2]["entries"][0]["roles"]

    def test_the_presentation_role_line_carries_the_gloss(self):
        roles = self.first_role(self.gloss())
        self.assertIn("Member of Technical Staff (Full-Stack Engineer)",
                      [r["left"] for r in roles])

    def test_the_ats_variant_carries_both_the_gloss_and_the_employer(self):
        roles = self.first_role(self.gloss(), fmt="ats-maximal")
        self.assertIn("Member of Technical Staff (Full-Stack Engineer), Acme Health",
                      [r["left"] for r in roles])

    def test_a_gloss_that_repeats_the_title_is_suppressed(self):
        """Transcribing a bundle fills both often enough, and "Senior Engineer
        (Senior Engineer)" is worse than either alone."""
        roles = self.first_role(self.gloss(functional="senior ENGINEER",
                                           title="Senior Engineer"))
        self.assertIn("Senior Engineer", [r["left"] for r in roles])
        self.assertNotIn("(", self.flat(self.plan(self.gloss(
            functional="senior ENGINEER", title="Senior Engineer"))))

    def test_a_position_without_a_gloss_is_unchanged(self):
        roles = self.first_role(self.gloss(functional=None))
        self.assertEqual([r["left"] for r in roles][-1], "Member of Technical Staff")

    def test_the_promotion_sentence_keeps_bare_titles(self):
        """The sentence exists to defeat the arrow trap; four parentheticals in
        one line defeat the reader instead. Each gloss is on its own role line."""
        doc = self.gloss(title="Member of Technical Staff II")
        doc["engagements"][0]["positions"].append(
            {"id": "pos_c", "title": "Distinguished Engineer",
             "period": {"start": {"value": "2025-01", "precision": "month"},
                        "state": "unknown"},
             "change": "promotion"})
        lines = self.plan(doc)["sections"][2]["entries"][0]["lines"]
        promoted = [l for l in lines if l.startswith("Promoted through")]
        self.assertTrue(promoted, lines)
        self.assertNotIn("(", promoted[0])

    def test_the_gloss_survives_the_ascii_fold(self):
        text = self.flat(self.plan(self.gloss(), fmt="ats-maximal"))
        self.assertIn("(Full-Stack Engineer)", text)


class AtsVariant(PlanCase):
    def test_ats_maximal_names_the_employer_on_every_role_line(self):
        plan = self.plan(fmt="ats-maximal")
        roles = plan["sections"][2]["entries"][0]["roles"]
        for role in roles:
            self.assertIn("Acme Health", role["left"])

    def test_ats_maximal_is_pure_ascii(self):
        text = self.flat(self.plan(fmt="ats-maximal"))
        offenders = sorted({c for c in text if ord(c) > 127})
        self.assertEqual(offenders, [], f"non-ASCII in ATS variant: {offenders}")

    def test_presentation_keeps_one_company_block(self):
        plan = self.plan(fmt="presentation")
        entry = plan["sections"][2]["entries"][0]
        self.assertEqual(entry["org_line"], "Acme Health")
        self.assertNotIn("Acme Health", entry["roles"][0]["left"])

    def test_ats_heading_is_the_word_a_parser_matches_on(self):
        headings = [s["heading"] for s in self.plan(fmt="ats-maximal")["sections"]]
        self.assertIn("Technical Skills", headings)

    def test_ats_variant_includes_skill_aliases_for_keyword_matching(self):
        doc = urs_doc()
        doc["skills"][0]["aliases"] = ["Microsoft Azure"]
        self.assertIn("Microsoft Azure", self.flat(self.plan(doc, fmt="ats-maximal")))


class EmittersDoNotDiverge(PlanCase):
    """The point of the narrow waist: the same bullets in every format."""

    def test_latex_and_text_carry_the_same_bullets(self):
        from urs import emit_latex, emit_text  # noqa
        plan = self.plan()
        bullets = plan["sections"][2]["entries"][0]["bullets"]
        tex = emit_latex.emit(plan)
        txt = emit_text.emit(plan)
        for bullet in bullets:
            self.assertIn(bullet, txt)
            self.assertIn(bullet.replace("%", r"\%"), tex)

    def test_latex_escapes_specials(self):
        from urs import emit_latex
        doc = urs_doc()
        doc["engagements"][0]["achievements"] = [achievement(
            "Raised margin by 30% on R&D spend under $2 budgets.",
            metrics=[{"kind": "ratio", "subject": "margin",
                      "quantity": {"value": 30, "unit": "%"},
                      "confidence": "reported"},
                     {"kind": "absolute", "subject": "budget",
                      "quantity": {"value": 2}, "confidence": "reported"}],
            aid="ach_margin")]
        doc["skills"][0]["evidence"] = ["ach_margin"]
        tex = emit_latex.emit(self.plan(doc))
        self.assertIn(r"30\%", tex)
        self.assertIn(r"R\&D", tex)
        self.assertIn(r"\$2", tex)


class RenderedFilesPassTheGates(unittest.TestCase):
    """A generated file is not a checked file. These run the real checker."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def render(self, source, *args):
        code, out = run(RENDER_RESUME, source, "--out", self.tmp, *args)
        self.assertEqual(code, 0, out)
        return out

    def test_the_plain_text_passes_check_ats_strict(self):
        self.render(EXAMPLE_URS, "--view", "view_au_default")
        code, out = run(CHECK_ATS, self.tmp / "Priya_Raman_Resume_ATS.txt", "--strict")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_one_record_yields_one_deliverable_and_the_paste_in_text(self):
        """Four artefacts became two plus the .tex they come from. The .docx was
        removed because the fitter measured it while the PDF was what shipped."""
        self.render(EXAMPLE_URS, "--view", "view_au_default")
        for name in ("Priya_Raman_Resume.tex", "Priya_Raman_Resume_ATS.txt"):
            self.assertTrue((self.tmp / name).exists(), name)
        self.assertEqual(list(self.tmp.glob("*.docx")), [])

    def test_ats_max_switches_the_variant_rather_than_adding_a_file(self):
        self.render(EXAMPLE_URS, "--view", "view_au_default", "--ats-max")
        self.assertTrue((self.tmp / "Priya_Raman_Resume_ATS.tex").exists())
        self.assertFalse((self.tmp / "Priya_Raman_Resume.tex").exists())

    def test_plain_text_is_ascii_only(self):
        self.render(EXAMPLE_URS, "--view", "view_au_default")
        raw = (self.tmp / "Priya_Raman_Resume_ATS.txt").read_bytes()
        self.assertTrue(all(b < 128 for b in raw))

    def test_a_missing_view_fails_loudly_rather_than_rendering_something_else(self):
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_nonexistent")
        self.assertEqual(code, 1)
        self.assertIn("view_nonexistent", out)

    def test_absent_tex_engine_is_reported_not_assumed(self):
        if tex.available_engine():
            self.skipTest("a TeX engine is installed, so there is nothing to report")
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_au_default", "--pdf")
        self.assertIn("UNVERIFIED", out)
        self.assertEqual(code, 1, out)


class ThePdfIsTheDeliverable(unittest.TestCase):
    """--pdf either produces a PDF or says so in the exit code.

    It used to append the failure to a list of notes and return 0, so a caller
    could ask for a PDF, be told in passing that there wasn't one, and still see
    success. Every gate downstream then reported on a document nobody rendered.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_a_pdf_is_actually_produced(self):
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_au_default", "--pdf")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.tmp / "Priya_Raman_Resume.pdf").exists(), out)

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_a_relative_out_dir_still_produces_a_pdf(self):
        """The reported bug: the engines run with cwd=out_dir, so a relative
        -o resolved against itself and the compile failed silently."""
        here = Path.cwd()
        try:
            os.chdir(self.tmp)
            os.mkdir("rel")
            code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", "rel",
                            "--view", "view_au_default", "--pdf")
            self.assertEqual(code, 0, out)
            self.assertTrue((self.tmp / "rel" / "Priya_Raman_Resume.pdf").exists(), out)
        finally:
            os.chdir(here)

    def test_a_failed_compile_exits_nonzero_and_says_unverified(self):
        module = load_script(RENDER_RESUME)
        module.compile_pdf = lambda tex_path, out_dir: (None, "stub: no PDF")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = module.main(["render_resume.py", str(EXAMPLE_URS),
                                "--out", str(self.tmp), "--view", "view_au_default",
                                "--pdf"])
        self.assertEqual(code, 1, buf.getvalue())
        self.assertIn("UNVERIFIED", buf.getvalue())

    def test_without_pdf_a_missing_engine_is_not_a_failure(self):
        """Rendering the .tex alone is a legitimate thing to ask for."""
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_au_default")
        self.assertEqual(code, 0, out)


class PaperSizeFollowsTheRegion(unittest.TestCase):
    """A4 was hardcoded in the LaTeX preamble while the .docx honoured the
    region, so one record produced a Letter .docx and an A4 PDF."""

    def plan(self, region):
        return planner.build(urs_doc(), region=region)

    def test_us_renders_letterpaper(self):
        self.assertIn("letterpaper", emit_latex.emit(self.plan("US")))

    def test_au_renders_a4paper(self):
        self.assertIn("a4paper", emit_latex.emit(self.plan("AU")))


class TheTemplateCannotEmitAnAtsHazard(PlanCase):
    """What replaced the seven structural checks in check_ats.py.

    Those read a .docx for a table, a text box, an image, a drawing, SmartArt,
    header content and a second column, on every render. None can reach a
    document by accident now, because one template produces every render - so
    the check moved from the output to the generator, which is the only place it
    can be proved rather than sampled. If it moves back, it moves back here.
    """

    HAZARDS = {
        "a table": ("tabular", "longtable"),
        "a text box": ("minipage", "fbox", "parbox"),
        "an image": ("includegraphics", "graphicx"),
        "a drawing, SmartArt or a chart": ("tikz", "pgfplots"),
        "content in a header or footer": ("fancyhdr", "markboth"),
        "a second column": ("multicol", "twocolumn"),
    }

    def rendered(self):
        return [(fmt, emit_latex.emit(self.plan(fmt=fmt)))
                for fmt in ("presentation", "ats-maximal")]

    def test_no_variant_can_express_a_structural_hazard(self):
        for fmt, tex in self.rendered():
            for hazard, markers in self.HAZARDS.items():
                for marker in markers:
                    self.assertNotIn(marker, tex, f"{fmt} emitted {hazard}")

    def test_the_package_list_is_pinned(self):
        """The golden file, narrowed to the part that carries risk. Every hazard
        above needs a package to express it, so pinning the list is what makes
        the class above hold for hazards nobody has thought of yet."""
        for fmt, tex in self.rendered():
            packages = re.findall(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}", tex)
            self.assertEqual(packages, ["fontenc", "inputenc", "geometry", "enumitem"], fmt)

    def test_the_ascii_variant_renders_an_ascii_bullet(self):
        """A PDF bullet is a glyph in the text layer, so U+2022 would fail the
        ATS-maximal variant's own ASCII rule."""
        by_fmt = dict(self.rendered())
        self.assertIn("label={-}", by_fmt["ats-maximal"])
        self.assertIn(r"label=\textbullet", by_fmt["presentation"])

    def test_the_ascii_variant_breaks_ligatures(self):
        """T1 Computer Modern turns "fi" into U+FB01 and "ffi" into U+FB03 - one
        codepoint each in the extracted text, so a parser reading "efficiency"
        gets a word that is not there."""
        doc = urs_doc()
        doc["engagements"][0]["achievements"] = [achievement(
            "Improved efficiency of the affiliate workflow.", "eff-1")]
        tex = emit_latex.emit(self.plan(doc, fmt="ats-maximal"))
        # "ff" and "fi" are both broken, so "efficiency" leaves as ef{}f{}iciency
        # and no ligature pair survives anywhere in the bullet.
        self.assertIn("ef{}f{}iciency", tex)
        self.assertIn("workf{}low", tex)
        self.assertNotIn("efficiency", tex)


class TargetSelection(unittest.TestCase):
    """--profile names a variant, --format names a file kind, and the stem
    follows the variant. It used to follow the format, so an ats-maximal .tex
    was written over the presentation one under the same name."""

    def setUp(self):
        self.select = load_script(RENDER_RESUME).select_targets

    def test_profile_is_not_discarded_under_the_default_format(self):
        rendered = self.select("all", "ats-maximal")
        self.assertEqual([v for v, k, _ in rendered if k == "latex"], ["ats-maximal"])

    def test_the_plain_text_rides_along_whichever_variant_is_chosen(self):
        for profile in (None, "ats-maximal"):
            kinds = {k for _, k, _ in self.select("all", profile)}
            self.assertEqual(kinds, {"latex", "txt"}, profile)

    def test_an_ats_render_cannot_overwrite_the_presentation_one(self):
        ats = self.select("latex", "ats-maximal")[0][2]
        presentation = self.select("latex", None)[0][2]
        self.assertNotEqual(ats, presentation)
        self.assertIn("_ATS", ats)

    def test_no_profile_renders_the_presentation_variant(self):
        rendered = self.select("all", None)
        self.assertEqual(len(rendered), 2)
        self.assertEqual([v for v, k, _ in rendered if k == "latex"], ["presentation"])


if __name__ == "__main__":
    unittest.main()
