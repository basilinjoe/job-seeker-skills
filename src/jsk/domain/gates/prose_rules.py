"""The prose gate's rules: whether a resume *reads*, over the paragraphs of its .tex or .txt.

These lived in check_prose.py beside the file reads and the printing. Judging needs only
the paragraphs, [(is_bullet, text)], so it is here and testable without a file;
check_prose.py opens the file and prints. The letter check (gates/letter.py) borrows
BANNED, ai_tells, dangling_tail and placeholders for a cover letter.
"""
import re

# Reused rather than reimplemented. numbers.numerals() already knows that a year, a
# glued designator (p95, S3, H100) and a standard's number (ISO 27001) are not claims,
# and a second detector without those exclusions would report a resume as unquantified
# because it mentions 2019.
from .numbers import numerals
from .report import Report

# --- fail: a resume is implied first person, and these are never the subject ---
# `they/them/their` are excluded deliberately. "Migrated their estate to Azure"
# is ordinary and correct - the ambiguity is real, so those only warn.
THIRD_PERSON = r"\b(he|him|his|she|her|hers|himself|herself)\b"
AMBIGUOUS_PERSON = r"\b(they|them|their|theirs|themselves)\b"

# --- a sentence that stops before its object ---
# The repo's own history carries "improved overall productivity of the organisation
# by" with no number. Curated rather than a general part-of-speech rule, and split
# in two because English lets a sentence end on a particle: "the platforms other
# teams build on" is finished, "increased productivity by" is not.
DANGLING_HARD = ("a", "an", "the", "and", "or", "but", "by", "of", "from", "into",
                 "onto", "than", "per", "using", "including", "such", "that",
                 "which", "between", "while", "when", "where")
DANGLING_SOFT = ("to", "with", "for", "through", "across", "via", "as")

# --- warn: activity dressed as achievement, per writing-rules.md "Cut on sight" ---
BANNED = ("responsible for", "worked on", "involved in", "gained experience in",
          "acquired knowledge of", "assisted with", "helped with", "participated in",
          "duties included", "tasked with", "exposure to", "familiar with")

# --- warn: the vocabulary a generated resume reaches for and a person rarely does ---
# Not a detector - nothing here can tell who wrote a line. These are the words a
# recruiter has read ten thousand times since 2023 and now skims past, whoever
# typed them. Kept short on purpose: `cross-functional`, `streamlined` and
# `utilized` are generated often too, but people write them just as often, and a
# gate that cries wolf gets switched off. Only the past tense of `orchestrated`,
# because container orchestration is a skill, not a tell.
AI_TELLS = re.compile(
    r"\b(spearhead(?:ed|ing|s)?|leverag(?:e|ed|es|ing)|orchestrated|seamless(?:ly)?|"
    r"synerg(?:y|ies|istic)|foster(?:ed|ing|s)?|robust|cutting-edge|world-class|"
    r"best-in-class|game-chang\w*|proven track record|fast-paced|results-driven|"
    r"detail-oriented|delv(?:e|ed|es|ing)|pivotal role|instrumental in)\b", re.I)

# --- warn: every bullet built on the same frame ---
# "Did X, resulting in Y% Z" once is a sentence; on a third of the bullets it is
# a template, and it is the shape generated resumes repeat. Counted, never
# matched on one bullet: the clause itself is ordinary English.
FORMULA = re.compile(r",\s+(?:resulting in|which resulted in|leading to|contributing to|"
                     r"driving|enabling|ensuring)\b", re.I)
FORMULA_MIN = 3                # bullets on the frame before it reads as one
FORMULA_SHARE = 1 / 3          # ...and the share of all bullets they must be

# --- warn: the no-throat-clearing rule. A bullet opens on what they did. ---
# Suffix rules catch most of it ("Architected", "Owned"); the list carries the
# irregulars and the few present-tense forms that are legitimate on a resume.
VERBS = {
    "built", "led", "ran", "grew", "cut", "drove", "won", "sold", "spoke", "wrote",
    "rebuilt", "rewrote", "broke", "chose", "set", "kept", "held", "brought",
    "began", "left", "met", "took", "made", "gave", "found", "sent", "spent",
    "taught", "put", "shrank", "sped", "beat", "oversaw", "undertook", "rose",
    "own", "build", "lead", "run", "design", "architect", "deliver", "ship",
}
VERB_SUFFIXES = ("ed", "ised", "ized", "ated", "ected", "ored", "ered")

