"""`jsk mcp`: the career and graph-native applications served as typed tools - P4 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md, Rulings 13-18.

The rules pinned: the server registers Ruling 18's eighteen tools and the three of Ruling
21's amendment (2026-10-03, tests/test_mcp_timeline.py) by name, with batch
shapes whose fields the schema shows; every result is `{"ok": ...}` JSON and every refusal
a finding with its fix, never a traceback (Ruling 16); the whole graph-native run goes
through the tools and leaves nothing on disk; a raised verdict is a FAIL with nothing
written; a legacy application is refused naming the file verb (Ruling 11); a call with no
workspace says how to make one (Ruling 15); an exception inside a use case is one FAIL and
the next call still works; the read cache sees a CLI write made in another process
(Ruling 14); a tool write waits for a CLI writer's turn, then lands, holding nothing
between calls; the server answers over stdio as `python -m jsk mcp`; and a plain install
says the extra is missing, exits 2, and names the install line (Ruling 13). From the
2026-10-02 review: career_query pages its rows with a total, a refused changeset gives each
refusal its own fix, an ask's `about` is kept, and career_confirm on a selection returns
the confirmed block alone.

Calls go through the SDK's in-memory client session (P0 results, item 6), so what is
tested is what an agent receives: the JSON text of each result.
"""
import asyncio
import contextlib
import datetime
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

import appkit
import careerkit
from fixtures import child_env
from test_graph_native_apps import ADVERT, DROPS, K8S, ROWS, STEM

HAS_MCP = importlib.util.find_spec("mcp") is not None
TODAY = datetime.date(2026, 10, 2)
TOOLS = {"career_view", "career_show", "career_query", "career_log", "career_preview",
         "career_apply", "career_confirm", "app_list", "app_show", "posting_capture",
         "posting_decide", "posting_complete", "assessment_derive", "assessment_review",
         "assessment_complete", "resume_select", "resume_update", "resume_ship",
         # Ruling 21's amendment (2026-10-03): the main session's, granted to no agent.
         "app_freeze", "app_event", "letter_check"}
PFX = ("@prefix j: <tag:jsk,2026:ns#> .\n@prefix k: <tag:jsk,2026:id/> .\n"
       "@prefix c: <tag:jsk,2026:concept/> .\n@prefix op: <tag:jsk,2026:op#> .\n")
RENAME = PFX + 'op:set { k:prj_portal j:name "Customer portal" . }\n'
MISSING = "the MCP server needs the mcp extra: pip install 'jsk-resume[mcp]'"


def fails(result):
    return [f["text"] for f in result["findings"] if f["severity"] == "FAIL"]


@unittest.skipUnless(HAS_MCP, "the mcp extra is not installed")
class Served(unittest.TestCase):
    """The claims fixture, stored, served by a server built over it."""

    def setUp(self):
        from jsk.adapters.mcp import server, session

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws")
        clock = mock.patch.object(session, "today", return_value=TODAY)
        clock.start()
        self.addCleanup(clock.stop)
        self.session = session.Session(root=self.root)
        self.server = server.build(self.session)

    async def called(self, calls):
        from mcp.shared.memory import create_connected_server_and_client_session as connect

        out = []
        async with connect(self.server._mcp_server) as client:
            for name, args in calls:
                r = await client.call_tool(name, args)
                self.assertFalse(r.isError, r.content)
                out.append(json.loads(r.content[0].text))
        return out

    def call(self, tool, /, **args):
        """One tool's result, as the agent reads it."""
        return asyncio.run(self.called([(tool, args)]))[0]

    def graph(self, kind, stem=STEM):
        return appkit.triples(self.root, f"applications/{stem}/{kind}")


class Listed(Served):
    def test_the_server_registers_its_twenty_one_tools(self):
        async def listed():
            from mcp.shared.memory import create_connected_server_and_client_session as connect

            async with connect(self.server._mcp_server) as client:
                return (await client.list_tools()).tools
        tools = {t.name: t for t in asyncio.run(listed())}
        self.assertEqual(set(tools), TOOLS)
        # A batch row's fields are in the schema, so an agent need not guess them.
        decide = json.dumps(tools["posting_decide"].inputSchema)
        for field in ('"slug"', '"asked"', '"concepts"', '"need"', '"reason"'):
            self.assertIn(field, decide)
        self.assertEqual(tools["app_show"].inputSchema["required"], ["app", "part"])


