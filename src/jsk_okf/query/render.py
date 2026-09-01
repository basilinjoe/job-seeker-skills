"""How every answer here is printed, decided once.

Five commands and fourteen listings each formatting their own output is five chances
for the column truncation to differ, five wordings for "and 40 more", and five shapes
of `--json`. `pipeline.py` formats its board inline and is right to - it is one
command. This is not.

So a query module's whole output contract is: build a `Result`, hand it back. It never
prints, never decides whether `--json` was asked for, and never truncates. That means
a listing can be tested by reading its rows rather than by parsing a table, which is
the other reason this file exists.

Two rules the callers do not get to override:

**`--json` is never truncated.** `--top` is a reading aid, and a parser does not read.
`pipeline.py` settled this one already: "the whole board, unbounded".

**A cut is always visible.** A bounded table prints how many rows it did not show and
what flag shows them. A listing that silently stopped at twenty is a listing somebody
draws a conclusion from.
"""

import json
import sys

# Wide enough for a compiled id (`ach_projects_care_platform_rebuild_md_2` is 41) and
# narrow enough that four columns still fit a terminal. A value longer than its column
# is truncated with a `…` so the cut is visible in the cell as well as in the trailer.
ELLIPSIS = "…"

# What a row from the archive says about itself, written once.
#
# Four commands can surface one and each had grown its own wording. That is worse here
# than the usual duplication argument makes it sound: this sentence is the only thing
# standing between a caller and editing the record of what was already posted, so four
# spellings of it means a person learns it in one answer and does not recognise it in
# the next. `walk.Scope.frozen` decides *which* files this is true of - and note it is
# narrower than "in the archive": an application's own `<stem>.md` is appended to for as
# long as the process is live.
FROZEN = "FROZEN - an archived copy beside a sent application; do not edit it"

# The same fact as a note above a table, where a marker per row would be noise.
FROZEN_NOTE = ("some rows below are frozen copies beside a sent application - they are "
               "the record of what was already posted and may not be edited")

# The default row cap, matching `pipeline.py`'s. A hundred applications is a real
# search and an unreadable board; a hundred bullets is the same problem.
DEFAULT_TOP = 15


class Column:
    __slots__ = ("header", "key", "width")

    def __init__(self, header, key, width=None):
        self.header = header
        self.key = key
        # None means "take what is left and do not truncate" - correct for the last
        # column, which is usually the sentence somebody is reading.
        self.width = width


class Result:
    """What a query answered, before anyone has decided how to show it.

    `columns` renders an aligned table; `block` renders each row as a small stanza,
    for an answer where one row is a location plus the text found there. Exactly one
    of the two.

    `notes` are printed above the answer and are for what the query did *not* look at -
    the archive it skipped, the scope it was narrowed to. A query whose boundaries are
    invisible is one whose empty result reads as "there is nothing there".
    """

    __slots__ = ("rows", "columns", "block", "summary", "notes", "extra")

    def __init__(self, rows, columns=None, block=None, summary=None, notes=(),
                 extra=None):
        if (columns is None) == (block is None):
            raise ValueError("a Result renders as columns or as blocks, not both")
        self.rows = list(rows)
        self.columns = tuple(columns) if columns else None
        self.block = block
        self.summary = summary
        self.notes = list(notes)
        # Anything a command wants in its --json envelope that is not a row: the
        # capability histogram's totals, the census counts.
        self.extra = extra or {}

    def __len__(self):
        return len(self.rows)


def console():
    """Make stdout survive a non-ASCII value on a cp1252 terminal.

    The same two lines `cli.py` and `authoring/commands.py` each carry, for the same
    reason: a path or a title under a non-ASCII name reaches a Windows console as a
    UnicodeEncodeError from inside the print, which loses the whole answer rather than
    one character of it.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass


def cell(value, width):
    """One value as a column of `width`, truncated visibly."""
    if value is None or value == "":
        text = "-"
    elif isinstance(value, (list, tuple)):
        text = ", ".join(str(v) for v in value)
    elif value is True:
        text = "yes"
    elif value is False:
        text = "no"
    else:
        text = str(value)
    text = text.replace("\n", " ").strip()
    if width and len(text) > width:
        return text[:width - 1] + ELLIPSIS
    return text


def widths(result):
    """Each column's printed width: the wider of its header and its widest value.

    Computed over the rows actually shown rather than declared, so a listing of three
    projects does not pad every column to the width a hundred would need.
    """
    out = []
    for column in result.columns:
        seen = [len(column.header)]
        seen += [len(cell(row.get(column.key), column.width)) for row in result.rows]
        want = max(seen)
        out.append(min(want, column.width) if column.width else want)
    return out


def table(result, rows):
    lines = []
    sizes = widths(result)
    last = len(result.columns) - 1
    header = "  ".join(
        column.header.upper().ljust(size) if n != last else column.header.upper()
        for n, (column, size) in enumerate(zip(result.columns, sizes)))
    lines.append("  " + header.rstrip())
    for row in rows:
        printed = "  ".join(
            cell(row.get(column.key), column.width).ljust(size)
            if n != last else cell(row.get(column.key), column.width)
            for n, (column, size) in enumerate(zip(result.columns, sizes)))
        lines.append("  " + printed.rstrip())
    return lines


def emit(result, command, bundle, top=None, as_json=False, more_flag=None):
    """Print one answer. Returns 0, always - see `query/__init__.py`."""
    if as_json:
        # `default=str` for the same reason `pipeline.py` carries it: an unquoted
        # `timestamp: 2026-08-30` in somebody's frontmatter is a date to YAML and
        # nothing at all to json, and a query is not the place that discovery should
        # end a run.
        print(json.dumps({"command": command, "bundle": str(bundle),
                          "count": len(result.rows), "rows": result.rows,
                          **result.extra}, indent=2, default=str, ensure_ascii=False))
        return 0

    console()
    for note in result.notes:
        print(note)
    if result.notes:
        print()

    shown = result.rows if not top or top <= 0 else result.rows[:top]
    if not result.rows:
        print(result.summary or "nothing matched")
        return 0

    if result.block:
        for n, row in enumerate(shown):
            if n:
                print()
            for line in result.block(row):
                print(line)
    else:
        for line in table(result, shown):
            print(line)

    hidden = len(result.rows) - len(shown)
    if hidden:
        flag = more_flag or f"--top {len(result.rows)}"
        print(f"\n  ... and {hidden} more - {flag} for the rest")
    if result.summary:
        print(f"\n{result.summary}")
    return 0
