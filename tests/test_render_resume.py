"""The render: one plan, many renderings, no divergence between them.

These tests pin the claims the pipeline is built to make:

  * the PDF and the plain text say the same things, because the builder decided
    what they say and the emitters only chose markup
  * the template cannot express an ATS hazard, in any theme or variant
  * a rendered document still has to pass check_ats.py - generating a file is
    not the same as checking one

What the plan says - selection, chronology, titles, the skills block, the header,
the region's sections - is tests/test_build.py's. The plans here are built from the
career the same way: tests/claims_fixtures edited in Turtle (tests/careerkit.py),
or the shipped example workspace.
"""
import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path

import careerkit
from fixtures import CHECK_ATS, RENDER_RESUME, load_script, run, urs_module
from jsk import paths
from jsk.resume import build
from test_build import LEAD_TITLE, BuildCase, short

emit_latex = urs_module("urs.emit_latex")
tex = urs_module("urs.tex")

EXAMPLE = paths.EXAMPLE_SHORT
TEAM = '"Led a team of 6 engineers."'


def reworded(text):
    """ach_events_team's words replaced - an edit for BuildCase.plan(edits=...)."""
    return [(TEAM, f'"{text}"')]


class PlanCase(BuildCase):
    """A plan over claims_fixtures with test_build's full person (Test Person, Melbourne)."""


class SkillsShowEachNameOnce(PlanCase):
    """The Everforth ATS render filled 45% of page 1 with its skills block - LINQ,
    Entity Framework, Cosmos DB and Azure AI Foundry each in two rows - while page 2
    was half empty."""

    def rows(self, skills, chosen, **kwargs):
        extra = "".join(f'k:{sid} j:name "{name}" ; j:category "{cat}" ; j:rank {n + 1} .\n'
                        for n, (sid, name, cat) in enumerate(skills))
        plan = self.plan(short(skills=chosen), edits=[("# == Skills\n\n",
                                                       "# == Skills\n\n" + extra)], **kwargs)
        section = self.section(plan, "Technical Skills") or self.section(plan, "Skills")
        return [(r["label"], r["items"]) for r in section["rows"]]

    def test_a_name_in_two_categories_shows_once_first_wins(self):
        rows = self.rows([("skill_linq", "LINQ", "language"),
                          ("skill_linq2", "linq", "framework"),
                          ("skill_ef", "Entity Framework", "framework")],
                         ["skill_linq", "skill_linq2", "skill_ef"], fmt="ats-maximal")
        self.assertEqual(rows, [("Language", ["LINQ"]), ("Framework", ["Entity Framework"])])

    def test_a_row_emptied_by_deduplication_is_not_rendered(self):
        rows = self.rows([("skill_a", "Cosmos DB", "database"),
                          ("skill_b", "Cosmos DB", "data")], ["skill_b", "skill_a"])
        self.assertEqual([label for label, _ in rows], ["Data"])


class HeaderEdges(PlanCase):
    """What test_build's Header does not already pin."""

    def test_an_unknown_country_renders_as_written(self):
        plan = self.plan(edits=[('j:city "Melbourne" ; j:region "VIC" ; j:country "AU" ;',
                                 'j:city "Reykjavik" ; j:country "Iceland" ;')])
        self.assertIn("Reykjavik, Iceland", " ".join(plan["header_lines"]))

    def test_no_web_profile_means_no_second_line(self):
        plan = self.plan(edits=[('    j:linkedin "linkedin.com/in/test" ; '
                                 'j:github "github.com/test" ;\n', '')], region="us")
        self.assertEqual(len(plan["header_lines"]), 2)


