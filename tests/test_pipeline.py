"""pipeline.py tells someone what to do this week, so it has to be right about time.

Most of these run against pipeline_model directly: the derivation is pure, and putting
it through a subprocess would say much less about it. The CLI tests cover what only the
CLI can get wrong - grouping, exit codes, and the date the report is computed against.
"""
import datetime
import tempfile
import unittest
from pathlib import Path

from fixtures import INIT_BUNDLE, PIPELINE, PIPELINE_MODEL, VALIDATE_BUNDLE, load_script, run

model = load_script(PIPELINE_MODEL)

DAY = datetime.date(2026, 9, 18)


def timeline(*rows):
    """A body with a `# Timeline` table. Each row is a 2-5 tuple."""
    out = ["# What was sent", "", "The ATS variant.", "",
           "# Timeline", "", "| Date | Event | Channel | Note | Due |", "|---|---|---|---|---|"]
    for row in rows:
        cells = list(row) + [""] * (5 - len(row))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def state(*rows, as_of=DAY, rules=None):
    return model.derive(model.parse_timeline(timeline(*rows)), as_of, rules)


class DeriveCase(unittest.TestCase):
    """Stage, staleness and next action, from a timeline."""

    def test_stage_is_the_last_advancing_event(self):
        s = state(("2026-09-01", "submitted"), ("2026-09-10", "recruiter-contact"))
        self.assertEqual(s.stage, "recruiter-contact")

    def test_a_note_moves_nothing(self):
        s = state(("2026-09-01", "submitted"), ("2026-09-17", "note", "", "thought about it"))
        self.assertEqual(s.stage, "submitted")

    def test_a_note_does_not_restart_the_clock(self):
        """Writing something down is not contact. The clock keeps running."""
        s = state(("2026-09-01", "submitted"), ("2026-09-17", "note", "", "thought about it"))
        self.assertEqual(s.days_quiet, 17)
        self.assertTrue(s.needs_action)

    def test_a_follow_up_restarts_the_clock_without_moving_the_stage(self):
        """The regression that would be felt first: a board that nags about work done."""
        s = state(("2026-09-01", "submitted"), ("2026-09-17", "follow-up-sent", "email"))
        self.assertEqual(s.stage, "submitted")
        self.assertEqual(s.days_quiet, 1)
        self.assertFalse(s.needs_action)

    def test_silence_past_the_limit_needs_action(self):
        s = state(("2026-09-01", "submitted"))       # 17 days, limit 14
        self.assertTrue(s.needs_action)
        self.assertEqual(s.urgency, "overdue 3d")
        self.assertEqual(s.action, "chase or close")

    def test_inside_the_limit_waits(self):
        s = state(("2026-09-10", "submitted"))       # 8 days, limit 14
        self.assertFalse(s.needs_action)
        self.assertEqual(s.urgency, "8d")

    def test_exactly_at_the_limit_is_due_today(self):
        s = state(("2026-09-04", "submitted"))       # 14 days, limit 14
        self.assertTrue(s.needs_action)
        self.assertEqual(s.urgency, "due today")

    def test_an_offer_is_a_stage_not_an_ending(self):
        """Closing at `offer` would silence the board when a deadline matters most."""
        s = state(("2026-09-01", "submitted"), ("2026-09-15", "interview-done"),
                  ("2026-09-15", "offer"))
        self.assertIsNone(s.terminal)
        self.assertEqual(s.stage, "offer")
        self.assertTrue(s.needs_action)               # 3 days quiet, limit 2
        self.assertEqual(s.action, "respond - you owe them")

    def test_accepting_an_offer_closes_it(self):
        s = state(("2026-09-01", "submitted"), ("2026-09-15", "offer"),
                  ("2026-09-16", "accepted"))
        self.assertEqual(s.terminal, "accepted")
        self.assertFalse(s.needs_action)

    def test_a_bundles_own_rules_win(self):
        rules = dict(model.DEFAULT_RULES, submitted=30)
        s = state(("2026-09-01", "submitted"), rules=rules)
        self.assertFalse(s.needs_action)


class DueCase(unittest.TestCase):
    """An explicit promise beats the rule, in both directions."""

    def test_a_future_due_holds_back_an_item_the_rule_would_chase(self):
        s = state(("2026-08-20", "submitted", "", "", "2026-09-30"))
        self.assertFalse(s.needs_action)
        self.assertEqual(s.urgency, "in 12d")

    def test_a_passed_due_brings_an_item_forward(self):
        s = state(("2026-09-16", "recruiter-contact", "", "said Wednesday", "2026-09-17"))
        self.assertTrue(s.needs_action)
        self.assertEqual(s.urgency, "overdue 1d")

    def test_the_latest_due_wins(self):
        s = state(("2026-09-01", "submitted", "", "", "2026-09-10"),
                  ("2026-09-09", "recruiter-contact", "", "pushed it back", "2026-09-30"))
        self.assertEqual(s.due, datetime.date(2026, 9, 30))
        self.assertFalse(s.needs_action)

    def test_a_scheduled_interview_is_not_stale_before_it_happens(self):
        s = state(("2026-09-01", "submitted"),
                  ("2026-09-05", "interview-scheduled", "email", "", "2026-09-25"))
        self.assertFalse(s.needs_action)
        self.assertEqual(s.action, "prepare")

    def test_a_scheduled_interview_that_has_passed_wants_recording(self):
        s = state(("2026-09-01", "submitted"),
                  ("2026-09-05", "interview-scheduled", "email", "", "2026-09-15"))
        self.assertTrue(s.needs_action)
        self.assertEqual(s.action, "record what happened")

    def test_a_scheduled_event_with_no_due_says_so(self):
        """Not silently forgiven, but it cannot wait forever either."""
        s = state(("2026-09-01", "submitted"), ("2026-09-01", "interview-scheduled", "email"))
        self.assertIn("no date recorded", s.flags)
        self.assertTrue(s.needs_action)


