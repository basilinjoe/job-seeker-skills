"""`okf search` has one product and it is the line number.

A hit that points at the wrong line sends somebody to edit the wrong sentence and
nothing tells them, so most of what is pinned below is arithmetic: the row's line,
opened, holds the row's text - in a LF file, in a CRLF file, in frontmatter, in the body
and inside a bullet's field lines. The rest is what grep cannot say and this must:
whether the hit is frozen, which claim it landed in, and what that claim's own
provenance is.

Run against `search.run` directly wherever the answer is a row, because a Result can be
read and a table has to be parsed. The CLI tests cover only what the CLI can get wrong -
the exit codes, and `--top` not reaching `--json`.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixtures import CLI, query_bundle, query_module, run

search = query_module("search")
commands = query_module("commands")
walk = query_module("walk")
filters = query_module("filters")

# A file Windows wrote. Every line ends `\r\n`, there is prose above the first heading,
# and there is a bullet with a field line under it - the three shapes whose reported
# line numbers are derived rather than counted.
CRLF_CONCEPT = (
    "---\r\n"
    "type: Project\r\n"
    'title: "Carriage return platform"\r\n'
    "status: confirmed\r\n"
    "strength: 4\r\n"
    "recency: 2025\r\n"
    "capabilities: [event-driven-architecture]\r\n"
    "---\r\n"
    "\r\n"
    "Preamble prose sitting above every heading in the file.\r\n"
    "\r\n"
    "# The problem\r\n"
    "\r\n"
    "Windows wrote this file and each of its line endings is two bytes.\r\n"
    "\r\n"
    "# Bullets\r\n"
    "\r\n"
    "- Shipped the carriage-return handling nobody asked for.\r\n"
    "  metric: Lines counted correctly\r\n"
    "  status: inferred\r\n"
)

# What each needle in CRLF_CONCEPT is on, counting the file the way an editor does.
CRLF_LINES = {"Preamble prose": 10, "each of its line endings": 14,
              "carriage-return handling": 18, "Lines counted correctly": 19}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bundle = query_bundle(Path(self._tmp.name) / "bundle")

    def args(self, *argv):
        """A namespace from the real parser, so a test cannot drift from `okf`'s flags."""
        return commands.build_parser().parse_args(
            ["search", str(self.bundle)] + [str(a) for a in argv])

    def query(self, *argv):
        return search.run(str(self.bundle), self.args(*argv))

    def rows(self, *argv):
        return self.query(*argv).rows

    def files(self, *argv):
        return sorted({row["file"] for row in self.rows(*argv)})

    def only(self, *argv):
        rows = self.rows(*argv)
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def row_in(self, name, *argv):
        """The one row from `name`, so a needle that also appears elsewhere is usable."""
        rows = [row for row in self.rows(*argv) if row["file"] == name]
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def write_crlf(self, name="carriage-return.md", text=CRLF_CONCEPT):
        path = self.bundle / "projects" / name
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def file_line(self, row):
        """The row's line, as a reader opening the file would see it."""
        with open(self.bundle / row["file"], encoding="utf-8") as handle:
            return handle.readlines()[row["line"] - 1]


