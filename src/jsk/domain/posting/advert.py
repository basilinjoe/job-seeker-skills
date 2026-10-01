"""An advert's text as the posting rules read it: squashed to its words, and its lines
numbered by the section they sit in.

What quote-verbatim and advert-uncovered compare a posting's quotes against, and what
`jsk posting extract` numbers and `jsk posting build` quotes.
"""
import re
import unicodedata
from dataclasses import dataclass


# Typography an advert carries and a quote typed from it does not: curly quotes, the
# dashes, the non-breaking hyphen. Folded on both sides, so neither form is wrong.
TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "‛": "'", "“": '"',
                            "”": '"', "‐": "-", "‑": "-", "‒": "-",
                            "–": "-", "—": "-", "―": "-", "−": "-"})
# Markdown emphasis and code marks: `**K8s**` in posting.md says what `K8s` says.
EMPHASIS = re.compile(r"[*_`]+")


def squash(text):
    """Text as the quote check compares it: the words, not their typesetting.

    Args:
        text: any text, an advert's or a quote's.

    Returns:
        It NFKC-normalised, typography folded, emphasis marks dropped, whitespace single.
    """
    text = unicodedata.normalize("NFKC", text).translate(TYPOGRAPHY)
    return re.sub(r"\s+", " ", EMPHASIS.sub("", text)).strip()


OPTIONAL_WORDS = re.compile(r"\b(a plus|nice to have|bonus|desirable)\b", re.I)
REQUIRED_WORDS = re.compile(r"\b(must|required|essential)\b", re.I)


# The advert's lines a requirement should quote: list items under a heading that names
# requirements. Deliberately narrow - a responsibilities or benefits list is not asked of
# the person, and a warning on every line of one would teach the analyst to ignore this.
HEADING_ASKS = re.compile(
    r"\b(requirements?|qualifications?|must|needs?|you have|you('ll| will)? bring|looking for|"
    r"about you|who you are|skills|experience|nice to have|bonus|preferred|desirable)\b", re.I)
HEADING_NOT = re.compile(r"\b(benefits?|perks|we offer|responsibilit\w*|what you('ll| will) do|"
                         r"compensation|salary)\b", re.I)
# Eligibility is the assessment's `# Eligibility`, never a requirement, so it can never be quoted:
# excluded by its words, or it would warn for the life of the application.
ELIGIBILITY = re.compile(r"authori[sz]\w*|\bvisa|sponsor|clearance|citizen|right to work|"
                         r"work permit|relocat|on-?site|hybrid|remote|located in|based in|"
                         r"time ?zone|background check|export control|security check", re.I)
LIST_ITEM = re.compile(r"\s*(?:[-*•]|\d+[.)])\s+(.*)")
BOLD_LINE = re.compile(r"(\*\*|__)[^*_]+\1:?")
# What `jsk posting extract` sorts the rest of an advert by. A responsibility is listed, not
# asked of the person: its requirement defaults to implicit. A benefits list asks nothing.
HEADING_DOES = re.compile(r"\b(responsibilit\w*|what you('ll| will) (do|work on)|in this role|"
                          r"day[- ]to[- ]day)\b|\byou('ll| will):?\Z", re.I)
HEADING_OFFERS = re.compile(r"\b(benefits?|perks|we offer|compensation|salary)\b", re.I)
HEADING_OPTIONAL = re.compile(r"\b(nice to have|bonus|preferred|desirable|a plus)\b", re.I)
# Headings that offer, beyond HEADING_OFFERS: "What's in it for you?" is a benefits list.
OFFERS_MORE = re.compile(r"(?i)what'?s in it for|\brewards?\b|why join|\bour (values|culture)\b|"
                         r"\babout us\b|\bperks\b")
# A sentence's end. A closing `?` is allowed: "What's in it for me?" is a heading.
TERMINAL = re.compile(r"[.!;,]\Z")
# Headings about the company or the role as a whole: they end a section, never sit in one.
ABOUT = re.compile(r"(?i)about\b|(job description|(role |job )?overview|the role)\s*:?\Z")
# posting.md's first line: the URL, or `Source: <file>` when it was fetched from a file.
FIRST_LINE = re.compile(r"https?://\S+|Source: .+")


def bare_heading(text):
    """A heading without markup: short, no sentence end, and either in capitals (`HOW WE
    WORK`, not `AWS`) or worded as a heading. Words are letter-initial, so `&` is not one.

    Args:
        text: a line of the advert, stripped.

    Returns:
        Whether it reads as a heading.
    """
    words = re.findall(r"[A-Za-z][\w'/-]*", text)
    if not words or len(words) > 6 or TERMINAL.search(text):
        return False
    letters = re.sub(r"[^A-Za-z]", "", text)
    if len(words) >= 2 and len(letters) >= 3 and letters.isupper():
        return True
    return bool(HEADING_ASKS.search(text) or HEADING_DOES.search(text)
                or HEADING_OFFERS.search(text) or HEADING_NOT.search(text) or OFFERS_MORE.search(text)
                or ABOUT.match(text))


