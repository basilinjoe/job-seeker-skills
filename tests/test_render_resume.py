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
                    out.extend(role.get("bullets") or [])
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

    def test_a_promotion_is_its_role_lines_never_an_arrow_chain_or_a_sentence(self):
        """This pinned a "Promoted through 3 roles: ..." sentence. Every role has
        its own dated line now, so on the Experion engagement that sentence only
        repeated the six role lines directly above it; it is gone, and the arrow
        trap it guarded against is still guarded - there is no chain at all."""
        doc = urs_doc()
        doc["engagements"][0]["positions"].append(
            {"id": "pos_c", "title": "Distinguished Engineer",
             "period": {"start": {"value": "2025-01", "precision": "month"},
                        "state": "unknown"},
             "change": "promotion"})
        plan = self.plan(doc)
        text = self.flat(plan)
        self.assertNotIn("Promoted through", text)
        self.assertNotIn("→", text)
        roles = [r["left"] for r in plan["sections"][2]["entries"][0]["roles"]]
        self.assertEqual(sorted(roles), ["Distinguished Engineer", "Principal Engineer",
                                         "Senior Engineer"])

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

    def test_ats_variant_never_renders_skill_aliases(self):
        """This pinned the opposite: the ATS variant expanded aliases for keyword
        matching. The Everforth render then read "C# / .NET, .NET, C#, ...
        dotnet" and "PostgreSQL, Postgres" - a modern ATS matches variants
        itself, and the recruiter reading next sees keyword stuffing."""
        doc = urs_doc()
        doc["skills"][0]["aliases"] = ["Microsoft Azure"]
        for fmt in ("ats-maximal", "presentation"):
            self.assertNotIn("Microsoft Azure", self.flat(self.plan(doc, fmt=fmt)), fmt)


def with_projects(doc, *projects):
    """`doc` with its engagement's own bullets moved into projects.

    Each item is (project id, position id or None, [(achievement id, text)]).
    """
    doc["engagements"][0]["achievements"] = []
    doc["projects"] = []
    for pid, position, bullets in projects:
        project = {"id": pid, "name": pid, "engagement": "eng_acme", "strength": 3,
                   "achievements": [achievement(text, aid=aid) for aid, text in bullets],
                   "provenance": {"status": "confirmed"}}
        if position:
            project["position"] = position
        doc["projects"].append(project)
    doc["engagements"][0]["projects"] = [p[0] for p in projects]
    return doc


