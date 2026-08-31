"""The write core: emit, splice, stage, commit.

Every test here pins a rule from
docs/superpowers/specs/2026-08-31-okf-write-cli-design.md. The rules that matter
most are the ones about not touching what the command was not asked to touch: a
person's bundle is hand-editable by design, and a tool that reflows their file is
a tool they stop running.
"""
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import INIT_BUNDLE, PIPELINE_MODEL, authoring_module, load_script

concept = authoring_module("authoring.concept")
init_bundle = load_script(INIT_BUNDLE)
pipeline_model = load_script(PIPELINE_MODEL)


class Quoting(unittest.TestCase):
    def test_prose_is_double_quoted(self):
        self.assertEqual(concept.scalar("Acme - the platform"), '"Acme - the platform"')

    def test_embedded_quote_is_escaped(self):
        self.assertEqual(concept.scalar('He said "no"'), '"He said \\"no\\""')

    def test_slug_is_bare(self):
        self.assertEqual(concept.scalar("architecture-ownership"),
                         "architecture-ownership")

    def test_integer_is_bare(self):
        self.assertEqual(concept.scalar(5), "5")

    def test_list_is_flow_style(self):
        self.assertEqual(concept.scalar(["healthcare", "aged-care"]),
                         "[healthcare, aged-care]")

    def test_colon_forces_quoting(self):
        # bundle-spec.md: "Quote the value if it contains a colon."
        self.assertEqual(concept.scalar("latency: 5 min"), '"latency: 5 min"')

    def test_a_trailing_newline_does_not_escape_quoting(self):
        # `$` matches before a trailing newline in Python, so a value ending in
        # one used to be emitted bare and end its own frontmatter line early.
        self.assertEqual(concept.scalar("abc\n"), '"abc\\n"')

    def test_an_embedded_newline_stays_on_one_line(self):
        # A quoted value spanning two physical lines breaks set_key(), which
        # finds a key by scanning lines and would rewrite the wrong one.
        self.assertEqual(concept.scalar("a\nb"), '"a\\nb"')

    def test_a_tab_is_escaped(self):
        self.assertEqual(concept.scalar("tab\there"), '"tab\\there"')

    def test_a_backslash_is_doubled(self):
        self.assertEqual(concept.scalar("back\\slash"), '"back\\\\slash"')

    def test_the_backslash_rule_runs_before_the_others(self):
        # A literal backslash-n must not become an escaped newline. If the
        # newline rule ran first, this would read back as "a\nb".
        self.assertEqual(concept.scalar("a\\nb"), '"a\\\\nb"')

    def test_a_forbidden_control_character_is_escaped(self):
        # A form feed is what PDF text extraction leaves at a page boundary, and
        # raw in the block it makes the whole concept unreadable to safe_load.
        self.assertEqual(concept.scalar("a\x0cb"), '"a\\x0cb"')

    def test_a_null_byte_is_escaped(self):
        self.assertEqual(concept.scalar("a\x00b"), '"a\\x00b"')

    def test_a_unicode_line_separator_is_escaped(self):
        # str.splitlines() breaks on these, so an unescaped one ends a value
        # early for any reader that scans lines - silently, in U+0085's case.
        self.assertEqual(concept.scalar("a\u2028b"), '"a\\u2028b"')
        self.assertEqual(concept.scalar("a\x85b"), '"a\\x85b"')

    def test_yaml_keywords_are_quoted(self):
        for word in ("no", "yes", "true", "false", "null", "on", "off", "Yes"):
            with self.subTest(word=word):
                self.assertEqual(concept.scalar(word), '"%s"' % word)

    def test_numeric_looking_strings_are_quoted(self):
        for text in ("007", "42", "1.0", "0x1f"):
            with self.subTest(text=text):
                self.assertEqual(concept.scalar(text), '"%s"' % text)

    def test_yaml_digit_separators_are_quoted(self):
        # PyYAML's int resolver allows `_`, and so does BARE, so "12_000" was
        # emitted bare and read back as the integer 12000.
        for text in ("12_000", "0_7", "1_0", "1_0.0", "5."):
            with self.subTest(text=text):
                self.assertEqual(concept.scalar(text), '"%s"' % text)

    def test_dates_and_years_are_emitted_bare(self):
        # bundle-spec.md writes all three precisions bare and reads precision
        # from what was written. Quoting one of them would make a generated
        # concept disagree with a hand-edited one about the same field.
        for text in ("2019", "2019-04", "2026-08-31"):
            with self.subTest(text=text):
                self.assertEqual(concept.scalar(text), text)

    def test_a_full_date_reads_back_as_a_date(self):
        # The one deliberate exception to the round-trip guarantee, pinned so a
        # later tightening cannot quietly remove it.
        import datetime
        import yaml
        parsed = yaml.safe_load("start: " + concept.scalar("2026-08-31"))
        self.assertEqual(parsed["start"], datetime.date(2026, 8, 31))

    def test_escaped_values_read_back_as_themselves(self):
        # The emitter's contract: whatever pyyaml reads back must equal what was
        # handed in, or a concept quietly stops saying what its author said.
        import yaml
        for raw in ("abc\n", "a\nb", "tab\there", 'say "hi"', "back\\slash",
                    "latency: 5 min"):
            with self.subTest(raw=raw):
                parsed = yaml.safe_load("title: " + concept.scalar(raw))
                self.assertEqual(parsed["title"], raw)

    def test_every_emitted_value_survives_a_round_trip(self):
        import yaml
        cases = ("a\x0cb", "a\x00b", "a\u2028b", "a\x85b", "no", "007", "1.0",
                 "12_000", "5.", "abc\n", "a\nb", 'say "hi"', "back\\slash",
                 " lead", "trail ", "", "café-ops", "日本語", "x" * 5000)
        for raw in cases:
            with self.subTest(raw=raw):
                line = "title: " + concept.scalar(raw)
                self.assertEqual(len(line.splitlines()), 1)
                self.assertEqual(yaml.safe_load(line)["title"], raw)