class LatexEscapes(PlanCase):
    def test_latex_escapes_specials(self):
        rendered = emit_latex.emit(self.plan(
            edits=reworded("Raised margin by 30% on R&D spend under $2 budgets.")))
        self.assertIn(r"30\%", rendered)
        self.assertIn(r"R\&D", rendered)
        self.assertIn(r"\$2", rendered)


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
        self.render(EXAMPLE)
        code, out = run(CHECK_ATS, self.tmp / "Priya_Raman_Resume_ATS.txt", "--strict")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_one_record_yields_one_deliverable_and_the_paste_in_text(self):
        """Four artefacts became two plus the .tex they come from. The .docx was
        removed because the fitter measured it while the PDF was what shipped."""
        self.render(EXAMPLE)
        for name in ("Priya_Raman_Resume.tex", "Priya_Raman_Resume_ATS.txt"):
            self.assertTrue((self.tmp / name).exists(), name)
        self.assertEqual(list(self.tmp.glob("*.docx")), [])

    def test_ats_max_switches_the_variant_rather_than_adding_a_file(self):
        """One .tex either way, named for the recruiter - `_ATS` was the name on the
        file they were sent. What it holds is in its own jsk-variant keyword."""
        self.render(EXAMPLE, "--ats-max")
        self.assertEqual([p.name for p in self.tmp.glob("*.tex")], ["Priya_Raman_Resume.tex"])
        self.assertIn("jsk-variant:ats-maximal",
                      (self.tmp / "Priya_Raman_Resume.tex").read_text(encoding="utf8"))

    def test_plain_text_is_ascii_only(self):
        self.render(EXAMPLE)
        raw = (self.tmp / "Priya_Raman_Resume_ATS.txt").read_bytes()
        self.assertTrue(all(b < 128 for b in raw))

    def test_a_view_is_a_usage_error_naming_one_resume(self):
        """A resume.json is one resume: --view chose among a full record's views, and
        went with the record."""
        code, out = run(RENDER_RESUME, EXAMPLE, "--out", self.tmp, "--view", "view_x")
        self.assertEqual(code, 2, out)
        self.assertIn("a resume.json is one resume", out)
        self.assertEqual(list(self.tmp.glob("*")), [])

    def test_a_legacy_record_is_refused_with_migrate_as_the_fix(self):
        root, path = careerkit.workspace(self.tmp / "ws")
        legacy = Path(__file__).parent / "migrate_fixtures" / "contoso-resume.urs.json"
        Path(path).write_bytes(legacy.read_bytes())
        code, out = run(RENDER_RESUME, path, "--out", self.tmp / "out")
        self.assertEqual(code, 2, out)
        self.assertIn("jsk migrate", out)
        self.assertNotIn("Traceback", out)

    def test_absent_tex_engine_is_reported_not_assumed(self):
        if tex.available_engine():
            self.skipTest("a TeX engine is installed, so there is nothing to report")
        code, out = run(RENDER_RESUME, EXAMPLE, "--out", self.tmp, "--pdf")
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
        code, out = run(RENDER_RESUME, EXAMPLE, "--out", self.tmp, "--pdf")
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
            code, out = run(RENDER_RESUME, EXAMPLE, "--out", "rel", "--pdf")
            self.assertEqual(code, 0, out)
            self.assertTrue((self.tmp / "rel" / "Priya_Raman_Resume.pdf").exists(), out)
        finally:
            os.chdir(here)

    def test_a_failed_compile_exits_nonzero_and_says_unverified(self):
        module = load_script(RENDER_RESUME)
        module.compile_pdf = lambda tex_path, out_dir: (None, "stub: no PDF")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = module.main(["render_resume.py", str(EXAMPLE),
                                "--out", str(self.tmp), "--pdf"])
        self.assertEqual(code, 1, buf.getvalue())
        self.assertIn("UNVERIFIED", buf.getvalue())

    def test_without_pdf_a_missing_engine_is_not_a_failure(self):
        """Rendering the .tex alone is a legitimate thing to ask for."""
        code, out = run(RENDER_RESUME, EXAMPLE, "--out", self.tmp)
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

        code, out = run(RENDER_RESUME, EXAMPLE, "--out", self.tmp, "--pdf")
        self.assertEqual(code, 0, out)
        with pymupdf.open(self.tmp / "Priya_Raman_Resume.pdf") as pdf:
            actual = pdf.page_count
        self.assertIn(f"pages  Priya_Raman_Resume.pdf: {actual} page", out)
        budget = build.from_path(EXAMPLE)[0]["pages"]
        self.assertIn(f"against a budget of {budget}", out)

    def test_over_budget_is_named_rather_than_left_to_be_noticed(self):
        self.assertIn("OVER BUDGET", self.report("Resume.pdf", 3, 2))
        self.assertNotIn("OVER BUDGET", self.report("Resume.pdf", 2, 2))
        self.assertNotIn("OVER BUDGET", self.report("Resume.pdf", 1, 2))

    def test_an_unmeasurable_render_says_so_instead_of_reporting_the_budget(self):
        """Reported, not fatal: fit_pages.py exits 2 without pymupdf because
        measuring is its whole job. Here it costs one line of the report."""
        self.assertIn("not measured", self.report("Resume.pdf", None, 2))