class Career(Served):
    def test_career_view_pages_the_markdown_and_the_pages_join_up(self):
        whole = self.call("career_view", limit=10 ** 6)
        self.assertTrue(whole["ok"])
        self.assertIn("Meridian Health", whole["text"])
        self.assertIsNone(whole["next"])
        first = self.call("career_view", limit=400)
        self.assertLessEqual(len(first["text"]), 400)
        self.assertTrue(first["text"].endswith("\n"), "a page ends at a line's end")
        rest = self.call("career_view", offset=first["next"], limit=10 ** 6)
        self.assertEqual(first["text"] + rest["text"], whole["text"])

    def test_career_show_gives_turtle_and_the_base_and_a_missing_id_is_a_finding(self):
        shown = self.call("career_show", ids=["prj_data"], bullets=True)
        self.assertTrue(shown["ok"], shown)
        self.assertIsInstance(shown["base"], int)
        [entry] = shown["entries"]
        self.assertIn("Built a FastAPI ingestion service.", entry["graphs"][0]["turtle"])
        missing = self.call("career_show", ids=["prj_dta"])
        self.assertEqual(fails(missing), ["k:prj_dta is not in the record"])
        self.assertIn("k:prj_data", missing["findings"][0]["fix"])

    def test_career_query_returns_rows_and_refuses_a_wrong_call_as_a_finding(self):
        got = self.call("career_query", name="unconfirmed")
        self.assertTrue(got["ok"])
        self.assertIn("k:ach_data_ingestion", json.dumps(got["rows"]))
        near = self.call("career_query", name="concepts", args=["kubernetes"])
        self.assertIn("kubernetes", near["near"])
        for args in ({"name": "nonesuch"}, {"name": "holds"}):
            with self.subTest(args=args):
                refused = self.call("career_query", **args)
                self.assertFalse(refused["ok"])
                self.assertTrue(refused["findings"][0]["fix"])

    def test_career_query_pages_its_rows_and_says_how_many_there_are(self):
        whole = self.call("career_query", name="person", limit=10 ** 6)
        self.assertGreater(whole["total"], 2)
        self.assertEqual((len(whole["rows"]), whole["next"]), (whole["total"], None))
        first = self.call("career_query", name="person", limit=2)
        self.assertEqual((first["rows"], first["total"], first["next"]),
                         (whole["rows"][:2], whole["total"], 2))
        rest = self.call("career_query", name="person", offset=2, limit=10 ** 6)
        self.assertEqual(first["rows"] + rest["rows"], whole["rows"])

    def test_a_refused_changeset_gives_each_refusal_its_own_fix(self):
        refused = self.call("career_apply",
                            changeset=PFX + 'op:set { k:prj_nowhere j:name "x" . }\n')
        self.assertFalse(refused["ok"])
        [found] = refused["findings"]
        # The fix was folded into the text with no fix beside it (2026-10-02).
        self.assertEqual((found["text"], found["fix"]),
                         ("k:prj_nowhere - op:set on an entry that does not exist",
                          "op:add it instead"))

    def test_preview_writes_nothing_and_apply_writes_and_logs(self):
        before = appkit.facts(self.root, "kb")
        preview = self.call("career_preview", changeset=RENAME)
        self.assertTrue(preview["ok"], preview)
        self.assertFalse(preview["written"])
        self.assertIn('Customer portal', preview["diff"])
        self.assertEqual(appkit.facts(self.root, "kb"), before)
        applied = self.call("career_apply", changeset=RENAME)
        self.assertEqual((applied["written"], applied["touched"]),
                         (True, ["k:prj_portal"]))
        log = self.call("career_log", last=1)
        self.assertEqual(log["entries"][0]["by"], "apply")
        self.assertEqual(log["entries"][0]["revision"], str(applied["revision"]))
        again = self.call("career_apply", changeset=RENAME)
        self.assertEqual((again["ok"], again["changed"]), (True, False))

    def test_a_changeset_that_does_not_parse_is_a_finding(self):
        refused = self.call("career_apply", changeset=PFX + "op:add { k:prj_x j:name . }\n")
        self.assertFalse(refused["ok"])
        self.assertTrue(fails(refused))

    def test_confirm_needs_the_persons_words_and_then_logs_them(self):
        refused = self.call("career_confirm", ids=["ach_data_ingestion"], answer="yes")
        self.assertFalse(refused["ok"])
        done = self.call("career_confirm", ids=["ach_data_ingestion"],
                         answer="I built that FastAPI service myself in 2024.")
        self.assertTrue(done["written"], done)
        self.assertIn("k:ach_data_ingestion", done["touched"])
        self.assertFalse(self.call("career_confirm", answer="I did")["ok"], "no ids, no target")