class ReportedLines(Base):
    """The line number is what a caller acts on. Every hit's line, opened, must be the
    line holding the match - not the line above it, and not the concept's first line."""

    def test_every_reported_line_holds_the_text_it_reported(self):
        """The whole product. A needle in frontmatter, in prose, in a table and inside a
        bullet's field line, all in one answer - because the offsets are derived
        differently for each and only one of them is a plain count."""
        rows = self.rows("latency", "--archive")
        self.assertGreater(len(rows), 4, rows)
        for row in rows:
            self.assertIn(row["text"], self.file_line(row),
                          f"{row['file']}:{row['line']} does not hold its own text")

    def test_a_frontmatter_hit_reports_the_file_line_not_a_frontmatter_offset(self):
        row = self.row_in("projects/care-platform.md", "headline_metric")
        self.assertEqual(row["where"], "frontmatter")
        self.assertEqual(row["line"], 13)
        self.assertIn("headline_metric", self.file_line(row))

    def test_a_body_hit_reports_the_file_line_not_a_body_line(self):
        row = self.row_in("projects/care-platform.md", "data-sovereignty design")
        self.assertEqual(row["line"], 26)
        self.assertIn("data-sovereignty design", self.file_line(row))

    def test_a_hit_in_a_file_with_no_frontmatter_counts_from_line_one(self):
        """`offset` is 0 there, so an off-by-one in `line_of` shows up here first."""
        row = self.row_in("sources/retro-notes.md", "latency")
        self.assertEqual(row["line"], 3)
        self.assertIn("latency", self.file_line(row))

    def test_a_crlf_file_reports_the_line_a_reader_will_see(self):
        """A bundle written on Windows is the common case, not the exotic one. The
        frontmatter split slices at a different width for `\\r\\n---\\r\\n`, so a line
        number derived from that width rather than from what survived it would be wrong
        by two for every hit in the file."""
        self.write_crlf()
        for needle, expected in CRLF_LINES.items():
            row = self.row_in("projects/carriage-return.md", needle)
            self.assertEqual(row["line"], expected, needle)
            self.assertIn(needle, self.file_line(row))

    def test_a_crlf_line_number_agrees_with_the_untranslated_bytes(self):
        """`file_line` reads with universal newlines, which is the one reader that
        cannot disagree. This counts the `\\r\\n` separators the editor counts."""
        path = self.write_crlf()
        raw = path.read_bytes().decode("utf-8").split("\r\n")
        row = self.row_in("projects/carriage-return.md", "carriage-return handling")
        self.assertIn("carriage-return handling", raw[row["line"] - 1])

    def test_a_hit_above_every_heading_has_no_heading(self):
        self.write_crlf()
        row = self.row_in("projects/carriage-return.md", "Preamble prose")
        self.assertIsNone(row["heading"])

    def test_a_body_hit_names_the_heading_it_sits_under(self):
        self.write_crlf()
        row = self.row_in("projects/carriage-return.md", "each of its line endings")
        self.assertEqual(row["heading"], "The problem")

    def test_the_frontmatter_fences_are_not_searchable(self):
        """`---` is the only line in a concept nobody wrote. Matching it would return
        every concept in the bundle and say nothing about any of them."""
        self.assertEqual(self.rows("^-{3}$", "--regex", "--archive"), [])
        # The control: an anchored pattern does find a whole line when there is one.
        self.assertTrue(self.rows("^# Bullets$", "--regex"))


class Archive(Base):
    """The frozen copies beside a sent application are off by default and, when read,
    must say what they are: a hit there is the record of what was already posted, and
    somebody sent to fix a sentence in one would be editing history."""

    FROZEN = "tailoring/applications/2025/2025-11-03-kestrel-staff.posting.md"

    def test_the_archive_is_silent_by_default(self):
        self.assertNotIn(self.FROZEN, self.files("latency"))
        self.assertTrue(all(not row["frozen"] for row in self.rows("latency")))

    def test_the_archive_is_read_when_asked_for(self):
        self.assertIn(self.FROZEN, self.files("latency", "--archive"))

    def test_an_archived_hit_is_marked_frozen(self):
        row = self.row_in(self.FROZEN, "latency", "--archive")
        self.assertTrue(row["frozen"])

    def test_the_human_answer_prints_frozen_over_an_archived_hit(self):
        code, out = run(CLI, "search", self.bundle, "latency", "--archive")
        self.assertEqual(code, 0, out)
        self.assertIn("FROZEN", out)

    def test_the_human_answer_never_prints_frozen_without_the_flag(self):
        code, out = run(CLI, "search", self.bundle, "latency")
        self.assertEqual(code, 0, out)
        self.assertNotIn("FROZEN", out)

    def test_an_empty_answer_says_the_archive_was_not_read(self):
        """The failure this prevents: an empty result whose boundaries are invisible
        reads as "there is nothing there", and somebody concludes they never applied."""
        result = self.query("Went internal")
        self.assertEqual(result.rows, [])
        self.assertTrue(any("--archive" in note for note in result.notes), result.notes)

    def test_the_archive_note_is_dropped_once_the_archive_is_read(self):
        result = self.query("Went internal", "--archive")
        self.assertEqual(len(result.rows), 1, result.rows)
        self.assertFalse(any("--archive" in note for note in result.notes))


