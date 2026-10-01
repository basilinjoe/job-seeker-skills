"""`jsk resume check` as a use case: the record, parse, prose and layout gates over one render.

The same gates jsk-verifier.md runs, in its order - record, parse, prose, layout - and the
render gate after them, which nothing here can run and which is said out loud instead.

It is file-driven rather than a fixed list of five commands, because the render profile
decides which files exist: every render writes <name>_Resume.{tex,pdf} beside
<name>_Resume_ATS.txt, and --ats-max changes which variant that one PDF holds -
strict_for() reads which from the PDF, not the name.

Each step comes back as a GateStep holding the gate's own output and the counts and page
measurements the summary restates, as fields: the summary used to read them back out of
the text with regular expressions. It prints nothing: adapters/cli/gates/check.py does.
"""
import glob
import os
from dataclasses import dataclass

from ...domain.render.page_report import page_report
from .result import GateResult, GateStopped

DOC_GATES = [
    ("parse gate", "check_ats.py", (".pdf", ".txt")),
    ("prose gate", "check_prose.py", (".tex", ".txt")),
]

# The glob jsk-verifier.md already tells the agent to use when a file name is not
# given. render_resume.py's stems all contain `_Resume`, so this finds a render and
# nothing else that happens to be sitting in the directory.
RENDERED = "*_Resume*"

# The name the skill writes beside a render, and what `--record` defaults to. Named
# rather than searched: a directory holding two records has no way to say which one
# the documents came from, and guessing would put a passing record gate against a
# resume it never described.
DEFAULT_RECORD = "resume.json"


@dataclass(frozen=True)
class GateStep:
    """One step of `jsk resume check`: which gate, how it was called, and what it said."""

    gate: str
    command: str | None
    status: str                 # PASS, FAIL, ERROR, SKIPPED or UNVERIFIED
    exit: int | None            # None for the render gate, which nothing runs
    output: str                 # everything the gate printed, verbatim
    counts: tuple | None = None     # (failures or None, warnings) from its count line
    pages: tuple = ()               # (PDF name, pages, budget) for each PDF measured
    withheld: tuple = ()            # `jsk resume ship`'s render: each id held below the floor
    fitted: str | None = None       # `jsk resume ship`'s fit: what it came to, as its line says it


def step(gate, command, code, output, outcome=None):
    """The GateStep for a gate that ran.

    Args:
        gate: its label, e.g. "parse gate".
        command: how it was called, as the heading shows it.
        code: its exit code.
        output: what it printed.
        outcome: what it returned - a GateResult, the GateStopped it stopped with, or None.

    Returns:
        The GateStep: PASS, FAIL or ERROR by exit code, and SKIPPED for a gate that says
        it did not run (the layout gate without pymupdf) - a failure either way.
    """
    status = {0: "PASS", 1: "FAIL"}.get(code, "ERROR")
    if code == 1 and isinstance(outcome, GateStopped) and outcome.kind == "skipped":
        status = "SKIPPED"
    counts = ((len(outcome.fails), len(outcome.warns)) if isinstance(outcome, GateResult)
              else None)
    return GateStep(gate, command, status, code, output, counts)


def skipped_gate(gate, command, why):
    """A gate that had nothing to read. Same wording as `jsk resume check`, deliberately.

    Args:
        gate: its label.
        command: the script it would have run.
        why: what was missing.

    Returns:
        A SKIPPED GateStep exiting 1.
    """
    return GateStep(gate, command, "SKIPPED", 1,
                    f"SKIPPED - {why}\n  A gate that did not run is not a gate "
                    f"that passed.\n")


def rendered_documents(out_dir, extensions, only=None):
    """The files a render left in `out_dir` that one gate reads, in a fixed order.

    `only` narrows it to named paths. A directory keeps every earlier render, so
    `jsk resume ship --ats-max` after a default ship left both PDFs beside each other, and
    gating the directory failed a run on a file it never made.

    Args:
        out_dir: the render's directory.
        extensions: the kinds of file the gate reads, in the order to read them.
        only: the paths to keep, or None for every render.

    Returns:
        The paths, by extension and then by name. Lists the directory.
    """
    keep = None if only is None else {os.path.normcase(os.path.abspath(p)) for p in only}
    found = []
    for ext in extensions:
        found.extend(p for p in sorted(glob.glob(os.path.join(out_dir, RENDERED + ext)))
                     if keep is None or os.path.normcase(os.path.abspath(p)) in keep)
    return found


def strict_for(path, *, pdf_variant, tex_variant):
    """Whether a rendered document is held to the ATS-maximal rules.

    A PDF says which variant it holds in its own metadata (jsk-variant:), because the
    ATS PDF no longer carries `_ATS` in its name - that was the name a recruiter read on
    the file. A PDF whose engine wrote no metadata falls back to the .tex it was
    compiled from, whose hypersetup line carries the same keyword; one rendered before
    the marker existed, and every .txt, still go by the name.

    Args:
        path: the document.
        pdf_variant: pdf -> the variant its metadata names, or None.
        tex_variant: tex -> the variant its hypersetup line names, or None - also for a
            .tex that is missing or will not read.

    Returns:
        True for the ATS-maximal variant.
    """
    if path.lower().endswith(".pdf"):
        variant = pdf_variant(path)
        if variant is None:
            variant = tex_variant(os.path.splitext(path)[0] + ".tex")
        if variant is not None:
            return variant == "ats-maximal"
    return "_ATS" in os.path.basename(path)