class Flow(Served):
    """The analyst's calls in order, every one a tool."""

    def test_the_graph_native_run_goes_through_the_tools_and_leaves_no_file(self):
        captured = self.call("posting_capture", app=STEM, text=ADVERT)
        self.assertEqual((captured["ok"], captured["lines"]), (True, 7))
        decided = self.call("posting_decide", app=STEM, requirements=ROWS, drops=DROPS)
        self.assertEqual(fails(decided), [])
        self.assertEqual(self.call("posting_complete", app=STEM)["state"], "complete")

        derived = self.call("assessment_derive", app=STEM)
        self.assertTrue(derived["ok"], derived)
        rows = {r["slug"]: r for r in derived["rows"]}
        self.assertEqual(rows["rust"]["verdict"], "unsatisfied")
        self.assertIn("rust", [q["requirement"] for q in derived["questions"]])

        raised = self.call("assessment_review", app=STEM,
                           verdicts=[{"slug": "rust", "verdict": "satisfied"}])
        self.assertEqual(fails(raised), ["the review: rust: satisfied, above the match's "
                                         "unsatisfied"])
        self.assertIsNone(self.graph("review"), "a raised verdict writes nothing")

        reviewed = self.call("assessment_review", app=STEM, fit="partial",
                             verdicts=[{"slug": "kubernetes", "verdict": "partial",
                                        "reason": "AKS only"}], short=["Rust"],
                             asks=[{"question": "Have you written Rust?", "about": "rust"}])
        self.assertTrue(reviewed["ok"], reviewed)
        # `about` is kept now (the review item's j:about), so there is nothing to warn of;
        # until 2026-10-02 it was dropped with a WARN.
        self.assertEqual(reviewed["findings"], [])
        self.assertEqual(self.call("assessment_complete", app=STEM)["state"], "complete")

        parts = {part: self.call("app_show", app=STEM, part=part)
                 for part in ("posting", "lines", "requirements", "review", "assessment")}
        self.assertTrue(all(p["ok"] for p in parts.values()), parts)
        self.assertEqual(parts["posting"]["posting"]["state"], "complete")
        self.assertEqual(parts["lines"]["total"], 7)
        self.assertEqual(len(parts["requirements"]["requirements"]["requirements"]), 3)
        self.assertEqual(parts["review"]["review"]["state"], "complete")
        assessment = parts["assessment"]["assessment"]
        self.assertEqual((assessment["fit"], assessment["short"]), ("partial", ["Rust"]))
        self.assertIn("| Kubernetes | required | partial", assessment["markdown"])
        self.assertEqual([(q["requirement"], q["concepts"]) for q in assessment["questions"]],
                         [("rust", ["c:rust"])])
        # A graph-native assessment has no gaps.txt: its header names the review tool.
        self.assertIn("assessment_review", assessment["markdown"])
        self.assertNotIn("gaps.txt", assessment["markdown"])

        listed = {a["app"]: a for a in self.call("app_list")["applications"]}
        self.assertEqual((listed[STEM]["kind"], listed[STEM]["posting"],
                          listed[STEM]["review"]), ("native", "complete", "complete"))
        demand = self.call("career_query", name="demand")
        self.assertIn("c:rust", [r["concept"] for r in demand["rows"]])
        self.assertFalse((Path(self.root) / "applications" / STEM).exists())

    def test_a_row_that_fails_writes_nothing_and_comes_back_as_its_finding(self):
        self.call("posting_capture", app=STEM, text=ADVERT)
        before = appkit.facts(self.root, f"applications/{STEM}/posting")
        got = self.call("posting_decide", app=STEM, requirements=[{**ROWS[0], "asked": "Go"}],
                        header={"seniority": "galactic"})
        self.assertFalse(got["ok"])
        self.assertTrue(any("'Go' is not in line" in t for t in fails(got)), got)
        self.assertTrue(any("seniority" in t for t in fails(got)), got)
        self.assertEqual(appkit.facts(self.root, f"applications/{STEM}/posting"), before)

    def test_lines_page_by_offset_and_limit(self):
        self.call("posting_capture", app=STEM, text=ADVERT)
        first = self.call("app_show", app=STEM, part="lines", limit=K8S)
        self.assertEqual(([x["n"] for x in first["lines"]], first["next"]), ([1, 2, 3], 3))
        rest = self.call("app_show", app=STEM, part="lines", offset=first["next"])
        self.assertEqual(([x["n"] for x in rest["lines"]], rest["next"]), ([4, 5, 6, 7], None))

    def test_a_second_capture_is_refused_and_replace_takes_it_again(self):
        self.call("posting_capture", app=STEM, text=ADVERT)
        again = self.call("posting_capture", app=STEM, text=ADVERT)
        self.assertFalse(again["ok"])
        self.assertIn("replace", again["findings"][0]["fix"])
        self.assertTrue(self.call("posting_capture", app=STEM, text=ADVERT, replace=True)["ok"])

    def test_a_legacy_application_is_refused_naming_the_file_verb(self):
        for tool, args in (("posting_decide", {"requirements": ROWS}),
                           ("assessment_derive", {}), ("app_show", {"part": "lines"})):
            with self.subTest(tool=tool):
                got = self.call(tool, app="contoso-platform", **args)
                self.assertFalse(got["ok"])
                self.assertIn("jsk posting build", got["findings"][0]["fix"])

    def test_an_application_with_no_posting_is_told_to_capture_one(self):
        got = self.call("posting_complete", app="nobody-yet")
        self.assertIn("posting_capture", got["findings"][0]["fix"])


