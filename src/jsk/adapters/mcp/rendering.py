"""The MCP tools for a resume's files: resume_check, resume_render, resume_preview and resume_fit.

docs/superpowers/plans/2026-10-04-mcp-first.md, Rulings 2 and 5: `jsk resume check|render|
preview|fit` became these tools, and each calls the entry point its command called
(captured.py), so a verdict reads as it did and the flags are the commands' own. They write
files, never the record, so none passes `writes=True`: render and preview open the career to
read a selection and fit rewrites a .tex, and nothing here reaches the store's write path.
They live apart from server.py, which registers them, only to keep each module under
tests/test_sizes.py's limit.

A render, a preview and a fit answer with `wrote`, the files the call created or changed. The
entry points print their own file lists, but each in its own words and relative to its own
directory; one list in one form (workspace-relative, forward slashes, sorted) is what a caller
can open without parsing a report. It is worked out from the directory's state before and
after, so it holds for every entry point and cannot drift from what they print.

Not exposed: `--max-findings`, `--json` and `--region` of resume_check (a report cut short or
a second format is not what a tool's own JSON wants), and `--format`, `--profile`, `--name`,
`--view`, `--dry-run`, `--in-place` and `-o` of the others, which no tool use needed.
"""
import os
from typing import Literal

from . import captured
from .server import described


def snapshot(directory):
    """{path: (mtime_ns, size)} of every file under `directory`; empty when it is no directory.

    Args:
        directory: an absolute path. A directory that does not exist yet is the state before
            a render makes it.
    """
    state = {}
    for here, _, names in os.walk(directory):
        for name in names:
            path = os.path.join(here, name)
            try:
                stat = os.stat(path)
            except OSError:
                # Gone between the walk and the stat (a TeX engine's scratch file).
                continue
            state[path] = (stat.st_mtime_ns, stat.st_size)
    return state


def wrote(root, directory, before):
    """The files under `directory` that are new or changed since `before` (snapshot's), as
    paths relative to `root` with forward slashes, sorted.

    Args:
        root: the workspace root.
        directory: an absolute path, or None when the call's directory could not be worked
            out (its target was wrong), which wrote nothing.
        before: snapshot(directory) from before the call.
    """
    if directory is None:
        return []
    after = snapshot(directory)
    changed = (p for p, seen in after.items() if before.get(p) != seen)
    return sorted(relative(root, p) for p in changed)


def relative(root, path):
    """`path` relative to `root` with forward slashes; as it is on another drive, where no
    relative path exists."""
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        return path.replace(os.sep, "/")


def absolute(root, path):
    """`path` against the workspace root, not the server's working directory."""
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(root, path))


def render_directory(root, target, out):
    """The directory a render of `target` writes to: `out` when given, else the target's own
    (render.targeted); None when `target` names no target and `out` is absent.

    Args:
        root: the workspace root.
        target: the positional as the tool was given it.
        out: --out as given, or None.
    """
    if out:
        return absolute(root, out)
    from ..cli.render import arg, targeted

    with captured.inside(root):
        own = arg(targeted(["render_resume.py", target]), "--out")
    return absolute(root, own) if own else None


def watching(root, directory, run):
    """(exit code, output, the files written) of `run()`, which prints as an entry point does.

    Args:
        root: the workspace root.
        directory: where it writes (absolute), or None.
        run: () -> (exit code, output), the captured call.
    """
    before = snapshot(directory) if directory else {}
    code, output = run()
    return code, output, wrote(root, directory, before)


def renders(srv, tools):
    """resume_check, resume_render, resume_preview and resume_fit."""

    @described(srv)("Gates for a target: <stem>, resumes/<name>, a render or its directory. "
                    "Verdict is the last line.")
    def resume_check(target: str, record: str | None = None,
                     only: Literal["parse", "prose", "layout"] | None = None,
                     strict: bool = False, pages: int | None = None) -> dict:
        def run(root, today):
            from ..cli.resume import cmd_resume_check

            argv = [target]
            for flag, value in (("--record", record), ("--only", only), ("--pages", pages)):
                if value is not None:
                    argv += [flag, value]
            if strict:
                argv.append("--strict")
            return captured.answered(*captured.called(root, cmd_resume_check, argv))
        return tools.call("resume_check", run)

    @described(srv)("Render a target's selection to .tex, and a PDF with pdf. "
                    "wrote: the files made.")
    def resume_render(target: str, out: str | None = None, pdf: bool = False,
                      template: str | None = None, ats_max: bool = False,
                      region: str | None = None) -> dict:
        def run(root, today):
            argv = [target]
            for flag, value in (("--out", out), ("--template", template),
                                ("--region", region)):
                if value is not None:
                    argv += [flag, value]
            argv += [flag for flag, on in (("--pdf", pdf), ("--ats-max", ats_max)) if on]
            code, output, made = watching(
                root, render_directory(root, target, out),
                lambda: captured.ran(root, "render_resume.py", argv))
            return captured.answered(code, output, wrote=made)
        return tools.call("resume_render", run)

    @described(srv)("Render a target in every template into out, with page counts. "
                    "wrote: the files made.")
    def resume_preview(target: str, out: str) -> dict:
        def run(root, today):
            code, output, made = watching(
                root, absolute(root, out),
                lambda: captured.ran(root, "preview_templates.py", [target, "--out", out]))
            return captured.answered(code, output, wrote=made)
        return tools.call("resume_preview", run)

    @described(srv)("Fit a rendered .tex to a page budget, floors held. wrote: the files made.")
    def resume_fit(tex: str, target_pages: int = 2) -> dict:
        def run(root, today):
            code, output, made = watching(
                root, os.path.dirname(absolute(root, tex)),
                lambda: captured.ran(root, "fit_pages.py", [tex, "--target-pages", target_pages]))
            return captured.answered(code, output, wrote=made)
        return tools.call("resume_fit", run)
