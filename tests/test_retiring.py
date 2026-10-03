"""The file pipeline says it retires in 6.0, and the unsent applications it still serves are
named: P1 of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md.

Ruling 1: every file verb, used in its file form, keeps working in 5.x and prints one added
WARN naming the tool that replaces it - its exit code and every line it printed before stay
as they were, and a `--json` stdout still parses, the WARN going to stderr there. The same
verb in its graph-native form prints nothing new. The tools that take a file-made application
(`app_freeze`, `letter_check` with a resume.json) carry the WARN as a finding.

Ruling 5: an application made from files and not sent - its folder holds a resume.json,
decisions.txt or posting.md, its posting graph has no advert lines, and nothing froze it - is
named by `app_list`, `jsk doctor` and `jsk kb check`. A frozen one and a graph-native one are
not.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import appkit
import careerkit
from jsk import cli
from jsk.adapters.cli import retiring

HAS_MCP = importlib.util.find_spec("mcp") is not None
TODAY = "2026-10-03"
LETTER = "Dear team,\n\nI build platforms.\n\nRegards,\nJane\n"


def jsk(*argv):
    """(exit code, stdout, stderr) of `jsk argv...` run in this interpreter."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["jsk", *map(str, argv)])
    return code, out.getvalue(), err.getvalue()


def unwarned():
    """The commands as they were before 5.1: no call is in its file form, and no application
    was made from files."""
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch("jsk.adapters.cli.main.file_form", lambda *a: None))
    stack.enter_context(mock.patch(
        "jsk.adapters.cli.compose.timeline.made_from_files", lambda *a, **k: False))
    return stack


# command -> its call in the claims workspace, `{root}`, `{app}` and `{short}` filled in. The
# heavy verbs (render, preview, ship, confirm) are called on a resume.json that is not there:
# the file form is in the name, and a refusal's exit code is as much a contract as a pass's.
CALLS = {
    "jsk posting fetch": ["posting", "fetch", "https://example.com/jobs/1", "{app}"],
    "jsk posting extract": ["posting", "extract", "{app}"],
    "jsk posting build": ["posting", "build", "{app}"],
    "jsk tailor prepare": ["tailor", "prepare", "{app}"],
    "jsk tailor match": ["tailor", "match", "{app}"],
    "jsk kb export --out": ["kb", "export", "--from-match", "{app}", "--out",
                            "{root}/draft/resume.json", "--root", "{root}"],
    "jsk resume check <resume.json>": ["resume", "check", "{short}"],
    "jsk resume render <resume.json>": ["resume", "render", "{root}/missing.json",
                                        "--out", "{root}/out"],
    "jsk resume preview <resume.json>": ["resume", "preview", "{root}/missing.json",
                                         "--out", "{root}/out"],
    "jsk resume ship <resume.json>": ["resume", "ship", "{root}/missing.json",
                                      "--out", "{root}/out"],
    "jsk kb confirm --summary <resume.json>": ["kb", "confirm", "--summary",
                                               "{root}/missing.json", "--answer",
                                               "Yes, that is my summary.", "--root", "{root}"],
    "jsk kb confirm --headline <resume.json>": ["kb", "confirm", "--headline",
                                                "{root}/missing.json", "--answer",
                                                "Yes, that is my headline.", "--root", "{root}"],
    "jsk letter check --record <resume.json>": ["letter", "check", "{root}/letter.txt",
                                                "--record", "{short}"],
    "jsk app freeze": ["app", "freeze", "{app}", "--submitted", TODAY, "--channel", "Workday"],
}


