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


# The three formats an application archive may still hold from an older layout.
# Nothing writes them and nothing reads them: a sent application is frozen, so its
# posting and its assessment are there to be re-read by a person, not re-checked.
FROZEN = (".posting.json", ".gaps.json")


def record_refusal(target):
    """Why `target` is not a record the record gate can read, or None if it is.

    Shared by `jsk validate` and `jsk ship`, so that the two commands that start at a
    record turn the same wrong file away in the same words.

    Args:
        target: the path the command was given.

    Returns:
        The lines saying what is wrong and what to pass instead, or None. Asks only
        whether the path exists and is a directory.
    """
    if os.path.isdir(target):
        return [f"FAIL  cannot validate a directory: {target}",
                "fix:  there is no bundle format any more. Pass the application's",
                "      resume.json - `jsk kb export` writes one"]
    if not os.path.exists(target):
        return [f"file not found: {target}"]
    if target.endswith(FROZEN):
        return [f"FAIL  cannot validate: {target}",
                "fix:  this is an archived UJD or UGS document from an application",
                "      that has already been sent. Both formats are retired, and a",
                "      frozen document is meant to be read, not re-checked."]
    if target.endswith(".md"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  the career is in career/store/, which `jsk kb check` validates. This",
                "      gate reads an application's choice from the career - pass resume.json"]
    if target.endswith(".ttl"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  the graph record is validated on every load - `jsk kb check`",
                "      shows its findings. This gate reads an application's choice from",
                "      it - pass resume.json"]
    if not target.endswith(".json"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  pass the application's resume.json"]
    return None


# The line every command that took --view prints now. A resume.json is one resume: the
# view that picked a slice of a 41KB record went with the record (2026-09-25), and a
# shell history or an old mode file still passes it, so it is named, not "unknown flag".
VIEW_GONE = ["--view is gone: a resume.json is one resume", "fix:  drop --view"]


def view_refusal(args):
    """Refuse the --view flag every command that took one used to.

    Args:
        args: the command's arguments.

    Returns:
        VIEW_GONE when they pass --view, else None.
    """
    return VIEW_GONE if "--view" in args else None