class PaperSizeFollowsTheRegion(PlanCase):
    """A4 was hardcoded in the LaTeX preamble while the .docx honoured the
    region, so one record produced a Letter .docx and an A4 PDF."""

    def test_us_renders_letterpaper(self):
        self.assertIn("letterpaper", emit_latex.emit(self.plan(region="us")))

    def test_au_renders_a4paper(self):
        self.assertIn("a4paper", emit_latex.emit(self.plan(region="au")))


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
        plans = {fmt: self.plan(fmt=fmt) for fmt in ("presentation", "ats-maximal")}
        return [(f"{fmt}/{name}", emit_latex.emit(plan, template=name))
                for fmt, plan in plans.items()
                for name in themes_mod.names()]

    def test_no_variant_can_express_a_structural_hazard(self):
        for fmt, rendered in self.rendered():
            for hazard, markers in self.HAZARDS.items():
                for marker in markers:
                    self.assertNotIn(marker, rendered, f"{fmt} emitted {hazard}")

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

    def packages(self, rendered):
        return re.findall(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}", rendered)

    def test_the_package_list_is_pinned(self):
        """The golden file, narrowed to the part that carries risk."""
        for fmt, rendered in self.rendered():
            found = self.packages(rendered)
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
        for fmt, rendered in self.rendered():
            for pkg in self.packages(rendered):
                if pkg in self.REQUIRED or pkg == self.REQUIRED_LAST:
                    continue
                self.assertIn(r"\IfFileExists{%s.sty}{\usepackage{%s}}{}" % (pkg, pkg),
                              rendered, f"{fmt}: {pkg} loaded unguarded")

    def test_the_ascii_variant_renders_an_ascii_bullet(self):
        """A PDF bullet is a glyph in the text layer, so U+2022 would fail the
        ATS-maximal variant's own ASCII rule. Colouring the marker wraps the
        glyph and does not change it."""
        for fmt, rendered in self.rendered():
            expected = "{-}" if fmt.startswith("ats-maximal") else r"\textbullet"
            self.assertIn(r"label=\textcolor{jskbullet}{%s}" % expected, rendered, fmt)

    def test_the_ascii_variant_breaks_ligatures(self):
        """T1 Computer Modern turns "fi" into U+FB01 and "ffi" into U+FB03 - one
        codepoint each in the extracted text, so a parser reading "efficiency"
        gets a word that is not there."""
        rendered = emit_latex.emit(self.plan(
            edits=reworded("Improved efficiency of the affiliate workflow."), fmt="ats-maximal"))
        # "ff" and "fi" are both broken - by a kern, which survives TeX rebuilding a
        # hyphenated word where an empty group did not - and no pair survives.
        self.assertIn(r"ef\kern0pt{}f\kern0pt{}iciency", rendered)
        self.assertIn(r"workf\kern0pt{}low", rendered)
        self.assertNotIn("efficiency", rendered)

    def test_the_ascii_variant_sets_straight_quotes(self):
        """T1 sets ' as U+2019 and ` as U+2018: "platform's" failed the strict parse
        gate, and the run asked the person to reword a true bullet around it."""
        edits = reworded("Authored the platform's `retry` policies.")
        rendered = emit_latex.emit(self.plan(edits=edits, fmt="ats-maximal"))
        self.assertIn(r"platform\textquotesingle{}s", rendered)
        self.assertIn(r"\textasciigrave{}retry\textasciigrave{}", rendered)
        self.assertIn("platform's", emit_latex.emit(self.plan(edits=edits, fmt="presentation")))