NEAR_DUPLICATE = 0.75          # Jaccard over word sets; 1.0 is an exact repeat
WORD = re.compile(r"[a-z0-9']+")

# --- reading the .tex the PDF is built from ---
ITEM = "\\item"
# A control sequence is a backslash and letters; `\&` and friends are not, which
# is why the unescape below runs first and is left alone by this.
TEX_COMMAND = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
PREAMBLE_CMD = re.compile(
    r"\\(?:documentclass|usepackage|setlength|newcommand|setlist|pagestyle|begin|end"
    r"|hypersetup|hyphenpenalty|exhyphenpenalty)\b")
TEX_UNESCAPE = [
    ("\\&", "&"), ("\\%", "%"), ("\\$", "$"), ("\\#", "#"),
    ("\\_", "_"), ("\\{", "{"), ("\\}", "}"),
    # emit_latex.ASCII_QUOTES. Stripped as commands, "platform's" read as
    # "platform s" - two words, one of them a stray letter.
    ("\\textquotesingle{}", "'"), ("\\textasciigrave{}", "`"),
]
# Markup that is not a command-plus-argument and so survives TEX_COMMAND with a
# fragment of itself in the text. emit_latex's ligature break `\kern0pt{}` sits
# INSIDE a word: stripped as a command it left "0pt" behind and split the word,
# so the Everforth ATS render warned that "Codif 0pt ied the Azure estate" did
# not open on a verb. `\href{url}{text}` shows only its text; its URL is not
# something the reader sees and not prose to check.
TEX_INVISIBLE = re.compile(r"\\kern-?[\d.]+(?:pt|em)?(?:\{\})?|\\href\{[^{}]*\}")

# A bullet longer than this runs to a third rendered line. Measured, not
# guessed: in the default 11pt body on A4 with the 0.8in two-page margin, the
# full lines of monolith's ragged-right Everforth render held 88 to 100
# characters (median 95). So 200 is two of the longest lines - a bullet past it
# cannot fit on two, whatever the line breaks do - where the rough 220 first
# suggested would have let 3-line bullets of 200-220 through silently. The
# fitter may drop the body to 10pt, which widens a line by about a tenth; the
# warning then fires a little early, which is the right way round to be wrong.
LONG_BULLET = 200


def tex_paragraphs(raw_lines):
    """[(is_bullet, text)] one entry per paragraph of a .tex, in document order.

    A bullet is unambiguous in the .tex - it is `\\item`, not a glyph a text extractor
    may or may not have kept. Comments, blank lines and preamble commands are skipped.

    Args:
        raw_lines: the .tex file's lines, as read.

    Returns:
        [(is_bullet, text)] with the markup stripped from each text; a line left empty
        by stripping is dropped.
    """
    out = []
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        bullet = line.startswith(ITEM)
        if bullet:
            line = line[len(ITEM):]
        elif PREAMBLE_CMD.match(line):
            continue
        text = strip_tex(line)
        if text:
            out.append((bullet, text))
    return out


def strip_tex(line):
    """The words a reader sees, with the markup taken off.

    Args:
        line: one line of LaTeX.

    Returns:
        The line with invisible markup removed, escapes decoded, commands and braces
        turned to spaces, and whitespace collapsed.
    """
    line = TEX_INVISIBLE.sub("", line)
    for escaped, plain in TEX_UNESCAPE:
        line = line.replace(escaped, plain)
    line = TEX_COMMAND.sub(" ", line)
    line = line.replace("{", " ").replace("}", " ")
    return " ".join(line.split())


def txt_paragraphs(raw_lines):
    """The plain-text variant's paragraphs, where mode-resume.md step 6 prefixes list items '- '.

    Args:
        raw_lines: the .txt file's lines, as read.

    Returns:
        [(is_bullet, text)] for each non-blank line, the '- ' marker taken off a bullet.
    """
    return [(bool(re.match(r"^\s*-\s+", l)), re.sub(r"^\s*-\s+", "", l.rstrip()))
            for l in raw_lines if l.strip()]


