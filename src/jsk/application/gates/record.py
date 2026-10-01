"""The record gate over one short resume.json: its career loaded, then every finding asked.

The checks are gates/record.py's `findings`, over the career the file sits in. This reads
the file, loads its workspace and folds the warnings into the failures under --strict. It
prints nothing: adapters/cli/gates/record.py says what it found.
"""
import os
from dataclasses import dataclass

from .result import GateResult, GateStopped


@dataclass(frozen=True)
class RecordResult(GateResult):
    """The record gate's verdict, with the career revision it was checked against."""

    name: str
    revision: int | None        # the log's revision; None when the log has none


def record_gate(path, *, strict, read, workspace, has_engine, career, findings, state,
                today):
    """Check the short resume.json at `path` against the career it sits in.

    Args:
        path: the resume.json.
        strict: treat warnings as failures.
        read: path -> the file as a dict (resume.short.read).
        workspace: path -> the workspace root around it (resume.short.workspace).
        has_engine: () -> whether the graph engine can be imported.
        career: root -> the loaded workspace (resume.short.career).
        findings: (doc, store, today) -> (fails, warns) (gates.record.findings).
        state: store -> the career and its log's State (infra.oxigraph.record.state).
        today: the date the years claims are measured to.

    Returns:
        A RecordResult. Loads the workspace.

    Raises:
        ShortError: the file will not read, sits in no workspace, or its store will not
            open - each carrying .fix.
        GateStopped: "no-engine" (exit 1) when the graph engine is not installed.
    """
    doc = read(path)
    root = workspace(path)
    if not has_engine():
        raise GateStopped("no-engine", None, 1)
    store = career(root)
    fails, warns = findings(doc, store, today)
    if strict:
        fails, warns = fails + warns, []
    return RecordResult(fails=tuple(fails), warns=tuple(warns), name=os.path.basename(path),
                        revision=state(store).log_revision)
