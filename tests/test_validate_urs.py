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

    def test_quantified_prose_without_any_metric_only_warns(self):
        code, out = self.validate(self.bullet("Rolled out to 42 sites."))
        self.assertEqual(code, 0, out)
        self.assertIn("cannot be checked for inflation", out)

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
    def test_strict_promotes_warnings_to_failures(self):
        doc = urs_doc()
        doc["engagements"][0]["achievements"][1]["text"] = "Rebuilt 9 pipelines."
        self.assertFails(doc, "cannot be checked for inflation", "--strict")


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
