"""The companions a concept write implies, derived rather than remembered.

references/mode-braindump.md instructs five files in one sentence - "update
`projects/index.md`, link from the relevant role concept, add numbers to
`achievements/metrics.md`, append to `log.md`, run the validator" - and nothing
makes them atomic. Two of the five are mechanical and computable from what the
command already knows: the directory's index entry, and the `log.md` row. They
are derived here and staged alongside the concept rather than left to be
remembered.

Every function returns the whole new text of one file. Nothing here writes;
stage.py does that, because a function that both decides and writes cannot be
dry-run - and a dry run that skips the derivation is not a dry run of the
command, it is a dry run of half of it.

Standard library only, and no yaml: these files are read as text and appended to
as text. The frontmatter is passed through untouched, so nothing here needs to
understand it.

Written against what init_bundle.py actually scaffolds, which is not what a
person would guess: a directory index is one sentence of prose with no `# Contents`
heading, and log.md opens with `# <date> - Bundle created` - a level-one heading
with a suffix, not the `## <date>` this module writes. Both shapes are handled
below and each is commented where it is handled.

Known limits, measured rather than assumed, and left alone deliberately:

* An entry whose link carries a title attribute - `[Old](a.md "T")` - is not
  recognised as present, so the concept gains a second row. Nothing generates
  that shape; it would have to be typed.
* An empty index.md gains the entry and no frontmatter, and an index.md with
  frontmatter and no body gets the entry under a blank line. Both are already
  outside what the scaffolder produces.
"""

import os
import re

from . import stage


def _read(path):
    """One file's text with LF endings, and the convention it actually arrived in.

    `newline=""` rather than text mode, for exactly the reason concept.read()
    carries the same argument: universal newlines hands back "\\n" for a CRLF
    file, and these functions return the file's *whole* new text - so returning
    LF for a CRLF index would rewrite every line ending in it in order to add one
    line. init_bundle.py scaffolds through plain text mode, so on Windows every
    file in a fresh bundle is CRLF: this is the common case, not the exotic one.

    CRLF wins if it appears at all, matching concept.parse()'s decision on a
    mixed file: every option rewrites something in a file that is already
    inconsistent, and this one at least leaves it consistent afterwards.
    """
    with open(str(path), encoding="utf-8", newline="") as handle:
        raw = handle.read()
    newline = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), newline


def _restore(text, newline):
    """The text back in the file's own convention.

    Every return path goes through this, including the ones that changed nothing.
    A no-op that hands back LF is not a no-op once stage.py writes it.
    """
    return text if newline == "\n" else text.replace("\n", newline)


def _newline_terminated(text):
    """The text with a final newline, so an append starts on a line of its own.

    A file whose last line has no trailing newline is the ordinary result of a
    hand edit, and appending straight onto it glued the new entry to the end of
    somebody's last sentence. The added byte is the one change to an existing
    line this module makes, and it makes it deliberately.
    """
    return text if not text or text.endswith("\n") else text + "\n"


def _one_line(value):
    """Runs of whitespace collapsed to single spaces.

    A newline in a description or a log message split the entry across two lines,
    the second of them loose prose sitting outside the list. concept.scalar
    escapes newlines for exactly this reason; the difference is that a markdown
    line has no escape for one, so the only repair available is to not have one.
    """
    return re.sub(r"\s+", " ", str(value)).strip()


# Characters that end a markdown link destination early, or that validate_bundle.py's
# LINK regex - `\[([^\]]+)\]\(([^)]+)\)` - reads as the end of one: `care(old).md`
# reaches the gate as the target `care(old`, so it reports a broken link to a file
# sitting right beside the index. A space needs <> or %20 to survive CommonMark at all.
#
# Refused rather than escaped. A concept filename that cannot be written as a plain
# link is a filename the command should not have accepted, and escaping it here would
# bury that decision inside an index entry where nobody would find it again.
UNLINKABLE = {" ": "a space", "(": "an opening parenthesis",
              ")": "a closing parenthesis", "<": "an opening angle bracket",
              ">": "a closing angle bracket"}


def _refuse_unlinkable(filename):
    """Say no, naming the character, before it reaches somebody's index."""
    for char in filename:
        name = UNLINKABLE.get(char) or ("whitespace" if char.isspace() else None)
        if name:
            raise stage.Refused(
                f"{filename}: cannot be listed as a markdown link - it contains "
                f"{name} ({char!r})\n"
                f"fix:  name the concept file without it - a stem is lowercase "
                f"words joined by hyphens. A link this layer cannot write plainly "
                f"is one a renderer and validate_bundle.py will each read "
                f"differently from how it was meant.")


# The whole body init_bundle.py writes into every directory index. It is a placeholder
# for the list that replaces it, so leaving it above real entries makes the file assert
# something false about itself. Matched as an exact line, so a body somebody has written
# around it survives untouched: this module lists a concept, it is not a general-purpose
# index rewriter.
PLACEHOLDER = "Empty. Add concepts here."

LIST_ITEM = re.compile(r"^\s*[-*+]\s")


