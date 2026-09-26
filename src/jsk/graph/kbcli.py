"""jsk kb - the career record: changed through changesets, read by id.

Usage: jsk kb <verb> [arguments] [--root DIR]

  apply <changeset.trig> [--dry-run]   merge a changeset into career/kb.ttl; prints the diff
  confirm <id>... --answer "..."       confirm entries with the person's answer, logged;
          <id>... --source F --quote "..."  or with a document's own words;
          --summary <resume.json> --answer "..."  or a resume.json's summary
  adopt [--drop-comments]              log a hand edit, listing every provenance it raised
  fmt [<file>...] [--drop-comments]    rewrite in the canonical layout; kb.ttl's is logged
  show <id>... [--bullets]             entries as kb.ttl holds them, and the op:base to use;
                                       --bullets, a project's name and bullets only
  view [--section NAME]                the whole career as Markdown, to read
  query <name> [args] [--json]         open | unconfirmed | holds <concept> | stale |
                                       experience <concept> | pipeline |
                                       evidence <term>... | person |
                                       similar <words>... | duplicates
  export [--select <id>...]            the short resume.json: the bullets to show, as ids;
         [--from-match <posting.ttl>]  --from-match chooses them for a posting,
         [--ranked] [--cover N]        --ranked with none
         [--today D] [--out FILE]
  check                                validate the workspace; exit 1 on a FAIL
  path                                 the workspace, kb.ttl, log.ttl and applications/,
                                       as absolute paths - read these, never guess them

--root is the workspace, the folder holding career/; by default the nearest one above
the current directory. `jsk kb <verb> --help` says more about one verb.

Every write goes through the same gate: the workspace validates, kb.ttl is exactly what
the log last recorded (a hand edit is adopted first, so it is logged as one), and the
record it would write validates too. Then kb.ttl, then log.ttl, and the diff.

Exit 0 done (or nothing to do), 1 refused, 2 called wrong.
"""
import datetime
import difflib
import inspect
import os
import re
import sys

from ..cliutil import docstring_usage, wants_help

VERBS = {}


def verb(fn):
    VERBS[fn.__name__.removeprefix("cmd_")] = fn
    return fn


def find_root(start):
    """The nearest folder at or above `start` holding career/kb.ttl, or None."""
    here = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(here, "career", "kb.ttl")):
            return here
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up


def take(args, flag, value=False):
    """Remove `flag` (and its value) from args; the value, True, or None."""
    if flag not in args:
        return None
    at = args.index(flag)
    if not value:
        del args[at]
        return True
    if at + 1 >= len(args):
        raise SystemExit(usage(f"{flag} needs a value"))
    found = args[at + 1]
    del args[at:at + 2]
    return found


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
    from ..gates.report import show
    from . import store as S

    rep = S.Store("", findings=findings).report()
    print(title)
    show(rep.fails, "FAIL", 25)


GUIDE = {
    "unlogged": ("career/kb.ttl has no log yet", "run `jsk kb adopt` to start log.ttl from it"),
    "hand-edited": (None, "run `jsk kb adopt` first, so the hand edit is logged as one"),
    "torn": (None, "run `jsk kb adopt`: it logs the write that did not reach log.ttl"),
    "out-of-sync": (None, "restore the file that went back on its own, or `jsk kb adopt`"),
    "missing": ("there is no career/kb.ttl", "run `jsk migrate` or `jsk new`"),
    "unreadable": ("career/kb.ttl or career/log.ttl does not parse", "`jsk kb check` shows where"),
}


def writable(store, allow=("clean",), canonical=True):
    """None when the record may be written; otherwise the exit code of a refusal."""
    from . import record as R
    from .writer import write

    blocking = [f for f in store.fails() if f.rule not in ("log-sync",)
                and (not f.file.startswith("applications/") or f.rule == "syntax")]
    if blocking:
        show_findings(blocking, f"REFUSED  the career has {len(blocking)} failures - fix them first:")
        print("nothing was written")
        return 1
    st = R.state(store)
    if st.kind not in allow:
        message, fix = GUIDE[st.kind]
        return refuse([message or st.detail], fix)
    if canonical and st.kind == "clean" and \
            write(store.graph(R.KB), "kb") != store.parsed[R.KB].text:
        return refuse(["career/kb.ttl is not in the canonical layout this jsk writes"],
                      "run `jsk kb fmt` - a reformat is logged on its own, so no change hides in it")
    return None


