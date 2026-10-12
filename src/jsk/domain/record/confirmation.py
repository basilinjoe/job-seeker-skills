"""What a confirmation's quote has to share with the claim it confirms, and what an answer
has to say to confirm anything at all."""
import re

# A content word: four letters and longer. Shorter words are the connective tissue every
# sentence shares, and would let any quote "confirm" any claim.
WORD = re.compile(r"[a-z0-9]{4,}")

# An answer that is only a document's name: "From prior-resume.pdf" confirmed whatever
# was extracted from it, with nothing checking the document says so. Whole answer only,
# a file name of at most three words: an answer that says something and names a file
# as well is the person's words, and passes.
DOCUMENT_ONLY = re.compile(
    r"\s*(?:(?:yes|ok|okay|confirmed|correct)[,.;:!]?\s*)?"
    r"(?:(?:it'?s\s+)?(?:from|per|see|source:?|according\s+to|as\s+(?:in|per)|in)\s+)?"
    r"(?:the\s+|my\s+)?[\"'`]?[^\s\"'`]+(?:\s+[^\s\"'`]+){0,2}?"
    r"\.(?:pdf|docx?|md|txt|tex|rtf|odt|json)[\"'`]?\s*[.!]?\s*", re.I)

# The prose claims a document can state in so many words. Names and titles are labels a
# session often coins ("Care-site onboarding" for "the site programme"), and the quote's
# presence in the document is the check on them.
PROSE = {"Achievement": "text", "Person": "headline"}


def scaled(numerals):
    """Each numeral's value times its scale word (`42k` is 42000).

    Args:
        numerals: domain.gates.numbers.numerals' (value, suffix, text) triples.

    Returns:
        The values, in order.
    """
    from ..gates.numbers import SCALE
    return [value * SCALE.get(suffix, 1) for value, suffix, _ in numerals]


def unquoted_numbers(quads, iri, quote):
    """The numerals in an entry's claims the quote does not state - a number rounded or
    made up on the way out of the document.

    Args:
        quads: the career.
        iri: the entry confirmed, a jsk id with a class.
        quote: the document's words.

    Returns:
        The numerals as written in the claims, each once, in order.
    """
    from ..gates.numbers import numerals
    from .. import ontology as O

    said = scaled(numerals(quote))
    # iri is in a career writable() passed, where every subject is a jsk id.
    kinds = {p.name for p in O.class_named(iri).preds.values()
             if p.claim and p.obj in (O.STR, O.NUM)}
    out = []
    for q in quads:
        if q.subject.value == iri and q.predicate.value[len(O.J):] in kinds:
            for n in numerals(q.object.value):
                (value,) = scaled([n])
                if not any(abs(value - s) <= 1e-9 * max(abs(value), 1) for s in said):
                    out.append(n[2])
    return list(dict.fromkeys(out))


def stems(text):
    """The content words of `text` - four letters and longer - cut to five, so
    "onboarded" in a quote still meets "onboarding" in the claim.

    Args:
        text: any prose.

    Returns:
        The set of stems.
    """
    from ..posting.advert import squash
    return {w[:5] for w in WORD.findall(squash(text).lower())}


def unquoted_words(quads, iri, quote):
    """The content words of an entry's prose claim the quote does not hold, when more
    than a fifth of them are missing - a clause the session added on the way out of the
    document ("Brought 42 sites onto one platform, cutting onboarding to two weeks" from
    a document that says only the first half), or a quote about something else.

    Args:
        quads: the career.
        iri: the entry confirmed.
        quote: the document's words.

    Returns:
        The missing words, in the claim's order; [] when the quote holds enough of them.
    """
    from .. import ontology as O

    cls = O.class_of(iri)
    pred = PROSE.get(cls) if cls else None
    if not pred:
        return []
    said = stems(quote)
    for q in quads:
        if q.subject.value == iri and q.predicate.value == O.J + pred:
            words = [w for w in dict.fromkeys(WORD.findall(q.object.value.lower()))]
            missing = [w for w in words if w[:5] not in said]
            if words and len(missing) > len(words) / 5:
                return missing
    return []