class TheDateColumnHolds(PlanCase):
    r"""A two-column line without a two-column layout, and the case that breaks
    it is a long left side - which a functional title makes common.

    Three renderings of `#1 <gap> #2` were tried and two were wrong: plain
    \hfill splits the date across lines ("...Engineer)Aug 2016" / "- Feb 2019"),
    \mbox alone runs past the right margin. Both pass every checker, because a
    checker reads extracted text and neither defect is in the text.
    """

    LONG = "Member of Technical Staff, Distinguished Grade IV"
    GLOSS = "Principal Full-Stack Platform Engineer"
    EDIT = (LEAD_TITLE, f'    j:title "{LONG}" ;\n    j:functionalTitle "{GLOSS}" ;\n')

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_the_template_carries_both_guards(self):
        """Either one alone produces a defect, so neither may be dropped - in
        any theme. Four of the five also set \\raggedright, which sets the same
        \\rightskip globally; the \\hfill that pushes the date right is `fill`,
        an infinity order above `fil`, so it still wins and the guard is
        unaffected either way."""
        themes_mod = urs_module("urs.themes")
        plan = self.plan(edits=[self.EDIT])
        for name in themes_mod.names():
            rendered = emit_latex.emit(plan, template=name)
            self.assertIn(r"\rightskip=0pt plus 1fil", rendered, name)
            self.assertIn(r"\mbox{{\color{jskdate}#2}}", rendered, name)

    def long_pdf(self):
        _, path = careerkit.workspace(self.tmp / "ws", edits=list(self.EDITS) + [self.EDIT],
                                      short=short())
        out = self.tmp / "out"
        code, said = run(RENDER_RESUME, path, "--out", out, "--pdf")
        self.assertEqual(code, 0, said)
        return next(out.glob("*.pdf"))

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_a_long_role_line_stays_inside_the_right_margin(self):
        import pymupdf

        with pymupdf.open(self.long_pdf()) as doc:
            for page in doc:
                limit = page.rect.width - 0.5 * 72      # inside the tightest margin
                spilled = [b[4].strip()[:60] for b in page.get_text("blocks")
                           if b[2] > limit]
                self.assertEqual(spilled, [], "text past the right margin")

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_a_long_role_line_does_not_split_its_date(self):
        import pymupdf

        with pymupdf.open(self.long_pdf()) as doc:
            text = "".join(page.get_text() for page in doc)
        # The date on the long line specifically - the fixture gives that role
        # Jan 2023 - Jun 2026, and no other element carries it. Under a bare
        # \hfill it extracts as "...Engineer)Jan 2023" on one line and
        # "- Jun 2026" on the next, so the contiguous run is what fails.
        self.assertIn("Jan 2023 - Jun 2026", text)


class NoTemplateHyphenates(PlanCase):
    r"""monolith justified and hyphenated, and the Everforth render's text layer
    held "Mi-\ncroservices" - a search for "Microservices" missed the default
    template's own PDF. Every theme in both variants now turns it off; the
    compiled proof is check_ats.py's split-word rule, tested in test_check_ats."""

    def test_every_theme_and_variant_turns_hyphenation_off_and_sets_ragged_right(self):
        themes_mod = urs_module("urs.themes")
        for fmt in ("presentation", "ats-maximal"):
            plan = self.plan(fmt=fmt)
            for name in themes_mod.names():
                rendered = emit_latex.emit(plan, template=name)
                body = rendered.split(r"\begin{document}")
                for line in (r"\hyphenpenalty=10000", r"\exhyphenpenalty=10000"):
                    self.assertIn(line, body[0], f"{fmt}/{name}")
                self.assertIn("\n\\raggedright\n", body[1], f"{fmt}/{name}")


class TheHeaderLinksAndTheMetadata(PlanCase):
    """The PDFs carried an empty title and author and no clickable links. A link
    is an annotation, never text, so adding one must not move a character."""

    PROFILES = ('    j:linkedin "linkedin.com/in/test" ; j:github "github.com/test" ;\n',
                '    j:linkedin "linkedin.com/in/test-person" ; j:github "github.com/testperson" ;\n'
                '    j:website "https://testperson.dev" ;\n')

    def test_the_metadata_names_the_person_and_the_variant(self):
        for fmt in ("presentation", "ats-maximal"):
            rendered = emit_latex.emit(self.plan(fmt=fmt))
            self.assertIn(r"\hypersetup{hidelinks,pdftitle={Test Person - Resume},"
                          r"pdfauthor={Test Person},pdfkeywords={jsk-variant:%s}}" % fmt,
                          rendered, fmt)

    def test_email_and_web_contacts_are_linked(self):
        for fmt in ("presentation", "ats-maximal"):
            rendered = emit_latex.emit(self.plan(edits=[self.PROFILES], fmt=fmt))
            for link in (r"\href{mailto:test.person@example.com}{test.person@example.com}",
                         r"\href{https://linkedin.com/in/test-person}{linkedin.com/in/test-person}",
                         r"\href{https://github.com/testperson}{github.com/testperson}",
                         r"\href{https://testperson.dev}{https://testperson.dev}"):
                self.assertIn(link, rendered, fmt)
            self.assertNotIn(r"\href{https://+61", rendered)

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
            _, path = careerkit.workspace(Path(root, "ws"),
                                          edits=list(self.EDITS) + [self.PROFILES],
                                          short=short())
            out = Path(root, "out")
            code, said = run(RENDER_RESUME, path, "--out", out, "--pdf")
            self.assertEqual(code, 0, said)
            with pymupdf.open(next(out.glob("*.pdf"))) as pdf:
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
