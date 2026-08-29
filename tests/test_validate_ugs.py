"""validate_ugs.py audits a document a model wrote, so it is the load-bearing gate.

Most of these tests deform the shipped example rather than building a minimum
document. That is deliberate: the claim under test is that a *valid* gap analysis
stops being valid when one derived field is wrong, and a hand-built minimum tends
to pass for reasons unrelated to the rule.

The `--recompute` cases are the ones that matter. Each corresponds to something an
LLM-written document could get wrong while still validating cleanly against the
JSON Schema, which is exactly the class of error a schema cannot catch.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import (EXAMPLE_UGS, EXAMPLE_UJD, VALIDATE_UGS, gaps_workspace,
                      load_example, run, ugs_doc, write_json)


class UgsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def example(self):
        """The shipped gap document, laid out beside real subject documents."""
        from fixtures import SCHEMA_DIR
        return (load_example(EXAMPLE_UGS),
                load_example(EXAMPLE_UJD),
                load_example(SCHEMA_DIR / "example.resume.json"))

    def check(self, gaps, posting, record, *args, **kwargs):
        path = gaps_workspace(self.tmp, gaps, posting, record, **kwargs)
        return run(VALIDATE_UGS, path, *args)

    def assertRecomputeFails(self, gaps, posting, record, needle):
        code, out = self.check(gaps, posting, record, "--recompute")
        self.assertEqual(code, 1, f"expected FAIL, got exit {code}:\n{out}")
        self.assertIn(needle, out)
        return out


class ShippedExample(UgsCase):
    def test_example_document_is_valid_at_level_2(self):
        code, out = run(VALIDATE_UGS, EXAMPLE_UGS, "--recompute", "--level", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("conformance: level 2", out)

    def test_the_example_still_passes_once_relocated(self):
        """Guards resolve_ref: the refs are relative and must survive a move."""
        gaps, posting, record = self.example()
        code, out = self.check(gaps, posting, record, "--recompute")
        self.assertEqual(code, 0, out)

    def test_minimal_record_audit_is_valid(self):
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        path = write_json(self.tmp, ugs_doc(), "t.gaps.json")
        code, out = run(VALIDATE_UGS, path)
        self.assertEqual(code, 0, out)


class TheAggregateIsRecomputed(UgsCase):
    """An aggregate that cannot say how it was computed is refused by the schema.

    One that says so and is wrong anyway is refused here - otherwise design rule 8
    buys a formula string and no arithmetic.
    """

    def test_a_tampered_aggregate_fails(self):
        gaps, posting, record = self.example()
        gaps["score"]["aggregate"]["value"] = 0.95
        self.assertRecomputeFails(gaps, posting, record,
                                  "the number and the formula do not describe each other")

    def test_the_same_document_passes_without_recompute(self):
        """Without --recompute the derived fields are taken on trust, and it says so."""
        gaps, posting, record = self.example()
        gaps["score"]["aggregate"]["value"] = 0.95
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 0, out)
        self.assertIn("no --recompute", out)

    def test_a_changed_component_moves_the_expected_aggregate(self):
        gaps, posting, record = self.example()
        for component in gaps["score"]["components"]:
            if component["id"] == "cmp_domain":
                component["normalized"] = 0.0
        self.assertRecomputeFails(gaps, posting, record, "score.aggregate.value is")

    def test_components_included_must_name_real_components(self):
        gaps, posting, record = self.example()
        gaps["score"]["aggregate"]["components_included"].append("cmp_ghost")
        self.assertRecomputeFails(gaps, posting, record, "which are not components here")


class GroupsAreAnsweredAsGroups(UgsCase):
    """The case a flat requirement list gets wrong in both directions.

    'A degree and six years, OR a postgraduate qualification' scores a master's
    holder as missing two must-haves when flattened to independent requirements,
    and lets a bare bachelor's pass when flattened to one `any`.
    """

    def test_the_example_resolves_via_the_postgraduate_arm(self):
        gaps, _, _ = self.example()
        group = next(g for g in gaps["group_assessments"]
                     if g["group"] == "grp_qualification")
        self.assertEqual(group["verdict"], "satisfied")
        branches = {b["member"]: b["verdict"] for b in group["branches"]}
        self.assertEqual(branches["grp_degree_and_years"], "partial")
        self.assertEqual(branches["req_postgrad"], "satisfied")

    def test_a_group_verdict_that_disagrees_with_its_members_fails(self):
        gaps, posting, record = self.example()
        for assessment in gaps["assessments"]:
            if assessment["id"] == "asm_postgrad":
                assessment["verdict"] = "unsatisfied"
        # `any` over [partial, unsatisfied] is partial, not the stored satisfied.
        self.assertRecomputeFails(gaps, posting, record, "under `any` give 'partial'")

    def test_branches_must_be_the_groups_own_members_in_order(self):
        gaps, posting, record = self.example()
        for group in gaps["group_assessments"]:
            if group["group"] == "grp_qualification":
                group["branches"].reverse()
        self.assertRecomputeFails(gaps, posting, record, "in the group's own order")

    def test_satisfy_must_match_the_posting(self):
        gaps, posting, record = self.example()
        for group in gaps["group_assessments"]:
            if group["group"] == "grp_qualification":
                group["satisfy"] = "all"
        self.assertRecomputeFails(gaps, posting, record, "disagrees with the posting's")


class SubjectsArePinned(UgsCase):
    def test_a_stale_posting_checksum_fails(self):
        """A verdict recomputed against an edited posting is a different verdict."""
        gaps, posting, record = self.example()
        gaps["subjects"]["posting"]["checksum"] = "sha256:" + "0" * 64
        code, out = self.check(gaps, posting, record, "--recompute", seal=False)
        self.assertEqual(code, 1, out)
        self.assertIn("does not match the file as read", out)

    def test_editing_the_posting_after_the_fact_fails(self):
        import json
        gaps, posting, record = self.example()
        path = gaps_workspace(self.tmp, gaps, posting, record)
        posting["posting"]["title"] = "Something Else Entirely"
        (path.parent / "example.posting.json").write_bytes(
            json.dumps(posting, indent=2).encode("utf-8"))
        code, out = run(VALIDATE_UGS, path, "--recompute")
        self.assertEqual(code, 1, out)
        self.assertIn("does not match the file as read", out)

    def test_a_line_ending_conversion_is_not_an_edit(self):
        """Regression: a Windows clone with core.autocrlf rewrites every LF to CRLF.

        Hashing the bytes as they sit on disk would invalidate every past assessment
        on checkout, for a change that is not an edit to the posting in any sense a
        person would recognise. The checksum answers "was this document changed", so
        it is taken over normalised line endings.
        """
        import json
        gaps, posting, record = self.example()
        path = gaps_workspace(self.tmp, gaps, posting, record)
        for name in ("example.posting.json", "example.resume.json"):
            target = path.parent / name
            target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
        code, out = run(VALIDATE_UGS, path, "--recompute")
        self.assertEqual(code, 0, out)
        self.assertNotIn("does not match the file as read", out)

    def test_a_real_content_edit_still_fails_under_that_normalisation(self):
        """The normalisation must not soften what the checksum is for."""
        import json
        gaps, posting, record = self.example()
        path = gaps_workspace(self.tmp, gaps, posting, record)
        target = path.parent / "example.posting.json"
        target.write_bytes(json.dumps(posting, indent=2).encode("utf-8")
                           .replace(b"Acme Corp", b"Other Corp"))
        code, out = run(VALIDATE_UGS, path, "--recompute")
        self.assertEqual(code, 1, out)
        self.assertIn("does not match the file as read", out)

    def test_a_bare_hex_checksum_is_accepted_too(self):
        """`sha256:<hex>` and a bare `<hex>` name the same thing."""
        gaps, posting, record = self.example()
        code, out = self.check(gaps, posting, record, "--recompute", prefix="")
        self.assertEqual(code, 0, out)


class EligibilityIsNeverScored(UgsCase):
    """UJD keeps a visa bar out of requirements; UGS keeps it out of the score."""

    def test_a_hard_filter_reaching_a_score_component_fails(self):
        gaps, posting, record = self.example()
        posting["requirements"].append({
            "id": "req_visa", "kind": "work-authorization", "necessity": "must-have",
            "provenance": {"status": "confirmed", "source": {"kind": "posting-text"}},
        })
        gaps["assessments"].append({
            "id": "asm_visa", "requirement": "req_visa", "verdict": "satisfied",
            "evidence": [{"record_id": "eng_meridian", "relation": "direct"}],
        })
        gaps["score"]["components"][0]["of"].append("asm_visa")
        self.assertRecomputeFails(gaps, posting, record, "no skills overlap may offset")

    def test_eligibility_excluded_cannot_be_turned_off(self):
        gaps, posting, record = self.example()
        gaps["score"]["eligibility_excluded"] = False
        code, out = self.check(gaps, posting, record, "--recompute")
        self.assertEqual(code, 1)
        self.assertIn("eligibility is a gate", out)


class SurfaceGapsNeedAView(UgsCase):
    """Held in the record and absent from what was sent is a different failure."""

    def test_surface_without_a_view_fails(self):
        gaps, posting, record = self.example()
        del gaps["subjects"]["record"]["view"]
        code, out = self.check(gaps, posting, record, "--recompute")
        self.assertEqual(code, 1)
        self.assertIn("nothing has been sent yet", out)

    def test_a_view_that_does_not_exist_fails(self):
        gaps, posting, record = self.example()
        gaps["subjects"]["record"]["view"] = "view_nowhere"
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("is not a view in the pinned record", out)

    def test_evidence_outside_the_view_must_be_reported(self):
        gaps, posting, record = self.example()
        for view in record["views"]:
            if view["id"] == gaps["subjects"]["record"]["view"]:
                view["include"] = [e for e in view["include"]
                                   if e["ref"] != "eng_meridian"]
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("the rendered view does not include", out)


class TheJoinMustResolve(UgsCase):
    def test_evidence_naming_an_absent_record_id_fails(self):
        gaps, posting, record = self.example()
        gaps["assessments"][0]["evidence"][0]["record_id"] = "eng_ghost"
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("does not exist in the pinned record", out)

    def test_deeply_nested_record_ids_resolve(self):
        """pos_ ids live under engagements[].positions[], two levels down."""
        gaps, posting, record = self.example()
        code, out = self.check(gaps, posting, record)
        self.assertNotIn("pos_m1", out)
        self.assertEqual(code, 0, out)

    def test_an_assessment_naming_an_absent_requirement_fails(self):
        gaps, posting, record = self.example()
        gaps["assessments"][0]["requirement"] = "req_ghost"
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("does not exist in the pinned posting", out)

    def test_a_requirement_assessed_twice_fails(self):
        gaps, posting, record = self.example()
        duplicate = dict(gaps["assessments"][3])
        duplicate["id"] = "asm_azure_again"
        gaps["assessments"].append(duplicate)
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("is assessed twice", out)

    def test_an_unassessed_requirement_warns(self):
        """Unexamined is not the same as satisfied."""
        gaps, posting, record = self.example()
        gaps["assessments"] = [a for a in gaps["assessments"] if a["id"] != "asm_fhir"]
        gaps["score"]["components"] = [
            c for c in gaps["score"]["components"] if c["id"] != "cmp_domain"]
        gaps["score"]["aggregate"]["components_included"].remove("cmp_domain")
        gaps["score"]["aggregate"]["value"] = 0.71
        code, out = self.check(gaps, posting, record)
        self.assertIn("has no assessment - unexamined is not", out)
        self.assertEqual(code, 0, out)


class VerdictsCarryTheirObligations(UgsCase):
    def test_satisfied_with_no_evidence_fails(self):
        gaps, posting, record = self.example()
        for assessment in gaps["assessments"]:
            if assessment["id"] == "asm_azure":
                assessment["evidence"] = []
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("wearing a verdict's clothes", out)

    def test_partial_with_no_shortfall_fails(self):
        gaps, posting, record = self.example()
        for assessment in gaps["assessments"]:
            if assessment["id"] == "asm_six_years":
                assessment["shortfalls"] = []
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("a hedge, not a finding", out)

    def test_unevidenced_with_no_question_fails(self):
        gaps, posting, record = self.example()
        for assessment in gaps["assessments"]:
            if assessment["id"] == "asm_stakeholder":
                assessment.pop("question", None)
        code, out = self.check(gaps, posting, record)
        self.assertEqual(code, 1)
        self.assertIn("leaves it in the resume", out)

    def test_satisfied_on_asserted_only_evidence_warns(self):
        """It is identical to a real match in a keyword scan."""
        gaps, posting, record = self.example()
        for assessment in gaps["assessments"]:
            if assessment["id"] == "asm_fhir":
                assessment["verdict"] = "satisfied"
                for item in assessment["evidence"]:
                    item["relation"] = "asserted-only"
        code, out = self.check(gaps, posting, record)
        self.assertIn("most dangerous thing here to score", out)
        self.assertEqual(code, 0, out)


class RecordAuditNeedsNoPosting(UgsCase):
    """The UGS 1.1 widening: a bundle audit has no requirement side to pin."""

    def test_a_posting_less_document_is_valid_for_self_assessment(self):
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        path = write_json(self.tmp, ugs_doc(), "t.gaps.json")
        code, out = run(VALIDATE_UGS, path)
        self.assertEqual(code, 0, out)

    def test_a_posting_less_document_for_any_other_purpose_fails(self):
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        doc = ugs_doc()
        doc["meta"]["purpose"] = "application-preparation"
        path = write_json(self.tmp, doc, "t.gaps.json")
        code, out = run(VALIDATE_UGS, path)
        self.assertEqual(code, 1)
        self.assertIn("only valid for a record audit", out)

    def test_assessments_without_a_pinned_posting_fail(self):
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        doc = ugs_doc()
        doc["assessments"] = [{"id": "asm_x", "requirement": "req_x",
                               "verdict": "unsatisfied"}]
        path = write_json(self.tmp, doc, "t.gaps.json")
        code, out = run(VALIDATE_UGS, path)
        self.assertEqual(code, 1)
        self.assertIn("no posting is pinned", out)


class TheQueueIsOrdered(UgsCase):
    def test_unmet_requirement_is_an_accepted_priority(self):
        """The UGS 1.1 addition, and the reason a tailoring round asks anything."""
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        doc = ugs_doc()
        doc["questions"][0]["priority"] = "unmet-requirement"
        path = write_json(self.tmp, doc, "t.gaps.json")
        code, out = run(VALIDATE_UGS, path)
        self.assertEqual(code, 0, out)

    def test_unmet_requirement_outranks_record_hygiene(self):
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        doc = ugs_doc()
        doc["questions"] = [
            {"id": "qst_a", "text": "later", "priority": "missing-metric"},
            {"id": "qst_b", "text": "earlier", "priority": "unmet-requirement"},
        ]
        path = write_json(self.tmp, doc, "t.gaps.json")
        code, out = run(VALIDATE_UGS, path)
        self.assertIn("appears after a lower-priority question", out)
        self.assertEqual(code, 0, out)

    def test_a_parked_question_re_asked_next_round_warns(self):
        """Without this, a requirement nobody can close re-asks forever."""
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        previous = ugs_doc()
        previous["questions"][0]["resolution"] = "unavailable"
        prior_path = write_json(self.tmp, previous, "prev.gaps.json")
        path = write_json(self.tmp, ugs_doc(), "t.gaps.json")
        code, out = run(VALIDATE_UGS, path, "--carry", prior_path)
        self.assertIn("is how a loop stops ending", out)
        self.assertEqual(code, 0, out)


class TheLoopCanEndItself(UgsCase):
    """Three of the five termination reasons are properties of this document."""

    def _status(self, questions):
        write_json(self.tmp, {"urs": "1.0.0"}, "record.json")
        doc = ugs_doc(questions=questions)
        path = write_json(self.tmp, doc, "t.gaps.json")
        code, out = run(VALIDATE_UGS, path)
        self.assertEqual(code, 0, out)
        return out

    def test_no_questions_stops_the_loop(self):
        self.assertIn("loop: STOP - questions[] is empty", self._status([]))

    def test_all_questions_resolved_stops_the_loop(self):
        out = self._status([{"id": "qst_a", "text": "done", "priority": "blocking",
                             "resolution": "confirmed"}])
        self.assertIn("loop: STOP - questions[] is empty", out)

    def test_only_unexplored_left_stops_the_loop(self):
        out = self._status([{"id": "qst_a", "text": "tell me more",
                             "priority": "unexplored"}])
        self.assertIn("belongs in /jsk:gaps", out)

    def test_nothing_new_this_round_stops_the_loop(self):
        out = self._status([{"id": "qst_a", "text": "again", "priority": "blocking",
                             "asked": True}])
        self.assertIn("no new answerable question", out)

    def test_a_fresh_answerable_question_continues_the_loop(self):
        out = self._status([{"id": "qst_a", "text": "new", "priority": "blocking"}])
        self.assertIn("loop: CONTINUE", out)


class Usage(UgsCase):
    def test_no_arguments_is_a_usage_error(self):
        code, out = run(VALIDATE_UGS)
        self.assertEqual(code, 2)
        self.assertIn("usage:", out)

    def test_missing_file_is_a_usage_error(self):
        code, _ = run(VALIDATE_UGS, self.tmp / "absent.json")
        self.assertEqual(code, 2)

    def test_not_json_fails_rather_than_crashing(self):
        path = self.tmp / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        code, out = run(VALIDATE_UGS, path)
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", out)

    def test_report_renders_the_checkpoint(self):
        code, out = run(VALIDATE_UGS, EXAMPLE_UGS, "--recompute", "--report")
        self.assertEqual(code, 0, out)
        for heading in ("# Assessment", "# Requirement groups", "# Questions, in order",
                        "# Score:", "# Loop:"):
            self.assertIn(heading, out)


if __name__ == "__main__":
    unittest.main()
