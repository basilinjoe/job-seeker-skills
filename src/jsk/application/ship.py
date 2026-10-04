"""The resume_ship tool as a use case: the record gate, the render, the fit and the gates, in that order.

The three commands mode-ship.md used to have an agent run by hand - validate, render with
--pdf, gates - in one process, each stopping the next. A record that fails its gate is
never rendered: rendering it would produce a PDF that looks sendable and is not.

Every step is an existing use case run through the adapter that prints it, so none of
their verdicts is restated here: the record gate is what the resume_check tool runs, the render
the resume_render tool's, the fit the resume_fit tool's and the gates run_gates'. What ship reads of them - the
files the render wrote, its page counts, the levers the fit applied - it reads off the
RenderResult and the FitResult, never off what they printed. It prints nothing:
adapters/cli/ship.py does.
"""
import os
from dataclasses import dataclass

from ..domain.render.fit_levers import describe
from .gates.run_gates import GateStep, run_gates, step


@dataclass(frozen=True)
class ShipResult:
    """One ship: the record and directory it was given, and every step, in the order run."""

    record: str
    out_dir: str
    steps: tuple                # GateStep, the render gate last
    exit: int                   # 0 or 1


def ran(gate, command, code, output, **fields):
    """The GateStep for a step ship ran itself, by its exit code.

    Args:
        gate: its label.
        command: how it was called.
        code: its exit code.
        output: what it printed.
        **fields: the GateStep's counts, pages, withheld or fitted.

    Returns:
        The GateStep: PASS, FAIL or ERROR by exit code, SKIPPED for a failure whose output
        says it did not run.
    """
    status = {0: "PASS", 1: "FAIL"}.get(code, "ERROR")
    if code == 1 and output.startswith("SKIPPED"):
        status = "SKIPPED"
    return GateStep(gate, command, status, code, output, **fields)


def not_rendered(why):
    """The render gate's step when ship stopped before there was anything to read.

    render_section() would look in the output directory, and a PDF left there by an
    earlier run would be named as the thing to read - a document this run never made.

    Args:
        why: what stopped the ship.

    Returns:
        The UNVERIFIED GateStep, with no exit code.
    """
    return GateStep("render gate", None, "UNVERIFIED", None,
                    f"UNVERIFIED - {why}, so nothing was rendered and there is no\n"
                    f"  PDF from this run for anyone to read.\n")


def rendered_step(command, code, output, result):
    """The render's step, its warnings, pages and withheld lines read off its result.

    Args:
        command: how the render was called.
        code: its exit code.
        output: what it printed.
        result: its RenderResult, or None when it stopped.

    Returns:
        The GateStep.
    """
    if result is None:
        return ran("render", command, code, output)
    return ran("render", command, code, output,
               counts=(None, len(result.warnings)) if result.warnings else None,
               pages=result.measured, withheld=result.withheld)


def fit_one(tex, budget, count, out_dir, *, fitter, tex_engine, page_count, outputs):
    """Fit one render over its budget, move the fit over the render and recompile it.

    Args:
        tex: the render's .tex.
        budget: the page budget to fit it to.
        count: the pages the render counted.
        out_dir: where the render compiled, which the fitted .tex compiles into too.
        fitter: (args) -> (exit code, output, FitResult or None) for the resume_fit tool's arguments.
        tex_engine: compiles the fitted .tex as the render compiled its own
            (ports.tex.TexCompiler).
        page_count: pdf -> its pages, or None.
        outputs: removes an earlier fit's file and moves the fit over the render
            (ports.outputs.RenderOutputs).

    Returns:
        The fit's GateStep. May replace the .tex and its PDF.
    """
    fitted = os.path.splitext(tex)[0] + "-fitted.tex"
    outputs.discard(fitted)                     # an earlier fit's is not this one's
    fit_args = [tex, "--target-pages", str(budget)]
    command = " ".join(["fit_pages.py", os.path.basename(tex)] + fit_args[1:])
    code, output, result = fitter(fit_args)
    output += "" if output.endswith("\n") else "\n"
    if code == 1:
        over = result.over if result is not None and result.outcome == "floor" else None
        return GateStep("fit", command, "OVER BUDGET", None,
                        output + "\nkept the unfitted render; nothing was cut - that is "
                                 "the author's call, with a reason\n",
                        fitted=(f"over by ~{over} line{'' if over == 1 else 's'} at the floors"
                                if over is not None and over >= 0 else None))
    if code != 0 or not os.path.isfile(fitted):
        # Exit 0 with nothing written is a fitter that measured the render inside the
        # budget the render measured it over. Two counts of one document disagreeing
        # is a broken toolchain, and neither count can be trusted.
        return ran("fit", command, code if code else 2, output + (
            "" if code else f"FAIL  fit_pages.py found {os.path.basename(tex)} inside "
                            f"{budget} pages; the render counted {count}\n"))
    levers = describe(result.applied) if result is not None and result.applied else ""
    outputs.replace(fitted, tex)
    built, note = tex_engine.compile_pdf(tex, out_dir)
    if not built:
        return ran("fit", command, 2, output + (
            f"\nRENDER FAILED - {os.path.basename(tex)} was fitted and did not "
            f"recompile:\n  {note}\n"))
    now = page_count(built)
    line = (f"fit: {levers or 'levers applied'}, "
            f"{now if now is not None else 'unmeasured'} page{'' if now == 1 else 's'}")
    return ran("fit", command, 0, output + (
        f"\nmoved {os.path.basename(fitted)} over {os.path.basename(tex)} and "
        f"recompiled it ({note}); the gates below read the fitted render.\n{line}\n"),
        fitted=line)


