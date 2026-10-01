"""jsk kb - the career record: changed through changesets, read by id.

Usage: jsk kb <verb> [arguments] [--root DIR]

  apply <changeset.trig> [--dry-run]   merge a changeset into the career; prints the diff
  confirm <id>... --answer "..."       confirm entries with the person's answer, logged;
          <id>... --source F --quote "..."  or with a document's own words;
          --summary <resume.json> --answer "..."  or a resume.json's summary
  show <id>... [--bullets]             entries as Turtle, and the op:base to use;
                                       --bullets, a project's name and bullets only
  view [--section NAME]                the whole career as Markdown, to read
  query <name> [args] [--json]         open | unconfirmed | holds <concept> | stale |
                                       experience <concept> | pipeline |
                                       evidence <term>... | person |
                                       similar <words>... | duplicates |
                                       concepts | bare
  pack capabilities [--out FILE]       the capability starter pack, as a changeset of
                                       what the record lacks; not applied
  merge c:a --into c:b [--out FILE]    two concepts that are one, as a changeset; not applied
  export [--select <id>...]            the short resume.json: the bullets to show, as ids;
         [--from-match <app-dir>]      --from-match chooses them for an application,
         [--ranked] [--cover N]        --ranked with none
         [--today D] [--out FILE [--replace]]
  check                               validate the workspace; exit 1 on a FAIL
  path                                 the workspace, career/store/ and applications/,
                                       as absolute paths
  load <workspace | dump.trig>         fill an empty career/store/, once: from a workspace
                                       still laid out as .ttl files, or from a dump
  dump [--out FILE]                    the whole record as TriG: a backup, and what load reads
  log [--last N]                       the record's history, newest first

--root is the workspace, the folder holding career/; by default the nearest one above
the current directory. `jsk kb <verb> --help` says more about one verb.

The record lives in career/store/ and is read and written only through jsk. Every write
goes through the same gate: it waits its turn behind any other write, the workspace
validates, and the record it would write validates too. Then the career and its log
entry change in one update - both, or neither - and the diff is printed.

Exit 0 done (or nothing to do), 1 refused, 2 called wrong.
"""
import datetime
import inspect
import os
import re
import sys

from ....application.record.read import iri_of, unknown
from ....cliutil import docstring_usage, parse_flags, wants_help
from ....domain.record.confirmation import WORD
from ....domain.record.state import diff, new_failures
from ....domain.record.writer import curies
from ....domain.resume.constants import PROVENANCE_RANK
from ....infra.files import find_root
from ..presenters import GUIDE, refuse, show_findings, usage
from . import draft, export, load, read

# The verbs that can write the career: each runs inside its turn (record.turn).
WRITES = {"apply", "confirm", "load"}


def writable(store):
    """None when the record may be written; otherwise the exit code of a refusal. Only a
    clean record is: in a store, anything else means something outside jsk wrote it."""
    from ....infra.oxigraph import record as R

    blocking = [f for f in store.fails() if f.rule not in ("log-sync",)
                and (not f.file.startswith("applications/") or f.rule == "syntax")]
    if blocking:
        show_findings(blocking, f"REFUSED  the career has {len(blocking)} failures - fix them first:")
        print("nothing was written")
        return 1
    st = R.state(store)
    if st.kind != "clean":
        message, fix = GUIDE[st.kind]
        return refuse([message or st.detail], fix)
    return None


