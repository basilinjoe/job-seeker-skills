"""`jsk match --draft-gaps`: code writes gaps.md from the match, the analyst fills the slots.

The draft is only worth writing if `--gaps` accepts it once the slots are filled - otherwise the
analyst is back to fixing rows by hand - and refuses it while any slot is still open.
"""
import contextlib
import datetime
import io
import re
import tempfile
import unittest
from pathlib import Path

from jsk.graph import gapsdraft as G
from jsk.graph import match as M
from jsk.graph import ontology as O
from jsk.graph import store

FIXTURES = Path(__file__).parent / "match_fixtures"
TODAY = datetime.date(2026, 9, 24)
SLOT = re.compile(r"<!-- jsk:.*?-->", re.S)


def section(text, heading):
    """The lines under `heading` up to the next heading of the same level or higher."""
    level = len(heading) - len(heading.lstrip("#"))
    out, inside = [], False
    for line in text.split("\n"):
        if line.startswith("#") and len(line) - len(line.lstrip("#")) <= level:
            if inside:
                break
            inside = line == heading
        elif inside:
            out.append(line)
    return "\n".join(out).strip("\n")


class Draft(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = store.load(FIXTURES, vocabulary=FIXTURES / "vocabulary.ttl")
        cls.r, cls.text = {}, {}
        for p in ("contoso", "fabrikam", "northwind", "tailspin"):
            post = O.K + "post_" + p
            cls.r[p] = M.result(cls.s, post, TODAY, 3)
            cls.text[p] = G.draft_gaps(cls.r[p], cls.s, post, TODAY,
                                       str(FIXTURES / "applications" / p / "posting.md"))

    def check(self, posting, text):
        """report_gaps' exit code and printed lines, for `text` as gaps.md."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gaps.md"
            path.write_text(text, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = M.report_gaps(self.r[posting], str(path))
        return code, out.getvalue().splitlines()

    def test_a_fresh_draft_fails_once_per_slot_and_nothing_else(self):
        for p, text in self.text.items():
            slots = [n for n, line in enumerate(text.split("\n"), 1) if "<!-- jsk:" in line]
            code, out = self.check(p, text)
            self.assertEqual(code, 1)
            self.assertEqual([x for x in out if x.startswith(("FAIL", "WARN"))],
                             [f"FAIL  line {n}: unfilled slot" for n in slots], p)
            self.assertTrue(out[-1].endswith(f"{len(slots)} FAIL, 0 WARN"), out[-1])

    def test_the_filled_draft_passes_clean(self):
        """Every row comes from a requirement id, so nothing drifts: 0 FAIL and 0 WARN."""
        for p, text in self.text.items():
            code, out = self.check(p, SLOT.sub("filled in", text))
            self.assertEqual((code, out[-1].split(": ")[-1]),
                             (0, f"{len(self.r[p]['requirements'])} rows, 0 FAIL, 0 WARN"), out)

    def rows(self, posting):
        return {row["requirement"]: row for row in M.gaps_table(self.text[posting])}

    def test_implicit_rows_are_indeterminate_with_the_implicit_shortfall(self):
        self.assertEqual(self.rows("contoso")["Mentoring"],
                         {"requirement": "Mentoring", "need": "implicit",
                          "verdict": "indeterminate", "evidence": "",
                          "shortfall": "implicit — the match does not assess it"})

    def test_verdicts_are_the_match_and_evidence_cites_ids(self):
        rows = self.rows("contoso")
        self.assertEqual({q["asked"]: q["verdict"] or "indeterminate"
                          for q in self.r["contoso"]["requirements"]},
                         {k: v["verdict"] for k, v in rows.items()})
        for row in rows.values():
            if row["verdict"] in ("satisfied", "partial"):
                self.assertTrue(M.cites_id(row["evidence"]), row)
            self.assertEqual(row["shortfall"] == "", row["verdict"] == "satisfied", row)
        self.assertEqual(rows["K8s"]["evidence"], "prj_events")      # the confirmed carrier only
        self.assertEqual(rows[".NET"]["evidence"], "prj_events (tag), prj_identity (tag)")
        self.assertEqual(rows["EKS"]["evidence"], "prj_data")        # near, for a partial
        self.assertEqual(self.rows("northwind")["Python"]["evidence"], "prj_data (unconfirmed)")

    def test_the_ranking_is_the_match_s(self):
        printed = M.markdown(self.r["contoso"])
        self.assertEqual(section(self.text["contoso"], "# Ranking"),
                         section(printed, "## Ranking") + "\n\n" + section(printed, "## Cover"))

    def test_questions_keep_the_match_s_wording_in_the_analyst_s_order(self):
        qs = section(self.text["contoso"], "# Questions").split("\n")
        self.assertIn("blocking", qs[0])
        kinds = [re.match(r"- \*\*([a-z-]+)\*\*", q)[1] for q in qs if q.startswith("- **")]
        self.assertEqual(kinds, ["broader-held", "implied", "tag-only", "missing-metric",
                                 "ambiguous", "unknown-term"])
        for q in self.r["contoso"]["questions"]:
            self.assertIn(M.question_line(q), qs)
        self.assertIn("reword each to be said aloud", qs[-1])
        # A required requirement nothing carries is unmet, and asked before the unconfirmed.
        fab = section(self.text["fabrikam"], "# Questions").split("\n")
        self.assertTrue(fab[1].startswith("- **unsatisfied** .NET Framework: required"), fab)
        self.assertNotIn("Angular", "\n".join(fab))                  # preferred: not unmet

    def test_new_terms_hold_the_candidates(self):
        self.assertEqual(section(self.text["contoso"], "# New terms"),
                         "- **K3s** — candidate: no concept holds it.")
        self.assertEqual(section(self.text["fabrikam"], "# New terms"), "None.")

    def test_decisions_drops_reach_new_terms_but_eligibility_drops_do_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            advert = Path(tmp) / "posting.md"
            advert.write_text("Senior Developer at Fabrikam\n\n## Requirements\n\n"
                              "- Years of .NET Framework.\n- Origin CI, Kargo and WoK, our "
                              "internal tooling, which you will learn on the job over your first "
                              "quarter.\n- Must hold a UK work visa.\n", encoding="utf-8")
            (Path(tmp) / "decisions.txt").write_text(
                "company: Fabrikam\n\n# n | slug | asked | concepts | need\n"
                "2 | dotnet_framework | .NET Framework | - |\n3 | - | internal tooling\n"
                "4 | - | eligibility: judged under # Eligibility\n", encoding="utf-8")
            text = G.draft_gaps(self.r["fabrikam"], self.s, O.K + "post_fabrikam", TODAY,
                                str(advert))
        terms = section(text, "# New terms").split("\n")
        self.assertEqual(len(terms), 1, terms)
        self.assertTrue(terms[0].startswith("- **Origin CI, Kargo and WoK, our internal"), terms)
        self.assertTrue(terms[0].endswith("…** — dropped: internal tooling"), terms)
        self.assertLessEqual(len(terms[0].split("**")[1]), G.CUT + 1)
        self.assertIn('advert: "Must hold a UK work visa."', section(text, "# Eligibility"))

    def test_no_decisions_file_is_a_legacy_posting_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = G.draft_gaps(self.r["fabrikam"], self.s, O.K + "post_fabrikam", TODAY,
                                str(Path(tmp) / "posting.md"))
        self.assertEqual(section(text, "# New terms"), "None.")

    def test_eligibility_lists_the_person_facts(self):
        elig = section(self.text["contoso"], "# Eligibility")
        self.assertTrue(elig.startswith("<!-- jsk: judge eligibility"), elig)
        self.assertIn("  location: not recorded", elig)
        self.assertIn("  advert: nothing it says is about eligibility", elig)
        self.assertTrue(elig.endswith("-->"), elig)

    def test_frontmatter(self):
        self.assertTrue(self.text["contoso"].startswith(
            "---\ntype: Gap Assessment\nposting: posting.ttl\nassessed: 2026-09-24\n"
            "fit: <!-- jsk: strong | partial | poor -->\n---\n"))


if __name__ == "__main__":
    unittest.main()