def render_section(out_dir, pages, only=None, *, measure):
    """The gate this command will never run, said out loud.

    Every other line of output here is a checker's. This one is not, and it is the
    reason the command can be trusted: a resume whose parse and prose gates passed
    has still been read by nobody. `mode-ship.md` calls this the gate nobody else
    can run, and a `jsk resume check` that exited 0 without saying so would teach every
    caller that the render gate is decorative - which is exactly the lesson
    render_resume.py's UNVERIFIED exit was added to unteach.

    Args:
        out_dir: the render's directory.
        pages: the page budget to measure each PDF against, or None.
        only: the paths to keep (rendered_documents), or None.
        measure: pdf -> (pages or None, last page's fill or None); raises ImportError
            when the measuring code will not load.

    Returns:
        The render gate's GateStep: UNVERIFIED, with no exit code. Reads each PDF under
        --pages.
    """
    lines, measured = [], []
    pdfs = rendered_documents(out_dir, (".pdf",), only)
    if pages is not None:
        if not pdfs:
            lines.append(f"  pages  budget {pages}, not measured - there is no PDF "
                         f"to count")
        else:
            # render_resume.py's own line, reused rather than restated. Over budget
            # is reported and not failed there because fit_pages.py owns that
            # verdict and is the only thing that can act on it; two places printing
            # one measurement in different words is how they start disagreeing.
            try:
                counted = [(pdf, *measure(pdf)) for pdf in pdfs]
            except ImportError as exc:
                lines.append(f"  pages  budget {pages}, not measured - "
                             f"render_resume.py would not load: {exc}")
            else:
                for pdf, count, fill in counted:
                    lines.append(page_report(os.path.basename(pdf), count, pages, fill))
                    if count is not None:
                        measured.append((os.path.basename(pdf), count, pages))
    if pdfs:
        lines.append(f"UNVERIFIED - open {os.path.basename(pdfs[0])} and read every page.")
    else:
        lines.append(f"UNVERIFIED - there is no PDF in {out_dir} for anyone to read.")
    lines.append("  Does it look right as a whole, and is it true? The layout gate measures")
    lines.append("  fonts, tofu, headings, dates and paper; nothing above can see a verb that")
    lines.append("  overstates ownership. The gates that passed say nothing about this one.")
    return GateStep("render gate", None, "UNVERIFIED", None, "\n".join(lines) + "\n",
                    pages=tuple(measured))


def run_gates(out_dir, record, pages=None, limit=None, record_gate=True, only=None, *,
              run, strict, measure):
    """Every `jsk resume check` step over one directory, the render gate last.

    `jsk resume ship` and `jsk app freeze` run these gates rather than a second copy of them:
    three commands that each decided what "the mechanical gates" meant would be three
    chances to disagree about it.

    `record_gate=False` is for `jsk resume ship`, which has just run that gate on the same file
    and stopped had it failed. The record gate reads the career itself, so there is no
    claims gate beside it: the claims gate joined a copy of the career with the career,
    and the copy went with the URS record (2026-09-25).

    Args:
        out_dir: the render's directory.
        record: the resume.json the documents rendered from, or None.
        pages: the page budget, or None.
        limit: --max-findings for the record gate, or None for its default.
        record_gate: run the record gate.
        only: the documents to gate (rendered_documents), or None for every render.
        run: (script, args) -> (exit code, output, outcome) for one gate, with a gate that
            raised already turned into its exit code and output.
        strict: path -> whether that document is held to the ATS-maximal rules.
        measure: pdf -> (pages or None, last page's fill or None), for the render gate
            (render_section).

    Returns:
        The GateSteps, in the order run.
    """
    steps = []
    if record_gate and record is None:
        steps.append(skipped_gate(
            "record gate", "record.py",
            f"no record given, and no {DEFAULT_RECORD} in {out_dir}; "
            f"pass --record <resume.json>."))
    elif record_gate:
        record_args = [record] + (["--max-findings", str(limit)] if limit is not None
                                  else [])
        steps.append(step("record gate", " ".join(["record.py"] + record_args),
                          *run("record.py", record_args)))

    for gate, script, extensions in DOC_GATES:
        found = rendered_documents(out_dir, extensions, only)
        if not found:
            steps.append(skipped_gate(gate, script,
                                      f"no {' or '.join(extensions)} render in {out_dir}."))
            continue
        for path in found:
            # The same rule render_resume.py prints after a render: the ATS-maximal
            # variant is the one aimed at a parser, so it is the one held to the
            # ATS-maximal rules.
            held = script == "check_ats.py" and strict(path)
            command = f"{script} {os.path.basename(path)}" + (" --strict" if held else "")
            steps.append(step(gate, command,
                              *run(script, [path] + (["--strict"] if held else []))))

    # The PDF alone: it reads the region and budget from the record the render used.
    pdfs = rendered_documents(out_dir, (".pdf",), only)
    if not pdfs:
        steps.append(skipped_gate("layout gate", "layout.py", f"no .pdf render in {out_dir}."))
    for path in pdfs:
        layout_args = ([path] + (["--record", record] if record else [])
                       + (["--pages", str(pages)] if pages else []))
        steps.append(step("layout gate", f"layout.py {os.path.basename(path)}",
                          *run("layout.py", layout_args)))

    steps.append(render_section(out_dir, pages, only, measure=measure))
    return steps
