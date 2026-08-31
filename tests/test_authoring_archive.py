"""`okf application file` and `okf application event` - the frozen archive.

Every test here pins a rule from bundle-spec.md's "Applications on disk" and "The
application timeline", or from mode-ship.md's "Freeze the archive". The one that
matters most is that `validate_bundle.py` exits 0 over the whole bundle after a
filing: the gate checks the archive's layout, the timeline, the event vocabulary
and every link, so a green gate is the assertion that the filing is *correct*
rather than merely present. Everything else here says which part would have been
wrong.
"""
import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from fixtures import (INIT_BUNDLE, OKF_COMPILE, PIPELINE, VALIDATE_BUNDLE,
                      authoring_module, run)

archive = authoring_module("authoring.archive")
common = authoring_module("authoring.common")
concept = authoring_module("authoring.concept")
stage = authoring_module("authoring.stage")


# --- a parser holding this module's verbs and nothing else -----------------------
#
# authoring.commands assembles five verb modules, and a fault in any of the other
# four would fail every test in this file on an ImportError that says nothing
# about the archive. So this builds the same parser over archive.register alone
# and runs the body main() runs, which keeps the argparse wiring - the positional,
# the defaults, the common flags - under test rather than bypassed.
# `TheWholeCli` below drives one filing through commands.main itself, so the
# assembled parser is covered too and this shortcut cannot hide a noun that never
# got registered.

def build_parser():
    parser = argparse.ArgumentParser(prog="okf")
    nouns = parser.add_subparsers(dest="noun", metavar="<noun>")
    archive.register(nouns)
    return parser


def okf(*argv):
    """One command, as main() runs it: (exit code, what it printed, the payload)."""
    args = build_parser().parse_args([str(item) for item in argv])
    out, err = io.StringIO(), io.StringIO()
    payload = None
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            payload = stage.commit(args.build(args), dry_run=args.dry_run)
        except (stage.Refused, concept.Unsplicable) as exc:
            print(f"FAIL  {exc}")
            return 1, out.getvalue() + err.getvalue(), None
        if args.json:
            print(json.dumps(payload, indent=2))
    return 0, out.getvalue() + err.getvalue(), payload


ORGANISATION = ("---\ntype: Organisation\ntitle: \"Acme Health\"\n"
                "description: \"Aged-care provider.\"\n"
                "timestamp: \"2026-01-01T00:00:00Z\"\nstatus: confirmed\n"
                "relationship: both\n---\n\n# People\n\nNobody yet.\n")

ROLE = ("---\ntype: Role\ntitle: \"Lead Engineer\"\n"
        "description: \"Owned the platform.\"\n"
        "timestamp: \"2026-01-01T00:00:00Z\"\nstatus: confirmed\n"
        "organisation: acme-health\nstart: 2019-04\nend: 2021-12\n"
        "state: ended\nseniority: team-leadership\n---\n\n# Notes\n\nWhat happened.\n")

PROJECT = ("---\ntype: Project\ntitle: \"Acme - care coordination platform\"\n"
           "description: \"Multi-tenant platform for aged-care providers.\"\n"
           "timestamp: \"2026-01-01T00:00:00Z\"\nstatus: confirmed\n"
           "role: lead-engineer\nstrength: 5\nrecency: 2026\n"
           "seniority: architecture-ownership\ndomains: [healthcare]\n"
           "capabilities: [ai-platform-architecture]\n---\n\n"
           "# The problem\n\nThe legacy scheduler could not express care plans.\n")

# The advertisement, with one relative link that leaves tailoring/targets/ and one
# frontmatter path that does the same. Both must gain exactly one `../`.
POSTING = ("---\ntype: Job Posting\ntitle: \"Acme - Senior Engineer\"\n"
           "description: \"Platform engineering, Melbourne.\"\n"
           "timestamp: \"2026-01-01T00:00:00Z\"\nstatus: confirmed\n"
           "company: \"Acme Health\"\nurl: \"https://acme.example/jobs/1\"\n"
           "resource: \"../../sources/acme-advertisement.md\"\n"
           "seniority: architecture-ownership\n"
           "requirements:\n"
           "  - value: ai-platform-architecture\n"
           "    kind: capability\n"
           "    necessity: required\n"
           "    label: \"Platform architecture at scale\"\n"
           "---\n\n"
           "# The advertisement\n\n"
           "Closest evidence is [the care platform](../../projects/care-platform.md),\n"
           "and the advertisement itself is at <https://acme.example/jobs/1>.\n")

GAPS = ("---\ntype: Gap Assessment\ntitle: \"Acme - Senior Engineer: gaps\"\n"
        "description: \"Where the record falls short of the posting.\"\n"
        "timestamp: \"2026-01-01T00:00:00Z\"\nstatus: inferred\n"
        "posting: acme-engineer\nassessed: 2026-08-20\nfit: strong\n---\n\n"
        "# Gaps\n\nNo Terraform evidence. See "
        "[the platform](../../projects/care-platform.md).\n")

# `target.ref` names the posting sitting beside it. That reference does not leave
# the directory, the three companions move together, and it must come out of the
# freeze exactly as it went in.
VIEW = ("---\ntype: View\ntitle: \"Acme - Senior Engineer: view\"\n"
        "description: \"What this application selected.\"\n"
        "timestamp: \"2026-01-01T00:00:00Z\"\nstatus: confirmed\n"
        "id: view_acme\nformat_profile: ats-maximal\n"
        "target:\n  title: \"Acme - Senior Engineer\"\n"
        "  ref: \"acme-engineer.posting.md\"\n"
        "provenance_floor: confirmed\n---\n\n"
        "# Notes\n\nThe selection this application rendered from.\n")

# A PDF as far as anything reading it is concerned: a header, a null byte and a
# high byte. Through text mode any one of the three is corrupted or refused, in
# the one directory whose whole purpose is to hold what was actually sent.
BINARY = b"%PDF-1.7\r\n1 0 obj\x00\xff\xfe binary \x0c\ntrailer\n%%EOF\n"