class Resume(Served):
    """The author's and the main session's calls over a selection: select, update, confirm,
    read and ship, every one a tool, over an application the analyst has finished."""

    def setUp(self):
        import shipkit
        from jsk.adapters.cli.compose import native
        from jsk.adapters.mcp import server, session

        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # The parse gate reads contact details and a summary off the render; the bare
        # claims fixture has neither, so a clean ship needs them.
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", edits=[shipkit.CONTACTED])
        self.session = session.Session(root=self.root)
        self.server = server.build(self.session)
        native.capture(self.root, STEM, text=ADVERT, today=TODAY)
        native.decide(self.root, STEM, rows=ROWS, drops=DROPS, today=TODAY)
        native.complete_posting(self.root, STEM, today=TODAY)
        native.derive_assessment(self.root, STEM, today=TODAY)
        native.complete_review(self.root, STEM, today=TODAY)

    def shipped(self, **compile_args):
        import shipkit
        from jsk.adapters.cli.compose import render

        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile(**compile_args)):
            return self.call("resume_ship", target=STEM, fit=False)

    def test_select_update_confirm_and_read_go_through_the_tools(self):
        selected = self.call("resume_select", target=STEM, mode="from_match")
        self.assertTrue(selected["ok"], selected)
        self.assertTrue(selected["doc"]["bullets"])
        updated = self.call("resume_update", target=STEM, headline="Platform Engineer")
        self.assertTrue(updated["ok"], updated)
        # A headline the author wrote is the author's until the person stands behind it.
        self.assertEqual(updated["doc"]["headline"]["status"], "inferred")
        confirmed = self.call("career_confirm", target=STEM, block="headline",
                              answer="It is the title I hold.")
        self.assertEqual((confirmed["ok"], confirmed["changed"]), (True, True), confirmed)
        # The confirmed block alone, not the selection before and after (~8k characters).
        self.assertEqual(confirmed["block"], {"text": "Platform Engineer", "status": "confirmed",
                                              "answer": "It is the title I hold."})
        self.assertNotIn("before", confirmed)
        self.assertNotIn("after", confirmed)
        shown = self.call("app_show", app=STEM, part="selection")
        self.assertEqual(shown["selection"]["doc"]["headline"]["status"], "confirmed")

    def test_an_unknown_bullet_is_a_finding_and_the_selection_is_unchanged(self):
        self.call("resume_select", target=STEM, mode="from_match")
        before = self.call("app_show", app=STEM, part="selection")["selection"]["doc"]
        got = self.call("resume_update", target=STEM, bullets=["ach_never_written"])
        self.assertFalse(got["ok"])
        self.assertTrue(fails(got))
        after = self.call("app_show", app=STEM, part="selection")["selection"]["doc"]
        self.assertEqual(after, before)

    def test_a_ship_leaves_only_the_pdf_and_the_tex(self):
        self.call("resume_select", target=STEM, mode="from_match")
        got = self.shipped()
        steps = {s["gate"]: s for s in got["steps"]}
        self.assertEqual(steps["render"]["status"], "PASS", steps["render"]["output"])
        app = Path(self.root) / "applications" / STEM
        self.assertEqual(sorted(p.suffix for p in app.iterdir()), [".pdf", ".tex"])

    def test_a_ship_that_does_not_pass_is_not_ok(self):
        # A ship exits 1 when its compile produces nothing; ok must say so without the
        # caller reading every step's output.
        self.call("resume_select", target=STEM, mode="from_match")
        got = self.shipped(fail=True)
        self.assertEqual(got["exit"], 1, got)
        self.assertFalse(got["ok"])
        self.assertTrue(fails(got))


