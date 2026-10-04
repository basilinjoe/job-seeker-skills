"""The MCP tools for a resume's files: resume_check, resume_render, resume_preview and resume_fit.

docs/superpowers/plans/2026-10-04-mcp-first.md, Rulings 2 and 5: `jsk resume check|render|
preview|fit` became these tools, and each calls the entry point its command called
(captured.py), so a verdict reads as it did. They write files, never the record.
They live apart from server.py, which registers them, only to keep each module under
tests/test_sizes.py's limit.
"""


def renders(srv, tools):
    """resume_check, resume_render, resume_preview and resume_fit."""
