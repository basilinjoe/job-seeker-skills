"""6.0 retired the commands that served only applications made from files: P2 of
docs/superpowers/plans/2026-10-03-retire-file-pipeline.md.

Ruling 1: each retired command, and each file form of a command that stays, exits 2 - through
adapters/cli/main.py's retired table, or the command's own refusal - names the tool or the
target form that replaces it, and writes nothing; never a silent shim and never "unknown
command", which reads as a broken install. A retired noun answers for every verb it had, and
for --help. The tools that took a file-made application (`app_freeze`, `letter_check` with a
resume.json) say it as a FAIL finding.

Ruling 2: a frozen application made from files stays readable - its quotes are still checked
against the posting.md beside it on every load. Ruling 5: one made from files and not sent is
named by `app_list`, `jsk doctor` and the career_check tool, with the release that still
finishes one (5.1.0) and the app_drop tool; its files are no longer judged, since nothing here can
change them.

2026-10-04, docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 4: `jsk kb check|pack|merge`,
`jsk resume check|render|preview|fit|ship`, `jsk app drop` and the nouns `resume` and `app` went
too. Each exits 2, says it was retired, names its tool and writes nothing; `validate`, `check`,
`gates`, `render`, `preview`, `fit` and `ship` name the tool, not another retired command.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import appkit
import careerkit
from jsk import cli
from jsk.adapters.cli import main as M

HAS_MCP = importlib.util.find_spec("mcp") is not None
TODAY = "2026-10-03"
LETTER = "Dear team,\n\nI build platforms.\n\nRegards,\nJane\n"


def jsk(*argv):
    """(exit code, stdout and stderr) of `jsk argv...` run in this interpreter."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(["jsk", *map(str, argv)])
    return code, out.getvalue()


def tree(root):
    """{relative path: bytes} of every file under `root`: what a call must leave alone."""
    found = {}
    for d, _, names in os.walk(root):
        for name in names:
            path = os.path.join(d, name)
            with open(path, "rb") as fh:
                found[os.path.relpath(path, root)] = fh.read()
    return found


# (the retired call, `{app}` the file-made application and `{root}` the workspace, what the
# fix must name). A resume.json is named whether or not one is there: the form went, and
# "file not found" would read as the fix.
RETIRED_CALLS = [
    (["posting", "fetch", "https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd",
      "{app}"], "posting_capture"),
    (["posting", "extract", "{app}"], "app_show"),
    (["posting", "build", "{app}"], "posting_decide"),
    (["posting", "build", "{app}", "decisions.txt", "--replace"], "posting_complete"),
    (["posting"], "posting_capture"),
    (["posting", "--help"], "posting_capture"),
    (["tailor", "match", "{app}"], "assessment_derive"),
    (["tailor", "match", "{app}", "--gaps", "{app}/gaps.txt"], "assessment_review"),
    (["tailor", "match", "{app}", "--draft-gaps", "{app}/gaps.txt"], "assessment_derive"),
    (["tailor", "prepare", "{app}", "--draft-gaps"], "assessment_derive"),
    (["tailor"], "assessment_complete"),
    # Ruling 10 of the onion design retired `jsk match` for `jsk tailor match`; 6.0 retired
    # that too, so the older name now names the tool as well.
    (["match", "{app}"], "assessment_derive"),
    (["kb", "export", "--from-match", "{app}", "--out", "{app}/resume.json"], "resume_select"),
    (["kb", "export", "--ranked", "--out", "{app}/resume.json", "--replace"], "resume_select"),
    (["kb", "confirm", "--summary", "{app}/resume.json", "--answer", "That is my summary."],
     "career_confirm"),
    (["kb", "confirm", "--headline", "{app}/resume.json", "--answer", "That is my title."],
     "career_confirm"),
    (["resume", "check", "{app}/resume.json"], "resume_check"),
    (["resume", "render", "{app}/resume.json", "--out", "{root}/out"], "resume_render"),
    (["resume", "preview", "{app}/resume.json", "--out", "{root}/out"], "resume_preview"),
    (["resume", "ship", "{app}/resume.json", "--out", "{root}/out"], "resume_ship"),
    (["resume", "check", "{root}", "--record", "{app}/resume.json"], "resume_check"),
    (["letter", "check", "{root}/letter.txt", "--record", "{app}/resume.json"],
     "letter_check"),
    (["app", "freeze", "{app}", "--submitted", TODAY, "--channel", "Workday"], "app_freeze"),
]


