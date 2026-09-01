"""The markdown primitives every layer reads a bundle with.

These were five idioms in four modules before markup.py existed, and they had already
drifted: the frontmatter split handled CRLF in `okf_compile` and nowhere else, under a
docstring claiming `pipeline.py` used it. The point of the module is that there is now
one answer per question, so most of what is worth testing is *identity* - that the
callers hold the same object rather than an equal one.
"""
import unittest

from fixtures import load_script

markup = load_script("markup")
okf_compile = load_script("okf_compile")
pipeline = load_script("pipeline")
validate_bundle = load_script("validate_bundle")


def authoring(name):
    from fixtures import authoring_module      # noqa: PLC0415 - test helper
    return authoring_module(f"authoring.{name}")


class OneDefinition(unittest.TestCase):
    """Every caller holds the same object, not a copy that happens to match today.

    An equality test would pass for a copy and go on passing right up until somebody
    edited one of them, which is the whole failure this module exists to end.
    """

    def test_the_link_pattern_is_one_object(self):
        self.assertIs(okf_compile.LINK, markup.LINK)
        self.assertIs(validate_bundle.LINK, markup.LINK)

    def test_the_list_item_and_term_patterns_are_one_object(self):
        self.assertIs(validate_bundle.LIST_ITEM, markup.LIST_ITEM)
        self.assertIs(authoring("common").VOCABULARY_ITEM, markup.LIST_ITEM)
        self.assertIs(authoring("common").TERM, markup.TERM)
        self.assertIs(authoring("common").HEADING, markup.HEADING)

    def test_the_fence_toggle_is_one_object(self):
        self.assertIs(authoring("bookkeeping").FENCE, markup.FENCE)

    def test_the_two_frontmatter_readers_agree(self):
        """okf_compile's docstring claimed pipeline.py used its parser. It did not -
        it had a weaker copy with no CRLF arm. The claim is checkable now."""
        text = "---\ntype: Project\ntitle: X\n---\n\nbody\n"
        self.assertEqual(okf_compile.read_frontmatter(text),
                         pipeline.read_frontmatter(text))


class Frontmatter(unittest.TestCase):
    def test_a_block_is_split_from_its_body(self):
        meta, body = markup.split_frontmatter("---\na: 1\n---\n\nbody\n")
        self.assertEqual(meta, "a: 1")
        self.assertEqual(body, "\nbody\n")

    def test_no_frontmatter_returns_the_text_unchanged(self):
        self.assertEqual(markup.split_frontmatter("just prose\n"),
                         (None, "just prose\n"))

    def test_an_unterminated_block_is_not_frontmatter(self):
        """`---` with no closer is a document that opens a block and never shuts it.
        Reading to the end of the file and calling it frontmatter would swallow the
        whole concept."""
        self.assertEqual(markup.split_frontmatter("---\na: 1\nno closer\n"),
                         (None, "---\na: 1\nno closer\n"))

    def test_crlf_is_split_at_the_right_offset(self):
        """Unreachable through every caller in the package - they all open with
        universal newlines - but the old copy sliced at [4:] for a five-character
        CRLF opener and handed YAML a leading newline. It parsed anyway, by luck."""
        meta, body = markup.split_frontmatter("---\r\na: 1\r\n---\r\n\r\nbody\r\n")
        self.assertEqual(meta, "a: 1")
        self.assertFalse(meta.startswith("\n"), "the opener was sliced short")

    def test_a_reader_survives_bad_yaml_and_the_gate_does_not(self):
        """The one difference between the two parsers, and it is deliberate.

        `okf_compile` and `pipeline` walk every file in a bundle and must not die on
        one; `validate_bundle` exists to report exactly that file. A single function
        would have had to pick, and either choice is wrong for one of them.
        """
        import yaml
        bad = "---\na: [unclosed\n---\n\nbody\n"
        self.assertEqual(markup.read_frontmatter(bad, yaml), (None, "\nbody\n"))
        with self.assertRaises(yaml.YAMLError):
            markup.load_frontmatter(bad, yaml)

    def test_a_non_mapping_block_reads_as_no_frontmatter(self):
        import yaml
        meta, _ = markup.load_frontmatter("---\n- a\n- b\n---\n\nbody\n", yaml)
        self.assertIsNone(meta)


class Fences(unittest.TestCase):
    LINES = ["outside", "```", "inside", "```", "after"]

    def test_scan_reports_the_opener_as_fenced(self):
        """A caller splicing a row into log.md must never write between a fence's
        opener and its content - that is how a dated heading landed under a closing
        fence, above the real sections, in the file whose job is to be truthful."""
        self.assertEqual([f for _, _, f in markup.scan(self.LINES)],
                         [False, True, True, True, False])

    def test_unfenced_skips_the_openers_too(self):
        self.assertEqual(list(markup.unfenced(self.LINES)), ["outside", "after"])

    def test_an_unclosed_fence_swallows_the_rest(self):
        """Deliberate, and matching what every copy of this did: a file that opens a
        fence and never shuts it has no content after it, and guessing otherwise would
        make a gate's answer depend on how the file ends."""
        self.assertEqual(list(markup.unfenced(["a", "```", "b", "c"])), ["a"])


class Terms(unittest.TestCase):
    def test_only_list_items_outside_a_fence_count(self):
        text = ("# Theme\n\nProse mentioning `not-a-term`.\n\n"
                "- `alpha`\n"
                "```\n- `fenced-example`\n```\n"
                "- `beta`\n")
        self.assertEqual(markup.terms(text), {"alpha", "beta"})

    def test_a_fresh_bundles_vocabulary_is_empty_by_design(self):
        """init_bundle scaffolds the file with its examples INSIDE a fence, so a fresh
        bundle yields nothing and both gates leave capabilities unchecked. Rejecting
        every value on a fresh bundle and accepting every value on a populated one are
        the same defect wearing opposite signs."""
        self.assertEqual(markup.terms("# Theme\n\n```\n- `example`\n```\n"), set())

    def test_it_takes_a_string_or_an_iterable_of_lines(self):
        self.assertEqual(markup.terms("- `a`\n"), markup.terms(["- `a`"]))


class IdSlug(unittest.TestCase):
    def test_non_alphanumerics_collapse_to_one_underscore(self):
        self.assertEqual(markup.id_slug("Acme - Care Platform!"), "acme_care_platform")

    def test_it_is_not_the_file_stem_rule(self):
        """`authoring.common.slug` makes a file stem - hyphens, and NFKD folding so
        that "Café" keeps its final letter. Merging the two would rename either every
        file in every bundle or every id in every view."""
        stem = authoring("common").slug
        self.assertEqual(stem("Café Project"), "cafe-project")
        self.assertEqual(markup.id_slug("Café Project"), "caf_project")


if __name__ == "__main__":
    unittest.main()
