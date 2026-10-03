"""`jsk app event`: what happened to a frozen application after it was sent."""
import json
import unittest
from unittest import mock

import appkit
from shipkit import GraphCase


class Event(GraphCase):
    def setUp(self):
        super().setUp()
        code, out = self.freeze()
        self.assertEqual(code, 0, out)

    def event(self, *args):
        return self.jsk("app", "event", self.sent, *args)

    @property
    def record(self):
        return appkit.facts(self.root, self.graph(self.sent, "application"))

    def test_an_event_is_appended_and_the_stage_follows_it(self):
        name = self.graph(self.sent, "application")
        before, text = self.record, appkit.text(self.root, name)
        log = appkit.facts(self.root, "log")
        code, out = self.event("screen-scheduled", "--date", "2026-09-26", "--channel", "email",
                               "--due", "2026-09-30", "--note", "Phone screen, 30 min")
        self.assertEqual(code, 0, out)
        self.assertIn("added    k:evt_contoso_platform_2026_09_26_screen_scheduled", out)
        self.assertIn(f"+++ b/{name}", out)                  # the diff names the graph
        self.assertTrue(self.record > before)               # added to, nothing taken away
        after = appkit.text(self.root, name)
        self.assertTrue(after.startswith(text.split("# == Timeline")[0]), after)
        self.assertEqual(appkit.facts(self.root, "log"), log)   # the career's log is not its
        self.assertFalse((self.sent / "application.ttl").exists())
        _, events = self.application()
        e = events["evt_contoso_platform_2026_09_26_screen_scheduled"]
        self.assertEqual((e["date"], e["channel"], e["due"], e["note"]),
                         ("2026-09-26", "email", "2026-09-30", "Phone screen, 30 min"))
        code, out = self.jsk("kb", "query", "pipeline", "--json", "--root", self.root)
        self.assertEqual(code, 0, out)
        [row] = json.loads(out)
        self.assertEqual((row["application"], row["stage"], row["since"], row["due"],
                          row["events"]),
                         ("k:app_contoso_platform", "screen-scheduled", "2026-09-26",
                          "2026-09-30", 2))

    def test_a_step_on_the_day_of_submitted_is_the_stage(self):
        """The P3 replay (2026-10-04): a same-day tie went to the event IRI, and
        `..._submitted` sorts after `..._acknowledged` and `..._rejected`, so the stage
        stayed `submitted`. A note that day is not the stage either."""
        for kind in ("acknowledged", "rejected"):
            with self.subTest(kind=kind):
                code, out = self.event(kind, "--date", "2026-09-24")
                self.assertEqual(code, 0, out)
                code, out = self.event("note", "--date", "2026-09-24", "--note", kind)
                self.assertEqual(code, 0, out)
                code, out = self.jsk("kb", "query", "pipeline", "--json", "--root", self.root)
                self.assertEqual(code, 0, out)
                [row] = json.loads(out)
                self.assertEqual((row["stage"], row["since"]), (kind, "2026-09-24"))

    def test_a_store_failing_after_the_event_landed_does_not_say_nothing_was_written(self):
        with appkit.failing_after_write():
            code, out = self.event("note", "--date", "2026-09-26", "--note", "chased")
        self.assertEqual(code, 1, out)
        self.assertIn("landed", out)
        self.assertNotIn("nothing was written", out)
        _, events = self.application()
        self.assertIn("evt_contoso_platform_2026_09_26_note", events)

    def test_the_same_event_twice_is_refused(self):
        """Same kind, day, channel, note and due as one already there: a true duplicate."""
        before = self.record
        code, out = self.event("submitted", "--date", "2026-09-24", "--channel", "Workday portal")
        self.assertEqual(code, 1, out)
        self.assertIn("already recorded", out)
        self.assertIn("k:evt_contoso_platform_2026_09_24_submitted", out)
        self.assertEqual(self.record, before)

    def test_a_second_event_of_a_kind_on_a_day_gets_the_next_suffix(self):
        """Two notes, two interview rounds, on one day: each is recorded, minted `_2`,
        then `_3`."""
        stem = "evt_contoso_platform_2026_09_26"
        for n, (kind, note, want) in enumerate([
                ("note", "Recruiter called", f"{stem}_note"),
                ("note", "Sent the portfolio link", f"{stem}_note_2"),
                ("note", "Recruiter called back", f"{stem}_note_3"),
                ("interview-done", "Round 1", f"{stem}_interview_done"),
                ("interview-done", "Round 2", f"{stem}_interview_done_2")]):
            with self.subTest(n=n):
                code, out = self.event(kind, "--date", "2026-09-26", "--note", note)
                self.assertEqual(code, 0, out)
                self.assertIn(f"added    k:{want}\n", out)
        _, events = self.application()
        self.assertEqual(events[f"{stem}_note_2"]["note"], "Sent the portfolio link")
        self.assertEqual(events[f"{stem}_interview_done_2"]["note"], "Round 2")
        self.assertEqual([f.text() for f in self.store().fails()], [])

    def test_a_repeat_of_a_suffixed_event_is_refused_too(self):
        for note in ("first", "second"):
            code, out = self.event("note", "--date", "2026-09-26", "--note", note)
            self.assertEqual(code, 0, out)
        code, out = self.event("note", "--date", "2026-09-26", "--note", "second")
        self.assertEqual(code, 1, out)
        self.assertIn("k:evt_contoso_platform_2026_09_26_note_2 is already recorded", out)

    def test_two_events_of_a_kind_with_unknown_dates_are_both_recorded(self):
        for note, want in (("LinkedIn", ""), ("Email", "_2")):
            code, out = self.event("recruiter-contact", "--date", "unknown", "--note", note)
            self.assertEqual(code, 0, out)
            self.assertIn(f"evt_contoso_platform_unknown_recruiter_contact{want}\n", out)

    def test_an_unknown_kind_is_refused_with_the_nearest(self):
        before = self.record
        code, out = self.event("interview-schedule", "--date", "2026-09-26")
        self.assertEqual(code, 2, out)
        self.assertIn("did you mean 'interview-scheduled'?", out)
        self.assertEqual(self.record, before)

    def test_a_bad_date_is_a_call_error(self):
        for bad in ("26/09/2026", "2026-02-30", "soon"):
            with self.subTest(date=bad):
                code, out = self.event("note", "--date", bad)
                self.assertEqual(code, 2, out)

    def test_an_unknown_date_is_an_event_too(self):
        code, out = self.event("recruiter-contact", "--date", "unknown")
        self.assertEqual(code, 0, out)
        self.assertIn("evt_contoso_platform_unknown_recruiter_contact", out)
        self.assertIn("recorded recruiter-contact on unknown\n", out)
        self.assertNotIn("WARN", out)

    def test_the_dates_come_back_with_their_weekday_and_distance(self):
        """"Last Thursday" worked out wrong shows as the wrong weekday."""
        code, out = self.event("screen-scheduled", "--date", "2026-09-25", "--due", "2026-09-30",
                               "--today", "2026-09-29")
        self.assertEqual(code, 0, out)
        self.assertIn("recorded screen-scheduled on 2026-09-25 (Friday, 4 days ago)\n", out)
        self.assertIn("due 2026-09-30 (Wednesday, tomorrow)\n", out)
        self.assertNotIn("WARN", out)
        code, out = self.event("note", "--date", "2026-09-26", "--due", "2026-10-02",
                               "--today", "2026-09-26")
        self.assertIn("recorded note on 2026-09-26 (Saturday, today)\n", out)
        self.assertIn("due 2026-10-02 (Friday, in 6 days)\n", out)

    def test_a_date_after_today_is_recorded_with_a_warning(self):
        """Every kind's date is the day it happened, a booking's too - so a future one is
        arithmetic gone wrong. A WARN, not a refusal: the person may have said so."""
        code, out = self.event("interview-done", "--date", "2026-09-30", "--today", "2026-09-26")
        self.assertEqual(code, 0, out)
        self.assertIn("added    k:evt_contoso_platform_2026_09_30_interview_done", out)
        self.assertIn("recorded interview-done on 2026-09-30 (Wednesday, in 4 days)\n", out)
        self.assertIn("WARN  2026-09-30 is after today", out)
        self.assertIn("--due of its -scheduled event", out)

    def test_a_bad_today_is_a_call_error(self):
        code, out = self.event("note", "--date", "2026-09-26", "--today", "Saturday")
        self.assertEqual(code, 2, out)

    def test_an_event_that_would_not_validate_is_never_written(self):
        """The workspace is loaded with the event in it before the file is replaced. The
        flags are checked first, so reaching this takes an event the command itself got
        wrong - which is what the check is for."""
        from jsk.domain.timeline import events as timeline

        real = timeline.event_quads

        def broken(*args, **kwargs):
            iri, quads = real(*args, **kwargs)
            return iri, quads + [timeline.quad(iri, "due", timeline.lit("soon"))]
        before = self.record
        with mock.patch.object(timeline, "event_quads", broken):
            code, out = self.event("note", "--date", "2026-09-27")
        self.assertEqual(code, 1, out)
        self.assertIn("would leave", out)
        self.assertEqual(self.record, before)

    def test_an_unfrozen_application_has_no_record_to_add_to(self):
        code, out = self.jsk("app", "event", self.root / "applications" / "elsewhere-x", "note",
                             "--date", "2026-09-27")
        self.assertEqual(code, 2, out)
        (self.root / "applications" / "elsewhere-x").mkdir()
        code, out = self.jsk("app", "event", self.root / "applications" / "elsewhere-x", "note",
                             "--date", "2026-09-27")
        self.assertEqual(code, 1, out)
        self.assertIn("holds no application record", out)
        self.assertIn("jsk app freeze", out)

    def test_a_directory_outside_applications_is_a_call_error(self):
        code, out = self.jsk("app", "event", self.root / "career", "note", "--date", "2026-09-27")
        self.assertEqual(code, 2, out)
        self.assertIn("not in an applications/ folder", out)

    def test_a_markdown_application_is_pointed_at_its_timeline_table(self):
        md = self.root / "applications" / "old"
        md.mkdir()
        (md / "application.md").write_text("---\n---\n", encoding="utf-8")
        code, out = self.jsk("app", "event", md, "note", "--date", "2026-09-27")
        self.assertEqual(code, 1, out)
        self.assertIn("# Timeline", out)


if __name__ == "__main__":
    unittest.main()
