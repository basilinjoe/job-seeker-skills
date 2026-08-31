"""The write schema against the readers it has to agree with.

`schema.py` claims to be the only machine-readable statement of the format's shape.
That claim is worth nothing unless it is checked against the things that actually
read a bundle, because a schema that has drifted does not fail loudly - it accepts a
concept a gate then rejects, or refuses one the compile is perfectly happy with, and
either way the person finds out later and somewhere else.

Three readers, three agreements:

  - `validate_urs.VIEW_KEYS` - what a view may carry. A key this layer writes that
    the gate does not know fails the record gate on every run from the day it is
    written, permanently, because the gate compiles the whole bundle and an archive
    never gets better.
  - `okf_compile.blocks()`' key tuples - what an authored item may carry. A key this
    layer accepts that the compiler does not parse becomes part of the printed
    sentence.
  - `okf_compile.CONCEPT_KEYS` - the bookkeeping stripped from a view before it
    reaches URS.

Each of these was found by a defect rather than by foresight. The View one was found
by tailoring.py's author noticing that COMMON gives every type `tags` and `resource`,
neither of which is a view key and neither of which is stripped.
"""
import unittest

from fixtures import OKF_COMPILE, SCRIPTS, authoring_module, load_script

body = authoring_module("authoring.body")
schema = authoring_module("authoring.schema")
okf_compile = load_script(OKF_COMPILE)
validate_urs = load_script(SCRIPTS / "validate_urs.py")


class ViewKeysMatchTheRecordGate(unittest.TestCase):
    """Every key this layer may write on a View is one the record gate knows.

    Asserted in one direction only, deliberately. A view key the gate knows and this
    schema does not model is a view nobody can author through a command - a gap, and
    a visible one, because the command refuses and says so. A key this schema models
    and the gate does not know is the silent case: it writes a file that fails the
    record gate forever.
    """

    def view_keys(self):
        return {key.name for key in schema.TYPES["View"]}

    def test_every_view_key_is_a_view_key_or_stripped_bookkeeping(self):
        allowed = set(validate_urs.VIEW_KEYS) | set(okf_compile.CONCEPT_KEYS)
        for name in sorted(self.view_keys() - allowed):
            self.fail(
                f"schema.TYPES['View'] models {name!r}, which is neither in "
                f"validate_urs.VIEW_KEYS nor stripped by "
                f"okf_compile.CONCEPT_KEYS - a view carrying it fails the record "
                f"gate on every run from the day it is written")

    def test_the_keys_the_gate_requires_are_modelled(self):
        """`format_profile` is the one the gate fails a view for lacking."""
        self.assertIn("format_profile", self.view_keys())
        required = {key.name for key in schema.TYPES["View"] if key.required}
        self.assertIn("format_profile", required)

    def test_the_gates_own_view_keys_are_all_reachable(self):
        """Not a failure, but worth seeing: which view keys have no flag yet.

        `x` is the extension point and is modelled. Anything else missing here is a
        view a person can hand-write and no command can author, which is a real gap
        even though it is a visible one.
        """
        missing = sorted(set(validate_urs.VIEW_KEYS) - self.view_keys())
        self.assertEqual(missing, [], f"view keys this layer cannot write: {missing}")