def dangling_tail(line):
    """(word, hard) for a line ending on a word that leaves the clause unfinished.

    Args:
        line: one line of prose.

    Returns:
        (the last word, True) for a word in DANGLING_HARD, (the word, False) for one in
        DANGLING_SOFT, or None.
    """
    stripped = re.sub(r"[\s.;:,]+$", "", line)
    words = WORD.findall(stripped.lower())
    if not words:
        return None
    last = words[-1]
    if last in DANGLING_HARD:
        return last, True
    if last in DANGLING_SOFT:
        return last, False
    return None


def opens_on_a_verb(text):
    """writing-rules.md: the Z position is where seniority shows, and it comes last -
    which only works if the bullet opens on the action rather than on context.

    Args:
        text: one bullet.

    Returns:
        True when one of its first three words is in VERBS or ends like a past tense.
    """
    for word in WORD.findall(text.lower())[:3]:
        if word in VERBS or (len(word) > 4 and word.endswith(VERB_SUFFIXES)):
            return True
    return False


def placeholders(text):
    """FAIL lines for a bracket left in the text. Its own function because the letter
    check (letter.py) asks it of a cover letter too.

    Args:
        text: the document's prose.

    Returns:
        [failure line], empty when no bracket is left.
    """
    fails = []
    brackets = re.findall(r"\[[^\[\]]{0,60}\]", text)
    if brackets:
        shown = ", ".join(repr(b) for b in brackets[:4])
        more = f" (+{len(brackets) - 4} more)" if len(brackets) > 4 else ""
        fails.append(f"unresolved placeholder(s): {shown}{more} - worse than omitting "
                     f"the number")
    if re.search(r"\[(?![^\[\]]{0,60}\])", text):
        fails.append("unmatched open bracket '[' - almost always a leftover placeholder")
    return fails


def ai_tells(text):
    """Each distinct stock word in `text`, lowercased, in the order it first appears.
    Its own function because the letter check (letter.py) asks it of a cover letter too.

    Args:
        text: the prose to search.

    Returns:
        [word], each at most once.
    """
    seen = []
    for m in AI_TELLS.finditer(text):
        word = m.group(0).lower()
        if word not in seen:
            seen.append(word)
    return seen


def overlap(a, b):
    """Jaccard similarity of two bullets' word sets.

    Args:
        a: one bullet.
        b: another.

    Returns:
        A float from 0.0 (no word shared, or both empty) to 1.0 (the same words).
    """
    x, y = set(WORD.findall(a.lower())), set(WORD.findall(b.lower()))
    return len(x & y) / len(x | y) if x | y else 0.0


def person(text, report):
    """Fail each third-person pronoun once; warn once on each ambiguous one.

    Args:
        text: the document's lines, joined by newlines.
        report: the Report the findings are added to.
    """
    reported = set()
    for m in re.finditer(THIRD_PERSON, text, re.I):
        word = m.group(0).lower()
        if word in reported:
            continue
        reported.add(word)
        line = text[text.rfind("\n", 0, m.start()) + 1:].split("\n")[0]
        report.fail(f"third person {m.group(0)!r} - a resume is implied first "
                    f"person: {line[:70]!r}")
    seen = set()
    for m in re.finditer(AMBIGUOUS_PERSON, text, re.I):
        word = m.group(0).lower()
        if word in seen:
            continue
        seen.add(word)
        report.warn(f"{word!r} appears - fine about a client or a team, wrong about "
                    f"the subject; check which this is")


def dangling(lines, report):
    """Flag each line that stops mid-clause: a failure on a hard word, a warning on a soft.

    Args:
        lines: [(is_bullet, line)], one per non-empty line.
        report: the Report the findings are added to.
    """
    for _, line in lines:
        tail = dangling_tail(line)
        if not tail:
            continue
        word, hard = tail
        message = f"sentence stops mid-clause on {word!r}: {line[-60:]!r}"
        (report.fail if hard else report.warn)(message)


