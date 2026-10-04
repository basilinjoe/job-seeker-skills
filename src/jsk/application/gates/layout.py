"""The layout gate over one PDF: its region and budget found, its lines read, then judged.

The rules are domain/gates/layout_rules.py's. This decides where the region and the page
budget come from - the flags, else the resume.json the PDF rendered from - and what a PDF
that will not open is. It prints nothing: adapters/entry/gates/layout.py says what it found.
"""
import os
from dataclasses import dataclass

from ...domain.gates.layout_rules import check
from .result import GateResult, GateStopped, unreadable


@dataclass(frozen=True)
class LayoutResult(GateResult):
    """The layout gate's verdict, with what its heading reports."""

    name: str
    region: str | None
    pages: int
    budget: int | None
    papers: tuple
    faces: tuple


def check_layout(path, *, region, budget, record, available, read_lines, plan_of):
    """Judge the layout of the PDF at `path`.

    Args:
        path: the PDF; it exists.
        region: the region whose paper it must be on, or None to ask the record.
        budget: the page budget, or None to ask the record.
        record: the ref of the target it rendered from - the caller finds the one its
            directory holds - or None.
        available: () -> whether a PDF reader is installed.
        read_lines: path -> (pages, Type3 font names), as ports.pdf.PdfInspector.lines.
        plan_of: (record, pdf) -> (region, page budget, None) from the plan the render
            built, or (None, None, why) when the record would not build.

    Returns:
        A LayoutResult, or an Unreadable when the PDF would not open. Reads the record
        when region or budget is missing.

    Raises:
        GateStopped: "skipped" (exit 1) when there is no PDF reader on this machine.
    """
    name = os.path.basename(path)
    if not available():
        raise GateStopped("skipped", name, 1)

    notes = []
    if record is not None and (region is None or budget is None):
        planned_region, planned_pages, why = plan_of(record, path)
        if why:
            notes.append(f"{os.path.basename(record)} unread, so no region or budget: {why}")
        region = region or planned_region
        budget = budget or planned_pages

    try:
        pages, type3 = read_lines(path)
    except Exception as exc:                       # noqa: BLE001 - the verdict, not a crash
        return unreadable(name, f"unreadable: {type(exc).__name__}: {exc}")
    fails, warns, faces, papers = check(pages, type3, region)
    return LayoutResult(fails=tuple(fails), warns=tuple(notes + warns), name=name,
                        region=region, pages=len(pages), budget=budget,
                        papers=tuple(papers), faces=tuple(faces))
