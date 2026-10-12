"""Ruling 19 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: each
plugin agent is held to the `jsk mcp` tools it names, and the grants are the boundaries the prose
states - the analyst cannot touch the career, no agent can confirm, the extractor stops at the
preview.
"""
import json
import re
import unittest
from pathlib import Path

import fixtures  # noqa: F401 - puts src/ on the path, for the server's tool names

REPO =Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "jsk"

try:
    import yaml
except ImportError:                                     # pragma: no cover
    yaml = None


def frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    return yaml.safe_load(m.group(1)) if m else None


# How Claude Code names the plugin's MCP tools: mcp__plugin_<plugin>_<server>__<tool>
# (P0 results, docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md).
MCP = "mcp__plugin_jsk_graph__"


def granted(fm):
    """An agent's `tools:` as a list of names; a substring test on the raw string would
    find `Write` inside a longer name."""
    tools = fm.get("tools") or ""
    return [t.strip() for t in (tools.split(",") if isinstance(tools, str) else tools)
            if t.strip()]


def grant_faults(fm):
    """Why an agent's frontmatter does not hold it to the tools it names: no `tools:` line,
    an empty one, or a wildcard (P0: each grants every MCP tool)."""
    if "tools" not in fm:
        return ["no tools: line"]
    tools = granted(fm)
    if not tools:
        return ["an empty tools: line"]
    return [f"wildcard {t}" for t in tools if "*" in t]


def unknown_tools(text, registered, command=False):
    """The `mcp__plugin_jsk_graph__<x>` names in `text` that are not registered tools, in
    order; a command (main session, all twenty-nine per Ruling 19) may use the wildcard."""
    found = []
    for name in re.findall(re.escape(MCP) + r"([A-Za-z_*]+)", text):
        if name in registered or (name == "*" and command) or name in found:
            continue
        found.append(name)
    return found


def server_tools():
    """The names `jsk mcp` registers, as `tools/list` returns them; None without the extra."""
    import asyncio
    import importlib.util

    if importlib.util.find_spec("mcp") is None:
        return None
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    from jsk.adapters.mcp import server, session

    async def listed():
        async with connect(server.build(session.Session(root=str(REPO)))._mcp_server) as c:
            return (await c.list_tools()).tools

    return {t.name for t in asyncio.run(listed())}


