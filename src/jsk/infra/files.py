"""The workspace on disk: where it is, how its files are named as it spells them, and an
application's documents written so a reader never sees half of one."""
import os
import time

from ..domain.naming import short_name
from ..domain.record.parsed import GraphError, NotUtf8, normalise
from ..domain.record.parsed import Missing as Missing
from ..domain.record.parsed import Unreadable as Unreadable
from ..domain.timeline.errors import Unwritable

REPLACE_TRIES = 6                                # a Windows lock usually clears in ms


def find_root(start):
    """The nearest folder at or above `start` holding career/store/ - or career/kb.ttl, a
    career from before the store, found so that it can be refused with the import as the
    fix - or None."""
    here = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(here, "career", "store")) or \
                os.path.isfile(os.path.join(here, "career", "kb.ttl")):
            return here
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up


def rel(path, root):
    """`path` relative to `root`, forward slashes - or, on another Windows drive, where
    relpath raises rather than answering, the absolute path with forward slashes."""
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def inside(path, root):
    """Is `path` (followed through links) under `root`? False across drives, where
    commonpath raises."""
    here, top = (os.path.normcase(os.path.realpath(p)) for p in (path, root))
    try:
        return os.path.commonpath([here, top]) == top
    except ValueError:
        return False


def spelled(folder, name):
    """`name` as `folder` spells it on disk. Windows and macOS open `ACME` as `acme`, and a
    graph named by the typed spelling would be another application's: a sent one's posting
    written again, its sent check looking for a graph that is not there. The typed name is
    kept when nothing on disk is that same folder under another spelling."""
    try:
        names = os.listdir(folder)
    except OSError:
        return name
    if name in names:
        return name
    for other in names:
        if other.casefold() == name.casefold():
            try:
                if os.path.samefile(os.path.join(folder, name), os.path.join(folder, other)):
                    return other
            except OSError:
                pass
    return name


def file_name(path, root):
    """How findings name a file: relative to the workspace, forward slashes, each part
    spelled as it is on disk (spelled). A file outside it - the shipped vocabulary - is
    named by its basename, including when it is on another Windows drive."""
    name = rel(path, root)
    if name.startswith("../") or os.path.isabs(name):
        return os.path.basename(path)
    if name == ".":
        return name
    here, parts = os.path.abspath(root), []
    for part in name.split("/"):
        parts.append(spelled(here, part))
        here = os.path.join(here, parts[-1])
    return "/".join(parts)


def graph_name(path, root):
    """The record graph a file holds, by the name the store gives it and findings use:
    career/kb.ttl is `kb`, career/log.ttl `log`, applications/<stem>/posting.ttl
    `applications/<stem>/posting` (and application, gaps), the shipped vocabulary
    `vocabulary`. Any other path is named as file_name names it."""
    return short_name(file_name(path, root))


def read_text(path, what=None):
    """A text file a person or an agent wrote, as the writer would write it: UTF-8, no BOM,
    LF only. `what` names it in the message; the path does when it is not given. Every
    authored file is read here, so a BOM, a CRLF or a cp1252 save is handled once -
    tests/test_plugin_surface.py fails on a text read anywhere else."""
    name = what or str(path)
    try:
        with open(path, encoding="utf-8") as fh:
            return normalise(fh.read())
    except FileNotFoundError:
        raise Missing(f"{name}: no such file" + (f" at {path}" if what else ""),
                      "check the path") from None
    except UnicodeDecodeError as e:
        raise NotUtf8(f"{name}: not UTF-8 ({e.reason} at byte {e.start})",
                      "save the file as UTF-8") from None
    except OSError as e:
        raise Unreadable(f"{name}: {e.strerror or e}", "check the path and its permissions") \
            from None


def write_document(path, text, tries=REPLACE_TRIES, wait=0.05):
    """`text` staged beside `path` as path.tmp, flushed, then renamed over it - the one step
    the filesystem makes atomic, so a crash leaves the old document or the new one. The
    rename is retried: on Windows an editor, a sync client or a virus scanner holding the
    file makes it fail for a moment, and a moment later it succeeds.

    Args:
        path: the document to replace or create.
        text: its whole new text, written UTF-8 with LF line ends.
        tries: how many times the rename is attempted.
        wait: seconds before the second attempt; each later one waits that much longer.

    Returns:
        `path`.

    Raises:
        Unwritable: the file is locked or the disk refused, having written nothing; the
            staged path.tmp is removed either way.
    """
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        for n in range(tries):
            try:
                os.replace(tmp, path)
                return path
            except PermissionError:
                if n == tries - 1:
                    raise Unwritable(f"{path}: not written - it is locked by another "
                                     "program - an editor, a sync client or a virus scanner",
                                     "close it and run the command again") from None
                time.sleep(wait * (n + 1))
    except OSError as e:
        raise Unwritable(f"{path}: not written - {e.strerror or e}",
                         "check the folder and its permissions") from None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def remove_document(path):
    """Remove the document at `path` if it is there.

    Args:
        path: the file to remove.

    Returns:
        True when a file was removed, False when there was none.

    Raises:
        Unwritable: the file is there and could not be removed.
    """
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
    except OSError as e:
        raise Unwritable(f"{path}: not removed - {e.strerror or e}",
                         "close whatever holds it and run the command again") from None
    return True


def parse(path, root=None):
    """Parse a file on disk; `root` makes the reported name relative to the workspace."""
    file = rel(path, root) if root else str(path).replace("\\", "/")
    try:
        text = read_text(path, file)
    except NotUtf8 as e:
        raise GraphError(str(e), e.fix, file) from None
    from .oxigraph.codec import parse_text

    return parse_text(text, file)
