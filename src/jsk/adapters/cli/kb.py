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
import difflib
import inspect
import os
import re
import sys

from ...cliutil import docstring_usage, parse_flags, wants_help
from ...domain.record.confirmation import WORD
from ...domain.resume.constants import PROVENANCE_RANK
from ...infra.files import find_root
from ...graph.record import diff, new_failures
from ...domain.record.writer import entry_text, with_children

VERBS = {}
# verb -> (flags taking a value, switches, flags taking a list), beside --root, which
# every verb takes. main parses them, so an unknown flag is refused by name.
FLAGS = {}
# The verbs that can write the career: each runs inside its turn (record.turn).
WRITES = {"apply", "confirm", "load"}


def verb(values=(), switches=(), lists=()):
    def register(fn):
        name = fn.__name__.removeprefix("cmd_")
        VERBS[name], FLAGS[name] = fn, (values, switches, lists)
        return fn
    return register


def usage(message):
    print(message)
    print("usage: jsk kb <verb> [arguments] [--root DIR] - `jsk kb --help` lists the verbs")
    return 2


def refuse(lines, fix=None):
    """Print why nothing was written. Returns the exit code."""
    for line in lines:
        print(f"REFUSED  {line}")
    if fix:
        print(f"        fix: {fix}")
    print("nothing was written")
    return 1


def show_findings(findings, title):
    from ...cliutil import show
    from ...graph import store as S

    rep = S.Store("", findings=findings).report()
    print(title)
    show(rep.fails, "FAIL", 25)


# Why a record may not be written, and the fix: the states a stored record can be in
# other than clean (record.stored_state).
GUIDE = {
    "out-of-sync": (None, "restore the record from its backup: `jsk kb load .jsk/backup.trig` "
                          "into a new workspace (--root), then use that one"),
    "missing": ("there is no career record here",
                "run `jsk new`, or `jsk kb load` to import a workspace or a dump"),
}


def writable(store):
    """None when the record may be written; otherwise the exit code of a refusal. Only a
    clean record is: in a store, anything else means something outside jsk wrote it."""
    from ...graph import record as R

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


def curies(iris):
    from ...domain.record.writer import curie
    return ", ".join(curie(i) for i in sorted(iris))


def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None,
                 dry_run=False, notes=()):
    """Stamp, validate, print and - unless a dry run - write. Returns the exit code.

    The command already holds its turn (main takes it), so `store` is the record as it
    stands, and nothing lands between this validating the candidate and writing it."""
    from ...graph import record as R
    from ...graph import store as S
    from ...domain.record.writer import write

    missed = changed_subjects(store.graph(R.KB), quads) - set(touched) - set(minted)
    if missed:
        # Rebase trusts the log to name every id a write changed; one it left out would
        # let a changeset drafted before this write overwrite it unrefused.
        return refuse([f"this write changes {curies(missed)} without logging it - a jsk bug"],
                      "report it; the record is untouched")
    today = datetime.date.today()
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
    from ...domain import ontology as O

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


@verb(switches=("--dry-run",))
def cmd_apply(args, flags, root):
    """jsk kb apply <changeset.trig> [--dry-run]

    Merges a changeset (op:add, op:set, op:retire, op:delete; see docs/SCRIPTS.md) into
    the career, then logs it. A changed claim drops to j:inferred and is asked about; a
    new bullet gets its id; a sent metric version gets a successor instead of a change.
    --dry-run prints the diff and writes nothing.
    """
    from ...graph import changeset, edit
    from ...graph import store as S
    from ...graph.io import GraphError

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
        e = edit.apply(store, cs, datetime.date.today())
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
                        dry_run="--dry-run" in flags, notes=e.notes)


def drafted(text, out, what):
    """A drafted changeset to `out`, or to stdout. Returns the exit code."""
    if not out:
        sys.stdout.write(text)
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {out}: {what}")
    print(f"next: `jsk kb apply {out} --dry-run`, read the diff, then apply it")
    return 0


def draft_out(flags):
    """--out FILE for a drafted changeset: (path or None, exit code or None)."""
    out = flags.get("--out")
    if out is not None and not out.endswith(".trig"):
        return None, usage(f"{out}: a changeset is a .trig file")
    return out, None