def key(f):
    return (f.rule, f.file, f.focus, f.detail)


def new_failures(before, after):
    """What a write would break: any FAIL in the career or the vocabulary, and a FAIL
    anywhere that was not already there - an old application's fault is not this one's."""
    had = {key(f) for f in before.fails()}
    return [f for f in after.fails() if not f.file.startswith("applications/") or key(f) not in had]


def diff(old, new, name="career/kb.ttl"):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        f"a/{name}", f"b/{name}"))


def curies(iris):
    from .writer import curie
    return ", ".join(curie(i) for i in sorted(iris))


def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None,
                 content=True, dry_run=False, notes=(), old=None):
    """Stamp, validate, print and - unless a dry run - write. Returns the exit code.
    The diff is from `old` when given (adopt: the revision the log last recorded)."""
    from . import record as R
    from . import store as S
    from .io import parse_text

    today = datetime.date.today()
    rev, kb_text, log_text = R.prepare(store, quads, today, by, summary, touched, minted,
                                       answer, content)
    # gofmt's promise, checked every time: what was written parses back to what was meant.
    if set(parse_text(kb_text, R.KB).quads) != set(R.stamp(quads, rev, today, content)):
        return refuse(["the writer did not reproduce the record it was given - a jsk bug"],
                      "report it; kb.ttl is untouched")
    after = S.load(root, texts={R.KB: kb_text, R.LOG: log_text})
    broken = new_failures(store, after)
    if broken:
        show_findings(broken, f"REFUSED  the change would leave {len(broken)} failures:")
        print("nothing was written")
        return 1
    print(diff(store.parsed[R.KB].text if old is None else old, kb_text), end="")
    for label, ids in (("minted", minted), ("touched", touched)):
        if ids:
            print(f"{label:8} {curies(ids)}")
    for note in notes:
        print(f"note     {note}")
    if dry_run:
        print(f"dry run: r{rev} not written")
        return 0
    try:
        R.commit(root, kb_text, log_text)
    except R.RecordError as e:
        print(f"FAIL  {e}\n        fix: {e.fix}")
        return 1
    print(f"r{rev} written: career/kb.ttl and career/log.ttl")
    return 0


def changeset_text(path):
    """A changeset file's text. UTF-8, with or without a byte-order mark - and UTF-16 when a
    byte-order mark says so, because that is what Windows PowerShell 5.1's `>` and Out-File
    write. Anything else raises UnicodeDecodeError: guessing an encoding would guess words."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


@verb
def cmd_apply(args, root):
    """jsk kb apply <changeset.trig> [--dry-run]

    Merges a changeset (op:add, op:set, op:retire, op:delete; see docs/SCRIPTS.md) into
    career/kb.ttl, then logs it. A changed claim drops to j:inferred and is asked about; a
    new bullet gets its id; a sent metric version gets a successor instead of a change.
    --dry-run prints the diff and writes nothing.
    """
    from . import changeset, edit
    from . import store as S
    from .io import GraphError

    dry = bool(take(args, "--dry-run"))
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
                        dry_run=dry, notes=e.notes)


def iri_of(text):
    """k:prj_x, prj_x or c:kafka as an iri."""
    from . import ontology as O

    if text.startswith("k:"):
        return O.K + text[2:]
    if text.startswith("c:"):
        return O.C + text[2:]
    return O.K + text


def unknown(iri, store):
    from .writer import curie

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
    from .rules import DENIAL, PLACEHOLDER

    if DENIAL.fullmatch(answer):
        return refuse([f"{answer!r}: a denial is not a confirmation"], denial_fix)
    if PLACEHOLDER.fullmatch(answer):
        return refuse([f"{answer!r} is not an answer"],
                      "record what the person said, in their words: it is kept as the "
                      "reason this is confirmed")
    return None


def inside(path, root):
    here, top = (os.path.normcase(os.path.realpath(p)) for p in (path, root))
    return os.path.commonpath([here, top]) == top


def document_text(path):
    """(text, None) or (None, (reason, fix)): the words of a document to quote from."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".doc", ".odt", ".rtf"):
        return None, (f"{path}: a {ext} file is not read here", "convert it to .md or .txt first")
    if ext == ".pdf":
        from ..gates.check_ats import read_pdf
        try:
            return read_pdf(path)[0], None
        except ImportError:
            return None, (f"{path}: reading a PDF needs pymupdf, which this Python has not got",
                          "install pymupdf, or convert it to .md")
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return None, (f"{path} is not UTF-8 text", "convert it to .md or .txt first")


