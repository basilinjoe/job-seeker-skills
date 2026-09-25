"""jsk kb - the career record: changed through changesets, read by id.

Usage: jsk kb <verb> [arguments] [--root DIR]

  apply <changeset.trig> [--dry-run]   merge a changeset into career/kb.ttl; prints the diff
  confirm <id>... --answer "..."       confirm entries with the person's answer, logged
  adopt [--drop-comments]              log a hand edit, listing every provenance it raised
  fmt [<file>...] [--drop-comments]    rewrite in the canonical layout; kb.ttl's is logged
  show <id>... [--bullets]             entries as kb.ttl holds them, and the op:base to use;
                                       --bullets, a project's name and bullets only
  view [--section NAME]                the whole career as Markdown, to read
  query <name> [args] [--json]         open | unconfirmed | holds <concept> | stale |
                                       experience <concept> | pipeline |
                                       evidence <term>... | person
  export --urs [--select <id>...]      a draft resume.json, ids and metrics as held
         [--out FILE]
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
    from ..gates.validate_urs import show
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


@verb
def cmd_confirm(args, root):
    """jsk kb confirm <id>... --answer "what the person said"

    The only way an entry becomes j:confirmed. Ask the person; record their answer in their
    words. Each entry named is confirmed, every open question about it is answered today,
    and the log keeps the answer beside the ids - the audit trail of why it is confirmed.
    An answer that says nothing ("yes", "ok", "confirmed") is refused.
    """
    import pyoxigraph as ox

    from . import ontology as O
    from . import record as R
    from . import store as S
    from .rules import DENIAL, PLACEHOLDER

    answer = take(args, "--answer", value=True)
    if not args or answer is None:
        return usage('jsk kb confirm takes ids and --answer "what the person said"')
    if DENIAL.fullmatch(answer):
        return refuse([f"{answer!r}: a denial is not a confirmation"],
                      "record what they said is wrong: op:set the entry's j:provenance "
                      "j:disputed, or correct it with `jsk kb apply`")
    if PLACEHOLDER.fullmatch(answer):
        return refuse([f"{answer!r} is not an answer"],
                      "record what the person said, in their words: the log keeps it as the "
                      "reason this is confirmed")
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
    """jsk kb export --urs [--select <id>...] [--out resume.json]

    A draft resume.json out of career/kb.ttl: every id, provenance, period and metric as
    the career holds them (a metric at its current version), so the draft passes
    `jsk validate` and the claims gate before a word is changed. Retune the words and the
    view; the gates check what changed.

    --select narrows the experience: prj_ brings a project and its bullets, ach_ one
    bullet (and its project), pos_ a role. An employer always comes with every role held
    there. The person, skills, education and the rest come across whole. Retired entries
    never do. Without --select, the whole career.

    --out writes the file, never over an existing one; without it the record is printed.
    """
    import json

    from . import record as R
    from . import store as S
    from .export import ExportError, urs

    out = take(args, "--out", value=True)
    fmt = take(args, "--urs")
    select = None
    if "--select" in args:
        at = args.index("--select")
        select = []
        while at + 1 < len(args) and not args[at + 1].startswith("--"):
            select += [i for i in args.pop(at + 1).split(",") if i]
        args.pop(at)
        if not select:
            return usage("--select needs one or more ids")
    if args or not fmt:
        return usage("jsk kb export --urs [--select <id>...] [--out FILE] - URS is the "
                     "one format it writes")
    store = S.load(root)
    if R.KB not in store.parsed:
        st = R.state(store)
        return refuse([GUIDE[st.kind][0] or st.detail], GUIDE[st.kind][1])
    blocking = [f for f in store.fails() if f.rule != "log-sync"
                and not f.file.startswith("applications/")]
    if blocking:
        show_findings(blocking, f"REFUSED  the career has {len(blocking)} failures - "
                                "a draft would carry them:")
        return 1
    if out and os.path.exists(out):
        return refuse([f"{out} exists - export writes a draft, never over a record"],
                      "export to a new path, or delete the old record first")
    try:
        doc = urs(store, select, today=datetime.date.today())
    except ExportError as err:
        return refuse([str(err)], err.fix)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    loose = [p["id"] for p in doc.get("projects", []) if "engagement" not in p]
    for pid in loose:
        print(f"NOTE  {pid} names no role (j:position), so no engagement lists it and it "
              "will not render", file=sys.stderr if not out else sys.stdout)
    if not out:
        sys.stdout.write(text)
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    bullets = sum(len(p["achievements"]) for p in doc.get("projects", []))
    st = R.state(store)
    at = f" at r{st.log_revision}" if st.log_revision else ""
    print(f"wrote {out}: {len(doc.get('projects', []))} projects, {bullets} bullets "
          f"from career/kb.ttl{at}")
    print("next: retune the words and the view, then `jsk validate` it - a reworded "
          "bullet goes into the career first, with `jsk kb apply`")
    return 0


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


@verb
def cmd_check(args, root):
    """jsk kb check

    Validates the whole workspace - every rule, every file - and says where kb.ttl and
    log.ttl stand, and which record files are not in the canonical layout. Exit 1 on any
    FAIL; a WARN is printed and passes.
    """
    from ..gates.validate_urs import show
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