def logged_base(store):
    """(the log's revision, None) for op:base, or (None, exit code)."""
    from ...graph import record as R

    st = R.state(store)
    if st.kind == "missing" or st.log_revision is None:
        message, fix = GUIDE.get(st.kind, (st.detail, "`jsk kb check` says what is wrong"))
        return None, refuse([message or st.detail], fix)
    return st.log_revision, None


@verb(values=("--out",))
def cmd_pack(args, flags, root):
    """jsk kb pack capabilities [--out FILE.trig]

    Drafts a changeset adopting the capability starter pack (data/capabilities.ttl):
    capabilities and domains with the wordings postings use, and the counts-as edges
    true for anyone. The pack is never loaded as vocabulary; it becomes the person's
    once applied, to change like any of their own concepts.

    Only what the record lacks: a concept it has not got comes whole; one it has with the
    same class gets the missing labels and edges. A concept the record has with another
    class, a label that already names another concept, and an edge whose target is
    missing or that would make a cycle or cross a distinct wall are skipped, each one
    said. Nothing is applied: read it with `jsk kb apply FILE --dry-run`, then apply it.
    The changeset goes to stdout, or --out; what was skipped to stderr, or stdout with --out.
    """
    from ...graph import pack as P
    from ...graph import store as S

    out, code = draft_out(flags)
    if code is not None:
        return code
    if len(args) != 1 or args[0] not in P.PACKS:
        return usage(f"jsk kb pack takes one of: {', '.join(P.PACKS)}")
    store = S.load(root)
    base, code = logged_base(store)
    if code is not None:
        return code
    d = P.draft(store, P.read_pack(P.PACKS[args[0]]))
    report = sys.stdout if out else sys.stderr
    for line in d.skipped:
        print(f"skipped  {line}", file=report)
    if not d.add:
        print(f"nothing to add: the record already has all of the {args[0]} pack it can take",
              file=report)
        return 0
    what = f"{len(d.added)} concepts added, {len(d.enriched)} enriched"
    text = P.trig(base, f"Adopted the {args[0]} pack: {what}.", {"add": d.add},
                  comments=[f"jsk kb pack {args[0]}: {what}, {len(d.skipped)} skipped.",
                            "Read it with `jsk kb apply <this file> --dry-run` before applying."])
    return drafted(text, out, what)


@verb(values=("--out", "--into"))
def cmd_merge(args, flags, root):
    """jsk kb merge c:a --into c:b [--out FILE.trig]

    Drafts a changeset making two concepts one. Every career triple pointing at c:a -
    j:uses, j:domain, j:industry, j:shows, another concept's edges - points at c:b; c:a's
    labels, former labels and own edges move to c:b, and c:a's id is added to c:b as a
    label in words, so the wording that found c:a finds c:b.

    c:a is then deleted - or retired, with a reason, when a posting still names it
    through j:concept: a changeset does not edit postings, and deleting it would leave
    the posting dangling.

    Refused: a concept into itself, one either side the record lacks, a c:a the shipped
    vocabulary defines, two classes, and two concepts declared distinct.

    A bullet whose j:shows changes is a changed claim: applying drops it to j:inferred.
    Those bullets are printed as the re-confirm list. Nothing is applied: read it with
    `jsk kb apply FILE --dry-run`, then apply it.
    """
    from ...graph import merge as M
    from ...graph import pack as P
    from ...graph import store as S

    out, code = draft_out(flags)
    if code is not None:
        return code
    into = flags.get("--into")
    if len(args) != 1 or into is None:
        return usage("jsk kb merge c:a --into c:b - the concept to merge away, and the one "
                     "it becomes")
    a, b = M.concept_iri(args[0]), M.concept_iri(into)
    store = S.load(root)
    base, code = logged_base(store)
    if code is not None:
        return code
    try:
        m = M.draft(store, a, b)
    except M.Refused as err:
        for detail, fix in err.reasons:
            print(f"REFUSED  {detail}\n        fix: {fix}")
        print("nothing was written")
        return 1
    report = sys.stdout if out else sys.stderr
    for note in m["notes"]:
        print(f"note     {note}", file=report)
    if m["named_by"]:
        print(f"note     {curies(m['named_by'])} still name {curies([a])}, so it is retired, "
              "not deleted - re-point them to it and delete it later", file=report)
    if m["reconfirm"]:
        print(f"re-confirm {curies(m['reconfirm'])}", file=report)
        print("         applying drops them to inferred: read each again with the person, "
              "then `jsk kb confirm <ids> --answer \"...\"`", file=report)
    text = P.trig(base, M.summary(a, b, m),
                  {"delete": m["delete"], "add": m["add"], "retire": m["retire"]},
                  entries=m["entries"], comments=[f"jsk kb merge {curies([a])} --into {curies([b])}"])
    return drafted(text, out, M.summary(a, b, m))


