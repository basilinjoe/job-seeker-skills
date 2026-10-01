"""`jsk freeze`: its flags, the application frozen, its gates and what was written said.

Archives one application directory: renames it to its day and writes its record. Never
touches the career or its log. `jsk event` records what happens to the application
afterwards; this command only freezes what was sent. The freeze itself is
application/timeline/freeze.py.
"""
import datetime
import os

from ...cliutil import parse_flags, wants_help

FREEZE_USAGE = ("usage: jsk freeze <app-dir> --submitted YYYY-MM-DD|false "
                "--channel TEXT [--doc FILE ...]")
GRAPH_STORE = os.path.join("career", "store")


def freeze_refusal(*lines):
    """Print a refused freeze: the reason, then each further line indented.

    Args:
        *lines: what the refusal says, the reason first.

    Returns:
        1, the exit code of a refused freeze.
    """
    print("REFUSED - " + lines[0])
    for line in lines[1:]:
        print("  " + line)
    return 1


class Applications:
    """An application's record graphs, as graph.timeline keeps them, looked up at each call.

    A test patches timeline.write_frozen, so the freeze is handed this rather than the
    functions themselves: the patch is then what the freeze writes with.
    """

    def frozen(self, app_dir):
        """What says `app_dir` was frozen, else None (timeline.frozen)."""
        from ...graph import timeline

        return timeline.frozen(app_dir)

    def has_record(self, app_dir, kind):
        """Whether the application holds its `kind` graph (timeline.has_record)."""
        from ...graph import timeline

        return timeline.has_record(app_dir, kind)

    def freeze(self, root, app_dir, plan, short_bytes, submitted, channel, documents):
        """(Sealed, None) or (None, the lines saying why not) (timeline.freeze)."""
        from ...graph import timeline

        return timeline.freeze(root, app_dir, plan, short_bytes, submitted, channel,
                               documents)

    def write_frozen(self, root, sealed, final):
        """Write what freeze() validated; the graph's name (timeline.write_frozen)."""
        from ...graph import timeline

        return timeline.write_frozen(root, sealed, final)


class Gates:
    """jsk.cli's gate plumbing, as application.timeline.freeze.gate runs it.

    Looked up in jsk.cli at each call, so `jsk freeze`, `jsk gates` and `jsk ship` run one
    set of gates and not three copies of it.
    """

    def run(self, app_dir, record, only):
        """Every `jsk gates` result over the documents `only`, the render gate last."""
        from ... import cli

        return cli.gate_results(app_dir, record, only=only)

    def read(self, app_dir, only):
        """The paths of `only` that those gates read."""
        from ... import cli

        extensions = sorted({ext for _, _, exts in cli.DOC_GATES for ext in exts} | {".pdf"})
        return cli.rendered_documents(app_dir, extensions, only)

    def letter(self, path, record, name):
        """The letter gate's result over `path`, against the application's resume.json."""
        from ... import cli
        from ...application.gates.run_gates import step
        from .gates.check import Shown, contained

        return Shown(step("letter gate", f"letter.py {name} --record {cli.DEFAULT_RECORD}",
                          *contained("letter.py", [path, "--record", record])))

    def failed(self, results):
        """Whether any result is not a pass."""
        from ... import cli

        return bool(cli.worst_exit(results))