class ItemKeysMatchTheCompiler(unittest.TestCase):
    """Every field an authored item may carry is one okf_compile.blocks() parses.

    blocks() takes a closed tuple of keys and treats every other line as text. So a
    key this schema accepts and the compiler does not parse is not ignored - it is
    printed, in the middle of a resume bullet.
    """

    # The tuples okf_compile passes to blocks(), read off the calls themselves
    # rather than restated: bullets() at the `# Bullets` call, build_skills() at
    # `# Skills`, build_credentials() at `# Held`.
    COMPILER_KEYS = {
        "bullet": ("status", "metric", "for", "id"),
        "skill": ("id", "category", "aliases", "last_used"),
        "credential": ("issuer", "issued", "expires", "status", "id"),
    }

    def test_the_schema_and_the_compiler_hold_the_same_keys(self):
        for kind, keys in sorted(self.COMPILER_KEYS.items()):
            with self.subTest(kind=kind):
                mine = {field.name for field in schema.ITEMS[kind]}
                self.assertEqual(mine, set(keys))

    def test_body_and_the_compiler_hold_the_same_keys(self):
        """body.KINDS carries the parser's tuple; it must be the compiler's."""
        for kind, keys in sorted(self.COMPILER_KEYS.items()):
            with self.subTest(kind=kind):
                self.assertEqual(set(body.KINDS[kind]["keys"]), set(keys))

    def test_the_written_order_covers_every_key_the_parser_takes(self):
        """A key in the parser's tuple and absent from the written order would be
        emitted after the ones that are listed, in whatever order a dict happened
        to hold - which is how two commands writing one kind of item produce two
        different files."""
        for kind, spec in sorted(body.KINDS.items()):
            with self.subTest(kind=kind):
                self.assertEqual(set(spec["keys"]), set(spec["order"]))

    def test_the_compiler_calls_blocks_with_exactly_these_tuples(self):
        """Reads okf_compile.py's source, so a change to a call site fails here.

        The tuples above are a copy, and this is what stops the copy going stale -
        the same move `SchemaAgreesWithTheGate` makes for the bundle gate.
        """
        import re
        source = (SCRIPTS / "okf_compile.py").read_text(encoding="utf-8")
        found = {}
        for heading, keys in re.findall(
                r'blocks\(\s*body,\s*"(\w+)",\s*\(([^)]*)\)', source):
            found[heading] = set(re.findall(r'"(\w+)"', keys))
        by_heading = {spec["heading"]: kind for kind, spec in body.KINDS.items()}
        for heading, keys in sorted(found.items()):
            with self.subTest(heading=heading):
                kind = by_heading.get(heading)
                self.assertIsNotNone(
                    kind, f"okf_compile parses a `# {heading}` block that "
                          f"body.KINDS does not know about")
                self.assertEqual(set(self.COMPILER_KEYS[kind]), keys)
        self.assertEqual(sorted(found), sorted(by_heading),
                         "the blocks() call sites and body.KINDS disagree")


class StructuredKeysMatchTheirReaders(unittest.TestCase):
    """The four mapping-valued keys, against what actually reads them."""

    def test_a_requirement_carries_what_the_compile_demands(self):
        """okf_compile.posting() refuses a requirement without value and kind, by
        name. Both must therefore be required here, or this layer writes a posting
        the compile then refuses - and `okf score` compiles."""
        fields = {f.name: f for f in schema.STRUCTURED["requirements"][1]}
        self.assertTrue(fields["value"].required)
        self.assertTrue(fields["kind"].required)

    def test_the_budget_carries_the_key_the_renderer_reads(self):
        """urs/resolve.py reads budget.ats_maximal_pages for the ATS variant."""
        fields = {f.name for f in schema.STRUCTURED["budget"][1]}
        self.assertEqual(fields, {"pages", "ats_maximal_pages"})
        source = (SCRIPTS / "urs" / "resolve.py").read_text(encoding="utf-8")
        self.assertIn("ats_maximal_pages", source)

    def test_an_include_entry_carries_what_the_renderer_selects_on(self):
        """resolve.py reads `ref` and `achievements` off an include entry."""
        fields = {f.name for f in schema.STRUCTURED["include"][1]}
        self.assertIn("ref", fields)
        self.assertIn("achievements", fields)

    def test_an_include_order_is_not_capped_at_five(self):
        """A view selecting eight engagements has to be able to number the sixth.

        `order` was `rank`, which is 1-5 and whose refusal talks about flagship
        evidence - a message about `strength`, on a key about ordering. Found by
        tailoring.py's author.
        """
        self.assertEqual(
            schema.check("View", {"title": "V", "format_profile": "web",
                                  "include": [{"ref": "eng_a", "order": 8}]}), [])