def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None,
                 dry_run=False, notes=(), *, today):
    """Stamp, validate, print and - unless a dry run - write. Returns the exit code.

    The command already holds its turn (main takes it), so `store` is the record as it
    stands, and nothing lands between this validating the candidate and writing it."""
    from ....infra.oxigraph import record as R
    from ....graph import store as S
    from ....domain.record.writer import write

    missed = changed_subjects(store.graph(R.KB), quads) - set(touched) - set(minted)
    if missed:
        # Rebase trusts the log to name every id a write changed; one it left out would
        # let a changeset drafted before this write overwrite it unrefused.
        return refuse([f"this write changes {curies(missed)} without logging it - a jsk bug"],
                      "report it; the record is untouched")
    p = R.prepared(store, quads, today, by, summary, touched, minted, answer)
    after = S.load(root, graphs=p.graphs())
    broken = new_failures(store, after)
    if broken:
        show_findings(broken, f"REFUSED  the change would leave {len(broken)} failures:")
        print("nothing was written")
        return 1
    print(diff(write(store.graph(R.KB), "kb"), p.kb_text), end="")
    for label, ids in (("minted", minted), ("touched", touched)):
        if ids:
            print(f"{label:8} {curies(ids)}")
    for note in notes:
        print(f"note     {note}")
    if dry_run:
        print(f"dry run: r{p.revision} not written")
        return 0
    try:
        R.write_graphs(root, p.graphs())
    except R.RecordError as e:
        print(f"FAIL  {e}\n        fix: {e.fix}")
        return 1
    print(f"r{p.revision} written: career/store/")
    return 0


def changed_subjects(before, after):
    """The subjects whose triples differ between two versions of the career, leaving out
    the header's revision and day, which every write moves: what a write's log entry must
    name as touched or minted, or a changeset drafted before it would rebase over it
    unrefused (edit.base_conflicts checks ids, and only the ids the log names)."""
    from ....domain import ontology as O

    stamp = {(O.K + "kb", O.J + "revision"), (O.K + "kb", O.J + "updated")}

    def triples(quads):
        return {(q.subject.value, q.predicate.value, str(q.object)) for q in quads
                if (q.subject.value, q.predicate.value) not in stamp}
    return {s for s, _, _ in triples(before) ^ triples(after)}


