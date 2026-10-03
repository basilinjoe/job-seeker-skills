"""The MCP tools for the person's acts: app_freeze, app_event and letter_check.

Ruling 21 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md kept a
freeze, an event and the letter check on the CLI; its amendment of 2026-10-03 made them
tools, so the main session needs no shell for a jsk job. No agent's `tools:` names them
(tests/test_agent_grants.py): freezing and recording an event are the person's acts.

Each tool calls what its command calls - compose/timeline.py's freeze_app and add_event,
and the letter gate's own adapter - so a freeze or an event made either way is the same
write, and like their commands they take an application made from files as well as a
graph-native one. A call error the command would exit 2 on (a bad date, an unknown kind) is
a FAIL with its fix here. They live apart from server.py, which registers them, only to keep
each module under tests/test_sizes.py's limit.
"""
import contextlib
import io
import os

from .server import described, failed, plain, result


def app_dir_of(root, app):
    """(the application directory `app` names in the workspace, None), or (None, the FAIL
    saying why there is none).

    Args:
        root: the workspace root.
        app: `<stem>` or `applications/<stem>`.
    """
    name = (app or "").replace("\\", "/").strip().strip("/").removeprefix("applications/")
    path = os.path.join(root, "applications", name)
    if not name or "/" in name or not os.path.isdir(path):
        return None, ("FAIL", f"no application directory applications/{name or '?'}",
                      "pass the stem app_list names; a graph-native application gets its "
                      "directory from resume_ship")
    return path, None


def submitted_problem(submitted):
    """The FAIL for a `submitted` that is neither YYYY-MM-DD nor "false", else None: the
    check `jsk app freeze --submitted` makes."""
    from ...domain.timeline.events import is_date

    if submitted == "false" or is_date(submitted):
        return None
    return ("FAIL", f"submitted needs YYYY-MM-DD or false, got {submitted!r}",
            "the day it was sent, e.g. 2026-09-08, or false for one deliberately held back")


def gate_findings(steps):
    """A FAIL for each gate step that did not pass, as resume_ship reports them."""
    return [("FAIL", f"{s['gate']}: {s['status']}", "its output is in steps")
            for s in steps if s["status"] in ("FAIL", "ERROR", "SKIPPED")]


def gate_line(severity, text):
    """(severity, detail, fix or None) of one finding as domain.gates.report.line words it:
    the detail, then its fix on an indented line of its own."""
    detail, _, fix = text.partition("\n        fix: ")
    return severity, detail, fix or None


def said(output):
    """(the first thing `output` says is wrong, its fix or None): a gate's call error or
    stop, as its adapter printed it."""
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    text = next((ln for ln in lines if ln.startswith("FAIL")), lines[0] if lines else output)
    fix = next((ln for ln in lines if ln.startswith("fix:")), None)
    return text.removeprefix("FAIL").strip(), fix


def freezes(srv, tools):
    """app_freeze: `jsk app freeze`, its gates' steps and what it wrote as JSON."""
    from ..cli.compose import timeline as T

    @described(srv)("`jsk app freeze`: gate, record and rename a shipped application. "
                    "submitted: YYYY-MM-DD or false.")
    def app_freeze(app: str, submitted: str, channel: str,
                   docs: list[str] | None = None) -> dict:
        def run(root, today):
            from ...application.timeline import freeze as F

            app_dir, missing = app_dir_of(root, app)
            bad = missing or submitted_problem(submitted) or (
                None if channel.strip() else
                ("FAIL", "channel is required", "where it was sent, e.g. \"Workday portal\""))
            if bad:
                return failed(bad)
            steps = []
            nothing = dict(written=None, renamed_to=None, recordSha256=None, carried=[],
                           documents=[])
            try:
                done = T.freeze_app(app_dir, root, submitted, channel.strip(), docs or None,
                                    gated=steps.extend)
            except F.FreezeRefused as refusal:
                return result(gate_findings(steps) + [
                    ("FAIL", refusal.lines[0], " ".join(refusal.lines[1:]) or None)],
                    **nothing, steps=plain(steps))
            except F.FreezeLanded as landed:
                return result([("FAIL", f"the application's record was written, and then: "
                                        f"{landed}", landed.fix)], **nothing,
                              steps=plain(steps))
            moved = done.final != done.app_dir
            return result(written=done.written,
                          renamed_to=("applications/" + os.path.basename(done.final)
                                      if moved else None),
                          **T.frozen_record(root, done.written), steps=plain(steps))
        return tools.call("app_freeze", run, writes=True)


