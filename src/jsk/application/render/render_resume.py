"""Rendering one resume.json: its plans built, its files written, its PDF compiled and measured.

Every content decision is domain/resume/plan.py's and every markup decision the emitters'.
This decides which files are written and what they are called, compiles the .tex when
asked, and measures what the TeX engine produced. It prints nothing: adapters/cli/render.py
says what it did.
"""
import os
from dataclasses import dataclass

from ...domain.render import emit_latex, emit_text, themes
from ...domain.render.fit_levers import fill_percent
from ...domain.render.targets import safe_name, select_targets
from ...domain.render.page_report import page_report
from ...domain.resume.plan import build


class RenderStopped(Exception):
    """A render that stopped before it finished.

    `kind` says why: "frozen" (`detail` is the refusal's lines, from
    application.guards.frozen_refusal), "plan" (`detail` is what the builder raised) or
    "format" (`detail` is the file kind nobody renders). `code` is the exit code.
    """

    def __init__(self, kind, detail, code):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
        self.code = code


@dataclass(frozen=True)
class RenderResult:
    """What one render wrote and measured."""

    view: str
    profile: str
    budget: int                 # the page budget of the first variant rendered
    template: str
    written: tuple              # every file, in the order written
    pages: tuple                # one page_report line per PDF
    notes: tuple                # what the TeX engine said, one per compile
    warnings: tuple             # each once, in the order raised
    variants: dict              # PDF path -> the variant it holds
    unverified: bool            # a PDF was asked for and none was produced
    measured: tuple = ()        # (PDF name, pages, budget) for each PDF whose pages counted
    withheld: tuple = ()        # the id of each entry held below the floor, each once


def page_count(reader, pdf):
    """Pages in the PDF just written, or None if it cannot be measured.

    Optional here in the way it is not in fit_pages.py, which exits 2 without it:
    that script's whole job is the page count, where this one reports it beside the
    budget. Same import guard, different consequence.

    Args:
        reader: reads the PDF (ports.pdf.PdfInspector).
        pdf: the PDF.

    Returns:
        The count, or None when there is no PDF reader or the PDF will not open.
    """
    try:
        return reader.page_count(pdf)
    except Exception:                               # noqa: BLE001 - ImportError too; never fatal
        return None


def last_page_fill(reader, pdf):
    """How far down the last page the text reaches, in percent, or None.

    fit_pages.py's own measurement, reused. The Everforth render filled 45% of page 1
    with a padded skills block and left page 2 half empty, and the page count - two,
    against a budget of two - reported it as a success.

    Args:
        reader: reads the PDF (ports.pdf.PdfInspector).
        pdf: the PDF.

    Returns:
        The percentage, or None when it cannot be measured.
    """
    try:
        pages = reader.measure(pdf)
    except Exception:                               # noqa: BLE001 - reported, never fatal
        return None
    return fill_percent(pages[-1]) if pages else None


def measured(reader, pdf, budget, counted):
    """The page line for a PDF just compiled (domain.render.page_report).

    Args:
        reader: counts and measures it (ports.pdf.PdfInspector).
        pdf: the PDF.
        budget: the plan's page budget.
        counted: gains (the PDF's name, its pages, the budget) when its pages counted.

    Returns:
        The line. Reads the PDF twice: its page count and its last page's fill.
    """
    name, count = os.path.basename(pdf), page_count(reader, pdf)
    if count is not None:
        counted.append((name, count, budget))
    return page_report(name, count, budget, last_page_fill(reader, pdf))


def basename_for(plan_for, company_of, src, store):
    """The outputs' basename when the call names none: the person, then the employer.

    mode-tailor.md lays an application out as `<Name>_<Company>_Resume.*`.

    Args:
        plan_for: builds the plan for a variant.
        company_of: (src, store) -> the posting's employer or None.
        src: the resume.json.
        store: its career.

    Returns:
        The basename, safe as a file name.
    """
    base = safe_name(plan_for("presentation")["name"])
    company = company_of(src, store)
    return f"{base}_{safe_name(company)}" if company else base