def changeset_text(path):
    """A changeset file's text. UTF-8, with or without a byte-order mark - and UTF-16 when a
    byte-order mark says so, because that is what Windows PowerShell 5.1's `>` and Out-File
    write. Anything else raises UnicodeDecodeError: guessing an encoding would guess words."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def cmd_apply(args, flags, root, today):
    """jsk kb apply <changeset.trig> [--dry-run]

    Merges a changeset (op:add, op:set, op:retire, op:delete; see docs/SCRIPTS.md) into
    the career, then logs it. A changed claim drops to j:inferred and is asked about; a
    new bullet gets its id; a sent metric version gets a successor instead of a change.
    --dry-run prints the diff and writes nothing.
    """
    from ....graph import changeset, store as S
    from ....domain.record import edit
    from ....domain.record.parsed import GraphError

    if len(args) != 1:
        return usage("jsk kb apply takes one changeset")
    path = args[0]
    if path == "-":
        return usage("a changeset is a file: write it to changes.trig and pass that path - "
                     "stdin is refused, because a pipe that never closes hangs the command")
    if not path.endswith(".trig") or not os.path.isfile(path):
        return usage(f"{path}: not a .trig file")
    store = S.load(root)
    code = writable(store)
    if code is not None:
        return code
    try:
        text = changeset_text(path)
    except UnicodeDecodeError as err:
        return refuse([f"{path} is not UTF-8 ({err.reason} at byte {err.start})"],
                      "save it as UTF-8 - in PowerShell, `Set-Content -Encoding utf8`")
    try:
        cs = changeset.read(text, os.path.basename(path))
        e = edit.apply(store, cs, today)
    except GraphError as err:
        return refuse([str(err)], err.fix)
    except changeset.Refused as err:
        return refuse([r.text() for r in err.refusals])
    if not e.touched and not e.minted:
        print("nothing to change: the record already says all of that")
        return 0
    summary = cs.summary or (f"Applied {os.path.basename(path)}: {len(e.minted)} added, "
                             f"{len(e.touched)} changed.")
    return write_logged(store, root, e.quads, "apply", summary, e.touched, e.minted,
                        dry_run="--dry-run" in flags, notes=e.notes, today=today)


# An answer that is only a document's name: "From prior-resume.pdf" confirmed whatever
# was extracted from it, with nothing checking the document says so. Whole answer only,
# a file name of at most three words: an answer that says something and names a file
# as well is the person's words, and passes.
DOCUMENT_ONLY = re.compile(
    r"\s*(?:(?:yes|ok|okay|confirmed|correct)[,.;:!]?\s*)?"
    r"(?:(?:it'?s\s+)?(?:from|per|see|source:?|according\s+to|as\s+(?:in|per)|in)\s+)?"
    r"(?:the\s+|my\s+)?[\"'`]?[^\s\"'`]+(?:\s+[^\s\"'`]+){0,2}?"
    r"\.(?:pdf|docx?|md|txt|tex|rtf|odt|json)[\"'`]?\s*[.!]?\s*", re.I)


def bad_answer(answer, denial_fix):
    """The exit code refusing an answer that says nothing, or None."""
    from ....domain.record.rules import DENIAL, PLACEHOLDER

    if DENIAL.fullmatch(answer):
        return refuse([f"{answer!r}: a denial is not a confirmation"], denial_fix)
    if PLACEHOLDER.fullmatch(answer):
        return refuse([f"{answer!r} is not an answer"],
                      "record what the person said, in their words: it is kept as the "
                      "reason this is confirmed")
    return None


def document_text(path):
    """(text, None) or (None, (reason, fix)): the words of a document to quote from."""
    from ....infra.files import NotUtf8, Unreadable, read_text
    from ....domain.record.parsed import normalise

    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".doc", ".odt", ".rtf"):
        return None, (f"{path}: a {ext} file is not read here", "convert it to .md or .txt first")
    if ext == ".pdf":
        from ....infra.pdf import read_pdf
        try:
            return normalise(read_pdf(path)[0]), None
        except ImportError:
            return None, (f"{path}: reading a PDF needs pymupdf, which this Python has not got",
                          "install pymupdf, or convert it to .md")
    try:
        return read_text(path), None
    except NotUtf8:
        return None, (f"{path} is not UTF-8 text", "convert it to .md or .txt first")
    except Unreadable as e:
        return None, (str(e), e.fix)


def scaled(numerals):
    from ....domain.gates.numbers import SCALE
    return [value * SCALE.get(suffix, 1) for value, suffix, _ in numerals]


def unquoted_numbers(quads, iri, quote):
    """The numerals in an entry's claims the quote does not state - a number rounded or
    made up on the way out of the document."""
    from ....domain.gates.numbers import numerals
    from ....domain import ontology as O

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


# The prose claims a document can state in so many words. Names and titles are labels a
# session often coins ("Care-site onboarding" for "the site programme"), and the quote's
# presence in the document is the check on them.
PROSE = {"Achievement": "text", "Person": "headline"}


def stems(text):
    """The content words of `text` - four letters and longer - cut to five, so
    "onboarded" in a quote still meets "onboarding" in the claim."""
    from ....domain.posting.advert import squash
    return {w[:5] for w in WORD.findall(squash(text).lower())}


def unquoted_words(quads, iri, quote):
    """The content words of an entry's prose claim the quote does not hold, when more
    than a fifth of them are missing - a clause the session added on the way out of the
    document ("Brought 42 sites onto one platform, cutting onboarding to two weeks" from
    a document that says only the first half), or a quote about something else."""
    from ....domain import ontology as O

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


def quoted_answer(source, quote, root):
    """(answer, None) or (None, exit code): `From <source>: "<quote>"` once the quote is
    checked against the document, word for word as rules.unquoted checks a posting's."""
    from ....domain.record.rules import DENIAL, PLACEHOLDER, squash
    from ....infra.files import inside, rel

    if not os.path.isfile(source) or not inside(source, root):
        return None, refuse([f"{source}: not a file inside this workspace"],
                            "copy the document into the workspace and pass its path")
    if PLACEHOLDER.fullmatch(quote) or DENIAL.fullmatch(quote) or len(squash(quote).split()) < 3:
        return None, refuse([f"{quote!r} is too short to show the document says it"],
                            "quote the document's own sentence that says it - three words "
                            "at least")
    text, problem = document_text(source)
    if problem:
        return None, refuse([problem[0]], problem[1])
    if squash(quote) not in squash(text):
        return None, refuse([f"{source} does not say {quote!r}"],
                            "copy the words exactly as the document has them - the quote is "
                            "checked word for word")
    return f'From {rel(source, root)}: "{squash(quote)}"', None


