"""The fixtures `jsk resume ship`, `jsk app freeze` and `jsk app event` are tested on.

ShipCase is a general resume at a workspace root, shipped with the TeX compile faked;
GraphCase is graphsim's career in a store with the Contoso application rendered and
ready to freeze; ShortCase is that application with a short resume.json. fake_compile
and margin_compile stand in for the TeX engine.
"""
import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import appkit
import careerkit
from fixtures import CLEAN_RESUME, build_pdf, build_text


BAD = "Scaled the platform to [NUMBER] tenants."


MERIDIAN = ["ach_events_latency", "ach_events_team", "ach_identity_sso"]


# The summary is what the strict parse gate finds a summary heading by.
GOOD = {"resume": 2, "bullets": MERIDIAN,
        "summary": {"text": "Platform engineer with 5 years of Kubernetes, building event "
                            "platforms that other teams build on.", "status": "confirmed",
                    "answer": "Yes - that is how I describe what I do.",
                    "text_sha256": "2218dd810a58"}}


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
        from jsk.infra import tex
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
        from jsk.adapters.cli.compose import render as render_resume
        args = ["jsk", "resume", "ship", str(self.record), "--out", str(self.out)]
        buf = io.StringIO()
        with mock.patch.object(render_resume, "compile_pdf",
                               compile_pdf or fake_compile()), \
                contextlib.redirect_stdout(buf):
            code = cli.main(args + [str(a) for a in extra])
        return code, buf.getvalue()

    def headings(self, out):
        return [line[4:].split(":")[0] for line in out.splitlines()
                if line.startswith("--- ")]


MARGIN = re.compile(r"margin=([\d.]+)in\]")


def margin_compile(fits_at=None, over=3, under=2):
    """A compile_pdf whose page count follows the margin the .tex asks for: `over`
    pages until the margin is at or inside `fits_at`, then `under`. None never fits.

    Stands in for the TeX engine on both sides of the fit - the render's compile and
    the fitter's - so the fitter's levers are the real ones, run over the real .tex
    the render wrote, and only the typesetting is faked. Every page carries text,
    because the fitter measures where the text on each page ends."""
    def compile_pdf(tex_path, out_dir):
        import pymupdf
        from jsk.infra import tex
        compile_pdf.into.append(Path(out_dir).resolve())
        margin = float(MARGIN.search(Path(tex_path).read_text(encoding="utf-8")).group(1))
        pages = under if fits_at is not None and margin <= fits_at else over
        pdf = tex.pdf_path_for(tex_path, out_dir)
        doc = pymupdf.open()
        for number in range(pages):
            page = doc.new_page()
            # Full pages, then ten lines on the last: an overrun of about ten lines.
            full = 10 if number == pages - 1 else 50
            lines = CLEAN_RESUME if number == 0 else [f"Page {number + 1} line {i}"
                                                      for i in range(full)]
            page.insert_text((72, 72), "\n".join(lines), fontsize=11)
        doc.save(pdf)
        doc.close()
        return pdf, "compiled with fake"
    compile_pdf.into = []                  # the directory of every compile, in order
    return compile_pdf


# --- the graph record: career/store/ ---------------------------------------------------

class GraphCase(unittest.TestCase):
    """graphsim's career (tests/claims_fixtures) in a store, with the Contoso application
    rendered and ready to freeze - built without a TeX engine."""

    EDITS = ()      # (old, new) in kb.ttl before it goes into the store, as careerkit's

    def setUp(self):
        import shutil

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        shutil.copytree(careerkit.FIXTURES, self.root, dirs_exist_ok=True)
        if self.EDITS:
            kb = self.root / "career" / "kb.ttl"
            text = kb.read_text(encoding="utf-8")
            for old, new in self.EDITS:
                assert text.count(old) == 1, old
                text = text.replace(old, new)
            kb.write_text(text, encoding="utf-8", newline="\n")
            careerkit.relog(self.root)
        appkit.seed(self.root)
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
        """The career's words changed in the store, as `jsk kb apply` would change them:
        its log's newest entry holding the new career's hash."""
        import storekit

        text = appkit.text(self.root, "kb")
        assert text.count(old) == 1, old
        appkit.put(self.root, "kb", text.replace(old, new), prefixes=False)
        storekit.rehash(self.root)

    def graph(self, where, kind):
        return appkit.name(where, kind)

    def jsk(self, *args):
        from jsk import cli

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["jsk", *map(str, args)])
        return code, buf.getvalue()

    def freeze(self, *args, submitted="2026-09-24", channel="Workday portal"):
        return self.jsk("app", "freeze", self.app, "--submitted", submitted, "--channel", channel,
                        *args)

    @property
    def sent(self):
        return self.root / "applications" / "2026-09-24-contoso-platform"

    def application(self, where=None):
        """{predicate: sorted values} of the frozen application, and its events."""
        from jsk.domain import ontology as O

        app, events = {}, {}
        for q in appkit.triples(self.root, self.graph(where or self.sent, "application")):
            name, value = q.predicate.value[len(O.J):], q.object.value
            if O.class_of(q.subject.value) == "Application":
                app.setdefault(name, []).append(value)
            else:
                events.setdefault(q.subject.value[len(O.K):], {})[name] = value
        return {k: sorted(v) for k, v in app.items()}, events

    def store(self):
        from jsk.adapters.cli.compose import record
        return record.load(self.root)


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
