"""decisions.txt: the analyst's choices for an application made from files. Nothing writes one
since 6.0 retired `jsk posting build`; a frozen application's is still read, for the advert
lines it drops (Ruling 2 of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md), so its
format is still pinned here."""
import unittest

import fixtures  # noqa: F401  (puts src/ on the path)

from jsk.domain.record import decisions

GOOD = """company: JumpCloud
title: Staff Software Engineer, PAM / PWM - India
captured: 2026-09-26

# n | slug | asked | concepts | need
17 | csharp | C# | c:csharp | required
17 | grpc | gRPC | - |
18 | pam_tools | CyberArk, BeyondTrust | c:cyberark, c:beyondtrust
2  | anchor | primary technical anchor | - | implicit
12 | - | internal tooling - Origin CI, Kargo, WoK
"""


class Parse(unittest.TestCase):
    def test_header_rows_and_drops(self):
        d = decisions.parse(GOOD)
        self.assertEqual(d.header, {"company": "JumpCloud",
                                    "title": "Staff Software Engineer, PAM / PWM - India",
                                    "captured": "2026-09-26"})
        self.assertEqual([(r.n, r.slug, r.asked, r.concepts, r.need) for r in d.rows], [
            (17, "csharp", "C#", ("c:csharp",), "required"),
            (17, "grpc", "gRPC", (), None),
            (18, "pam_tools", "CyberArk, BeyondTrust", ("c:cyberark", "c:beyondtrust"), None),
            (2, "anchor", "primary technical anchor", (), "implicit")])
        self.assertEqual([(x.n, x.reason) for x in d.drops],
                         [(12, "internal tooling - Origin CI, Kargo, WoK")])

    def test_each_bad_line_is_named(self):
        for text, said in (
                ("17 | csharp | C#", "has 3 fields"),
                ("17 | C Sharp | C# | - |", "slug"),
                ("17 | csharp | | - |", "`asked` is empty"),
                ("17 | csharp | C# | - | must", "need 'must'"),
                ("17 | csharp | C# | csharp |", "write it c:<slug>"),
                ("12 | - |", "a drop needs its reason"),
                ("12 | - | internal | tooling", "holds a `|`"),
                ("teh company: x", "neither"),
                ("17 | csharp | C# | - |\ncompany: x", "after the rows"),
                ("company: a\ncompany: b", "twice")):
            with self.subTest(text=text):
                with self.assertRaises(decisions.DecisionsError) as caught:
                    decisions.parse(text)
                self.assertIn(said, str(caught.exception))
                self.assertIn("line ", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