class BulletsSitUnderTheirRole(PlanCase):
    """The Experion engagement listed six positions, 2016 to 2025, then every
    project's bullets in one block under them. An ATS credits a bullet to the
    title directly above it, so 2016 work belonged to "Associate Technical
    Architect, Jun 2025 - Present", and no reader could tell which role did what.
    """

    def split_doc(self):
        return with_projects(
            urs_doc(),
            ("prj_new", "pos_b", [("ach_new", "Led the platform rewrite.")]),
            ("prj_old", "pos_a", [("ach_old", "Built the original ingestion service.")]),
            ("prj_loose", None, [("ach_loose", "Mentored four engineers.")]))

    def entry(self, doc, **kwargs):
        return self.plan(doc, **kwargs)["sections"][2]["entries"][0]

    def test_each_role_carries_the_bullets_of_its_projects(self):
        for fmt in ("presentation", "ats-maximal"):
            entry = self.entry(self.split_doc(), fmt=fmt)
            by_role = {r["left"].split(",")[0]: r["bullets"] for r in entry["roles"]}
            self.assertEqual(by_role["Principal Engineer"],
                             ["Led the platform rewrite.", "Mentored four engineers."], fmt)
            self.assertEqual(by_role["Senior Engineer"],
                             ["Built the original ingestion service."], fmt)
            self.assertEqual(entry["bullets"], [], fmt)

    def test_a_bullet_with_no_role_goes_under_the_most_recent_one(self):
        """Engagement-level achievements have no project, so no position."""
        doc = self.split_doc()
        doc["engagements"][0]["achievements"] = [achievement("Ran the on-call rota.",
                                                             aid="ach_rota")]
        roles = self.entry(doc)["roles"]
        self.assertEqual(roles[0]["left"], "Principal Engineer")
        self.assertEqual(roles[0]["bullets"][0], "Ran the on-call rota.")

    def test_a_position_the_engagement_does_not_hold_warns_and_falls_back(self):
        doc = self.split_doc()
        doc["projects"][1]["position"] = "pos_elsewhere"
        plan = self.plan(doc)
        roles = plan["sections"][2]["entries"][0]["roles"]
        self.assertIn("Built the original ingestion service.", roles[0]["bullets"])
        self.assertEqual(roles[1]["bullets"], [])
        self.assertIn("pos_elsewhere", " ".join(plan["warnings"]))

    def test_a_role_with_no_bullets_keeps_its_line(self):
        """The role lines are the promotion history once the sentence is gone."""
        doc = with_projects(urs_doc(), ("prj_new", "pos_b", [("ach_new", "Led it.")]))
        roles = self.entry(doc)["roles"]
        self.assertEqual([r["left"] for r in roles], ["Principal Engineer", "Senior Engineer"])
        self.assertEqual(roles[1]["bullets"], [])

    def test_no_position_anywhere_renders_as_it_always_did(self):
        """A record that predates `position`: every bullet after every role line."""
        from jsk.urs import emit_text
        doc = with_projects(urs_doc(),
                            ("prj_a", None, [("ach_a", "Did the first thing.")]),
                            ("prj_b", None, [("ach_b", "Did the second thing.")]))
        entry = self.entry(doc)
        self.assertEqual(entry["bullets"], ["Did the first thing.", "Did the second thing."])
        self.assertTrue(all(r["bullets"] == [] for r in entry["roles"]))
        txt = emit_text.emit(self.plan(doc))
        self.assertLess(txt.index("Senior Engineer"), txt.index("Did the first thing."))

    def test_both_emitters_put_each_role_line_above_its_own_bullets(self):
        from jsk.urs import emit_latex, emit_text
        for fmt in ("presentation", "ats-maximal"):
            plan = self.plan(self.split_doc(), fmt=fmt)
            for rendered in (emit_text.emit(plan), emit_latex.emit(plan)):
                # From the section heading on: the headline repeats a title.
                rendered = rendered[rendered.upper().index("PROFESSIONAL EXPERIENCE"):]
                order = [rendered.index(s) for s in (
                    "Principal Engineer", "Led the platform rewrite.",
                    "Mentored four engineers.", "Senior Engineer",
                    "Built the original ingestion service.")]
                self.assertEqual(order, sorted(order), fmt)

    def test_presentation_names_the_employer_once_ats_on_every_role(self):
        from jsk.urs import emit_text
        txt = emit_text.emit(self.plan(self.split_doc(), fmt="presentation"))
        self.assertEqual(txt.count("Acme Health"), 1)
        txt = emit_text.emit(self.plan(self.split_doc(), fmt="ats-maximal"))
        self.assertIn("Principal Engineer, Acme Health", txt)
        self.assertIn("Senior Engineer, Acme Health", txt)


class SkillsBlockShowsEachNameOnce(PlanCase):
    """The Everforth ATS render filled 45% of page 1 with its skills block -
    aliases expanded, and LINQ, Entity Framework, Cosmos DB and Azure AI Foundry
    each in two rows - while page 2 was half empty."""

    def skills_doc(self, skills, chosen=None):
        doc = urs_doc()
        doc["skills"] = [{"id": sid, "name": name, "category": cat}
                         for sid, name, cat in skills]
        if chosen is not None:
            doc["views"][0]["skills"] = chosen
        return doc

    def rows(self, doc, **kwargs):
        plan = self.plan(doc, **kwargs)
        return [(r["label"], r["items"]) for r in plan["sections"][1]["rows"]], plan

    def test_a_name_in_two_categories_shows_once_first_wins(self):
        doc = self.skills_doc([("skill_linq", "LINQ", "language"),
                               ("skill_linq2", "linq", "framework"),
                               ("skill_ef", "Entity Framework", "framework")])
        rows, _ = self.rows(doc, fmt="ats-maximal")
        self.assertEqual(rows, [("Language", ["LINQ"]), ("Framework", ["Entity Framework"])])

    def test_a_row_emptied_by_deduplication_is_not_rendered(self):
        doc = self.skills_doc([("skill_a", "Cosmos DB", "database"),
                               ("skill_b", "Cosmos DB", "data")])
        rows, _ = self.rows(doc)
        self.assertEqual([label for label, _ in rows], ["Data"])

    def test_categories_follow_the_view_order_when_it_lists_skills(self):
        """The author ordered the view's skills by relevance to the posting."""
        doc = self.skills_doc([("skill_sql", "SQL", "database"),
                               ("skill_azure", "Azure", "cloud-platform"),
                               ("skill_cs", "C#", "language")],
                              chosen=["skill_cs", "skill_sql", "skill_azure"])
        rows, _ = self.rows(doc)
        self.assertEqual([label for label, _ in rows], ["Language", "Database", "Cloud Platform"])

    def test_without_a_view_list_the_category_order_holds(self):
        doc = self.skills_doc([("skill_sql", "SQL", "database"),
                               ("skill_azure", "Azure", "cloud-platform")])
        rows, _ = self.rows(doc)
        self.assertEqual([label for label, _ in rows], ["Cloud Platform", "Database"])

    def test_a_row_is_capped_and_the_dropped_names_are_warned(self):
        names = [f"Tool{n}" for n in range(12)]
        doc = self.skills_doc([(f"skill_t{n}", name, "tooling") for n, name in enumerate(names)])
        rows, plan = self.rows(doc)
        self.assertEqual(rows[0][1], names[:10])
        warning = " ".join(plan["warnings"])
        self.assertIn("Tool10, Tool11", warning)