class Untyped(Base):
    """A file with no frontmatter at all is still text somebody wrote. The compile drops
    it; a search that could not see it is a search they stop trusting."""

    def test_a_file_with_no_frontmatter_is_searchable(self):
        row = self.row_in("sources/retro-notes.md", "the latency work")
        self.assertIsNone(row["type"])

    def test_an_untyped_hit_carries_the_defaulted_status_the_record_uses(self):
        """Blank would be a second answer to a question `okf_compile.provenance` has
        already answered - an absent `status` is `needs-verification`."""
        row = self.row_in("sources/retro-notes.md", "the latency work")
        self.assertEqual(row["status"], "needs-verification")

    def test_the_block_calls_an_untyped_hit_untyped(self):
        row = self.row_in("sources/retro-notes.md", "the latency work")
        self.assertIn("untyped", "\n".join(search.block(row)))

    def test_a_search_finds_text_in_a_job_advertisement(self):
        """`walk()` defaults to `tailoring="views"`, which skips every `*.posting.md` and
        `*.gaps.md` under `tailoring/targets/` because nothing else needs them. A search
        does: "did I already apply somewhere that wanted this?" is a question only the
        advertisement answers. And the failure is silent - the search reports nothing
        matched, which is a sentence this command is trusted about.
        """
        row = self.row_in("tailoring/targets/meridian-principal.posting.md",
                          "Meridian Health is hiring")
        self.assertEqual(row["heading"], "Advertisement")
        self.assertIn("Meridian Health is hiring", self.file_line(row))

    def test_a_search_finds_text_in_a_gap_assessment(self):
        """The other file the narrow tailoring read skips."""
        self.assertEqual(
            self.files("Strong fit"),
            ["tailoring/targets/meridian-principal.gaps.md"])

    def test_an_index_file_is_never_a_hit(self):
        """Its rows are generated from the concepts they point at, so every hit in one
        is a duplicate attached to a file nobody should edit by hand."""
        for row in self.rows("Contents", "--archive"):
            self.assertFalse(row["file"].endswith("index.md"), row)


