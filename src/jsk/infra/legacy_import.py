"""A workspace still laid out as files - career/kb.ttl, log.ttl, applications/*/*.ttl -
read once into the graphs `jsk kb load` puts in career/store/.

The files are read by the loader that read them before the store existed, so they are
validated exactly as they always were. Numbers are rewritten to the form the store keeps
them in (`8.40` becomes `8.4`), and each rewrite is reported: after the import there is no
text left to show the old form. The files are left where they are, and never read again.

Deleted in release N+1, with the file loader it is the last user of.
"""
import glob
import os

from .workspace import SHIPPED_VOCABULARY


def has_files(root):
    """Whether the workspace at `root` is still laid out as files.

    Args:
        root: the workspace root.

    Returns:
        True when career/kb.ttl is there. Reads only whether the file exists.
    """
    return os.path.isfile(os.path.join(root, "career", "kb.ttl"))


def workspace_files(root, vocabulary=SHIPPED_VOCABULARY):
    """The record files under a workspace root still laid out as files - what the import reads.

    Args:
        root: the workspace root.
        vocabulary: the shipped vocabulary's file, read last; None or a missing file for none.

    Returns:
        The paths in a fixed order: the career, its log, each application's posting,
        application and gaps files, each general resume's selection, then the vocabulary.
        Missing ones are absent.
    """
    found = [os.path.join(root, "career", "kb.ttl"), os.path.join(root, "career", "log.ttl")]
    for pattern in ("posting.ttl", "application.ttl", "gaps.ttl"):
        # Escaped: a root named "jobs [2026]" is a glob character class, and would
        # silently match no application at all.
        found += sorted(glob.glob(os.path.join(glob.escape(str(root)), "applications", "*",
                                               pattern)))
    # A general resume's selection (resumes/<name>/resume.ttl): the shipped example carries
    # its own since 6.0, which reads no resume.json, so `jsk doctor` imports a resume to
    # render with the career (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2).
    found += sorted(glob.glob(os.path.join(glob.escape(str(root)), "resumes", "*",
                                           "resume.ttl")))
    found = [f for f in found if os.path.isfile(f)]
    if vocabulary and os.path.isfile(vocabulary):
        found.append(vocabulary)
    return found


def read_workspace(root):
    """The files under `root`, read for the store.

    The load is application/record/load.py's over the files themselves, with this
    workspace's disk and a fresh engine, as `jsk kb load` has always validated them.

    Args:
        root: the workspace root, laid out as files.

    Returns:
        (store, {name: [Triple]}, [(graph name, quad, kept literal)]): the store as the
        file loader validated it, the record graphs ready for the store, and every number
        the store will keep in another form. Reads the files.
    """
    import pyoxigraph as ox

    from ..application.record.load import load
    from .adverts import Adverts
    from .oxigraph.codec import canonical_numbers
    from .oxigraph.engine import OxigraphEngine
    from .workspace import Workspace

    store = load(root, SHIPPED_VOCABULARY, workspace_files(root), None, source=Workspace(),
                 new_engine=OxigraphEngine, adverts=Adverts())
    record, rewrites = {}, []
    for name, parsed in store.parsed.items():
        if parsed.kind == "vocabulary":
            continue
        quads, changed = canonical_numbers(parsed.quads)
        rewrites += [(name, q, kept) for q, kept in changed]
        record[name] = [ox.Triple(q.subject, q.predicate, q.object) for q in quads]
    return store, record, rewrites