class ArchiveCase(unittest.TestCase):
    """A scaffolded bundle with a company, a role, a project and one answered target."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)
        self.write("organisations/acme-health.md", ORGANISATION)
        self.write("roles/lead-engineer.md", ROLE)
        self.write("projects/care-platform.md", PROJECT)
        self.write("sources/acme-advertisement.md",
                   "---\ntype: Source\ntitle: \"The advertisement\"\n"
                   "description: \"As posted.\"\n"
                   "timestamp: \"2026-01-01T00:00:00Z\"\n---\n\n"
                   "# Text\n\nAs posted.\n")
        self.write("tailoring/targets/acme-engineer.posting.md", POSTING)
        self.write("tailoring/targets/acme-engineer.gaps.md", GAPS)
        self.write("tailoring/targets/acme-engineer.view.md", VIEW)
        self.documents = Path(self._tmp.name) / "out"
        self.documents.mkdir()
        self.pdf = self.documents / "Test_Person_Acme_Resume.pdf"
        self.pdf.write_bytes(BINARY)

    # --- the bundle ------------------------------------------------------------

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read(self, relative):
        return (self.root / relative).read_text(encoding="utf-8")

    def meta(self, relative):
        return concept.read(str(self.root / relative)).meta

    def snapshot(self):
        """Every file in the bundle: relative path -> (bytes, mtime)."""
        out = {}
        for dirpath, _, filenames in os.walk(self.root):
            for name in filenames:
                path = Path(dirpath) / name
                out[str(path.relative_to(self.root))] = (path.read_bytes(),
                                                         path.stat().st_mtime_ns)
        return out

    # --- the verbs -------------------------------------------------------------

    def file_it(self, *extra, slug="acme-engineer"):
        return okf("application", "file", slug, "--bundle", self.root, *extra)

    def event(self, *extra, stem="2026-08-26-acme-engineer"):
        return okf("application", "event", stem, "--bundle", self.root, *extra)

    def filed(self, *extra):
        """A complete filing on a fixed date, so every path in a test is nameable."""
        code, out, payload = self.file_it("--submitted", "2026-08-26",
                                          "--channel", "Workday portal", *extra)
        self.assertEqual(code, 0, out)
        return payload

    def year(self, name):
        return f"tailoring/applications/2026/{name}"

    def assert_gate_is_clean(self):
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("VALID", out)

    def assert_compile_is_clean(self):
        code, out = run(OKF_COMPILE, self.root)
        self.assertEqual(code, 0, out)


class Filing(ArchiveCase):
    """`application file` - the enumerated-by-hand procedure, as one command."""

    STEM = "2026-08-26-acme-engineer"

    def test_the_four_markdown_files_land_in_the_year_directory(self):
        self.filed()
        for name in (f"{self.STEM}.md", f"{self.STEM}.posting.md",
                     f"{self.STEM}.gaps.md", f"{self.STEM}.view.md", "index.md"):
            with self.subTest(name=name):
                self.assertTrue((self.root / self.year(name)).exists(), name)

    def test_each_copy_is_frozen_with_the_submission_date(self):
        # mode-ship.md: the freeze is what makes the archive answerable. A copy
        # that is not frozen is a copy somebody can still edit, and then the
        # application no longer says what it was answering.
        self.filed()
        for suffix in (".posting.md", ".gaps.md", ".view.md"):
            with self.subTest(suffix=suffix):
                meta = self.meta(self.year(f"{self.STEM}{suffix}"))
                self.assertIs(meta["frozen"], True)
                self.assertEqual(str(meta["frozen_date"]), "2026-08-26")

    def test_the_working_copies_are_untouched(self):
        """The whole point of a freeze: targets/ stays editable and unchanged."""
        before = {name: (self.root / "tailoring" / "targets" / name).read_bytes()
                  for name in ("acme-engineer.posting.md", "acme-engineer.gaps.md",
                               "acme-engineer.view.md")}
        self.filed()
        for name, was in before.items():
            with self.subTest(name=name):
                self.assertEqual(
                    (self.root / "tailoring" / "targets" / name).read_bytes(), was)

    def test_a_body_link_that_leaves_the_directory_gains_one_dot_dot(self):
        self.filed()
        text = self.read(self.year(f"{self.STEM}.posting.md"))
        self.assertIn("(../../../projects/care-platform.md)", text)
        self.assertNotIn("(../../projects/care-platform.md)", text)

    def test_a_frontmatter_path_that_leaves_the_directory_gains_one_dot_dot(self):
        self.filed()
        meta = self.meta(self.year(f"{self.STEM}.posting.md"))
        self.assertEqual(meta["resource"], "../../../sources/acme-advertisement.md")

    def test_a_sibling_reference_does_not_change(self):
        """The companions move together and keep sharing a stem, so a reference
        that never left the directory was already right."""
        self.filed()
        meta = self.meta(self.year(f"{self.STEM}.view.md"))
        self.assertEqual(meta["target"]["ref"], "acme-engineer.posting.md")

    def test_a_url_in_the_advertisement_is_left_alone(self):
        self.filed()
        text = self.read(self.year(f"{self.STEM}.posting.md"))
        self.assertIn("https://acme.example/jobs/1", text)
        self.assertNotIn("../https", text)

    def test_every_rewritten_path_resolves_from_where_the_copy_now_sits(self):
        """The arithmetic, checked against the filesystem rather than the string."""
        self.filed()
        here = self.root / "tailoring" / "applications" / "2026"
        meta = self.meta(self.year(f"{self.STEM}.md"))
        for key in ("target_working_copy", "company_ref", "posting", "assessment",
                    "view_file"):
            with self.subTest(key=key):
                self.assertTrue(os.path.exists(os.path.normpath(
                    os.path.join(str(here), meta[key]))), meta[key])

    def test_the_application_frontmatter_is_the_shape_the_format_gives(self):
        self.filed()
        meta = self.meta(self.year(f"{self.STEM}.md"))
        self.assertEqual(meta["type"], "Application")
        self.assertEqual(meta["posting"], f"{self.STEM}.posting.md")
        self.assertEqual(meta["assessment"], f"{self.STEM}.gaps.md")
        self.assertEqual(meta["view_file"], f"{self.STEM}.view.md")
        self.assertEqual(meta["target_working_copy"],
                         "../../targets/acme-engineer.posting.md")
        self.assertEqual(meta["company_ref"],
                         "../../../organisations/acme-health.md")
        self.assertEqual(meta["company"], "Acme Health")
        self.assertEqual(meta["channel"], "Workday portal")
        self.assertEqual(str(meta["submitted"]), "2026-08-26")

    def test_there_is_no_outcome_key(self):
        """bundle-spec.md refuses one by design: a status word and the prose
        beneath it stop agreeing the moment one is edited."""
        self.filed()
        self.assertNotIn("outcome", self.meta(self.year(f"{self.STEM}.md")))

    def test_the_view_id_is_read_out_of_the_view(self):
        payload = self.filed()
        self.assertEqual(self.meta(self.year(f"{self.STEM}.md"))["view"], "view_acme")
        self.assertEqual(payload["ids"]["view"], "view_acme")

    def test_an_undeclared_view_id_is_derived_the_way_the_compile_derives_it(self):
        # okf_compile.build_views defaults an absent id to view_<slug(stem)> over
        # the file's own stem, `.view` included.
        text = self.read("tailoring/targets/acme-engineer.view.md")
        self.write("tailoring/targets/acme-engineer.view.md",
                   text.replace("id: view_acme\n", ""))
        self.filed()
        self.assertEqual(self.meta(self.year(f"{self.STEM}.md"))["view"],
                         "view_acme_engineer_view")

    def test_the_timeline_opens_with_the_submitted_row(self):
        self.filed("--note", "ATS variant uploaded")
        body = concept.read(str(self.root / self.year(f"{self.STEM}.md"))).body
        self.assertIn("# Timeline", body)
        self.assertIn("| 2026-08-26 | submitted | Workday portal | "
                      "ATS variant uploaded | |", body)

    def test_the_year_index_and_the_archive_index_both_list_it(self):
        self.filed()
        self.assertIn(f"({self.STEM}.md)", self.read(self.year("index.md")))
        self.assertIn("(2026/index.md)",
                      self.read("tailoring/applications/index.md"))

    def test_a_second_filing_that_year_joins_the_index_that_is_there(self):
        self.filed()
        self.write("tailoring/targets/globex-lead.posting.md",
                   POSTING.replace("Acme - Senior Engineer", "Globex - Lead"))
        self.write("tailoring/targets/globex-lead.gaps.md",
                   GAPS.replace("posting: acme-engineer", "posting: globex-lead"))
        self.write("tailoring/targets/globex-lead.view.md",
                   VIEW.replace("id: view_acme", "id: view_globex")
                       .replace("acme-engineer.posting.md",
                                "globex-lead.posting.md"))
        code, out, _ = self.file_it("--submitted", "2026-09-01", slug="globex-lead")
        self.assertEqual(code, 0, out)
        index = self.read(self.year("index.md"))
        self.assertIn(f"({self.STEM}.md)", index)
        self.assertIn("(2026-09-01-globex-lead.md)", index)
        # One row for the year, not two.
        self.assertEqual(
            self.read("tailoring/applications/index.md").count("(2026/index.md)"), 1)

    def test_the_log_records_the_filing(self):
        self.filed()
        self.assertIn("Filed tailoring/applications/2026/"
                      f"{self.STEM}.md", self.read("log.md"))

    def test_the_bundle_gate_is_clean_afterwards(self):
        """The assertion that proves the filing is right: the gate checks the
        archive's layout, the timeline, the event vocabulary and every link."""
        self.filed("--document", self.pdf)
        self.assert_gate_is_clean()

    def test_the_compile_still_runs_and_the_archive_stays_out_of_the_record(self):
        # The frozen `.view.md` declares the same view id as the live copy it was
        # made from, and the archived one used to shadow it - so a tailoring run
        # rendered last quarter's selection from this quarter's record. One id in
        # the record, from tailoring/targets/, is what says that is gone.
        self.filed()
        self.assert_compile_is_clean()
        code, out = run(OKF_COMPILE, self.root, "--dump-record", "-", "--quiet")
        self.assertEqual(code, 0, out)
        self.assertEqual([view["id"] for view in json.loads(out)["views"]],
                         ["view_acme"])

    def test_pipeline_groups_the_filing_under_its_company(self):
        """The reason `company:` is written at all. pipeline.py reads it off the
        Application's own frontmatter and falls back to `title`, so a filing that
        left it out was groupable only by accident of what its title said."""
        self.filed()
        code, out = run(PIPELINE, self.root, "--company", "Acme Health")
        self.assertEqual(code, 0, out)
        self.assertIn("2026-08-26-acme-engineer", out)
        self.assertNotIn("no applications to a company matching", out)

    def test_json_names_every_file_written_and_every_id(self):
        code, out, payload = self.file_it("--submitted", "2026-08-26",
                                          "--channel", "email",
                                          "--document", self.pdf, "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["ids"], payload["ids"])
        self.assertEqual(payload["ids"]["application"], self.STEM)
        self.assertEqual(payload["ids"]["year"], "2026")
        wrote = {os.path.basename(path) for path in payload["changed"]}
        self.assertLessEqual({f"{self.STEM}.md", f"{self.STEM}.posting.md",
                              f"{self.STEM}.gaps.md", f"{self.STEM}.view.md",
                              "Test_Person_Acme_Resume.pdf", "index.md", "log.md"},
                             wrote)


class Documents(ArchiveCase):
    """`--document` - the files actually sent, byte for byte."""

    STEM = "2026-08-26-acme-engineer"

    def test_a_binary_document_is_copied_byte_for_byte(self):
        # change.copy rather than a text write. A PDF through text mode is
        # corrupted silently, in the one directory whose whole purpose is to hold
        # what was sent.
        self.filed("--document", self.pdf)
        self.assertEqual(
            (self.root / self.year("Test_Person_Acme_Resume.pdf")).read_bytes(),
            BINARY)

    def test_the_application_links_to_what_was_sent(self):
        # migrate_bundle.attribute reads exactly this - "a link in the
        # application's log" - to work out which application a loose document
        # belongs to, and these copies keep the name they were sent under.
        self.filed("--document", self.pdf)
        body = concept.read(str(self.root / self.year(f"{self.STEM}.md"))).body
        self.assertIn("[Test_Person_Acme_Resume.pdf](Test_Person_Acme_Resume.pdf)",
                      body)
        self.assert_gate_is_clean()

    def test_a_filename_no_plain_link_can_carry_is_recorded_in_backticks(self):
        # validate_bundle.py strips inline code before it checks links, so a name
        # holding a space is recorded in the one form that cannot become a broken
        # link in the file whose findings are errors rather than warnings.
        spaced = self.documents / "Test Person Resume.pdf"
        spaced.write_bytes(BINARY)
        self.filed("--document", spaced)
        body = concept.read(str(self.root / self.year(f"{self.STEM}.md"))).body
        self.assertIn("`Test Person Resume.pdf`", body)
        self.assertNotIn("](Test Person Resume.pdf)", body)
        self.assert_gate_is_clean()

    def test_two_documents_with_one_filename_are_refused(self):
        other = self.documents / "second"
        other.mkdir()
        (other / "Test_Person_Acme_Resume.pdf").write_bytes(BINARY)
        code, out, _ = self.file_it("--submitted", "2026-08-26", "--document",
                                    self.pdf, "--document",
                                    other / "Test_Person_Acme_Resume.pdf")
        self.assertEqual(code, 1, out)
        self.assertIn("share the filename", out)

    def test_a_document_landing_on_one_of_the_archive_files_is_refused(self):
        clash = self.documents / f"{self.STEM}.gaps.md"
        clash.write_bytes(b"not the assessment\n")
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--document", clash)
        self.assertEqual(code, 1, out)
        self.assertIn("which this filing already writes", out)

    def test_a_document_over_one_already_filed_is_refused(self):
        self.filed("--document", self.pdf)
        self.write("tailoring/targets/globex-lead.posting.md", POSTING)
        self.write("tailoring/targets/globex-lead.gaps.md",
                   GAPS.replace("posting: acme-engineer", "posting: globex-lead"))
        self.write("tailoring/targets/globex-lead.view.md",
                   VIEW.replace("id: view_acme", "id: view_globex"))
        code, out, _ = self.file_it("--submitted", "2026-09-01", "--document",
                                   self.pdf, slug="globex-lead")
        self.assertEqual(code, 1, out)
        self.assertIn("already there", out)

    def test_a_document_that_is_not_there_is_refused_before_anything_is_written(self):
        code, out, _ = self.file_it("--submitted", "2026-08-26", "--document",
                                    self.documents / "nothing.pdf")
        self.assertEqual(code, 1, out)
        self.assertFalse((self.root / "tailoring" / "applications" / "2026").exists())


class HeldBack(ArchiveCase):
    """bundle-spec.md's one exemption: an application worked through and not sent."""

    def stem(self):
        return f"{common.today()}-acme-engineer"

    def test_submitted_false_is_written_and_no_submitted_row_is(self):
        # Never a `submitted` row to clear the validator error: it trades an
        # accurate red for a false green, and every stage derived from that
        # timeline afterwards is wrong.
        code, out, _ = self.file_it("--held-back")
        self.assertEqual(code, 0, out)
        path = f"tailoring/applications/{common.today()[:4]}/{self.stem()}.md"
        doc = concept.read(str(self.root / path))
        self.assertIs(doc.meta["submitted"], False)
        self.assertNotIn("| submitted |", doc.body)
        self.assertIn("| note |", doc.body)

    def test_the_gate_is_clean_with_no_submitted_row(self):
        code, out, _ = self.file_it("--submitted", "false")
        self.assertEqual(code, 0, out)
        self.assert_gate_is_clean()

    def test_a_channel_is_refused_because_nothing_was_sent(self):
        code, out, _ = self.file_it("--held-back", "--channel", "email")
        self.assertEqual(code, 1, out)
        self.assertIn("was not sent through one", out)

    def test_a_date_and_held_back_together_are_refused(self):
        code, out, _ = self.file_it("--held-back", "--submitted", "2026-08-26")
        self.assertEqual(code, 1, out)
        self.assertIn("drop one", out)


class FilingRefusals(ArchiveCase):
    """The refusals are the product. Every row of them, with its named cause."""

    def test_a_year_that_cannot_be_established_is_refused(self):
        for given, cause in (("unknown", "cannot be established"),
                             ("2026", "not a whole day"),
                             ("2026-08", "not a whole day"),
                             ("last tuesday", "not a whole day")):
            with self.subTest(given=given):
                code, out, _ = self.file_it("--submitted", given)
                self.assertEqual(code, 1, out)
                self.assertIn(cause, out)
                self.assertFalse((self.root / "tailoring" / "applications"
                                  / "2026").exists())

    def test_a_missing_working_file_is_refused_by_name(self):
        (self.root / "tailoring" / "targets" / "acme-engineer.gaps.md").unlink()
        code, out, _ = self.file_it("--submitted", "2026-08-26")
        self.assertEqual(code, 1, out)
        self.assertIn("acme-engineer.gaps.md is not there", out)

    def test_every_missing_working_file_is_named_at_once(self):
        for name in ("acme-engineer.gaps.md", "acme-engineer.view.md"):
            (self.root / "tailoring" / "targets" / name).unlink()
        code, out, _ = self.file_it("--submitted", "2026-08-26")
        self.assertEqual(code, 1, out)
        self.assertIn("acme-engineer.gaps.md and acme-engineer.view.md are not "
                      "there", out)

    def test_a_stem_already_filed_under_that_date_is_refused(self):
        """A second round at the same posting is ordinary - that is what the date
        in the stem is for - but overwriting the first is not."""
        self.filed()
        code, out, _ = self.file_it("--submitted", "2026-08-26")
        self.assertEqual(code, 1, out)
        self.assertIn("are already there", out)
        self.assertIn("okf application event", out)

    def test_a_second_round_on_another_date_is_allowed(self):
        self.filed()
        code, out, _ = self.file_it("--submitted", "2027-01-11")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / "tailoring" / "applications" / "2027"
                         / "2027-01-11-acme-engineer.md").exists())
        self.assert_gate_is_clean()

    def test_a_company_with_no_concept_is_refused(self):
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--company", "no-such-company")
        self.assertEqual(code, 1, out)
        self.assertIn("no such organisation", out)

    def test_a_posting_with_no_company_and_no_flag_is_refused(self):
        self.write("tailoring/targets/acme-engineer.posting.md",
                   POSTING.replace("company: \"Acme Health\"\n", ""))
        code, out, _ = self.file_it("--submitted", "2026-08-26")
        self.assertEqual(code, 1, out)
        self.assertIn("company_ref` cannot be derived", out)

    def test_the_flag_overrides_the_company_derived_from_the_posting(self):
        # The default is the posting's own `company:`, slugged - `Acme Health`
        # becomes `acme-health`. A bundle whose concept is filed under another
        # stem says so with the flag rather than being asked to rename the file.
        self.write("organisations/acme-group.md", ORGANISATION)
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--company", "acme-group")
        self.assertEqual(code, 0, out)
        meta = self.meta(self.year("2026-08-26-acme-engineer.md"))
        self.assertEqual(meta["company_ref"],
                         "../../../organisations/acme-group.md")
        # The flag renames the file the link points at; it does not rename the
        # employer. The posting said who that was and still does.
        self.assertEqual(meta["company"], "Acme Health")

    def test_the_company_name_falls_back_to_the_organisations_own_title(self):
        # `--company <stem>` against a posting that names no employer. Without
        # this the key would be absent and `pipeline --company` would be matching
        # on whatever happens to be in the application's title.
        self.write("tailoring/targets/acme-engineer.posting.md",
                   POSTING.replace("company: \"Acme Health\"\n", ""))
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--company", "acme-health")
        self.assertEqual(code, 0, out)
        self.assertEqual(
            self.meta(self.year("2026-08-26-acme-engineer.md"))["company"],
            "Acme Health")

    def test_a_set_company_is_refused_because_the_command_stamps_it(self):
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--set", "company=Ashby")
        self.assertEqual(code, 1, out)
        self.assertIn("this command stamps it itself", out)

    def test_a_set_role_is_written_because_nothing_else_carries_one(self):
        # A Job Posting has a title and a seniority and no role key, so `--set`
        # is the only source for the second column of pipeline.py's board. The
        # schema models the key, so this is checked rather than merely tolerated.
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--set", "role=Senior Engineer")
        self.assertEqual(code, 0, out)
        self.assertEqual(
            self.meta(self.year("2026-08-26-acme-engineer.md"))["role"],
            "Senior Engineer")

    def test_a_view_of_another_type_is_refused(self):
        self.write("tailoring/targets/acme-engineer.view.md",
                   VIEW.replace("type: View", "type: Project"))
        code, out, _ = self.file_it("--submitted", "2026-08-26")
        self.assertEqual(code, 1, out)
        self.assertIn("not View", out)

    def test_a_slug_naming_a_path_is_refused(self):
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    slug="../../etc/passwd")
        self.assertEqual(code, 1, out)
        self.assertIn("not a path", out)

    def test_a_bundle_that_is_not_one_is_refused(self):
        code, out, _ = okf("application", "file", "acme-engineer",
                           "--bundle", self.documents)
        self.assertEqual(code, 1, out)
        self.assertIn("not a bundle", out)

    def test_a_set_naming_a_key_the_command_owns_is_refused(self):
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--set", "channel=email")
        self.assertEqual(code, 1, out)
        self.assertIn("is not an extension key", out)

    def test_an_extension_key_is_written(self):
        code, out, _ = self.file_it("--submitted", "2026-08-26",
                                    "--set", "requisition=R-4417")
        self.assertEqual(code, 0, out)
        self.assertEqual(
            self.meta(self.year("2026-08-26-acme-engineer.md"))["requisition"],
            "R-4417")


