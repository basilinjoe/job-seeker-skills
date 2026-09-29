"""A workspace still laid out as files - career/kb.ttl, log.ttl, applications/*/*.ttl -
read once into the graphs `jsk kb load` puts in career/store/.

The files are read by the loader that read them before the store existed, so they are
validated exactly as they always were. Numbers are rewritten to the form the store keeps
them in (`8.40` becomes `8.4`), and each rewrite is reported: after the import there is no
text left to show the old form. The files are left where they are, and never read again.

Deleted in release N+1, with the file loader it is the last user of.
"""
import os


def has_files(root):
    return os.path.isfile(os.path.join(root, "career", "kb.ttl"))


def read_workspace(root):
    """(store, {name: [Triple]}, [(graph name, quad, kept literal)]) for the files under
    `root`: the store as the file loader validated it, the record graphs ready for the
    store, and every number the store will keep in another form."""
    import pyoxigraph as ox

    from . import store as S
    from .io import canonical_numbers

    store = S.load(root, files=S.workspace_files(root))
    record, rewrites = {}, []
    for name, parsed in store.parsed.items():
        if parsed.kind == "vocabulary":
            continue
        quads, changed = canonical_numbers(parsed.quads)
        rewrites += [(name, q, kept) for q, kept in changed]
        record[name] = [ox.Triple(q.subject, q.predicate, q.object) for q in quads]
    return store, record, rewrites