class Types(unittest.TestCase):
    def test_a_float_is_bare(self):
        self.assertEqual(concept.scalar(1.5), "1.5")

    def test_an_unmodelled_type_is_refused(self):
        # str() used to turn None into the bare word "None" and a dict into a
        # quoted repr, so a caller building a list from optional fields wrote
        # the literal word None into somebody's concept.
        for value in (None, {"a": 1}, b"x", object()):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    concept.scalar(value)

    def test_a_none_inside_a_list_is_refused(self):
        with self.assertRaises(ValueError):
            concept.scalar(["a", None])


class Emitting(unittest.TestCase):
    def test_new_concept_has_frontmatter_and_body(self):
        text = concept.new("Project",
                           {"title": "Care platform", "strength": 5},
                           "# The problem\n\nIt was slow.\n")
        self.assertTrue(text.startswith("---\ntype: Project\n"))
        self.assertIn('title: "Care platform"\n', text)
        self.assertIn("strength: 5\n", text)
        self.assertIn("\n---\n\n# The problem\n", text)

    def test_type_is_always_first(self):
        text = concept.new("Role", {"title": "Engineer"}, "")
        lines = text.splitlines()
        self.assertEqual(lines[0], "---")
        self.assertEqual(lines[1], "type: Role")

    def test_none_values_are_omitted(self):
        text = concept.new("Project", {"title": "X", "end": None}, "")
        self.assertNotIn("end:", text)

    def test_a_whole_emitted_block_parses(self):
        import yaml
        text = concept.new("Project", {
            "title": 'Acme: the "flagship" - care platform',
            "tags": ["healthcare", "azure"],
            "strength": 5,
            "recency": 2026,
            "start": "2019-04",
            "status": "confirmed",
        }, "# The problem\n\nIt was slow.\n")
        block = text.split("---\n")[1]
        meta = yaml.safe_load(block)
        self.assertEqual(meta["type"], "Project")
        self.assertEqual(meta["title"], 'Acme: the "flagship" - care platform')
        self.assertEqual(meta["tags"], ["healthcare", "azure"])
        self.assertEqual(meta["strength"], 5)
        self.assertEqual(meta["recency"], 2026)


