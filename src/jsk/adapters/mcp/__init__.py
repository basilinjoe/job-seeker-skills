"""`jsk mcp`: the career and graph-native applications served to agents as typed tools.

This module is the entry point and nothing more, and it imports only the standard library
(tests/test_layers.py holds it to that, STDLIB_ONLY): the `mcp` SDK is a required
dependency since 6.0 (Ruling 3 of docs/superpowers/plans/2026-10-04-retire-duplicated-cli.md),
but a global Python can still lack it or hold an old one another package pinned, so the
entry point says to reinstall jsk-resume rather than fail on an import at the top of a module. The tools are server.py's, the shapes of their batches schemas.py's,
and the workspace and the read cache session.py's.
"""
import sys

# What an interpreter without the SDK says when asked to serve: reinstall, which brings the
# `mcp` jsk-resume now requires.
MISSING = ("the MCP server needs the mcp package, which jsk-resume requires: "
           "pip install -U jsk-resume")

# The oldest mcp the server runs on: the pin in pyproject.toml's dependencies. An older SDK left in
# the same interpreter by something else (1.4.1 on this author's machine, 2026-10-02) imports
# fine and then fails on FastMCP.tool(structured_output=...) with a traceback, so the version
# is checked before the import.
OLDEST = (1, 30)

USAGE = """usage: jsk mcp
  serve the career and its applications to an agent as MCP tools, over stdio.
  The workspace is the one around the current directory, or JSK_ROOT.
  Needs the mcp package jsk-resume requires: pip install -U jsk-resume"""


def main(argv):
    """`jsk mcp`: serve over stdio until the client closes it.

    Args:
        argv: the arguments after `mcp`.

    Returns:
        0 when the client closed the session or help was asked for; 2 for arguments it
        does not take, or when the mcp package is not installed or is too old.
    """
    if any(a in ("-h", "--help", "help") for a in argv):
        print(USAGE)
        return 0
    if argv:
        print(f"jsk mcp takes no arguments, not {' '.join(argv)}\n{USAGE}", file=sys.stderr)
        return 2
    old = too_old()
    if old:
        print(f"the MCP server needs mcp {'.'.join(map(str, OLDEST))} or later, and this "
              f"Python has mcp {old}: pip install -U jsk-resume", file=sys.stderr)
        return 2
    try:
        from . import server
    except ImportError as e:
        # Only the SDK's absence is the reinstall refusal; a broken jsk module is a bug and
        # says so with its traceback.
        if (e.name or "").split(".")[0] != "mcp":
            raise
        print(MISSING, file=sys.stderr)
        return 2
    server.serve()
    return 0


def too_old():
    """The installed mcp's version when it is older than OLDEST, else None - None too when it
    is not installed at all, which the import's refusal reports instead."""
    from importlib import metadata

    try:
        version = metadata.version("mcp")
    except metadata.PackageNotFoundError:
        return None
    parts = []
    for piece in version.split(".")[:2]:
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits or 0))
    return version if tuple(parts) < OLDEST else None
