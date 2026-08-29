"""validate_ujd.py is the gate in front of scoring, so it does not go unchecked.

Two of its rules are structural guarantees rather than preferences. A span must
be a substring of the text it claims to come from, and a requirement group must
not contain itself. If either stops failing, a posting document can claim a
traceability it does not have, or hang every evaluator that reads it.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import EXAMPLE_UJD, VALIDATE_UJD, load_example, run, ujd_doc, write_json


class UjdCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def validate(self, doc, *args):
        path = write_json(self.tmp, doc, "posting.json")
        return run(VALIDATE_UJD, path, *args)

    def assertPasses(self, doc, *args):
        code, out = self.validate(doc, *args)
        self.assertEqual(code, 0, f"expected PASS, got:\n{out}")
        return out

    def assertFails(self, doc, needle, *args):
        code, out = self.validate(doc, *args)
        self.assertEqual(code, 1, f"expected FAIL, got exit {code}:\n{out}")
        self.assertIn(needle, out)
        return out


class ShippedExample(UjdCase):
    def test_example_document_is_valid_at_level_2(self):
        code, out = run(VALIDATE_UJD, EXAMPLE_UJD, "--level", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("conformance: level 2", out)

    def test_baseline_fixture_is_valid(self):
        self.assertPasses(ujd_doc())


class SpansMustBeTraceable(UjdCase):
    """An extraction nobody can trace back to a span is an assertion."""

    def test_span_not_present_in_raw_text_fails(self):
        doc = ujd_doc()
        doc["requirements"][0]["provenance"]["source"]["span"] = "never said this"
        self.assertFails(doc, "not a substring of source.raw_text")

    def test_level_2_requires_a_span_on_posting_text(self):
        doc = ujd_doc()
        del doc["requirements"][0]["provenance"]["source"]["span"]
        self.assertFails(doc, "posting-text extraction with no span", "--level", "2")

    def test_seniority_provenance_is_walked_even_though_it_is_named_differently(self):
        """role.seniority_provenance is a provenance that is not called one.

        The whole seniority axis rests on it, so a walker keyed on the field name
        would skip the single claim most worth checking.
        """
        doc = ujd_doc()
        doc["role"]["seniority_provenance"] = {
            "status": "confirmed",
            "source": {"kind": "posting-text", "span": "not in the advertisement"},
        }
        self.assertFails(doc, "not a substring of source.raw_text")


class GroupsMustResolve(UjdCase):
    def test_member_that_is_neither_requirement_nor_group_fails(self):
        doc = ujd_doc()
        doc["requirement_groups"] = [
            {"id": "grp_a", "satisfy": "any", "members": ["req_one", "req_ghost"]}]
        self.assertFails(doc, "which is neither a requirement nor a group")

    def test_a_cycle_is_caught_rather_than_recursed_into(self):
        doc = ujd_doc()
        doc["requirement_groups"] = [
            {"id": "grp_a", "satisfy": "any", "members": ["grp_b"]},
            {"id": "grp_b", "satisfy": "any", "members": ["grp_a"]},
        ]
        self.assertFails(doc, "requirement group cycle")

    def test_at_least_more_than_members_fails(self):
        doc = ujd_doc()
        doc["requirement_groups"] = [
            {"id": "grp_a", "satisfy": "at-least", "n": 3, "members": ["req_one"]}]
        self.assertFails(doc, "asks for at least 3 of 1 members")

    def test_requirement_naming_a_missing_group_fails(self):
        doc = ujd_doc()
        doc["requirements"][0]["group"] = "grp_nowhere"
        self.assertFails(doc, "which does not exist")


class ProvenanceCannotBeLaundered(UjdCase):
    def test_confirmed_on_an_inferred_source_fails(self):
        doc = ujd_doc()
        doc["requirements"][0]["provenance"] = {
            "status": "confirmed", "source": {"kind": "inferred"}}
        self.assertFails(doc, "laundering a guess into a fact")

    def test_implicit_necessity_must_carry_an_inferred_source(self):
        doc = ujd_doc()
        doc["requirements"][0]["necessity"] = "implicit"
        self.assertFails(doc, "requires source.kind `inferred`")


class HardFiltersAreNotScored(UjdCase):
    def test_work_authorization_as_a_requirement_fails(self):
        """No amount of skills overlap may offset a visa bar."""
        doc = ujd_doc()
        doc["requirements"].append({
            "id": "req_visa", "kind": "work-authorization", "necessity": "must-have",
            "provenance": {"status": "confirmed", "source": {"kind": "posting-text",
                                                             "span": "integration"}},
        })
        self.assertFails(doc, "belongs in `eligibility`")


class SeniorityStaysAlignedWithUrs(UjdCase):
    def test_a_seniority_outside_the_shared_enum_fails(self):
        doc = ujd_doc()
        doc["role"]["seniority"] = "principal-ish"
        self.assertFails(doc, "not one of the eight URS values")

    def test_the_enum_matches_the_one_the_scorer_uses(self):
        """A copied vocabulary that drifts breaks the axis silently."""
        import importlib.util

        from fixtures import SCRIPTS

        def load(name):
            spec = importlib.util.spec_from_file_location(name, str(SCRIPTS / name))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        self.assertEqual(load("validate_ujd.py").SENIORITY,
                         load("score_projects.py").SENIORITY)


class VocabularyIsWarnedAboutNotRejected(UjdCase):
    def test_capability_absent_from_the_bundle_vocabulary_warns(self):
        """It scores zero on every project, which looks identical to absent evidence."""
        bundle = self.tmp / "bundle"
        (bundle / "framework").mkdir(parents=True)
        (bundle / "framework" / "capability-vocabulary.md").write_text(
            "# Vocabulary\n\n## Theme\n\n- `something-else`\n", encoding="utf-8")
        code, out = self.validate(ujd_doc(), "--bundle", str(bundle))
        self.assertEqual(code, 0, out)
        self.assertIn("is not in the bundle vocabulary", out)

    def test_strict_turns_that_warning_into_a_failure(self):
        bundle = self.tmp / "bundle"
        (bundle / "framework").mkdir(parents=True)
        (bundle / "framework" / "capability-vocabulary.md").write_text(
            "- `something-else`\n", encoding="utf-8")
        code, _ = self.validate(ujd_doc(), "--bundle", str(bundle), "--strict")
        self.assertEqual(code, 1)

    def test_a_known_capability_is_silent(self):
        bundle = self.tmp / "bundle"
        (bundle / "framework").mkdir(parents=True)
        (bundle / "framework" / "capability-vocabulary.md").write_text(
            "- `integration-architecture`\n", encoding="utf-8")
        code, out = self.validate(ujd_doc(), "--bundle", str(bundle))
        self.assertEqual(code, 0, out)
        self.assertNotIn("not in the bundle vocabulary", out)


class Usage(UjdCase):
    def test_no_arguments_is_a_usage_error(self):
        code, out = run(VALIDATE_UJD)
        self.assertEqual(code, 2)
        self.assertIn("usage:", out)

    def test_missing_file_is_a_usage_error(self):
        code, _ = run(VALIDATE_UJD, self.tmp / "absent.json")
        self.assertEqual(code, 2)

    def test_not_json_fails_rather_than_crashing(self):
        path = self.tmp / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        code, out = run(VALIDATE_UJD, path)
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", out)

    def test_a_document_missing_a_title_fails(self):
        doc = ujd_doc()
        del doc["posting"]["title"]
        self.assertFails(doc, "posting.title is required")


if __name__ == "__main__":
    unittest.main()
