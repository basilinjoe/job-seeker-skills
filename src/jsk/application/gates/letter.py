"""The letter check over one cover letter: its length and prose judged, its numbers traced.

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

A numeral inside quotation marks that the posting's advert holds verbatim is the posting's
words, not a claim, and is skipped. The record is a target's selection's ref
(application/render/selection.py), and the advert is the lines its posting graph holds,
read from the store already loaded (P5 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md, 2026-10-02). A
resume.json and the posting.md beside it were read until 6.0, which reads neither
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2). Whether
each sentence is true of the career is not provable without reading it as a person would,
so it is not attempted.

The rules over the words are domain/gates/letter_rules.py's; the number check reads the
career through `queries` (ports.queries.RecordQueries). This reads the letter, loads the
career the target's workspace holds, and reads its advert for the quotes it may hold.
It prints nothing: adapters/cli/gates/letter.py says what it found.
"""
import os
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.gates.letter_rules import body, length_lines, prose_lines, unquote_posting
from ...domain.gates.report import line
from ...domain.record.writer import curie
from ..render.selection import shown_name
from .result import GateResult, GateStopped


@dataclass(frozen=True)
class LetterResult(GateResult):
    """The letter check's verdict, with what its heading reports."""

    name: str
    against: str        # the selection's graph, or why there was none
    words: int          # in the body, as the limit counts them


def check_letter(path, record, *, read, read_short, workspace, has_engine, career,
                 number_lines, today):
    """Check the cover letter at `path` against the target's selection it goes out beside.

    Args:
        path: the letter, a .txt or .md; it exists.
        record: the target's ref, or None - which fails the number check as SKIPPED.
        read: path -> a text file's contents, normalised (infra.documents.read_letter).
        read_short: ref -> the selection as a dict (compose.resume.read).
        workspace: ref -> the workspace root it names (compose.resume.workspace).
        has_engine: () -> whether the graph engine can be imported.
        career: root -> the loaded workspace (compose.resume.career).
        number_lines: (body, doc, store, posting, today) -> the number check's failures
            (compose.gates.number_lines).
        today: the date the years claims are measured to.

    Returns:
        A LetterResult. Reads the letter, and with a record its career and its advert.

    Raises:
        ShortError: no target's ref, no selection, or a store that will not open - each
            carrying .fix.
        GateStopped: "no-engine" (exit 1) when the graph engine is not installed.
    """
    text = read(path)
    fails, words = length_lines(text)
    more, warns = prose_lines(text)
    fails += more
    if record is None:
        fails.append(line("numbers-skipped", "letter",
                          "SKIPPED - no record, so no number in it was traced. A gate that "
                          "did not run is not a gate that passed",
                          "pass record=<stem> - the target it goes out beside"))
        against = "nothing - no record"
    else:
        doc = read_short(record)
        root = workspace(record)
        if not has_engine():
            raise GateStopped("no-engine", None, 1)
        store = career(root)
        posting = advert(record, store)
        fails += number_lines(body(text), doc, store, posting, today)
        against = shown_name(record)
    return LetterResult(fails=tuple(fails), warns=tuple(warns), name=os.path.basename(path),
                        against=against, words=words)


def advert(record, store):
    """The advert the letter may quote: the target's posting's stored lines, one to a line;
    None for a general resume, which answers no posting.

    Args:
        record: the target's ref.
        store: its workspace, loaded.
    """
    from ...domain.posting.lines import from_triples
    from ..render.selection import parse_ref

    found = parse_ref(record)
    parsed = store.parsed.get(f"{found[1]}/posting") if found is not None else None
    lines = from_triples(parsed.quads)[0] if parsed is not None else []
    return "\n".join(line.text for line in lines) or None


def years_lines(store, text, today, queries):
    """The record gate's years check, as a failure - in a letter nothing else stands
    behind the number.

    Args:
        store: the loaded workspace.
        text: the letter's body.
        today: the date the roles' months are measured to.
        queries: a RecordQueries over `store`.

    Returns:
        (findings, `text` with each "N years of <label>" blanked).
    """
    from ..record.holdings import experience_of, holdings
    from .record import YEARS, Vocabulary

    vocabulary, held, out = Vocabulary(queries), None, []
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
                            f"state what the roles cover (the career_query tool (jsk mcp))"))
        text = text[:m.start()] + " " * (m.end() - m.start()) + text[m.end():]
    return out, text


