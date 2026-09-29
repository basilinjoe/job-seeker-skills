"""Every command that reads a file a person or an agent wrote, over the four ways that file
reaches it: as jsk writes it, with a BOM, with CRLF line endings, and as cp1252.

Three of the nine defects in the 2026-09-28 review were one reader meeting one of these:
a BOM hid application.md's frontmatter from the Markdown reader, and a cp1252 posting.md,
decisions.txt, gaps.txt or posting.ttl raised UnicodeDecodeError past an `except OSError`.
No test had fed a reader anything but the bytes jsk itself writes. Every authored file is
read through io.read_text now; these tests hold each command to what that promises.

The first three forms are the same text, so the command must do the same thing with each:
the same exit code, the same output once the temp directory is taken out, and the same
files written. The fourth is not UTF-8, and the command must say so - naming the file,
exiting non-zero, writing nothing, and never with a traceback. `jsk render` is the one
exception: posting.ttl only gives it the company for the file name, so an unreadable one
names the file with no company (Ruling 8).

Each command runs in a child interpreter, as a person runs it, so that a traceback is
something the output would show rather than something the test runner would catch.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import careerkit
from fixtures import AWKWARD, CLI, run, write_awkward
from test_build import short
from test_graph_kbcli import QUOTE, SOURCE
from test_graph_shapes import FIXTURES as GRAPH
from test_posting_build import ADVERT, HEADER, ROWS

MATCH = Path(__file__).parent / "match_fixtures"
PLAIN, SAME, REFUSED = AWKWARD[0], AWKWARD[1:3], AWKWARD[3]

# Each authored text carries a character cp1252 writes above 0x7f, or its cp1252 form
# would be plain ASCII and test nothing: write_awkward refuses one that does not.
GAPS_TXT = ("fit: poor\neligibility: meets it – based in Pune\n"
            "k8s | partial | one AKS cluster | never on call\n"
            "short: no on-call ownership\nask: Who ran it?\n")
DECISIONS = HEADER + "\n# the analyst’s rows, one per line the advert asks for\n" + ROWS
DOCUMENT = SOURCE.replace("# Prior resume", "# Prior résumé")
SUMMARY = "Architect who builds clinical event platforms – the ones other teams build on."
TITLE = ('j:title "Platform Engineer"', 'j:title "Platform Engineer – Core"')


def snapshot(root, skip=None):
    """{relative path: bytes} of every file under root, less any holding `skip` - the
    authored file as written, and a verbatim copy of it, which differ between the forms
    by design. A refusal is compared with nothing skipped: a verbatim copy it left
    behind is a write."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file() and p.read_bytes() != skip}


def scrubbed(out, root):
    """The output with the temp directory taken out, however it was spelled."""
    # Longest first: /private/var/... holds /var/... on macOS, and a set's order is not fixed.
    spellings = {str(root.resolve()), str(root), root.as_posix(), root.resolve().as_posix()}
    for spelling in sorted(spellings, key=len, reverse=True):
        out = out.replace(spelling, "<root>")
    return out


class Forms(unittest.TestCase):
    """One command, run once over a fresh workspace for each form of one authored file."""

    def forms(self, text, build, target, command):
        """{form: (exit code, output, files after less the authored file, every file
        before, every file after)}. `build(root)` makes the
        workspace, `target(root)` is the authored file, `command(root)` the arguments."""
        found = {}
        for form in AWKWARD:
            root = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, root, True)
            build(root)
            written = write_awkward(target(root), text, form)
            before = snapshot(root)
            code, out = run(CLI, *command(root))
            found[form] = (code, scrubbed(out, root), snapshot(root, written), before,
                           snapshot(root))
        return found

    def assert_the_same(self, found):
        code, out, after, _, _ = found[PLAIN]
        self.assertEqual(code, 0, out)
        self.assertNotIn("Traceback", out)
        for form in SAME:
            with self.subTest(form=form):
                self.assertEqual(found[form][:2], (code, out))
                self.assertEqual(sorted(found[form][2]), sorted(after))
                for name, data in after.items():
                    self.assertEqual(found[form][2][name], data, name)

    def assert_refused(self, found, names):
        code, out, _, before, after = found[REFUSED]
        with self.subTest(form=REFUSED):
            self.assertNotEqual(code, 0, out)
            self.assertIn(names, out)
            self.assertIn("UTF-8", out)
            self.assertNotIn("Traceback", out)
            self.assertEqual(sorted(after), sorted(before), "a refusal writes nothing")
            self.assertEqual(after, before, "a refusal writes nothing")

    def check(self, text, build, target, command, names):
        found = self.forms(text, build, target, command)
        self.assert_the_same(found)
        self.assert_refused(found, names)
        return found


# --- jsk posting extract / build ------------------------------------------------------

STEM = "acme-staff-platform"


def posting_app(root):
    return root / "applications" / STEM


def graph_workspace(root):
    shutil.copytree(GRAPH, root, dirs_exist_ok=True)


def with_decisions(root):
    graph_workspace(root)
    write_awkward(posting_app(root) / "decisions.txt", DECISIONS, PLAIN)


def with_advert(root):
    graph_workspace(root)
    write_awkward(posting_app(root) / "posting.md", ADVERT, PLAIN)