class DryRun(ArchiveCase):
    """The flag most worth testing here, because this verb touches the most files."""

    def test_a_dry_run_decides_everything_and_writes_nothing(self):
        before = self.snapshot()
        code, out, payload = self.file_it("--submitted", "2026-08-26",
                                         "--channel", "Workday portal",
                                         "--document", self.pdf, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(self.snapshot(), before)

    def test_a_dry_run_does_not_even_make_the_year_directory(self):
        # stage.commit creates each target's parent as part of the transaction, so
        # the year directory comes into existence with the files that land in it
        # and this verb arranges nothing itself.
        self.file_it("--submitted", "2026-08-26", "--dry-run")
        self.assertFalse((self.root / "tailoring" / "applications" / "2026").exists())

    def test_a_dry_run_names_the_files_it_would_have_written(self):
        _, _, payload = self.file_it("--submitted", "2026-08-26",
                                     "--document", self.pdf, "--dry-run")
        names = {os.path.basename(path) for path in payload["changed"]}
        self.assertIn("2026-08-26-acme-engineer.md", names)
        self.assertIn("Test_Person_Acme_Resume.pdf", names)

    def test_a_dry_run_still_makes_every_refusal(self):
        code, out, _ = self.file_it("--submitted", "unknown", "--dry-run")
        self.assertEqual(code, 1, out)

    def test_a_dry_run_of_an_event_writes_nothing(self):
        self.filed()
        before = self.snapshot()
        code, out, _ = self.event("--event", "acknowledged", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.snapshot(), before)


class Events(ArchiveCase):
    """`application event` - append only, never edit."""

    STEM = "2026-08-26-acme-engineer"

    def setUp(self):
        super().setUp()
        self.filed()
        self.path = self.root / self.year(f"{self.STEM}.md")

    def body(self):
        return concept.read(str(self.path)).body

    def test_a_row_is_appended_with_every_column(self):
        code, out, _ = self.event("--event", "screen-scheduled",
                                  "--date", "2026-09-11", "--channel", "email",
                                  "--note", "Phone screen, 30 min",
                                  "--due", "2026-09-15")
        self.assertEqual(code, 0, out)
        self.assertIn("| 2026-09-11 | screen-scheduled | email | "
                      "Phone screen, 30 min | 2026-09-15 |", self.body())

    def test_the_row_goes_below_the_one_that_was_there(self):
        self.event("--event", "acknowledged", "--date", "2026-08-27")
        self.event("--event", "screen-done", "--date", "2026-09-15")
        rows = [line for line in self.body().split("\n")
                if line.startswith("| 2026")]
        self.assertEqual([row.split("|")[2].strip() for row in rows],
                         ["submitted", "acknowledged", "screen-done"])

    def test_the_frontmatter_keeps_its_own_bytes(self):
        was = self.path.read_bytes().split(b"---", 2)[1]
        self.event("--event", "acknowledged")
        self.assertEqual(self.path.read_bytes().split(b"---", 2)[1], was)

    def test_the_gate_and_the_compile_are_clean_afterwards(self):
        self.event("--event", "screen-scheduled", "--date", "2026-09-11",
                   "--due", "2026-09-15")
        self.event("--event", "rejected", "--date", "2026-09-20")
        self.assert_gate_is_clean()
        self.assert_compile_is_clean()

    def test_the_log_records_the_event(self):
        self.event("--event", "acknowledged", "--date", "2026-08-27")
        self.assertIn(f"Logged acknowledged on tailoring/applications/2026/"
                      f"{self.STEM}.md", self.read("log.md"))

    def test_json_names_the_file_and_the_event(self):
        code, out, payload = self.event("--event", "offer", "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(payload["ids"], {"application": self.STEM,
                                          "event": "offer"})
        self.assertEqual(json.loads(out)["ids"]["event"], "offer")

    def test_a_stem_is_found_without_the_caller_naming_the_year(self):
        code, out, _ = self.event("--event", "acknowledged",
                                  stem=f"{self.STEM}.md")
        self.assertEqual(code, 0, out)

    def test_the_timeline_is_written_when_the_section_is_absent(self):
        """An Application with no `# Timeline` is already a validate_bundle.py
        error, so writing the section is the repair rather than a refusal."""
        doc = concept.read(str(self.path))
        doc.body = "# Notes\n\nNothing yet.\n"
        # newline="" because doc.text() has already put the file's own convention
        # back, and text mode on Windows would translate it a second time.
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write(doc.text())
        code, out, _ = self.event("--event", "acknowledged", "--date", "2026-08-27")
        self.assertEqual(code, 0, out)
        self.assertIn("# Timeline", self.body())
        self.assertIn("| 2026-08-27 | acknowledged |", self.body())
        # The gate is not asserted here: replacing the body threw away the
        # `submitted` row, and the point of this test is the section, not a green
        # bundle. pipeline_model reading the new row back is what matters.
        rows = archive._model().parse_timeline(self.body())
        self.assertEqual([row.event for row in rows], ["acknowledged"])
        self.assertIn("# Notes", self.body())