class HeaderSaysOnlyWhatTheMarketAsks(PlanCase):
    """"Work rights: IN citizen" and "Kochi, Kerala, IN" on a US application,
    and a contact line that wrapped mid-way in every template."""

    def header(self, doc=None, **kwargs):
        return self.plan(doc, **kwargs)["header_lines"]

    def test_work_rights_render_only_where_the_profile_requires_them(self):
        self.assertTrue(any(l.startswith("Work rights") for l in self.header(region="AU")))
        for region in ("US", "IN", "XX"):
            self.assertFalse(any("Work rights" in l for l in self.header(region=region)), region)

    def test_a_country_code_renders_as_the_country(self):
        doc = urs_doc()
        doc["person"]["location"] = {"city": "Kochi", "region": "Kerala", "country": "IN"}
        line = self.header(doc, region="US")[1]
        self.assertTrue(line.startswith("Kochi, Kerala, India"), line)

    def test_an_unknown_country_renders_as_written(self):
        doc = urs_doc()
        doc["person"]["location"] = {"city": "Reykjavik", "country": "Iceland"}
        self.assertIn("Reykjavik, Iceland", " ".join(self.header(doc)))

    def test_contacts_split_into_direct_then_web_lines(self):
        doc = urs_doc()
        doc["person"]["contacts"] += [{"kind": "linkedin", "value": "linkedin.com/in/test"},
                                      {"kind": "github", "value": "github.com/test"}]
        lines = self.header(doc, region="US", fmt="ats-maximal")
        self.assertEqual(lines[1:], [
            "Melbourne, VIC, Australia | Email: test.person@example.com | "
            "Phone: +61 400 000 000",
            "linkedin.com/in/test | github.com/test"])

    def test_no_web_profile_means_no_second_line(self):
        self.assertEqual(len(self.header(region="US")), 2)


class EmittersDoNotDiverge(PlanCase):
    """The point of the narrow waist: the same bullets in every format."""

    def test_latex_and_text_carry_the_same_bullets(self):
        from jsk.urs import emit_latex, emit_text  # noqa
        plan = self.plan()
        bullets = plan["sections"][2]["entries"][0]["bullets"]
        tex = emit_latex.emit(plan)
        txt = emit_text.emit(plan)
        for bullet in bullets:
            self.assertIn(bullet, txt)
            self.assertIn(bullet.replace("%", r"\%"), tex)

    def test_latex_escapes_specials(self):
        from jsk.urs import emit_latex
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


