"""The workspace on disk: where it is, and how its files are named as it spells them."""
import os

from ..domain.naming import short_name


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
