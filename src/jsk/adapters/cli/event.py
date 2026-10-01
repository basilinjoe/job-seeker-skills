"""An application's record: what `jsk app freeze` writes, and `jsk app event` adds to.

Usage: jsk app event <app-dir> <kind> --date YYYY-MM-DD|unknown [--channel TEXT] [--note TEXT]
                 [--due YYYY-MM-DD] [--today YYYY-MM-DD]

  <kind>   one of the pipeline vocabulary: submitted, acknowledged, screen-scheduled,
           screen-done, interview-scheduled, interview-done, onsite-scheduled, onsite-done,
           offer, offer-accepted, rejected, withdrawn, no-response, offer-declined,
           follow-up-sent, note, referral, recruiter-contact

Adds one event, k:evt_<stem>_<date>_<kind>, to the application's record (the graph
applications/<dir>/application) - never edits one, never removes one. A second of the
same kind on the same day - another note, a second interview round - is
k:evt_..._<kind>_2, then _3; only an event identical to one already there (kind, date,
channel, note and due) is refused. The whole workspace is validated with the event in it
before anything is written. The application is not logged in the career's log: the log
is the career's, and an application is not the career.

A stage is not stored anywhere: `jsk kb query pipeline` derives it from the latest event.

The date is the day it happened - a screen-scheduled event's is the day it was booked,
the screen itself its --due. Both are printed back with their weekday and distance from
today (--today, for a test), so "last Tuesday" worked out wrong shows as the wrong
weekday; a --date after today is a WARN, since nothing has happened yet on it.

Exit 0 added; 1 refused, with why; 2 called wrong.

`jsk app event` is this module's main; the event is added by application/timeline/add_event.py.
"""
import datetime
import difflib
import os
import sys

from ...domain import ontology as O
from ...domain.timeline.events import is_date, when

KINDS = O.ENUMS["eventKind"]


def usage(message):
    """Print a call error and the usage line.

    Args:
        message: what was wrong with the call.

    Returns:
        2, the exit code of a call made wrong.
    """
    print(message)
    print("usage: jsk app event <app-dir> <kind> --date YYYY-MM-DD|unknown [--channel TEXT] "
          "[--note TEXT] [--due YYYY-MM-DD] [--today YYYY-MM-DD]")
    return 2


def refuse(lines, fix):
    """Print a refused event: each reason, the fix, and that nothing was written.

    Args:
        lines: why, one line each.
        fix: what to do about it.

    Returns:
        1, the exit code of a refusal.
    """
    for line in lines:
        print(f"REFUSED  {line}")
    print(f"        fix: {fix}")
    print("nothing was written")
    return 1


def main(argv=None):
    """`jsk app event`: add one event to a frozen application's record.

    Args:
        argv: the arguments after `event`; sys.argv's when None.

    Returns:
        The exit code: 0 added, 1 refused, 2 called wrong. Reads the clock once, for
        --today's default; writes the application graph.
    """
    from ...cliutil import parse_flags, wants_help
    from ...infra.files import workspace_of_app
    from .compose import timeline

    args = list(sys.argv[1:] if argv is None else argv)
    if wants_help(args):
        # __doc__ is None only under -OO, which nothing runs jsk with.
        print(__doc__.split("\n\nAdds", 1)[0])  # pyright: ignore[reportOptionalMemberAccess]
        return 0
    parsed, problem = parse_flags(args, ("--date", "--channel", "--note", "--due", "--today"), ())
    if parsed is None:
        return usage(problem)
    positional, flags = parsed
    if len(positional) != 2:
        return usage("jsk app event takes an application directory and a kind")
    app_dir, kind = positional[0].rstrip("/\\") or positional[0], positional[1]
    if kind not in KINDS:
        near = difflib.get_close_matches(kind, KINDS, n=1, cutoff=0.5)
        return usage(f"unknown kind: {kind!r} - " + (f"did you mean {near[0]!r}? " if near else "")
                     + f"one of {', '.join(KINDS)}")
    date = flags.get("--date")
    if date is None:
        return usage("--date is required: the day it happened, or `unknown`")
    if date != "unknown" and not is_date(date):
        return usage(f"--date needs YYYY-MM-DD or unknown, got {date!r}")
    due = flags.get("--due")
    if due is not None and not is_date(due):
        return usage(f"--due needs YYYY-MM-DD, got {due!r}")
    today = flags.get("--today", datetime.date.today().isoformat())
    if not is_date(today):
        return usage(f"--today needs YYYY-MM-DD, got {today!r}")
    if not os.path.isdir(app_dir):
        return usage(f"not a directory: {app_dir}")
    if workspace_of_app(app_dir)[0] is None:
        # An application's graph is named applications/<dir>/application, so an event
        # written anywhere else would be one no query ever reads.
        return usage(f"{app_dir} is not in an applications/ folder - pass "
                     "applications/<dir>, beside career/")
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk app event needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    if not timeline.has_record(app_dir, "application"):
        if os.path.isfile(os.path.join(app_dir, "application.md")):
            return refuse([f"{app_dir} was frozen as application.md, which this command does "
                           f"not write"], "append the row to its # Timeline table by hand")
        return refuse([f"{app_dir} holds no application record"],
                      "an application gets one when it is frozen: `jsk app freeze`")
    return add(workspace_of_app(app_dir)[0], app_dir, kind, date,
               flags.get("--channel"), flags.get("--note"), due,
               datetime.date.fromisoformat(today))


def add(root, app_dir, kind, date, channel, note, due, today):
    """Add the event inside this process's turn, and say what was added.

    Args:
        root: the workspace root.
        app_dir: the application directory.
        kind, date, channel, note, due: the event, as the flags gave it.
        today: the date the command runs on.

    Returns:
        The exit code: 0 added, 1 refused or failed after the write.
    """
    from ...application.timeline.add_event import EventLanded, EventRefused, add_event
    from ...domain.timeline import events
    from ...graph import store as S
    from ...infra.files import file_name
    from ...infra.oxigraph import record as R

    try:
        with R.turn(root):
            result = add_event(root, app_dir, kind, date, channel, note, due, today,
                               load=S.load, name_of=file_name,
                               event_quads=events.event_quads, write_graphs=R.write_graphs)
    except EventRefused as e:
        return refuse(e.lines, e.fix)
    except EventLanded as e:
        # The event is in the store: not "nothing was written".
        print(f"FAIL     {e}")
        print(f"        fix: {e.fix}")
        return 1
    return added(result)


def added(result):
    """Print the diff of the event added, and its dates against today.

    Args:
        result: the application.timeline.add_event.EventResult.

    Returns:
        0.
    """
    print(result.diff, end="")
    print(f"added    {result.iri}")
    print(f"recorded {result.kind} on {when(result.date, result.today)}")
    if result.due:
        print(f"due {when(result.due, result.today)}")
    if result.ahead:
        print(f"WARN  {result.date} is after today, and the date is the day it happened - "
              "a meeting still to come is the --due of its -scheduled event; an event is "
              "never edited, so correct this one with a `note` event")
    return 0
