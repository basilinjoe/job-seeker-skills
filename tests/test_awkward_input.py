"""Every command that reads a file a person or an agent wrote, over the four ways that file
reaches it: as jsk writes it, with a BOM, with CRLF line endings, and as cp1252.

Three of the nine defects in the 2026-09-28 review were one reader meeting one of these:
a BOM hid application.md's frontmatter from the Markdown reader, and a cp1252 posting.md,
decisions.txt, gaps.txt or posting.ttl raised UnicodeDecodeError past an `except OSError`.
No test had fed a reader anything but the bytes jsk itself writes. Every authored file is
read through io.read_text now; these tests hold each command to what that promises.

The first three forms are the same text, so the command must do the same thing with each:
the same exit code, the same output once the temp directory is taken out, and the same
files - and the same record in career/store/ - written. The fourth is not UTF-8, and the
command must say so - naming the file, exiting non-zero, writing nothing, and never with
a traceback.

The record itself is no longer text: once it is in career/store/, kb.ttl and posting.ttl
are read exactly once, by `jsk kb load` importing a workspace still laid out as files, so
that is where their four forms are tried (Import). The texts that stay files - a source
document, resume.json - are tried against the command that reads each, over a
workspace whose record is in its store. posting.md, decisions.txt and gaps.txt left with the
posting and tailor nouns in 6.0: an advert in a file is read by `posting_capture`, whose four
forms are tests/test_posting.py's (FromAFile).

Each command runs in a child interpreter, as a person runs it, so that a traceback is
something the output would show rather than something the test runner would catch.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import AWKWARD, CLI, run, write_awkward
from storekit import seed
from test_kb_confirm import QUOTE, SOURCE
from test_graph_shapes import FIXTURES as GRAPH

from jsk.infra.oxigraph import db

PLAIN, SAME, REFUSED = AWKWARD[0], AWKWARD[1:3], AWKWARD[3]
# The store, as it is compared: its record dumped, since RocksDB's own files differ from
# one write of the same record to the next (ids, logs, manifests).
DUMP = "career/store (dumped)"

# Each authored text carries a character cp1252 writes above 0x7f, or its cp1252 form
# would be plain ASCII and test nothing: write_awkward refuses one that does not.
DOCUMENT = SOURCE.replace("# Prior resume", "# Prior résumé")
SUMMARY = "Architect who builds clinical event platforms – the ones other teams build on."
TITLE = ('j:title "Platform Engineer"', 'j:title "Platform Engineer – Core"')
HEADLINE = ('j:headline "Principal Solution Architect"',
            'j:headline "Principal Solution Architect – Health"')


def snapshot(root, skip=None):
    """{relative path: bytes} of every file under root, less any holding `skip` - the
    authored file as written, and a verbatim copy of it, which differ between the forms
    by design. A refusal is compared with nothing skipped: a verbatim copy it left
    behind is a write. career/store/ is one entry, its record as dumped."""
    store = root / db.STORE_DIR
    out = {p.relative_to(root).as_posix(): p.read_bytes()
           for p in sorted(root.rglob("*")) if p.is_file() and store not in p.parents
           and p not in (root / db.LOCK_FILE, root / db.ACCESS_FILE) and p.read_bytes() != skip}
    if db.exists(root):
        out[DUMP] = db.dump_text(db.read(root)).encode("utf-8")
    return out


def scrubbed(out, root):
    """The output with the temp directory taken out, however it was spelled."""
    # Longest first: /private/var/... holds /var/... on macOS, and a set's order is not fixed.
    spellings = {str(root.resolve()), str(root), root.as_posix(), root.resolve().as_posix()}
    for spelling in sorted(spellings, key=len, reverse=True):
        out = out.replace(spelling, "<root>")
    return out


def graphs(found):
    """The record graphs a form's run left in career/store/, by name."""
    dump = found[2].get(DUMP)
    return set(db.parse_dump(dump.decode("utf-8"))) if dump else set()


class Forms(unittest.TestCase):
    """One command, run once over a fresh workspace for each form of one authored file."""

    def forms(self, text, build, target, command):
        """{form: (exit code, output, files after less the authored file, every file
        before, every file after)}. `build(root)` makes the workspace, `target(root)` is
        the authored file, `command(root)` the arguments or a callable that runs it."""
        found = {}
        for form in AWKWARD:
            root = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, root, True)
            build(root)
            written = write_awkward(target(root), text, form)
            before = snapshot(root)
            ran = command(root)
            # A command is the jsk arguments, or a callable returning (code, output): what a
            # retired verb's tool does, called in-process (tests/recordkit.py).
            code, out = ran() if callable(ran) else run(CLI, *ran)
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


# --- jsk kb load: the one reader of the record's files ---------------------------------

ACME = Path("applications") / "acme-platform-engineer"


def edited(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    return text.replace(old, new)


def files_workspace(root):
    """The graph fixture as a workspace from before the store: files, and no store."""
    shutil.copytree(GRAPH, root, dirs_exist_ok=True)


class Import(Forms):
    """A kb.ttl or posting.ttl saved by a Windows editor is imported the same as one jsk
    wrote - or, as cp1252, refused naming it, with no store left behind half-filled."""

    def load(self, target, old, new, arrow=False):
        text = edited(GRAPH / target, old, new)
        if arrow:
            text = text.replace("→", "->")
        found = self.check(text, files_workspace,
                           lambda r: r / target, lambda r: ["kb", "load", r, "--root", r],
                           target.name)
        self.assertEqual(graphs(found[PLAIN]), {"kb", "log", f"{ACME.as_posix()}/posting",
                                                f"{ACME.as_posix()}/application"})
        return found

    def test_load_reads_kb_ttl(self):
        # The fixture's one arrow has no cp1252 byte, and a Windows editor saving it so
        # would have had to drop it; the rest is the fixture as it is.
        target = Path("career") / "kb.ttl"
        self.assertEqual((GRAPH / target).read_text(encoding="utf-8").count("→"), 1)
        found = self.load(target, *HEADLINE, arrow=True)
        self.assertIn("Principal Solution Architect – Health".encode(), found[PLAIN][2][DUMP])

    def test_load_reads_posting_ttl(self):
        found = self.load(ACME / "posting.ttl", *TITLE)
        self.assertIn("Platform Engineer – Core".encode(), found[PLAIN][2][DUMP])


def graph_workspace(root):
    """The graph fixture with its record in career/store/, as jsk keeps one."""
    shutil.copytree(GRAPH, root, dirs_exist_ok=True)
    seed(root)


# --- the career_confirm tool ----------------------------------------------------------

DOC = Path("imports") / "prior-resume.md"


class KbConfirm(Forms):
    """`jsk kb confirm` is retired; career_confirm reads its source document the same way."""

    def test_confirm_reads_its_source_document(self):
        import recordkit

        found = self.check(
            DOCUMENT, graph_workspace, lambda r: r / DOC,
            lambda r: lambda: recordkit.confirm(
                r, ["k:ach_site_onboarding_sites_one_platform"], source=str(r / DOC),
                quote=QUOTE), "prior-resume.md")
        self.assertIn(f'From imports/prior-resume.md: \\"{QUOTE}\\"'.encode(),
                      found[PLAIN][2][DUMP])



if __name__ == "__main__":
    unittest.main()