def iri_of(text):
    """k:prj_x, prj_x or c:kafka as an iri."""
    from ...domain import ontology as O

    if text.startswith("k:"):
        return O.K + text[2:]
    if text.startswith("c:"):
        return O.C + text[2:]
    return O.K + text


def unknown(iri, store):
    from ...domain.record.writer import curie

    near = difflib.get_close_matches(iri, list(store.homes), n=1)
    return (f"{curie(iri)} is not in the record",
            f"did you mean {curie(near[0])}?" if near else "check the id: `jsk kb view` lists them")


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
    from ...graph.rules import DENIAL, PLACEHOLDER

    if DENIAL.fullmatch(answer):
        return refuse([f"{answer!r}: a denial is not a confirmation"], denial_fix)
    if PLACEHOLDER.fullmatch(answer):
        return refuse([f"{answer!r} is not an answer"],
                      "record what the person said, in their words: it is kept as the "
                      "reason this is confirmed")
    return None


def document_text(path):
    """(text, None) or (None, (reason, fix)): the words of a document to quote from."""
    from ...graph.io import NotUtf8, Unreadable, normalise, read_text

    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".doc", ".odt", ".rtf"):
        return None, (f"{path}: a {ext} file is not read here", "convert it to .md or .txt first")
    if ext == ".pdf":
        from ...infra.pdf import read_pdf
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
    from ...domain.gates.numbers import SCALE
    return [value * SCALE.get(suffix, 1) for value, suffix, _ in numerals]


def unquoted_numbers(quads, iri, quote):
    """The numerals in an entry's claims the quote does not state - a number rounded or
    made up on the way out of the document."""
    from ...domain.gates.numbers import numerals
    from ...domain import ontology as O

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
    from ...graph.rules import squash
    return {w[:5] for w in WORD.findall(squash(text).lower())}


def unquoted_words(quads, iri, quote):
    """The content words of an entry's prose claim the quote does not hold, when more
    than a fifth of them are missing - a clause the session added on the way out of the
    document ("Brought 42 sites onto one platform, cutting onboarding to two weeks" from
    a document that says only the first half), or a quote about something else."""
    from ...domain import ontology as O

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
    from ...graph.rules import DENIAL, PLACEHOLDER, squash
    from ...graph.store import inside, rel

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

    from ...application.guards import frozen_refusal
    from ...resume import short
    from ...graph.io import read_text
    from ...graph.store import inside, rel
    from ...graph.timeline import Unwritable, write_document

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


@verb(values=("--answer", "--summary", "--source", "--quote"))
def cmd_confirm(args, flags, root):
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

    from ...domain import ontology as O
    from ...graph import record as R
    from ...graph import store as S

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
            from ...domain.gates.numbers import quoted
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
    quads += [ox.Quad(ox.NamedNode(q), answered, R.literal(datetime.date.today().isoformat(), "date"))
              for q in asked]
    return write_logged(store, root, quads, "confirm", f"Confirmed {curies(ids)}.",
                        touched=set(todo) | set(asked), answer=answer)


@verb(switches=("--bullets",))
def cmd_show(args, flags, root):
    """jsk kb show <id>... [--bullets]

    The entries as Turtle, each under the name of the graph that holds it (`kb`, the
    shipped `vocabulary`, an application's): a project with its bullets, a metric with its
    versions - the shape a changeset is drafted in. The first line is the revision to put
    in a changeset's op:base, so a change drafted from what was shown is checked against it.

    --bullets prints a project as its name and its bullets only - what citing it as
    evidence needs - without the problem, decisions and notes, which run to thousands of
    characters a project.
    """
    from ...domain import ontology as O
    from ...graph import record as R
    from ...graph import store as S
    from ...domain.record.writer import curie

    bullets = "--bullets" in flags
    if not args:
        return usage("jsk kb show takes one or more ids")
    store = S.load(root)
    st = R.state(store)
    print(f"# r{st.log_revision} - op:base {st.log_revision}" if st.log_revision else
          "# not logged yet - `jsk kb check` says why")
    code = 0
    for text in args:
        iri = iri_of(text)
        files = [f for f in store.definitions.get(iri, []) if f in store.parsed]
        if not files:
            detail, fix = unknown(iri, store)
            print(f"\nREFUSED  {detail}\n        fix: {fix}")
            code = 1
            continue
        for f in files:
            quads = store.graph(f)
            print(f"\n# {f}")
            shown = with_children(quads, iri)
            if bullets and O.class_of(iri) == "Project":
                name = next((q.object.value for q in quads if q.subject.value == iri
                             and q.predicate.value == O.J + "name"), "")
                print(f"# {curie(iri)} - {name}")
                shown = shown[1:]
            print("\n\n".join(entry_text(quads, i) for i in shown))
    return code


