"""Every file one command touches, written together and published in one order.

A command rarely changes one file. Adding a project writes the concept, its
directory index, and a line in log.md; three separate writes, and the second one
failing used to leave a bundle nobody had asked for.

This is not a transaction, and saying so plainly is the point. `os.replace` is
atomic for one file and there is no primitive that makes it atomic across
several: a crash between two replaces publishes the first and not the second.
What is guaranteed is narrower and still worth having - every file is written
and fsynced to a temp file beside its target *before* any of them is published,
so a failing write, a full disk or a missing directory all land before anything
is visible, and the bundle is exactly as it was.

What remains is the crash between two replaces, and the mitigation for that is
ORDER, not locking. The concept publishes first and its derived companions
after, because **the concept is the half that cannot be regenerated**. An index
entry is derivable from the tree; a concept is somebody's work. So a partial
publish must lose the derivable half and never the authored half. The reverse
order throws away the record and keeps a line naming a file that never landed.

The price of that choice is that the gap it leaves is silent, and this was
measured rather than assumed. Over a real scaffolded bundle, a concept absent
from its index is clean - validate_bundle.py exits 0 with no finding of any kind
- because it checks that an index.md exists and that its markdown links resolve,
and never that an index lists every concept sitting beside it. The reverse state
fails: `x projects/index.md: BROKEN LINK -> care-platform.md`. So this order
trades a loud, unfixable failure for a quiet, fixable one. That nothing reports
the quiet one is an argument for a reindex command existing, not against the
order.

Known residue, with an owner so it is not rediscovered: a hard crash - a killed
process, a power loss - between the write and the publish leaves a
`<name>.md.okf-tmp` file in the bundle. Every failure this module can see cleans
up after itself, so that is the only remaining source. It is invisible to
validate_bundle.py and okf_compile.py, both of which filter on a `.md` suffix
that the trailing `.okf-tmp` defeats, so it breaks nothing and reports nothing.
Sweeping it belongs to whichever command owns the bundle, not here: this module
only knows about the files of one changeset, and cannot tell its own leftovers
from those of a run still in progress.

Writes go out with `newline=""`, which turns off translation, because
concept.Concept.text() has already put the file's own line convention back. A
text-mode write here would translate a second time and rewrite every line ending
in a CRLF concept in order to change one key - which is exactly the defect
concept.read() carries its own `newline=""` to avoid.
"""

import os

# Lower publishes first. The names are the vocabulary a command uses when it
# stages a file, so the ordering rule is stated once, here, rather than being
# re-derived at each call site by whoever is writing the next command. `log` is
# last because it is the most derived thing in the bundle: a missing log line is
# a record of a change, not the change.
ORDER = {"concept": 0, "companion": 1, "log": 2}

# Beside the target, not in tempfile.gettempdir(): os.replace is only atomic
# within one filesystem, and a bundle on another drive would silently degrade
# into a copy that can tear.
#
# Fixed rather than per-process, which is a decision and not an oversight. Two
# commits running at once against one path would share this name and the last
# writer would win. That is accepted: this is a single-user CLI an agent drives
# one command at a time, and a `.okf-tmp.<pid>` suffix would buy isolation
# nobody needs at the cost of making the leftover of a hard crash unrecognisable
# to whatever eventually sweeps it.
SUFFIX = ".okf-tmp"


class Refused(Exception):
    """This command declined to change the bundle, and says why.

    Ends in a `fix:` line, matching concept.Unsplicable. A refusal a person
    cannot act on is only marginally better than a half-written bundle, and this
    is usually raised when the bundle is *un*touched - so the message is the
    whole of what they get.
    """


class Changeset:
    """Every file a command means to write, and the ids it wants to report back.

    Collected rather than written as they are decided, because a command cannot
    know its second write will succeed until it has tried it, and by then its
    first one is already on disk.
    """

    def __init__(self):
        self._writes = []      # (path, text, kind), in the order staged
        self.ids = {}

    def write(self, path, text, kind="companion"):
        """Stage one file's whole new text under one of ORDER's kinds."""
        if kind not in ORDER:
            # Named rather than defaulted: a typo'd kind silently sorted into
            # some arbitrary position is the ordering guarantee quietly going
            # away, which is the one thing this module exists to provide.
            raise Refused(
                f"{path}: staged as `{kind!r}`, which is not a kind of file\n"
                f"fix:  one of {', '.join(sorted(ORDER))} - the kind is what "
                f"decides which file publishes first")
        if not isinstance(text, str):
            # bytes reached open(newline="") in text mode as a TypeError from
            # inside the write loop, after other temp files had already been
            # written. Refused here, where nothing has been staged to disk yet.
            raise Refused(
                f"{path}: staged {type(text).__name__}, not text\n"
                f"fix:  pass the file's whole new text as a str - concept.text() "
                f"returns one")
        path = str(path)
        if any(path == staged for staged, _, _ in self._writes):
            # Both entries derive one temp name from SUFFIX, so the first
            # replace consumed the temp and the second raised FileNotFoundError
            # halfway through publishing - a caller's bug arriving as an
            # incoherent failure with the bundle already part-written. Refused
            # at staging time, before anything touches disk: a command that
            # stages one path twice holds two opinions about a file's contents,
            # and nothing here can know which one it meant.
            raise Refused(
                f"{path}: staged twice in one change\n"
                f"fix:  stage each file once, with its whole final text - this "
                f"command cannot know which of the two versions was meant")
        self._writes.append((path, text, kind))

    def record_id(self, name, value):
        """One id for the --json payload an agent reads back after the command."""
        self.ids[name] = value

    def ordered(self):
        """Every staged path, in publish order.

        Stable within a kind: two companions publish in the order they were
        staged, because nothing here knows enough to prefer one over the other
        and a sort that reordered them would only make the result harder to
        predict.
        """
        return [path for path, _, _ in self._ordered()]

    def _ordered(self):
        return sorted(self._writes, key=lambda item: ORDER[item[2]])