class Faults(Served):
    def test_an_exception_inside_a_use_case_is_one_fail_and_the_server_keeps_serving(self):
        from jsk.adapters.cli.compose import native

        err = io.StringIO()
        with mock.patch.object(native, "list_apps", side_effect=RuntimeError("boom")), \
                contextlib.redirect_stderr(err):
            broken = self.call("app_list")
        self.assertEqual(fails(broken), ["app_list raised RuntimeError: boom"])
        self.assertIn("Traceback", err.getvalue(), "the traceback goes to stderr")
        self.assertTrue(self.call("app_list")["ok"], "the next call still works")

    def test_a_call_with_no_workspace_says_how_to_make_one(self):
        from jsk.adapters.mcp import server, session

        with tempfile.TemporaryDirectory() as empty, \
                mock.patch.dict(os.environ, {session.ROOT_ENV: ""}), \
                mock.patch.object(os, "getcwd", return_value=empty):
            self.server = server.build(session.Session())
            got = self.call("career_view")
        self.assertFalse(got["ok"])
        self.assertIn("jsk kb new", got["findings"][0]["fix"])


class Cache(Served):
    """Ruling 14: reads share one loaded record while the disk has not moved."""

    def test_a_cli_write_between_two_reads_is_seen_by_the_second(self):
        self.assertNotIn("Customer portal", self.call("career_view", limit=10 ** 6)["text"])
        self.call("career_show", ids=["prj_portal"])
        self.assertEqual(self.session.loads, 1, "two reads, one load")
        path = Path(self.root) / "rename.trig"
        path.write_text(RENAME, encoding="utf-8")
        cli = subprocess.run([sys.executable, "-m", "jsk", "kb", "apply", str(path),
                              "--root", self.root], env=child_env(), capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertIn("Customer portal", self.call("career_view", limit=10 ** 6)["text"])
        self.assertEqual(self.session.loads, 2)

    def test_the_servers_own_write_is_seen_by_its_next_read(self):
        self.call("career_view")
        self.call("career_apply", changeset=RENAME)
        self.assertIn("Customer portal", self.call("career_view", limit=10 ** 6)["text"])


class Turn(Served):
    """Ruling 14: a tool's write takes the writers' turn for that call, as the CLI does."""

    HOLD = """
        import sys, time
        from jsk.infra.oxigraph import db
        with db.write_turn(sys.argv[1]):
            print('got', flush=True)
            time.sleep(2.0)
            print('released', time.time(), flush=True)
    """

    def test_a_tool_write_waits_for_a_cli_writer_then_lands(self):
        holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(self.HOLD), self.root],
                                  env=child_env(), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "got")
        with contextlib.redirect_stderr(io.StringIO()) as said:
            captured = self.call("posting_capture", app=STEM, text=ADVERT)
        landed = time.time()
        out, _ = holder.communicate(timeout=60)
        released = float(out.split("released", 1)[1].split()[0])
        self.assertTrue(captured["ok"], captured)
        # Order, not timing: the write finished after the holder gave the turn up.
        self.assertGreaterEqual(landed, released)
        self.assertIn("waiting for another jsk write", said.getvalue())
        self.assertIsNotNone(self.graph("posting"))