class EventRefusals(ArchiveCase):
    STEM = "2026-08-26-acme-engineer"

    def setUp(self):
        super().setUp()
        self.filed()

    def test_an_event_outside_the_vocabulary_is_refused(self):
        for given in ("phone-screen", "Submitted", "rejection"):
            with self.subTest(given=given):
                code, out, _ = self.event("--event", given)
                self.assertEqual(code, 1, out)
                self.assertIn("is not in framework/pipeline-vocabulary.md", out)
                self.assertIn("a row that stops counting", out)

    def test_a_vocabulary_that_lists_nothing_falls_back_to_the_model(self):
        # validate_bundle.py switches its own check off on an empty vocabulary.
        # pipeline_model.py is still the module allowed to decide what an event
        # signifies, so a row nothing can compute a stage from is still refused.
        (self.root / "framework" / "pipeline-vocabulary.md").write_text(
            "---\ntype: Vocabulary\ntitle: \"Pipeline vocabulary\"\n"
            "timestamp: \"2026-01-01T00:00:00Z\"\n---\n\nNothing listed.\n",
            encoding="utf-8")
        code, out, _ = self.event("--event", "acknowledged")
        self.assertEqual(code, 0, out)
        code, out, _ = self.event("--event", "phone-screen")
        self.assertEqual(code, 1, out)
        self.assertIn("lists nothing", out)

    def test_a_date_that_is_not_a_date_is_refused(self):
        for flag, given in (("--date", "26-08-2026"), ("--date", "2026-08"),
                            ("--due", "next tuesday"), ("--due", "2026-8-1")):
            with self.subTest(flag=flag, given=given):
                code, out, _ = self.event("--event", "note", flag, given)
                self.assertEqual(code, 1, out)
                self.assertIn("not a date", out)

    def test_unknown_is_a_legitimate_date(self):
        code, out, _ = self.event("--event", "note", "--date", "unknown",
                                  "--note", "A migration could not date this")
        self.assertEqual(code, 0, out)
        self.assert_gate_is_clean()

    def test_a_pipe_in_a_cell_is_refused(self):
        code, out, _ = self.event("--event", "note", "--note", "they said a | b")
        self.assertEqual(code, 1, out)
        self.assertIn("column separator", out)

    def test_a_stem_that_is_not_filed_is_refused(self):
        code, out, _ = self.event("--event", "note", stem="2026-01-01-nobody")
        self.assertEqual(code, 1, out)
        self.assertIn("no application with that stem", out)

    def test_a_stem_that_is_not_an_application_is_refused(self):
        code, out, _ = self.event("--event", "note",
                                  stem=f"{self.STEM}.posting")
        self.assertEqual(code, 1, out)
        self.assertIn("not Application", out)

    def test_an_ambiguous_stem_is_refused(self):
        twin = self.root / "tailoring" / "applications" / "2027"
        twin.mkdir()
        (twin / f"{self.STEM}.md").write_text(
            self.read(self.year(f"{self.STEM}.md")), encoding="utf-8")
        code, out, _ = self.event("--event", "note")
        self.assertEqual(code, 1, out)
        self.assertIn("filed more than once", out)

    def test_a_set_is_refused_because_a_row_is_not_a_key(self):
        code, out, _ = self.event("--event", "note", "--set", "anything=1")
        self.assertEqual(code, 1, out)
        self.assertIn("an event is a row, not a key", out)


