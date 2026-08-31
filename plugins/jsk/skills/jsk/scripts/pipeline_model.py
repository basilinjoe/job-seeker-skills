"""What an application timeline means.

Three scripts read this format - `pipeline.py` reports on it, `validate_bundle.py`
checks it, `migrate_bundle.py` writes it - so exactly one of them is allowed to
decide what an event signifies. That is this module. Re-deriving "is this stale"
in each caller is how two of them end up disagreeing about a person's job search.

Standard library only. Nothing here reads a file except `load_rules`, and nothing
here writes one at all. The one frontmatter block it produces comes from the write
layer's emitter rather than an f-string here, because there is one definition of
the format and this file is not it. A hand-formatted block is exactly how this
one's `timestamp` went out bare - a datetime to YAML rather than a string, the
shape okf_compile.py records as having ended a compile in a TypeError.
`authoring.concept` imports only `re`, so the no-dependency claim still holds.
"""
import datetime
import os
import re
import sys

# pipeline_model.py is imported by file path - tests/test_pipeline.py loads it
# standalone - so the scripts directory is not reliably on sys.path by the time
# this runs. The same guard init_bundle.py carries, for the same reason.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from authoring import concept  # noqa: E402

# Ordered, because "the last advancing event" is the stage and the order is what a
# reader expects a pipeline to move through. Membership matters to the code; the
# order matters to anyone reading the vocabulary file.
ADVANCING = [
    "submitted",
    "acknowledged",
    "recruiter-contact",
    "screen-scheduled",
    "screen-done",
    "task-issued",
    "task-submitted",
    "interview-scheduled",
    "interview-done",
    "offer",
]

# An offer is not the end - the answer to it is. Leaving `offer` terminal would close an
# application at the one moment its owner most needs prompting, and would make the two-day
# rule below unreachable.
TERMINAL = ["accepted", "declined", "rejected", "withdrawn", "no-response"]

# Two independent attributes. An event can move the stage, restart the staleness
# clock, both, or neither - and conflating them is the bug that makes a report nag
# about work already done.
CLOCK_RESETTING = set(ADVANCING) | {"follow-up-sent"}
INERT = {"note"}

ALL_EVENTS = set(ADVANCING) | set(TERMINAL) | {"follow-up-sent"} | INERT

# Stages where elapsed time says nothing, because something is booked. The `Due`
# date governs instead.
SCHEDULED = {"screen-scheduled", "interview-scheduled", "task-issued"}

# Days of silence before a stage wants chasing. A bundle's own
# resume-generation/pipeline-rules.md overrides any of these.
DEFAULT_RULES = {
    "submitted": 14,
    "acknowledged": 14,
    "recruiter-contact": 5,
    "screen-done": 7,
    "interview-done": 7,
    "task-submitted": 7,
    "offer": 2,
}

# A scheduled event with no Due date recorded. It should not be silently forgiven -
# the report says the date is missing - but it cannot wait forever either.
NO_DUE_FALLBACK = 14

ACTIONS = {
    "submitted": "chase or close",
    "acknowledged": "chase or close",
    "recruiter-contact": "reply or follow up",
    "screen-done": "follow up",
    "interview-done": "follow up",
    "task-submitted": "follow up",
    "offer": "respond - you owe them",
}

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Row:
    """One timeline row. `date` is None when the source said `unknown`."""

    __slots__ = ("date", "raw_date", "event", "channel", "note", "due", "line")

    def __init__(self, raw_date, event, channel, note, due, line):
        self.raw_date = raw_date
        self.date = parse_date(raw_date)
        self.event = event
        self.channel = channel
        self.note = note
        self.due = parse_date(due)
        self.line = line


class State:
    """What a timeline adds up to, as of a given date."""

    __slots__ = ("stage", "terminal", "last_event", "days_quiet", "due",
                 "needs_action", "action", "urgency", "flags")

    def __init__(self):
        self.stage = None
        self.terminal = None
        self.last_event = None
        self.days_quiet = None
        self.due = None
        self.needs_action = False
        self.action = ""
        self.urgency = ""
        self.flags = []