def confirm_summary(path, answer, root):
    """`jsk kb confirm --summary`: the summary confirmed in resume.json, beside the answer
    and its text's hash. Not logged: a logged write stamps the career with a new revision,
    and the summary is not in the career. resume.json holds the audit trail, and `jsk
    freeze` hashes it into the application graph."""
    import json

    from ....application.guards import frozen_refusal
    from ....resume import short
    from ....infra.files import read_text
    from ....infra.files import inside, rel, write_document
    from ....domain.timeline.errors import Unwritable

    code = bad_answer(answer, "write the summary again with what the person said, and ask "
                              "them about the new words")
    if code is not None:
        return code
    if not inside(path, root):
        return refuse([f"{path}: not inside this workspace"], "pass the application's resume.json")
    if frozen_refusal(os.path.dirname(os.path.abspath(path))):
        return refuse([f"{path}: frozen - the record holds its application as it was sent"],
                      "copy the application to a new dated directory to reuse it")
    try:
        doc = short.read(path)
    except short.ShortError as err:
        return refuse([str(err)], err.fix)
    summary = doc.get("summary")
    if not isinstance(summary, dict):
        return refuse([f"{path} has no summary to confirm"],
                      'write one first - "summary": {"text": "...", "status": "inferred"} - '
                      "and read it to the person")
    # The summary's own shape, less the unearned confirmation this is here to earn.
    earned = short.unearned(summary)
    faults = [f for f in short.shape({"resume": short.VERSION, "bullets": ["ach_"],
                                      "summary": summary}) if f not in earned]
    if faults:
        return refuse(faults, "fix the summary in resume.json, then confirm it")
    if summary.get("status") == "confirmed" and not earned:
        print("nothing to change: the summary is confirmed already")
        return 0
    doc["summary"] = short.confirmed(summary, answer)
    old = read_text(path, "resume.json")
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    try:
        write_document(path, text)
    except Unwritable as err:
        return refuse([str(err)], err.fix)
    print(diff(old, text, rel(path, root)), end="")
    print(f"confirmed the summary in {path}")
    return 0