class EventWarnings(ArchiveCase):
    """Both of these warn in validate_bundle.py and must not fail here: refusing
    would block a legitimate backfill or a genuinely reopened process."""

    STEM = "2026-08-26-acme-engineer"

    def setUp(self):
        super().setUp()
        self.filed()

    def test_a_row_dated_before_the_one_above_it_warns_and_is_written(self):
        code, out, _ = self.event("--event", "recruiter-contact",
                                  "--date", "2026-08-20")
        self.assertEqual(code, 0, out)
        self.assertIn("dated before the row above it", out)
        self.assertIn("| 2026-08-20 | recruiter-contact |",
                      concept.read(str(self.root / self.year(f"{self.STEM}.md"))).body)

    def test_an_advancing_event_after_a_terminal_one_warns_and_is_written(self):
        self.event("--event", "rejected", "--date", "2026-09-01")
        code, out, _ = self.event("--event", "interview-scheduled",
                                  "--date", "2026-10-01", "--due", "2026-10-08")
        self.assertEqual(code, 0, out)
        self.assertIn("follows", out)
        self.assertIn("reopened process", out)
        self.assert_gate_is_clean()

    def test_a_warning_does_not_reach_the_json_payload_on_stdout(self):
        # --json's stdout has to stay parseable, so a warning goes to stderr.
        args = build_parser().parse_args(
            ["application", "event", self.STEM, "--bundle", str(self.root),
             "--event", "recruiter-contact", "--date", "2026-08-20", "--json"])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            payload = stage.commit(args.build(args), dry_run=False)
            print(json.dumps(payload, indent=2))
        self.assertIn("dated before", err.getvalue())
        self.assertEqual(json.loads(out.getvalue())["ids"]["event"],
                         "recruiter-contact")