def parse_date(text):
    """ISO dates only. `unknown` - what a migration writes when it could not
    establish a date - is a legitimate value and parses to None, not an error."""
    if not text:
        return None
    text = text.strip()
    if not ISO.match(text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def parse_timeline(body):
    """Rows from the `# Timeline` table. Returns [] when the section is absent.

    Only the table under a `# Timeline` heading counts. An application file has
    other tables in it - what was sent, the gates - and treating any pipe-delimited
    line as a timeline row would turn a documentation table into pipeline state.
    """
    rows = []
    in_section = False
    for n, line in enumerate(body.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            in_section = stripped.lower().lstrip("# ").startswith("timeline")
            continue
        if not in_section or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set(cells[0]) <= set("-: "):        # the |---| separator
            continue
        if cells[0].lower() == "date":         # the header
            continue
        cells += [""] * (5 - len(cells))
        rows.append(Row(cells[0], cells[1], cells[2], cells[3], cells[4], n))
    return rows


def derive(rows, as_of, rules=None):
    """Reduce a timeline to a state. Never raises on malformed input - reporting a
    bad row is validate_bundle.py's job, and a report that dies on one typo in one
    application is a report nobody can run against a real bundle."""
    rules = dict(DEFAULT_RULES if rules is None else rules)
    state = State()
    if not rows:
        state.flags.append("no timeline")
        return state

    for row in rows:
        if row.event in TERMINAL:
            state.terminal = row.event
        elif row.event in ADVANCING:
            state.stage = row.event
            state.terminal = None          # a reopened process is not closed
        if row.due is not None:
            state.due = row.due
        if row.event in CLOCK_RESETTING and row.date is not None:
            if state.last_event is None or row.date > state.last_event:
                state.last_event = row.date

    if state.terminal:
        return state

    if state.stage is None:
        state.flags.append("no stage - the timeline has no advancing event")
        return state

    if state.last_event is None:
        state.flags.append("no dated event")
        return state

    state.days_quiet = (as_of - state.last_event).days

    if state.stage in SCHEDULED:
        if state.due is None:
            state.flags.append("no date recorded")
            limit = NO_DUE_FALLBACK
            state.needs_action = state.days_quiet >= limit
            state.action = "record what happened, or add the date"
            state.urgency = _urgency(state.days_quiet, limit)
        else:
            overdue = (as_of - state.due).days
            state.needs_action = overdue >= 0
            state.action = ("record what happened" if state.needs_action else "prepare")
            state.urgency = _due_urgency(overdue)
        return state

    limit = rules.get(state.stage, NO_DUE_FALLBACK)
    if state.due is not None:
        # An explicit promise beats the rule in both directions: it can bring an
        # item forward, and it can hold one back that the rule would have chased.
        overdue = (as_of - state.due).days
        state.needs_action = overdue >= 0
        state.urgency = _due_urgency(overdue)
    else:
        state.needs_action = state.days_quiet >= limit
        state.urgency = _urgency(state.days_quiet, limit)
    state.action = ACTIONS.get(state.stage, "follow up")
    return state


def _urgency(days_quiet, limit):
    over = days_quiet - limit
    if over > 0:
        return f"overdue {over}d"
    if over == 0:
        return "due today"
    return f"{days_quiet}d"


def _due_urgency(overdue):
    if overdue > 0:
        return f"overdue {overdue}d"
    if overdue == 0:
        return "due today"
    return f"in {-overdue}d"


RULE_LINE = re.compile(r"^\|\s*`([a-z-]+)`\s*\|\s*(\d+)")


def load_rules(bundle_root, os_module=None):
    """Merge resume-generation/pipeline-rules.md over the defaults, if it exists.

    A bundle's own rules win - the same contract every other rule file here has.
    Rows look like:  | `submitted` | 21 |
    """
    import os
    os_module = os_module or os
    path = os_module.path.join(bundle_root, "resume-generation", "pipeline-rules.md")
    rules = dict(DEFAULT_RULES)
    if not os_module.path.exists(path):
        return rules
    fenced = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            m = RULE_LINE.match(line.strip())
            if m and m.group(1) in set(ADVANCING) | set(TERMINAL):
                rules[m.group(1)] = int(m.group(2))
    return rules


def vocabulary_markdown(timestamp):
    """The seed content for framework/pipeline-vocabulary.md.

    Ships full, unlike capability-vocabulary.md which ships empty and grows with the
    person. The distinction is who owns the list: capabilities describe someone's own
    work and are theirs to extend, while these name a process the scripts reason about.
    Adding a value here without teaching pipeline_model.py what it means gives you a
    row nothing can compute a stage from.

    Both init_bundle.py and migrate_bundle.py write this, so it is generated in one
    place rather than pasted into two.
    """
    def rows(events, advances, resets):
        return "\n".join(f"- `{e}` - {advances}, {resets}" for e in events)

    return concept.frontmatter("Vocabulary", {
        "title": "Pipeline vocabulary",
        "description": "The event values an application timeline may use. "
                       "Exact strings.",
        "timestamp": timestamp,
        "status": "confirmed",
    }) + f"""
The `Event` column of an application's `# Timeline` table. `pipeline.py` derives the stage and the
staleness from these strings, and `validate_bundle.py` rejects anything absent from this file, so a
synonym is not a small mistake - it is a row that stops counting.

Two independent attributes. An event can move the stage, restart the staleness clock, both, or
neither.

# Advancing

The stage is the **last** of these. Each also restarts the clock.

{rows(ADVANCING, "advances the stage", "restarts the clock")}

# Terminal

The application is closed. It stops appearing in the weekly board.

{rows(TERMINAL, "closes the application", "no clock")}

# Contact without progress

- `follow-up-sent` - does not advance the stage, **restarts the clock**

Restarting the clock is the point. Without it, chasing someone on Monday has the report telling you
to chase them again on Tuesday, and a report that nags about work already done is one people stop
opening.

# Neither

- `note` - does not advance the stage, does not restart the clock

Writing something down is not contact.

# The Due column

Optional, on any row: the date the next thing is expected. `"they said they would come back on the
22nd"` goes here rather than into a field somebody has to remember to clear. The latest non-empty
`Due` wins, a later row supersedes an earlier one, and what was promised stays in the history.

An explicit `Due` beats the staleness rule in both directions - it can bring an item forward, and it
can hold back one the rule would have chased.
"""