@unittest.skipUnless(HAS_MCP, "the mcp extra is not installed")
class Stdio(unittest.TestCase):
    """The server as an agent's client starts it: `python -m jsk mcp`, over stdio."""

    def test_python_m_jsk_mcp_lists_its_tools_and_answers_app_list(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root, _ = careerkit.workspace(Path(tmp.name) / "ws")
        env = {**child_env(), "JSK_ROOT": str(root)}
        params = StdioServerParameters(command=sys.executable, args=["-m", "jsk", "mcp"],
                                       env=env)

        async def talk():
            async with stdio_client(params, errlog=open(os.devnull, "w")) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    tools = (await client.list_tools()).tools
                    listed = await client.call_tool("app_list", {})
                    return {t.name for t in tools}, json.loads(listed.content[0].text)

        names, listed = asyncio.run(asyncio.wait_for(talk(), timeout=120))
        self.assertEqual(names, TOOLS)
        self.assertTrue(listed["ok"], listed)
        self.assertIn("contoso-platform", [a["app"] for a in listed["applications"]])


class WithoutTheExtra(unittest.TestCase):
    """Ruling 13: a plain install says the extra is missing; it never fails an import."""

    def test_jsk_mcp_without_the_sdk_exits_2_and_names_the_install_line(self):
        # `mcp` made unimportable, as in a wheel installed without the extra.
        script = ("import sys\nsys.modules['mcp'] = None\n"
                  "from jsk.adapters.cli.main import main\nsys.exit(main(['jsk', 'mcp']))\n")
        proc = subprocess.run([sys.executable, "-c", script], env=child_env(),
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stderr.strip(), MISSING)
        self.assertEqual(proc.stdout, "")

    def test_an_mcp_older_than_the_pin_exits_2_and_names_the_upgrade(self):
        # mcp 1.4.1 sat in this author's global Python (2026-10-02): it imported, then the
        # server died on FastMCP.tool(structured_output=...) with a traceback.
        from jsk.adapters import mcp as entry

        err = io.StringIO()
        with mock.patch("importlib.metadata.version", return_value="1.4.1"), \
                contextlib.redirect_stderr(err):
            code = entry.main([])
        self.assertEqual(code, 2)
        self.assertIn("this Python has mcp 1.4.1: pip install -U 'jsk-resume[mcp]'",
                      err.getvalue())

    def test_the_entry_point_imports_only_the_standard_library(self):
        # The layers test holds jsk.adapters.mcp to the standard library; this is its
        # behaviour: importing the package does not import the SDK.
        script = ("import sys\nsys.modules['mcp'] = None\nimport jsk.adapters.mcp as m\n"
                  "print(m.MISSING)\n")
        proc = subprocess.run([sys.executable, "-c", script], env=child_env(),
                              capture_output=True, text=True, timeout=120)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, MISSING), proc.stderr)


if __name__ == "__main__":
    unittest.main()