def sub_heading(text):
    """A marked heading that names no section: under qualifications or responsibilities it
    keeps theirs. The Arrow .docx put "Technical Expertise" and "Team Collaboration and
    Coordination" under "Key Responsibilities", and all 21 items read as `other`.

    Not a bare heading - `S,T,O` in capitals opened Allianz's 96-line skills grid - nor a
    `#LI-Remote` hashtag, which in the corpus comes before the boilerplate: both end the
    section as before.

    Args:
        text: a line of the advert, stripped.

    Returns:
        Whether it is a sub-heading.
    """
    if re.match(r"#[^#\s]", text) or not (text.startswith("#") or BOLD_LINE.fullmatch(text)
                                          or text.endswith(":")):
        return False
    words = squash(text).lstrip("#").strip()
    return not (HEADING_ASKS.search(words) or HEADING_DOES.search(words)
                or HEADING_OFFERS.search(words) or HEADING_NOT.search(words)
                or OFFERS_MORE.search(words) or ABOUT.match(words)
                or re.match(r"(?i)the position\b", words))


@dataclass(frozen=True)
class AdvertLine:
    """One line of an advert a requirement could quote, as advert_lines numbers it."""

    n: int              # from 1, in the advert's order
    section: str        # qualification | responsibility | other
    text: str           # squashed: what a requirement built from it quotes
    optional: bool      # under an optional heading, or worded optionally itself
    elig: bool          # eligibility's words: the assessment's `# Eligibility`, never a requirement


def _heading(line, text, item):
    """Whether a line of the advert is a heading: marked, ending in a colon, or bare.

    Args:
        line: the line as written.
        text: it stripped.
        item: its LIST_ITEM match, or None; a list item is never a heading.

    Returns:
        A truthy value when it is one.
    """
    return not item and (text.startswith("#") or BOLD_LINE.fullmatch(text)
                         or (text.endswith(":") and len(text.split()) <= 8)
                         or bare_heading(text))


def advert_lines(advert):
    """Every line of the advert a requirement could quote, numbered, with its section. Under
    a qualifications or a responsibilities heading each line is its own item, listed or not:
    a posting.md is written one item per line, and joining them made one quote of a section.
    A heading naming no section is a sub-heading there, and keeps it. Elsewhere a list item
    is `other`, and so is a prose paragraph, its lines joined. What an offered (benefits)
    heading lists is left out; so are posting.md's first line (the URL, or `Source: <file>`)
    and headings, which name sections and ask nothing.

    Args:
        advert: posting.md's text.

    Returns:
        [AdvertLine], numbered from 1.
    """
    advert = re.sub(r"\A---\n.*?\n---\n", "", advert, flags=re.S)    # frontmatter
    found = []          # [section, text, optional heading, is an item]
    section, opt_heading, wrapping, prose = "other", False, None, False
    for line in advert.split("\n"):
        text = line.strip()
        item = LIST_ITEM.fullmatch(line) if not BOLD_LINE.fullmatch(text) else None
        # A wrapped item's continuation - unless an item outside the qualifications is
        # followed by what reads as a heading: asked_lines never joined those, so it is one.
        if wrapping and text and not item and line[:1].isspace() and not (
                section != "qualification" and _heading(line, text, item)):
            if wrapping == "join":
                found[-1][1] = f"{found[-1][1]} {squash(text)}"
            continue
        wrapping = None
        if not text:
            prose = False
        elif not found and not prose and not item and FIRST_LINE.fullmatch(text):
            continue                                # posting.md's first line: where it came from
        elif _heading(line, text, item):
            words = squash(text)
            prose = False
            if HEADING_ASKS.search(words) and not HEADING_NOT.search(words):
                section, opt_heading = "qualification", bool(HEADING_OPTIONAL.search(words))
            elif HEADING_DOES.search(words):
                section, opt_heading = "responsibility", False
            elif (HEADING_OFFERS.search(words) or HEADING_NOT.search(words)
                  or OFFERS_MORE.search(words)):
                section, opt_heading = "offered", False
            elif not (section in ("qualification", "responsibility") and sub_heading(text)):
                section, opt_heading = "other", False
        elif item:
            prose, wrapping = False, "skip"
            if section != "offered":
                found.append([section, squash(item.group(1)), opt_heading, True])
                wrapping = "join"
        elif section == "offered":
            continue                                # a benefits paragraph asks nothing
        elif section in ("qualification", "responsibility"):
            found.append([section, squash(text), opt_heading, False])   # never joined
            prose = True
        elif prose:
            found[-1][1] = f"{found[-1][1]} {squash(text)}"
        else:
            found.append(["other", squash(text), False, False])
            prose = True
    return [AdvertLine(n, sec, text, opt or bool(OPTIONAL_WORDS.search(text)),
                       bool(ELIGIBILITY.search(text)))
            for n, (sec, text, opt, _) in enumerate(found, 1)]


def asked_lines(advert):
    """The advert's requirement-like list items, squashed, in order: what advert-uncovered
    reads back against the quotes.

    Args:
        advert: posting.md's text.

    Returns:
        [str]: each qualification of four words or more that is not eligibility.
    """
    return asked_of(advert_lines(advert))


def asked_of(lines):
    """asked_lines over lines already numbered - posting.md's, or a graph-native posting's
    stored ones (domain/posting/lines.py), so both are read back by one rule.

    Args:
        lines: [AdvertLine].

    Returns:
        [str]: each qualification of four words or more that is not eligibility.
    """
    return [x.text for x in lines
            if x.section == "qualification" and len(x.text.split()) >= 4 and not x.elig]