class Workspaces(unittest.TestCase):
    """The claims fixture, stored: applications/contoso-platform is made from files and
    unsent (posting.md, a posting graph built from decisions, and a resume.json)."""

    def workspace(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root, short = careerkit.workspace(Path(tmp.name) / "ws", short=careerkit.short())
        Path(root, "letter.txt").write_text(LETTER, encoding="utf-8")
        return root, short

    def call(self, command, warned=True):
        """(exit code, stdout, stderr) of `command`'s CALLS entry in a fresh workspace, its
        paths written as <root>."""
        root, short = self.workspace()
        app = str(Path(root) / "applications" / "contoso-platform")
        argv = [a.format(root=root, app=app, short=short) for a in CALLS[command]]
        with contextlib.nullcontext() if warned else unwarned():
            code, out, err = jsk(*argv)
        return code, out.replace(root, "<root>"), err.replace(root, "<root>")


class FileVerbs(Workspaces):
    def test_every_file_verb_warns_once_and_otherwise_says_what_it_said(self):
        # Every command of the plan's table, so a verb added to it and not warned fails here.
        self.assertEqual(set(CALLS), set(retiring.REPLACEMENTS))
        for command in CALLS:
            with self.subTest(command=command):
                before = self.call(command, warned=False)
                code, out, err = self.call(command)
                warning = retiring.lines(command) + "\n"
                self.assertTrue(out.startswith(warning), out)
                self.assertEqual(out.count("retires in 6.0"), 1, out)
                # The WARN is an added line: the exit code and everything printed before
                # are unchanged.
                self.assertEqual((code, out[len(warning):], err), before)

    def test_the_warn_says_ruling_1_s_words_and_names_its_replacement(self):
        text, fix = retiring.warning("jsk posting build")
        self.assertEqual(text, "jsk posting build serves applications made from files and "
                               "retires in 6.0 - finish this application or drop it")
        self.assertIn("posting_decide", fix)
        self.assertTrue(retiring.lines("jsk posting build").startswith("WARN  "))

    def test_a_json_stdout_still_parses_and_the_warn_goes_to_stderr(self):
        root, _ = self.workspace()
        code, out, err = jsk("tailor", "match", Path(root) / "applications" / "contoso-platform",
                             "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["posting"], "k:post_contoso_platform")
        self.assertIn("WARN  jsk tailor match serves applications made from files", err)

    def test_a_graph_native_form_prints_no_warn(self):
        root, _ = self.workspace()
        for argv in (["resume", "check", "contoso-platform"],
                     ["letter", "check", Path(root) / "letter.txt", "--record",
                      "contoso-platform"],
                     ["kb", "check", "--root", root],
                     ["resume", "render", "--help"]):
            with self.subTest(argv=argv):
                _, out, err = jsk(*argv)
                self.assertNotIn("retires in 6.0", out + err)

    def test_only_the_file_form_is_one(self):
        form = retiring.file_form
        self.assertEqual(form("resume", "check", ["r.json"]), "jsk resume check <resume.json>")
        self.assertIsNone(form("resume", "check", ["out", "--record", "r.json"]))
        self.assertIsNone(form("resume", "ship", ["acme", "--out", "x.json"]))
        self.assertIsNone(form("kb", "export", ["--ranked"]))
        self.assertIsNone(form("kb", "confirm", ["k:ach_x", "--answer", "yes"]))
        self.assertIsNone(form("kb", "confirm", ["--summary", "acme", "--answer", "yes"]))
        self.assertIsNone(form("letter", "check", ["l.txt", "--record", "acme"]))
        self.assertIsNone(form("app", "freeze", ["applications/acme"]))


def served(root):
    """call(tool, **args) -> the tool's JSON result, from a server built over `root` and
    called through the SDK's in-memory client, as tests/test_mcp_server.py calls one."""
    import asyncio

    from jsk.adapters.mcp import server, session

    built = server.build(session.Session(root=root))

    async def called(name, args):
        from mcp.shared.memory import create_connected_server_and_client_session as connect

        async with connect(built._mcp_server) as client:
            r = await client.call_tool(name, args)
            return json.loads(r.content[0].text)

    return lambda name, **args: asyncio.run(called(name, args))


@unittest.skipUnless(HAS_MCP, "the mcp extra is not installed")
class Tools(Workspaces):
    """The tools that take a file-made application say what the command says."""

    def test_letter_check_with_a_resume_json_carries_the_warn(self):
        root, short = self.workspace()
        call = served(root)
        found = call("letter_check", letter="letter.txt", record=short)
        warns = [f["text"] for f in found["findings"] if f["severity"] == "WARN"]
        self.assertEqual(warns[0], retiring.warning("jsk letter check --record <resume.json>")[0])
        found = call("letter_check", letter="letter.txt", record="contoso-platform")
        self.assertNotIn("retires in 6.0", json.dumps(found))

    def test_app_freeze_on_a_file_made_application_carries_the_warn(self):
        root, _ = self.workspace()
        found = served(root)("app_freeze", app="contoso-platform", submitted=TODAY,
                             channel="Workday")
        self.assertEqual((found["findings"][0]["severity"], found["findings"][0]["text"]),
                         ("WARN", retiring.warning("jsk app freeze")[0]))


class Unsent(unittest.TestCase):
    """One workspace holding all three kinds: the claims fixture's contoso-platform, made from
    files and unsent; acme-sent, made from files and frozen; and acme-native, graph-native,
    with a resume.json left beside it that is never read (Ruling 11)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", short=careerkit.short())
        apps = Path(self.root) / "applications"
        sent = apps / "acme-sent"
        shutil.copytree(apps / "contoso-platform", sent)
        posting = appkit.text(self.root, "applications/contoso-platform/posting")
        appkit.put(self.root, "applications/acme-sent/posting", posting, prefixes=False)
        appkit.put(self.root, "applications/acme-sent/application",
                   'k:app_acme_sent j:posting k:post_contoso_platform ; '
                   'j:submitted "2026-09-10"^^xsd:date ; j:channel "company site" .\n')
        from jsk.adapters.cli.compose import native

        native.capture(self.root, "acme-native", text="- Kubernetes in production.\n",
                       company="Acme Health", title="Platform Engineer",
                       today=datetime.date(2026, 10, 3))
        (apps / "acme-native").mkdir()
        (apps / "acme-native" / "resume.json").write_text("{}", encoding="utf-8")
        (apps / "notes").mkdir()                     # a folder with no record file at all

    def test_the_one_rule_finds_only_the_unsent_file_made_application(self):
        from jsk.application.timeline.unsent import file_made_unsent
        from jsk.infra.files import application_listing

        found = file_made_unsent(appkit.graphs(self.root), application_listing(self.root))
        self.assertEqual(found, ("contoso-platform",))

    def test_a_folder_with_only_a_resume_json_and_no_graph_is_unsent_too(self):
        from jsk.application.timeline.unsent import file_made_unsent

        self.assertEqual(file_made_unsent({}, {"globex": {"resume.json"}}), ("globex",))
        self.assertEqual(file_made_unsent({}, {"globex": {"resume.json", "application.md"}}),
                         (), "an application.md is one frozen before the career was a graph")

    def test_kb_check_warns_file_made_unsent_naming_it_and_the_fix(self):
        code, out, _ = jsk("kb", "check", "--root", self.root)
        self.assertIn("WARN  file-made-unsent applications/contoso-platform was made from "
                      "files and is not sent", out)
        self.assertIn("send it with this 5.x CLI", out)
        # It named a changeset until 2026-10-03, which cannot remove an application's graphs.
        self.assertIn("or drop it: `jsk app drop applications/contoso-platform`", out)
        self.assertEqual(out.count("file-made-unsent"), 1, out)
        code, out, _ = jsk("kb", "check", "--root", self.root, "--only",
                           "applications/acme-native")
        self.assertNotIn("file-made-unsent", out)

    def test_doctor_counts_them_in_an_info_line(self):
        from jsk.adapters.cli.doctor import store_report

        lines, broken = store_report(self.root)
        self.assertFalse(broken)
        self.assertIn("  info  unsent   1 application made from files is not sent, and jsk 6.0 "
                      "no longer finishes it", lines)
        self.assertTrue(any("`jsk kb check` names each" in line for line in lines), lines)

    @unittest.skipUnless(HAS_MCP, "the mcp extra is not installed")
    def test_app_list_marks_it_unsent_with_the_note(self):
        found = served(self.root)("app_list")
        apps = {a["app"]: a for a in found["applications"]}
        self.assertTrue(apps["contoso-platform"]["unsent"])
        self.assertIn("send it with this 5.x CLI", apps["contoso-platform"]["note"])
        self.assertFalse(apps["acme-sent"]["unsent"])
        self.assertFalse(apps["acme-native"]["unsent"])
        self.assertNotIn("notes", apps, "a folder with no record file is no application")
        self.assertEqual([(f["severity"], f["text"].split(" ")[0]) for f in found["findings"]],
                         [("WARN", "applications/contoso-platform")])


if __name__ == "__main__":
    unittest.main()