class TheFourCareerTypesAgreeWithEachOther(unittest.TestCase):
    """A verb generic over four types needs the four to carry the same bookkeeping.

    `Organisation` was missing `retired` and `retired_reason` while the other three
    had them, so `org retire` wrote two keys the schema would then refuse on the
    next `org set` - and career.py's author had to declare them as extensions to
    get the verb working at all. A generic verb over an inconsistent table is how
    that happens, and this is the assertion that stops it recurring.
    """

    CAREER = ("Project", "Role", "Organisation", "Education")

    def test_every_career_type_can_be_retired(self):
        for name in self.CAREER:
            with self.subTest(type=name):
                keys = {key.name for key in schema.TYPES[name]}
                self.assertIn("retired", keys)
                self.assertIn("retired_reason", keys)

    def test_a_retired_concept_is_still_clean(self):
        """Retiring must not make a concept the schema then refuses to amend."""
        base = EveryTypeCanBeWrittenAndReadBack.CLEAN
        for name in self.CAREER:
            with self.subTest(type=name):
                values = dict(base[name], retired="2026-08-31",
                              retired_reason="no longer claimed")
                self.assertEqual(schema.check(name, values), [])


class EveryTypeCanBeWrittenAndReadBack(unittest.TestCase):
    """A concept the schema approves, emitted and parsed, is still approved.

    The round trip is where a kind and the emitter disagree: `submitted: false`
    reads back as a bool, a `timestamp` as a datetime, a date as a date. A schema
    that approves what it cannot read back approves a file no `set` can then touch.
    """

    CLEAN = {
        "Project": {"title": "T", "role": "r", "strength": 3, "recency": 2026,
                    "seniority": "hands-on", "domains": ["d"],
                    "capabilities": ["c"]},
        "Role": {"title": "T", "organisation": "o", "start": "2019-04",
                 "end": "2021-12", "state": "ended"},
        "Organisation": {"title": "T", "relationship": "employer",
                         "industry": ["healthcare"]},
        "Education": {"title": "BSc", "level": "bachelor"},
        "Certification Status": {"title": "Certifications"},
        "Skill Set": {"title": "Competencies"},
        "Metric Set": {"title": "Verified numbers"},
        "Job Posting": {"title": "T", "company": "C",
                        "requirements": [{"value": "v", "kind": "capability",
                                          "necessity": "required"}]},
        "Gap Assessment": {"posting": "p", "assessed": "2026-08-30",
                           "fit": "partial"},
        "View": {"title": "T", "format_profile": "ats-maximal",
                 "budget": {"pages": 2}, "target": {"title": "T", "ref": "p.md"},
                 "include": [{"ref": "eng_a", "order": 1,
                              "achievements": ["ach_a"]}]},
        "Application": {"title": "T", "submitted": "2026-08-26",
                        "channel": "Workday", "view": "view_a"},
    }

    def test_every_type_has_a_clean_example_here(self):
        """So a new type cannot be added without one."""
        self.assertEqual(sorted(self.CLEAN), sorted(schema.TYPES))

    def test_each_clean_example_is_clean(self):
        for name, values in sorted(self.CLEAN.items()):
            with self.subTest(type=name):
                self.assertEqual(schema.check(name, values), [])

    def test_each_one_survives_the_round_trip(self):
        concept = authoring_module("authoring.concept")
        for name, values in sorted(self.CLEAN.items()):
            with self.subTest(type=name):
                text = concept.new(name, dict(values, timestamp="2026-01-01T00:00:00Z"),
                                   "# Notes\n\nWhat happened.\n")
                doc = concept.parse(text, f"{name}.md")
                read_back = {k: v for k, v in doc.meta.items() if k != "type"}
                self.assertEqual(schema.check(name, read_back), [],
                                 f"{name}: approved, written, and refused on read")

    def test_a_held_back_application_survives_the_round_trip(self):
        """`submitted: false` is the one value whose YAML type is not a string, and
        the exemption validate_bundle.py honours. It has to read back as False."""
        concept = authoring_module("authoring.concept")
        text = concept.new("Application", {"title": "T", "submitted": False}, "")
        doc = concept.parse(text, "a.md")
        self.assertIs(doc.meta["submitted"], False)
        self.assertEqual(schema.check("Application",
                                      {"title": "T", "submitted": False}), [])


if __name__ == "__main__":                                # pragma: no cover
    unittest.main()