@verb(values=("--section",))
def cmd_view(args, flags, root):
    """jsk kb view [--section NAME]

    The whole career as Markdown, in the career's section order, to read end to end and
    correct - stdout only; it is never written to a file, so it cannot drift. Entries not
    confirmed, and retired ones, say so beside their names.
    """
    from ...graph import record as R
    from ...graph import store as S
    from ...graph.view import render

    only = flags.get("--section")
    if args:
        return usage("jsk kb view takes only --section NAME")
    store = S.load(root)
    if R.KB not in store.parsed:
        return refuse([GUIDE[R.state(store).kind][0]], GUIDE[R.state(store).kind][1])
    print(render(store.graph(R.KB), only), end="")
    return 0


@verb(values=("--out", "--from-match", "--cover", "--today"),
      switches=("--ranked", "--replace", "--urs", "--refresh"), lists=("--select",))
def cmd_export(args, flags, root):
    """jsk kb export [--select <id>...] [--from-match <app-dir> [--cover N] | --ranked]
                     [--today YYYY-MM-DD] [--out resume.json [--replace]]

    The short resume.json an application starts from: the bullets it shows, in order,
    and its settings - `"resume": 2`, the region when a profile ships for the person's
    country, `"pages": 2`. Nothing the career holds is copied: the render reads the
    words, numbers and dates from the career as it stands, so a changeset applied or a
    bullet confirmed afterwards is in the next ship with nothing to update.

    --select names what to show: prj_ brings a project and its bullets, ach_ one bullet
    (and narrows its project to the bullets named), pos_ a role shown with no bullet.
    Retired entries never come. With none of --select, --from-match or --ranked, the
    whole career.

    --from-match chooses the bullets from `jsk match` of the application (its directory,
    applications/<dir>): the projects that carry the posting with confirmed evidence,
    their bullets by what they show, the skills the posting asks for first - each skills
    row cut to the most a row renders, and a NOTE naming what each cut left out. What it
    cannot close prints as GAP lines - tag-only, unconfirmed, uncovered, unresolved - for
    gaps.md. --select adds to it; --cover and --today are jsk match's.

    --ranked is the same with no posting, for a general rebuild: the projects by strength
    and recency, their confirmed bullets by the same bands, a bullet citing a current
    number first. The scorer chooses rather than the model, as it does for a posting.
    --select adds to it.

    --out writes the file, and then each chosen bullet as `id | its first 100 characters`
    - what a survey of the projects would have read, one line a bullet. It never writes
    over an existing file unless --replace is given: a re-export after a changeset is
    the file the career now selects. Without --out the file is printed.

    A number in a chosen bullet that no current metric version holds is printed as a
    WARN: it is in the career, not in anything authored, so it is a question for the
    person before any word is retuned.

    --urs and --refresh are gone with the full record: the short file is the one format,
    and there is nothing in it to refresh.
    """
    import json

    from ...domain import ontology as O
    from ...graph import record as R
    from ...graph import store as S
    from ...graph.export import Career, ExportError, chosen, short_file
    from ...graph.match import COVER, application, blocks, posting_in
    from ...domain.record.writer import curie

    # Said by name rather than as an unknown flag - so they are switches it takes: an
    # agent file or a shell history written before the short file still has them.
    if "--urs" in flags:
        return usage("--urs is gone: export writes the short resume.json, the one format "
                     "there is - drop --urs")
    if "--refresh" in flags:
        return usage("--refresh is gone: a short resume.json holds ids, and every render "
                     "builds from the career as it stands, so there is nothing to refresh")
    out, posting, cover_text, today_text = (flags.get(f) for f in
                                            ("--out", "--from-match", "--cover", "--today"))
    by_rank = "--ranked" in flags
    select = None
    if "--select" in flags:
        select = [i for token in flags["--select"] for i in token.split(",") if i]
        if not select:
            return usage("--select needs one or more ids")
    if args:
        return usage("jsk kb export [--select <id>...] [--from-match <app-dir> | --ranked] "
                     "[--out resume.json] - the short resume.json is the one format it writes")
    if posting and by_rank:
        return usage("--ranked is the selection with no posting, --from-match the one for a "
                     "posting - give one")
    if cover_text and not posting:
        return usage("--cover goes with --from-match")
    if today_text and not (posting or by_rank):
        return usage("--today goes with --from-match or --ranked")
    if "--replace" in flags and not out:
        return usage("--replace goes with --out: it lets the export write over that file")
    today, budget = datetime.date.today(), COVER
    try:
        if today_text:
            today = datetime.date.fromisoformat(today_text)
        if cover_text:
            budget = int(cover_text)
    except ValueError:
        return usage("--cover takes a whole number and --today a YYYY-MM-DD date")
    if budget < 1:
        return usage("--cover takes a whole number of at least 1")
    app = None
    if posting:
        home, app = application(posting, "jsk kb export --from-match")
        if home is None:
            print("\n".join(app))
            return 2
        if os.path.normcase(os.path.realpath(home)) != os.path.normcase(os.path.realpath(root)):
            return usage(f"{posting}: not an application of this workspace ({root})")
    store = S.load(root)
    if R.KB not in store.parsed:
        st = R.state(store)
        return refuse([GUIDE[st.kind][0] or st.detail], GUIDE[st.kind][1])
    # The career always; with --from-match, the application's own directory too, as jsk
    # match.
    here = S.file_name(app, store.root) + "/" if posting else None
    blocking = [f for f in store.fails() if f.rule != "log-sync"
                and (not f.file.startswith("applications/") or (here and blocks(f, here)))]
    if blocking:
        where = "the career and the posting have" if posting else "the career has"
        show_findings(blocking, f"REFUSED  {where} {len(blocking)} failures - "
                                "a resume would carry them:")
        return 1
    if out and os.path.exists(out) and "--replace" not in flags:
        return refuse([f"{out} exists - export writes a new resume.json, never over one "
                       "unless told to"],
                      "edit it, or pass --replace to export it again - it holds only ids and "
                      "settings, and the career is read afresh at every render")
    selection, notes = None, []
    report = sys.stdout if out else sys.stderr
    try:
        if posting or by_rank:
            from ...graph import select as SEL
            chosen(Career(store.graph(R.KB)), select)      # a bad --select refuses first
            extra = [O.K + t.removeprefix("k:") for t in select or []]
            if by_rank:
                selection = SEL.ranked(store, today, extra)
            else:
                post = posting_in(store, app)
                if post is None:
                    return refuse([f"{posting} holds no posting"],
                                  f"`jsk posting build {posting}` writes it from posting.md")
                selection = SEL.select(store, post, today, budget, extra)
        if selection is not None:
            # The gaps first: when nothing is selected they are the reason, and a refusal
            # printed without them would leave the author to run jsk match to find out why.
            for p in selection.projects:
                if not selection.bullets.get(p):
                    print(f"NOTE  {curie(p)} has no confirmed bullet, so it comes with none - "
                          "name the bullet with --select, or confirm one", file=report)
            for gap in selection.gaps:
                print(gap.line(), file=report)
        doc = short_file(store, selection=selection, select=select, notes=notes)
    except ExportError as err:
        return refuse([str(err)], err.fix)
    for note in notes:
        print(note, file=report)
    faults = untraced_lines(store, today, [O.K + b for b in doc["bullets"]])
    if faults:
        print(f"WARN  {len(faults)} check(s) fail on the chosen bullets as the career holds "
              "them - a question for the person, answered in the career (`jsk kb apply`) "
              "before any word is retuned:", file=report)
        for line in faults:
            print(f"        {line}", file=report)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if not out:
        sys.stdout.write(text)
        return 0
    wrote(store, out, text, doc)
    career = Career(store.graph(R.KB))
    for b in doc["bullets"]:
        words = " ".join((career.get(O.K + b, "text") or "").split())
        print(f"{b} | {words[:100]}")
    print("next: order `bullets`, add a `summary` and set `pages` or `format` if this posting "
          "wants them, then `jsk validate` it - a reworded bullet goes into the career "
          "(`jsk kb apply`), then export again with --replace")
    return 0