class PathArithmetic(unittest.TestCase):
    """`deeper` and `deepened`, over the shapes a real target directory holds."""

    def test_a_reference_that_leaves_the_directory_gains_one_dot_dot(self):
        for target, expected in (
                ("../targets/x.md", "../../targets/x.md"),
                ("../../projects/care-platform.md",
                 "../../../projects/care-platform.md"),
                ("../../../organisations/acme.md",
                 "../../../../organisations/acme.md"),
                ("..", "../.."),
                ("../../projects/x.md#metrics", "../../../projects/x.md#metrics")):
            with self.subTest(target=target):
                self.assertEqual(archive.deeper(target), expected)

    def test_everything_that_stays_put_is_left_alone(self):
        for target in ("x.md", "./x.md", "acme-engineer.posting.md",
                       "sub/x.md", "https://example.com/a", "http://a/b",
                       "mailto:a@b.c", "#anchor", "/absolute.md", "",
                       "urs:profile:au/1"):
            with self.subTest(target=target):
                self.assertIsNone(archive.deeper(target))

    def test_the_arithmetic_agrees_with_the_filesystem(self):
        """One `../` is right because applications/<yyyy>/ is exactly one segment
        deeper than targets/ and both resolve through tailoring/."""
        old, new = "tailoring/targets", "tailoring/applications/2026"
        for target in ("../targets/x.md", "../../projects/x.md",
                       "../../../organisations/acme.md"):
            with self.subTest(target=target):
                self.assertEqual(
                    os.path.normpath(os.path.join(old, target)),
                    os.path.normpath(os.path.join(new, archive.deeper(target))))

    def test_a_nested_frontmatter_path_is_rewritten(self):
        text = ("---\ntype: View\nid: view_x\n"
                "target:\n  title: \"A job\"\n  ref: \"../../sources/ad.md\"\n"
                "---\n\nbody\n")
        out = archive.deepened(text, "x.view.md")
        self.assertIn("  ref: \"../../../sources/ad.md\"", out)

    def test_a_quoted_value_keeps_its_quotes_and_a_comment_survives(self):
        text = ("---\ntype: View\nid: view_x\n"
                "resource: '../../sources/ad.md'   # where it came from\n"
                "---\n\nbody\n")
        out = archive.deepened(text, "x.view.md")
        self.assertIn("resource: '../../../sources/ad.md'   # where it came from",
                      out)

    def test_a_link_whose_label_is_its_own_path_is_rewritten_on_both_sides(self):
        text = "---\ntype: View\n---\n\n[../../x.md](../../x.md)\n"
        self.assertIn("[../../../x.md](../../../x.md)",
                      archive.deepened(text, "x.view.md"))

    def test_the_line_convention_survives(self):
        # A bundle scaffolded on Windows is entirely CRLF, so this is the common
        # case: a copy rewritten in LF would be the one file in the archive that
        # disagrees with the rest of the bundle.
        text = "---\r\ntype: View\r\nid: view_x\r\n---\r\n\r\n[a](../../x.md)\r\n"
        out = archive.deepened(text, "x.view.md")
        self.assertIn("[a](../../../x.md)", out)
        self.assertEqual(out.count("\r\n"), text.count("\r\n"))
        self.assertEqual(out.count("\n"), out.count("\r\n"))

    def test_a_file_with_nothing_to_rewrite_comes_back_byte_for_byte(self):
        text = ("---\ntype: Job Posting\ntitle: \"A job\"\n---\n\n"
                "# The advertisement\n\nSee [the sibling](x.posting.md).\n")
        self.assertEqual(archive.deepened(text, "x.gaps.md"), text)


