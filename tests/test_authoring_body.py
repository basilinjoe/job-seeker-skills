"""A concept's body: the authored blocks, the prose sections, and the derived ids.

Two classes here are the load-bearing ones. `ItemsMatchTheCompiler` asserts that
this module reads a block exactly as `okf_compile.blocks()` does, and
`IdsMatchTheCompiler` that it derives an id exactly as the compile would - both
over a corpus of shapes rather than one example. Either one drifting is the
write layer editing a claim the compile does not read, or repointing every view
that named one.
"""
import unittest

from fixtures import OKF_COMPILE, authoring_module, load_script

body = authoring_module("authoring.body")
concept = authoring_module("authoring.concept")
okf_compile = load_script(OKF_COMPILE)

BULLET_KEYS = body.BULLET_KEYS
BULLET_ORDER = body.BULLET_ORDER
SKILL_KEYS = body.SKILL_KEYS
HELD_KEYS = body.HELD_KEYS

# Every block shape worth reading, including the ones that look like defects. Each
# is a whole concept body, so the heading search is exercised too.
SHAPES = [
    "# Bullets\n\n- One sentence.\n",
    "# Bullets\n\n- One sentence.\n  status: confirmed\n",
    "# Bullets\n\n- One.\n  status: confirmed\n- Two.\n  metric: Latency\n",
    # No blank line under the heading.
    "# Bullets\n- One.\n",
    # A sentence introducing the list.
    "# Bullets\n\nThe lines this project earned:\n\n- One.\n",
    # Prose with no blank line before the list.
    "# Bullets\n\nThe lines:\n- One.\n",
    # Wrapped text, which blocks() joins with a space.
    "# Bullets\n\n- One sentence\n  spread over two lines.\n  status: confirmed\n",
    # Fields in an order nobody would choose, and extra spaces around the colon.
    "# Bullets\n\n- One.\n  status :  confirmed\n  id: ach_one\n",
    # A field-looking line whose key is not in the closed set: text, to both readers.
    "# Bullets\n\n- One.\n  statuss: confirmed\n",
    # A second block after the first, ended by a level-one heading.
    "# Bullets\n\n- One.\n\n# What I decided\n\nProse.\n",
    # A level-two heading, which does NOT end a block - the compiler's own rule.
    "# Bullets\n\n- One.\n\n## A note\n\n- Two.\n",
    # An empty block.
    "# Bullets\n\n# What I decided\n\nProse.\n",
    # A heading with trailing spaces, and one at a deeper level.
    "### Bullets  \n\n- One.\n",
    # A nested list item, which blocks() reads as a second entry.
    "# Bullets\n\n- One.\n  - Nested.\n",
    # Blank lines inside and after.
    "# Bullets\n\n- One.\n\n  status: confirmed\n\n\n",
    # Prose before the heading.
    "What this was.\n\n# Bullets\n\n- One.\n",
    # A bullet whose text starts with a dash after the marker.
    "# Bullets\n\n- - One.\n",
    # CRLF is normalised by the reader before this module sees a body, so LF only
    # here - but a lone CR inside a line is possible and must not split anything.
    "# Bullets\n\n- One.\n  status: confirmed\n",
]