def cmd_confirm(args, flags, root, today):
    """jsk kb confirm <id>... --answer "what the person said"
       jsk kb confirm <id>... --source <file> --quote "the document's words"
       jsk kb confirm --summary <resume.json> --answer "what the person said"

    The only way an entry becomes j:confirmed. Ask the person; record their answer in their
    words. Each entry named is confirmed, every open question about it is answered today,
    and the log keeps the answer beside the ids - the audit trail of why it is confirmed.
    An answer that says nothing ("yes", "ok", "confirmed") is refused, and so is one that
    only names a document ("From resume.pdf"): nothing would check the document says it.

    --source/--quote confirm from a document in the workspace instead: the quote must be
    in it word for word, every number in each entry's claims must be in the quote, and so
    must four in five of a bullet's words - a clause the document lacks is the session's.
    The log keeps `From <file>: "<quote>"`. A .docx is refused; a .pdf needs pymupdf.

    --summary confirms a resume.json's summary: resume.json keeps the answer and the
    text's hash, so an edit to the text afterwards drops it back to inferred.
    """
    import pyoxigraph as ox

    from ....domain import ontology as O
    from ....infra.oxigraph import record as R
    from ....graph import store as S

    answer, summary, source, quote = (flags.get(f) for f in
                                      ("--answer", "--summary", "--source", "--quote"))
    if (source is not None or quote is not None) and answer is not None:
        return usage("--source/--quote and --answer are two ways to confirm - pass one")
    if (source is None) != (quote is None):
        return usage('--source and --quote go together: the file, and the words in it')
    if summary is not None:
        if args or answer is None:
            return usage('jsk kb confirm --summary <resume.json> --answer "what the person '
                         'said" - the summary alone, no ids, and the person\'s answer')
        return confirm_summary(summary, answer, root)
    if not args or (answer is None and source is None):
        return usage('jsk kb confirm takes ids and --answer "what the person said", or '
                     '--source <file> --quote "its words"')
    if answer is not None:
        code = bad_answer(answer, "record what they said is wrong: op:set the entry's "
                                  "j:provenance j:disputed, or correct it with `jsk kb apply`")
        if code is not None:
            return code
        if DOCUMENT_ONLY.fullmatch(answer):
            return refuse([f"{answer!r} names a document and says nothing else"],
                          'confirm from a document with --source <file> --quote "its words"')
    else:
        answer, code = quoted_answer(source, quote, root)
        if code is not None:
            return code
    store = S.load(root)
    code = writable(store)
    if code is not None:
        return code
    quads = list(store.graph(R.KB))
    in_kb = {q.subject.value for q in quads}
    prov, confirmed = ox.NamedNode(O.J + "provenance"), ox.NamedNode(O.J + "confirmed")
    ids, problems = [], []
    for text in args:
        iri = iri_of(text)
        cls = O.class_of(iri)
        if iri not in in_kb:
            problems.append(unknown(iri, store))
        # In a career writable() passed, so a jsk id with a class.
        elif not O.class_named(iri).claims:
            problems.append((f"{text} has no provenance to confirm: a {cls} is not a claim",
                             "confirm the entry that makes the claim"))
        elif any(q.subject.value == iri and q.predicate.value == O.J + "retired" for q in quads):
            problems.append((f"{text} is retired", "a retired entry is not confirmed"))
        elif source is not None and (missing := unquoted_numbers(quads, iri, quote)):
            from ....domain.gates.numbers import quoted
            problems.append((f"{text} says {quoted(missing)}, which the quote does not",
                             "quote the document's sentence that states it - or, if the "
                             "document does not, ask the person and confirm with --answer"))
        elif source is not None and (missing := unquoted_words(quads, iri, quote)):
            problems.append((f"{text} says {', '.join(repr(w) for w in missing[:6])}, which the "
                             "quote does not",
                             "quote the document's sentence that says all of it - words it "
                             "does not have are the session's, so ask the person and "
                             "confirm with --answer"))
        else:
            ids.append(iri)
    if problems:
        for detail, fix in problems:
            print(f"REFUSED  {detail}\n        fix: {fix}")
        print("nothing was written")
        return 1
    todo = [i for i in ids if (ox.NamedNode(i), prov, confirmed) not in
            {(q.subject, q.predicate, q.object) for q in quads}]
    about, answered = ox.NamedNode(O.J + "about"), ox.NamedNode(O.J + "answered")
    done = {q.subject for q in quads if q.predicate == answered}
    asked = sorted({q.subject.value for q in quads if q.predicate == about
                    and q.object.value in ids and q.subject not in done})
    if not todo and not asked:
        print("nothing to change: every one of them is confirmed already")
        return 0
    quads = [q for q in quads if not (q.subject.value in todo and q.predicate == prov)]
    quads += [ox.Quad(ox.NamedNode(i), prov, confirmed) for i in todo]
    quads += [ox.Quad(ox.NamedNode(q), answered, R.literal(today.isoformat(), "date"))
              for q in asked]
    return write_logged(store, root, quads, "confirm", f"Confirmed {curies(ids)}.",
                        touched=set(todo) | set(asked), answer=answer, today=today)


SHADOW = os.path.join(".jsk", "kb.last.ttl")      # the file workspace's copy of its last write


def provenances(quads):
    from ....domain import ontology as O
    return {q.subject.value: q.object.value[len(O.J):] for q in quads
            if q.predicate.value == O.J + "provenance"}


def claims(quads, s):
    from ....domain import ontology as O
    names = O.resets(O.class_named(s))
    return {(q.predicate.value, q.object.value) for q in quads
            if q.subject.value == s and q.predicate.value[len(O.J):] in names}