def scaled(numerals):
    from ..gates.numbers import SCALE
    return [value * SCALE.get(suffix, 1) for value, suffix, _ in numerals]


def unquoted_numbers(quads, iri, quote):
    """The numerals in an entry's claims the quote does not state - a number rounded or
    made up on the way out of the document."""
    from ..gates.numbers import numerals
    from . import ontology as O

    said = scaled(numerals(quote))
    kinds = {p.name for p in O.BY_NAME[O.class_of(iri)].preds.values()
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
WORD = re.compile(r"[a-z0-9]{4,}")


def stems(text):
    """The content words of `text` - four letters and longer - cut to five, so
    "onboarded" in a quote still meets "onboarding" in the claim."""
    from .rules import squash
    return {w[:5] for w in WORD.findall(squash(text).lower())}


def unquoted_words(quads, iri, quote):
    """The content words of an entry's prose claim the quote does not hold, when more
    than a fifth of them are missing - a clause the session added on the way out of the
    document ("Brought 42 sites onto one platform, cutting onboarding to two weeks" from
    a document that says only the first half), or a quote about something else."""
    from . import ontology as O

    pred = PROSE.get(O.class_of(iri))
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
    from .io import normalise
    from .rules import DENIAL, PLACEHOLDER, squash

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
    if squash(quote) not in squash(normalise(text)):
        return None, refuse([f"{source} does not say {quote!r}"],
                            "copy the words exactly as the document has them - the quote is "
                            "checked word for word")
    rel = os.path.relpath(os.path.abspath(source), root).replace(os.sep, "/")
    return f'From {rel}: "{squash(quote)}"', None


def confirm_summary(path, answer, root):
    """`jsk kb confirm --summary`: the summary confirmed in resume.json, beside the answer
    and its text's hash. Not logged in log.ttl: a logged write stamps kb.ttl with a new
    revision, and the summary is not in kb.ttl. resume.json holds the audit trail, and
    `jsk freeze` hashes it into application.ttl."""
    import json

    from ..cli import frozen_refusal
    from ..resume import short
    from . import record as R

    code = bad_answer(answer, "write the summary again with what the person said, and ask "
                              "them about the new words")
    if code is not None:
        return code
    if not inside(path, root):
        return refuse([f"{path}: not inside this workspace"], "pass the application's resume.json")
    if frozen_refusal(os.path.dirname(os.path.abspath(path))):
        return refuse([f"{path}: frozen - application.ttl beside it records it as it was sent"],
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
    with open(path, encoding="utf-8") as fh:
        old = fh.read()
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    R.replace(R.staged(path, text), path)
    print(diff(old, text, os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")),
          end="")
    print(f"confirmed the summary in {path}")
    return 0


@verb
def cmd_confirm(args, root):
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

    from . import ontology as O
    from . import record as R
    from . import store as S

    answer = take(args, "--answer", value=True)
    summary = take(args, "--summary", value=True)
    source = take(args, "--source", value=True)
    quote = take(args, "--quote", value=True)
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
        elif not O.BY_NAME[cls].claims:
            problems.append((f"{text} has no provenance to confirm: a {cls} is not a claim",
                             "confirm the entry that makes the claim"))
        elif any(q.subject.value == iri and q.predicate.value == O.J + "retired" for q in quads):
            problems.append((f"{text} is retired", "a retired entry is not confirmed"))
        elif source is not None and unquoted_numbers(quads, iri, quote):
            from ..gates.numbers import quoted
            missing = unquoted_numbers(quads, iri, quote)
            problems.append((f"{text} says {quoted(missing)}, which the quote does not",
                             "quote the document's sentence that states it - or, if the "
                             "document does not, ask the person and confirm with --answer"))
        elif source is not None and unquoted_words(quads, iri, quote):
            missing = unquoted_words(quads, iri, quote)
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


PROVENANCE_RANK = {"confirmed": 3, "inferred": 2, "needs-verification": 1, "disputed": 0}


def provenances(quads):
    from . import ontology as O
    return {q.subject.value: q.object.value[len(O.J):] for q in quads
            if q.predicate.value == O.J + "provenance"}


def claims(quads, s):
    from . import ontology as O
    names = O.resets(O.BY_NAME[O.class_of(s)])
    return {(q.predicate.value, q.object.value) for q in quads
            if q.subject.value == s and q.predicate.value[len(O.J):] in names}


def upgrades(before, after):
    """What a hand edit raised: provenance moved up, an entry added as confirmed, or a
    claim changed under a confirmation it no longer earns. Without the revision the log
    last recorded to compare against, every confirmed entry is listed."""
    from .writer import curie

    now = provenances(after)
    if before is None:
        return [f"{curie(s)} is confirmed" for s, p in sorted(now.items()) if p == "confirmed"]
    was, out = provenances(before), []
    for s, p in sorted(now.items()):
        if s not in was:
            if p == "confirmed":
                out.append(f"{curie(s)}: added as confirmed")
        elif PROVENANCE_RANK[p] > PROVENANCE_RANK[was[s]]:
            out.append(f"{curie(s)}: {was[s]} -> {p}")
        elif p == "confirmed" and claims(before, s) != claims(after, s):
            changed = sorted({curie(pred) for pred, _ in claims(before, s) ^ claims(after, s)})
            out.append(f"{curie(s)}: {', '.join(changed)} changed while confirmed")
    return out


def comments_refused(parsed):
    lines = [f"{parsed.file}:{n} {text}" for n, text in parsed.comments]
    return refuse([f"{len(lines)} hand comment(s) the canonical layout would drop:"] + lines,
                  "move each into a j:note on the entry it is about, or pass --drop-comments")


@verb
def cmd_adopt(args, root):
    """jsk kb adopt [--drop-comments]

    Logs career/kb.ttl as it now is: after a hand edit, a torn write, a restored file, or
    for a kb.ttl that has no log yet. It writes the file in the canonical layout and lists
    every provenance the edit raised - an entry marked confirmed by hand is exactly what
    `jsk kb confirm` exists to prevent, so each one is named, to be checked with the person.
    This is detection, not prevention: the edit already happened; adopt makes it visible.
    """
    from . import record as R
    from . import store as S
    from .io import parse_text

    drop = bool(take(args, "--drop-comments"))
    if args:
        return usage("jsk kb adopt takes no arguments")
    store = S.load(root)
    st = R.state(store)
    if st.kind == "clean":
        print(f"nothing to adopt: career/kb.ttl is what r{st.log_revision} logged")
        return 0
    code = writable(store, allow=("unlogged", "hand-edited", "torn", "out-of-sync"))
    if code is not None:
        return code
    if store.parsed[R.KB].comments and not drop:
        return comments_refused(store.parsed[R.KB])
    old = R.shadow(root, st.logged_sha)
    before = parse_text(old, R.KB).quads if old is not None else None
    after = store.graph(R.KB)
    raised = upgrades(before, after)
    # With nothing to compare against, every entry may have changed: log them all, so a
    # changeset drafted before this edit still conflicts with it through op:base.
    touched = ({q.subject.value for q in set(before) ^ set(after)} if before is not None
               else {q.subject.value for q in after})
    what = {"unlogged": "a kb.ttl with no log yet", "hand-edited": "a hand edit",
            "torn": "a write that did not reach log.ttl", "out-of-sync": "a restored file"}[st.kind]
    compared = "" if before is not None or st.kind == "unlogged" else \
        f" No copy of r{st.log_revision} to compare against, so every confirmed entry is listed."
    summary = (f"Adopted {what}.{compared} " + ("Raised: " + "; ".join(raised) + "." if raised
                                               else "Raised no provenance.")).strip()
    for line in raised:
        print(f"raised   {line}")
    if raised:
        print("         check each with the person; `jsk kb confirm <id> --answer` records it")
    return write_logged(store, root, after, "adopt", summary, touched, old=old)


@verb
def cmd_fmt(args, root):
    """jsk kb fmt [<file>...] [--drop-comments]

    Rewrites record files in the canonical layout - career/kb.ttl when none is named. A
    reformat of kb.ttl is logged on its own (`by fmt`), so no content change can hide in
    it; a hand-edited kb.ttl is adopted, not formatted. Any other record file (a
    posting.ttl, an application.ttl) is rewritten in place and not logged. Hand comments
    would be lost, so a file holding any is refused unless --drop-comments.
    """
    from . import ontology as O
    from . import record as R
    from . import store as S
    from .writer import WriteError, write

    drop = bool(take(args, "--drop-comments"))
    store = S.load(root)
    names = [S.file_name(os.path.abspath(a), root) for a in args] or [R.KB]
    for name in names:
        if name == R.LOG:
            return refuse(["career/log.ttl is written by jsk only"], "leave it; every write keeps it")
        if name not in store.parsed or O.kind_of(name) in (None, "vocabulary"):
            return usage(f"{name}: not a record file of this workspace that parses")
    code = 0
    for name in names:
        parsed = store.parsed[name]
        if parsed.comments and not drop:
            code = comments_refused(parsed)
            continue
        try:
            text = write(store.graph(name), parsed.kind)
        except WriteError as e:
            code = refuse([f"{name}: {e}"], "`jsk kb check` shows what is wrong with it")
            continue
        if text == parsed.text:
            print(f"{name}: already canonical")
            continue
        if name == R.KB:
            refused = writable(store, canonical=False)
            code = refused if refused is not None else write_logged(
                store, root, store.graph(R.KB), "fmt", "Reformatted kb.ttl; no content changed.",
                content=False)
            continue
        path = os.path.join(root, name)
        R.replace(R.staged(path, text), path)
        print(diff(parsed.text, text, name), end="")
        print(f"{name}: rewritten")
    return code


def entry_text(quads, iri):
    """One entry as kb.ttl writes it - every part, for the Person's Positioning too."""
    from .writer import Subjects, block

    sub = Subjects(quads)
    parts = ["main"] + sorted({p.section for p in sub.cls[iri].preds.values() if p.section})
    return "\n\n".join(b[0] for b in (block(sub, iri, part) for part in parts) if b)


def with_children(quads, iri):
    """The entry and what is read with it: a project's bullets, a metric's versions."""
    from . import ontology as O

    def of(pred):
        return sorted({q.subject.value for q in quads if q.predicate.value == O.J + pred
                       and q.object.value == iri})
    kids = {"Project": sorted(of("project"), key=lambda a: rank(quads, a)),
            "Metric": sorted(of("of"), key=lambda v: int(v.rsplit(".v", 1)[1]))}
    return [iri] + kids.get(O.class_of(iri), [])


def rank(quads, iri):
    from . import ontology as O
    return next((int(q.object.value) for q in quads if q.subject.value == iri
                 and q.predicate.value == O.J + "rank"), 1 << 30)


@verb
def cmd_show(args, root):
    """jsk kb show <id>... [--bullets]

    The entries as their files hold them, in the canonical layout: a project with its
    bullets, a metric with its versions. The first line is the revision to put in a
    changeset's op:base, so a change drafted from what was shown is checked against it.

    --bullets prints a project as its name and its bullets only - what citing it as
    evidence needs - without the problem, decisions and notes, which run to thousands of
    characters a project.
    """
    from . import ontology as O
    from . import record as R
    from . import store as S
    from .writer import curie

    bullets = bool(take(args, "--bullets"))
    if not args:
        return usage("jsk kb show takes one or more ids")
    store = S.load(root)
    st = R.state(store)
    print(f"# r{st.log_revision} - op:base {st.log_revision}" if st.log_revision else
          "# not logged yet - `jsk kb adopt` starts the log")
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


@verb
def cmd_view(args, root):
    """jsk kb view [--section NAME]

    The whole career as Markdown, in kb.ttl's section order, to read end to end and
    correct - stdout only; it is never written to a file, so it cannot drift. Entries not
    confirmed, and retired ones, say so beside their names.
    """
    from . import record as R
    from . import store as S
    from .view import render

    only = take(args, "--section", value=True)
    if args:
        return usage("jsk kb view takes only --section NAME")
    store = S.load(root)
    if R.KB not in store.parsed:
        return refuse([GUIDE[R.state(store).kind][0]], GUIDE[R.state(store).kind][1])
    print(render(store.graph(R.KB), only), end="")
    return 0


@verb
def cmd_export(args, root):
    """jsk kb export [--select <id>...] [--from-match <posting.ttl> [--cover N] | --ranked]
                     [--today YYYY-MM-DD] [--out resume.json]

    The short resume.json an application starts from: the bullets it shows, in order,
    and its settings - `"resume": 2`, the region when a profile ships for the person's
    country, `"pages": 2`. Nothing the career holds is copied: the render reads the
    words, numbers and dates from kb.ttl as it stands, so a changeset applied or a bullet
    confirmed afterwards is in the next ship with nothing to update.

    --select names what to show: prj_ brings a project and its bullets, ach_ one bullet
    (and narrows its project to the bullets named), pos_ a role shown with no bullet.
    Retired entries never come. With none of --select, --from-match or --ranked, the
    whole career.

    --from-match chooses the bullets from `jsk match`: the projects that carry the
    posting with confirmed evidence, their bullets by what they show, the skills the
    posting asks for first. What it cannot close prints as GAP lines - tag-only,
    unconfirmed, uncovered, unresolved - for gaps.md. --select adds to it; --cover and
    --today are jsk match's.

    --ranked is the same with no posting, for a general rebuild: the projects by strength
    and recency, their confirmed bullets by the same bands, a bullet citing a current
    number first. The scorer chooses rather than the model, as it does for a posting.
    --select adds to it.

    --out writes the file, never over an existing one; without it the file is printed.

    A number in a chosen bullet that no current metric version holds is printed as a
    WARN: it is in kb.ttl, not in anything authored, so it is a question for the person
    before any word is retuned.

    --urs and --refresh are gone with the full record: the short file is the one format,
    and there is nothing in it to refresh.
    """
    import json

    from . import ontology as O
    from . import record as R
    from . import store as S
    from .export import Career, ExportError, chosen, short_file
    from .match import COVER, blocks, workspace_of
    from .writer import curie

    # Said by name rather than as an unknown flag: an agent file or a shell history
    # written before the short file still has them.
    if "--urs" in args:
        return usage("--urs is gone: export writes the short resume.json, the one format "
                     "there is - drop --urs")
    if "--refresh" in args:
        return usage("--refresh is gone: a short resume.json holds ids, and every render "
                     "builds from kb.ttl as it stands, so there is nothing to refresh. A full "
                     "URS record is converted once with `jsk migrate`")
    out = take(args, "--out", value=True)
    posting = take(args, "--from-match", value=True)
    by_rank = take(args, "--ranked")
    cover_text = take(args, "--cover", value=True)
    today_text = take(args, "--today", value=True)
    select = None
    if "--select" in args:
        at = args.index("--select")
        select = []
        while at + 1 < len(args) and not args[at + 1].startswith("--"):
            select += [i for i in args.pop(at + 1).split(",") if i]
        args.pop(at)
        if not select:
            return usage("--select needs one or more ids")
    if args:
        return usage("jsk kb export [--select <id>...] [--from-match <posting.ttl> | --ranked] "
                     "[--out resume.json] - the short resume.json is the one format it writes")
    if posting and by_rank:
        return usage("--ranked is the selection with no posting, --from-match the one for a "
                     "posting - give one")
    if cover_text and not posting:
        return usage("--cover goes with --from-match")
    if today_text and not (posting or by_rank):
        return usage("--today goes with --from-match or --ranked")
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
    if posting:
        home = workspace_of(posting)
        if (home is None or not os.path.isfile(posting)
                or os.path.normcase(os.path.realpath(home))
                != os.path.normcase(os.path.realpath(root))):
            return usage(f"{posting}: not a posting.ttl inside this workspace's "
                         "applications/<dir>/ folder")
    store = S.load(root)
    if R.KB not in store.parsed:
        st = R.state(store)
        return refuse([GUIDE[st.kind][0] or st.detail], GUIDE[st.kind][1])
    # The career always; with --from-match, the posting's own directory too, as jsk match.
    here = (S.file_name(os.path.dirname(os.path.abspath(posting)), store.root) + "/"
            if posting else None)
    blocking = [f for f in store.fails() if f.rule != "log-sync"
                and (not f.file.startswith("applications/") or (here and blocks(f, here)))]
    if blocking:
        where = "the career and the posting have" if posting else "the career has"
        show_findings(blocking, f"REFUSED  {where} {len(blocking)} failures - "
                                "a resume would carry them:")
        return 1
    if out and os.path.exists(out):
        return refuse([f"{out} exists - export writes a new resume.json, never over one"],
                      "edit it, or delete it to start again - it holds only ids and settings, "
                      "and the career is read afresh at every render")
    selection, notes = None, []
    report = sys.stdout if out else sys.stderr
    try:
        if posting or by_rank:
            from . import select as SEL
            chosen(Career(store.graph(R.KB)), select)      # a bad --select refuses first
            extra = [O.K + t.removeprefix("k:") for t in select or []]
        if by_rank:
            selection = SEL.ranked(store, today, extra)
        elif posting:
            posts = [iri for iri in store.homes if O.class_of(iri) == "Posting"
                     and store.file_of(iri) == S.file_name(posting, store.root)]
            if len(posts) != 1:
                return refuse([f"{posting} holds no posting"], "check it with `jsk kb check`")
            selection = SEL.select(store, posts[0], today, budget, extra)
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
        print(f"WARN  {len(faults)} check(s) fail on the chosen bullets as kb.ttl holds them - "
              "a question for the person, answered in kb.ttl (`jsk kb apply`) before any "
              "word is retuned:", file=report)
        for line in faults:
            print(f"        {line}", file=report)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if not out:
        sys.stdout.write(text)
        return 0
    wrote(store, out, text, doc)
    print("next: order `bullets`, add a `summary` and set `pages` or `format` if this posting "
          "wants them, then `jsk validate` it - a reworded bullet goes into the career first, "
          "with `jsk kb apply`")
    return 0


def wrote(store, path, text, doc):
    from . import record as R

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    st = R.state(store)
    at = f" at r{st.log_revision}" if st.log_revision else ""
    print(f"wrote {path}: {len(doc['bullets'])} bullets chosen from career/kb.ttl{at}")


@verb
def cmd_query(args, root):
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

    A table by default; --json for the same rows, structured.
    """
    import json

    from . import store as S
    from .named import QUERIES, table

    as_json = bool(take(args, "--json"))
    if not args or args[0] not in QUERIES:
        return usage(f"jsk kb query takes one of: {', '.join(QUERIES)}")
    name, rest = args[0], args[1:]
    want, _, fn = QUERIES[name]
    if want.endswith("...") and not rest or not want.endswith("...") and len(rest) != len(want.split()):
        return usage(f"jsk kb query {name} {want}".rstrip())
    columns, rows = fn(S.load(root), *rest)
    print(json.dumps(rows, indent=2, ensure_ascii=False) if as_json else table(columns, rows))
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
    from ..gates import numbers
    from ..resume.career import Career
    from . import record as R
    from .shapes import curie

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


@verb
def cmd_check(args, root):
    """jsk kb check

    Validates the whole workspace - every rule, every file - and says where kb.ttl and
    log.ttl stand, and which record files are not in the canonical layout. Exit 1 on any
    FAIL; a WARN is printed and passes.

    It also asks the record gate's number check of every live bullet: a bullet it
    refuses fails every resume that selects it, so it is warned of here, once, rather
    than found by each resume run.
    """
    from ..gates.report import show
    from . import record as R
    from . import store as S
    from .writer import WriteError, write

    if args:
        return usage("jsk kb check takes no arguments")
    store = S.load(root)
    rep = store.report()
    for name, parsed in sorted(store.parsed.items()):
        if parsed.kind in ("kb", "log", "posting", "application"):
            try:
                if write(parsed.quads, parsed.kind) != parsed.text:
                    rep.warn(f"{name} - not in the canonical layout\n        fix: `jsk kb fmt {name}`")
            except WriteError:
                pass                     # a file the writer cannot lay out has a FAIL already
    if not rep.fails and R.KB in store.parsed:
        for line in untraced_lines(store, datetime.date.today()):
            rep.warn(f"a record selecting it fails a gate: {line}\n        fix: record the "
                     "number as a metric version and cite it (j:cites), or correct the words, "
                     "with `jsk kb apply` - every application selecting it pays this otherwise")
    st = R.state(store)
    print(f"record   {st.kind}" + (f" at r{st.log_revision}" if st.log_revision else "")
          + (f" - {st.detail}" if st.detail else ""))
    print(f"{len(rep.fails)} FAIL, {len(rep.warns)} WARN")
    show(rep.fails, "FAIL", 0)
    show(rep.warns, "WARN", 0)
    return 1 if rep.fails else 0


@verb
def cmd_path(args, root):
    """jsk kb path [--root DIR]

    Prints where the record is, as absolute paths: the workspace, career/kb.ttl,
    career/log.ttl and applications/. Run it from anywhere inside the workspace - an
    application directory will do - and read the files at the paths it prints.

    The workspace is the folder holding career/, so kb.ttl sits at
    <workspace>/career/kb.ttl. A workspace that is itself named `career` puts it at
    career/career/kb.ttl, which is why the path is printed rather than worked out.
    Needs nothing but the files; exit 1 when there is no career/kb.ttl there.
    """
    if args:
        return usage("jsk kb path takes no arguments")
    kb = os.path.join(root, "career", "kb.ttl")
    if not os.path.isfile(kb):
        print(f"no career/kb.ttl under {root}")
        if os.path.isfile(os.path.join(root, "kb.ttl")):
            print(f"        fix: that folder is career/ itself - the workspace is {os.path.dirname(root)}")
        return 1
    print(f"workspace     {root}")
    print(f"kb            {kb}")
    print(f"log           {os.path.join(root, 'career', 'log.ttl')}")
    print(f"applications  {os.path.join(root, 'applications')}")
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
    try:
        root = take(rest, "--root", value=True) or find_root(os.getcwd())
    except SystemExit as e:
        return e.code
    if root is None or not os.path.isdir(root):
        return usage("no workspace here: run it inside one, or pass --root DIR "
                     "(the folder holding career/)")
    if name == "path":
        return cmd_path(rest, os.path.abspath(root))
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk kb needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    try:
        return VERBS[name](rest, os.path.abspath(root))
    except SystemExit as e:
        return e.code


if __name__ == "__main__":
    sys.exit(main())