class TerminalCase(unittest.TestCase):
    def test_a_closed_application_never_needs_action(self):
        s = state(("2026-01-01", "submitted"), ("2026-02-01", "rejected"))
        self.assertEqual(s.terminal, "rejected")
        self.assertFalse(s.needs_action)

    def test_a_reopened_process_is_live_again(self):
        s = state(("2026-01-01", "submitted"), ("2026-02-01", "rejected"),
                  ("2026-09-01", "recruiter-contact", "email", "role reopened"))
        self.assertIsNone(s.terminal)
        self.assertEqual(s.stage, "recruiter-contact")

    def test_an_unknown_date_does_not_crash_or_chase(self):
        """What a migration writes when it could not establish a date."""
        s = state(("unknown", "submitted"), ("unknown", "rejected"))
        self.assertEqual(s.terminal, "rejected")
        self.assertFalse(s.needs_action)

    def test_a_live_application_with_no_dated_event_is_flagged_not_guessed(self):
        s = state(("unknown", "submitted"))
        self.assertIn("no dated event", s.flags)
        self.assertFalse(s.needs_action)


class ParseCase(unittest.TestCase):
    def test_only_the_timeline_table_counts(self):
        """An application file has other tables in it. Treating any pipe-delimited line
        as pipeline state would turn the gate output into a stage."""
        body = ("# Gates\n\n| Gate | Verdict |\n|---|---|\n| parse | PASS |\n\n"
                + timeline(("2026-09-01", "submitted")))
        rows = model.parse_timeline(body)
        self.assertEqual([r.event for r in rows], ["submitted"])

    def test_a_missing_timeline_is_empty_not_an_error(self):
        self.assertEqual(model.parse_timeline("# What was sent\n\nThe ATS variant.\n"), [])

    def test_no_timeline_is_flagged(self):
        s = model.derive([], DAY)
        self.assertIn("no timeline", s.flags)


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.root = self.tmp / "my-career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)

    def application(self, stem, company, role, *rows):
        (self.root / "tailoring/applications" / f"{stem}.md").write_text(
            f"""---
type: Application
title: "{company} - {role}"
description: "Submitted."
timestamp: 2026-08-26T00:00:00Z
status: confirmed
company: "{company}"
role: "{role}"
submitted: {rows[0][0]}
---

""" + timeline(*rows), encoding="utf-8")

    def test_an_empty_bundle_says_so(self):
        code, out = run(PIPELINE, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("no applications yet", out)

    def test_nothing_due_exits_zero(self):
        self.application("kestrel", "Kestrel Health", "Principal Architect",
                         ("2026-09-15", "submitted"))
        code, out = run(PIPELINE, self.root, "--as-of", "2026-09-18")
        self.assertEqual(code, 0, out)
        self.assertIn("NEEDS YOU (0)", out)
        self.assertIn("ACTION 0 | LIVE 1 | CLOSED 0", out)

    def test_something_due_exits_one(self):
        self.application("kestrel", "Kestrel Health", "Principal Architect",
                         ("2026-08-01", "submitted"))
        code, out = run(PIPELINE, self.root, "--as-of", "2026-09-18")
        self.assertEqual(code, 1, out)
        self.assertIn("NEEDS YOU (1)", out)
        self.assertIn("overdue", out)

    def test_as_of_makes_the_report_deterministic(self):
        self.application("kestrel", "Kestrel Health", "Principal Architect",
                         ("2026-09-01", "submitted"))
        early, _ = run(PIPELINE, self.root, "--as-of", "2026-09-05")
        late, _ = run(PIPELINE, self.root, "--as-of", "2026-10-05")
        self.assertEqual((early, late), (0, 1))

    def test_closed_applications_are_counted_not_chased(self):
        self.application("old", "Harbourline", "Solution Architect",
                         ("2026-01-01", "submitted"), ("2026-02-01", "rejected"))
        code, out = run(PIPELINE, self.root, "--as-of", "2026-09-18")
        self.assertEqual(code, 0, out)
        self.assertIn("CLOSED (1)", out)
        self.assertIn("rejected 1", out)

    def test_company_query_finds_every_application(self):
        self.application("kestrel-a", "Kestrel Health", "Principal Architect",
                         ("2026-01-01", "submitted"), ("2026-02-01", "rejected"))
        self.application("kestrel-b", "Kestrel Health", "Staff Architect",
                         ("2026-09-15", "submitted"))
        _, out = run(PIPELINE, self.root, "--as-of", "2026-09-18", "--company", "kestrel")
        self.assertIn("MATCHED 2 | LIVE 1", out)
        self.assertIn("Staff Architect", out)

    def test_a_bad_date_is_a_usage_error(self):
        code, out = run(PIPELINE, self.root, "--as-of", "18th September")
        self.assertEqual(code, 2, out)

    def test_not_a_bundle_is_a_usage_error(self):
        code, out = run(PIPELINE, self.tmp / "nowhere")
        self.assertEqual(code, 2, out)

    def test_a_bundle_with_timelines_still_validates(self):
        self.application("kestrel", "Kestrel Health", "Principal Architect",
                         ("2026-09-01", "submitted"), ("2026-09-10", "follow-up-sent", "email"))
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("VALID", out)


if __name__ == "__main__":
    unittest.main()