def commit(changeset, dry_run=False):
    """Write every file, then publish them in order. The payload --json prints.

    On any failure during the write phase nothing is published and every temp
    file is removed, so the bundle is exactly as it was. A failure during the
    publish phase cannot be undone - see the module docstring - so it reports
    which files landed and which did not, rather than pretending either way.
    """
    ordered = changeset._ordered()
    payload = {"changed": [path for path, _, _ in ordered],
               "ids": dict(changeset.ids),
               "dry_run": bool(dry_run)}
    if dry_run:
        return payload

    written = []
    try:
        for path, text, _ in ordered:
            temp = path + SUFFIX
            # newline="" disables translation, so the bytes handed in are the
            # bytes that land. Text mode would rewrite every line ending in a
            # CRLF concept in order to change one key - see the module docstring.
            with open(temp, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
                handle.flush()
                # Before any replace, not after all of them: a replace that
                # publishes a name pointing at unflushed content is the one way
                # a crash can leave a *corrupt* file rather than an old one.
                # Measured at 1.9 ms per file over 200 4 KB writes - 1.1 ms
                # without, 3.0 ms with - so about 6 ms for a three-file change.
                # The number is here so nobody removes this on a guess about
                # what it costs.
                os.fsync(handle.fileno())
            written.append(temp)
    except OSError as exc:
        _discard(written)
        raise Refused(f"{exc.filename or ''}: could not be written - {exc.strerror}\n"
                      f"fix:  nothing was changed. Check the path exists and is "
                      f"writable, then run the command again")

    published = []
    try:
        for (path, _, _), temp in zip(ordered, written):
            os.replace(temp, path)
            published.append(path)
    except OSError as exc:
        # Reached by the ordinary case, not an exotic one: a read-only attribute
        # on the target, an editor holding a handle, antivirus on Windows. It
        # used to escape as a bare PermissionError, so the one failure that
        # leaves a bundle half-changed was also the only one that reported
        # itself as a traceback instead of two lines and a fix.
        #
        # Atomicity cannot be restored here - what is published is published, and
        # rolling back would need the previous contents of files this module was
        # never given. So it says exactly what landed instead of implying either
        # that everything did or that nothing did.
        _discard(written[len(published):])
        pending = [path for path, _, _ in ordered[len(published):]]
        lines = ["the change was published in part, and could not be completed"]
        lines += [f"published:     {path}" for path in published]
        lines += [f"not published: {pending[0]} - {exc.strerror}"]
        lines += [f"not published: {path}" for path in pending[1:]]
        # The `fix:` used to say "run the same command again - it rewrites all of
        # them", and that is a claim about callers this module has no business
        # making. Measured against the first real one: `okf project add` refuses the
        # second run with "already exists", and a resume is not available to it
        # either - the concept carries a `timestamp`, so a second run cannot produce
        # the same bytes. So the instruction was false for the only command that
        # could reach it. What is always true is the ordering guarantee above: the
        # concept publishes first, so whatever landed is the authored half and
        # whatever did not is derivable from it. The repair itself belongs to a
        # command that does not exist yet - see the module docstring on reindex -
        # and naming one nobody can run would only be the old lie in a new spelling.
        lines.append("fix:  what landed is correct; what did not is derivable from "
                     "it. Clear whatever blocked the write, then bring the listed "
                     "files up to date - re-running the same command may refuse, "
                     "because the concept it would write is now there.")
        raise Refused("\n".join(lines))
    return payload


def _discard(temps):
    """Remove temp files that will never be published.

    Best effort, and deliberately silent: it runs while an error is already on
    its way up, and a failure to clean up must not replace the message saying
    what went wrong. What it misses is the residue named in the module docstring.
    """
    for temp in temps:
        try:
            os.remove(temp)
        except OSError:                                  # pragma: no cover
            pass