def wrote(store, path, text, doc):
    from ...graph import record as R

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    st = R.state(store)
    at = f" at r{st.log_revision}" if st.log_revision else ""
    print(f"wrote {path}: {len(doc['bullets'])} bullets chosen from the career{at}")


@verb(switches=("--json",), lists=("--near",))
def cmd_query(args, flags, root):
    """jsk kb query <name> [arguments] [--json]

      open                questions not yet answered, oldest first
      unconfirmed         live entries not confirmed, with the question open about each
      holds <concept>     projects holding a concept, or one that counts as it
      stale               applications that sent a metric version since replaced
      experience <concept>  months the roles behind the projects holding it cover
      pipeline            each application's stage: its latest event, and how long ago
      evidence <term>...  per term: projects holding its concept, then entries whose text
                          names it (whole words; an all-capitals term matches as written)
      person              location, work mode, rights to work, and the roles held now
      similar <words>...  the live projects closest to the words (a name, technologies,
                          a sentence), best five, each with the words and concepts shared
      duplicates          pairs of live projects that look like one project told twice
      concepts [--near <term>...]  the vocabulary; with --near, per term, only what it
                          names and the few concepts closest to it - one table each,
                          `== <term>` above it (quote a term of several words)

    A table by default; --json for the same rows, structured.
    """
    import json

    from ...graph import store as S
    from ...graph.named import QUERIES, table

    as_json, near = "--json" in flags, flags.get("--near")
    if not args or args[0] not in QUERIES:
        return usage(f"jsk kb query takes one of: {', '.join(QUERIES)}")
    name, rest = args[0], args[1:]
    want, _, fn = QUERIES[name]
    if want.endswith("...") and not rest or not want.endswith("...") and len(rest) != len(want.split()):
        return usage(f"jsk kb query {name} {want}".rstrip())
    if near is not None and name != "concepts":
        return usage("--near is for `jsk kb query concepts --near <term>...` only")
    if near is None:
        columns, rows = fn(S.load(root), *rest)
        print(json.dumps(rows, indent=2, ensure_ascii=False) if as_json else table(columns, rows))
        return 0
    if not near:
        return usage("jsk kb query concepts --near <term>... - one or more terms")
    # Several terms from one load: the analyst ran this 21 times in a shell loop, 15-25 s.
    store = S.load(root)
    found = {term: fn(store, near=term) for term in near}
    if as_json:
        print(json.dumps({t: rows for t, (_, rows) in found.items()}, indent=2,
                         ensure_ascii=False))
    else:
        print("\n\n".join(f"== {t}\n{table(columns, rows)}" for t, (columns, rows) in found.items()))
    return 0


