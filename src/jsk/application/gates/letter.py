"""The letter check over one cover letter: its length and prose judged, its numbers traced.

The rules over the words are domain/gates/letter_rules.py's; the number check, which reads
the career, is gates/letter.py's `number_lines`. This reads the letter, loads the career
the resume.json beside it sits in, and finds posting.md for the quotes it may hold. It
prints nothing: adapters/cli/gates/letter.py says what it found.
"""
import os
from dataclasses import dataclass

from ...domain.gates.letter_rules import body, length_lines, prose_lines
from ...domain.gates.report import line
from .result import GateResult, GateStopped


@dataclass(frozen=True)
class LetterResult(GateResult):
    """The letter check's verdict, with what its heading reports."""

    name: str
    against: str        # the resume.json's name, or why there was none
    words: int          # in the body, as the limit counts them


def check_letter(path, record, *, read, read_short, workspace, has_engine, career,
                 number_lines, today):
    """Check the cover letter at `path` against the resume.json it goes out beside.

    Args:
        path: the letter, a .txt or .md; it exists.
        record: the application's resume.json, or None - which fails the number check
            as SKIPPED.
        read: path -> a text file's contents, normalised (gates.letter.read).
        read_short: path -> the resume.json as a dict (resume.short.read).
        workspace: path -> the workspace root around it (resume.short.workspace).
        has_engine: () -> whether the graph engine can be imported.
        career: root -> the loaded workspace (resume.short.career).
        number_lines: (body, doc, store, posting, today) -> the number check's failures
            (gates.letter.number_lines).
        today: the date the years claims are measured to.

    Returns:
        A LetterResult. Reads the letter, and with a record its career and the posting.md
        beside it.

    Raises:
        ShortError: the resume.json will not read, sits in no workspace, or its store will
            not open - each carrying .fix.
        GateStopped: "no-engine" (exit 1) when the graph engine is not installed.
    """
    text = read(path)
    fails, words = length_lines(text)
    more, warns = prose_lines(text)
    fails += more
    if record is None:
        fails.append(line("numbers-skipped", "letter",
                          "SKIPPED - no --record, so no number in it was traced. A gate that "
                          "did not run is not a gate that passed",
                          "pass --record applications/<dir>/resume.json"))
        against = "nothing - no --record"
    else:
        doc = read_short(record)
        root = workspace(record)
        if not has_engine():
            raise GateStopped("no-engine", None, 1)
        store = career(root)
        beside = os.path.join(os.path.dirname(os.path.abspath(record)), "posting.md")
        posting = read(beside) if os.path.exists(beside) else None
        fails += number_lines(body(text), doc, store, posting, today)
        against = os.path.basename(record)
    return LetterResult(fails=tuple(fails), warns=tuple(warns), name=os.path.basename(path),
                        against=against, words=words)
