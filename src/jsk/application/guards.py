"""The refusals several commands share, returned as lines and never printed.

A command that refuses says why in the same words wherever it runs: `jsk render`,
`jsk preview`, `jsk ship` and `jsk kb confirm` all turn a frozen application away, and every
command that reads the record turns away a workspace still laid out as files. The wording
lives here once; each adapter prints it.
"""
import os


def unloaded_refusal(root):
    """Refuse a workspace whose career is still career/kb.ttl, with no career/store/.

    The record lives in the store: a command that read the files would answer from a
    record jsk no longer writes, so each refuses until `jsk kb load .` has imported them,
    once. The shipped example (paths.EXAMPLE_WORKSPACE) is no exception: it ships as files,
    since a store's format is tied to the installed pyoxigraph, and whatever reads it
    imports it into a store of its own first, as `jsk doctor` does (preflight.verify).

    Args:
        root: the workspace root, or None when no workspace was found.

    Returns:
        [what is wrong, the fix] as two lines, or None when the workspace has a store or
        is not laid out as files. Reads only whether two paths exist.
    """
    if root and os.path.isfile(os.path.join(root, "career", "kb.ttl")) and \
            not os.path.isdir(os.path.join(root, "career", "store")):
        return [f"{root}: the career is still career/kb.ttl, and jsk reads it from "
                "career/store/ now",
                f"fix:  jsk kb load .   - run in {root}, it imports the files once"]
    return None


def frozen_refusal(*dirs):
    """Refuse a render into, or from, a frozen application.

    Frozen is what the application's record says (timeline.frozen), not whether a file
    is there.

    Args:
        *dirs: the directories the command would write into or read from.

    Returns:
        [what is wrong, the fix] for the first frozen directory, or None. Opens the
        record read-only to ask.
    """
    from ..graph.timeline import frozen

    for d in dirs:
        path = frozen(d)
        if path:
            return [f"frozen: {path} - re-rendering would overwrite what was sent",
                    "fix:  copy the application to a new dated directory to reuse it"]
    return None