class ItemsMatchTheCompiler(unittest.TestCase):
    """What this module reads, okf_compile.blocks() reads identically."""

    def assert_agrees(self, text, name, keys):
        block = body.parse(text, name, keys)
        mine = [(item.text, item.fields) for item in (block.claims() if block else [])]
        theirs = okf_compile.blocks(text, name, keys)
        self.assertEqual(mine, theirs, f"disagreed on {text!r}")

    def test_an_entry_with_no_sentence_is_dropped_by_both_and_takes_no_position(self):
        """blocks() ends `if text: out.append(...)`, so a `- ` carrying only fields
        is not an achievement and does not consume a number. `items` keeps it,
        because a writer has to put back the lines it did not touch; `claims` is
        the compiler's view. Anything numbering items has to use the second, which
        common.item_ids did not until this was written down.
        """
        text = "# Bullets\n\n- \n  status: confirmed\n- A real one.\n"
        self.assert_agrees(text, "Bullets", BULLET_KEYS)
        block = body.parse(text, "Bullets", BULLET_KEYS)
        self.assertEqual(len(block.items), 2)
        self.assertEqual([item.text for item in block.claims()], ["A real one."])
        # And the real bullet is therefore the compile's number 1, not its 2.
        built = okf_compile.bullets(text, "projects/care.md", {})
        self.assertEqual([a["id"] for a in built], [body.derived_bullet_id("care", 1)])

    def test_every_shape_reads_the_same(self):
        for text in SHAPES:
            with self.subTest(text=text):
                self.assert_agrees(text, "Bullets", BULLET_KEYS)

    def test_a_missing_heading_is_no_items_in_both(self):
        text = "# What I decided\n\nProse.\n"
        self.assertIsNone(body.parse(text, "Bullets", BULLET_KEYS))
        self.assertEqual(okf_compile.blocks(text, "Bullets", BULLET_KEYS), [])

    def test_the_skill_and_held_blocks_read_the_same(self):
        skills = ("# Skills\n\n- C# / .NET\n  id: skill_dotnet\n  category: language\n"
                  "  aliases: C#, .NET, ASP.NET Core\n")
        self.assert_agrees(skills, "Skills", SKILL_KEYS)
        held = ("# Held\n\n- Azure Solutions Architect Expert\n  issuer: Microsoft\n"
                "  issued: 2024-05\n  status: active\n")
        self.assert_agrees(held, "Held", HELD_KEYS)

    def test_a_fenced_heading_is_found_by_both(self):
        """Copied crudeness, asserted so nobody 'fixes' one side of it."""
        text = "Example:\n\n```\n# Bullets\n\n- Fenced.\n```\n"
        self.assert_agrees(text, "Bullets", BULLET_KEYS)
        block = body.parse(text, "Bullets", BULLET_KEYS)
        self.assertEqual([item.text for item in block.items], ["Fenced. ```"])


class RoundTrip(unittest.TestCase):
    """Parse, put the same items back, and the body is unchanged - byte for byte."""

    def test_every_shape_round_trips(self):
        for text in SHAPES:
            with self.subTest(text=text):
                block = body.parse(text, "Bullets", BULLET_KEYS)
                if block is None:
                    continue
                self.assertEqual(body.replace(text, block, block.items), text)

    def test_an_untouched_item_keeps_its_own_bytes(self):
        text = ("# Bullets\n\n- Wrapped over\n  two lines.\n  status: confirmed\n"
                "- Second.\n")
        block = body.parse(text, "Bullets", BULLET_KEYS)
        items = block.items[:1] + [body.item("Rewritten.", {"status": "inferred"},
                                             BULLET_KEYS)]
        out = body.replace(text, block, items)
        self.assertIn("- Wrapped over\n  two lines.\n  status: confirmed\n", out)
        self.assertIn("- Rewritten.\n  status: inferred\n", out)


class Emitting(unittest.TestCase):
    def test_fields_are_written_in_the_order_given(self):
        item = body.item("Cut latency.", {"status": "confirmed", "metric": "Latency"},
                         BULLET_ORDER)
        self.assertEqual(item.lines,
                         ["- Cut latency.", "  metric: Latency", "  status: confirmed"])

    def test_an_absent_field_is_not_written(self):
        item = body.item("Cut latency.", {"status": None, "metric": ""}, BULLET_KEYS)
        self.assertEqual(item.lines, ["- Cut latency."])

    def test_a_newline_in_text_is_collapsed_rather_than_breaking_the_item(self):
        item = body.item("One.\nTwo.", {}, BULLET_KEYS)
        self.assertEqual(item.lines, ["- One. Two."])

    def test_a_newline_in_a_field_is_collapsed(self):
        item = body.item("One.", {"metric": "A\nB"}, BULLET_KEYS)
        self.assertEqual(item.lines, ["- One.", "  metric: A B"])

    def test_an_emitted_item_reads_back_as_itself(self):
        item = body.item("Cut latency 4.2s to 380ms.",
                         {"status": "confirmed", "metric": "Claim latency"},
                         BULLET_KEYS)
        text = "# Bullets\n\n" + "\n".join(item.lines) + "\n"
        self.assertEqual(okf_compile.blocks(text, "Bullets", BULLET_KEYS),
                         [("Cut latency 4.2s to 380ms.",
                           {"metric": "Claim latency", "status": "confirmed"})])

    def test_text_is_required(self):
        with self.assertRaises(concept.Unsplicable):
            body.item("   ", {"status": "confirmed"}, BULLET_KEYS)

    def test_an_unlisted_field_is_written_rather_than_dropped(self):
        item = body.item("One.", {"zzz": "kept"}, BULLET_KEYS)
        self.assertEqual(item.lines, ["- One.", "  zzz: kept"])


