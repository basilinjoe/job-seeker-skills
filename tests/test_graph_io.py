"""Reading a record file: its triples, where each subject starts, and what a rewrite
would lose. Errors name file:line:column, because a person fixes a hand edit by going
to that line.
"""
import tempfile
import unittest
from pathlib import Path

from jsk.graph import io
from jsk.graph import ontology as O

PFX = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES)


class Reading(unittest.TestCase):
    def test_syntax_error_names_file_line_and_column(self):
        with self.assertRaises(io.GraphError) as cm:
            io.parse_text(PFX + "k:org_x j:name \"A\" ;\n    j:size ,, .\n", "career/kb.ttl")
        e = cm.exception
        self.assertEqual((e.file, e.line), ("career/kb.ttl", 6))
        self.assertIsNotNone(e.col)
        self.assertIn("career/kb.ttl:6:", str(e))

    def test_crlf_and_bom_read_as_lf(self):
        text = "﻿" + (PFX + 'k:org_x j:name """two\r\nlines""" .\r\n')
        parsed = io.parse_text(text, "kb.ttl")
        self.assertEqual(parsed.quads[0].object.value, "two\nlines")

    def test_the_kind_comes_from_the_file_name(self):
        self.assertEqual(io.parse_text(PFX, "applications/a/posting.ttl").kind, "posting")

    def test_subject_lines_point_at_the_first_line_of_each_subject(self):
        text = (PFX + '\nk:met_team j:subject "engineers led" .\n'
                "k:met_team.v1 j:of k:met_team ;\n    j:value 6 .\n\n"
                "c:kafka j:isA c:event-driven-architecture .\n")
        lines = io.parse_text(text, "kb.ttl").lines
        self.assertEqual((lines[O.K + "met_team"], lines[O.K + "met_team.v1"],
                          lines[O.C + "kafka"]), (6, 7, 10))

    def test_comments_are_found_but_banners_and_hashes_in_strings_are_not(self):
        text = (PFX + "# == Skills\n\n# my own note\n"
                'k:skill_dotnet j:name "C# / .NET" ; j:category "language" .  # trailing\n'
                'k:os_x j:name "x" ; j:url <https://x/#frag> .\n'
                'k:prj_x j:problem """A # in prose\nis prose.""" .\n')
        found = io.parse_text(text, "kb.ttl").comments
        self.assertEqual(found, [(7, "# my own note"), (8, "# trailing")])

    def test_a_file_with_no_hash_has_no_comments(self):
        self.assertEqual(io.comments('k:x j:name "y" .\n'), [])

    def test_a_non_utf8_file_is_an_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kb.ttl"
            path.write_bytes(b'k:org_x j:name "caf\xe9" .')
            with self.assertRaises(io.GraphError) as cm:
                io.parse(path)
            self.assertIn("not UTF-8", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