class BarePython(unittest.TestCase):
    """init_bundle.py runs on a bare Python, and it imports this module.

    ARCHITECTURE.md lists it among the scripts that need no dependency at all.
    A module-level `import yaml` here would break that, and the failure would
    surface on somebody else's machine as a broken install. A source grep is
    deliberately not the check: a later task guards its own yaml import behind
    try/except, which is correct and which a grep would fail.
    """

    def test_the_emitter_imports_with_no_pyyaml(self):
        import builtins
        import importlib
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "yaml" or name.startswith("yaml."):
                raise ImportError("pyyaml is blocked for this test")
            return real_import(name, *args, **kwargs)

        for name in [m for m in list(sys.modules) if m.startswith("yaml")]:
            del sys.modules[name]
        del sys.modules["authoring.concept"]
        builtins.__import__ = blocked
        try:
            fresh = importlib.import_module("authoring.concept")
            self.assertEqual(fresh.scalar("architecture-ownership"),
                             "architecture-ownership")
        finally:
            builtins.__import__ = real_import
            del sys.modules["authoring.concept"]
            importlib.import_module("authoring.concept")


class OneEmitter(unittest.TestCase):
    """init_bundle.py must not define the format a second time.

    The spec forbids a second definition. This is the mechanical form of that
    rule: the scaffolder's emitter and the write layer's emitter are the same
    object, so they cannot drift into quoting a title differently.
    """

    def test_scaffolded_frontmatter_matches_the_emitter(self):
        self.assertEqual(
            init_bundle.fm("Index", 'A "quoted" name', "Desc",
                           "2026-01-01T00:00:00Z"),
            concept.frontmatter("Index", {
                "title": 'A "quoted" name',
                "description": "Desc",
                "timestamp": "2026-01-01T00:00:00Z",
            }) + "\n")

    def test_trailing_keys_go_through_the_emitter_too(self):
        # The revision stamp and `status: needs-verification` used to be spliced
        # in as a preformatted block, which meant two of the scaffolder's keys
        # never met the emitter at all.
        self.assertEqual(
            init_bundle.fm("Index", "Root", "Desc", "2026-01-01T00:00:00Z",
                           {"okf_bundle": 7}),
            concept.frontmatter("Index", {
                "title": "Root", "description": "Desc",
                "timestamp": "2026-01-01T00:00:00Z", "okf_bundle": 7,
            }) + "\n")

    def test_the_pipeline_vocabulary_uses_the_shared_emitter(self):
        """The last hand-formatted frontmatter block in the scaffolder.

        It emitted `timestamp:` bare, which safe_load returns as a datetime -
        the shape okf_compile.dump_record records as having ended a compile in a
        TypeError. One definition of the format means this one too.

        Both assertions earn their place: the block one pins the mechanism, and
        a hand-written `timestamp: "..."` f-string would satisfy the round-trip
        alone.
        """
        import yaml
        text = pipeline_model.vocabulary_markdown("2026-01-01T00:00:00Z")
        self.assertTrue(text.startswith(concept.frontmatter("Vocabulary", {
            "title": "Pipeline vocabulary",
            "description": "The event values an application timeline may use. "
                           "Exact strings.",
            "timestamp": "2026-01-01T00:00:00Z",
            "status": "confirmed",
        })))
        meta = yaml.safe_load(text.split("---")[1])
        self.assertIsInstance(meta["timestamp"], str)
        self.assertEqual(meta["timestamp"], "2026-01-01T00:00:00Z")


HAND_WRITTEN = """---
type: Project
# I keep the strength here so I remember to revisit it
title: "Care platform"
strength: 3
capabilities: [ai-platform-architecture]

status: confirmed
---

# The problem

It was slow.
"""


def write_lf(path, text):
    """Write `text` with its line endings intact.

    write_text() goes through text mode, which on Windows turns every "\\n" into
    "\\r\\n" - so the LF fixtures below were landing on disk as CRLF and the tests
    that pin LF behaviour were silently exercising the CRLF path instead. Bytes,
    so a fixture that says LF is LF on every platform.
    """
    path.write_bytes(text.encode("utf-8"))
    return path