class Inserting(unittest.TestCase):
    def test_an_item_appends_to_an_existing_list(self):
        text = "# Bullets\n\n- One.\n"
        block = body.parse(text, "Bullets", BULLET_KEYS)
        items = block.inserted(body.item("Two.", {}, BULLET_KEYS))
        self.assertEqual(body.replace(text, block, items),
                         "# Bullets\n\n- One.\n- Two.\n")

    def test_an_item_inserts_at_a_position(self):
        text = "# Bullets\n\n- One.\n- Two.\n"
        block = body.parse(text, "Bullets", BULLET_KEYS)
        items = block.inserted(body.item("Zero.", {}, BULLET_KEYS), at=1)
        self.assertEqual(body.replace(text, block, items),
                         "# Bullets\n\n- Zero.\n- One.\n- Two.\n")

    def test_a_first_item_under_prose_gains_a_blank_line(self):
        text = "# Bullets\n\nThe lines this earned:\n"
        block = body.parse(text, "Bullets", BULLET_KEYS)
        items = block.inserted(body.item("One.", {}, BULLET_KEYS))
        self.assertEqual(body.replace(text, block, items),
                         "# Bullets\n\nThe lines this earned:\n\n- One.\n")

    def test_a_new_block_is_appended_to_the_body(self):
        out = body.add_block("What this was.\n", "Bullets", ["- One."])
        self.assertEqual(out, "What this was.\n\n# Bullets\n\n- One.\n")
        self.assertEqual(okf_compile.blocks(out, "Bullets", BULLET_KEYS),
                         [("One.", {})])

    def test_a_new_block_on_an_empty_body(self):
        out = body.add_block("", "Bullets", ["- One."])
        self.assertEqual(out, "# Bullets\n\n- One.\n")


class Sections(unittest.TestCase):
    BODY = ("# The problem\n\nIt was slow.\n\n# What I decided\n\nRewrite it.\n\n"
            "## A detail\n\nKept.\n\n# What changed\n\nLatency fell.\n")

    def test_a_section_is_replaced_and_its_neighbours_are_not(self):
        out = body.set_section(self.BODY, "What I decided", "Rebuild it instead.")
        self.assertIn("# What I decided\n\nRebuild it instead.\n", out)
        self.assertIn("# The problem\n\nIt was slow.\n", out)
        self.assertIn("# What changed\n\nLatency fell.\n", out)

    def test_a_deeper_heading_belongs_to_the_section_above_it(self):
        out = body.set_section(self.BODY, "What I decided", "New.")
        self.assertNotIn("## A detail", out)
        self.assertIn("# What changed", out)

    def test_paragraph_breaks_survive(self):
        out = body.set_section(self.BODY, "The problem", "One.\n\nTwo.")
        self.assertIn("# The problem\n\nOne.\n\nTwo.\n", out)

    def test_a_heading_inside_a_fence_is_not_a_section(self):
        text = "# Real\n\n```\n# Fenced\n```\n"
        self.assertIsNone(body.section(text, "Fenced"))
        self.assertIsNotNone(body.section(text, "Real"))

    def test_an_absent_section_is_refused_and_the_real_ones_named(self):
        with self.assertRaises(concept.Unsplicable) as caught:
            body.set_section(self.BODY, "What I Decide", "New.")
        self.assertIn("'What I decided'", str(caught.exception))
        self.assertIn("fix:", str(caught.exception))

    def test_a_new_section_is_appended(self):
        out = body.add_section("Prose.\n", "What changed", "Latency fell.")
        self.assertEqual(out, "Prose.\n\n# What changed\n\nLatency fell.\n")

    def test_a_new_section_that_is_already_there_is_refused(self):
        with self.assertRaises(concept.Unsplicable):
            body.add_section(self.BODY, "What changed", "Again.")

    def test_matching_is_case_insensitive_but_reports_the_real_spelling(self):
        out = body.set_section(self.BODY, "what i decided", "New.")
        self.assertIn("# What I decided\n\nNew.\n", out)


