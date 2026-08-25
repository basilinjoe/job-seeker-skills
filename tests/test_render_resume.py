"""The pipeline: one URS record, many renderings, no divergence between them.

These tests pin the three claims the JSON-first pipeline is built to make:

  * the .docx and the .tex say the same things, because one resolver decided
    what they say and the emitters only chose markup
  * a region profile changes what is emitted, so the same record is lawful in
    Sydney and conventional in Dubai
  * a rendered document still has to pass check_ats.py - generating a file is
    not the same as checking one
"""
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from fixtures import (CHECK_ATS, EXAMPLE_URS, RENDER_RESUME, achievement, run,
                      urs_doc, urs_package, write_urs)

planner = urs_package()


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf8")
    xml = re.sub(r"<w:tab\b[^>]*/?>", "\t", xml)
    xml = re.sub(r"<w:p\b[^>]*>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


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

    def test_docx_latex_and_text_carry_the_same_bullets(self):
        from urs import emit_docx, emit_latex, emit_text  # noqa
        plan = self.plan()
        bullets = plan["sections"][2]["entries"][0]["bullets"]
        tex = emit_latex.emit(plan)
        txt = emit_text.emit(plan)
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "r.docx")
            emit_docx.emit(plan, path)
            docx = docx_text(path)
        for bullet in bullets:
            self.assertIn(bullet, txt)
            self.assertIn(bullet, docx)
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

    def test_presentation_docx_passes_check_ats(self):
        self.render(EXAMPLE_URS, "--view", "view_au_default")
        code, out = run(CHECK_ATS, self.tmp / "Priya_Raman_Resume.docx")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_ats_docx_passes_check_ats_strict(self):
        self.render(EXAMPLE_URS, "--view", "view_au_default")
        code, out = run(CHECK_ATS, self.tmp / "Priya_Raman_Resume_ATS.docx", "--strict")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_all_four_artefacts_come_from_one_record(self):
        self.render(EXAMPLE_URS, "--view", "view_au_default")
        for name in ("Priya_Raman_Resume.tex", "Priya_Raman_Resume.docx",
                     "Priya_Raman_Resume_ATS.docx", "Priya_Raman_Resume_ATS.txt"):
            self.assertTrue((self.tmp / name).exists(), name)

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
        import shutil
        if any(shutil.which(e) for e in ("tectonic", "latexmk", "pdflatex")):
            self.skipTest("a TeX engine is installed, so there is nothing to report")
        out = self.render(EXAMPLE_URS, "--view", "view_au_default", "--pdf")
        self.assertIn("UNVERIFIED", out)


if __name__ == "__main__":
    unittest.main()