def upgrades(before, after):
    """What a hand edit raised: provenance moved up, an entry added as confirmed, or a
    claim changed under a confirmation it no longer earns."""
    from ....domain.record.writer import curie

    now, was, out = provenances(after), provenances(before), []
    for s, p in sorted(now.items()):
        if s not in was:
            if p == "confirmed":
                out.append(f"{curie(s)}: added as confirmed")
        elif PROVENANCE_RANK.get(p, 0) > PROVENANCE_RANK.get(was[s], 0):
            out.append(f"{curie(s)}: {was[s]} -> {p}")
        elif p == "confirmed" and claims(before, s) != claims(after, s):
            changed = sorted({curie(pred) for pred, _ in claims(before, s) ^ claims(after, s)})
            out.append(f"{curie(s)}: {', '.join(changed)} changed while confirmed")
    return out


def hand_edit(before, src):
    """(lines naming what a hand edit of kb.ttl raised, the ids it changed - every id in
    the career when there is nothing to compare against). A provenance raised by hand
    renders as confirmed with no answer behind it, and after the import no text is left
    to show it was: so each one is named now, against the shadow copy of the revision the
    log last recorded when there is one."""
    from ....infra.oxigraph import record as R
    from ....infra.files import Unreadable, read_text
    from ....infra.oxigraph.codec import parse_text
    from ....domain.record.parsed import sha256

    st = R.state(before)
    after = before.graph(R.KB)
    try:
        old = read_text(os.path.join(src, SHADOW), "the shadow copy")
    except Unreadable:
        old = None
    if old is None or sha256(old) != st.logged_sha:
        return ([f"note     kb.ttl was edited by hand after r{st.log_revision}, and there is "
                 f"nothing to compare it against ({SHADOW} is not r{st.log_revision}): a "
                 "provenance the edit raised to confirmed cannot be named - check the "
                 "confirmed entries with the person"],
                {q.subject.value for q in after})
    was = parse_text(old, R.KB).quads
    raised = upgrades(was, after)
    lines = [f"raised   {line}" for line in raised]
    if raised:
        lines.append("         check each with the person; `jsk kb confirm <id> --answer` "
                     "records it")
    return lines, {q.subject.value for q in set(was) ^ set(after)}


def imported(before, record, rewrites, src, today):
    """The files' record with the import's own log entry: the career stamped at the next
    revision, and an entry `by load` holding its hash - so the store's newest entry hashes
    its career, as every jsk write leaves it, and a dump of it loads back. Prints the WARNs
    the file loader found, and what a hand edit raised, before anything is written."""
    import pyoxigraph as ox

    from ....cliutil import show
    from ....infra.oxigraph import record as R
    from ....graph import store as S

    warns = before.warns()
    if warns:
        print(f"{len(warns)} WARN in the files, imported as they are:")
        show(S.Store("", findings=warns).report().warns, "WARN", 0)
    touched = {q.subject.value for name, q, _ in rewrites if name == R.KB}
    if R.state(before).kind == "hand-edited":
        lines, changed = hand_edit(before, src)
        for line in lines:
            print(line)
        touched |= changed
    rev = R.next_revision(R.state(before))
    kb = R.stamp([ox.Quad(t.subject, t.predicate, t.object) for t in record[R.KB]], rev, today)
    summary = (f"Imported from the files by jsk kb load: {len(record)} graphs, "
               f"{len(rewrites)} numbers kept by value.")
    log = [ox.Quad(t.subject, t.predicate, t.object) for t in record.get(R.LOG, [])]
    log += R.entry(rev, today, "load", summary, R.career_sha(kb), touched)
    return {**record, R.KB: kb, R.LOG: log}


