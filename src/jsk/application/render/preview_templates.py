"""Previewing one resume.json in every template: each rendered, compiled, and measured.

Nothing here decides anything about the document: each template is rendered by
render_resume.render_loaded from the one loaded resume.json and region, so the only
variable is the look. The .tex files are written one after another; the TeX compiles,
which are external processes and nearly all of the time, run side by side. It prints
nothing: adapters/entry/preview.py says what it did.
"""
import contextlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ...domain.render import themes
from .render_resume import render_loaded


class PreviewStopped(Exception):
    """A preview that could not start: `kind` says why.

    "frozen" (`detail` is the refusal's lines, exit 1), "no-engine" (no TeX engine to
    make a page with, exit 2) or "unknown" (`detail` is the template names no theme
    has, exit 2).
    """

    def __init__(self, kind, detail, code):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
        self.code = code


@dataclass(frozen=True)
class TemplatePreview:
    """One template's preview: its PDF, or why there is none."""

    name: str
    pdf: str | None             # DIR/<template>.pdf, or None when it did not build
    failure: Exception | None   # what the render raised, when it did not get to compile
    note: str                   # what the TeX engine said, when it did not compile
    pages: int | None           # the page count, when a thumbnail could be made
    thumbnail_note: str | None  # why the thumbnail could not be made, when pymupdf failed
    blurb: str


@dataclass(frozen=True)
class PreviewResult:
    """Every template's preview, in the order asked for."""

    templates: tuple

    @property
    def failed(self):
        """The names of the templates that did not build."""
        return [t.name for t in self.templates if t.pdf is None]


def preview_templates(src, out_dir, only, *, region, ats_max, today, load, profiles, tex,
                      reader, outputs, frozen):
    """Render the resume.json at `src` in each template, into `out_dir`.

    The file is loaded once, here, before any template: a legacy record, a file outside
    a workspace or a frozen application fails every template the same way, and five
    FAILED blocks under "a template that does not build" blamed the templates for it.

    Args:
        src: the resume.json.
        out_dir: where DIR/<template>.{tex,pdf,png} go; it exists.
        only: a comma-separated list of templates, or None for every one.
        region: overrides the file's region profile.
        ats_max: render the ATS-maximal variant.
        today: the date a declaration is signed on.
        load: loads and checks the resume.json (load_resume bound to its ports).
        profiles: the region profiles (ports.profiles.Profiles).
        tex: compiles each template (ports.tex.TexCompiler).
        reader: makes each first-page thumbnail (ports.pdf.PdfInspector).
        outputs: stages and moves the files (ports.outputs.RenderOutputs).
        frozen: what says a directory was frozen, or None (compose.timeline.frozen).

    Returns:
        A PreviewResult. Writes each template's .tex, .pdf and .png into `out_dir`.

    Raises:
        PreviewStopped: frozen, no TeX engine, or an unknown template.
        ShortError: from `load`.
    """
    from ..guards import frozen_refusal

    refusal = frozen_refusal(out_dir, os.path.dirname(os.path.abspath(src)), frozen=frozen)
    if refusal:
        raise PreviewStopped("frozen", refusal, 1)
    loaded = load(src)
    if not tex.available_engine():
        raise PreviewStopped("no-engine", None, 2)
    wanted = [n.strip() for n in only.split(",")] if only else themes.names()
    unknown = [n for n in wanted if n not in themes.names()]
    if unknown:
        raise PreviewStopped("unknown", unknown, 2)

    options = {"fmt": "latex", "region": region, "profile": "ats-maximal" if ats_max else None,
               "today": today, "profiles": profiles, "company_of": None, "tex": tex,
               "reader": reader, "outputs": outputs}
    with contextlib.ExitStack() as stack:
        # Each render is staged in its own scratch directory, because the render names
        # its outputs after the person rather than the template: five templates sharing
        # one directory is one filename five times, and the last would win silently.
        # Separate directories are also what lets the compiles below run at once
        # without touching each other.
        stages, problems = {}, {}
        for name in wanted:
            stage = stack.enter_context(outputs.scratch())
            staged = os.path.join(stage, f"{name}_Resume.tex")
            try:
                done = render_loaded(loaded, src, stage, template=name, name=name, **options)
            except Exception as exc:                # noqa: BLE001 - one template, reported
                problems[name] = exc
                continue
            if staged in done.written:
                stages[name] = staged
            else:
                problems[name] = None

        # Threads, not processes: each one only waits on a TeX engine, which is its
        # own process already. map() hands the results back in submission order, and
        # the results below walk `wanted`, so they read the same however the
        # compiles finished.
        workers = max(1, min(len(stages), os.cpu_count() or 1))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            compiled = dict(zip(stages, pool.map(
                lambda t: tex.compile_pdf(t, os.path.dirname(t)), stages.values()),
                strict=True))
        return PreviewResult(tuple(
            placed(name, compiled.get(name), problems.get(name), stages, out_dir,
                   reader=reader, outputs=outputs)
            for name in wanted))


def placed(name, compiled, failure, stages, out_dir, *, reader, outputs):
    """One template's preview: its PDF and .tex moved into `out_dir`, its first page drawn.

    Args:
        name: the template.
        compiled: (the PDF or None, the TeX engine's note), or None when it never
            reached the compile.
        failure: what its render raised, if it did.
        stages: {template: its staged .tex}.
        out_dir: where the preview goes.
        reader: draws the thumbnail (ports.pdf.PdfInspector).
        outputs: moves the files (ports.outputs.RenderOutputs).

    Returns:
        A TemplatePreview. Moves DIR/<name>.pdf and .tex into place and writes its .png.
    """
    blurb = themes.get(name)["blurb"]
    pdf, note = compiled or (None, "")
    if not pdf:
        return TemplatePreview(name, None, failure, note, None, None, blurb)
    final_pdf = os.path.join(out_dir, f"{name}.pdf")
    outputs.replace(pdf, final_pdf)
    outputs.replace(stages[name], os.path.join(out_dir, f"{name}.tex"))
    pages, why = thumbnail(reader, final_pdf, os.path.join(out_dir, f"{name}.png"))
    return TemplatePreview(name, final_pdf, None, note, pages, why, blurb)


def thumbnail(reader, pdf, png, dpi=110):
    """First page as a PNG. Optional: the PDFs are the deliverable and a
    missing pymupdf costs a convenience, not the preview.

    Args:
        reader: draws it (ports.pdf.PdfInspector).
        pdf: the PDF.
        png: where the image goes.
        dpi: its resolution.

    Returns:
        (the page count or None, why it could not be read or None). Writes `png`.
    """
    try:
        return reader.thumbnail(pdf, png, dpi), None
    except ImportError:
        return None, None
    except Exception as e:                          # noqa: BLE001 - reported, never fatal
        return None, f"could not read {os.path.basename(pdf)}: {e}"