def number_lines(text, doc, store, posting, today, *, queries, state):
    """FAIL lines for each numeral the application cannot stand on (the module docstring).

    Args:
        text: the letter's body.
        doc: the target's selection, as a dict.
        store: the loaded workspace.
        posting: the advert's stored lines, or None.
        today: the date the years claims are measured to.
        queries: a RecordQueries over `store`.
        state: store -> the career and its log's State (infra.oxigraph.record.state).

    Returns:
        The FAIL lines. Runs the store's SELECTs.
    """
    from ...domain.record.career import Career
    from ...domain.record.state import KB
    from ...domain.resume import short
    from ...domain.resume.constants import PROVENANCE_RANK  # the floor as the render reads it
    from .record import career_refusal

    refusal = career_refusal(store, state)
    unsound = [refusal] if refusal else short.shape(doc) or short.ids(doc, store)
    if unsound:
        # It named "resume.json" until 2026-10-04, which 6.0 no longer reads (the P3 review).
        return [line("record-unsound", "selection",
                     f"the target's selection does not pass the record gate ({len(unsound)} "
                     "failures), so no number can be traced through it",
                     "run `jsk resume check <stem>` (or resumes/<name>) and fix that first")]
    career = Career(store.graph(KB))
    floor = PROVENANCE_RANK.get(doc.get("floor", "confirmed"), 3)

    def clears(s):
        return PROVENANCE_RANK.get(career.status(s), 0) >= floor

    live = career.live("Achievement")
    alive = set(live)
    selected = [O.K + i for i in doc["bullets"] if O.K + i in alive]
    rendered = [b for b in selected if clears(b) and clears(career.get(b, "project"))]
    unsure = [b for b in live if b not in rendered
              and (b in selected or career.status(b) != "confirmed")]
    out, text = years_lines(store, unquote_posting(text, posting), today, queries)
    return out + numeral_lines(text, career, rendered, unsure, queries)


def numeral_lines(text, career, rendered, unsure, queries):
    """A FAIL line for each numeral in `text` no current metric version behind a rendered
    bullet holds: unconfirmed, superseded or untraced, in that order of what it says.

    Args:
        text: the letter's body, its quotes of the posting and its years claims blanked.
        career: the career graph.
        rendered: the bullets the resume renders.
        unsure: the live bullets it withholds or that are not confirmed.
        queries: a RecordQueries over the loaded workspace; its metric facts are read.

    Returns:
        The FAIL lines.
    """
    from . import numbers
    from ...domain.gates.numbers import covered, numerals

    words, cites, versions = numbers.facts(queries)

    def held(bullets, current):
        return {n for b in bullets for m in cites.get(b, ()) for _, nums, until
                in versions.get(m, []) if (until is None) == current for n in nums}

    pool = held(rendered, True)
    closed = [(until, v, nums) for b in rendered for m in cites.get(b, ())
              for v, nums, until in versions.get(m, []) if until is not None]
    out, reported = [], set()
    for value, suffix, shown in numerals(text):
        if shown in reported or covered(value, suffix, pool):
            continue
        reported.add(shown)
        whose = next((b for b in unsure if covered(value, suffix, held([b], True))
                      or any(covered(value, suffix, {v})
                             for v, _, _ in numerals(words.get(b, "")))), None)
        old = sorted((until, v) for until, v, nums in closed if covered(value, suffix, nums))
        if whose:
            ident = whose[len(O.K):]
            out.append(line("number-unconfirmed", "letter",
                            f"'{shown}' is only in {ident}, which the resume does not render "
                            f"(provenance '{career.status(whose)}')",
                            f"confirm {ident} with the person (the career_confirm tool (jsk mcp)) before any "
                            "letter or resume states it - or cut the number"))
        elif old:
            until, v = old[-1]
            out.append(line("number-superseded", "letter",
                            f"'{shown}' is {curie(v)}'s number, replaced on {until}",
                            f"state the current number - the career_show tool (jsk mcp) on {curie(v.rsplit('.v', 1)[0])}"))
        else:
            out.append(line("number-untraced", "letter",
                            f"'{shown}' is in no current metric version a bullet on the resume "
                            "cites", "use a number the resume states, or ask the person for the "
                            "figure and its source and add it to the career first"))
    return out
