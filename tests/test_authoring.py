"""The write core: emit, splice, stage, commit.

Every test here pins a rule from
docs/superpowers/specs/2026-08-31-okf-write-cli-design.md. The rules that matter
most are the ones about not touching what the command was not asked to touch: a
person's bundle is hand-editable by design, and a tool that reflows their file is
a tool they stop running.
"""
import sys
import unittest

from fixtures import INIT_BUNDLE, authoring_module, load_script

concept = authoring_module("authoring.concept")
init_bundle = load_script(INIT_BUNDLE)


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

    def test_init_bundle_uses_the_shared_quoter(self):
        self.assertIs(init_bundle.yq, concept.scalar)

    def test_scaffolded_frontmatter_matches_the_emitter(self):
        self.assertEqual(
            init_bundle.fm("Index", 'A "quoted" name', "Desc", "2026-01-01T00:00:00Z"),
            concept.frontmatter("Index", {
                "title": 'A "quoted" name',
                "description": "Desc",
                "timestamp": "2026-01-01T00:00:00Z",
            }) + "\n")
