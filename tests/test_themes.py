"""Themes change how the resume looks and nothing else.

That sentence is the whole contract, and it is the one thing about a coloured
resume worth being suspicious of, so almost nothing here is asserted from the
source. The claims that matter are checked against compiled PDFs: five themes
are rendered from one record, the text layer is extracted from each, and the
five are compared. If a theme ever changes a word - or a glyph, which is what
`\\MakeUppercase` on the name quietly did in the first cut - this is where it
surfaces.

The rest are the rules `themes.py` states in prose, made enforceable: contrast
floors, the accent budget, guarded font loads, and the fitter's reach.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import (CHECK_ATS, EXAMPLE_URS, RENDER_RESUME, SCRIPTS, run,
                      urs_doc, urs_module, urs_package, write_urs)

CHECK_PROSE = SCRIPTS / "check_prose.py"

planner = urs_package()
emit_latex = urs_module("urs.emit_latex")
themes = urs_module("urs.themes")
tex = urs_module("urs.tex")

ENGINE = tex.available_engine()


def has_pymupdf():
    try:
        import pymupdf  # noqa: F401,PLC0415
        return True
    except ImportError:
        return False


# --- contrast ------------------------------------------------------------------

def _channel(value):
    v = value / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b))


def contrast(hex_colour, other="FFFFFF"):
    a, b = luminance(hex_colour), luminance(other)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


class ThePaletteSurvivesABadScreen(unittest.TestCase):
    """A resume is read on a laptop at 60% brightness, printed in greyscale and
    forwarded as a phone screenshot. An accent that only works on a calibrated
    monitor is a decoration that costs information."""

    def themes(self):
        return [(name, themes.get(name)) for name in themes.names()]

    def test_body_ink_is_near_black_in_every_theme(self):
        for name, theme in self.themes():
            self.assertGreaterEqual(contrast(theme["ink"]), 12.0,
                                    f"{name}: body ink too light")

    def test_every_colour_that_carries_words_clears_4_5_to_1(self):
        """AA for body text, applied to the muted and accent roles too, because
        both of them set actual words - dates and section headings are not
        decoration just because they are secondary."""
        for name, theme in self.themes():
            for role in ("accent", "muted"):
                self.assertGreaterEqual(
                    contrast(theme[role]), 4.5,
                    f"{name}: {role} #{theme[role]} fails AA on white")

    def test_rules_are_lighter_than_the_text_they_separate(self):
        """A rule at text weight competes with the text. Monolith is the stated
        exception: it has no colour at all, so its rule is ink by definition and
        earns its restraint through weight instead - 0.4pt against 0.6."""
        for name, theme in self.themes():
            if theme["rule"] == theme["ink"]:
                self.assertLessEqual(theme["head_rule_pt"], 0.4, name)
                continue
            self.assertLess(contrast(theme["rule"]), contrast(theme["ink"]), name)


class TheAccentHasABudget(unittest.TestCase):
    """More than a few accent sites and the eye has no path to follow, because
    everything is emphasised and so nothing is."""

    # Roles where the accent colours actual words. Rules and bullet markers are
    # marks, not text, and are excluded deliberately: they guide without
    # competing for the reader's attention.
    TEXT_ROLES = ("name_color", "headline_color", "head_color", "org_color",
                  "role_color", "date_color", "label_color")

    def test_no_theme_spends_more_than_the_budget(self):
        for name in themes.names():
            theme = themes.get(name)
            if theme["accent"] == theme["ink"]:
                continue                       # an ink-only theme has no accent to spend
            spent = [r for r in self.TEXT_ROLES if theme[r] == "jskaccent"]
            self.assertLessEqual(len(spent), themes.ACCENT_BUDGET,
                                 f"{name}: accent on {spent}")


class NoThemeTouchesTheTextLayer(unittest.TestCase):
    """The reason a coloured resume is safe, checked rather than asserted."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def render(self, name):
        out = self.tmp / name
        code, output = run(RENDER_RESUME, EXAMPLE_URS, "--out", out,
                           "--template", name, "--format", "latex", "--pdf")
        self.assertEqual(code, 0, output)
        return next(out.glob("*.pdf"))

    def extract(self, pdf):
        import pymupdf

        with pymupdf.open(pdf) as doc:
            # Normalised for whitespace only: a wider typeface wraps a bullet at
            # a different word, which moves line breaks and changes nothing a
            # parser cares about. Every other difference is a real one.
            return " ".join("".join(p.get_text() for p in doc).split())

    def test_no_theme_uppercases_the_name(self):
        """The defect this test exists for. Two themes shipped \\MakeUppercase
        on the name, because a heavy all-caps name is the strongest anchor
        available at the top of a page - and it is the one theme choice a parser
        can see, on the single highest-value field in the document."""
        doc = urs_doc()
        for name in themes.names():
            rendered = emit_latex.emit(planner.build(doc), template=name)
            head = rendered.split(r"\begin{document}")[0]
            command = [l for l in head.splitlines()
                       if l.startswith(r"\newcommand{\resumename}")]
            self.assertEqual(len(command), 1,
                             f"{name}: expected exactly one \\resumename definition")
            self.assertNotIn("MakeUppercase", command[0],
                             f"{name} uppercases the name")

    @unittest.skipUnless(ENGINE and has_pymupdf(), "needs a TeX engine and pymupdf")
    def test_every_theme_extracts_to_the_same_document(self):
        texts = {name: self.extract(self.render(name)) for name in themes.names()}
        reference = texts[themes.DEFAULT]
        for name, text in texts.items():
            self.assertEqual(text, reference,
                             f"{name} changed the text layer, not just the look")

    @unittest.skipUnless(ENGINE and has_pymupdf(), "needs a TeX engine and pymupdf")
    def test_every_theme_extracts_what_the_record_says(self):
        """The test above compares the themes against each other, which cannot
        see a change they all make: uppercase the name in the shared command and
        five identical-but-wrong documents still agree.

        So this one compares against the record instead. The name and the
        headline are the two fields where a display transformation is most
        tempting and most expensive, and they have to come back out of the PDF
        exactly as the resolver wrote them.
        """
        import json

        with open(EXAMPLE_URS, encoding="utf8") as fh:
            plan = planner.build(json.load(fh))
        for name in themes.names():
            text = self.extract(self.render(name))
            self.assertIn(plan["name"], text, f"{name}: the name is not in the text layer")
            if plan.get("headline"):
                self.assertIn(plan["headline"], text, f"{name}: headline altered")
            for section in plan["sections"]:
                if section.get("heading"):
                    self.assertIn(section["heading"].lower(), text.lower(),
                                  f"{name}: heading {section['heading']!r} altered")

    @unittest.skipUnless(ENGINE and has_pymupdf(), "needs a TeX engine and pymupdf")
    def test_every_theme_passes_the_ats_gate(self):
        """Colour, a typeface and a rule cannot break a parse - but "cannot" is
        a claim, and check_ats.py is the thing that answers it."""
        for name in themes.names():
            pdf = self.render(name)
            proc = subprocess.run([sys.executable, str(CHECK_ATS), str(pdf)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"{name}:\n{proc.stdout}")

    def test_no_template_emits_something_the_prose_gate_reads_as_a_placeholder(self):
        r"""check_prose.py reads the .tex, not the PDF, so LaTeX a template emits
        can reach a checker looking for prose defects.

        It did. `\makebox[0pt][r]{...}` hung the margin bar exactly where it
        belonged, and check_prose strips a command plus *one* optional argument
        - so `[r]` survived into the scanned text and was reported as an
        unresolved placeholder, failing the gate on a clean document. The gate
        was right to flag a stray bracket. The template was wrong to emit one.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = write_urs(Path(tmp), urs_doc(), "resume.json")
            for name in themes.names():
                code, out = run(RENDER_RESUME, path, "--out", tmp,
                                "--template", name, "--format", "latex")
                self.assertEqual(code, 0, out)
                tex_file = next(Path(tmp).glob("*.tex"))
                proc = subprocess.run(
                    [sys.executable, str(CHECK_PROSE), str(tex_file)],
                    capture_output=True, text=True)
                self.assertNotIn("unresolved placeholder", proc.stdout,
                                 f"{name} emitted LaTeX the prose gate reads as text")

    @unittest.skipUnless(ENGINE and has_pymupdf(), "needs a TeX engine and pymupdf")
    def test_ragged_right_does_not_push_the_date_column_off_the_page(self):
        r"""Four themes set \raggedright, which sets the same \rightskip that
        \dateright relies on. The reasoning says \hfill still wins because
        `fill` outranks `fil`; this is the measurement that says so. The case
        is a long role line, which is where the date column breaks if it
        breaks at all."""
        import pymupdf

        doc = urs_doc()
        position = doc["engagements"][0]["positions"][0]
        position["title"] = "Member of Technical Staff, Distinguished Grade IV"
        position["functional_title"] = "Principal Full-Stack Platform Engineer"
        path = write_urs(self.tmp, doc, "long.json")

        for name in themes.names():
            out = self.tmp / f"long-{name}"
            code, output = run(RENDER_RESUME, path, "--out", out, "--template", name,
                               "--view", "view_default", "--format", "latex", "--pdf")
            self.assertEqual(code, 0, output)
            with pymupdf.open(next(out.glob("*.pdf"))) as pdf:
                for page in pdf:
                    limit = page.rect.width - 0.5 * 72   # inside the tightest margin
                    spilled = [b[4].strip()[:60] for b in page.get_text("blocks")
                               if b[2] > limit]
                    self.assertEqual(spilled, [], f"{name}: text past the right margin")


class TheTemplateChoiceIsExplicit(unittest.TestCase):
    def test_an_unknown_template_is_an_error_not_a_default(self):
        """A resume rendered in a theme nobody chose is a resume nobody has
        looked at, and it would look perfectly fine."""
        with self.assertRaises(KeyError):
            themes.get("chartreuse")

    def test_the_error_names_the_templates_that_do_exist(self):
        with self.assertRaises(KeyError) as caught:
            themes.get("chartreuse")
        for name in themes.names():
            self.assertIn(name, caught.exception.args[0])

    def test_the_cli_refuses_an_unknown_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", tmp,
                            "--template", "chartreuse")
            self.assertEqual(code, 2, out)
            self.assertIn("chartreuse", out)

    def test_the_catalogue_says_what_each_theme_is_for(self):
        """--list-templates is the only place the choice is explained at the
        point it is made, so an entry without guidance is a broken entry."""
        for name, blurb, best_for in themes.catalogue():
            self.assertTrue(blurb.strip(), name)
            self.assertTrue(best_for.strip(), name)

    def test_the_default_is_the_ink_only_theme(self):
        """Colour is opt-in. Someone re-rendering a resume mid-search gets the
        document they had, not a redesign they did not ask for."""
        theme = themes.get(None)
        self.assertEqual(theme["accent"], theme["ink"])


class TheRhythmIsAGrid(unittest.TestCase):
    """Every vertical gap is a multiple of one unit per theme. That is what
    makes the spacing read as intentional rather than as four numbers someone
    tuned by eye until it stopped looking wrong."""

    def test_every_gap_is_a_multiple_of_the_themes_unit(self):
        for name in themes.names():
            theme = themes.get(name)
            for key, value in themes.rhythm_lengths(theme).items():
                ratio = value / theme["rhythm"]
                self.assertAlmostEqual(ratio, round(ratio, 2), places=2,
                                       msg=f"{name}: {key} is off the grid")

    def test_sections_are_separated_more_than_entries_within_them(self):
        """Proximity is the whole hierarchy: if the gap above a heading does not
        beat the gap between two employers, the sections stop reading as
        sections and the document becomes one list."""
        for name in themes.names():
            gaps = themes.rhythm_lengths(themes.get(name))
            self.assertGreater(gaps["sectiongap"], gaps["entrygap"], name)


if __name__ == "__main__":
    unittest.main()
