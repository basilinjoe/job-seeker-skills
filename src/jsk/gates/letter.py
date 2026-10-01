#!/usr/bin/env python3
"""The letter check's number check, at the gate's old module path.

The command is adapters/cli/gates/letter.py, the check application/gates/letter.py and its
rules over the words domain/gates/letter_rules.py; this module keeps the path, the letter's
reader, the number check that reads the career, and the names callers and tests reach
through it (Ruling 4 of the onion design).

mode-tailor.md had the model write a letter nobody checked, beside a resume whose every
numeral must trace to a current metric version. A number in the letter is the same claim
in a looser paragraph, so it is asked the same question:

  FAIL  over 250 words in the body - the salutation line, anything above it, and the
        closing ("Sincerely,", "Best regards,") with everything under it are not counted
  FAIL  a numeral (numbers.numerals: a year, p95, ISO 27001 are not claims) that no
        current version of a metric cited by a bullet the resume renders holds - untraced;
        one only a replaced version holds - superseded; one only a bullet the resume
        withholds (below its floor) or an unconfirmed bullet states - unconfirmed
  FAIL  "N years of X" beyond what the roles behind the projects holding X cover
  FAIL  a placeholder, a sentence stopping on "the"/"by"/..., enthusiasm padding
  WARN  check_prose's "cut on sight" phrases; a sentence stopping on "to"/"with"/...

A numeral inside quotation marks that posting.md (beside resume.json) holds verbatim is
the posting's words, not a claim, and is skipped. Whether each sentence is true of the
career is not provable without reading it as a person would, so it is not attempted.
"""
import datetime
import sys

from ..domain.gates.letter_rules import LIMIT as LIMIT
from ..domain.gates.letter_rules import WORD as WORD
from ..domain.gates.letter_rules import SALUTATION as SALUTATION
from ..domain.gates.letter_rules import CLOSING as CLOSING
from ..domain.gates.letter_rules import QUOTED as QUOTED
from ..domain.gates.letter_rules import PADDING as PADDING
from ..domain.gates.letter_rules import body as body
from ..domain.gates.letter_rules import paragraphs as paragraphs
from ..domain.gates.letter_rules import length_lines as length_lines
from ..domain.gates.letter_rules import prose_lines as prose_lines
from ..domain.gates.letter_rules import unquote_posting as unquote_posting
from ..domain.gates.report import line as line


def read(path):
    """The letter's text; .md is read as written - its markup is not words. Lenient on a
    stray byte, as the gates are, but a BOM is stripped: kept, it hid the salutation."""
    from ..domain.record.parsed import normalise

    with open(path, encoding="utf-8", errors="replace") as fh:
        return normalise(fh.read())


def years_lines(store, text, today):
    """(findings, text with each "N years of <label>" blanked): record.py's years check,
    as a failure - in a letter nothing else stands behind the number."""
    from ..graph.named import experience_of, holdings
    from .record import YEARS, Vocabulary, curie

    vocabulary, held, out = Vocabulary(store), None, []
    for m in YEARS.finditer(text):
        label = next((lab for lab, pat in vocabulary.patterns if pat.match(text[m.end():])),
                     None)
        if label is None:
            continue                  # not a career label: the numeral is traced as any other
        held = holdings(store) if held is None else held
        concepts = vocabulary.labels[label]
        months = max(experience_of(store, c, today, held)[0] for c in concepts)
        claimed = int(m.group(1))
        if claimed * 12 > months:
            out.append(line("years-overstated", "letter",
                            f"claims {claimed} years of {label}; the roles behind the projects "
                            f"holding it cover {months // 12}y{months % 12}m",
                            f"state what the roles cover (`jsk kb query experience "
                            f"{curie(sorted(concepts)[0])}`)"))
        text = text[:m.start()] + " " * (m.end() - m.start()) + text[m.end():]
    return out, text


def number_lines(text, doc, store, posting=None, today=None):
    """FAIL lines for each numeral the application cannot stand on - see the docstring."""
    from ..domain import ontology as O
    from ..infra.oxigraph import record as R
    from ..resume import short
    from ..domain.resume.constants import PROVENANCE_RANK  # the floor as the render reads it
    from ..domain.record.career import Career
    from . import numbers
    from .record import career_refusal, curie

    today = today or datetime.date.today()
    refusal = career_refusal(store)
    unsound = [refusal] if refusal else short.shape(doc) or short.ids(doc, store)
    if unsound:
        return [line("record-unsound", "resume.json",
                     f"it does not pass the record gate ({len(unsound)} failures), so no number "
                     "can be traced through it", "run `jsk resume check` on it and fix that first")]
    career = Career(store.graph(R.KB))
    floor = PROVENANCE_RANK.get(doc.get("floor", "confirmed"), 3)

    def clears(s):
        return PROVENANCE_RANK.get(career.status(s), 0) >= floor

    live = career.live("Achievement")
    alive = set(live)
    selected = [O.K + i for i in doc["bullets"] if O.K + i in alive]
    rendered = [b for b in selected if clears(b) and clears(career.get(b, "project"))]
    unsure = [b for b in live if b not in rendered
              and (b in selected or career.status(b) != "confirmed")]
    words, cites, versions = numbers.facts(store)

    def held(bullets, current):
        return {n for b in bullets for m in cites.get(b, ()) for _, nums, until
                in versions.get(m, []) if (until is None) == current for n in nums}

    pool = held(rendered, True)
    closed = [(until, v, nums) for b in rendered for m in cites.get(b, ())
              for v, nums, until in versions.get(m, []) if until is not None]
    out, text = years_lines(store, unquote_posting(text, posting), today)
    reported = set()
    for value, suffix, shown in numbers.numerals(text):
        if shown in reported or numbers.covered(value, suffix, pool):
            continue
        reported.add(shown)
        whose = next((b for b in unsure if numbers.covered(value, suffix, held([b], True))
                      or any(numbers.covered(value, suffix, {v})
                             for v, _, _ in numbers.numerals(words.get(b, "")))), None)
        old = sorted((until, v) for until, v, nums in closed
                     if numbers.covered(value, suffix, nums))
        if whose:
            ident = whose[len(O.K):]
            out.append(line("number-unconfirmed", "letter",
                            f"'{shown}' is only in {ident}, which the resume does not render "
                            f"(provenance '{career.status(whose)}')",
                            f"confirm {ident} with the person (`jsk kb confirm`) before any "
                            "letter or resume states it - or cut the number"))
        elif old:
            until, v = old[-1]
            out.append(line("number-superseded", "letter",
                            f"'{shown}' is {curie(v)}'s number, replaced on {until}",
                            f"state the current number - `jsk kb show {curie(v.rsplit('.v', 1)[0])}`"))
        else:
            out.append(line("number-untraced", "letter",
                            f"'{shown}' is in no current metric version a bullet on the resume "
                            "cites", "use a number the resume states, or ask the person for the "
                            "figure and its source and add it to the career first"))
    return out


def main(argv=None):
    """The check, as an exit code (adapters.cli.gates.letter.main).

    Args:
        argv: the arguments alone; by default sys.argv's.

    Returns:
        The exit code. Prints the verdict.
    """
    from ..adapters.cli.gates.letter import main as letter

    return letter(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.gates.letter", "jsk letter check"))
