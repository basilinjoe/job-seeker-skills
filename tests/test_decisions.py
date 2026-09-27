"""decisions.txt: the analyst's choices, read before `jsk posting build` writes anything."""
import unittest

import fixtures  # noqa: F401  (puts src/ on the path)

from jsk.graph import decisions as D

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
        d = D.parse(GOOD)
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
                ("teh company: x", "neither"),
                ("17 | csharp | C# | - |\ncompany: x", "after the rows"),
                ("company: a\ncompany: b", "twice")):
            with self.subTest(text=text):
                with self.assertRaises(D.DecisionsError) as caught:
                    D.parse(text)
                self.assertIn(said, str(caught.exception))
                self.assertIn("line ", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