def render_resume(src, out_dir, *, load, **options):
    """Render the resume.json at `src` into `out_dir`.

    A frozen application's resume.json builds from today's career, so a render into or
    from it would overwrite the PDF that was sent with one that was not. Ship refused
    this; render did not, until the final review.

    Args:
        src: the resume.json.
        out_dir: where the files go; it exists.
        load: loads and checks the resume.json (load_resume bound to its ports).
        **options: render_loaded's keyword arguments.

    Returns:
        A RenderResult.

    Raises:
        RenderStopped: the application is frozen, or render_loaded stopped.
        ShortError: from `load`.
    """
    from ..guards import frozen_refusal

    refusal = frozen_refusal(out_dir, os.path.dirname(os.path.abspath(src)))
    if refusal:
        raise RenderStopped("frozen", refusal, 1)
    return render_loaded(load(src), src, out_dir, **options)


def render_loaded(loaded, src, out_dir, *, fmt="all", region=None, profile=None,
                  template=None, want_pdf=False, name=None, today, profiles, company_of,
                  tex, reader, outputs):
    """Render a resume.json already loaded, without asking whether it is frozen.

    Args:
        loaded: the resume.json and its career (load_resume.LoadedResume).
        src: the resume.json's path, which company_of reads the application from.
        out_dir: where the files go; it exists.
        fmt: latex | txt | all - the file kinds.
        region: overrides the file's region profile.
        profile: the variant; by default the file's own format, else presentation.
        template: the visual theme; None is the default one.
        want_pdf: compile the .tex.
        name: the outputs' basename; by default the person's name and the company.
        today: the date a declaration is signed on.
        profiles: the region profiles (ports.profiles.Profiles).
        company_of: (src, store) -> the posting's employer or None.
        tex, reader, outputs: compile the .tex, measure the PDF and write the files
            (ports.tex.TexCompiler, ports.pdf.PdfInspector, ports.outputs.RenderOutputs).

    Returns:
        A RenderResult. Writes a .tex and a .txt per target, and a PDF with `want_pdf`.

    Raises:
        RenderStopped: a KeyError from the builder, or a `fmt` naming no file kind.
    """
    store, doc = loaded.store, loaded.doc

    def plan_for(variant):
        return build(store, doc, profiles=profiles, today=today, region=region, fmt=variant)

    base = name or basename_for(plan_for, company_of, src, store)

    # The file's own `format` is the variant when the call names none: the final review
    # found it, documented as the place to choose, doing nothing - --ats-max or
    # presentation, whatever the file said.
    targets = select_targets(fmt, profile or doc.get("format"))

    written, warnings, notes, pages, held, counted, withheld = [], [], [], [], {}, [], []
    first, unverified = None, False
    for variant, kind, stem in targets:
        try:
            rendered = plan_for(variant)
        except KeyError as e:
            raise RenderStopped("plan", str(e), 1) from None
        if first is None:
            first = rendered
        warnings.extend(f"[{variant}/{kind}] {w}" for w in rendered["warnings"])
        withheld.extend(rendered["withheld"])
        path = os.path.join(out_dir, stem.format(name=base))

        if kind == "latex":
            tex_path = path + ".tex"
            outputs.write_text(tex_path, emit_latex.emit(rendered, template=template))
            written.append(tex_path)
            if want_pdf:
                pdf, note = tex.compile_pdf(tex_path, out_dir)
                notes.append(note)
                if pdf:
                    written.append(pdf)
                    held[pdf] = variant
                    pages.append(measured(reader, pdf, rendered["pages"], counted))
                else:
                    unverified = True
        elif kind == "txt":
            txt = path + ".txt"
            outputs.write_text(txt, emit_text.emit(rendered), encoding="ascii",
                               errors="replace")
            written.append(txt)
        else:
            raise RenderStopped("format", kind, 2)

    assert first is not None, "select_targets names at least one target"
    return RenderResult(view=first["view"], profile=first["profile"], budget=first["pages"],
                        template=template or themes.DEFAULT, written=tuple(written),
                        pages=tuple(pages), notes=tuple(notes),
                        warnings=tuple(dict.fromkeys(warnings)),
                        variants=held, unverified=unverified, measured=tuple(counted),
                        withheld=tuple(dict.fromkeys(withheld)))