def edited_dump(record, name):
    """None for a dump as jsk wrote it; else the exit code of its refusal. A number in a
    spelling the store would rewrite, or a career whose hash is not what its log's newest
    entry recorded, is a dump changed outside jsk: loaded, the change would enter the
    record unlogged - a provenance raised by hand renders as confirmed."""
    import pyoxigraph as ox

    from ....infra.oxigraph import record as R
    from ....graph.changeset import numbers_as_kept

    fix = ("load the dump as `jsk kb dump` wrote it (or .jsk/backup.trig), then change the "
           "record through `jsk kb apply`")
    found = []
    for graph, triples in sorted(record.items()):
        numbers_as_kept([ox.Quad(t.subject, t.predicate, t.object) for t in triples],
                        lambda focus, detail, _fix, g=graph: found.append(f"{g} {focus} {detail}"))
    if found:
        return refuse([f"{name}: {line}" for line in found] + ["the dump was changed outside jsk"],
                      fix)
    if R.KB in record:
        kb = [ox.Quad(t.subject, t.predicate, t.object) for t in record[R.KB]]
        why = R.unrecorded(kb, record.get(R.LOG, []))
        if why:
            return refuse([f"{name}: the career in it - {why} - was changed outside jsk"], fix)
    return None


def cmd_load(args, flags, root, today):
    """jsk kb load <workspace folder | dump.trig>

    Fills this workspace's empty career/store/ - once. From a workspace still laid out as
    files (career/kb.ttl, log.ttl, applications/*/*.ttl): they are read and validated as
    they always were, every number is kept as the store keeps it (`8.40` becomes `8.4`, each
    one listed), and the files are left where they are - jsk stops reading them. Or from a
    `jsk kb dump` (or .jsk/backup.trig): the record as it was dumped.

    Refused when the store already holds a record, when a workspace of files has any FAIL,
    and when the career it would load has one. An application's documents - posting.md and
    the rest - are files beside it, not the record: loaded into another workspace, its
    folder is named so it can be copied across.
    """
    from ....infra.oxigraph import db
    from ....graph import legacy
    from ....infra.oxigraph import record as R
    from ....graph import store as S
    from ....infra.files import Unreadable, read_text

    if len(args) != 1:
        return usage("jsk kb load takes one workspace folder or one .trig dump")
    src = os.path.abspath(args[0])
    if db.exists(root) and any(db.read(root).values()):
        return refuse([f"{os.path.join(root, db.STORE_DIR)} already holds a record"],
                      "load into a new workspace (`jsk new` elsewhere is not needed - an "
                      "empty folder with --root will do)")
    rewrites = []
    if os.path.isdir(src):
        if not legacy.has_files(src):
            return usage(f"{src}: no career/kb.ttl - not a workspace laid out as files")
        before, record, rewrites = legacy.read_workspace(src)
        if before.fails():
            show_findings(before.fails(), f"REFUSED  {src} has {len(before.fails())} failures "
                                          "- fix them in the files first:")
            print("nothing was written")
            return 1
        record = imported(before, record, rewrites, src, today)
    elif src.endswith(".trig") and os.path.isfile(src):
        try:
            record = db.parse_dump(read_text(src, os.path.basename(src)))
        except (Unreadable, db.StoreError) as e:
            return refuse([str(e)], e.fix)
        except SyntaxError as e:
            return refuse([f"{os.path.basename(src)}:{e.lineno}: {e.msg}"],
                          "a dump is TriG as `jsk kb dump` writes it")
        code = edited_dump(record, os.path.basename(src))
        if code is not None:
            return code
    else:
        return usage(f"{args[0]}: not a folder, nor a .trig file")
    after = S.load(root, files=[S.SHIPPED_VOCABULARY], graphs=record)
    # As for any write: the career must validate, and an application's fault does not
    # stop it. An application's rules read the documents beside it (posting.md), so one
    # loaded into another workspace fails them until its folder is copied across.
    blocking = [f for f in after.fails()
                if not f.file.startswith("applications/") or f.rule == "syntax"]
    if blocking:
        show_findings(blocking, f"REFUSED  the record would load with {len(blocking)} failures:")
        print("nothing was written")
        return 1
    for name, q, kept in rewrites:
        print(f"number   {name} {curies([q.subject.value])} {curies([q.predicate.value])} "
              f"{q.object.value} kept as {kept.value}")
    try:
        R.write_graphs(root, record, create=True)
    except R.RecordError as e:
        print(f"FAIL  {e}\n        fix: {e.fix}")
        return 1
    st = R.state(S.load(root))
    print(f"loaded   {sum(map(len, record.values()))} triples in {len(record)} graphs into "
          f"career/store/, at r{st.kb_revision}")
    if legacy.has_files(root):
        print("note     career/kb.ttl and the other .ttl files are no longer read - the record "
              "is career/store/; `jsk kb dump` writes it out as text")
    apps = sorted({n.rsplit("/", 1)[0] for n in record if n.startswith("applications/")})
    for app in apps:
        if not os.path.isdir(os.path.join(root, app)):
            print(f"note     {app}: its documents (posting.md, gaps.md, resume.json, the files "
                  f"sent) are not in this workspace - copy the folder into {root}")
    if any(f.file.startswith("applications/") for f in after.fails()):
        print(f"note     {sum(f.file.startswith('applications/') for f in after.fails())} "
              "failures in applications - `jsk kb check` lists them")
    return 0