class Claims(Base):
    """A hit inside a `# Bullets`, `# Skills` or `# Held` item is a hit on a claim, and a
    claim carries its own id and its own provenance."""

    CARE = "projects/care-platform.md"

    def test_a_hit_in_a_bullet_carries_the_bullets_id(self):
        row = self.row_in(self.CARE, "data-sovereignty design")
        self.assertEqual(row["claim"], "ach_projects_care_platform_md_2")

    def test_a_bullet_hit_carries_the_bullets_status_not_the_concepts(self):
        """`care-platform.md` is `status: confirmed` and holds an `inferred` bullet.
        Printing the concept's status there tells somebody a sentence is signed off when
        nobody has signed it off - and they put it on a resume."""
        row = self.row_in(self.CARE, "data-sovereignty design")
        self.assertEqual(row["status"], "inferred")
        concept = next(c for c in walk.walk(str(self.bundle))
                       if c.rel == self.CARE)
        self.assertEqual(concept.status, "confirmed")

    def test_a_hit_on_a_bullets_field_line_still_carries_the_bullet(self):
        """The reason spans are used rather than each claim's first line: `metric:` sits
        under the sentence it belongs to, and a hit there with no id is a hit whose claim
        the caller has to go and find by eye."""
        row = self.row_in(self.CARE, "metric: Event propagation latency")
        self.assertEqual(row["claim"], "ach_projects_care_platform_md_1")
        self.assertEqual(row["status"], "confirmed")

    def test_a_hit_in_the_prose_above_the_bullets_carries_no_claim(self):
        row = self.row_in(self.CARE, "legacy scheduler")
        self.assertIsNone(row["claim"])
        self.assertEqual(row["status"], "confirmed")

    def test_a_skill_hit_uses_the_id_the_item_declares(self):
        """`skill_` ids are content-derived, so deriving one here rather than reading the
        declared `id:` would print `skill_c_net` - an id `okf view include` refuses."""
        row = self.row_in("skills/competencies.md", "ASP.NET Core")
        self.assertEqual(row["claim"], "skill_dotnet")

    def test_a_skill_hit_with_no_declared_id_gets_the_derived_one(self):
        row = self.row_in("skills/competencies.md", "cloud-platform")
        self.assertEqual(row["claim"], "skill_azure")

    def test_a_held_credential_hit_carries_its_own_status(self):
        row = self.row_in("education/cloud-certifications.md", "Solutions Architect")
        self.assertEqual(row["claim"], "cred_cloud_certifications_1")
        self.assertEqual(row["status"], "active")

    def test_a_crlf_bullet_hit_carries_the_bullet(self):
        """Line arithmetic and claim spans are derived from the same body, so a CRLF file
        is where the two could disagree without either being obviously wrong."""
        self.write_crlf()
        row = self.row_in("projects/carriage-return.md", "Lines counted correctly")
        self.assertEqual(row["claim"], "ach_projects_carriage_return_md_1")
        self.assertEqual(row["status"], "inferred")


class FiltersAlone(Base):
    """`--capability X --strength 4+` with no text is the tailoring query. It has to
    work, and it has to be a listing of concepts rather than of lines."""

    def test_capability_and_strength_select_the_strong_project(self):
        row = self.only("--capability", "event-driven-architecture", "--strength", "4+")
        self.assertEqual(row["file"], "projects/care-platform.md")
        self.assertEqual(row["strength"], 5)

    def test_the_low_strength_project_is_excluded(self):
        """`billing-reconciliation.md` carries the capability at strength 2. A filter that
        handed it back would be handing back evidence the scorer will then rank last."""
        strong = self.files("--capability", "event-driven-architecture",
                            "--strength", "4+")
        both = self.files("--capability", "event-driven-architecture")
        self.assertNotIn("projects/billing-reconciliation.md", strong)
        self.assertIn("projects/billing-reconciliation.md", both)
        self.assertEqual(len(both), 2, both)

    def test_repeated_capabilities_read_as_carries_all_of_them(self):
        rows = self.rows("--capability", "event-driven-architecture",
                         "--capability", "ai-platform-architecture")
        self.assertEqual([row["file"] for row in rows], ["projects/care-platform.md"])

    def test_a_filters_only_answer_is_one_row_per_concept(self):
        rows = self.rows("--type", "Project")
        self.assertEqual(len(rows), 2, rows)
        self.assertEqual(len({row["file"] for row in rows}), 2)

    def test_a_filters_only_answer_renders_as_columns(self):
        result = self.query("--type", "Project")
        self.assertIsNotNone(result.columns)
        self.assertIsNone(result.block)

    def test_a_text_answer_renders_as_blocks(self):
        result = self.query("latency")
        self.assertIsNotNone(result.block)
        self.assertIsNone(result.columns)

    def test_filters_narrow_a_text_search_as_well(self):
        rows = self.rows("latency", "--type", "Project")
        self.assertEqual({row["file"] for row in rows}, {"projects/care-platform.md"})

    def test_neither_text_nor_a_filter_is_a_usage_error(self):
        """Otherwise `okf search <bundle>` dumps the bundle, which is `okf list`'s job
        and reads as an answer to a question nobody asked."""
        code, out = run(CLI, "search", self.bundle)
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


