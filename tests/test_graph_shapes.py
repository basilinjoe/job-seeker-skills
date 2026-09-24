"""Tier 1: every per-file rule fires, at the right place, on the one edit that breaks it.

The fixture workspace is valid. Each mutation below is one edit a person or an agent
could plausibly make; the test copies the workspace, makes the edit, loads it and
asserts that the named rule reports the named id at that id's line. A rule with no
mutation fails `test_every_rule_has_a_mutation` - no rule exists without proof that it
fires. tests/test_graph_rules.py does the same for tier 2.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import shapes, store

FIXTURES = Path(__file__).parent / "graph_fixtures"


def load(root):
    """A workspace loaded against its own vocabulary.ttl, not the shipped one: the fixtures'
    hand-worked answers must not move when the shipped vocabulary grows."""
    return store.load(root, vocabulary=Path(root) / "vocabulary.ttl")

KB = "career/kb.ttl"
POSTING = "applications/acme-platform-engineer/posting.ttl"
APPLICATION = "applications/acme-platform-engineer/application.ttl"

# rule: (file, old text, new text, focus id, the fix contains). old=None appends new.
MUTATIONS = {
    "syntax": (KB, 'j:rank 2 ;', 'j:rank 2 ,;', "", "fix the syntax"),
    "id-form": (KB, "k:ach_clinical_events_led_migration", "k:ach_clinical_events_2",
                "k:ach_clinical_events_2", "name it after its content"),
    "id-home": (POSTING, None, '\nk:pos_stray j:organisation k:org_meridian .\n',
                "k:pos_stray", "move it to kb.ttl"),
    "closed": (KB, 'j:size "1001-5000"', 'j:sise "1001-5000"', "k:org_meridian",
               "did you mean j:size?"),
    "cardinality": (KB, 'j:start "2020-02" ; j:end "2023-06" ; j:state j:ended ;',
                    'j:start "2020-02" ; j:end "2023-06" ;', "k:pos_meridian_senior",
                    "add j:state"),
    "object": (KB, "j:workMode j:hybrid", "j:workMode j:hybird", "k:person", "j:onsite"),
    "no-blank-nodes": (KB, None, "\nk:met_team j:note _:b1 .\n", "k:met_team",
                       "give the node an id"),
    "no-derived": (KB, "k:org_northbridge j:name", "k:org_northbridge a j:Organisation ; j:name",
                   "k:org_northbridge", "delete the `a"),
    "retired-reason": (KB, ' j:reason "Too old and too small to earn a line." ;', "",
                       "k:prj_intranet_refresh", "add j:reason"),
    "comment": (KB, "# == Metrics", "# remember to ask about this\n# == Metrics", "",
                "j:note"),
    "shipped-vocabulary": ("vocabulary.ttl", 'c:docker a j:Technology ; j:label "Docker" .',
                           'c:docker a j:Capability ; j:label "Docker" .', "c:docker",
                           "move it into a person's kb.ttl"),
}


def mutated(mutation):
    """A loaded copy of the fixture workspace with one (file, old, new, ...) edit applied;
    returns the store and the edited file's text."""
    file, old, new = mutation[:3]
    tmp = tempfile.mkdtemp()
    shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
    path = Path(tmp) / file
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if old is None:
        text += new
    else:
        assert old in text, f"{old!r} is not in {file}"
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")
    try:
        return load(tmp), text
    finally:
        shutil.rmtree(tmp)


def assert_fires(case, rule, mutation):
    """`rule` reports `focus` at the line that id starts on, with the expected fix."""
    _, _, _, focus, fix = mutation
    s, text = mutated(mutation)
    hits = [f for f in s.findings if f.rule == rule and f.focus == focus]
    case.assertTrue(hits, f"{rule} did not fire on {focus!r}: {[f.text() for f in s.findings]}")
    # Exactly once: one edit, one finding of its rule - a rule that fires twice for one
    # fault doubles what a person has to read, and hides which line is the real one.
    case.assertEqual(len([f for f in s.findings if f.rule == rule]), 1,
                     f"{rule} fired more than once: {[f.text() for f in s.findings]}")
    hit = hits[0]
    if focus:
        line = text.split("\n")[hit.line - 1]
        case.assertTrue(line.startswith(focus + " "), f"{rule}: line {hit.line} is {line!r}")
    case.assertIn(fix, hit.fix)
    return hit


