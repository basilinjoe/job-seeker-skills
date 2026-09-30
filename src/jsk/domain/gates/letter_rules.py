"""The letter check's rules over a cover letter's text: its length, its prose, its quotes.

A letter is the resume's claims in a looser paragraph, so the number check that reads the
career stays with the gate (gates/letter.py); these read the words alone.
"""
import re

from .report import line

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


def body(text):
    """The paragraphs a reader counts: between the salutation and the closing."""
    lines = [ln.strip().lstrip("#").strip() for ln in text.splitlines()]
    start = next((i + 1 for i, ln in enumerate(lines) if ln and SALUTATION.match(ln)), 0)
    end = next((i for i, ln in enumerate(lines) if i >= start and CLOSING.match(ln)), len(lines))
    return "\n".join(lines[start:end]).strip()


def paragraphs(text):
    """The letter's paragraphs, each on one line with its whitespace squashed."""
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def length_lines(text):
    """([the too-long failure] or [], the body's word count)."""
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
    from .prose_rules import BANNED, ai_tells, dangling_tail, placeholders

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
    warns += [line("stock-vocabulary", "letter", f"{w!r} - the word every generated "
                   f"letter uses", "say what you did in the words you would use out loud")
              for w in ai_tells(text)]
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
