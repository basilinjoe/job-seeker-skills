"""The render plan, built from the career and a short resume.json.

These are the resolver's tests, carried over: what they pinned about a URS record -
chronology, functional titles, the ATS variant, bullets under their role, the skills
block, the header, the floor - is what the plan must still say when it is built from
kb.ttl. A career is edited the way a person's is, in Turtle; the short file says what
this resume picks.
"""
import tempfile
from pathlib import Path
import unittest

import careerkit
from jsk.resume import build
from jsk.urs import emit_latex, emit_text

PERSON = 'k:person j:fullName "Test Person" ; j:headline "Platform Engineer" ; j:provenance j:confirmed .'
FULL_PERSON = ('k:person j:fullName "Test Person" ; j:headline "Platform Engineer" ;\n'
               '    j:city "Melbourne" ; j:region "VIC" ; j:country "AU" ;\n'
               '    j:email "test.person@example.com" ; j:phone "+61 400 000 000" ;\n'
               '    j:linkedin "linkedin.com/in/test" ; j:github "github.com/test" ;\n'
               '    j:positioning "Engineer who owns platforms end to end." ;\n'
               '    j:provenance j:confirmed .\n\n'
               'k:auth_au j:jurisdiction "AU" ; j:kind j:permanent ; j:authorization j:held ;\n'
               '    j:provenance j:confirmed .\n\n'
               'k:lang_en j:language "en" ; j:native true ; j:provenance j:confirmed .')
LEAD_ENDED = 'j:start "2023-01" ; j:end "2026-06" ; j:state j:ended ;'
LEAD_ONGOING = 'j:start "2023-01" ; j:state j:ongoing ;'
LEAD_TITLE = '    j:title "Lead Engineer" ;\n'

MERIDIAN = ["ach_events_latency", "ach_events_team", "ach_identity_sso"]
EVERYTHING = MERIDIAN + ["ach_data_ingestion", "ach_portal_frontend", "ach_game_players"]


def short(bullets=MERIDIAN, **keys):
    return {"resume": 2, "bullets": list(bullets), **keys}