class Where(Base):
    """`--frontmatter` and `--body` restrict where a line may match, and say so."""

    def test_frontmatter_only_ignores_the_body(self):
        rows = self.rows("azure", "--frontmatter")
        self.assertTrue(rows)
        self.assertEqual({row["where"] for row in rows}, {"frontmatter"})

    def test_body_only_ignores_the_frontmatter(self):
        rows = self.rows("azure", "--body")
        self.assertTrue(rows)
        self.assertEqual({row["where"] for row in rows}, {"body"})

    def test_the_two_together_are_the_whole_file(self):
        both = len(self.rows("azure"))
        self.assertEqual(both, len(self.rows("azure", "--frontmatter"))
                         + len(self.rows("azure", "--body")))

    def test_a_restricted_search_says_what_it_did_not_read(self):
        notes = "\n".join(self.query("azure", "--frontmatter").notes)
        self.assertIn("frontmatter", notes)

    def test_a_scoped_search_says_what_it_did_not_read(self):
        result = self.query("latency", "--scope", "projects")
        self.assertTrue(any("projects" in note for note in result.notes), result.notes)
        self.assertEqual(self.files("latency", "--scope", "projects"),
                         ["projects/care-platform.md"])


class Prefilter(Base):
    """`must_contain` skips a file before its YAML is parsed - five sixths of a walk.

    It is sound only where the test it applies matches the test the search itself
    applies, and a mismatch makes a search miss files in silence. These check the
    *property* rather than the returned shape: the shape moved once already, when
    `filters.literals(needle, regex)` - which could not be told whether the search was
    folded - became `filters.prefilter(needle, regex, case_sensitive)`, which cannot be
    called wrong.
    """

    def admits(self, raw, *argv):
        """Whether the pre-filter would let a file with this text be parsed."""
        holds = search.prefilter(self.args(*argv))
        return True if holds is None else holds(raw)

    def test_an_exact_case_search_skips_a_file_that_cannot_hold_the_string(self):
        self.assertTrue(self.admits("cut latency", "latency", "--case-sensitive"))
        self.assertFalse(self.admits("cut LATENCY", "latency", "--case-sensitive"))

    def test_a_folded_search_is_prefiltered_by_folding_both_sides(self):
        """This is the case that used to give up the optimisation entirely, and it is
        the *default* - so almost every search anybody runs was paying the full parse.
        Folding both sides is sound and costs a fraction of the parse it avoids."""
        self.assertTrue(self.admits("cut latency", "Latency"))
        self.assertTrue(self.admits("cut LATENCY", "latency"))
        self.assertFalse(self.admits("cut throughput", "latency"))

    def test_a_regex_search_is_not_prefiltered_at_all(self):
        """There is no literal a pattern is guaranteed to contain, and deriving one from
        its non-metacharacter runs is how a search comes to miss a file for a reason
        nobody can see."""
        self.assertIsNone(search.prefilter(
            self.args("lat.ncy", "--regex", "--case-sensitive")))
        self.assertTrue(self.admits("anything at all", "lat.ncy", "--regex"))

    def test_the_prefilter_never_excludes_a_file_the_search_would_match(self):
        """The one property that makes it safe, over every combination of the flags that
        affect it. A pre-filter that excludes a matching file is a hit nobody knows is
        missing."""
        texts = ("cut latency 62%", "cut LATENCY 62%", "Latency work", "throughput")
        for argv in (("latency",), ("Latency",), ("latency", "--case-sensitive"),
                     ("LATENCY", "--case-sensitive")):
            matcher = filters.text_matcher(
                argv[0], case_sensitive="--case-sensitive" in argv)
            for raw in texts:
                if matcher(raw):
                    self.assertTrue(self.admits(raw, *argv),
                                    f"{argv} matches {raw!r} but was pre-filtered out")

    def test_a_folded_search_finds_a_spelling_the_literal_would_have_skipped(self):
        self.assertIn("projects/care-platform.md", self.files("HEADLINE_METRIC"))

    def test_an_exact_case_search_does_not_find_the_other_spelling(self):
        self.assertEqual(self.rows("LATENCY", "--case-sensitive"), [])

    def test_a_prefiltered_search_finds_what_the_folded_one_finds(self):
        """The pre-filter is meant to be invisible. A file it skipped that should have
        matched is a hit nobody knows is missing."""
        self.assertEqual(self.files("latency", "--case-sensitive"),
                         self.files("latency"))


