"""`jsk kb confirm`: the only way an entry becomes j:confirmed, and a resume.json's summary
or headline with it.

An answer is the person's words, or a document's quoted word for word; one that says
nothing, or only names a document, is refused. Confirming ids is a logged write, planned
here and written through WriteLogged; the summary lives in resume.json, not the career,
so it is not logged. Where a quote's document and a resume.json are read and written is
the caller's to give (`files`: infra.files; `read_pdf`: infra.pdf.read_pdf).
"""
import os
from dataclasses import dataclass

from ...domain.record.confirmation import DOCUMENT_ONLY, unquoted_numbers, unquoted_words
from ...domain.record.state import KB
from .read import iri_of, unknown
from .refusals import Problems, Refused
from .write import writable


def said_nothing(answer, denial_fix):
    """Refuse an answer that says nothing: a denial, or a placeholder.

    Args:
        answer: the answer given.
        denial_fix: the fix to give for a denial.

    Raises:
        Refused: it says nothing.
    """
    from ...domain.record.rules import DENIAL, PLACEHOLDER

    if DENIAL.fullmatch(answer):
        raise Refused([f"{answer!r}: a denial is not a confirmation"], denial_fix)
    if PLACEHOLDER.fullmatch(answer):
        raise Refused([f"{answer!r} is not an answer"],
                      "record what the person said, in their words: it is kept as the "
                      "reason this is confirmed")


def document_text(path, *, files, read_pdf):
    """(text, None) or (None, (reason, fix)): the words of a document to quote from.

    Args:
        path: the document.
        files: reads its text (infra.files.read_text).
        read_pdf: reads a PDF's text (infra.pdf.read_pdf).

    Returns:
        The pair. Reads the file.
    """
    from ...domain.record.parsed import NotUtf8, Unreadable, normalise

    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".doc", ".odt", ".rtf"):
        return None, (f"{path}: a {ext} file is not read here", "convert it to .md or .txt first")
    if ext == ".pdf":
        try:
            return normalise(read_pdf(path)[0]), None
        except ImportError:
            return None, (f"{path}: reading a PDF needs pymupdf, which this Python has not got",
                          "install pymupdf, or convert it to .md")
    try:
        return files.read_text(path), None
    except NotUtf8:
        return None, (f"{path} is not UTF-8 text", "convert it to .md or .txt first")
    except Unreadable as e:
        return None, (str(e), e.fix)


def quoted_answer(source, quote, root, *, files, read_pdf):
    """`From <source>: "<quote>"` once the quote is checked against the document, word for
    word as rules.unquoted checks a posting's.

    Args:
        source: the document, inside the workspace.
        quote: its words.
        root: the workspace.
        files: the workspace's files (infra.files): inside, rel, read_text.
        read_pdf: reads a PDF's text (infra.pdf.read_pdf).

    Returns:
        The answer the log keeps. Reads the document.

    Raises:
        Refused: the document is outside the workspace or unreadable, or does not say it.
    """
    from ...domain.record.rules import DENIAL, PLACEHOLDER, squash

    if not os.path.isfile(source) or not files.inside(source, root):
        raise Refused([f"{source}: not a file inside this workspace"],
                      "copy the document into the workspace and pass its path")
    if PLACEHOLDER.fullmatch(quote) or DENIAL.fullmatch(quote) or len(squash(quote).split()) < 3:
        raise Refused([f"{quote!r} is too short to show the document says it"],
                      "quote the document's own sentence that says it - three words "
                      "at least")
    text, problem = document_text(source, files=files, read_pdf=read_pdf)
    if problem:
        raise Refused([problem[0]], problem[1])
    if squash(quote) not in squash(text or ""):
        raise Refused([f"{source} does not say {quote!r}"],
                      "copy the words exactly as the document has them - the quote is "
                      "checked word for word")
    return f'From {files.rel(source, root)}: "{squash(quote)}"'


def answer_of(answer, source, quote, root, *, files, read_pdf):
    """The answer the log keeps: the person's words, or the quote checked in its document.

    Args:
        answer: --answer, or None with --source.
        source, quote: --source and --quote, or None.
        root: the workspace.
        files, read_pdf: as quoted_answer takes them.

    Returns:
        The answer.

    Raises:
        Refused: it says nothing, only names a document, or the quote does not hold.
    """
    if answer is None:
        return quoted_answer(source, quote, root, files=files, read_pdf=read_pdf)
    said_nothing(answer, "record what they said is wrong: op:set the entry's "
                         "j:provenance j:disputed, or correct it with `jsk kb apply`")
    if DOCUMENT_ONLY.fullmatch(answer):
        raise Refused([f"{answer!r} names a document and says nothing else"],
                      'confirm from a document with --source <file> --quote "its words"')
    return answer


def problem_of(text, iri, quads, in_kb, store, quote):
    """(detail, fix) for an id that cannot be confirmed, or None when it can."""
    from ...domain import ontology as O
    from ...domain.gates.numbers import quoted

    cls = O.class_of(iri)
    if iri not in in_kb:
        return unknown(iri, store)
    # In a career writable() passed, so a jsk id with a class.
    if not O.class_named(iri).claims:
        return (f"{text} has no provenance to confirm: a {cls} is not a claim",
                "confirm the entry that makes the claim")
    if any(q.subject.value == iri and q.predicate.value == O.J + "retired" for q in quads):
        return (f"{text} is retired", "a retired entry is not confirmed")
    if quote is not None and (missing := unquoted_numbers(quads, iri, quote)):
        return (f"{text} says {quoted(missing)}, which the quote does not",
                "quote the document's sentence that states it - or, if the "
                "document does not, ask the person and confirm with --answer")
    if quote is not None and (missing := unquoted_words(quads, iri, quote)):
        return (f"{text} says {', '.join(repr(w) for w in missing[:6])}, which the "
                "quote does not",
                "quote the document's sentence that says all of it - words it "
                "does not have are the session's, so ask the person and "
                "confirm with --answer")
    return None