def events(srv, tools):
    """app_event: `jsk app event`, the event it added as JSON."""
    from ..cli.compose import timeline as T

    @described(srv)("`jsk app event`: one event on a frozen application. date: YYYY-MM-DD "
                    "or unknown.")
    def app_event(app: str, kind: str, date: str, channel: str | None = None,
                  due: str | None = None, note: str | None = None) -> dict:
        def run(root, today):
            import difflib

            from ...application.timeline.add_event import EventLanded, EventRefused
            from ...domain import ontology as O
            from ...domain.timeline.events import is_date, when

            kinds = O.ENUMS["eventKind"]
            app_dir, missing = app_dir_of(root, app)
            if app_dir is None:
                return failed(missing)
            if kind not in kinds:
                near = difflib.get_close_matches(kind, kinds, n=1, cutoff=0.5)
                return failed(("FAIL", f"unknown kind: {kind!r}",
                               (f"did you mean {near[0]!r}? " if near else "")
                               + f"one of {', '.join(kinds)}"))
            if date != "unknown" and not is_date(date):
                return failed(("FAIL", f"date needs YYYY-MM-DD or unknown, got {date!r}",
                               "the day it happened"))
            if due is not None and not is_date(due):
                return failed(("FAIL", f"due needs YYYY-MM-DD, got {due!r}",
                               "the day the scheduled meeting is"))
            if not T.has_record(app_dir, "application"):
                return failed(("FAIL", f"applications/{os.path.basename(app_dir)} holds no "
                                       "application record",
                               "an application gets one when it is frozen: app_freeze"))
            try:
                done = T.add_event(root, app_dir, kind, date, channel, note, due, today)
            except EventRefused as e:
                return failed(*[("FAIL", line, e.fix) for line in e.lines])
            except EventLanded as e:
                return failed(("FAIL", f"the event was written, and then: {e}", e.fix))
            # A date after today is arithmetic gone wrong, as `jsk app event` warns.
            ahead = [("WARN", f"{done.date} is after today, and the date is the day it "
                              "happened", "a meeting still to come is the due of its "
                                      "-scheduled event; correct this one with a note event")
                     ] if done.ahead else []
            return result(ahead, event={"id": done.iri, "kind": done.kind, "date": done.date,
                                        "due": done.due, "channel": channel, "note": note},
                          recorded=when(done.date, today),
                          due=when(done.due, today) if done.due else None)
        return tools.call("app_event", run, writes=True)


def letters(srv, tools):
    """letter_check: `jsk letter check`, its verdict line and findings as JSON."""

    @described(srv)("`jsk letter check`: a cover letter against its resume. record: a stem "
                    "or a resume.json.")
    def letter_check(letter: str, record: str) -> dict:
        def run(root, today):
            from ...application.gates.letter import LetterResult
            from ..cli.compose.selection import ref_for
            from ..cli.gates import letter as gate

            path = letter if os.path.isabs(letter) else os.path.join(root, letter)
            # A stem reads as the target's ref, which the gate takes as it is; a file is
            # found in the workspace, not the server's working directory.
            against = ref_for(record, dirs=True, root=root) or (
                record if os.path.isabs(record) else os.path.join(root, record))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code, checked = gate.gate([path, "--record", against])
            output = buf.getvalue()
            if not isinstance(checked, LetterResult):
                return result([("FAIL", *said(output))], verdict=None, output=output)
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
            found = [gate_line(severity, f) for severity, group
                     in (("FAIL", checked.fails), ("WARN", checked.warns)) for f in group]
            return result(found, verdict=lines[-1] if lines else None, exit=code,
                          output=output)
        return tools.call("letter_check", run)