class Reading(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = write_lf(Path(self.dir) / "care-platform.md", HAND_WRITTEN)

    def test_meta_is_parsed(self):
        doc = concept.read(self.path)
        self.assertEqual(doc.meta["type"], "Project")
        self.assertEqual(doc.meta["strength"], 3)

    def test_body_is_kept_verbatim(self):
        doc = concept.read(self.path)
        self.assertEqual(doc.body, "# The problem\n\nIt was slow.\n")

    def test_missing_frontmatter_is_refused(self):
        path = write_lf(Path(self.dir) / "bare.md", "# Just a heading\n")
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.read(path)
        self.assertIn("no frontmatter", str(caught.exception))

    def test_a_byte_order_mark_is_named_as_the_cause(self):
        # Notepad and PowerShell redirection both write one. "no frontmatter" is
        # visibly untrue of a file whose first visible characters are --- and
        # sends the reader looking at the wrong line.
        path = write_lf(Path(self.dir) / "bom.md",
                        "\ufeff---\ntype: Project\n---\n\nx\n")
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.read(path)
        self.assertIn("byte-order mark", str(caught.exception))

    def test_reading_and_rewriting_changes_nothing(self):
        """read() then text() with no edit must be byte-identical.

        D2 was a blank line invented on every splice; D4 is one invented when a
        block empties. Both are the same defect - a byte nobody asked about -
        and one property catches every future member of the family.
        """
        for name, raw in (
                ("lf", HAND_WRITTEN),
                ("crlf", HAND_WRITTEN.replace("\n", "\r\n")),
                ("no-gap", "---\ntype: Project\n---\n# Body\n"),
                ("wide-gap", "---\ntype: Project\n---\n\n\n\n# Body\n"),
                ("no-trailing-newline", "---\ntype: Project\n---\n\n# Body"),
                ("empty-body", "---\ntype: Project\n---\n"),
                ("one-trailing-blank", "---\ntype: Project\n\n---\n\n# Body\n"),
                ("two-trailing-blanks", "---\ntype: Project\n\n\n---\n\n# Body\n"),
        ):
            with self.subTest(name=name):
                path = Path(self.dir) / f"{name}.md"
                path.write_bytes(raw.encode("utf-8"))
                self.assertEqual(concept.read(path).text(), raw)


class Splicing(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = write_lf(Path(self.dir) / "care-platform.md", HAND_WRITTEN)
        self.doc = concept.read(self.path)

    def test_changing_one_key_changes_one_line(self):
        after = concept.set_key(self.doc, "strength", 5)
        before_lines = HAND_WRITTEN.splitlines()
        after_lines = after.splitlines()
        differing = [i for i, (a, b) in enumerate(zip(before_lines, after_lines))
                     if a != b]
        self.assertEqual(len(differing), 1)
        self.assertEqual(after_lines[differing[0]], "strength: 5")

    def test_comments_and_blank_lines_survive(self):
        after = concept.set_key(self.doc, "strength", 5)
        self.assertIn("# I keep the strength here so I remember to revisit it", after)
        self.assertIn("capabilities: [ai-platform-architecture]\n\nstatus: confirmed",
                      after)

    def test_body_is_untouched(self):
        after = concept.set_key(self.doc, "strength", 5)
        self.assertTrue(after.endswith("# The problem\n\nIt was slow.\n"))

    def test_a_new_key_is_appended_to_the_block(self):
        after = concept.set_key(self.doc, "recency", 2026)
        self.assertIn("status: confirmed\nrecency: 2026\n---\n", after)

    def test_a_duplicated_key_is_refused_rather_than_guessed(self):
        path = write_lf(Path(self.dir) / "dupe.md",
                        "---\ntype: Project\nstrength: 1\nstrength: 2\n---\n\nx\n")
        doc = concept.read(path)
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.set_key(doc, "strength", 5)
        message = str(caught.exception)
        self.assertIn("dupe.md", message)
        self.assertIn("appears twice", message)

    def test_a_crlf_file_keeps_its_line_endings(self):
        # A bundle scaffolded on Windows is entirely CRLF. Rewriting one key must
        # not rewrite every line ending - that is a whole-file diff in git and
        # the loudest possible version of touching what nobody asked for.
        path = Path(self.dir) / "crlf.md"
        path.write_bytes(HAND_WRITTEN.replace("\n", "\r\n").encode("utf-8"))
        doc = concept.read(path)
        after = concept.set_key(doc, "strength", 5)
        self.assertEqual(after.count("\r\n"), HAND_WRITTEN.count("\n"))
        self.assertIn("strength: 5\r\n", after)

    def test_an_lf_file_keeps_its_line_endings(self):
        after = concept.set_key(self.doc, "strength", 5)
        self.assertNotIn("\r", after)

    def test_a_block_list_is_refused_rather_than_reflowed(self):
        path = write_lf(Path(self.dir) / "block.md",
                        "---\ntype: Project\ntags:\n  - one\n  - two\n---\n\nx\n")
        doc = concept.read(path)
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.set_key(doc, "tags", ["three"])
        self.assertIn("block.md", str(caught.exception))

    def test_a_value_continuing_onto_the_next_line_is_refused(self):
        """Every shape whose value starts on the key's line and does not end there.

        Testing "nothing after the colon" caught `tags:` and missed all four of
        these. The wrapped flow list spliced into a file pyyaml could no longer
        parse; the other three spliced into a file that still parses and reports
        a value neither the author nor the caller ever wrote - `title` came back
        as 'New two"'. Silent, which is what makes it the worst of the family.
        """
        for name, block, key in (
                ("wrapped-flow", "tags: [a,\n  b]", "tags"),
                ("wrapped-quoted", 'title: "one\n  two"', "title"),
                ("block-scalar", "desc: |\n  line one\n  line two", "desc"),
                ("folded-scalar", "desc: >\n  line one\n  line two", "desc"),
        ):
            with self.subTest(name=name):
                path = write_lf(Path(self.dir) / f"{name}.md",
                                f"---\ntype: Project\n{block}\n---\n\nx\n")
                doc = concept.read(path)
                with self.assertRaises(concept.Unsplicable) as caught:
                    concept.set_key(doc, key, "New")
                self.assertIn(f"{name}.md", str(caught.exception))

    def test_a_null_key_on_one_line_is_spliced_not_refused(self):
        # `title:` with nothing after it is one line and not a block, so the
        # "written as a block, over several lines" refusal was a false
        # explanation for a file this command can change perfectly well.
        path = write_lf(Path(self.dir) / "null.md",
                        "---\ntype: Project\ntitle:\n---\n\nx\n")
        doc = concept.read(path)
        self.assertEqual(concept.set_key(doc, "title", "New"),
                         "---\ntype: Project\ntitle: New\n---\n\nx\n")

    def test_a_key_defined_three_times_says_three(self):
        # "appears twice, at lines 3, 4, 5" reads like a bug in the tool, which
        # undermines a message whose whole job is to be trusted.
        path = write_lf(Path(self.dir) / "thrice.md",
                        "---\ntype: Project\ns: 1\ns: 2\ns: 3\n---\n\nx\n")
        doc = concept.read(path)
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.set_key(doc, "s", 9)
        self.assertIn("appears 3 times, at lines 3, 4, 5", str(caught.exception))

    def test_a_continuation_that_looks_like_a_key_is_refused(self):
        """The shapes that defeated reading the next line, rather than parsing.

        A wrapped value can continue at column 0 and look exactly like a
        top-level key. Splicing the first line then left the rest behind as a
        line the parser read as a key, so the document silently *gained* a key
        `b` and the tool reported success.
        """
        for name, block in (
                ("dq", 'title: "a\nb: c"'),
                ("sq", "title: 'a\nb: c'"),
                ("flow-list", 'tags: [a,\nb: c]'),
                ("flow-map", 'meta: {a: 1,\nb: c}'),
        ):
            with self.subTest(name=name):
                path = write_lf(Path(self.dir) / f"{name}.md",
                                f"---\ntype: Project\n{block}\n---\n\nx\n")
                doc = concept.read(path)
                key = block.split(":")[0]
                with self.assertRaises(concept.Unsplicable) as caught:
                    concept.set_key(doc, key, "New")
                self.assertIn(f"{name}.md", str(caught.exception))

    def test_a_block_scalar_is_refused_however_it_opens(self):
        """Including the two shapes a comment test cannot tell from a comment.

        A block scalar's first content line may be blank or may start with `#`.
        Neither is a comment, and treating them as one spliced the key while
        leaving the block behind as its new value.
        """
        for name, block in (
                ("blank-first", "desc: |\n\n  real content"),
                ("hash-first", "desc: |\n  # not a comment"),
                ("comment-between", "desc: |\n  # one\n  two"),
                ("folded", "desc: >\n  one\n  two"),
        ):
            with self.subTest(name=name):
                path = write_lf(Path(self.dir) / f"bs-{name}.md",
                                f"---\ntype: Project\n{block}\n---\n\nx\n")
                doc = concept.read(path)
                with self.assertRaises(concept.Unsplicable) as caught:
                    concept.set_key(doc, "desc", "New")
                self.assertIn(f"bs-{name}.md", str(caught.exception))

    def test_an_anchor_or_alias_refuses_the_whole_block(self):
        # Splicing either end breaks the other: replacing `a: &x 1` leaves
        # `b: *x` pointing at nothing, which pyyaml will not read back.
        for name, block in (
                ("anchor", "a: &x 1\nb: *x"),
                ("merge", "defaults: &d {s: 1}\n<<: *d"),
        ):
            with self.subTest(name=name):
                path = write_lf(Path(self.dir) / f"anchor-{name}.md",
                                f"---\ntype: Project\n{block}\n---\n\nx\n")
                doc = concept.read(path)
                with self.assertRaises(concept.Unsplicable) as caught:
                    concept.set_key(doc, "type", "Role")
                self.assertIn("anchor", str(caught.exception))

    def test_keys_the_old_regex_could_not_see_are_spliced_not_duplicated(self):
        """These three used to brick the file for the tool itself.

        `KEY` matched none of them, so set_key appended a *second* definition
        rather than replacing the one that was there - creating exactly the
        duplicate that locate() then refuses to touch, forever, silently.
        """
        for name, line, key, want in (
                ("dotted", "job.title: old", "job.title", "job.title: New"),
                ("quoted", '"job title": old', "job title", '"job title": New'),
                ("spaced", "strength : old", "strength", "strength : New"),
        ):
            with self.subTest(name=name):
                path = write_lf(Path(self.dir) / f"key-{name}.md",
                                f"---\ntype: Project\n{line}\n---\n\nx\n")
                doc = concept.read(path)
                after = concept.set_key(doc, key, "New")
                self.assertEqual(
                    after, f"---\ntype: Project\n{want}\n---\n\nx\n")

    def test_a_trailing_comment_survives_the_splice(self):
        # The comment is the author's. Rewriting the whole line threw it away.
        for name, line, key, want in (
                ("plain", "t: old  # note", "t", "t: New  # note"),
                ("quoted-key", '"job title": old  # x', "job title",
                 '"job title": New  # x'),
                ("flow-with-colon", 't: [a, "b: c"] # tail', "t",
                 't: [x] # tail'),
                ("null-with-comment", "t:  # todo", "t", "t: New  # todo"),
        ):
            with self.subTest(name=name):
                path = write_lf(Path(self.dir) / f"cmt-{name}.md",
                                f"---\ntype: Project\n{line}\n---\n\nx\n")
                doc = concept.read(path)
                value = ["x"] if name == "flow-with-colon" else "New"
                after = concept.set_key(doc, key, value)
                self.assertEqual(
                    after, f"---\ntype: Project\n{want}\n---\n\nx\n")
                import yaml
                self.assertEqual(
                    yaml.safe_load(after.split("---\n")[1])[key],
                    value if isinstance(value, list) else "New")

    def test_an_empty_string_value_is_replaced_not_prefixed(self):
        # `t: ""` is an empty value that *has* text. Treating it as the implicit
        # null - which has none - would have written `t: New""`.
        path = write_lf(Path(self.dir) / "empty-string.md",
                        '---\ntype: Project\nt: ""\n---\n\nx\n')
        doc = concept.read(path)
        self.assertEqual(concept.set_key(doc, "t", "New"),
                         "---\ntype: Project\nt: New\n---\n\nx\n")

    def test_a_new_key_goes_above_a_trailing_blank_line(self):
        # The blank line is the author's; a key appended below it reads as a
        # second stanza rather than as part of the block.
        path = write_lf(Path(self.dir) / "trailing-blank.md",
                        "---\ntype: Project\n\n---\n\nx\n")
        doc = concept.read(path)
        self.assertEqual(concept.set_key(doc, "strength", 5),
                         "---\ntype: Project\nstrength: 5\n\n---\n\nx\n")

    def test_the_gap_before_the_body_is_not_invented(self):
        # A hand-written concept with no blank line after its frontmatter used
        # to gain one on every splice.
        path = write_lf(Path(self.dir) / "no-gap.md",
                        "---\ntype: Project\nstrength: 1\n---\n# Body\n")
        doc = concept.read(path)
        self.assertEqual(concept.set_key(doc, "strength", 5),
                         "---\ntype: Project\nstrength: 5\n---\n# Body\n")