@dataclass(frozen=True)
class Confirmation:
    """A confirmation planned: the career as it leaves it, the ids named, and what changes."""

    quads: list
    ids: tuple                  # every id named, as iris
    touched: set                # those not confirmed yet, and the questions answered


def confirmation(store, texts, quote, today, *, state):
    """Plan confirming the ids `texts` in the loaded record.

    Args:
        store: the record as it stands, read inside the command's turn.
        texts: the ids as typed.
        quote: --quote when confirming from a document, else None: then every number and
            most words of each entry's claims must be in it.
        today: the day each open question about them is answered.
        state: where the career and its log stand (infra.oxigraph.record.state).

    Returns:
        Confirmation, or None when every one of them is confirmed already.

    Raises:
        Failing, Unclean: the record may not be written. Problems: an id cannot be
            confirmed.
    """
    import pyoxigraph as ox

    from ...domain import ontology as O
    from ...domain.record.state import literal

    writable(store, state)
    quads = list(store.graph(KB))
    in_kb = {q.subject.value for q in quads}
    prov, confirmed = ox.NamedNode(O.J + "provenance"), ox.NamedNode(O.J + "confirmed")
    ids, problems = [], []
    for text in texts:
        iri = iri_of(text)
        problem = problem_of(text, iri, quads, in_kb, store, quote)
        if problem:
            problems.append(problem)
        else:
            ids.append(iri)
    if problems:
        raise Problems(problems)
    todo = [i for i in ids if (ox.NamedNode(i), prov, confirmed) not in
            {(q.subject, q.predicate, q.object) for q in quads}]
    about, answered = ox.NamedNode(O.J + "about"), ox.NamedNode(O.J + "answered")
    done = {q.subject for q in quads if q.predicate == answered}
    asked = sorted({q.subject.value for q in quads if q.predicate == about
                    and q.object.value in ids and q.subject not in done})
    if not todo and not asked:
        return None
    quads = [q for q in quads if not (q.subject.value in todo and q.predicate == prov)]
    quads += [ox.Quad(ox.NamedNode(i), prov, confirmed) for i in todo]
    quads += [ox.Quad(ox.NamedNode(q), answered, literal(today.isoformat(), "date"))
              for q in asked]
    return Confirmation(quads, tuple(ids), set(todo) | set(asked))


@dataclass(frozen=True)
class SummaryConfirmed:
    """A resume.json's summary confirmed: the file's text before and after, or nothing to
    change when it was confirmed already."""

    old: str | None
    new: str | None


def confirm_summary(path, answer, root, *, files, short, frozen, key="summary"):
    """`jsk kb confirm --summary` (or `--headline`, `key`): the summary or the headline
    confirmed in resume.json, beside the answer
    and its text's hash. Not logged: a logged write stamps the career with a new revision,
    and the summary is not in the career. resume.json holds the audit trail, and `jsk
    freeze` hashes it into the application graph.

    Args:
        path: the resume.json.
        answer: the person's words.
        root: the workspace.
        files: the workspace's files (infra.files): inside, read_text, write_document.
        short: reads a resume.json (compose.resume.read).
        frozen: what says a directory was frozen, or None (compose.timeline.frozen).
        key: "summary" or "headline" - which of the file's two prose blocks.

    Returns:
        SummaryConfirmed. Writes resume.json.

    Raises:
        Refused: the answer says nothing, the file is outside the workspace or frozen,
            it will not read, its summary is missing or malformed, or the write failed.
    """
    import json

    from ...domain.resume import short as shape_of
    from ...domain.timeline.errors import Unwritable
    from ..guards import frozen_refusal

    said_nothing(answer, f"write the {key} again with what the person said, and ask "
                         "them about the new words")
    if not files.inside(path, root):
        raise Refused([f"{path}: not inside this workspace"], "pass the application's resume.json")
    if frozen_refusal(os.path.dirname(os.path.abspath(path)), frozen=frozen):
        raise Refused([f"{path}: frozen - the record holds its application as it was sent"],
                      "copy the application to a new dated directory to reuse it")
    try:
        doc = short(path)
    except shape_of.ShortError as err:
        raise Refused([str(err)], err.fix) from None
    summary = doc.get(key)
    if not isinstance(summary, dict):
        raise Refused([f"{path} has no {key} to confirm"],
                      f'write one first - "{key}": {{"text": "...", "status": "inferred"}} - '
                      "and read it to the person")
    # The block's own shape, less the unearned confirmation this is here to earn.
    earned = shape_of.unearned(summary, key)
    faults = [f for f in shape_of.shape({"resume": shape_of.VERSION, "bullets": ["ach_"],
                                         key: summary}) if f not in earned]
    if faults:
        raise Refused(faults, f"fix the {key} in resume.json, then confirm it")
    if summary.get("status") == "confirmed" and not earned:
        return SummaryConfirmed(None, None)
    doc[key] = shape_of.confirmed(summary, answer)
    old = files.read_text(path, "resume.json")
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    try:
        files.write_document(path, text)
    except Unwritable as err:
        raise Refused([str(err)], err.fix) from None
    return SummaryConfirmed(old, text)