def vocabulary(text, report):
    """Warn on each banned phrase and each stock word in the text.

    Args:
        text: the document's lines, joined by newlines.
        report: the Report the findings are added to.
    """
    lowered = text.lower()
    for phrase in BANNED:
        if phrase in lowered:
            report.warn(f"{phrase!r} - activity, not achievement; "
                        f"writing-rules.md says cut on sight")
    for word in ai_tells(text):
        report.warn(f"{word!r} - stock resume vocabulary a recruiter skims past; say what "
                    f"you did in the words you would use out loud")


def shapes(bullets, report):
    """Warn on bullets built on one frame, near-duplicates, and a bullet not opening on a verb.

    Args:
        bullets: the bullets' lines, in document order.
        report: the Report the findings are added to.
    """
    framed = [b for b in bullets if FORMULA.search(b)]
    if len(framed) >= FORMULA_MIN and len(framed) >= FORMULA_SHARE * len(bullets):
        report.warn(f"{len(framed)} of {len(bullets)} bullets close on the same "
                    f"', resulting in ...' frame - vary it: lead some with the result, "
                    f"name the constraint in others, let some stop at what shipped: "
                    f"{framed[0][:50]!r}")

    for i, a in enumerate(bullets):
        for b in bullets[i + 1:]:
            score = overlap(a, b)
            if score >= NEAR_DUPLICATE:
                kind = "duplicate" if score == 1.0 else f"{score:.0%} overlap"
                report.warn(f"near-{kind} bullets: {a[:50]!r} / {b[:50]!r}")

    for bullet in bullets:
        if not opens_on_a_verb(bullet):
            report.warn(f"bullet does not open on a verb: {bullet[:60]!r}")

    # A warning, never a failure: length is a reading cost, not a defect, and
    # some bullets earn a third line. But a recruiter's first pass reads the
    # opening of a bullet and skips the rest, so a bullet that runs to three or
    # four lines spends its space on words nobody reaches.
    for bullet in bullets:
        if len(bullet) > LONG_BULLET:
            report.warn(f"long bullet, {len(bullet)} characters - more than two "
                        f"rendered lines (~{LONG_BULLET}); split it or cut to the "
                        f"result: {bullet[:50]!r}")


def quantified(bullets, report):
    """Warn on the bullets that carry no number, and count the ones that do.

    Listed rather than counted, because the useful output is *which* bullets, and
    capped because a wholly unquantified draft would otherwise bury every other
    finding. Deliberately never a failure and never a threshold: a gate that demands a
    number is a gate that gets fed an invented one, which is the exact failure
    provenance exists to prevent. writing-rules.md names the metrics worth chasing, and
    mode-gaps.md is where the chasing happens - with the person present.

    Args:
        bullets: the bullets' lines, in document order.
        report: the Report the findings are added to.

    Returns:
        How many bullets hold a number, or None when there are no bullets.
    """
    if not bullets:
        return None
    unquantified = [b for b in bullets if not numerals(b)]
    for bullet in unquantified[:4]:
        report.warn(f"no metric in bullet: {bullet[:60]!r}")
    if len(unquantified) > 4:
        report.warn(f"...and {len(unquantified) - 4} more bullets carry no number - "
                    f"writing-rules.md anchors Y on latency, defect rate, "
                    f"release frequency, onboarding time, users served")
    return len(bullets) - len(unquantified)


def check(paragraphs):
    """Every prose rule over a document's paragraphs, in the gate's order.

    Args:
        paragraphs: [(is_bullet, text)], as tex_paragraphs or txt_paragraphs return.

    Returns:
        (fails, warns, quantified): the failure and warning lines, and how many bullets
        hold a number (None with no bullets).
    """
    report = Report()
    lines = [(bullet, line.strip())
             for bullet, body in paragraphs
             for line in body.split("\n") if line.strip()]
    text = "\n".join(t for _, t in lines)
    bullets = [t for b, t in lines if b]

    person(text, report)
    for message in placeholders(text):
        report.fail(message)
    dangling(lines, report)
    vocabulary(text, report)
    shapes(bullets, report)
    count = quantified(bullets, report)
    return report.fails, report.warns, count