class ABadValueIsTheRecordsFault(unittest.TestCase):
    """Only "several views and none named" is the caller's to fix. Every other value
    the planner cannot read is the record's - and was reported as a missing --view,
    exit 2, to someone who had passed one."""

    def test_a_malformed_date_names_the_record_not_the_view(self):
        from fixtures import ended

        doc = urs_doc()
        doc["engagements"][0]["positions"][0]["period"] = ended("2021-xx", "2023-06")
        with tempfile.TemporaryDirectory() as root:
            record = write_urs(Path(root), doc)
            code, out = run(RENDER_RESUME, record, "--out", root, "--view", "view_default")
        self.assertEqual(code, 1, out)
        self.assertIn("jsk validate", out)
        self.assertNotIn("--view <id>", out)


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
        """One .tex either way, named for the recruiter - `_ATS` was the name on the
        file they were sent. What it holds is in its own jsk-variant keyword."""
        self.render(EXAMPLE_URS, "--view", "view_au_default", "--ats-max")
        self.assertEqual([p.name for p in self.tmp.glob("*.tex")], ["Priya_Raman_Resume.tex"])
        self.assertIn("jsk-variant:ats-maximal",
                      (self.tmp / "Priya_Raman_Resume.tex").read_text(encoding="utf8"))

    def test_plain_text_is_ascii_only(self):
        self.render(EXAMPLE_URS, "--view", "view_au_default")
        raw = (self.tmp / "Priya_Raman_Resume_ATS.txt").read_bytes()
        self.assertTrue(all(b < 128 for b in raw))

    def test_a_missing_view_fails_loudly_rather_than_rendering_something_else(self):
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_nonexistent")
        self.assertEqual(code, 1)
        self.assertIn("view_nonexistent", out)

    def test_omitting_the_view_where_there_are_several_is_a_usage_error(self):
        """It used to render views[0] - whichever sorted first - and announce it
        exactly as it announces a view that was asked for. With a bundle of live
        targets that is an arbitrary resume, sent under the wrong tailoring."""
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp, "--format", "txt")
        self.assertEqual(code, 2, out)
        self.assertIn("view_au_default", out)
        self.assertIn("--view", out)
        self.assertEqual(list(self.tmp.glob("*.txt")), [])

    def test_one_view_is_unambiguous_and_still_needs_no_flag(self):
        path = write_urs(self.tmp, urs_doc(), "resume.json")
        code, out = run(RENDER_RESUME, path, "--out", self.tmp, "--format", "txt")
        self.assertEqual(code, 0, out)

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


