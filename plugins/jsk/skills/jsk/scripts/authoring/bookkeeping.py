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
"""

import os
import re


def _read(path):
    """One file's text with LF endings, and the convention it actually arrived in.

    `newline=""` rather than text mode, for exactly the reason concept.read()
    carries the same argument: universal newlines hands back "\\n" for a CRLF
    file, and these functions return the file's *whole* new text - so returning
    LF for a CRLF index would rewrite every line ending in it in order to add one
    line. A bundle scaffolded on Windows is entirely CRLF, so that is the common
    case and not the exotic one.

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
    entry = f"- [{title}]({filename})"
    if description:
        entry += f" - {description}"
    return _restore(_newline_terminated(text) + entry + "\n", newline)


HEADING = "## %s"

# The heading line, and everything under it up to the next heading or the end.
#
# One expression locates the heading AND the end of its block, because two
# mechanisms disagreeing is how this goes wrong: a substring test for the heading
# paired with a regex that also required a newline immediately after it meant a
# heading somebody had annotated - `## 2026-08-31 - applied to Acme` - passed the
# test, matched no regex, and reached .end() on None as an AttributeError.
# `[^\n]*` on the first line is what admits the annotated form.
#
# `\n*` inside the lookahead rather than the body: the blank line before the next
# heading belongs to that heading, so the block ends above it and a new row lands
# under the last row of its own day instead of in the gap below it.
def _block_end(text, heading):
    match = re.search(
        r"^" + re.escape(heading) + r"[^\n]*\n(?:[^\n]*\n)*?(?=\n*##\s|\Z)",
        text, re.M)
    return None if match is None else match.end()


def log_entry(path, message, today):
    """`log.md` with one line appended under today's `## <date>` heading.

    The heading is reused where it exists, so a day's work reads as a day's work
    rather than as one entry per command - a braindump, a metric and a ship on
    one afternoon are three rows under one date, which is what a person scanning
    the log is looking for.

    Newest last, matching bundle-spec.md's "chronological history, newest
    appended". A heading for a later date already in the file therefore stays
    below today's - the file is ordered by when it was written, not sorted by
    date, and this module does not reorder what it did not write.
    """
    text, newline = _read(path)
    text = _newline_terminated(text)
    heading = HEADING % today
    row = f"- {message}"
    end = _block_end(text, heading)
    if end is None:
        # A blank line before the heading, and none invented above it when the
        # file is empty - an opening blank line is a byte nobody asked for.
        gap = "\n" if text else ""
        return _restore(f"{text}{gap}{heading}\n\n{row}\n", newline)
    # rstrip on the block's own text only: what follows `end` is the next day's
    # heading and its blank line, and both are somebody else's. Bound rather than
    # inlined into the f-string: a backslash inside an f-string expression is a
    # SyntaxError before 3.12, and these scripts are documented as running on a
    # bare Python of whatever vintage the machine has.
    block = text[:end].rstrip("\n")
    return _restore(f"{block}\n{row}\n{text[end:]}", newline)


def index_path(bundle, directory):
    """The index.md a concept in `directory` belongs to.

    Here rather than at each call site, because bundle-spec.md makes `index.md`
    one of the two reserved filenames and a command that spelt it itself would be
    the second definition of that rule.
    """
    return os.path.join(str(bundle), directory, "index.md")