def untraced_lines(store, today, bullets=None):
    """numbers.untraced over `bullets` (iris; every live bullet when None), a line each:
    what the record gate would refuse in any resume selecting the bullet. Export asks it
    of the bullets it chose - on the Everforth run the author found four of these one
    gate at a time, three changesets deep.

    This exported the whole career as a URS record and ran the record and claims gates
    on it (export.gate_failures); the number check is now one function over the graph,
    so it is asked of the bullets directly. The wording is the old record gate's - it is
    what the Everforth and ElevenLabs runs taught people to read here."""
    from ...gates import numbers
    from ...domain.record.career import Career
    from ...graph import record as R
    from ...graph.shapes import curie

    career = Career(store.graph(R.KB))
    out = []
    chosen = sorted(career.live("Achievement")) if bullets is None else bullets
    for f in numbers.untraced(store, chosen, today):
        if f.numbers:
            one = len(f.numbers) == 1
            out.append(f"{curie(f.bullet)} - {numbers.quoted(f.numbers)} "
                       f"{'appears' if one else 'appear'} "
                       "in the text but in no metric it cites ("
                       + (", ".join(curie(m) for m in f.cites) or "it cites none") + ")")
        for s in f.superseded:
            out.append(f"{curie(f.bullet)} - '{s['number']}' is {curie(s['version'])}'s number, "
                       f"replaced on {s['until']}")
    return out


