#!/usr/bin/env python3
"""The letter check: a cover letter, against the resume.json it goes out beside.

Usage: jsk check <cover-letter.txt|.md> --only letter --record <resume.json>
       python -m jsk.gates.letter <cover-letter.txt|.md> [--record <resume.json>]
       --record R    the application's resume.json; without it the number check is
                     SKIPPED, and a gate that did not run is a failure

Exit 0 = fit to send. Exit 1 = do not send this letter. Exit 2 = usage, or a
resume.json outside a workspace.

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
import os
import re
import sys

from ..cliutil import docstring_usage, wants_help
from .report import show

LIMIT = 250

# A word as a reader counts one: "event-driven", "40K", "62%" and "don't" are one each.
WORD = re.compile(r"[A-Za-z0-9]+(?:['’.,-][A-Za-z0-9]+)*")
SALUTATION = re.compile(r"^(dear|hi|hello|to whom)\b.{0,60}[,:]?$", re.I)
CLOSING = re.compile(r"^(sincerely|regards|best|best regards|kind regards|warm regards|"
                     r"many thanks|thanks|thank you|cheers|respectfully|"
                     r"yours(?: sincerely| faithfully| truly)?)[,.!]?$", re.I)
QUOTED = re.compile(r"\"([^\"\n]{1,200})\"|“([^”\n]{1,200})”")

# mode-tailor.md: "No enthusiasm padding." writing-rules.md's filler ("passionate about
# technology", "stayed current with industry trends") is this in a resume's clothes. A
# failure rather than a warning: in a letter there is no legitimate "thrilled".
PADDING = re.compile(r"\b(passionat\w*|excit(?:ed|ement|ing opportunity)|thrill\w*|"
                     r"delighted|eager\w*|dream (?:job|role|company)|perfect fit|"
                     r"stayed current with industry trends)\b", re.I)


def line(check, focus, detail, fix):
    from .record import line as record_line
    return record_line(check, focus, detail, fix)


def read(path):
    """The letter's text; .md is read as written - its markup is not words."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def body(text):
    """The paragraphs a reader counts: between the salutation and the closing."""
    lines = [ln.strip().lstrip("#").strip() for ln in text.splitlines()]
    start = next((i + 1 for i, ln in enumerate(lines) if ln and SALUTATION.match(ln)), 0)
    end = next((i for i, ln in enumerate(lines) if i >= start and CLOSING.match(ln)), len(lines))
    return "\n".join(lines[start:end]).strip()


def paragraphs(text):
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def length_lines(text):
    words = len(WORD.findall(body(text)))
    if words <= LIMIT:
        return [], words
    return [line("too-long", "letter", f"{words} words in the body; the limit is {LIMIT}",
                 "cut to the strongest match, one piece of evidence with its metric and the "
                 "gap in one line - mode-tailor.md")], words


def prose_lines(text):
    """(fails, warns): the check_prose rules that hold for a letter. Its third-person,
    opens-on-a-verb, duplicate, long and unquantified bullet rules do not - a letter is
    written in the first person, to someone, in sentences."""
    from .check_prose import BANNED, dangling_tail, placeholders

    fails = [line("placeholder", "letter", f, "write the words it stands for, or drop them")
             for f in placeholders(text)]
    warns = []
    for para in paragraphs(body(text)):
        tail = dangling_tail(para)
        if tail:
            word, hard = tail
            (fails if hard else warns).append(line(
                "unfinished", "letter", f"a sentence stops on {word!r}: {para[-60:]!r}",
                "finish the sentence"))
    seen = set()
    for m in PADDING.finditer(text):
        if m.group(0).lower() not in seen:
            seen.add(m.group(0).lower())
            fails.append(line("padding", "letter", f"{m.group(0)!r} is enthusiasm, not evidence",
                              "cut it; say what you did and what it moved"))
    lowered = text.lower()
    warns += [line("cut-on-sight", "letter", f"{p!r} - activity, not achievement",
                   "say what changed because of the work - writing-rules.md")
              for p in BANNED if p in lowered]
    return fails, warns


def unquote_posting(text, posting):
    """`text` with each quotation the posting holds verbatim blanked out."""
    if not posting:
        return text
    held = " ".join(posting.split()).casefold()

    def blank(m):
        said = " ".join((m.group(1) or m.group(2)).split()).casefold()
        return " " * len(m.group(0)) if said in held else m.group(0)
    return QUOTED.sub(blank, text)


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
    from ..graph import ontology as O
    from ..graph import record as R
    from ..resume import short
    from ..resume.build import PROVENANCE_RANK          # the floor as the render reads it
    from ..resume.career import Career
    from . import numbers
    from .record import career_refusal, curie

    today = today or datetime.date.today()
    refusal = career_refusal(store)
    unsound = [refusal] if refusal else short.shape(doc) or short.ids(doc, store)
    if unsound:
        return [line("record-unsound", "resume.json",
                     f"it does not pass the record gate ({len(unsound)} failures), so no number "
                     "can be traced through it", "run `jsk validate` on it and fix that first")]
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


def parse(argv):
    """(letter, record, problem)."""
    args, record, positional = list(argv), None, []
    while args:
        token = args.pop(0)
        if token == "--record":
            record = args.pop(0) if args else None
            if not record:
                return None, None, "--record needs a value\nfix:  --record applications/<dir>/resume.json"
        elif token.startswith("-"):
            return None, None, f"unknown flag: {token}\n{docstring_usage(__doc__)}"
        else:
            positional.append(token)
    if len(positional) != 1:
        return None, None, docstring_usage(__doc__)
    return positional[0], record, None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    if wants_help(argv):
        print(docstring_usage(__doc__))
        return 0
    path, record, problem = parse(argv)
    if problem:
        print(problem)
        return 2
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2
    if os.path.splitext(path)[1].lower() not in (".txt", ".md"):
        print(f"unsupported file type {os.path.splitext(path)[1]!r} - write the letter as "
              ".txt or .md")
        return 2
    text = read(path)
    fails, words = length_lines(text)
    more, warns = prose_lines(text)
    fails += more
    against = "nothing - no --record"
    if record is None:
        fails.append(line("numbers-skipped", "letter",
                          "SKIPPED - no --record, so no number in it was traced. A gate that "
                          "did not run is not a gate that passed",
                          "pass --record applications/<dir>/resume.json"))
    else:
        from ..resume import short

        try:
            doc = short.read(record)
            root = short.workspace(record)
        except short.ShortError as err:
            print(f"FAIL  {err}")
            print(f"fix:  {err.fix}")
            return 2
        try:
            import pyoxigraph  # noqa: F401
        except ImportError:
            print("FAIL  the number check needs pyoxigraph, and this Python has not got it - "
                  "`jsk doctor` says how to install it")
            return 1
        from ..graph import store as S

        beside = os.path.join(os.path.dirname(os.path.abspath(record)), "posting.md")
        posting = read(beside) if os.path.exists(beside) else None
        fails += number_lines(body(text), doc, S.load(root), posting)
        against = os.path.basename(record)
    print(f"checking: {os.path.basename(path)}   against: {against}")
    print(f"words: {words} (limit {LIMIT})")
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    show(fails, "FAIL", None)
    show(warns, "warn", None)
    print("\nPASS - fit to send" if not fails else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
