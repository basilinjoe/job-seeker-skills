"""The argv entry points both doors run, named by the script names the docs use.

Each module here takes an argument list the way a command-line script does, prints, and
returns an exit code. The MCP tools run them inside the workspace through adapters/mcp/captured.py
and wrap what they print (Ruling 5 of docs/superpowers/plans/2026-10-04-mcp-first.md); the `jsk`
command runs the four that stay through adapters/cli/main.py. `dispatch.ADAPTERS` maps each
documented script name to its module, so both doors reach one entry point and neither owns it.
They bind their ports through adapters/compose/, never from the door that called them.
"""