def called(args):
    """The freeze a call asks for, or the exit code of one that is called wrong.

    Args:
        args: the arguments after `freeze`.

    Returns:
        (app_dir, workspace, submitted, channel, the --doc paths or None), or 0 for --help
        and 2 for a call error, having printed why.
    """
    from ... import cli

    if wants_help(args):
        print(FREEZE_USAGE)
        return 0
    if cli.view_refusal(args):
        print("\n".join(cli.VIEW_GONE))
        return 2
    parsed, problem = parse_flags(args, ("--submitted", "--channel"), (),
                                  repeats=("--doc",))
    if problem:
        print(problem)
        print(FREEZE_USAGE)
        return 2
    positional, flags = parsed
    if len(positional) != 1:
        print(FREEZE_USAGE)
        return 2
    app_dir = positional[0].rstrip("/\\") or positional[0]
    if not os.path.isdir(app_dir):
        print(f"not a directory: {app_dir}")
        print("fix:  pass the application directory - applications/<yyyy-mm-dd>-<company>-<role>/")
        return 2
    # An applications/ that is not beside the knowledge base is one the been-here-before
    # check never looks in, so an application frozen there is invisible to every later
    # round. It happened: a session wrote them relative to its working directory.
    apps = os.path.dirname(os.path.abspath(app_dir))
    workspace = os.path.dirname(apps)
    if not os.path.isdir(os.path.join(workspace, GRAPH_STORE)):
        print(f"no career/store/ beside {apps}")
        print("fix:  move the directory into the applications/ folder next to career/")
        return 2
    submitted = flags.get("--submitted")
    if submitted is None:
        print("--submitted is required")
        print("fix:  --submitted 2026-09-08   - the day it was sent, or `false` for one")
        print("      deliberately held back")
        return 2
    if submitted != "false":
        try:
            if datetime.date.fromisoformat(submitted).isoformat() != submitted:
                raise ValueError(submitted)
        except ValueError:
            print(f"--submitted needs YYYY-MM-DD or false, got {submitted!r}")
            print("fix:  --submitted 2026-09-08")
            return 2
    channel = (flags.get("--channel") or "").strip()
    if not channel:
        print("--channel is required")
        print("fix:  --channel \"Workday portal\"   - where it was sent")
        return 2
    return app_dir, workspace, submitted, channel, flags.get("--doc")


def main(args):
    """`jsk freeze`: archive one application directory, once every gate has passed.

    Args:
        args: the arguments after `freeze`.

    Returns:
        The exit code: 0 frozen, 1 refused, 2 called wrong. Prints the gates' output and
        what was written; renames the directory and writes the store.
    """
    call = called(args)
    if isinstance(call, int):
        return call
    app_dir, workspace, submitted, channel, named = call

    from ... import cli
    from ...application.timeline import freeze as F
    from ...infra import files
    from ...infra.oxigraph import db
    from ...infra.oxigraph import record as R
    from ...resume import build

    try:
        checked = F.check(app_dir, record=Applications(), build=build.from_path)
        planned = F.plan(app_dir, submitted, named, checked, spelled=files.spelled)
    except F.FreezeRefused as refusal:
        return freeze_refusal(*refusal.lines)
    gated = F.gate(planned, Gates())
    cli.print_results(f"gates: {app_dir}", gated.results)
    if gated.refusal:
        return freeze_refusal(*gated.refusal)

    try:
        # The turn before the record is read: what freeze() validates is what it writes over.
        with R.turn(workspace):
            result = F.write(workspace, planned, submitted, channel, record=Applications(),
                             files=files, store_errors=(db.StoreError,))
    except F.FreezeRefused as refusal:
        return freeze_refusal(*refusal.lines)
    except F.FreezeLanded as landed:
        print(f"FAIL  the application's record was written, and then: {landed}")
        print(f"      fix: {landed.fix}")
        return 1
    return froze(result)


def froze(result):
    """Print what a freeze wrote and what it could not check.

    Args:
        result: the FreezeResult.

    Returns:
        0.
    """
    print(f"froze  {result.written}")
    if result.final != result.app_dir:
        print(f"moved  {result.app_dir} -> {result.final}")
    print(result.final)
    print()
    print("Frozen on the mechanical gates. The render gate is a person's: freezing")
    print("assumes somebody opened the PDF and read it. Nothing in this directory is")
    print("edited again; later events are `jsk event <dir> <kind> --date ...`, and")
    print("`jsk kb query pipeline` gives each application's stage.")
    return 0