# verb -> (its handler, flags taking a value, switches, flags taking a list), beside --root,
# which every verb takes. main parses them, so an unknown flag is refused by name.
TABLE = {
    "apply": (cmd_apply, (), ("--dry-run",), ()),
    "pack": (draft.cmd_pack, ("--out",), (), ()),
    "merge": (draft.cmd_merge, ("--out", "--into"), (), ()),
    "confirm": (cmd_confirm, ("--answer", "--summary", "--source", "--quote"), (), ()),
    "show": (read.cmd_show, (), ("--bullets",), ()),
    "view": (read.cmd_view, ("--section",), (), ()),
    "export": (export.cmd_export, ("--out", "--from-match", "--cover", "--today"),
               ("--ranked", "--replace", "--urs", "--refresh"), ("--select",)),
    "query": (read.cmd_query, (), ("--json",), ("--near",)),
    "check": (read.cmd_check, ("--only",), (), ()),
    "path": (read.cmd_path, (), (), ()),
    "load": (cmd_load, (), (), ()),
    "dump": (load.cmd_dump, ("--out",), (), ()),
    "log": (read.cmd_log, ("--last",), (), ()),
}
VERBS = {name: row[0] for name, row in TABLE.items()}
FLAGS = {name: row[1:] for name, row in TABLE.items()}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (wants_help(args) and args[0] not in VERBS):
        print(docstring_usage(__doc__))
        return 0 if args else 2
    name, rest = args[0], args[1:]
    if name not in VERBS:
        return usage(f"unknown verb: {name} - one of {', '.join(VERBS)}")
    if wants_help(rest):
        print(inspect.cleandoc(VERBS[name].__doc__))
        return 0
    values, switches, lists = FLAGS[name]
    # A lone `-` is apply's to refuse (stdin is refused there), not an unknown flag.
    parsed, problem = parse_flags(rest, (*values, "--root"), switches, lists=lists,
                                  dash=True)
    if parsed is None:
        return usage(problem)
    rest, flags = parsed
    root = flags.pop("--root", None) or find_root(os.getcwd())
    today = datetime.date.today()
    if root is None or not os.path.isdir(root):
        return usage("no workspace here: run it inside one, or pass --root DIR "
                     "(the folder holding career/)")
    if name == "path":
        return read.cmd_path(rest, flags, os.path.abspath(root), today)
    if name != "load":
        # `load` is the import itself; every other verb would answer from, or write to, a
        # record jsk no longer keeps.
        from ....application.guards import unloaded_refusal
        from ....cliutil import refused
        refusal = unloaded_refusal(os.path.abspath(root))
        if refusal:
            return refused(refusal)
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk kb needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ....infra.oxigraph import record as R

    root = os.path.abspath(root)
    # A verb that writes the store takes its turn before it reads it (record.turn).
    with R.turn(root, dry_run=name not in WRITES or "--dry-run" in flags):
        return VERBS[name](rest, flags, root, today)