class BuildCase(unittest.TestCase):
    EDITS = [(PERSON, FULL_PERSON)]

    def plan(self, doc=None, edits=(), **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = careerkit.workspace(tmp, edits=list(self.EDITS) + list(edits),
                                          short=doc or short())
            return build.build(careerkit.store(root), doc or short(), **kwargs)

    def section(self, plan, heading):
        return next((s for s in plan["sections"] if s.get("heading") == heading), None)

    def entries(self, plan):
        return self.section(plan, "Professional Experience")["entries"]

    def entry(self, plan, org):
        return next(e for e in self.entries(plan)
                    if e["org_line"] == org or any(org in r["left"] for r in e["roles"]))

    def flat(self, plan):
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


class Selection(BuildCase):
    def test_only_the_named_bullets_render(self):
        text = self.flat(self.plan(short(["ach_events_latency"])))
        self.assertIn("Cut p95 event latency", text)
        self.assertNotIn("Led a team of 6 engineers.", text)
        self.assertNotIn("Moved 40 applications", text)

    def test_list_order_within_a_role_and_date_order_across_roles(self):
        # Review Focus 4: another project's bullet between two of one project's.
        plan = self.plan(short(["ach_events_team", "ach_identity_sso", "ach_events_latency"]))
        roles = self.entry(plan, "Meridian Health")["roles"]
        self.assertEqual([r["left"] for r in roles], ["Lead Engineer", "Senior Engineer"])
        self.assertEqual(roles[0]["bullets"], ["Led a team of 6 engineers.",
                                               "Cut p95 event latency from 5 s to 400 ms on AKS with Kafka."])
        self.assertEqual(roles[1]["bullets"], ["Moved 40 applications to Entra ID single sign-on."])

    def test_employers_render_latest_first_whatever_the_list_order(self):
        plan = self.plan(short(["ach_game_players", "ach_portal_frontend", "ach_events_latency"]))
        orgs = [e["org_line"] for e in self.entries(plan)]
        self.assertEqual(orgs, ["Meridian Health", "Harbour Systems", "Pixel Games"])

    def test_employers_and_roles_go_by_start_date_newest_first(self):
        """The resolver's order, kept: on the ElevenLabs render an open-source project
        started Feb 2026 and ended Apr 2026 led the section, above the ongoing roles
        that started earlier. Sorting ongoing-first moved it to the foot of the page."""
        ongoing = ('    j:title "Software Engineer" ;\n    j:start "2018-01" ; j:end "2021-05" ; '
                   'j:state j:ended ;\n',
                   '    j:title "Software Engineer" ;\n    j:start "2018-01" ; j:state j:ongoing ;\n')
        plan = self.plan(short(["ach_events_latency", "ach_portal_frontend"]), edits=[ongoing])
        self.assertEqual([e["org_line"] for e in self.entries(plan)],
                         ["Meridian Health", "Harbour Systems"])

    def test_a_role_with_no_bullet_keeps_its_line_and_its_employer_comes_whole(self):
        # A promotion history is never cut in half: both Meridian roles show.
        roles = self.entry(self.plan(short(["ach_events_latency"])), "Meridian Health")["roles"]
        self.assertEqual([r["left"] for r in roles], ["Lead Engineer", "Senior Engineer"])
        self.assertEqual(roles[1]["bullets"], [])

    def test_roles_add_an_employer_with_no_bullet(self):
        plan = self.plan(short(["ach_events_latency"], roles=["pos_pixel_developer"]))
        pixel = self.entry(plan, "Pixel Games")
        self.assertEqual([r["left"] for r in pixel["roles"]], ["Developer"])
        self.assertEqual(pixel["roles"][0]["bullets"], [])

    def test_sent_names_the_rendered_bullets_and_not_the_withheld(self):
        # ach_data_ingestion is j:inferred in claims_fixtures; the floor defaults to confirmed.
        plan = self.plan(short(["ach_events_latency", "ach_data_ingestion"]))
        self.assertEqual(plan["sent"], ["ach_events_latency"])
        self.assertTrue(any("withheld bullet ach_data_ingestion" in w for w in plan["warnings"]))
        self.assertNotIn("FastAPI ingestion", self.flat(plan))

    def test_lowering_the_floor_lets_inferred_content_through(self):
        plan = self.plan(short(["ach_events_latency", "ach_data_ingestion"], floor="inferred"))
        self.assertEqual(plan["sent"], ["ach_events_latency", "ach_data_ingestion"])

    def test_the_kind_of_work_is_said_for_a_contract(self):
        entry = self.entry(self.plan(short(["ach_events_latency"], roles=["pos_lakeside_contractor"])),
                           "Lakeside Data")
        self.assertIn("Contract", entry["lines"])


class Chronology(BuildCase):
    def test_current_role_is_listed_first_and_reads_present(self):
        plan = self.plan(edits=[(LEAD_ENDED, LEAD_ONGOING)])
        roles = self.entry(plan, "Meridian Health")["roles"]
        self.assertEqual(roles[0]["left"], "Lead Engineer")
        self.assertIn("Present", roles[0]["right"])

    def test_a_promotion_is_its_role_lines_never_an_arrow_chain(self):
        text = self.flat(self.plan())
        self.assertNotIn("Promoted through", text)
        self.assertNotIn("→", text)


class FunctionalTitles(BuildCase):
    def gloss(self, functional="Full-Stack Engineer", title="Member of Technical Staff"):
        new = f'    j:title "{title}" ;\n'
        if functional is not None:
            new += f'    j:functionalTitle "{functional}" ;\n'
        return [(LEAD_TITLE, new)]

    def roles(self, edits, **kwargs):
        return [r["left"] for r in self.entry(self.plan(edits=edits, **kwargs),
                                              "Meridian Health" if not kwargs else "Meridian")["roles"]]

    def test_the_presentation_role_line_carries_the_gloss(self):
        self.assertIn("Member of Technical Staff (Full-Stack Engineer)", self.roles(self.gloss()))

    def test_the_ats_variant_carries_both_the_gloss_and_the_employer(self):
        self.assertIn("Member of Technical Staff (Full-Stack Engineer), Meridian Health",
                      self.roles(self.gloss(), fmt="ats-maximal"))

    def test_a_gloss_that_repeats_the_title_is_suppressed(self):
        roles = self.roles(self.gloss(functional="senior ENGINEER", title="Senior Engineer"))
        self.assertEqual(roles[0], "Senior Engineer")


class AtsVariant(BuildCase):
    def test_ats_maximal_names_the_employer_on_every_role_line(self):
        for entry in self.entries(self.plan(fmt="ats-maximal")):
            self.assertIsNone(entry["org_line"])
        roles = [r["left"] for e in self.entries(self.plan(fmt="ats-maximal")) for r in e["roles"]]
        self.assertIn("Lead Engineer, Meridian Health", roles)
        self.assertIn("Senior Engineer, Meridian Health", roles)

    def test_ats_maximal_is_pure_ascii(self):
        text = self.flat(self.plan(fmt="ats-maximal"))
        self.assertEqual(sorted({c for c in text if ord(c) > 127}), [])

    def test_presentation_keeps_one_company_block(self):
        entry = self.entry(self.plan(fmt="presentation"), "Meridian Health")
        self.assertEqual(entry["org_line"], "Meridian Health")
        self.assertNotIn("Meridian Health", entry["roles"][0]["left"])

    def test_the_file_s_format_is_the_default_and_the_argument_wins(self):
        self.assertEqual(self.plan(short(format="ats-maximal"))["format"], "ats-maximal")
        self.assertEqual(self.plan(short(format="ats-maximal"), fmt="presentation")["format"],
                         "presentation")

    def test_ats_heading_is_the_word_a_parser_matches_on(self):
        headings = [s["heading"] for s in self.plan(fmt="ats-maximal")["sections"]]
        self.assertIn("Technical Skills", headings)

    def test_skill_aliases_never_render(self):
        for fmt in ("ats-maximal", "presentation"):
            text = self.flat(self.plan(fmt=fmt))
            self.assertIn("Kubernetes", text)
            self.assertNotIn("K8s", text, fmt)


class Skills(BuildCase):
    TOOLS = ("k:skill_kubernetes j:name \"Kubernetes\" ;",
             "k:skill_kubernetes j:name \"Kubernetes\" ;")

    def rows(self, doc=None, edits=()):
        plan = self.plan(doc, edits=edits)
        section = self.section(plan, "Skills")
        return [(r["label"], r["items"]) for r in section["rows"]], plan

    def test_the_file_s_order_orders_the_rows(self):
        rows, _ = self.rows(short(skills=["skill_kubernetes", "skill_dotnet"]))
        self.assertEqual(rows, [("Platforms", ["Kubernetes"]), ("Languages", [".NET"])])

    def test_only_the_named_skills_render(self):
        rows, _ = self.rows(short(skills=["skill_dotnet"]))
        self.assertEqual(rows, [("Languages", [".NET"])])

    def test_without_a_list_every_skill_renders(self):
        rows, _ = self.rows()
        self.assertEqual(sorted(n for _, items in rows for n in items), [".NET", "Kubernetes"])

    def test_a_row_is_capped_and_the_dropped_names_are_warned(self):
        extra = "".join(f'k:skill_t{n} j:name "Tool{n}" ; j:category "tooling" ; j:rank {n + 1} .\n'
                        for n in range(12))
        edit = ("# == Skills\n\n", "# == Skills\n\n" + extra)
        rows, plan = self.rows(edits=[edit])
        tooling = dict(rows)["Tooling"]
        self.assertEqual(tooling, [f"Tool{n}" for n in range(10)])
        self.assertIn("Tool10, Tool11", " ".join(plan["warnings"]))


class Header(BuildCase):
    def header(self, doc=None, **kwargs):
        return self.plan(doc, **kwargs)["header_lines"]

    def test_work_rights_render_only_where_the_profile_requires_them(self):
        self.assertTrue(any(l.startswith("Work rights") for l in self.header(region="au")))
        for region in ("us", "in", "xx"):
            self.assertFalse(any("Work rights" in l for l in self.header(region=region)), region)

    def test_a_country_code_renders_as_the_country(self):
        self.assertTrue(any(l.startswith("Melbourne, VIC, Australia") for l in self.header()))

    def test_contacts_split_into_direct_then_web_lines(self):
        lines = self.header(region="us", fmt="ats-maximal")
        self.assertEqual(lines[1:], [
            "Melbourne, VIC, Australia | Email: test.person@example.com | Phone: +61 400 000 000",
            "linkedin.com/in/test | github.com/test"])

    def test_the_name_and_headline(self):
        plan = self.plan()
        self.assertEqual(plan["name"], "Test Person")
        self.assertEqual(plan["headline"], "Platform Engineer")


class Summary(BuildCase):
    def paragraphs(self, plan):
        section = self.section(plan, "Professional Summary")
        return section["paragraphs"] if section else None

    def test_the_file_s_summary(self):
        plan = self.plan(short(summary={"text": "Builds event platforms.", "status": "confirmed"}))
        self.assertEqual(self.paragraphs(plan), ["Builds event platforms."])

    def test_absent_it_is_the_career_s_positioning(self):
        self.assertEqual(self.paragraphs(self.plan()), ["Engineer who owns platforms end to end."])

    def test_an_inferred_summary_is_withheld_under_a_confirmed_floor(self):
        plan = self.plan(short(summary={"text": "Builds event platforms.", "status": "inferred"}))
        self.assertIsNone(self.paragraphs(plan))
        self.assertTrue(any("withheld summary" in w for w in plan["warnings"]))


class RegionAndPages(BuildCase):
    def test_india_adds_languages_and_the_declaration(self):
        text = self.flat(self.plan(region="in"))
        self.assertIn("I hereby declare", text)
        self.assertIn("Place: Melbourne", text)
        self.assertIsNotNone(self.section(self.plan(region="in"), "Languages"))
        self.assertIsNone(self.section(self.plan(region="au"), "Languages"))

    def test_the_file_s_region_is_the_default(self):
        self.assertEqual(self.plan(short(region="in"))["profile"], "urs:profile:in/1")

    def test_without_a_region_the_person_s_country_decides(self):
        self.assertEqual(self.plan()["profile"], "urs:profile:au/1")

    def test_pages(self):
        # The file's budget, else the profile's (au and in allow 3), else 2.
        self.assertEqual(self.plan()["pages"], 3)
        self.assertEqual(self.plan(region="xx")["pages"], 2)
        self.assertEqual(self.plan(short(pages=1))["pages"], 1)
        self.assertEqual(self.plan(short(pages=1, ats_pages=3), fmt="ats-maximal")["pages"], 3)
        self.assertEqual(self.plan(short(pages=1), fmt="ats-maximal")["pages"], 1)

    def test_the_explicit_region_decides_the_paper(self):
        self.assertEqual(self.plan(region="us")["region"], "US")
        self.assertIn("letterpaper", emit_latex.emit(self.plan(region="us")))
        self.assertIn("a4paper", emit_latex.emit(self.plan(region="au")))


class EducationAndCredentials(BuildCase):
    GRADED = ('    j:start "2010" ; j:end "2013" ;\n',
              '    j:start "2010" ; j:end "2013" ;\n    j:gradeScheme "in-cgpa-10" ; j:gradeValue 8.4 ;\n')
    CRED = ("# == Certifications\n",
            "# == Certifications\n\nk:cred_cka j:name \"Certified Kubernetes Administrator\" ; "
            "j:issuer \"CNCF\" ; j:issued \"2024-05\" ; j:credentialState j:active ; "
            "j:provenance j:confirmed .\n")

    def test_education_with_its_grade(self):
        plan = self.plan(edits=[self.GRADED])
        entry = self.section(plan, "Education")["entries"][0]
        self.assertEqual(entry["org_line"], "Bachelor of Science, Computer Science")
        self.assertIn("University of Melbourne", entry["lines"][0])
        self.assertIn("8.4", entry["lines"][0])

    def test_credentials(self):
        lines = self.section(self.plan(edits=[self.CRED]), "Certifications")["lines"]
        self.assertEqual(lines, ["Certified Kubernetes Administrator · CNCF · May 2024"])


class EmittersDoNotDiverge(BuildCase):
    def test_latex_and_text_carry_the_same_bullets(self):
        plan = self.plan()
        txt, tex = emit_text.emit(plan), emit_latex.emit(plan)
        for entry in self.entries(plan):
            for role in entry["roles"]:
                for bullet in role["bullets"]:
                    self.assertIn(bullet, txt)

        self.assertIn("Test Person", tex)

    def test_both_emitters_put_each_role_line_above_its_own_bullets(self):
        for fmt in ("presentation", "ats-maximal"):
            plan = self.plan(fmt=fmt)
            for rendered in (emit_text.emit(plan), emit_latex.emit(plan)):
                rendered = rendered[rendered.upper().index("PROFESSIONAL EXPERIENCE"):]
                order = [rendered.index(s) for s in (
                    "Lead Engineer", "Cut p95 event latency", "Senior Engineer",
                    "Moved 40 applications")]
                self.assertEqual(order, sorted(order), fmt)


class RenderCommand(unittest.TestCase):
    """`jsk render <resume.json>` - the short file, built and emitted."""

    def render(self, *args):
        import contextlib
        import io

        from jsk.urs import render_resume
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = render_resume.main(["render_resume.py", *args])
        return code, out.getvalue()

    def test_a_short_file_renders_named_for_the_person_and_the_company(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, path = careerkit.workspace(Path(tmp, "ws"), short=short())
            out = Path(tmp, "out")
            code, text = self.render(path, "--out", str(out))
            self.assertEqual(code, 0, text)
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(names, ["Test_Person_Contoso_Resume.tex",
                                     "Test_Person_Contoso_Resume_ATS.txt"])
            txt = Path(out, "Test_Person_Contoso_Resume_ATS.txt").read_text(encoding="ascii")
            self.assertIn("Moved 40 applications to Entra ID single sign-on.", txt)

    def test_the_plain_text_is_ascii_whatever_the_career_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, path = careerkit.workspace(Path(tmp, "ws"), edits=[
                ('"Led a team of 6 engineers."', '"Led a team of 6 engineers — hiring two."')],
                short=short())
            out = Path(tmp, "out")
            self.render(path, "--out", str(out))
            txt = next(out.glob("*.txt")).read_bytes()
            self.assertTrue(all(b < 128 for b in txt))

    def test_outside_a_workspace_is_a_refusal_with_the_fix(self):
        # Review Focus 1.
        import json
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "resume.json")
            path.write_text(json.dumps(short()), encoding="utf-8")
            code, text = self.render(str(path), "--out", str(Path(tmp, "out")))
            self.assertEqual(code, 2)
            self.assertIn("career/kb.ttl", text)
            self.assertNotIn("Traceback", text)

    def test_view_is_refused_for_a_short_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, path = careerkit.workspace(Path(tmp, "ws"), short=short())
            code, text = self.render(path, "--out", tmp, "--view", "view_x")
            self.assertEqual(code, 2)
            self.assertIn("drop --view", text)

    def test_the_example_renders(self):
        from jsk import paths
        with tempfile.TemporaryDirectory() as tmp:
            code, text = self.render(paths.EXAMPLE_SHORT, "--out", tmp)
            self.assertEqual(code, 0, text)
            self.assertTrue(Path(tmp, "Priya_Raman_Resume.tex").exists())


class FromPath(unittest.TestCase):
    def test_a_file_that_fails_its_checks_does_not_build(self):
        from jsk.resume import short as S
        with tempfile.TemporaryDirectory() as tmp:
            _, path = careerkit.workspace(tmp, short=short(["ach_nothing_like_it"]))
            with self.assertRaises(S.ShortError) as err:
                build.from_path(path)
            self.assertIn("ach_nothing_like_it", str(err.exception))

    def test_a_good_file_builds_with_its_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(tmp, short=short())
            plan, found = build.from_path(path)
            self.assertEqual(found, root)
            self.assertEqual(plan["sent"], MERIDIAN)
