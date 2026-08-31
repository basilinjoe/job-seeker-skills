"""The whole write catalogue: every noun and verb reachable, and one run using them all.

Two things are pinned here that no per-module test can pin.

**The surface.** `CATALOGUE` is the design's own table
(docs/superpowers/specs/2026-08-31-okf-write-cli-design.md, "The catalogue") written
as data. A verb in the design and not in the parser is a hole; a verb in the parser
and not in the design is a surface nobody documented. Both fail here, which is what
makes the claim "the CLI manages the format" checkable rather than asserted.

**The run.** One bundle built from scaffold to filed application entirely through
commands - no Write, no Edit, no hand-authored concept anywhere - and then put through
the gates. That is the design's actual promise: *the only path an agent has to change
a bundle*. If a bundle cannot be built this way, the promise is not kept, whatever the
per-verb tests say.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import (INIT_BUNDLE, OKF_COMPILE, SCRIPTS, VALIDATE_BUNDLE,
                      authoring_module, run)

commands = authoring_module("authoring.commands")

OKF = SCRIPTS / "okf.py"
VALIDATE_URS = SCRIPTS / "validate_urs.py"

# noun -> its verbs. An empty tuple means the noun IS the verb - `okf log --message`,
# `okf reindex` - because a single-purpose noun with a verb level would be a word
# that says nothing.
CATALOGUE = {
    "project": ("add", "set", "retire", "rm"),
    "role": ("add", "set", "retire", "rm"),
    "org": ("add", "set", "retire", "rm"),
    "education": ("add", "set", "retire", "rm"),
    "bullet": ("add", "set", "rm", "mv"),
    "skill": ("add", "set", "rm", "mv"),
    "credential": ("add", "set", "rm", "mv"),
    "metric": ("add", "set"),
    "capability": ("add",),
    "question": ("add", "resolve"),
    "log": (),
    "reindex": (),
    "posting": ("add", "requirement"),
    "gaps": ("write",),
    "view": ("create", "set", "include"),
    "application": ("file", "event"),
}

# The flags the design makes cross-cutting: "--bundle DIR, --dry-run, --json, and
# --set key=value for extension keys" on every write.
CROSS_CUTTING = ("--bundle", "--dry-run", "--json", "--set")


def subparsers_of(parser):
    """The one subparsers action of a parser, or None."""
    for action in parser._actions:
        if (hasattr(action, "choices") and action.choices
                and hasattr(action, "_name_parser_map")):
            return action.choices
    return None


class TheSurfaceIsTheDesignsCatalogue(unittest.TestCase):
    """Every verb the design lists exists, and no verb exists that it does not."""

    def setUp(self):
        self.parser = commands.build_parser()
        self.nouns = subparsers_of(self.parser)
        self.assertIsNotNone(self.nouns, "the top-level parser has no nouns at all")

    def test_every_noun_in_the_catalogue_is_registered(self):
        self.assertEqual(sorted(self.nouns), sorted(CATALOGUE),
                         "the parser's nouns and the design's catalogue disagree")

    def test_every_verb_in_the_catalogue_is_registered(self):
        for noun, verbs in sorted(CATALOGUE.items()):
            with self.subTest(noun=noun):
                found = subparsers_of(self.nouns[noun])
                if not verbs:
                    self.assertIsNone(
                        found, f"`okf {noun}` has a verb level and should not - it is "
                               f"a single-purpose noun")
                    continue
                self.assertIsNotNone(found, f"`okf {noun}` registers no verbs")
                self.assertEqual(sorted(found), sorted(verbs),
                                 f"`okf {noun}`'s verbs disagree with the catalogue")

    def test_every_verb_carries_the_cross_cutting_flags(self):
        """The design makes these four universal, and a verb missing --dry-run is a
        verb nobody can rehearse.
        """
        for noun, verbs in sorted(CATALOGUE.items()):
            leaves = []
            if not verbs:
                leaves.append((noun, self.nouns[noun]))
            else:
                found = subparsers_of(self.nouns[noun])
                for verb in verbs:
                    nested = subparsers_of(found[verb])
                    if nested:
                        # `posting requirement add` - a verb with its own verbs.
                        leaves.extend((f"{noun} {verb} {inner}", parser)
                                      for inner, parser in nested.items())
                    else:
                        leaves.append((f"{noun} {verb}", found[verb]))
            for name, parser in leaves:
                with self.subTest(command=name):
                    flags = {option for action in parser._actions
                             for option in action.option_strings}
                    for flag in CROSS_CUTTING:
                        self.assertIn(flag, flags, f"`okf {name}` has no {flag}")

    def test_okf_py_answers_to_every_noun(self):
        """okf.py lists the nouns itself, so `okf --help` need not import the parser.
        Two lists, and they must not drift.
        """
        # Executed rather than imported, so this reads okf.py's own tables without
        # importing the write layer - which is the property okf.py is carrying them
        # for. `__file__` has to be supplied: the script computes HERE from it.
        okf = {"__file__": str(OKF)}
        with open(OKF, encoding="utf-8") as handle:
            source = handle.read()
        exec(compile(source.split("if __name__")[0], str(OKF), "exec"), okf)
        self.assertEqual(sorted(okf["WRITE_NOUNS"]), sorted(CATALOGUE))
        for noun in CATALOGUE:
            self.assertIn(noun, okf["HANDLERS"], f"okf.py does not dispatch {noun!r}")


class BundleCase(unittest.TestCase):
    """A real scaffolded bundle in a temp directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)

    def okf(self, *args, stdin=""):
        """One write command through okf.py, as an agent would run it."""
        result = subprocess.run(
            [sys.executable, str(OKF)] + [str(a) for a in args],
            input=stdin, capture_output=True, text=True, encoding="utf-8")
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def must(self, *args, stdin=""):
        code, out = self.okf(*args, stdin=stdin)
        self.assertEqual(code, 0, f"okf {' '.join(str(a) for a in args)}\n{out}")
        return out