@verb(values=("--only",))
def cmd_check(args, flags, root):
    """jsk kb check [--only <path>]

    Validates the whole workspace - every rule, every graph - and says where the career
    and its log stand. Exit 1 on any FAIL; a WARN is printed and passes.

    It also asks the record gate's number check of every live bullet: a bullet it
    refuses fails every resume that selects it, so it is warned of here, once, rather
    than found by each resume run.

    --only <graph or path>  the findings in that graph or under that application (`kb`,
                    `applications/acme`, or the application's folder), plus every FAIL
                    anywhere, since a FAIL still stops `jsk match`. The JumpCloud run's
                    full check printed 40 KB of other applications' warnings to find its
                    own five.
    """
    from ...cliutil import show
    from ...graph import record as R
    from ...graph import store as S

    only = flags.get("--only")
    if args:
        return usage("jsk kb check takes no arguments but --only <path>")
    store = S.load(root)
    if only is not None:
        here = os.path.abspath(only)
        only = (S.graph_name(here, store.root) if os.path.exists(here)
                else only.replace("\\", "/")).rstrip("/")

    def within(name):
        return only is None or name == only or name.startswith(only + "/")

    rep = S.Store(store.root, findings=[f for f in store.findings
                                        if f.severity == "FAIL" or within(f.file)]).report()
    if not rep.fails and R.KB in store.parsed and within(R.KB):
        for line in untraced_lines(store, datetime.date.today()):
            rep.warn(f"a record selecting it fails a gate: {line}\n        fix: record the "
                     "number as a metric version and cite it (j:cites), or correct the words, "
                     "with `jsk kb apply` - every application selecting it pays this otherwise")
    st = R.state(store)
    # The one check of the career's hash: only jsk writes the store, and every write it
    # makes to the career logs the hash - so a mismatch is a write from outside. It costs a
    # full write of the career, so check asks it and a plain load does not.
    if st.kind == "clean" and R.unrecorded(store.graph(R.KB), store.graph(R.LOG)):
        rep.fail(f"kb - the career is not what its log last recorded - written outside jsk "
                 f"(r{st.log_revision})\n        fix: restore it from .jsk/backup.trig "
                 "(`jsk kb load .jsk/backup.trig` into a new workspace, --root), or `jsk kb "
                 "dump` to see what it holds")
    print(f"record   {st.kind}" + (f" at r{st.log_revision}" if st.log_revision else "")
          + (f" - {st.detail}" if st.detail else ""))
    print(f"{len(rep.fails)} FAIL, {len(rep.warns)} WARN")
    show(rep.fails, "FAIL", 0)
    show(rep.warns, "WARN", 0)
    return 1 if rep.fails else 0


@verb()
def cmd_path(args, flags, root):
    """jsk kb path [--root DIR]

    Prints where the record is, as absolute paths: the workspace, career/store/ and
    applications/. Run it from anywhere inside the workspace - an application directory
    will do. The store is not a file to read: `jsk kb view`, `show` and `log` read it.

    The workspace is the folder holding career/. A workspace that is itself named
    `career` puts the store at career/career/store/, which is why the path is printed
    rather than worked out. Needs nothing but the folders; exit 1 when there is no
    career/store/ there.
    """
    from ...graph import db, legacy

    if args:
        return usage("jsk kb path takes no arguments")
    store = db.path(root)
    if not db.exists(root):
        print(f"no career/store/ under {root}")
        if legacy.has_files(root):
            print("        fix: this workspace is still laid out as .ttl files - "
                  "`jsk kb load .` moves the record into career/store/")
        elif os.path.isdir(os.path.join(root, "store")) or \
                os.path.isfile(os.path.join(root, "kb.ttl")):
            print(f"        fix: that folder is career/ itself - the workspace is {os.path.dirname(root)}")
        return 1
    print(f"workspace     {root}")
    print(f"store         {store}")
    print(f"applications  {os.path.join(root, 'applications')}")
    return 0


SHADOW = os.path.join(".jsk", "kb.last.ttl")      # the file workspace's copy of its last write


def provenances(quads):
    from ...domain import ontology as O
    return {q.subject.value: q.object.value[len(O.J):] for q in quads
            if q.predicate.value == O.J + "provenance"}


def claims(quads, s):
    from ...domain import ontology as O
    names = O.resets(O.class_named(s))
    return {(q.predicate.value, q.object.value) for q in quads
            if q.subject.value == s and q.predicate.value[len(O.J):] in names}