def fit_steps(wrote, rendered, pages, out_dir, **ports):
    """The fit step: each PDF the render put over its budget, fitted. [] when none is.

    The Arrow run (2026-09-29) spent 3 minutes and 13 turns here by hand: the resume_fit tool
    three times, three confirmed bullets cut, then `mv`, `tectonic` and the resume_check tool.
    The first fit had already reached 2 pages at 0.6in margins, inside the 0.5in floor.

    The fitter is deterministic and writes one file, `<stem>-fitted.tex`, and only when
    the levers reached the budget inside the floors. That file is moved over the
    render's .tex and compiled the way the render compiled, so the PDF the gates then
    read is built the way the render built it. At the floors, nothing is written and the
    unfitted render is kept: cutting evidence is the author's call. The page count stays
    reported and not failed, as the render reports it - so the step's exit is None then,
    and the verdict is what it was before ship fitted anything.

    Args:
        wrote: the files the render wrote, as ship names them.
        rendered: the RenderResult.
        pages: ship's --pages, else None for the render's own budget - which is
            `ats_pages` under --ats-max: the one the render's page line was measured
            against.
        out_dir: the render's directory.
        **ports: fit_one's fitter, tex_engine, page_count and outputs.

    Returns:
        The fit GateSteps, one per PDF fitted.
    """
    measured = {name: (count, budget) for name, count, budget in rendered.measured}
    steps = []
    for pdf in (p for p in wrote if p.lower().endswith(".pdf")):
        name = os.path.basename(pdf)
        tex = os.path.splitext(pdf)[0] + ".tex"
        if name not in measured or not os.path.isfile(tex):
            continue                              # unmeasured: nothing to fit against
        count, budget = measured[name][0], pages or measured[name][1]
        if count > budget:
            steps.append(fit_one(tex, budget, count, out_dir, **ports))
    return steps


def ship(record, out_dir, *, ats_max=False, template=None, pages=None, fit=True,
         run, render, fitter, tex_engine, page_count, outputs, rel, strict, measure):
    """Record gate, render, fit, mechanical gates - stopping at a failure.

    A legacy URS record is turned away by the record gate itself, with the resume_select tool (jsk mcp)
    as the fix, before anything renders.

    Args:
        record: the resume.json.
        out_dir: the directory to render into.
        ats_max: render the ATS-maximal variant.
        template: the visual theme, or None for the default.
        pages: the page budget, or None for the render's own.
        fit: fit each render over its budget before the gates read it.
        run: (script, args) -> (exit code, output, outcome) for one gate, as run_gates
            takes it.
        render: (args) -> (exit code, output, RenderResult or None) for the resume_render tool's
            arguments.
        fitter: (args) -> (exit code, output, FitResult or None) for the resume_fit tool's.
        tex_engine: recompiles a fitted .tex (ports.tex.TexCompiler).
        page_count: pdf -> its pages, or None.
        outputs: moves a fit over the render (ports.outputs.RenderOutputs).
        rel: (path, root) -> the path relative to root, as the render names its files.
        strict: path -> whether that document is held to the ATS-maximal rules.
        measure: pdf -> (pages or None, last page's fill or None), for the render gate.

    Returns:
        A ShipResult. Renders into `out_dir`, and may fit what it rendered.
    """
    steps = [step("record gate", f"record.py {record}", *run("record.py", [record]))]
    if steps[0].exit != 0:
        # A number the career replaced renders as a sendable PDF with that number in it.
        steps.append(not_rendered("the record gate did not pass"))
        return shipped(record, out_dir, steps)
    render_args = [record, "--out", out_dir, "--pdf"]
    render_args += ["--ats-max"] if ats_max else []
    render_args += ["--template", template] if template else []
    code, output, rendered = render(render_args)
    steps.append(rendered_step(" ".join(["render_resume.py"] + render_args), code, output,
                               rendered))
    if code != 0:
        steps.append(not_rendered("the render did not finish"))
        return shipped(record, out_dir, steps)
    # What the render wrote, and nothing an earlier ship left in the same directory, is
    # what this ship gates.
    wrote = [os.path.join(out_dir, rel(path, out_dir))
             for path in (rendered.written if rendered is not None else ())]
    if fit and rendered is not None:
        # Before the gates, so that what they read is what is sent.
        steps += fit_steps(wrote, rendered, pages, out_dir, fitter=fitter,
                           tex_engine=tex_engine, page_count=page_count, outputs=outputs)
    steps += run_gates(out_dir, record, pages, None, False, wrote, run=run, strict=strict,
                       measure=measure)
    return shipped(record, out_dir, steps)


def shipped(record, out_dir, steps):
    """The ShipResult over `steps`.

    A step's own exit 2 - an ERROR from a gate that raised, or a render refusing a file -
    is a failure of this ship, not a mistake in how it was called, so the exit is 0 or 1.

    Returns:
        The ShipResult.
    """
    worst = max([s.exit for s in steps if s.exit is not None] or [0])
    return ShipResult(record, out_dir, tuple(steps), 1 if worst else 0)