class Rows(unittest.TestCase):
    """The row appender, which is local to this module rather than in body.py."""

    def test_a_row_is_written_in_the_formats_own_spacing(self):
        self.assertEqual(
            archive.row("2026-08-26", "submitted", "Workday", "A note", ""),
            "| 2026-08-26 | submitted | Workday | A note | |")

    def test_an_empty_cell_is_one_space(self):
        self.assertEqual(archive.row("2026-08-26", "note", "", "", ""),
                         "| 2026-08-26 | note | | | |")

    def test_every_row_this_module_writes_reads_back_as_one_row(self):
        model = archive._model()
        for note in ("A note", "", "two   spaces", "a - b", "café"):
            with self.subTest(note=note):
                text = ("# Timeline\n\n%s\n%s\n%s\n"
                        % (archive.HEADER[0], archive.HEADER[1],
                           archive.row("2026-08-26", "submitted", "email",
                                       archive.cell(note, "--note"), "")))
                rows = model.parse_timeline(text)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].event, "submitted")
                self.assertEqual(rows[0].note, " ".join(note.split()))

    def test_a_row_joins_the_table_that_is_there(self):
        text = ("# Timeline\n\n| Date | Event | Channel | Note | Due |\n"
                "|---|---|---|---|---|\n| 2026-08-26 | submitted | | | |\n")
        out = archive.timeline_with(text, "| 2026-08-27 | acknowledged | | | |")
        self.assertTrue(out.endswith("| 2026-08-27 | acknowledged | | | |\n"))
        self.assertEqual(len(archive._model().parse_timeline(out)), 2)

    def test_a_row_lands_under_a_heading_with_no_table_yet(self):
        text = "# Timeline\n\nNothing has happened.\n\n# Notes\n\nElsewhere.\n"
        out = archive.timeline_with(text, "| 2026-08-27 | acknowledged | | | |")
        rows = archive._model().parse_timeline(out)
        self.assertEqual(len(rows), 1)
        self.assertIn("# Notes", out)
        self.assertTrue(out.index("acknowledged") < out.index("# Notes"))

    def test_a_row_does_not_land_in_a_table_belonging_to_another_section(self):
        text = ("# Sent\n\n| File | Is |\n|---|---|\n| a.pdf | the resume |\n\n"
                "# Timeline\n\n| Date | Event | Channel | Note | Due |\n"
                "|---|---|---|---|---|\n| 2026-08-26 | submitted | | | |\n")
        out = archive.timeline_with(text, "| 2026-08-27 | acknowledged | | | |")
        self.assertTrue(out.endswith("| 2026-08-27 | acknowledged | | | |\n"))
        self.assertEqual(len(archive._model().parse_timeline(out)), 2)

    def test_a_row_does_not_land_inside_a_fenced_block(self):
        text = ("# Timeline\n\n| Date | Event | Channel | Note | Due |\n"
                "|---|---|---|---|---|\n| 2026-08-26 | submitted | | | |\n\n"
                "The shape a row takes:\n\n```\n| 2026-08-26 | note | | | |\n```\n")
        out = archive.timeline_with(text, "| 2026-08-27 | acknowledged | | | |")
        self.assertIn("| 2026-08-26 | submitted | | | |\n"
                      "| 2026-08-27 | acknowledged | | | |", out)
        self.assertTrue(out.endswith("```\n"))

    def test_the_body_ends_in_exactly_one_newline(self):
        text = "# Timeline\n\n| Date |\n|---|\n| 2026-08-26 | submitted | | | |"
        out = archive.timeline_with(text, "| 2026-08-27 | note | | | |")
        self.assertTrue(out.endswith("\n"))
        self.assertFalse(out.endswith("\n\n"))


