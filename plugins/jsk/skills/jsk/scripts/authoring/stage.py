"""Every file one command touches, written together and published in one order.

A command rarely changes one file. Adding a project writes the concept, its
directory index, and a line in log.md; three separate writes, and the second one
failing used to leave a bundle nobody had asked for.

This is not a transaction, and saying so plainly is the point. `os.replace` is
atomic for one file and there is no primitive that makes it atomic across
several: a crash between two replaces publishes the first and not the second.
What is guaranteed is narrower and still worth having - every file is written
and fsynced to a temp file beside its target *before* any of them is published,
so the whole changeset either reaches the publish step or none of it does. A
failing write, a full disk, a missing directory: those all land before anything
is visible, and the bundle is untouched.

What remains is the crash between two replaces, and the mitigation for that is
ORDER, not locking. The concept publishes first and its derived companions
after, so a partial failure lands on the repairable side: a concept with no index
entry, which validate_bundle.py reports as a warning and which a later reindex
can rebuild from the tree. The reverse order leaves an index entry naming a file
that never landed - a broken link, and nothing anywhere can regenerate the
concept it wanted. One of the two failure states is recoverable from the files
that survived; this module always chooses that one.

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
SUFFIX = ".okf-tmp"


class Refused(Exception):
    """This command declined to change the bundle, and says why.

    Two lines, matching concept.Unsplicable: the reason, then a `fix:` line. A
    refusal a person cannot act on is only marginally better than a half-written
    bundle, and this is the one raised when the bundle is *un*touched - so the
    message has to be the whole of what they get.
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
        self._writes.append((str(path), text, kind))

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
    file already written is removed, so the bundle is exactly as it was.
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
                os.fsync(handle.fileno())
            written.append(temp)
    except OSError as exc:
        for temp in written:
            # A failed changeset must not leave litter inside somebody's bundle,
            # where validate_bundle.py walks. Best-effort: the write already
            # failed, and a failure to clean up must not replace the message
            # saying why.
            try:
                os.remove(temp)
            except OSError:                              # pragma: no cover
                pass
        raise Refused(f"{exc.filename or ''}: could not be written - {exc.strerror}\n"
                      f"fix:  nothing was changed. Check the path exists and is "
                      f"writable, then run the command again")

    for (path, _, _), temp in zip(ordered, written):
        os.replace(temp, path)
    return payload
