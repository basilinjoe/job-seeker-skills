"""validate_urs.py is the gate in front of rendering, so it does not go unchecked.

Two of its rules are structural guarantees rather than preferences, and both get
their own tests: a numeral in a bullet must be backed by a metric, and a view
must not contain content text. If either stops failing, the format stops meaning
what the spec says it means.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import (EXAMPLE_URS, VALIDATE_URS, achievement, ended, ongoing,
                      run, urs_doc, write_urs)


class UrsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def validate(self, doc, *args):
        path = write_urs(self.tmp, doc)
        return run(VALIDATE_URS, path, *args)

    def assertPasses(self, doc, *args):
        code, out = self.validate(doc, *args)
        self.assertEqual(code, 0, f"expected PASS, got:\n{out}")
        return out

    def assertFails(self, doc, needle, *args):
        code, out = self.validate(doc, *args)
        self.assertEqual(code, 1, f"expected FAIL, got exit {code}:\n{out}")
        self.assertIn(needle, out)
        return out


class ShippedExample(UrsCase):
    def test_example_document_is_still_valid(self):
        """The shipped example is a frozen archive shape: no schema, no conformance
        level, and still every invariant that stops a resume inventing something."""
        code, out = run(VALIDATE_URS, EXAMPLE_URS)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_baseline_fixture_is_valid(self):
        self.assertPasses(urs_doc())


class NumeralsMustBeBacked(UrsCase):
    """The rule that stops a rewritten bullet from quietly inflating a number."""

    def bullet(self, text, metrics=()):
        doc = urs_doc()
        doc["engagements"][0]["achievements"] = [
            achievement(text, metrics=metrics, aid="ach_one")]
        doc["skills"][0]["evidence"] = ["ach_one"]
        return doc

    def test_unbacked_numeral_fails(self):
        metrics = [{"kind": "count", "subject": "sites",
                    "quantity": {"value": 42}, "confidence": "measured"}]
        self.assertFails(
            self.bullet("Rolled out to 42 sites, cutting cost 31%.", metrics),
            "appears in the text")

    def test_backed_numerals_pass(self):
        metrics = [
            {"kind": "count", "subject": "sites", "quantity": {"value": 42},
             "confidence": "measured"},
            {"kind": "ratio", "subject": "cost", "quantity": {"value": 31, "unit": "%"},
             "baseline": {"value": 100, "unit": "%"}, "direction": "decrease",
             "confidence": "measured"},
        ]
        self.assertPasses(self.bullet("Rolled out to 42 sites, cutting cost 31%.", metrics))

    def test_quantified_prose_without_any_metric_fails(self):
        """This warned and skipped the check, which inverted the threat: a bullet
        whose number disagreed with its own metric failed, while one that invented a
        number and attached nothing passed and rendered. The second is what tailoring
        produces - prose written fresh against a posting - so it is the case worth
        failing, and the message names the row to add."""
        out = self.assertFails(self.bullet("Rolled out to 42 sites."),
                               "carries no metrics at all")
        self.assertIn("achievements/metrics.md", out)

    def test_standard_designators_are_not_quantities(self):
        # ISO 27001 and SOC 2 are names. Counting them would make the gate noise.
        self.assertPasses(self.bullet("Led the workstream for ISO 27001 and SOC 2 audits."))

    def test_metric_names_are_not_quantities(self):
        # p95 and S3 are glued to letters, so they are identifiers not claims.
        self.assertPasses(self.bullet("Tuned p95 read latency on S3 and IPv6 endpoints."))

    def test_years_are_not_quantities(self):
        self.assertPasses(self.bullet("Ran the 2024 platform consolidation."))

    def test_scaled_suffix_matches_the_metric(self):
        metrics = [{"kind": "absolute", "subject": "records",
                    "quantity": {"value": 1200000}, "confidence": "measured"}]
        self.assertPasses(self.bullet("Indexed 1.2m records.", metrics))


class ViewsSelectAndNeverWrite(UrsCase):
    """A view references content. It never contains it."""

    def test_free_text_in_a_view_fails(self):
        doc = urs_doc()
        doc["views"][0]["summary_text"] = (
            "Seasoned architect with a decade of delivery across regulated health")
        self.assertFails(doc, "a view references content, it never contains it")

    def test_unrecognised_key_is_rejected_not_ignored(self):
        # A typo must not pass silently. `startDate` for `start` is the failure
        # this catches, and the one that loses a date with nobody noticing.
        doc = urs_doc()
        doc["views"][0]["theme"] = "compact"
        self.assertFails(doc, "theme")

    def test_extensions_belong_under_x(self):
        doc = urs_doc()
        doc["views"][0]["x"] = {"com.example.tool": {"theme": "compact"}}
        self.assertPasses(doc)

    def test_unresolvable_region_profile_fails(self):
        doc = urs_doc()
        doc["views"][0]["region_profile"] = "urs:profile:zz/1"
        self.assertFails(doc, "no profile file")

    def test_view_without_a_format_profile_fails(self):
        doc = urs_doc()
        del doc["views"][0]["format_profile"]
        self.assertFails(doc, "no format_profile")


class PeriodsAreUnambiguous(UrsCase):
    def test_ongoing_must_not_carry_an_end_date(self):
        doc = urs_doc()
        doc["engagements"][0]["period"] = {
            "start": {"value": "2021-02", "precision": "month"},
            "end": {"value": "2024-02", "precision": "month"},
            "state": "ongoing"}
        self.assertFails(doc, "must not carry an end date")

    def test_ended_requires_an_end_date(self):
        doc = urs_doc()
        doc["engagements"][0]["period"] = {
            "start": {"value": "2021-02", "precision": "month"}, "state": "ended"}
        self.assertFails(doc, "requires an end date")

    def test_end_before_start_fails(self):
        doc = urs_doc()
        doc["engagements"][0]["period"] = ended("2023-06", "2021-02")
        self.assertFails(doc, "ends before it starts")


class IdentityAndReferences(UrsCase):
    def test_duplicate_ids_fail(self):
        doc = urs_doc()
        doc["organizations"].append({"id": "org_acme", "name": "Acme Again"})
        self.assertFails(doc, "duplicate id")

    def test_dangling_organization_reference_fails(self):
        doc = urs_doc()
        doc["engagements"][0]["organization"] = "org_missing"
        self.assertFails(doc, "unknown id")

    def test_dangling_skill_evidence_fails(self):
        doc = urs_doc()
        doc["skills"][0]["evidence"] = ["ach_nonexistent"]
        self.assertFails(doc, "unknown id")

    def test_dangling_view_selection_fails(self):
        doc = urs_doc()
        doc["views"][0]["include"] = [{"ref": "eng_ghost"}]
        self.assertFails(doc, "unknown id")


class ProvenanceAndPlaceholders(UrsCase):
    def test_achievement_without_provenance_fails(self):
        doc = urs_doc()
        del doc["engagements"][0]["achievements"][1]["provenance"]
        self.assertFails(doc, "no provenance status")

    def test_bracketed_placeholder_in_a_string_fails(self):
        doc = urs_doc()
        doc["engagements"][0]["achievements"][1]["text"] = "Rebuilt [X] pipelines."
        self.assertFails(doc, "bracketed placeholder")

    def test_json_arrays_are_not_placeholders(self):
        # The check reads string values, not the serialised document. A blanket
        # search over the JSON reports every list in the file as a defect.
        doc = urs_doc()
        doc["person"]["demographics"]["nationality"] = ["IN", "AU", "GB"]
        self.assertPasses(doc)


class StrictMode(UrsCase):
    """--strict is for the pass before an application goes out, where anything
    worth a second look is worth stopping for.

    It used to be tested against the unbacked-numeral warning, which is now a
    failure in its own right - so the test was proving nothing about --strict. An
    employer with no evidence anywhere beneath it is a warning that still exists,
    and is exactly the kind of thing a person wants stopped before sending."""

    def empty_employer(self):
        doc = urs_doc()
        doc["engagements"][0]["achievements"] = []
        # The skill's evidence points at a bullet that has just gone, and a
        # dangling reference would fail the document for an unrelated reason.
        doc["skills"][0]["evidence"] = []
        return doc

    def test_an_employer_with_nothing_beneath_it_only_warns(self):
        out = self.assertPasses(self.empty_employer())
        self.assertIn("renders with nothing beneath it", out)

    def test_strict_promotes_warnings_to_failures(self):
        self.assertFails(self.empty_employer(), "renders with nothing beneath it",
                         "--strict")


class OutputIsBounded(UrsCase):
    """jsk-verifier runs this gate and reports what it printed, verbatim.

    A bundle that has answered a hundred postings printed 381 lines of findings -
    about 10,600 tokens landing in an agent's context every time a resume is
    checked. The cap is validate_bundle.py's, to the flag name and the default,
    because two gates answering the same question must not answer it differently.
    """

    def many_failures(self, n=40):
        doc = urs_doc()
        # One unbacked numeral per bullet, small enough not to read as a year.
        doc["engagements"][0]["achievements"] = [
            achievement(f"Rolled out to {v} sites.", aid=f"ach_{v}")
            for v in range(3, 3 + n)]
        doc["skills"][0]["evidence"] = []
        return doc

    def many_warnings(self, n=40):
        doc = urs_doc()
        doc["organizations"] += [{"id": f"acme_{i}", "name": f"Acme {i}"}
                                 for i in range(n)]
        return doc

    def lines(self, out, mark):
        return [ln for ln in out.splitlines() if ln.startswith(f"  {mark}  ")]

    def test_failures_are_capped_at_twenty_five_by_default(self):
        code, out = self.validate(self.many_failures())
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.lines(out, "FAIL")), 26)   # 25 findings + the tally
        self.assertIn("... and 15 more", out)

    def test_warnings_are_capped_the_same_way(self):
        code, out = self.validate(self.many_warnings())
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.lines(out, "warn")), 26)
        self.assertIn("... and 15 more", out)

    def test_the_header_still_counts_every_finding(self):
        """Truncation is only safe while the total is visible."""
        _, out = self.validate(self.many_failures())
        self.assertIn("FAIL 40", out)

    def test_zero_prints_every_one(self):
        _, out = self.validate(self.many_failures(), "--max-findings", "0")
        self.assertEqual(len(self.lines(out, "FAIL")), 40)
        self.assertNotIn("more", out)

    def test_an_explicit_cap_is_honoured(self):
        _, out = self.validate(self.many_failures(), "--max-findings", "5")
        self.assertEqual(len(self.lines(out, "FAIL")), 6)
        self.assertIn("... and 35 more", out)

    def test_a_cap_that_is_not_a_number_is_a_usage_error(self):
        code, out = self.validate(urs_doc(), "--max-findings", "lots")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_the_cap_value_is_not_mistaken_for_the_document(self):
        path = write_urs(self.tmp, urs_doc())
        code, out = run(VALIDATE_URS, "--max-findings", "5", path)
        self.assertEqual(code, 0, out)


class Malformed(UrsCase):
    def test_unparseable_json_reports_rather_than_crashing(self):
        path = self.tmp / "broken.json"
        path.write_text("{ not json", encoding="utf-8")
        code, out = run(VALIDATE_URS, path)
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", out)

    def test_missing_name_fails(self):
        doc = urs_doc()
        doc["person"]["name"] = {}
        self.assertFails(doc, "person.name.full")

    def test_unsupported_version_fails(self):
        doc = urs_doc()
        doc["urs"] = "2.0.0"
        self.assertFails(doc, "unsupported urs version")


if __name__ == "__main__":
    unittest.main()