def index_entry(path, filename, title, description):
    """`index.md` with this concept listed, appended and never duplicated.

    Appended rather than sorted, and that is a decision rather than an
    expedient: these files are hand-maintained, some are deliberately ordered by
    importance rather than alphabetically, and a command that reorders somebody's
    index has changed something nobody asked it to. The diff of an append is one
    line; the diff of a sort is the whole file, and it is unreviewable.

    Presence is tested on the link target rather than on the whole entry, because
    the entry is what a person edits - retitling a row or rewriting its
    description must not make the concept look absent and earn it a second row.
    The cost of that choice is that a row already present is left exactly as
    written, title and all. Rewriting it would be this module deciding it knows
    better than the author about a line the author wrote, which is the same
    judgement the append-don't-sort rule already refuses to make.
    """
    text, newline = _read(path)
    if f"({filename})" in text:
        return _restore(text, newline)
    _refuse_unlinkable(filename)
    entry = f"- [{_one_line(title)}]({filename})"
    description = _one_line(description) if description else ""
    if description:
        entry += f" - {description}"
    lines = [line for line in _newline_terminated(text).split("\n")
             if line.strip() != PLACEHOLDER]
    body = "\n".join(lines)
    # A blank line between whatever the body says and the list. Without it the entry
    # renders as a list only by CommonMark's leave to interrupt a paragraph, and reads
    # as a mistake in the source either way. Not added when the body already ends in a
    # blank line, and not added when the row is joining a list that is already there.
    if not body or body.endswith("\n\n"):
        gap = ""
    else:
        gap = "" if LIST_ITEM.match(body.rstrip("\n").rsplit("\n", 1)[-1]) else "\n"
    return _restore(body + gap + entry + "\n", newline)


HEADING = "## %s"
FENCE = "```"


def _day_heading(today):
    """`#` or `##`, the date, and whatever the author wrote after it.

    Either level counts. init_bundle.py opens log.md with
    `# 2026-08-31 - Bundle created`, so recognising only `##` meant a bundle
    logged into on the day it was scaffolded gained a second heading for the same
    date one paragraph below the first - the scaffolder and this module
    disagreeing about what a day looks like, in the person's own file. Only a day
    with no heading at either level gets a new one, and a new one is always `##`.
    """
    return re.compile(r"^#{1,2}[ \t]+" + re.escape(today) + r"([ \t].*)?$")


# Any `#` or `##` heading ends the day above it. `###` and below do not: a subheading
# a person writes under a day's entries belongs to that day, and breaking there would
# put the new row above their own structure.
DAY_BOUNDARY = re.compile(r"^#{1,2}[ \t]")


def _scan(lines):
    """Every line, with whether it sits inside a ``` fence.

    The toggle validate_bundle.py uses twice - at :163-169 and :405-410 - and that
    pipeline_model.py:263-269 repeats. Borrowed rather than reinvented, because a
    fourth idiom for one rule is how three of them come to disagree.

    A log is the file in the bundle most exposed to this: mode-pipeline.md tells
    people to record mistakes rather than hide them, so a log quoting an earlier
    log, or showing the format a day's entries take, is ordinary rather than
    exotic. Without the toggle a `## <date>` inside such a block was matched, and
    the new row landed under the closing fence - above the real sections, with the
    genuine heading never created. Silently, in a file whose whole job is to be a
    truthful record.

    The fence delimiters report as fenced themselves, so a heading can never be
    the line that opens or closes one.
    """
    fenced = False
    for index, line in enumerate(lines):
        opener = line.lstrip().startswith(FENCE)
        yield index, line, fenced or opener
        if opener:
            fenced = not fenced


def log_entry(path, message, today):
    """`log.md` with one line appended under today's `## <date>` heading.

    The heading is reused where it exists, so a day's work reads as a day's work
    rather than as one entry per command - a braindump, a metric and a ship on
    one afternoon are three rows under one date, which is what a person scanning
    the log is looking for.

    Newest last, matching bundle-spec.md's "chronological history, newest
    appended". A heading for a *later* date already in the file therefore keeps
    its place and today's new heading goes below it: the file is ordered by when
    it was written, not sorted by date, and re-sorting somebody's log is a larger
    liberty than leaving it as they left it. For the same reason a date heading
    written twice is answered at the last one rather than the first.
    """
    text, newline = _read(path)
    text = _newline_terminated(text)
    row = "- " + _one_line(message)
    lines = text.split("\n")
    marks = list(_scan(lines))

    day = _day_heading(today)
    heading = None
    for index, line, fenced in marks:
        if not fenced and day.match(line):
            heading = index

    if heading is None:
        # No opening blank line invented above the heading when the file is empty.
        gap = "\n" if text else ""
        return _restore(f"{text}{gap}{HEADING % today}\n\n{row}\n", newline)

    # The last line carrying content under this heading. Fenced lines count as
    # content - a code sample is part of the day - they just cannot be headings.
    last = heading
    for index, line, fenced in marks[heading + 1:]:
        if not fenced and DAY_BOUNDARY.match(line):
            break
        if line.strip():
            last = index
    # Same blank-line rule as the index, and it covers the heading with nothing
    # under it: that used to get the row on the very next line, where the branch
    # that creates a heading writes a blank one first.
    joining = last != heading and LIST_ITEM.match(lines[last])
    lines[last + 1:last + 1] = [row] if joining else ["", row]
    return _restore("\n".join(lines), newline)


def index_path(bundle, directory):
    """The index.md a concept in `directory` belongs to.

    Here rather than at each call site, because bundle-spec.md makes `index.md`
    one of the two reserved filenames and a command that spelt it itself would be
    the second definition of that rule.
    """
    return os.path.join(str(bundle), directory, "index.md")
