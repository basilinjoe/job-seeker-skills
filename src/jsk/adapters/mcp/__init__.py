"""`jsk mcp`: the career and graph-native applications served to agents as typed tools.

This module is the entry point and nothing more, and it imports only the standard library
(tests/test_layers.py holds it to that, STDLIB_ONLY): the `mcp` SDK is an optional extra
(Ruling 13 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md), so a
plain install must be able to say the extra is missing rather than fail on an import at
the top of a module. The tools are server.py's, the shapes of their batches schemas.py's,
and the workspace and the read cache session.py's.
"""
import sys

# What a plain install says when asked to serve: the one line that installs the extra.
MISSING = "the MCP server needs the mcp extra: pip install 'jsk-resume[mcp]'"

# The oldest mcp the server runs on: the pin in pyproject.toml's extra. An older SDK left in
# the same interpreter by something else (1.4.1 on this author's machine, 2026-10-02) imports
# fine and then fails on FastMCP.tool(structured_output=...) with a traceback, so the version
# is checked before the import.
OLDEST = (1, 30)

USAGE = """usage: jsk mcp
  serve the career and its applications to an agent as MCP tools, over stdio.
  The workspace is the one around the current directory, or JSK_ROOT.
  Needs the mcp extra: pip install 'jsk-resume[mcp]'"""


def main(argv):
    """`jsk mcp`: serve over stdio until the client closes it.

    Args:
        argv: the arguments after `mcp`.

    Returns:
        0 when the client closed the session or help was asked for; 2 for arguments it
        does not take, or when the mcp extra is not installed.
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
              f"Python has mcp {old}: pip install -U 'jsk-resume[mcp]'", file=sys.stderr)
        return 2
    try:
        from . import server
    except ImportError as e:
        # Only the SDK's absence is the extra's refusal; a broken jsk module is a bug and
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