class ThePageCountIsMeasured(unittest.TestCase):
    """The render printed the page *budget* and stopped there.

    So a resume that came out on one page against a budget of two said nothing, and
    one that came out on three said nothing either - and the rule this repo renders
    under is that a page count nobody measured is a page count nobody knows.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.report = load_script(RENDER_RESUME).page_report

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_the_render_reports_the_pages_it_actually_produced(self):
        import pymupdf

        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_au_default", "--pdf")
        self.assertEqual(code, 0, out)
        with pymupdf.open(self.tmp / "Priya_Raman_Resume.pdf") as pdf:
            actual = pdf.page_count
        self.assertIn(f"pages  Priya_Raman_Resume.pdf: {actual} page", out)
        self.assertIn("against a budget of 2", out)

    def test_over_budget_is_named_rather_than_left_to_be_noticed(self):
        self.assertIn("OVER BUDGET", self.report("Resume.pdf", 3, 2))
        self.assertNotIn("OVER BUDGET", self.report("Resume.pdf", 2, 2))
        self.assertNotIn("OVER BUDGET", self.report("Resume.pdf", 1, 2))

    def test_an_unmeasurable_render_says_so_instead_of_reporting_the_budget(self):
        """Reported, not fatal: fit_pages.py exits 2 without pymupdf because
        measuring is its whole job. Here it costs one line of the report."""
        self.assertIn("not measured", self.report("Resume.pdf", None, 2))


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
        """Every variant crossed with every theme.

        Themes multiplied the number of templates that exist by five, so a
        check that ran against "the template" now has to run against all of
        them or it is sampling again - which is exactly what moving the check
        here was meant to stop.
        """
        themes_mod = urs_module("urs.themes")
        return [(f"{fmt}/{name}", emit_latex.emit(self.plan(fmt=fmt), template=name))
                for fmt in ("presentation", "ats-maximal")
                for name in themes_mod.names()]

    def test_no_variant_can_express_a_structural_hazard(self):
        for fmt, tex in self.rendered():
            for hazard, markers in self.HAZARDS.items():
                for marker in markers:
                    self.assertNotIn(marker, tex, f"{fmt} emitted {hazard}")

    # Everything a theme is allowed to load. `xcolor` draws no structure - it
    # sets colour in the graphics state and cannot make a box - and the four
    # typeface packages only select glyphs. Nothing here can express a hazard
    # above, which is what makes pinning the list the real guard: a hazard
    # nobody has thought of still needs a package, and a new package has to be
    # argued for here first.
    #
    # `hyperref` was argued for when the rendered PDFs turned out to carry an
    # empty title and author and no clickable email or profile links. It writes
    # the PDF information dictionary and link annotations - neither is in the
    # text layer, and it draws no structure a parser could trip on (hidelinks:
    # not even the coloured boxes). It is required rather than guarded because
    # it ships in TeX Live's collection-latex beside geometry, and a guard would
    # leave \href undefined in the header. It loads last, after the typefaces,
    # because hyperref has to.
    ALLOWED = {"fontenc", "inputenc", "geometry", "enumitem", "xcolor",
               "lmodern", "tgtermes", "tgpagella", "tgschola", "tgheros",
               "tgadventor", "hyperref"}
    REQUIRED = ["fontenc", "inputenc", "geometry", "enumitem", "xcolor"]
    REQUIRED_LAST = "hyperref"

    def packages(self, tex):
        return re.findall(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}", tex)

    def test_the_package_list_is_pinned(self):
        """The golden file, narrowed to the part that carries risk."""
        for fmt, tex in self.rendered():
            found = self.packages(tex)
            self.assertEqual(found[:len(self.REQUIRED)], self.REQUIRED, fmt)
            self.assertEqual(found[-1], self.REQUIRED_LAST, fmt)
            self.assertEqual(set(found) - self.ALLOWED, set(), fmt)

    def test_every_optional_font_load_is_guarded(self):
        r"""A typeface is worth a package; it is not worth a build failure on
        someone else's machine. Every font package is loaded inside
        \IfFileExists, so a thin TeX distribution substitutes Latin Modern and
        warns instead of stopping - and the four required packages, which every
        distribution has, are loaded plainly so a genuinely broken install
        fails loudly rather than rendering something unrecognisable."""
        for fmt, tex in self.rendered():
            for pkg in self.packages(tex):
                if pkg in self.REQUIRED or pkg == self.REQUIRED_LAST:
                    continue
                self.assertIn(r"\IfFileExists{%s.sty}{\usepackage{%s}}{}" % (pkg, pkg),
                              tex, f"{fmt}: {pkg} loaded unguarded")

    def test_the_ascii_variant_renders_an_ascii_bullet(self):
        """A PDF bullet is a glyph in the text layer, so U+2022 would fail the
        ATS-maximal variant's own ASCII rule. Colouring the marker wraps the
        glyph and does not change it."""
        for fmt, tex in self.rendered():
            expected = "{-}" if fmt.startswith("ats-maximal") else r"\textbullet"
            self.assertIn(r"label=\textcolor{jskbullet}{%s}" % expected, tex, fmt)

    def test_the_ascii_variant_breaks_ligatures(self):
        """T1 Computer Modern turns "fi" into U+FB01 and "ffi" into U+FB03 - one
        codepoint each in the extracted text, so a parser reading "efficiency"
        gets a word that is not there."""
        doc = urs_doc()
        doc["engagements"][0]["achievements"] = [achievement(
            "Improved efficiency of the affiliate workflow.", "eff-1")]
        tex = emit_latex.emit(self.plan(doc, fmt="ats-maximal"))
        # "ff" and "fi" are both broken - by a kern, which survives TeX rebuilding a
        # hyphenated word where an empty group did not - and no pair survives.
        self.assertIn(r"ef\kern0pt{}f\kern0pt{}iciency", tex)
        self.assertIn(r"workf\kern0pt{}low", tex)
        self.assertNotIn("efficiency", tex)

    def test_the_ascii_variant_sets_straight_quotes(self):
        """T1 sets ' as U+2019 and ` as U+2018: "platform's" failed the strict parse
        gate, and the run asked the person to reword a true bullet around it."""
        doc = urs_doc()
        doc["engagements"][0]["achievements"] = [achievement(
            "Authored the platform's `retry` policies.", "q-1")]
        tex = emit_latex.emit(self.plan(doc, fmt="ats-maximal"))
        self.assertIn(r"platform\textquotesingle{}s", tex)
        self.assertIn(r"\textasciigrave{}retry\textasciigrave{}", tex)
        self.assertIn("platform's", emit_latex.emit(self.plan(doc, fmt="presentation")))


class TheDateColumnHolds(unittest.TestCase):
    r"""A two-column line without a two-column layout, and the case that breaks
    it is a long left side - which functional_title makes common.

    Three renderings of `#1 <gap> #2` were tried and two were wrong: plain
    \hfill splits the date across lines ("...Engineer)Aug 2016" / "- Feb 2019"),
    \mbox alone runs past the right margin. Both pass every checker, because a
    checker reads extracted text and neither defect is in the text.
    """

    LONG = "Member of Technical Staff, Distinguished Grade IV"
    GLOSS = "Principal Full-Stack Platform Engineer"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def long_titled_doc(self):
        doc = urs_doc()
        position = doc["engagements"][0]["positions"][0]
        position["title"] = self.LONG
        position["functional_title"] = self.GLOSS
        return doc

    def test_the_template_carries_both_guards(self):
        """Either one alone produces a defect, so neither may be dropped - in
        any theme. Four of the five also set \\raggedright, which sets the same
        \\rightskip globally; the \\hfill that pushes the date right is `fill`,
        an infinity order above `fil`, so it still wins and the guard is
        unaffected either way."""
        themes_mod = urs_module("urs.themes")
        for name in themes_mod.names():
            rendered = emit_latex.emit(planner.build(self.long_titled_doc()),
                                       template=name)
            self.assertIn(r"\rightskip=0pt plus 1fil", rendered, name)
            self.assertIn(r"\mbox{{\color{jskdate}#2}}", rendered, name)

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_a_long_role_line_stays_inside_the_right_margin(self):
        import pymupdf

        path = write_urs(self.tmp, self.long_titled_doc(), "long.json")
        code, out = run(RENDER_RESUME, path, "--out", self.tmp,
                        "--view", "view_default", "--pdf")
        self.assertEqual(code, 0, out)
        pdf = next(self.tmp.glob("*.pdf"))
        with pymupdf.open(pdf) as doc:
            for page in doc:
                limit = page.rect.width - 0.5 * 72      # inside the tightest margin
                spilled = [b[4].strip()[:60] for b in page.get_text("blocks")
                           if b[2] > limit]
                self.assertEqual(spilled, [], "text past the right margin")

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_a_long_role_line_does_not_split_its_date(self):
        import pymupdf

        path = write_urs(self.tmp, self.long_titled_doc(), "long.json")
        run(RENDER_RESUME, path, "--out", self.tmp, "--view", "view_default", "--pdf")
        pdf = next(self.tmp.glob("*.pdf"))
        with pymupdf.open(pdf) as doc:
            text = "".join(page.get_text() for page in doc)
        # The date on the long line specifically - the fixture gives that
        # position Feb 2021 - Jun 2023, and no other element carries it.
        # Under a bare \hfill it extracts as "...Engineer)Feb 2021" on one line
        # and "- Jun 2023" on the next, so the contiguous run is what fails.
        self.assertIn("Feb 2021 - Jun 2023", text)


class NoTemplateHyphenates(PlanCase):
    r"""monolith justified and hyphenated, and the Everforth render's text layer
    held "Mi-\ncroservices" - a search for "Microservices" missed the default
    template's own PDF. Every theme in both variants now turns it off; the
    compiled proof is check_ats.py's split-word rule, tested in test_check_ats."""

    def test_every_theme_and_variant_turns_hyphenation_off_and_sets_ragged_right(self):
        themes_mod = urs_module("urs.themes")
        for fmt in ("presentation", "ats-maximal"):
            for name in themes_mod.names():
                rendered = emit_latex.emit(self.plan(fmt=fmt), template=name)
                body = rendered.split(r"\begin{document}")
                for line in (r"\hyphenpenalty=10000", r"\exhyphenpenalty=10000"):
                    self.assertIn(line, body[0], f"{fmt}/{name}")
                self.assertIn("\n\\raggedright\n", body[1], f"{fmt}/{name}")