def upgrades(before, after):
    """What a hand edit raised: provenance moved up, an entry added as confirmed, or a
    claim changed under a confirmation it no longer earns."""
    from ...domain.record.writer import curie

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
    from ...graph import record as R
    from ...graph.io import Unreadable, parse_text, read_text, sha256

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


def imported(before, record, rewrites, src):
    """The files' record with the import's own log entry: the career stamped at the next
    revision, and an entry `by load` holding its hash - so the store's newest entry hashes
    its career, as every jsk write leaves it, and a dump of it loads back. Prints the WARNs
    the file loader found, and what a hand edit raised, before anything is written."""
    import pyoxigraph as ox

    from ...cliutil import show
    from ...graph import record as R
    from ...graph import store as S

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
    today = datetime.date.today()
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

    from ...graph import record as R
    from ...graph.changeset import numbers_as_kept

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


@verb()
def cmd_load(args, flags, root):
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
    from ...graph import db, legacy
    from ...graph import record as R
    from ...graph import store as S
    from ...graph.io import Unreadable, read_text

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
        record = imported(before, record, rewrites, src)
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


@verb(values=("--out",))
def cmd_dump(args, flags, root):
    """jsk kb dump [--out FILE.trig]

    The whole record - the career, its log, every application's graphs - as TriG, to
    stdout or FILE: a backup, and what `jsk kb load` reads back. jsk writes one after every
    write to .jsk/backup.trig as well. Raising pyoxigraph's version is `dump` with the old
    one, then `load` into a new store with the new one.
    """
    from ...graph import db

    if args:
        return usage("jsk kb dump takes no arguments - --out FILE.trig, or stdout")
    out = flags.get("--out")
    if out is not None and not out.endswith(".trig"):
        return usage(f"{out}: a dump is a .trig file")
    try:
        text = db.dump_text(db.read(root))
    except db.StoreError as e:
        return refuse([str(e)], e.fix)
    if out is None:
        sys.stdout.write(text)
        return 0
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {out}")
    return 0


@verb(values=("--last",))
def cmd_log(args, flags, root):
    """jsk kb log [--last N]

    The record's history, newest first: each revision's date, what made it (apply, confirm,
    new, ...), its summary, and the ids it minted and touched. --last N, the newest N
    (default 10).
    """
    from ...domain import ontology as O
    from ...graph import record as R
    from ...graph import store as S

    if args:
        return usage("jsk kb log takes no arguments - --last N")
    last = flags.get("--last", "10")
    if not last.isdigit() or int(last) < 1:
        return usage(f"--last {last}: a count, 1 or more")
    store = S.load(root)
    if R.LOG not in store.parsed:
        return refuse(["the record has no log"], "`jsk kb check` says what is wrong")
    entries = {}
    for q in store.graph(R.LOG):
        if O.class_of(q.subject.value) == "LogEntry":
            entries.setdefault(q.subject.value, {}).setdefault(
                q.predicate.value[len(O.J):], []).append(q.object.value)
    rows = sorted(entries.values(), key=lambda e: -int(R.integer(e.get("revision", ["0"])[0]) or 0))
    for e in rows[:int(last)]:
        by = e.get("by", ["?"])[0].rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        print(f"r{e.get('revision', ['?'])[0]}  {e.get('date', ['?'])[0]}  {by:8} "
              f"{e.get('summary', [''])[0]}")
        for label in ("minted", "touched"):
            if e.get(label):
                print(f"    {label:8} {curies(e[label])}")
    return 0


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
    if root is None or not os.path.isdir(root):
        return usage("no workspace here: run it inside one, or pass --root DIR "
                     "(the folder holding career/)")
    if name == "path":
        return cmd_path(rest, flags, os.path.abspath(root))
    if name != "load":
        # `load` is the import itself; every other verb would answer from, or write to, a
        # record jsk no longer keeps.
        from ...application.guards import unloaded_refusal
        from ...cliutil import refused
        refusal = unloaded_refusal(os.path.abspath(root))
        if refusal:
            return refused(refusal)
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk kb needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ...graph import record as R

    root = os.path.abspath(root)
    # A verb that writes the store takes its turn before it reads it (record.turn).
    with R.turn(root, dry_run=name not in WRITES or "--dry-run" in flags):
        return VERBS[name](rest, flags, root)


if __name__ == "__main__":
    sys.exit(main())
