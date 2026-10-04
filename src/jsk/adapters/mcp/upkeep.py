"""The MCP tools for keeping the workspace: career_check, career_pack, career_merge and app_drop.

docs/superpowers/plans/2026-10-04-mcp-first.md, Rulings 2 and 5: `jsk kb check|pack|merge` and
`jsk app drop` became these tools, and each calls the entry point its command called
(captured.py). career_pack and career_merge return a changeset's text for career_preview and
career_apply, and write nothing. app_drop is destructive: no agent's `tools:` names it
(tests/test_agent_grants.py), and the main session calls it once the person has agreed.
They live apart from server.py, which registers them, only to keep each module under
tests/test_sizes.py's limit.
"""


def upkeep(srv, tools):
    """career_check, career_pack, career_merge and app_drop."""