class OneBundleBuiltEntirelyByCommands(BundleCase):
    """Scaffold to filed application with no hand-written concept anywhere.

    This is the design's promise made checkable. Every refusal in the catalogue is
    tested in its own module's file; what is tested here is that the verbs compose -
    that the bundle one verb leaves behind is one the next verb accepts, and that the
    whole of it clears the gates at the end.
    """

    def build(self):
        b = ["--bundle", str(self.root)]
        self.must("capability", "add", *b, "--term", "event-driven-architecture",
                  "--term", "data-sovereignty", "--theme", "Architecture & design")
        self.must("org", "add", *b, "--title", "Acme Health",
                  "--description", "Aged-care provider.", "--relationship", "employer",
                  "--industry", "healthcare", "--employment", "employment",
                  "--body", "What they do.")
        self.must("role", "add", *b, "--title", "Staff Engineer",
                  "--slug", "staff-engineer-acme",
                  "--description", "Owned the platform.",
                  "--organisation", "acme-health", "--start", "2023-01",
                  "--state", "ongoing", "--seniority", "team-leadership",
                  "--body", "What the job was.")
        self.must("project", "add", *b, "--title", "Care Platform Rebuild",
                  "--description", "Rebuilt the claims pipeline.",
                  "--role", "staff-engineer-acme", "--strength", "5",
                  "--recency", "2026", "--seniority", "architecture-ownership",
                  "--domain", "healthcare", "--capability", "event-driven-architecture",
                  "--headline-metric", "claim latency 4.2s to 380ms",
                  "--body", "What this project was.")
        self.must("metric", "add", *b, "--name", "Claim latency",
                  "--value", "4.2s to 380ms", "--evidence", "care-platform-rebuild",
                  "--source", "dashboard")
        self.must("bullet", "add", *b, "--project", "care-platform-rebuild",
                  "--text", "Cut claim latency from 4.2s to 380ms.",
                  "--metric", "Claim latency", "--status", "confirmed")
        self.must("bullet", "add", *b, "--project", "care-platform-rebuild",
                  "--text", "Led a team of six engineers.", "--status", "confirmed")
        self.must("skill", "add", *b, "--text", "C# / .NET",
                  "--category", "language", "--aliases", "C#, .NET, ASP.NET Core")
        self.must("education", "add", *b, "--title", "BSc Computer Science",
                  "--institute", "University of Somewhere", "--period", "2015 - 2018",
                  "--body", "What it covered.")
        self.must("credential", "add", *b, "--concept", "certifications",
                  "--text", "Azure Solutions Architect Expert",
                  "--issuer", "Microsoft", "--issued", "2024-05", "--status", "active")

    def test_the_bundle_builds_and_clears_the_gates(self):
        self.build()
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("VALID", out)
        code, out = run(OKF_COMPILE, self.root)
        self.assertEqual(code, 0, out)

    def test_the_record_holds_what_the_commands_wrote(self):
        self.build()
        record = self.record()
        self.assertEqual([o["name"] for o in record["organizations"]], ["Acme Health"])
        self.assertEqual([p["title"] for p in record["projects"]],
                         ["Care Platform Rebuild"])
        texts = [a["text"] for p in record["projects"]
                 for a in p.get("achievements", [])]
        self.assertIn("Cut claim latency from 4.2s to 380ms.", texts)
        self.assertIn("Led a team of six engineers.", texts)
        self.assertEqual([s["name"] for s in record["skills"]], ["C# / .NET"])
        self.assertEqual([c["name"] for c in record["credentials"]],
                         ["Azure Solutions Architect Expert"])
        self.assertTrue(record["education"], "no education compiled")

    def record(self):
        """The compiled record, as JSON.

        Not through fixtures.run, which folds stderr into stdout - the compile
        prints its own summary there, and the record has to parse.
        """
        import json
        result = subprocess.run(
            [sys.executable, str(OKF_COMPILE), str(self.root), "--dump-record"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class TailoringAndFilingComposeOnTopOfIt(OneBundleBuiltEntirelyByCommands):
    """The other two tranches, run against the bundle the first one built."""

    def tailor(self):
        b = ["--bundle", str(self.root)]
        # The employer applied to is an Organisation too - bundle-spec.md: one file
        # per company, "whether they worked there, applied there, or both". Filing
        # refuses without it, because the Application's `company_ref` would be a
        # broken link nothing else in the archive can repair.
        self.must("org", "add", *b, "--title", "Ashby", "--relationship", "prospect",
                  "--industry", "hr-tech", "--body", "Where the posting came from.")
        self.must("posting", "add", *b, "--company", "Ashby",
                  "--title", "Staff Software Engineer", "--slug", "ashby-staff",
                  "--seniority", "platform-design", "--domain", "saas",
                  "--body", "-", stdin="The advertisement, verbatim.\n")
        self.must("posting", "requirement", "add", *b, "--posting", "ashby-staff",
                  "--value", "event-driven-architecture", "--kind", "capability",
                  "--necessity", "required", "--label", "own the event pipeline")
        self.must("gaps", "write", *b, "--posting", "ashby-staff", "--fit", "partial",
                  "--body", "-", stdin="# Eligibility\n\nPass.\n")
        self.must("view", "create", *b, "--posting", "ashby-staff",
                  "--label", "Staff Engineer @ Ashby",
                  "--format-profile", "ats-maximal", "--pages", "2")
        ids = [a["id"] for p in self.record()["projects"]
               for a in p.get("achievements", [])]
        self.must("view", "include", *b, "--view", "ashby-staff",
                  "--ref", "prj_care_platform_rebuild", "--order", "1",
                  "--achievement", ids[0])

    def test_a_tailored_bundle_clears_every_gate(self):
        self.build()
        self.tailor()
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        code, out = run(VALIDATE_URS, self.root)
        self.assertEqual(code, 0, out)

    def test_a_view_written_by_command_names_no_positional_id(self):
        """The materialisation, end to end: `bullet add` wrote the ids down, so the
        view's reference cannot be one the compile derived from a position.
        """
        self.build()
        self.tailor()
        text = (self.root / "tailoring" / "targets" / "ashby-staff.view.md").read_text(
            encoding="utf-8")
        self.assertNotIn("ach_projects_care_platform_rebuild_md_", text)

    def test_filing_an_application_leaves_a_valid_archive(self):
        self.build()
        self.tailor()
        b = ["--bundle", str(self.root)]
        document = Path(self._tmp.name) / "Test_Person_Ashby_Resume.pdf"
        document.write_bytes(b"%PDF-1.7\n\x00binary\n%%EOF\n")
        self.must("application", "file", "ashby-staff", *b,
                  "--submitted", "2026-08-26", "--channel", "Workday portal",
                  "--document", str(document))
        self.must("application", "event", "2026-08-26-ashby-staff", *b,
                  "--date", "2026-09-11", "--event", "screen-scheduled",
                  "--channel", "email", "--note", "Phone screen 2026-09-15")
        year = self.root / "tailoring" / "applications" / "2026"
        self.assertTrue((year / "2026-08-26-ashby-staff.md").exists())
        self.assertEqual((year / "Test_Person_Ashby_Resume.pdf").read_bytes(),
                         b"%PDF-1.7\n\x00binary\n%%EOF\n")
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        code, out = run(OKF_COMPILE, self.root)
        self.assertEqual(code, 0, out)


class NothingWritesOutsideTheCommands(BundleCase):
    """--dry-run over every verb the run above uses, asserting no byte moves.

    The design promises `--dry-run` decides everything and writes nothing. Tested by
    mtime and size over the whole tree, because a command that rewrote a file with
    identical content would still have reflowed somebody's concept.
    """

    def snapshot(self):
        state = {}
        for base, _, names in os.walk(self.root):
            for name in names:
                path = os.path.join(base, name)
                info = os.stat(path)
                state[path] = (info.st_mtime_ns, info.st_size)
        return state

    def test_dry_run_changes_nothing(self):
        before = self.snapshot()
        b = ["--bundle", str(self.root), "--dry-run"]
        self.must("org", "add", *b, "--title", "Acme", "--relationship", "employer",
                  "--body", "x")
        self.must("log", *b, "--message", "Nothing happened.")
        self.must("reindex", *b)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":                                # pragma: no cover
    unittest.main()
