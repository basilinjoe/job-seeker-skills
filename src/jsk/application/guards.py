"""The refusals several commands share, returned as lines and never printed.

A command or tool that refuses says why in the same words wherever it runs: the resume_render,
resume_preview, resume_ship and career_confirm tools (jsk mcp) all turn a frozen application away,
and every command that reads the record turns away a workspace still laid out as files. The wording
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


def frozen_refusal(*dirs, frozen, sent=None, native=False):
    """Refuse a render into, or from, a frozen application.

    Frozen is what the application's record says (application.timeline.records.frozen),
    not whether a file is there. A held-back freeze (`--submitted false`) is frozen too,
    but nothing was sent: with `sent` the refusal says which it is. A graph-native
    application is reused by capturing its posting again under a new stem, since the
    tools' caller has no shell to copy a directory with (`native`).

    Args:
        *dirs: the directories the command would write into or read from.
        frozen: (directory) -> what says it was frozen, or None (compose.timeline.frozen).
        sent: (directory) -> the day it was sent, or None when held back
            (compose.timeline.sent_day); None says "sent" of every freeze, as before.
        native: the application is graph-native (Ruling 11 of
            docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md).

    Returns:
        [what is wrong, the fix] for the first frozen directory, or None. Opens the
        record read-only to ask.
    """
    from ..domain.record.parsed import GraphError

    for d in dirs:
        path = frozen(d)
        if not path:
            continue
        try:
            held_back = sent is not None and not sent(d)
        except GraphError:
            held_back = False           # unreadable: say the stronger thing
        what = ("re-rendering would overwrite what was frozen (held back, not sent)"
                if held_back else "re-rendering would overwrite what was sent")
        reuse = ("fix:  capture the posting again under a new stem (`posting_capture`) to "
                 "reuse it" if native else
                 "fix:  copy the application to a new dated directory to reuse it")
        return [f"frozen: {path} - {what}", reuse]
    return None


# The three formats an application archive may still hold from an older layout.
# Nothing writes them and nothing reads them: a sent application is frozen, so its
# posting and its assessment are there to be re-read by a person, not re-checked.
FROZEN = (".posting.json", ".gaps.json")


def record_refusal(target, verb="check"):
    """Why `target` is not a record the record gate can read, or None if it is.

    Shared by the resume_check and resume_ship tools, so that the two that start at a
    record turn the same wrong file away in the same words. A record is a target's selection
    since 6.0, which reads no resume.json: one named is told the target form (Ruling 1 of
    docs/superpowers/plans/2026-10-03-retire-file-pipeline.md).

    Args:
        target: the path the command was given, or a graph-native target's ref.
        verb: the resume tool the fix names: `check` for resume_check, `ship` for resume_ship.

    Returns:
        The lines saying what is wrong and what to pass instead, or None. Asks only
        whether the path exists and is a directory.
    """
    from .render.selection import parse_ref

    if parse_ref(target):
        # A target's selection is a graph, not a file: the record gate reads it
        # (application/render/selection.py), and there is nothing on disk to look for.
        return None
    if is_resume_json(target):
        return resume_json_refusal(f"resume_{verb}(<resume.json>)",
                                   f"resume_{verb}(<stem>) (or resumes/<name>) - the "
                                   "target's stored selection")
    if os.path.isdir(target):
        return [f"FAIL  cannot validate a directory: {target}",
                "fix:  name the target it renders: <stem> or resumes/<name>"]
    if not os.path.exists(target):
        return [f"file not found: {target}"]
    if target.endswith(FROZEN):
        return [f"FAIL  cannot validate: {target}",
                "fix:  this is an archived UJD or UGS document from an application",
                "      that has already been sent. Both formats are retired, and a",
                "      frozen document is meant to be read, not re-checked."]
    if target.endswith(".md"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  the career is in career/store/, which the career_check tool validates. This",
                "      gate reads a target's choice from the career - name the target"]
    if target.endswith(".ttl"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  the graph record is validated on every load - the career_check tool",
                "      shows its findings. This gate reads a target's choice from",
                "      it - name the target: <stem> or resumes/<name>"]
    return [f"FAIL  cannot validate: {target}",
            "fix:  name the target: <stem> or resumes/<name>"]


def is_resume_json(value):
    """Whether `value` names a resume.json - by its name alone, so a file that is not there
    is still told the form went, rather than that it is missing."""
    return isinstance(value, str) and value.lower().endswith(".json")


def resume_json_refusal(form, fix):
    """[what went, the fix] for a resume.json given where 6.0 reads a target's selection.

    docs/superpowers/plans/2026-10-03-retire-file-pipeline.md (Ruling 1, P2): every command
    that read or wrote a resume.json path takes a target - `<stem>` or `resumes/<name>` -
    instead, and says so by name, exit 2, never silently. The words are here once, so the
    record gate, the render, the preview, the ship, the confirm, the letter gate and the
    export say it alike.

    Args:
        form: the retired form, e.g. "resume_check(<resume.json>)".
        fix: the command or tool that replaces it.

    Returns:
        The two lines to print.
    """
    return [f"{form} was retired in 6.0: a resume.json is no longer read - a target's "
            "selection, in the store, is", f"fix:  {fix}"]


# The line every command that took --view prints now. A resume.json - a selection now - is
# one resume: the view that picked a slice of a 41KB record went with the record
# (2026-09-25), and a shell history or an old mode file still passes it, so it is named,
# not "unknown flag".
VIEW_GONE = ["--view is gone: a resume.json is one resume", "fix:  drop --view"]


def view_refusal(args):
    """Refuse the --view flag every command that took one used to.

    Args:
        args: the command's arguments.

    Returns:
        VIEW_GONE when they pass --view, else None.
    """
    return VIEW_GONE if "--view" in args else None