class NothingMatched(Base):
    """A search that matched nothing has answered the question it was asked. `0`, not
    grep's `1` - see `query/__init__.py`: `1` here would make an inferred bullet read as
    a failed check and somebody would start clearing them."""

    def test_a_search_matching_nothing_exits_zero_and_says_so(self):
        code, out = run(CLI, "search", self.bundle, "zzzznothinghere")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing matches", out)
        self.assertIn("zzzznothinghere", out)

    def test_an_empty_filters_only_answer_says_so(self):
        result = self.query("--capability", "quantum-alchemy")
        self.assertEqual(result.rows, [])
        self.assertIn("no concept carries every filter", result.summary)

    def test_text_narrowed_away_by_a_filter_says_which_way_to_loosen(self):
        result = self.query("latency", "--capability", "quantum-alchemy")
        self.assertEqual(result.rows, [])
        self.assertIn("filters", result.summary)


class Cli(Base):
    """What only the CLI can get wrong."""

    def test_an_uncompilable_regex_exits_2_with_a_fix_line(self):
        code, out = run(CLI, "search", self.bundle, "[unclosed", "--regex")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_a_bad_strength_exits_2_with_a_fix_line(self):
        code, out = run(CLI, "search", self.bundle, "--strength", "high")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_a_scope_outside_the_bundle_exits_2(self):
        code, out = run(CLI, "search", self.bundle, "latency", "--scope", "nowhere")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_json_is_not_truncated_by_top(self):
        """`--top` is a reading aid and a parser does not read. A JSON answer cut to the
        table's row cap is a parser silently seeing a fraction of the bundle."""
        code, out = run(CLI, "search", self.bundle, "latency", "--top", "1", "--json")
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertGreater(doc["count"], 1)
        self.assertEqual(len(doc["rows"]), doc["count"])

    def test_a_bounded_table_says_how_many_rows_it_did_not_show(self):
        code, out = run(CLI, "search", self.bundle, "latency", "--top", "1")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"and \d+ more")

    def test_every_json_row_carries_the_frozen_key(self):
        code, out = run(CLI, "search", self.bundle, "latency", "--archive", "--json")
        del code
        for row in json.loads(out)["rows"]:
            self.assertIn("frozen", row)

    def test_the_human_answer_prints_file_and_line_together(self):
        code, out = run(CLI, "search", self.bundle, "data-sovereignty design")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, re.escape("projects/care-platform.md") + r":26\b")


class NothingCompiles(Base):
    """The read layer's first rule. A query that paid for a compile would cost what the
    thing it replaces costs, and would refuse to answer about a bundle that is mid-edit -
    which is exactly when the question gets asked."""

    def test_search_answers_when_the_compile_cannot_load(self):
        boom = AssertionError("okf search compiled the bundle")
        with mock.patch("jsk_okf.okf_compile.load", side_effect=boom), \
                mock.patch("jsk_okf.okf_compile.concepts", side_effect=boom):
            rows = self.rows("latency", "--archive")
        self.assertTrue(rows)

    def test_a_filters_only_query_compiles_nothing_either(self):
        boom = AssertionError("okf search compiled the bundle")
        with mock.patch("jsk_okf.okf_compile.load", side_effect=boom), \
                mock.patch("jsk_okf.okf_compile.concepts", side_effect=boom):
            rows = self.rows("--capability", "event-driven-architecture")
        self.assertEqual(len(rows), 2, rows)


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()
