"""The record's reads and writes, called the way the MCP tools call them, for tests.

The rule this serves is docs/superpowers/plans/2026-10-04-retire-duplicated-cli.md, Ruling 6:
`jsk kb apply|confirm|show|view|query|log` and `jsk app freeze|event` and `jsk letter check`
were retired, so a test of what they did calls what the career_*, app_* and letter_check
tools call - adapters/compose/career.py, selection.py and timeline.py, and the letter
gate - and no test goes through a front end that no longer exists.

Each function returns `(exit code, output text)` in the shape the old command's helper
returned, so an assertion on the output carries over: the diff, `REFUSED  ...` lines with
their `fix:`, `nothing was written`. The codes are the commands' own: 0 done, 1 refused,
2 called wrong. Where a tool's words differ from what the command printed, this kit says the
tool's words and a comment names the difference - a test asserts the tool's text, not a
retired command's.

Standard library only, like the package under test; `fixtures` puts this checkout's src/
first on sys.path, and jsk is imported inside each function so importing the kit costs
nothing.
"""
import contextlib
import datetime
import io
import json
import os

import fixtures  # noqa: F401 - puts this checkout's src/ first on sys.path


# How the retired `jsk kb query` printed a query's rows, kept for the tests that read them.
def table(columns, rows):
    """A named query's rows as a Markdown table; `|` in a value is escaped so the row keeps
    its cells.

    Args:
        columns: the column names, in order.
        rows: dicts holding a value for each column.

    Returns:
        The table's text, without a trailing newline.
    """
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    out += ["| " + " | ".join(cell(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join(out)


def captured(fn):
    """(exit code, what `fn` printed): `fn` runs with stdout caught and returns the code."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = fn()
    return code, out.getvalue()


def refused_by(err):
    """The exit code of a refusal a record use case raised, having printed it as the old
    verbs did (adapters/entry/kb/write.py's `refused`)."""
    from jsk.adapters.entry.kb.write import refused

    return refused(err)


REFUSALS = ("Failing", "Problems", "Refused", "Unclean")


def refusal_types():
    """The refusal classes of application/record/refusals.py, as a tuple to catch."""
    from jsk.application.record import refusals

    return tuple(getattr(refusals, name) for name in REFUSALS)


def written(w, dry_run):
    """Print a logged write as the old verbs did: the diff, the ids it minted and touched,
    its notes, and whether it landed. Returns 0."""
    from jsk.domain.record.writer import curies

    print(w.diff, end="")
    for label, ids in (("minted", w.minted), ("touched", w.touched)):
        if ids:
            print(f"{label:8} {curies(ids)}")
    for note in w.notes:
        print(f"note     {note}")
    print(f"dry run: r{w.revision} not written" if dry_run
          else f"r{w.revision} written: career/store/")
    return 0


def apply(root, text, dry_run=False, today=None):
    """What `jsk kb apply` did, as career_preview (`dry_run`) and career_apply do it.

    Args:
        root: the workspace.
        text: the changeset, as TriG (a tool takes the text, not a path).
        dry_run: validate and print the diff, and write nothing.
        today: the day a changed claim is dated; the clock when None.

    Returns:
        (0 written or nothing to change, 1 refused; the output).
    """
    from jsk.adapters.compose import career
    from jsk.adapters.entry.presenters import unwritten
    from jsk.domain.record.state import RecordError

    def run():
        try:
            done = career.apply_changeset(root, text, dry_run=dry_run,
                                          today=today or datetime.date.today())
        except refusal_types() as err:
            return refused_by(err)
        except RecordError as err:
            return unwritten(err)
        if done is None:
            print("nothing to change: the record already says all of that")
            return 0
        return written(done, dry_run)
    return captured(run)


def confirm(root, ids=(), answer=None, source=None, quote=None, target=None, block=None,
            today=None):
    """What `jsk kb confirm` did, as career_confirm does it.

    Args:
        root: the workspace.
        ids: the entries to confirm (curies or bare ids).
        answer: the person's own words; or `source` and `quote`, a document and its words.
        target, block: a selection's summary or headline instead of ids: the target
            (`<stem>` or `resumes/<name>`) and "summary" or "headline", with `answer`.
        today: the day the answers are dated; the clock when None.

    Returns:
        (0 done or nothing to change, 1 refused, 2 called wrong; the output).
    """
    from jsk.adapters.compose import career, selection
    from jsk.adapters.entry.presenters import unwritten
    from jsk.domain.record.state import RecordError, diff

    today = today or datetime.date.today()

    def called_wrong(text, fix):
        # The tool's FAIL, which is what the command said as usage.
        print(f"FAIL  {text}\n        fix: {fix}")
        return 2

    def run():
        if (source is None) != (quote is None):
            return called_wrong("source and quote go together: the file, and the words in it",
                                "pass both, or answer instead")
        if source is not None and answer is not None:
            return called_wrong("answer, or source and quote: two ways to confirm", "pass one")
        if target is not None or block is not None:
            if ids or target is None or block is None or answer is None:
                return called_wrong("a selection's block is confirmed alone: target, block "
                                    "and the person's answer, no ids",
                                    "pass target, block and answer")
            try:
                done = selection.confirm(root, target, block, answer)
            except refusal_types() as err:
                return refused_by(err)
            if done.new is None:
                print(f"nothing to change: the {block} is confirmed already")
                return 0
            print(diff(done.old, done.new, f"{target}/resume"), end="")
            print(f"confirmed the {block} in {target}")
            return 0
        if not ids or (answer is None and source is None):
            return called_wrong("confirm takes ids and the person's answer, or a source and "
                                "its quote",
                                "pass ids with answer (their words), or source and quote")
        try:
            done = career.confirm_ids(root, list(ids), answer=answer, source=source,
                                      quote=quote, today=today)
        except refusal_types() as err:
            return refused_by(err)
        except RecordError as err:
            return unwritten(err)
        if done is None:
            print("nothing to change: every one of them is confirmed already")
            return 0
        return written(done, False)
    return captured(run)


def show(root, ids, bullets=False):
    """What `jsk kb show` printed, as career_show returns it: the revision line, then each
    entry as Turtle under the name of its graph; a missing id as `REFUSED` and exit 1.

    The first line is `# r<N> - op:base <N>`, as the command printed it.
    """
    from jsk.adapters.compose import career

    def run():
        try:
            shown = career.show(root, list(ids), bullets)
        except refusal_types() as err:
            return refused_by(err)
        revision = shown.log_revision
        print(f"# r{revision} - op:base {revision}" if revision else
              "# not logged yet - `jsk kb check` says why")
        code = 0
        for entry in shown.entries:
            if entry.missing:
                detail, fix = entry.missing
                print(f"\nREFUSED  {detail}\n        fix: {fix}")
                code = 1
                continue
            for name, heading, text in entry.graphs:
                print(f"\n# {name}")
                if heading:
                    print(heading)
                print(text)
        return code
    return captured(run)


def view(root, section=None):
    """What `jsk kb view` printed, as career_view returns it (whole, not paged): the career
    as Markdown, or a refusal (exit 1) when the record is not there."""
    from jsk.adapters.compose import career
    from jsk.application.record.refusals import Unclean
    from jsk.adapters.entry.presenters import GUIDE, refuse

    def run():
        try:
            text = career.view(root, section)
        except Unclean as err:
            return refuse([GUIDE[err.state.kind][0]], GUIDE[err.state.kind][1])
        print(text, end="")
        return 0
    return captured(run)


def query(root, name, *args, json=False, today=None):
    """What `jsk kb query` printed, as career_query returns it: a Markdown table, or with
    `json` the rows as JSON. For `concepts`, `args` are the terms `--near` took, one table
    each under `== <term>`.

    Returns:
        (0, the output), or (2, why) for a name or arguments the query does not take.
    """
    import json as jsonlib

    from jsk.adapters.compose import career
    from jsk.application.record.refusals import Refused

    as_json = json

    def run():
        try:
            got = career.query(root, name, args, today=today or datetime.date.today())
        except Refused as err:
            # The command said its usage line; the tool says the refusal.
            print("\n".join(err.lines))
            print(f"fix: {err.fix}")
            return 2
        if isinstance(got, dict):
            if as_json:
                print(jsonlib.dumps({t: rows for t, (_, rows) in got.items()}, indent=2,
                                    ensure_ascii=False))
            else:
                print("\n\n".join(f"== {t}\n{table(c, rows)}" for t, (c, rows) in got.items()))
            return 0
        columns, rows = got
        print(jsonlib.dumps(rows, indent=2, ensure_ascii=False) if as_json
              else table(columns, rows))
        return 0
    return captured(run)


def log(root, last=10):
    """What `jsk kb log` printed, as career_log returns it: each revision newest first with
    the ids it minted and touched."""
    from jsk.adapters.compose import career
    from jsk.adapters.entry.presenters import refuse
    from jsk.application.record.refusals import Refused
    from jsk.domain.record.writer import curies

    def run():
        if last < 1:
            print(f"last {last}: a count, 1 or more")
            return 2
        try:
            entries = career.log(root, last)
        except Refused as err:
            return refuse(err.lines, err.fix)
        for e in entries:
            print(f"r{e.revision}  {e.date}  {e.by:8} {e.summary}")
            for label, ids in (("minted", e.minted), ("touched", e.touched)):
                if ids:
                    print(f"    {label:8} {curies(ids)}")
        return 0
    return captured(run)


def app_dir_of(root, app):
    """The application directory `app` names - a path, or a stem under applications/ - as
    adapters/mcp/acts.py's app_dir_of finds it; None when there is none."""
    if os.path.isdir(app):
        return os.path.abspath(app)
    name = str(app).replace("\\", "/").strip("/").removeprefix("applications/")
    path = os.path.join(root, "applications", name)
    return path if name and "/" not in name and os.path.isdir(path) else None


def freeze(root, app, submitted, channel, docs=None):
    """What `jsk app freeze` printed, as app_freeze does it: the gates' results, then
    `froze` and `moved` lines; a refusal as `REFUSED - ...` and exit 1.

    Args:
        root: the workspace.
        app: the application, as a stem, `applications/<stem>` or a directory.
        submitted: YYYY-MM-DD, or "false" for one held back.
        channel: where it was sent.
        docs: the documents to carry, or None to list the directory's.

    Returns:
        (0 frozen, 1 refused, 2 called wrong; the output). The closing paragraph names the
        app_event and career_query tools where the command named `jsk app event` and
        `jsk kb query pipeline`.
    """
    from jsk.adapters.compose import timeline as T
    from jsk.adapters.entry.gates.check import print_results
    from jsk.application.timeline import freeze as F
    from jsk.application.timeline.unsent import note
    from jsk.domain.timeline.events import is_date

    def run():
        app_dir = app_dir_of(root, app)
        if app_dir is None:
            print(f"no application directory applications/{app}")
            return 2
        if submitted != "false" and not is_date(submitted):
            print(f"submitted needs YYYY-MM-DD or false, got {submitted!r}")
            return 2
        if not str(channel).strip():
            print("channel is required")
            return 2
        if T.made_from_files(app_dir):
            text, fix = note(os.path.basename(app_dir))
            print(f"FAIL  {text}; app_freeze freezes a graph-native one\n        fix: {fix}")
            return 2
        try:
            done = T.freeze_app(app_dir, root, submitted, channel.strip(), docs or None,
                                gated=lambda results: print_results(f"gates: {app_dir}",
                                                                          results))
        except F.FreezeRefused as refusal:
            print("REFUSED - " + refusal.lines[0])
            for line in refusal.lines[1:]:
                print("  " + line)
            return 1
        except F.FreezeLanded as landed:
            print(f"FAIL  the application's record was written, and then: {landed}")
            print(f"      fix: {landed.fix}")
            return 1
        print(f"froze  {done.written}")
        if done.final != done.app_dir:
            print(f"moved  {done.app_dir} -> {done.final}")
        print(done.final)
        print()
        print("Frozen on the mechanical gates. The render gate is a person's: freezing")
        print("assumes somebody opened the PDF and read it. Nothing in this directory is")
        print("edited again; later events are the app_event tool (jsk mcp), and the")
        print("career_query tool's `pipeline` gives each application's stage.")
        return 0
    return captured(run)


def event(root, app, kind, date, channel=None, note=None, due=None, today=None):
    """What `jsk app event` printed, as app_event does it: the diff of the event added,
    `added    <iri>`, `recorded <kind> on <date>`, and a WARN for a date after today.

    Args:
        root: the workspace.
        app: the application, as a stem, `applications/<stem>` or a directory.
        kind: one of the pipeline vocabulary (ontology.ENUMS["eventKind"]).
        date: YYYY-MM-DD or "unknown": the day it happened.
        channel, note, due: the event's other fields.
        today: the day the call runs on (a date or YYYY-MM-DD); the clock when None.

    Returns:
        (0 added, 1 refused, 2 called wrong; the output).
    """
    import difflib

    from jsk.adapters.compose import timeline as T
    from jsk.application.timeline.add_event import EventLanded, EventRefused
    from jsk.domain import ontology as O
    from jsk.domain.timeline.events import is_date, when

    kinds = O.ENUMS["eventKind"]
    if isinstance(today, str):
        today = datetime.date.fromisoformat(today)
    today = today or datetime.date.today()

    def run():
        app_dir = app_dir_of(root, app)
        if app_dir is None:
            print(f"no application directory applications/{app}")
            return 2
        if kind not in kinds:
            near = difflib.get_close_matches(kind, kinds, n=1, cutoff=0.5)
            print(f"unknown kind: {kind!r} - " + (f"did you mean {near[0]!r}? " if near else "")
                  + f"one of {', '.join(kinds)}")
            return 2
        if date != "unknown" and not is_date(date):
            print(f"date needs YYYY-MM-DD or unknown, got {date!r}")
            return 2
        if due is not None and not is_date(due):
            print(f"due needs YYYY-MM-DD, got {due!r}")
            return 2
        if not T.has_record(app_dir, "application"):
            print(f"REFUSED  {app_dir} holds no application record\n"
                  "        fix: an application gets one when it is frozen: the app_freeze tool\n"
                  "nothing was written")
            return 1
        try:
            done = T.add_event(root, app_dir, kind, date, channel, note, due, today)
        except EventRefused as err:
            for line in err.lines:
                print(f"REFUSED  {line}")
            print(f"        fix: {err.fix}")
            print("nothing was written")
            return 1
        except EventLanded as err:
            print(f"FAIL     {err}")
            print(f"        fix: {err.fix}")
            return 1
        print(done.diff, end="")
        print(f"added    {done.iri}")
        print(f"recorded {done.kind} on {when(done.date, done.today)}")
        if done.due:
            print(f"due {when(done.due, done.today)}")
        if done.ahead:
            print(f"WARN  {done.date} is after today, and the date is the day it happened - a "
                  "meeting still to come is the due of its -scheduled event; an event is "
                  "never edited, so correct this one with a `note` event")
        return 0
    return captured(run)


def letter(letter_path, record_target, root):
    """What `jsk letter check` printed, as letter_check runs it: the gate's heading,
    findings and verdict line (`PASS - fit to send`, ...), and its exit code.

    Args:
        letter_path: the letter, a path or relative to `root`.
        record_target: the target it goes out beside: `<stem>`, `resumes/<name>`, or a
            resume.json path (which the gate refuses, naming the target form).
        root: the workspace.

    Returns:
        (the gate's exit code - 0 fit to send, 1 do not send, 2 called wrong; the output).
    """
    from jsk.adapters.compose.selection import ref_for
    from jsk.adapters.entry.gates import letter as gate

    path = letter_path if os.path.isabs(letter_path) else os.path.join(root, letter_path)
    against = ref_for(record_target, dirs=True, root=root) or (
        record_target if os.path.isabs(record_target) else os.path.join(root, record_target))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code, _ = gate.gate([path, "--record", against])
    return code, out.getvalue()


def kb_verb(root, *args):
    """The kb adapter's `check`, `pack` or `merge` as the career_check, career_pack and
    career_merge tools run it: inside `root`, through adapters/mcp/captured.py, with stderr
    kept apart (a draft's notes go there, and the tools return them as `notes`).

    Args:
        root: the workspace.
        args: the verb and its arguments; `--root` is added.

    Returns:
        (exit code, what it printed to stdout, what it printed to stderr).
    """
    from jsk.adapters.mcp import captured

    err = io.StringIO()
    code, out = captured.ran(root, "kbcli.py", [*args, "--root", root], err=err)
    return code, out, err.getvalue()


def kb_check(root, *extra):
    """What the career_check tool runs: `check` on `root` (`jsk kb check` until 2026-10-04).

    Args:
        root: the workspace.
        extra: more arguments for it (`--only <stem>`, `--today DATE`, ...).

    Returns:
        (the exit code - 0 clean, 1 a FAIL, 2 called wrong; everything it printed).
    """
    code, out, err = kb_verb(root, "check", *extra)
    return code, out + err


def pack(root, name, *extra):
    """What the career_pack tool runs: `pack NAME` on `root`.

    Args:
        root: the workspace.
        name: the pack, `capabilities`.
        extra: more arguments (`--out FILE`).

    Returns:
        (exit code, stdout - the changeset, or with --out what was written - and stderr, what
        was skipped).
    """
    return kb_verb(root, "pack", name, *extra)


def merge(root, concept, into, *extra):
    """What the career_merge tool runs: `merge CONCEPT --into INTO` on `root`.

    Args:
        root: the workspace.
        concept: the id (or curie) merged away.
        into: the id (or curie) it becomes.
        extra: more arguments (`--out FILE`).

    Returns:
        (exit code, stdout, stderr), as pack.
    """
    return kb_verb(root, "merge", concept, "--into", into, *extra)


def drop(root, app, *extra):
    """What the app_drop tool runs: adapters/entry/drop.main inside `root`.

    Args:
        root: the workspace.
        app: `applications/<stem>`, a path, or the stem alone.
        extra: more arguments (`--reason TEXT`, `--dry-run`, `--today DATE`).

    Returns:
        (exit code - 0 dropped or a dry run, 1 refused, 2 called wrong; everything it printed).
    """
    from jsk.adapters.entry import drop as dropped
    from jsk.adapters.mcp import captured

    return captured.called(root, dropped.main, [app, *extra])


def as_json(output):
    """A `query(..., json=True)` output parsed."""
    return json.loads(output)
