"""The MCP tools for keeping the workspace: career_check, career_pack, career_merge and app_drop.

docs/superpowers/plans/2026-10-04-mcp-first.md, Rulings 2 and 5: `jsk kb check|pack|merge` and
`jsk app drop` became these tools, and each calls the entry point its command called
(captured.py). career_pack and career_merge return a changeset's text for career_preview and
career_apply, and write nothing. app_drop is destructive: no agent's `tools:` names it
(tests/test_agent_grants.py), and the main session calls it once the person has agreed.
The two drafts return stdout's changeset and stderr's notes (what a pack skipped, what a merge
asks to re-confirm) as `changeset` and `notes`, since a skipped line the caller cannot read is a
gap in the draft nobody saw. They live apart from server.py, which registers them, only to keep
each module under tests/test_sizes.py's limit.
"""
import io
from typing import Literal

from .captured import answered, called, findings_in, ran
from .server import described, result


def drafted(root, args):
    """(exit code, the changeset it printed, what it said besides) of a kb draft verb.

    The kb adapter writes the changeset to stdout and its notes - what a pack skipped, what a
    merge retires or asks to re-confirm - to stderr, so stderr is captured here as well.
    """
    notes = io.StringIO()
    code, output = ran(root, "kbcli.py", args, err=notes)
    return code, output, notes.getvalue()


def draft_answer(code, output, notes):
    """A draft verb's answer: the changeset for career_preview, its notes, and no changeset
    when the verb refused or had nothing to add.

    Args:
        code: the verb's exit code.
        output: what it printed to stdout.
        notes: what it printed to stderr.
    """
    if code:
        return answered(code, output + notes)
    if not output.strip():
        return result([("WARN", notes.strip().splitlines()[-1] if notes.strip()
                        else "nothing was drafted", None)],
                      exit=code, changeset=None, notes=notes)
    return result(findings_in(output), exit=code, changeset=output, notes=notes)


def upkeep(srv, tools):
    """career_check, career_pack, career_merge and app_drop."""

    @described(srv)("Validate the whole workspace. Findings carry their fixes.")
    def career_check() -> dict:
        def run(root, today):
            code, output = ran(root, "kbcli.py", ["check", "--root", root])
            return answered(code, output)
        return tools.call("career_check", run, writes=False)

    @described(srv)("Draft the capability starter pack as a changeset for career_preview. "
                    "Writes nothing.")
    def career_pack(pack: Literal["capabilities"]) -> dict:
        def run(root, today):
            return draft_answer(*drafted(root, ["pack", pack, "--root", root]))
        return tools.call("career_pack", run, writes=False)

    @described(srv)("Draft a changeset merging concept c:a into c:b, for career_preview. "
                    "Writes nothing.")
    def career_merge(concept: str, into: str) -> dict:
        def run(root, today):
            return draft_answer(*drafted(
                root, ["merge", concept, "--into", into, "--root", root]))
        return tools.call("career_merge", run, writes=False)

    @described(srv)("Set an unsent application aside: graphs removed, folder kept under "
                    "dropped/. dry_run writes nothing.")
    def app_drop(app: str, reason: str | None = None, dry_run: bool = False) -> dict:
        def run(root, today):
            from ..entry import drop

            argv = [app] + (["--reason", reason] if reason else []) \
                + (["--dry-run"] if dry_run else [])
            code, output = called(root, drop.main, argv)
            return answered(code, output)
        return tools.call("app_drop", run, writes=True)