@unittest.skipIf(yaml is None, "pyyaml not installed")
class AgentGrants(unittest.TestCase):
    """Ruling 19 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: the
    grants enforce the boundaries the prose states.

    This replaced `test_both_authoring_agents_keep_bash` (5.0.0), which pinned the opposite:
    Bash was how either authoring agent reached jsk at all. Every jsk call they make is a
    `jsk mcp` tool now, so Bash would only be a way round the grants.

    P0 measured Claude Code 2.1.280: an explicit `tools:` list holds a plugin subagent to
    exactly those tools; NO `tools:` line inherits every MCP tool of the session, and
    `mcp__plugin_jsk_graph__*` grants the whole server. So a grant is only a boundary when it
    names each tool, which is what these pin.
    """

    def agents(self):
        return sorted(PLUGIN.joinpath("agents").glob("*.md"))

    def test_every_agent_lists_its_tools_by_name(self):
        """An omitted `tools:` and a wildcard both hand an agent all twenty-nine tools,
        career_confirm among them."""
        for path in self.agents():
            with self.subTest(agent=path.name):
                self.assertEqual(grant_faults(frontmatter(path)), [])

    def test_a_missing_line_or_a_wildcard_is_a_fault(self):
        """The check above, planted: each way an agent ends up holding the whole server."""
        self.assertEqual(grant_faults({"name": "x"}), ["no tools: line"])
        self.assertEqual(grant_faults({"tools": f"Read, {MCP}*"}), [f"wildcard {MCP}*"])
        self.assertEqual(grant_faults({"tools": "Read, mcp__plugin_jsk_graph__app_show"}), [])

    def test_the_analyst_holds_no_tool_that_could_touch_the_career(self):
        """"**Never touch the career**" is true by construction: no Write or Edit, no shell
        to run `jsk kb apply` with, and no career_apply."""
        tools = granted(frontmatter(PLUGIN / "agents" / "jsk-tailor-analyst.md"))
        for denied in ("Write", "Edit", "Bash", MCP + "career_apply",
                       MCP + "career_preview"):
            with self.subTest(denied=denied):
                self.assertNotIn(denied, tools)
        for needed in ("posting_decide", "posting_complete", "assessment_derive",
                       "assessment_review", "assessment_complete"):
            with self.subTest(needed=needed):
                self.assertIn(MCP + needed, tools)

    def test_no_agent_can_confirm(self):
        """career_confirm carries the person's words, and only the main session talks to
        the person."""
        for path in self.agents():
            with self.subTest(agent=path.name):
                self.assertNotIn(MCP + "career_confirm", granted(frontmatter(path)))

    def test_no_agent_can_drop_an_application(self):
        """app_drop removes an application's graphs and moves its folder, so like
        career_confirm it is the main session's, after the person agrees (Ruling 3 of
        docs/superpowers/plans/2026-10-04-mcp-first.md)."""
        for path in self.agents():
            with self.subTest(agent=path.name):
                self.assertNotIn(MCP + "app_drop", granted(frontmatter(path)))

    def test_the_verifier_runs_the_gates_through_tools_and_holds_no_shell(self):
        """Ruling 3 of docs/superpowers/plans/2026-10-04-mcp-first.md: every gate it ran from
        a shell is a resume_check call now, and the fit and the ship are tools, so Bash would
        only be a way round the grants. Pinned whole, so a tool added to its list is a decision."""
        tools = granted(frontmatter(PLUGIN / "agents" / "jsk-verifier.md"))
        self.assertEqual(tools, ["Read", "Glob", MCP + "resume_check", MCP + "resume_fit",
                                 MCP + "resume_ship", MCP + "career_show", MCP + "app_show"])

    def test_the_auditor_checks_and_drafts_a_merge_but_applies_nothing(self):
        """It gains career_check and career_merge (which writes nothing: its changeset is
        text the caller previews) and resume_check, and loses Bash. It still holds no
        career_apply or career_preview."""
        tools = granted(frontmatter(PLUGIN / "agents" / "jsk-kb-auditor.md"))
        for needed in ("career_check", "career_merge", "resume_check"):
            with self.subTest(needed=needed):
                self.assertIn(MCP + needed, tools)
        for denied in ("Bash", "Edit", MCP + "career_apply", MCP + "career_preview",
                       MCP + "career_pack"):
            with self.subTest(denied=denied):
                self.assertNotIn(denied, tools)

    def test_no_agent_can_freeze_record_an_event_or_check_a_letter(self):
        """Ruling 21's amendment (2026-10-03): freezing and recording an event are the
        person's acts, and the letter check is the main session's, so these three are tools
        for the main session alone."""
        for path in self.agents():
            tools = granted(frontmatter(path))
            for denied in ("app_freeze", "app_event", "letter_check"):
                with self.subTest(agent=path.name, denied=denied):
                    self.assertNotIn(MCP + denied, tools)

    def test_neither_authoring_agent_holds_a_shell(self):
        """The analyst and the author write only through tools, each checked; a shell
        would reach `jsk kb confirm` and every file in the workspace."""
        for name in ("jsk-tailor-analyst", "jsk-resume-author"):
            with self.subTest(agent=name):
                self.assertNotIn("Bash", granted(frontmatter(PLUGIN / "agents" / f"{name}.md")))

    def test_the_author_applies_but_does_not_assess(self):
        """Its bullets go into the career (career_apply, which writes only inferred) and
        its choices into the selection; the review is the analyst's and the caller's."""
        tools = granted(frontmatter(PLUGIN / "agents" / "jsk-resume-author.md"))
        for needed in ("career_apply", "resume_select", "resume_update"):
            with self.subTest(needed=needed):
                self.assertIn(MCP + needed, tools)
        for denied in ("Write", "Edit", MCP + "assessment_review", MCP + "resume_ship"):
            with self.subTest(denied=denied):
                self.assertNotIn(denied, tools)

    def test_every_tool_the_plugin_names_is_one_the_server_registers(self):
        """A misspelt grant is silently no grant: the agent starts without the tool, and
        the first sign is a run that cannot take its next step."""
        registered = server_tools()
        if registered is None:
            self.skipTest("the mcp extra is not installed")
        self.assertEqual(len(registered), 29)
        for path in sorted(PLUGIN.rglob("*.md")):
            with self.subTest(file=path.name):
                self.assertEqual(unknown_tools(path.read_text(encoding="utf-8"), registered,
                                               command=path.parent.name == "commands"), [])

    def test_a_misspelt_tool_is_caught(self):
        """The check above, planted; and the wildcard is a command's alone."""
        known = {"app_show", "career_view"}
        self.assertEqual(unknown_tools(f"{MCP}app_show, {MCP}app_shows", known), ["app_shows"])
        self.assertEqual(unknown_tools(f"tools: {MCP}*", known), ["*"])
        self.assertEqual(unknown_tools(f"allowed-tools: Bash, {MCP}*", known, command=True), [])

    def test_the_plugin_starts_the_server(self):
        """The tools exist in a session only because plugin.json starts `jsk mcp`; the
        names above are `mcp__plugin_<plugin>_<server>__<tool>`, so the server is `jsk`."""
        plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["name"], "jsk")
        self.assertEqual(plugin["mcpServers"]["graph"], {"command": "jsk", "args": ["mcp"]})


if __name__ == "__main__":
    unittest.main()