class IdsMatchTheCompiler(unittest.TestCase):
    """The ids this module writes down are the ids the compile was deriving.

    The slug rule under both used to be two copies - `okf_compile.slug` and a
    `compile_slug` here - because importing a 1,000-line CLI for one regex was the
    wrong price on the hot path of every write. They are one object in `markup.py`
    now, which imports nothing, so the corpus below checks the *id builders* on top of
    it and `test_the_slug_rule_is_one_object` checks there is nothing left to drift.
    """

    STEMS = ["care-platform", "care_platform", "Care Platform", "aged-care-events",
             "a", "project.v2", "ünïcode-stem", "two--hyphens", "-leading",
             "trailing-", "MiXeD-Case", "9-lives"]

    def test_the_slug_rule_is_one_object(self):
        markup = load_script("markup")
        self.assertIs(body.compile_slug, markup.id_slug)
        self.assertIs(okf_compile.slug, markup.id_slug)

    def test_a_bullet_id_matches_what_the_compile_derives(self):
        for stem in self.STEMS:
            with self.subTest(stem=stem):
                text = "# Bullets\n\n- One.\n- Two.\n- Three.\n"
                built = okf_compile.bullets(text, f"projects/{stem}.md", {})
                self.assertEqual([a["id"] for a in built],
                                 [body.derived_bullet_id(stem, n) for n in (1, 2, 3)])

    def test_a_credential_id_matches_what_the_compile_derives(self):
        for stem in self.STEMS:
            with self.subTest(stem=stem):
                text = ("# Held\n\n- One\n  issuer: A\n- Two\n  issuer: B\n")
                built = okf_compile.build_credentials([(stem, {"type": "x"}, text)])
                self.assertEqual([c["id"] for c in built],
                                 [body.derived_credential_id(stem, n) for n in (1, 2)])

    def test_a_skill_id_matches_what_the_compile_derives(self):
        for name in ["C# / .NET", "Azure", "Terraform & Bicep", "SQL Server 2019"]:
            with self.subTest(name=name):
                text = f"# Skills\n\n- {name}\n"
                built = okf_compile.build_skills([("competencies", {}, text)])
                self.assertEqual(built[0]["id"], body.derived_skill_id(name))

    def test_compile_slug_is_the_compilers_slug(self):
        for text in ["Care Platform", "a-b_c", "  spaced  ", "C# / .NET", "2026",
                     "ünïcode", "", "---", "MiXeD"]:
            with self.subTest(text=text):
                self.assertEqual(body.compile_slug(text), okf_compile.slug(text))


class MintingIds(unittest.TestCase):
    def test_an_id_is_derived_from_the_items_own_words(self):
        self.assertEqual(
            body.mint_id("ach", "Cut claim latency from 4.2s to 380ms.", set()),
            "ach_cut_claim_latency")

    def test_noise_words_are_skipped(self):
        self.assertEqual(body.mint_id("ach", "Led the rebuild of the platform.", set()),
                         "ach_led_rebuild_platform")

    def test_a_taken_id_lengthens_before_it_numbers(self):
        taken = {"ach_cut_claim_latency"}
        self.assertEqual(
            body.mint_id("ach", "Cut claim latency from 4.2s to 380ms.", taken),
            "ach_cut_claim_latency_4")

    def test_a_text_with_nothing_left_to_give_is_numbered(self):
        taken = {"ach_latency"}
        self.assertEqual(body.mint_id("ach", "Latency", taken), "ach_latency_2")
        taken.add("ach_latency_2")
        self.assertEqual(body.mint_id("ach", "Latency", taken), "ach_latency_3")

    def test_text_with_no_words_at_all_still_yields_an_id(self):
        self.assertEqual(body.mint_id("ach", "!!! ???", set()), "ach_item")

    def test_a_minted_id_is_never_positional(self):
        """The whole point: a new id must not mean 'third from the top'."""
        minted = body.mint_id("ach", "Cut claim latency.", set())
        self.assertFalse(minted.rstrip("0123456789").endswith("_")
                         and minted.split("_")[-1].isdigit())


if __name__ == "__main__":                                # pragma: no cover
    unittest.main()