class TheWholeCli(ArchiveCase):
    """One filing and one event through commands.main, over the assembled parser."""

    def main(self, *argv):
        commands = authoring_module("authoring.commands")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = commands.main([str(item) for item in argv])
        return code, out.getvalue()

    def test_okf_application_file_and_event_run_through_main(self):
        code, out = self.main("application", "file", "acme-engineer",
                              "--bundle", self.root, "--submitted", "2026-08-26",
                              "--channel", "Workday portal",
                              "--document", self.pdf)
        self.assertEqual(code, 0, out)
        self.assertIn("2026-08-26-acme-engineer.md", out)
        code, out = self.main("application", "event", "2026-08-26-acme-engineer",
                              "--bundle", self.root, "--event", "acknowledged",
                              "--date", "2026-08-27")
        self.assertEqual(code, 0, out)
        self.assertIn("event: acknowledged", out)
        self.assert_gate_is_clean()

    def test_a_refusal_through_main_exits_one_and_carries_its_fix(self):
        code, out = self.main("application", "file", "acme-engineer",
                              "--bundle", self.root, "--submitted", "unknown")
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("fix:", out)


class Registration(unittest.TestCase):
    """The CLI contract: one noun, two verbs, and no third way to change a row."""

    def test_the_noun_is_the_one_okf_py_dispatches(self):
        parser = build_parser()
        args = parser.parse_args(["application", "file", "x", "--bundle", "."])
        self.assertIs(args.build, archive.application_file)
        args = parser.parse_args(["application", "event", "x", "--bundle", ".",
                                  "--event", "note"])
        self.assertIs(args.build, archive.application_event)

    def test_there_is_no_set_verb(self):
        # A correction is a new row, for the same reason log.md records mistakes
        # rather than hiding them. There is no `set` here and there must not be.
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                build_parser().parse_args(["application", "set", "x"])

    def test_every_verb_carries_the_common_flags(self):
        for argv in (["application", "file", "x", "--bundle", "."],
                     ["application", "event", "x", "--bundle", ".",
                      "--event", "note"]):
            with self.subTest(verb=argv[1]):
                args = build_parser().parse_args(argv)
                self.assertFalse(args.dry_run)
                self.assertFalse(args.json)
                self.assertEqual(args.set, [])


if __name__ == "__main__":                               # pragma: no cover
    unittest.main()