class TheFixtureIsClean(unittest.TestCase):
    def test_no_findings(self):
        s = load(FIXTURES)
        self.assertEqual([f.text() for f in s.findings], [])


class EveryRuleFires(unittest.TestCase):
    def test_every_rule_has_a_mutation(self):
        self.assertEqual(set(shapes.TIER1), set(MUTATIONS))

    def test_each_mutation_fires_its_rule_at_the_right_line(self):
        for rule, mutation in MUTATIONS.items():
            with self.subTest(rule=rule):
                assert_fires(self, rule, mutation)

    def test_the_comment_finding_points_at_the_comment(self):
        hit = assert_fires(self, "comment", MUTATIONS["comment"])
        _, text = mutated(MUTATIONS["comment"])
        self.assertEqual(text.split("\n")[hit.line - 1], "# remember to ask about this")
        self.assertEqual(hit.severity, "WARN")


class Findings(unittest.TestCase):
    def test_a_syntax_error_stops_only_its_own_file(self):
        s, _ = mutated(MUTATIONS["syntax"])
        self.assertEqual([f.file for f in s.findings if f.rule == "syntax"], [KB])
        self.assertIn(POSTING, s.parsed)

    def test_an_unknown_predicate_names_the_nearest(self):
        s, _ = mutated(MUTATIONS["closed"])
        [f] = [f for f in s.findings if f.rule == "closed"]
        self.assertRegex(f.text(), r"^career/kb\.ttl:\d+ k:org_meridian - j:sise is not an? "
                                   r"Organisation predicate\n        fix: did you mean j:size\?$")

    def test_an_empty_kb_is_not_a_valid_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "career").mkdir()
            (Path(tmp) / "career" / "kb.ttl").write_text("", encoding="utf-8")
            s = store.load(tmp)
        [f] = [f for f in s.findings if f.rule == "cardinality"]
        self.assertEqual((f.file, f.line), (KB, 0))
        self.assertIn("exactly one KB; this one holds 0", f.detail)

    def test_one_posting_per_posting_file(self):
        s, _ = mutated((POSTING, None, '\nk:post_other j:company "B" ; j:title "T" ; '
                        'j:captured "2026-09-01"^^xsd:date ; j:advert "posting.md" .\n', "", ""))
        self.assertTrue([f for f in s.findings if f.rule == "cardinality" and f.file == POSTING
                         and "holds 2" in f.detail])

    def test_a_line_copied_twice_is_one_fact_not_two(self):
        line = 'k:met_team j:subject "engineers led" ; j:unit "engineers" .'
        s, _ = mutated((KB, line, line + "\n" + line, "", ""))
        self.assertEqual([f.text() for f in s.findings], [])

    def test_an_impossible_date_is_refused(self):
        s, _ = mutated((KB, 'j:answered "2026-08-14"', 'j:answered "2026-02-30"', "", ""))
        self.assertTrue([f for f in s.findings if f.rule == "object"
                         and f.focus == "k:q_team_size" and "2026-02-30" in f.detail])

    def test_digits_are_ascii_digits(self):
        s, _ = mutated((KB, 'j:start "2016-08"', 'j:start "２０１６"', "", ""))
        self.assertTrue([f for f in s.findings if f.rule == "object"
                         and f.focus == "k:pos_northbridge_architect"])

    def test_a_syntax_error_is_not_buried_under_what_it_hid(self):
        """One typo in kb.ttl makes every id in it unreadable, so every reference to
        them would be `dangling` - with a confident "did you mean" each. The references
        cannot be judged until the file parses; the syntax error is the finding."""
        s, _ = mutated(MUTATIONS["syntax"])
        self.assertEqual([f.rule for f in s.findings if f.rule == "dangling"], [])
        self.assertTrue(s.report().fails[0].startswith(KB))

    def test_report_is_a_validate_urs_report(self):
        s, _ = mutated(MUTATIONS["object"])
        rep = s.report()
        self.assertEqual((len(rep.fails), len(rep.warns)), (len(s.fails()), len(s.warns())))
        self.assertTrue(rep.fails)


if __name__ == "__main__":
    unittest.main()