class TheHeaderLinksAndTheMetadata(PlanCase):
    """The PDFs carried an empty title and author and no clickable links. A link
    is an annotation, never text, so adding one must not move a character."""

    def doc_with_profiles(self):
        doc = urs_doc()
        doc["person"]["contacts"] += [
            {"kind": "linkedin", "value": "linkedin.com/in/test-person"},
            {"kind": "github", "value": "github.com/testperson"},
            {"kind": "website", "value": "https://testperson.dev"},
        ]
        return doc

    def test_the_metadata_names_the_person_and_the_variant(self):
        for fmt in ("presentation", "ats-maximal"):
            tex = emit_latex.emit(self.plan(fmt=fmt))
            self.assertIn(r"\hypersetup{hidelinks,pdftitle={Test Person - Resume},"
                          r"pdfauthor={Test Person},pdfkeywords={jsk-variant:%s}}" % fmt,
                          tex, fmt)

    def test_email_and_web_contacts_are_linked(self):
        for fmt in ("presentation", "ats-maximal"):
            tex = emit_latex.emit(self.plan(self.doc_with_profiles(), fmt=fmt))
            for link in (r"\href{mailto:test.person@example.com}{test.person@example.com}",
                         r"\href{https://linkedin.com/in/test-person}{linkedin.com/in/test-person}",
                         r"\href{https://github.com/testperson}{github.com/testperson}",
                         r"\href{https://testperson.dev}{https://testperson.dev}"):
                self.assertIn(link, tex, fmt)
            self.assertNotIn(r"\href{https://+61", tex)

    def test_a_link_does_not_change_the_visible_text(self):
        link = emit_latex.link_contacts
        line = r"Sydney, NSW \textperiodcentered{} a.b@example.com \textperiodcentered{} +61 400 000 000"
        linked = link(line)
        self.assertEqual(re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", linked), line)
        self.assertIn(r"\href{mailto:a.b@example.com}{a.b@example.com}", linked)

    def test_trailing_punctuation_stays_outside_the_link(self):
        self.assertEqual(emit_latex.link_contacts("github.com/x,"),
                         r"\href{https://github.com/x}{github.com/x},")

    def test_a_token_that_needed_escaping_is_left_alone(self):
        r"""`\_` in the URL argument of an \href nested in \resumecontact reaches
        the link as the escape, not the character - a broken link is worse than
        plain text, so the token stays plain."""
        line = emit_latex.esc("first_last@example.com | github.com/first_last")
        self.assertEqual(emit_latex.link_contacts(line), line)

    def test_a_ligature_break_is_not_part_of_the_address(self):
        line = emit_latex.esc("github.com/fiona", ascii_safe=True)
        self.assertIn(r"\kern0pt", line)
        self.assertEqual(emit_latex.link_contacts(line),
                         r"\href{https://github.com/fiona}{%s}" % line)

    def test_words_that_are_not_addresses_are_not_linked(self):
        for text in ("Work rights: AU citizen", "Kochi, Kerala, India", "Phone: +91 95676 61005",
                     "v3.5", "Email:"):
            self.assertEqual(emit_latex.link_contacts(emit_latex.esc(text)),
                             emit_latex.esc(text), text)

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_the_compiled_pdf_carries_metadata_and_links(self):
        import pymupdf

        with tempfile.TemporaryDirectory() as root:
            path = write_urs(Path(root), self.doc_with_profiles(), "resume.json")
            code, out = run(RENDER_RESUME, path, "--out", root, "--pdf")
            self.assertEqual(code, 0, out)
            with pymupdf.open(next(Path(root).glob("*.pdf"))) as pdf:
                meta = pdf.metadata
                uris = sorted(l.get("uri") for page in pdf for l in page.get_links())
                text = "".join(page.get_text() for page in pdf)
        self.assertEqual(meta["title"], "Test Person - Resume")
        self.assertEqual(meta["author"], "Test Person")
        self.assertEqual(meta["keywords"], "jsk-variant:presentation")
        self.assertEqual(uris, ["https://github.com/testperson",
                                "https://linkedin.com/in/test-person",
                                "https://testperson.dev",
                                "mailto:test.person@example.com"])
        self.assertIn("linkedin.com/in/test-person", text)
        self.assertNotIn("mailto", text)


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

    def test_the_pdf_is_named_for_its_reader_and_the_text_for_its_box(self):
        """The two variants were kept apart by an `_ATS` suffix, and that suffix was on
        the file a recruiter received. A directory holds one PDF - freeze refuses two,
        and --ats-max switches the variant rather than adding one - so both share the
        stem, and the gates read which variant from the render itself. The .txt keeps
        its suffix: it is pasted, never attached."""
        ats = self.select("latex", "ats-maximal")[0][2]
        presentation = self.select("latex", None)[0][2]
        self.assertEqual(ats, presentation)
        self.assertNotIn("_ATS", ats)
        text = [stem for _, kind, stem in self.select("all", "ats-maximal") if kind == "txt"]
        self.assertEqual(text, ["{name}_Resume_ATS"])

    def test_no_profile_renders_the_presentation_variant(self):
        rendered = self.select("all", None)
        self.assertEqual(len(rendered), 2)
        self.assertEqual([v for v, k, _ in rendered if k == "latex"], ["presentation"])


if __name__ == "__main__":
    unittest.main()