class Posting(Forms):
    def test_extract_reads_posting_md(self):
        self.check(ADVERT, graph_workspace, lambda r: posting_app(r) / "posting.md",
                   lambda r: ["posting", "extract", posting_app(r)], "posting.md")

    def test_build_reads_posting_md(self):
        found = self.check(ADVERT, with_decisions, lambda r: posting_app(r) / "posting.md",
                           lambda r: ["posting", "build", posting_app(r),
                                      posting_app(r) / "decisions.txt"], "posting.md")
        self.assertIn(f"applications/{STEM}/posting.ttl", found[PLAIN][2])

    def test_build_reads_decisions_txt(self):
        found = self.check(DECISIONS, with_advert, lambda r: posting_app(r) / "decisions.txt",
                           lambda r: ["posting", "build", posting_app(r),
                                      posting_app(r) / "decisions.txt"], "decisions.txt")
        self.assertIn(f"applications/{STEM}/posting.ttl", found[PLAIN][2])


# --- jsk match --gaps -----------------------------------------------------------------

CONTOSO = Path("applications") / "contoso"


class MatchGaps(Forms):
    def test_match_gaps_reads_gaps_txt(self):
        found = self.check(
            GAPS_TXT, lambda r: shutil.copytree(MATCH, r, dirs_exist_ok=True),
            lambda r: r / CONTOSO / "gaps.txt",
            lambda r: ["match", r / CONTOSO / "posting.ttl", "--gaps", r / CONTOSO / "gaps.txt",
                       "--today", "2026-09-24"], "gaps.txt")
        written = found[PLAIN][2]
        self.assertIn("applications/contoso/gaps.ttl", written)
        self.assertIn("meets it – based in Pune".encode(),
                      written["applications/contoso/gaps.md"])


# --- jsk tailor prepare ---------------------------------------------------------------

ACME = Path("applications") / "acme-platform-engineer"
ACME_POSTING = (GRAPH / ACME / "posting.ttl").read_text(encoding="utf-8")


def unsent(root):
    """The graph fixture with its application unsent, so that prepare writes gaps.ttl and
    gaps.md rather than keeping a frozen assessment."""
    graph_workspace(root)
    (root / ACME / "application.ttl").unlink()


class TailorPrepare(Forms):
    def test_prepare_reads_posting_ttl(self):
        text = ACME_POSTING.replace(*TITLE)
        self.assertNotEqual(text, ACME_POSTING)
        found = self.check(text, unsent, lambda r: r / ACME / "posting.ttl",
                           lambda r: ["tailor", "prepare", r / ACME, "--today", "2026-09-27"],
                           "posting.ttl")
        self.assertIn(f"{ACME.as_posix()}/gaps.ttl", found[PLAIN][2])


# --- jsk render -----------------------------------------------------------------------

WS = "ws"


def render_workspace(root):
    careerkit.workspace(root / WS, short=short())


def contoso_posting():
    text = (careerkit.FIXTURES / careerkit.APP / "posting.ttl").read_text(encoding="utf-8")
    return text.replace(*TITLE)


class Render(Forms):
    def test_render_reads_posting_ttl_for_the_company_or_goes_without(self):
        text = contoso_posting()
        self.assertIn("Platform Engineer – Core", text)
        found = self.forms(text, render_workspace,
                           lambda r: r / WS / careerkit.APP / "posting.ttl",
                           lambda r: ["render", r / WS / careerkit.APP / "resume.json",
                                      "--out", r / "out", "--format", "latex"])
        self.assert_the_same(found)
        tex = {form: sorted(n for n in found[form][2] if n.startswith("out/"))
               for form in AWKWARD}
        self.assertEqual(tex[PLAIN], ["out/Test_Person_Contoso_Resume.tex"])
        code, out, after, _, _ = found[REFUSED]
        with self.subTest(form=REFUSED):
            self.assertEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertEqual(tex[REFUSED], ["out/Test_Person_Resume.tex"])
            self.assertEqual(after["out/Test_Person_Resume.tex"],
                             found[PLAIN][2]["out/Test_Person_Contoso_Resume.tex"])


# --- jsk kb confirm -------------------------------------------------------------------

DOC = Path("imports") / "prior-resume.md"
GLOBEX = Path("applications") / "globex-architect" / "resume.json"


class KbConfirm(Forms):
    def test_confirm_reads_its_source_document(self):
        found = self.check(
            DOCUMENT, graph_workspace, lambda r: r / DOC,
            lambda r: ["kb", "confirm", "k:ach_site_onboarding_sites_one_platform",
                       "--source", r / DOC, "--quote", QUOTE, "--root", r], "prior-resume.md")
        self.assertIn(f'From imports/prior-resume.md: \\"{QUOTE}\\"'.encode(),
                      found[PLAIN][2]["career/log.ttl"])

    def test_confirm_summary_reads_resume_json(self):
        doc = {"resume": 2, "bullets": ["ach_clinical_events_event_latency"],
               "summary": {"text": SUMMARY, "status": "inferred"}, "pages": 2}
        found = self.check(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", graph_workspace,
            lambda r: r / GLOBEX,
            lambda r: ["kb", "confirm", "--summary", r / GLOBEX, "--answer",
                       "Yes, that is exactly what I do.", "--root", r], "resume.json")
        written = json.loads(found[PLAIN][2][GLOBEX.as_posix()])
        self.assertEqual(written["summary"]["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