class Workspace(unittest.TestCase):
    """The claims fixture, stored: applications/contoso-platform is made from files and
    unsent (posting.md and a posting graph built from decisions)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws")
        self.app = str(Path(self.root) / "applications" / "contoso-platform")
        Path(self.root, "letter.txt").write_text(LETTER, encoding="utf-8")
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)


class Retired(Workspace):
    def test_each_exits_2_names_its_replacement_and_writes_nothing(self):
        for argv, names in RETIRED_CALLS:
            argv = [a.format(app=self.app, root=self.root) for a in argv]
            with self.subTest(call=" ".join(argv[:2])):
                before = tree(self.root)
                code, out = jsk(*argv)
                self.assertEqual(code, 2, out)
                self.assertTrue(" was retired: in 6.0" in out or " was retired in 6.0: " in out,
                                out)
                self.assertIn("fix:  ", out)
                self.assertIn(names, out)
                self.assertNotIn("unknown command", out)
                self.assertEqual(tree(self.root), before, "a retired command writes nothing")

    def test_a_retired_noun_is_no_noun_and_every_verb_it_had_is_named(self):
        for noun in M.RETIRED_NOUNS:
            with self.subTest(noun=noun):
                self.assertNotIn(noun, M.NOUNS)
                self.assertIn(noun, M.RETIRED)
        for noun, verbs in (("posting", ("fetch", "extract", "build")),
                            ("tailor", ("match", "prepare"))):
            for verb in verbs:
                self.assertIn(f"{noun} {verb}", M.RETIRED)


# 2026-10-04, docs/superpowers/plans/2026-10-04-retire-duplicated-cli.md: the verbs the MCP
# tools duplicate went too. Each call is a verb as the skill and the mode files used to run
# it; the second item is what its refusal must name, and a "{changes}" argument is the
# changeset file in the workspace.
RETIRED_VERBS = [
    (["kb", "apply", "{changes}"], "career_apply"),
    (["kb", "apply", "{changes}", "--dry-run"], "career_preview"),
    (["kb", "confirm", "prj_site_onboarding", "--answer", "42 sites, said the person."],
     "career_confirm"),
    (["kb", "confirm", "--summary", "contoso-platform", "--answer", "Yes, that is mine."],
     "career_confirm"),
    (["kb", "show", "prj_site_onboarding", "--bullets"], "career_show"),
    (["kb", "view", "--section", "skills"], "career_view"),
    (["kb", "query", "pipeline", "--json"], "career_query"),
    (["kb", "log", "--last", "3"], "career_log"),
    (["kb", "export", "--ranked"], "resume_select"),
    (["kb", "path"], "jsk doctor"),
    (["app", "freeze", "contoso-platform", "--submitted", TODAY, "--channel", "Workday"],
     "app_freeze"),
    (["app", "event", "contoso-platform", "submitted", "--date", TODAY], "app_event"),
    (["letter", "check", "letter.txt", "--record", "contoso-platform"], "letter_check"),
    (["letter"], "letter_check"),
    (["letter", "--help"], "letter_check"),
]

# 2026-10-04, docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 4: the verbs the rendering
# and upkeep tools duplicate went as well, with the nouns they left empty, and the top-level
# names that pointed at them now name the tool rather than another retired command.
RETIRED_TOOLS = [
    (["kb", "check"], "career_check"),
    (["kb", "check", "--only", "applications/acme"], "career_check"),
    (["kb", "pack", "capabilities", "--out", "pack.trig"], "career_pack"),
    (["kb", "merge", "c:team-leadership", "--into", "c:people-management"], "career_merge"),
    (["resume", "check", "contoso-platform"], "resume_check"),
    (["resume", "render", "contoso-platform", "--pdf"], "resume_render"),
    (["resume", "preview", "contoso-platform", "--out", "previews"], "resume_preview"),
    (["resume", "fit", "resume.tex", "--target-pages", "2"], "resume_fit"),
    (["resume", "ship", "contoso-platform"], "resume_ship"),
    (["app", "drop", "contoso-platform", "--dry-run"], "app_drop"),
    (["resume"], "resume_ship"),
    (["resume", "--help"], "resume_check"),
    (["app"], "app_drop"),
    (["app", "--help"], "app_drop"),
    (["validate", "contoso-platform"], "resume_check"),
    (["check", "resume.pdf"], "resume_check"),
    (["gates", "out"], "resume_check"),
    (["render", "contoso-platform"], "resume_render"),
    (["preview", "contoso-platform", "--out", "previews"], "resume_preview"),
    (["fit", "resume.tex"], "resume_fit"),
    (["ship", "contoso-platform"], "resume_ship"),
]
RETIRED_VERBS += RETIRED_TOOLS


def kbcheck(root, *extra):
    """(exit code, output) of the kb adapter's check verb, as the career_check tool runs it:
    `jsk kb check` is refused before it gets there."""
    from jsk.adapters.mcp.captured import ran

    return ran(root, "kbcli.py", ["check", "--root", root, *extra])


class RetiredVerbs(Workspace):
    """Ruling 2 of the retire-duplicated-cli plan: a retired verb exits 2, names its tool,
    and writes nothing - even where its noun would otherwise hand off to its own adapter."""

    def setUp(self):
        super().setUp()
        Path(self.root, "changes.trig").write_text("# a changeset\n", encoding="utf-8")

    def test_each_exits_2_names_its_tool_and_leaves_the_store_as_it_was(self):
        for argv, names in RETIRED_VERBS:
            argv = [a.format(changes=os.path.join(self.root, "changes.trig")) for a in argv]
            with self.subTest(call=" ".join(argv[:2])):
                before = tree(self.root)
                code, out = jsk(*argv)
                self.assertEqual(code, 2, out)
                self.assertIn(" was retired: in 6.0 - ", out)
                self.assertIn("fix:  ", out)
                self.assertIn(names, out)
                self.assertNotIn("unknown", out)
                self.assertNotIn("usage: jsk kb", out, "kb prints no usage of its own for one")
                self.assertEqual(tree(self.root), before, "a retired verb writes nothing")

    def test_a_retired_verb_is_refused_before_the_workspace_is_looked_for(self):
        # Run from a folder that is no workspace: the refusal is not "no workspace here".
        elsewhere = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, elsewhere, True)
        os.chdir(elsewhere)
        code, out = jsk("kb", "show", "prj_site_onboarding")
        self.assertEqual(code, 2, out)
        self.assertIn("career_show", out)
        self.assertNotIn("no workspace", out)

    def test_the_retired_verbs_are_out_of_the_nouns_and_the_help(self):
        self.assertEqual(M.KB_VERBS, ("load", "dump"))
        for noun in ("letter", "resume", "app"):
            self.assertNotIn(noun, M.NOUNS)
            self.assertIn(noun, M.RETIRED_NOUNS)
        self.assertEqual(set(M.NOUNS), {"doctor", "kb", "mcp"})
        _, help_text = jsk("--help")
        for verb in ("kb apply", "kb confirm", "kb show", "kb view", "kb query", "kb log",
                     "kb export", "kb path", "app freeze", "app event", "letter check"):
            self.assertNotIn(f"jsk {verb}", help_text)
        # `kb --help` may say the verbs went, but lists none of them as a verb.
        _, help_text = jsk("kb", "--help")
        for verb in ("apply <changeset", "confirm <id>", "show <id>", "view [--section",
                     "query <name>", "export [--select", "log [--last", "path   "):
            self.assertNotIn(f"  {verb}", help_text)
        # What stays is listed, and what went is not a command in it.
        _, help_text = jsk("--help")
        for kept in ("jsk doctor", "jsk kb new", "jsk kb load", "jsk kb dump", "jsk mcp"):
            self.assertIn(kept, help_text)
        for gone in ("jsk resume", "jsk app", "jsk kb check", "jsk kb pack", "jsk kb merge"):
            self.assertNotIn(gone, help_text)
        for tool in ("career_check", "career_pack", "career_merge", "resume_ship", "app_drop"):
            self.assertIn(tool, help_text)

    def test_a_top_level_name_names_a_tool_and_not_another_retired_command(self):
        for name in ("validate", "check", "gates", "render", "preview", "fit", "ship"):
            with self.subTest(name=name):
                code, out = jsk(name, "x")
                self.assertEqual(code, 2, out)
                self.assertNotIn("jsk resume", out)
                self.assertIn("(jsk mcp)", out)
        # `new` is still a command's old name: kb new stays.
        self.assertIn("jsk kb new", jsk("new", "p")[1])

    def test_the_kb_adapter_keeps_check_pack_and_merge_for_the_tools(self):
        from jsk.adapters.cli import kb

        self.assertLessEqual({"check", "pack", "merge"}, set(kb.VERBS))
        code, out = kbcheck(self.root)
        self.assertNotIn("was retired", out)
        self.assertEqual(code, 0, out)

    def test_the_verbs_that_stay_still_run(self):
        # kb dump and load are not retired: the refusal must not catch them.
        code, out = jsk("kb", "dump", "--root", self.root, "--out",
                        os.path.join(self.root, "backup.trig"))
        self.assertNotIn("was retired", out)
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "backup.trig")))
        # An unknown kb verb still reaches the adapter's own usage, not an unknown-command.
        code, out = jsk("kb", "nosuchverb")
        self.assertEqual(code, 2, out)
        self.assertIn("usage: jsk kb", out)


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
class Tools(Workspace):
    """The tools that took a file-made application say what the command says, as a FAIL."""

    def test_letter_check_with_a_resume_json_fails_naming_the_target_form(self):
        found = served(self.root)("letter_check", letter="letter.txt",
                                  record=os.path.join(self.app, "resume.json"))
        fails = [f for f in found["findings"] if f["severity"] == "FAIL"]
        self.assertIn("was retired in 6.0", fails[0]["text"])
        self.assertIn("record=<stem>", fails[0]["fix"])
        self.assertIsNone(found["verdict"])

    def test_app_freeze_on_a_file_made_application_fails_with_ruling_5_s_fix(self):
        before = tree(self.root)
        found = served(self.root)("app_freeze", app="contoso-platform", submitted=TODAY,
                                  channel="Workday")
        self.assertFalse(found["ok"])
        [fail] = found["findings"]
        self.assertEqual(fail["severity"], "FAIL")
        self.assertIn("was made from files", fail["text"])
        self.assertIn("send it with jsk 5.1.0", fail["fix"])
        self.assertIn('the app_drop tool (jsk mcp), app_drop(app="contoso-platform")', fail["fix"])
        self.assertEqual(tree(self.root), before, "nothing frozen, nothing renamed")


class FrozenArchive(unittest.TestCase):
    """Ruling 2 over tests/graph_fixtures, whose acme-platform-engineer was made from files
    and frozen: its application graph is in the store, its posting.md beside it."""

    POSTING_MD = "applications/acme-platform-engineer/posting.md"
    APPLICATION = "applications/acme-platform-engineer/application"
    ASKED = "Deep, hands-on K8s experience in production."

    def workspace(self, frozen=True, reworded=False):
        from test_graph_shapes import FIXTURES

        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
        if reworded:
            # The advert no longer says what the requirement quotes.
            advert = root / self.POSTING_MD
            text = advert.read_text(encoding="utf-8")
            self.assertIn(self.ASKED, text)
            advert.write_text(text.replace(self.ASKED, "Kubernetes."), encoding="utf-8")
        appkit.seed(root)
        if not frozen:
            appkit.drop(root, self.APPLICATION)
        return root

    def findings(self, root):
        from test_graph_shapes import load

        return [f for f in load(root).findings if f.file.startswith("applications/")]

    def test_a_frozen_file_made_application_still_validates(self):
        root = self.workspace()
        self.assertEqual([f.text() for f in self.findings(root) if f.severity == "FAIL"], [])
        code, out = kbcheck(root)
        self.assertNotIn("file-made-unsent", out, "a frozen one is no unsent one")

    def test_its_quotes_are_still_checked_against_the_posting_md_beside_it(self):
        # The archive is read, not trusted: an advert that no longer says a quote fails.
        rules = {f.rule for f in self.findings(self.workspace(reworded=True))
                 if f.severity == "FAIL"}
        self.assertIn("quote-verbatim", rules)

    def test_one_frozen_as_an_application_md_is_checked_like_one_frozen_as_a_graph(self):
        # The P3 review (2026-10-04): records.frozen and file_made_unsent counted an
        # application.md as frozen, the advert rules did not, so such a folder was neither
        # unsent nor judged and a quote its posting.md no longer said passed.
        root = self.workspace(frozen=False, reworded=True)
        Path(root, "applications/acme-platform-engineer/application.md").write_text(
            "---\nsubmitted: 2026-09-10\n---\n", encoding="utf-8")
        rules = {f.rule for f in self.findings(root) if f.severity == "FAIL"}
        self.assertIn("quote-verbatim", rules)
        code, out = kbcheck(root)
        self.assertNotIn("file-made-unsent", out)

    def test_an_unsent_one_is_not_judged_and_is_named_instead(self):
        root = self.workspace(frozen=False, reworded=True)
        self.assertEqual([f.text() for f in self.findings(root)
                          if f.rule in ("quote-verbatim", "advert-uncovered")], [])
        code, out = kbcheck(root)
        self.assertIn("WARN  file-made-unsent applications/acme-platform-engineer was made "
                      "from files and is not sent", out)


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

    @unittest.skipUnless(HAS_MCP, "the mcp extra is not installed")
    def test_resume_check_on_a_file_made_stem_says_it_has_no_selection(self):
        # The P3 replay (2026-10-04): "not a directory: acme-sent ... pass the directory jsk
        # resume render --out wrote to" sent the person to render a frozen application.
        check = served(self.root)

        def checked(target):
            found = check("resume_check", target=target)
            return found["exit"], found["output"]

        code, out = checked("acme-sent")
        self.assertEqual(code, 2, out)
        self.assertIn("acme-sent names applications/acme-sent, a frozen application made "
                      "from files: it has no selection to check", out)
        self.assertIn("the career_show tool (jsk mcp) on k:post_contoso_platform or the app_show tool", out)
        self.assertNotIn("not a directory", out)
        code, out = checked("contoso-platform")
        self.assertEqual(code, 2, out)
        self.assertIn("send it with jsk 5.1.0", out)
        self.assertNotIn("not a directory", out)
        # A name that is no application is still not a directory.
        code, out = checked("no-such-thing")
        self.assertIn("not a directory: no-such-thing", out)

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
        code, out = kbcheck(self.root)
        self.assertIn("WARN  file-made-unsent applications/contoso-platform was made from "
                      "files and is not sent; jsk 6.0 no longer finishes such an application",
                      out)
        # The release that still finishes one is named: the reader runs one that cannot.
        self.assertIn("send it with jsk 5.1.0, the last CLI that does", out)
        # It named a changeset until 2026-10-03, which cannot remove an application's graphs.
        self.assertIn('or drop it: the app_drop tool (jsk mcp), app_drop(app="contoso-platform")', out)
        self.assertEqual(out.count("file-made-unsent"), 1, out)
        code, out = kbcheck(self.root, "--only", "applications/acme-native")
        self.assertNotIn("file-made-unsent", out)

    def test_doctor_counts_them_in_an_info_line(self):
        from jsk.adapters.cli.doctor import store_report

        lines, broken = store_report(self.root)
        self.assertFalse(broken)
        self.assertIn("  info  unsent   1 application made from files is not sent, and jsk 6.0 "
                      "no longer finishes it", lines)
        self.assertTrue(any("the career_check tool names each" in line and "jsk 5.1.0" in line
                            for line in lines), lines)

    @unittest.skipUnless(HAS_MCP, "the mcp extra is not installed")
    def test_app_list_marks_it_unsent_with_the_note(self):
        found = served(self.root)("app_list")
        apps = {a["app"]: a for a in found["applications"]}
        self.assertTrue(apps["contoso-platform"]["unsent"])
        self.assertIn("send it with jsk 5.1.0", apps["contoso-platform"]["note"])
        self.assertFalse(apps["acme-sent"]["unsent"])
        self.assertFalse(apps["acme-native"]["unsent"])
        self.assertNotIn("notes", apps, "a folder with no record file is no application")
        self.assertEqual([(f["severity"], f["text"].split(" ")[0]) for f in found["findings"]],
                         [("WARN", "applications/contoso-platform")])


if __name__ == "__main__":
    unittest.main()
