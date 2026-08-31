# okf Write Layer — Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/authoring/` — the transactional write core for an OKF bundle — and prove it end to end with one command, `okf project add`.

**Architecture:** A four-module package behind a narrow waist. `schema.py` is the single machine-readable statement of what a concept type takes. `concept.py` reads, splices and emits one file and judges nothing. `bookkeeping.py` produces the derived companions (index entries, log rows). `stage.py` collects every file a command touches into a changeset and commits them in an order that makes a partial failure repairable. Commands assemble these and decide nothing themselves.

**Tech Stack:** Python 3, standard library only except `pyyaml` (already the bundle-reading dependency). Tests are `unittest`, run under `pytest`, importing via `tests/fixtures.py`.

**Source spec:** `docs/superpowers/specs/2026-08-31-okf-write-cli-design.md`

**Scope of this plan:** the core, plus `okf project add`. The remaining tranche-1 verbs (`role`, `org`, `bullet`, `metric`, …), tranche 2 and tranche 3 are separate plans written against these interfaces once they exist.

---

## Context an implementer needs

**Where things live.** Scripts are at `plugins/jsk/skills/jsk/scripts/`. Tests are at `tests/`, and every test resolves paths from `tests/fixtures.py`, never from the working directory.

**House rules that are not negotiable in this codebase:**

1. **Tests assert on output text.** Over 240 `assertIn` calls check strings like `PASS - safe to send`. You may *add* output lines. Rewording an existing verdict line breaks tests.
2. **A failing test after a refactor means the refactor was wrong.** Do not edit an existing test to accommodate new behaviour.
3. **Scripts are the public API.** `check_ats.py`, `--strict` and friends appear in shell histories. Internals are free; the invocation surface is not.
4. **Anything that cannot run reports loudly and exits non-zero** rather than passing quietly.
5. Comments in this codebase explain *why*, and often cite the defect that motivated the code. Match that. Do not write comments that restate the line beneath them.

**Run the suite** with `python -m pytest tests -q` (about two minutes; TeX tests dominate and skip themselves where no TeX engine exists). A single file: `python -m pytest tests/test_authoring.py -q`. Use `python`, not `python3` — this is Windows.

**Do not write these files with a shell heredoc.** The Bash tool collapses doubled backslashes in heredoc bodies *even when the delimiter is quoted* (`<<'EOF'`), so `"\\n"` lands as a real newline. Every file in this plan contains escape sequences, and the failure is silent: the source looks right and the tests fail on expectations that read correctly. Use the Write tool. This cost two separate cycles during Task 1 — once for the plan author, once for the implementer.

**The frontmatter style you must match**, from a real bundle concept:

```markdown
---
type: Project
title: "Acme - care coordination platform"
description: "Multi-tenant platform for aged-care providers."
tags: [healthcare, azure]
timestamp: 2026-01-01T00:00:00Z
status: confirmed
strength: 5
recency: 2026
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture, data-sovereignty]
technologies: [azure-ai-foundry, bicep]
---

# The problem

...
```

Lists are **flow style** (`[a, b]`), not block style. Strings that are prose are double-quoted; slugs, integers, dates and enum values are bare.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/authoring/__init__.py` | package marker; exports nothing |
| `scripts/authoring/concept.py` | one concept file: read it, emit a new one, splice one key. Formats; never judges. |
| `scripts/authoring/schema.py` | what each type takes and what each value must satisfy. The only definition. Judges; never formats. |
| `scripts/authoring/bookkeeping.py` | the derived companions: an index entry, a `log.md` row |
| `scripts/authoring/stage.py` | the changeset: collect, dry-run, commit in repairable order |
| `scripts/authoring/commands.py` | one function per noun-verb; assembles the four above and decides nothing |
| `scripts/init_bundle.py` | **modified** — drops its own `yq`/`fm` and imports `concept.py`'s |
| `scripts/okf.py` | **modified** — routes `okf project <verb>` into `commands.py` |
| `tests/fixtures.py` | **modified** — gains `authoring_module()` and `bundle_with()` |
| `tests/test_authoring.py` | the core's tests |

---

### Task 1: Frontmatter emitter, and one definition of it

`init_bundle.py:69-75` already has `yq()` and `fm()`. The spec forbids a second definition of the format, so `concept.py` takes ownership and `init_bundle.py` imports from it. Task 2 does the second half; this task makes the emitter exist and be correct.

**Files:**
- Create: `plugins/jsk/skills/jsk/scripts/authoring/__init__.py`
- Create: `plugins/jsk/skills/jsk/scripts/authoring/concept.py`
- Modify: `tests/fixtures.py`
- Test: `tests/test_authoring.py`

- [ ] **Step 1: Add the import helper to `tests/fixtures.py`**

Append to `tests/fixtures.py`:

```python
def authoring_module(name):
    """Import a module from the authoring package the write commands use.

    Same shape as urs_module: the scripts directory is not on the path, because
    these are CLIs rather than an installed package.
    """
    import importlib
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(name)
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_authoring.py`:

```python
"""The write core: emit, splice, stage, commit.

Every test here pins a rule from
docs/superpowers/specs/2026-08-31-okf-write-cli-design.md. The rules that matter
most are the ones about not touching what the command was not asked to touch: a
person's bundle is hand-editable by design, and a tool that reflows their file is
a tool they stop running.
"""
import unittest

from fixtures import authoring_module

concept = authoring_module("authoring.concept")


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

    def test_date_is_bare(self):
        self.assertEqual(concept.scalar("2026-08-31"), "2026-08-31")

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

    def test_a_backslash_is_escaped_before_anything_else(self):
        self.assertEqual(concept.scalar("back\\slash"), '"back\\\\slash"')

    def test_escaped_values_read_back_as_themselves(self):
        # The emitter's contract: whatever pyyaml reads back must equal what was
        # handed in, or a concept quietly stops saying what its author said.
        import yaml
        for raw in ("abc\n", "a\nb", "tab\there", 'say "hi"', "back\\slash",
                    "latency: 5 min"):
            with self.subTest(raw=raw):
                parsed = yaml.safe_load("title: " + concept.scalar(raw))
                self.assertEqual(parsed["title"], raw)


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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m pytest tests/test_authoring.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'authoring.concept'`

- [ ] **Step 4: Create the package and the emitter**

Create `plugins/jsk/skills/jsk/scripts/authoring/__init__.py` containing only:

```python
"""The write half of okf: typed commands that change a bundle.

Every module here obeys one split. schema.py judges and never formats;
concept.py formats and never judges. A validation rule inside a formatter, or a
quoting decision inside the schema, is the seam being crossed.
"""
```

Create `plugins/jsk/skills/jsk/scripts/authoring/concept.py`:

```python
"""One concept file: emit a new one, or change one key of an existing one.

This module formats and does not judge. Whether a value is *allowed* is
schema.py's question; whether it needs quoting is this one's.

The emitter used to live in init_bundle.py. It moved here rather than being
copied, because the spec this implements forbids a second definition of the
format - and two emitters disagreeing about quoting is exactly how a bundle
acquires a file that reads differently from every other file in it.
"""

import re

# A bare scalar is one YAML will read back as the string we wrote. Slugs, dates,
# years and enum values qualify; anything with a colon, a quote, leading or
# trailing space, or a leading indicator character does not. When in doubt this
# quotes, because an over-quoted slug is ugly and an under-quoted colon is a
# parse error in somebody's record.
#
# `\Z` rather than `$`: in Python `$` also matches immediately before a trailing
# newline, so "abc\n" matched BARE and was emitted bare, ending its own
# frontmatter line early.
BARE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*\Z")

# Ordered: the backslash rule must run first, or it re-escapes the backslashes
# the later rules introduce. A value is always emitted as exactly one physical
# line - a newline that survives into the block ends the value early, and
# set_key() below finds a key by scanning lines and would then rewrite the
# wrong one.
ESCAPES = (
    ("\\", "\\\\"),
    ('"', '\\"'),
    ("\n", "\\n"),
    ("\r", "\\r"),
    ("\t", "\\t"),
)


def _quoted(text):
    for old, new in ESCAPES:
        text = text.replace(old, new)
    return '"' + text + '"'


def scalar(value):
    """One frontmatter value, as it should be written.

    Lists are flow style - `[a, b]` - because that is what every concept in a
    real bundle uses and a block list here would make one file look hand-made.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(scalar(v) for v in value) + "]"
    text = str(value)
    if BARE.match(text):
        return text
    return _quoted(text)


def frontmatter(type_name, keys):
    """The `---` block for a new concept. `type` leads; None values are dropped."""
    lines = ["---", f"type: {type_name}"]
    for key, value in keys.items():
        if value is None:
            continue
        lines.append(f"{key}: {scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def new(type_name, keys, body):
    """A whole concept file: frontmatter, a blank line, then the body."""
    body = body or ""
    if body and not body.endswith("\n"):
        body += "\n"
    return frontmatter(type_name, keys) + "\n" + body
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_authoring.py -q`
Expected: PASS, 15 tests

- [ ] **Step 6: Commit**

```bash
git add plugins/jsk/skills/jsk/scripts/authoring/ tests/test_authoring.py tests/fixtures.py
git commit -m "Write core: one frontmatter emitter, owned by the write layer"
```

---

### Task 2: `init_bundle.py` stops defining the format twice

**Files:**
- Modify: `plugins/jsk/skills/jsk/scripts/init_bundle.py:69-75`
- Test: `tests/test_authoring.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_authoring.py`:

```python
from fixtures import INIT_BUNDLE, load_script

init_bundle = load_script(INIT_BUNDLE)


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_authoring.py -k OneEmitter -q`
Expected: FAIL — `init_bundle.yq` is a different function object

- [ ] **Step 3: Replace the duplicate emitter in `init_bundle.py`**

`init_bundle.py:14-18` already inserts its own directory on `sys.path` and imports
`pipeline_model` through it. Add one line beside that import — do **not** add a
second path block:

```python
import pipeline_model  # noqa: E402
from authoring import concept  # noqa: E402
```

Then delete `yq` and `fm` at `init_bundle.py:69-75` and put this in their place:

```python

# Kept as module-level names because this file's callers and tests use them, and
# because `yq` is the older name for what the write layer calls `scalar`. One
# object under two names cannot drift; two functions can.
yq = concept.scalar


def fm(t, title, desc, ts, extra=""):
    """The scaffolder's frontmatter, emitted by the write layer's emitter.

    `extra` is a raw block the caller has already formatted - the bundle
    revision stamp - so it is appended rather than passed through the emitter.
    """
    block = concept.frontmatter(t, {"title": title, "description": desc,
                                    "timestamp": ts})
    if extra:
        block = block[:-len("---\n")] + extra + "---\n"
    return block + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_authoring.py tests/test_init_bundle.py -q`
Expected: PASS — both the new tests and every existing `test_init_bundle.py` test.

The existing scaffolder tests are the real check here. If any fails, the emitter
changed a byte of what `init_bundle.py` writes, and that is a defect in this task
rather than a test to update.

**One byte does change, and it is a fix rather than a regression.** The timestamp
was written bare and is now quoted, because it carries colons. Do not "restore"
the bare form: `okf_compile.py:854-858` records the defect that came from exactly
that shape —

> An unquoted `timestamp: 2026-08-30` in a concept's frontmatter is a date to
> YAML and nothing at all to json, and one reaching a View's passthrough ended
> the whole compile in a TypeError — a bundle problem reported as a crash.

— and its `fix:` line says to quote the value. The emitter now does that
automatically for every bundle it scaffolds. No test asserts the bare form, so
nothing breaks; say it in the commit message so the change is not mistaken for
an accident later.

Dates and years are the deliberate opposite: `start: 2019-04` stays bare, because
`bundle-spec.md:315` documents all three precisions bare and `okf_compile.loose_date`
normalises whatever YAML hands back. A timestamp is an ISO datetime with colons;
a date is not. The two are different shapes and the emitter treats them differently
on purpose.

- [ ] **Step 5: Commit**

```bash
git add plugins/jsk/skills/jsk/scripts/init_bundle.py tests/test_authoring.py
git commit -m "init_bundle: use the write layer's emitter rather than its own"
```

---

### Task 3: Read a concept, and splice exactly one key

This is the task that decides whether people keep using their own editor. A splice
changes the lines for one key and no other byte of the file.

**Files:**
- Modify: `plugins/jsk/skills/jsk/scripts/authoring/concept.py`
- Test: `tests/test_authoring.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_authoring.py`:

```python
import tempfile
from pathlib import Path

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


class Reading(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "care-platform.md"
        self.path.write_text(HAND_WRITTEN, encoding="utf-8")

    def test_meta_is_parsed(self):
        doc = concept.read(self.path)
        self.assertEqual(doc.meta["type"], "Project")
        self.assertEqual(doc.meta["strength"], 3)

    def test_body_is_kept_verbatim(self):
        doc = concept.read(self.path)
        self.assertEqual(doc.body, "# The problem\n\nIt was slow.\n")

    def test_missing_frontmatter_is_refused(self):
        path = Path(self.dir) / "bare.md"
        path.write_text("# Just a heading\n", encoding="utf-8")
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.read(path)
        self.assertIn("no frontmatter", str(caught.exception))


class Splicing(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "care-platform.md"
        self.path.write_text(HAND_WRITTEN, encoding="utf-8")
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
        path = Path(self.dir) / "dupe.md"
        path.write_text("---\ntype: Project\nstrength: 1\nstrength: 2\n---\n\nx\n",
                        encoding="utf-8")
        doc = concept.read(path)
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.set_key(doc, "strength", 5)
        message = str(caught.exception)
        self.assertIn("dupe.md", message)
        self.assertIn("appears twice", message)

    def test_a_block_list_is_refused_rather_than_reflowed(self):
        path = Path(self.dir) / "block.md"
        path.write_text("---\ntype: Project\ntags:\n  - one\n  - two\n---\n\nx\n",
                        encoding="utf-8")
        doc = concept.read(path)
        with self.assertRaises(concept.Unsplicable) as caught:
            concept.set_key(doc, "tags", ["three"])
        self.assertIn("block.md", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_authoring.py -k "Reading or Splicing" -q`
Expected: FAIL — `module 'authoring.concept' has no attribute 'read'`

- [ ] **Step 3: Implement reading and splicing**

Append to `plugins/jsk/skills/jsk/scripts/authoring/concept.py`:

```python
class Unsplicable(Exception):
    """This file cannot be changed safely, and saying so beats guessing.

    Carries the fix line the rest of the tooling prints, because a refusal a
    person cannot act on is only marginally better than a mangled file.
    """


try:
    import yaml
except ImportError:                                  # pragma: no cover
    yaml = None


SPLIT = re.compile(r"^---\n(.*?\n)---\n", re.S)
# A key line, at the top level of the block. The negative lookahead on space is
# what keeps a nested mapping's keys from being mistaken for the block's own.
KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$")


class Concept:
    """One concept file, split into the three parts a command needs.

    `lines` is the frontmatter as written, so a splice can put a line back where
    it found it. `meta` is the same block parsed, for anything that needs to read
    a value rather than rewrite one.
    """

    def __init__(self, path, lines, meta, body):
        self.path = path
        self.lines = lines
        self.meta = meta
        self.body = body

    def text(self, lines=None):
        block = "\n".join(self.lines if lines is None else lines)
        return f"---\n{block}\n---\n\n{self.body}"


def read(path):
    """Parse one concept file, or refuse with a reason naming it."""
    if yaml is None:
        raise Unsplicable(
            "reading a concept needs pyyaml:  pip install pyyaml")
    raw = open(str(path), encoding="utf-8").read()
    match = SPLIT.match(raw)
    if not match:
        raise Unsplicable(
            f"{path}: no frontmatter\n"
            f"fix:  a concept opens with a --- block naming its type")
    block = match.group(1).rstrip("\n")
    body = raw[match.end():].lstrip("\n")
    try:
        meta = yaml.safe_load(block) or {}
    except yaml.YAMLError as exc:
        raise Unsplicable(f"{path}: frontmatter is not valid YAML: {exc}\n"
                          f"fix:  open it and correct the block by hand")
    if not isinstance(meta, dict):
        raise Unsplicable(f"{path}: frontmatter is not a mapping\n"
                          f"fix:  a concept's block is `key: value` lines")
    return Concept(path, block.split("\n"), meta, body)


def locate(doc, key):
    """The single line index defining `key`, or None. Refuses on ambiguity.

    Ambiguity is a refusal rather than a first-match because both alternatives
    silently do the wrong thing: taking the first leaves a second line that still
    says something else, and taking the last is the same defect upside down.
    """
    found = []
    for index, line in enumerate(doc.lines):
        match = KEY.match(line)
        if match and match.group(1) == key:
            found.append(index)
    if len(found) > 1:
        rows = ", ".join(str(i + 2) for i in found)     # +2: the --- and 1-indexing
        raise Unsplicable(
            f"{doc.path}: `{key}` appears twice, at lines {rows}\n"
            f"fix:  delete the wrong one by hand - which is right is not "
            f"something this command can know")
    if not found:
        return None
    index = found[0]
    value = KEY.match(doc.lines[index]).group(2).strip()
    if not value:
        raise Unsplicable(
            f"{doc.path}: `{key}` is written as a block, over several lines\n"
            f"fix:  this command writes flow style - [a, b] - and rewriting the "
            f"block would reflow lines nobody asked it to touch. Change it by hand.")
    return index


def set_key(doc, key, value):
    """The file's text with `key` set, and every other byte where it was."""
    lines = list(doc.lines)
    index = locate(doc, key)
    if value is None:
        if index is not None:
            del lines[index]
        return doc.text(lines)
    rendered = f"{key}: {scalar(value)}"
    if index is None:
        lines.append(rendered)
    else:
        lines[index] = rendered
    return doc.text(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_authoring.py -q`
Expected: PASS, all tests

- [ ] **Step 5: Commit**

```bash
git add plugins/jsk/skills/jsk/scripts/authoring/concept.py tests/test_authoring.py
git commit -m "Write core: splice one key, or refuse and say which line"
```

---

### Task 4: `schema.py` — the only definition of what a type takes

**Files:**
- Create: `plugins/jsk/skills/jsk/scripts/authoring/schema.py`
- Test: `tests/test_authoring.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_authoring.py`:

```python
schema = authoring_module("authoring.schema")


class Schema(unittest.TestCase):
    def test_a_project_needs_a_title(self):
        problems = schema.check("Project", {"role": "eng"})
        self.assertIn("title is required", "; ".join(problems))

    def test_a_known_type_with_its_required_keys_is_clean(self):
        self.assertEqual(schema.check("Project", {"title": "X", "role": "eng"}), [])

    def test_an_unknown_key_is_rejected_not_warned(self):
        problems = schema.check("Project",
                                {"title": "X", "role": "eng", "startDate": "2026"})
        joined = "; ".join(problems)
        self.assertIn("startDate", joined)
        self.assertIn("unknown key", joined)

    def test_the_typo_suggests_the_key_it_meant(self):
        # startDate for start is the defect validate_urs.py gained a hand-written
        # check for. Catching it at write time is the point of this layer.
        problems = schema.check("Role", {"title": "X", "organisation": "acme",
                                         "state": "ongoing", "startDate": "2026"})
        self.assertIn("did you mean `start`", "; ".join(problems))

    def test_seniority_is_a_closed_vocabulary(self):
        problems = schema.check("Project", {"title": "X", "role": "eng",
                                            "seniority": "very-senior"})
        self.assertIn("seniority", "; ".join(problems))

    def test_a_legal_seniority_passes(self):
        self.assertEqual(
            schema.check("Project", {"title": "X", "role": "eng",
                                     "seniority": "architecture-ownership"}), [])

    def test_strength_is_one_to_five(self):
        self.assertIn("strength", "; ".join(
            schema.check("Project", {"title": "X", "role": "eng", "strength": 9})))

    def test_status_is_the_provenance_vocabulary(self):
        self.assertIn("status", "; ".join(
            schema.check("Project", {"title": "X", "role": "eng",
                                     "status": "probably"})))

    def test_an_unknown_type_is_refused(self):
        self.assertIn("unknown concept type",
                      "; ".join(schema.check("Widget", {"title": "X"})))

    def test_extension_keys_are_allowed_when_declared(self):
        # --set is the escape hatch for keys the schema does not name.
        self.assertEqual(
            schema.check("Project", {"title": "X", "role": "eng",
                                     "custom_field": "v"},
                         extensions=("custom_field",)), [])

    def test_the_escape_hatch_does_not_swallow_a_typo(self):
        # Declaring a near-miss as an extension must not launder it. This is the
        # hole a --set that accepted anything would open.
        problems = schema.check("Role", {"title": "X", "organisation": "acme",
                                         "state": "ongoing", "startDate": "2026"},
                                extensions=("startDate",))
        self.assertIn("did you mean `start`", "; ".join(problems))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_authoring.py -k Schema -q`
Expected: FAIL — `No module named 'authoring.schema'`

- [ ] **Step 3: Implement the schema**

Create `plugins/jsk/skills/jsk/scripts/authoring/schema.py`:

```python
"""What each concept type takes, and what each value must satisfy.

This is the only machine-readable statement of the format. `bundle-spec.md` is
its prose counterpart and the two are meant to be read together; a rule that
exists in one and not the other is a defect in whichever is missing it.

This module judges and does not format. It returns problems as strings a person
can act on, never exit codes and never output - what to do about a problem is
the caller's decision.
"""

import difflib

# The closed vocabularies. Each compares as an exact string, which is the whole
# reason they are closed: a synonym does not fail, it silently stops matching.
VOCABULARIES = {
    "seniority": ("architecture-ownership", "product-ownership", "platform-design",
                  "team-leadership", "technical-ownership", "hands-on-senior",
                  "hands-on", "junior"),
    "status": ("confirmed", "inferred", "needs-verification"),
    "state": ("ended", "ongoing", "unknown"),
    "change": ("hire", "promotion", "lateral", "title-change"),
    "relationship": ("employer", "prospect", "both"),
}


class Key:
    """One frontmatter key: what it is called, what it holds, whether it is required."""

    def __init__(self, name, kind, required=False):
        self.name = name
        self.kind = kind
        self.required = required


# Keys every concept may carry. `type` is not here: it is the argument, not a key.
COMMON = (
    Key("title", "text"),
    Key("description", "text"),
    Key("tags", "slugs"),
    Key("timestamp", "text"),
    Key("status", "vocab:status"),
)

TYPES = {
    "Project": COMMON + (
        Key("title", "text", required=True),
        Key("role", "slug", required=True),
        Key("strength", "rank"),
        Key("recency", "year"),
        Key("seniority", "vocab:seniority"),
        Key("domains", "slugs"),
        Key("capabilities", "slugs"),
        Key("technologies", "slugs"),
        Key("headline_metric", "text"),
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    "Role": COMMON + (
        Key("title", "text", required=True),
        Key("functional_title", "text"),
        Key("organisation", "slug", required=True),
        Key("start", "date"),
        Key("end", "date"),
        Key("state", "vocab:state", required=True),
        Key("seniority", "vocab:seniority"),
        Key("change", "vocab:change"),
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    "Organisation": COMMON + (
        Key("title", "text", required=True),
        Key("relationship", "vocab:relationship", required=True),
        Key("industry", "text"),
        Key("sector", "text"),
        Key("size", "text"),
        Key("url", "text"),
    ),
}


def _kinds(type_name):
    """{key name: Key}. Later entries win, so a type may sharpen a COMMON key."""
    return {key.name: key for key in TYPES[type_name]}


def _value_problem(key, value):
    """What is wrong with this value, or None."""
    if key.kind.startswith("vocab:"):
        allowed = VOCABULARIES[key.kind.split(":", 1)[1]]
        if value not in allowed:
            return (f"{key.name}: {value!r} is not one of "
                    f"{', '.join(allowed)}")
    elif key.kind == "rank":
        if not isinstance(value, int) or not 1 <= value <= 5:
            return f"{key.name}: {value!r} is not a whole number from 1 to 5"
    elif key.kind == "year":
        if not (isinstance(value, int) and 1900 <= value <= 2200):
            return f"{key.name}: {value!r} is not a four-digit year"
    elif key.kind == "slugs":
        if not isinstance(value, (list, tuple)):
            return f"{key.name}: {value!r} is not a list"
    return None


def check(type_name, values, extensions=()):
    """Every problem with these values, as sentences. Empty means clean.

    `extensions` are keys the caller declared with --set. They are accepted
    without a kind, because an extension key is by definition one this schema
    does not model - `bundle-spec.md` says type is the only key OKF requires and
    everything past the recommended handful is an extension.

    What an extension may not be is a near-miss of a real key. `--set
    startDate=2026` is the defect this layer exists to stop, and an escape hatch
    that swallows it silently is not an escape hatch, it is the hole. So the
    spelling check runs on extensions too; only the kind check is skipped.
    """
    if type_name not in TYPES:
        return [f"unknown concept type: {type_name}\n"
                f"fix:  one of {', '.join(sorted(TYPES))}"]
    kinds = _kinds(type_name)
    problems = []
    for name, value in values.items():
        key = kinds.get(name)
        if key is None:
            near = difflib.get_close_matches(name, kinds, n=1, cutoff=0.7)
            if near:
                problems.append(
                    f"unknown key `{name}` on a {type_name} - did you mean "
                    f"`{near[0]}`?\n"
                    f"fix:  a key one letter away from a real one loses whatever "
                    f"it was meant to say, silently. Correct the spelling, or "
                    f"rename it to something no real key is close to.")
            elif name not in extensions:
                problems.append(f"unknown key `{name}` on a {type_name}\n"
                                f"fix:  --set {name}=... writes it as an "
                                f"extension key if that is what you meant")
            continue
        if value is None:
            continue
        problem = _value_problem(key, value)
        if problem:
            problems.append(problem)
    for key in kinds.values():
        if key.required and values.get(key.name) in (None, ""):
            problems.append(f"{key.name} is required on a {type_name}")
    return problems
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_authoring.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/jsk/skills/jsk/scripts/authoring/schema.py tests/test_authoring.py
git commit -m "Write core: one machine-readable definition of what a type takes"
```

---

### Task 5: `stage.py` — the changeset, and a commit order that fails repairably

**Files:**
- Create: `plugins/jsk/skills/jsk/scripts/authoring/stage.py`
- Test: `tests/test_authoring.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_authoring.py`:

```python
import os

stage = authoring_module("authoring.stage")


class Staging(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def path(self, name):
        return str(Path(self.dir) / name)

    def test_dry_run_writes_nothing(self):
        change = stage.Changeset()
        change.write(self.path("a.md"), "content\n", kind="concept")
        result = stage.commit(change, dry_run=True)
        self.assertFalse(os.path.exists(self.path("a.md")))
        self.assertEqual(result["changed"], [self.path("a.md")])
        self.assertTrue(result["dry_run"])

    def test_commit_writes_every_file(self):
        change = stage.Changeset()
        change.write(self.path("a.md"), "one\n", kind="concept")
        change.write(self.path("b.md"), "two\n", kind="companion")
        stage.commit(change)
        self.assertEqual(Path(self.path("a.md")).read_text(encoding="utf-8"), "one\n")
        self.assertEqual(Path(self.path("b.md")).read_text(encoding="utf-8"), "two\n")

    def test_the_concept_commits_before_its_companions(self):
        # A partial failure must land on the repairable side: a concept with no
        # index entry is a validate_bundle warning that okf reindex can fix. An
        # index entry naming a file that never landed is a broken link, and
        # nothing can regenerate the concept it wanted.
        change = stage.Changeset()
        change.write(self.path("index.md"), "listing\n", kind="companion")
        change.write(self.path("concept.md"), "body\n", kind="concept")
        self.assertEqual([os.path.basename(p) for p in change.ordered()],
                         ["concept.md", "index.md"])

    def test_nothing_lands_when_a_later_write_fails(self):
        change = stage.Changeset()
        change.write(self.path("a.md"), "one\n", kind="concept")
        change.write(str(Path(self.dir) / "missing-dir" / "b.md"), "two\n",
                     kind="companion")
        with self.assertRaises(stage.Refused):
            stage.commit(change)
        self.assertFalse(os.path.exists(self.path("a.md")))

    def test_no_temp_files_are_left_behind(self):
        change = stage.Changeset()
        change.write(self.path("a.md"), "one\n", kind="concept")
        stage.commit(change)
        self.assertEqual(sorted(os.listdir(self.dir)), ["a.md"])

    def test_json_payload_reports_ids(self):
        change = stage.Changeset()
        change.write(self.path("a.md"), "one\n", kind="concept")
        change.record_id("project", "care-platform")
        result = stage.commit(change)
        self.assertEqual(result["ids"], {"project": "care-platform"})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_authoring.py -k Staging -q`
Expected: FAIL — `No module named 'authoring.stage'`

- [ ] **Step 3: Implement staging**

Create `plugins/jsk/skills/jsk/scripts/authoring/stage.py`:

```python
"""The transaction: collect every file a command touches, then commit them.

os.replace is atomic for one file and not across several, so this is not a
transaction in the database sense and does not claim to be. What it guarantees
is weaker and worth having: every file is fully written and validated before any
of them is visible, and the order they become visible in is chosen so that an
interruption leaves the bundle in the state somebody can repair.

That order is the concept first, its derived companions after. A concept with no
index entry is a validate_bundle.py warning and `okf reindex` rebuilds it from
the tree. An index entry naming a concept that never landed is a broken link,
and nothing can regenerate the file it wanted.
"""

import os

# Lower commits first. The names are the vocabulary a command uses when it stages
# a file, so the ordering rule is stated once here rather than at each call site.
ORDER = {"concept": 0, "companion": 1, "log": 2}

SUFFIX = ".okf-tmp"


class Refused(Exception):
    """A command declined to change the bundle, with a reason and a fix."""


class Changeset:
    """What one command intends to change. Nothing here has touched the disk."""

    def __init__(self):
        self._files = []          # (order, path, text)
        self.ids = {}

    def write(self, path, text, kind="companion"):
        if kind not in ORDER:
            raise Refused(f"unknown staging kind: {kind}\n"
                          f"fix:  one of {', '.join(sorted(ORDER))}")
        self._files.append((ORDER[kind], str(path), text))

    def record_id(self, name, value):
        """An id the caller minted, for the --json payload the agent reads back."""
        self.ids[name] = value

    def ordered(self):
        """The paths, in the order they will become visible."""
        return [path for _, path, _ in sorted(self._files, key=lambda f: f[0])]


def commit(changeset, dry_run=False):
    """Write, then publish. Returns the payload --json prints.

    Everything is written to a sibling temp file first, so a failure part-way
    through the writing phase publishes nothing at all. Only the rename phase can
    leave a partial result, and that is what ORDER exists to make survivable.
    """
    payload = {"changed": changeset.ordered(), "ids": changeset.ids,
               "dry_run": bool(dry_run)}
    if dry_run:
        return payload

    staged = []
    try:
        for _, path, text in sorted(changeset._files, key=lambda f: f[0]):
            temp = path + SUFFIX
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            staged.append((temp, path))
    except OSError as exc:
        for temp, _ in staged:
            _discard(temp)
        raise Refused(f"could not stage the change: {exc}\n"
                      f"fix:  nothing was written - check the path exists and "
                      f"is writable")

    for temp, path in staged:
        os.replace(temp, path)
    return payload


def _discard(path):
    try:
        os.unlink(path)
    except OSError:
        pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_authoring.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/jsk/skills/jsk/scripts/authoring/stage.py tests/test_authoring.py
git commit -m "Write core: stage every file, publish in repairable order"
```

---

### Task 6: `bookkeeping.py` — the derived companions

The five-file braindump write is the problem this layer exists for. Two of those
five are mechanical: the directory's `index.md` entry, and the `log.md` row.

**Files:**
- Create: `plugins/jsk/skills/jsk/scripts/authoring/bookkeeping.py`
- Test: `tests/test_authoring.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_authoring.py`:

```python
bookkeeping = authoring_module("authoring.bookkeeping")

INDEX = """---
type: Index
title: "Projects"
---

# Contents

- [Ledger rebuild](ledger-rebuild.md) - the general ledger migration
"""

LOG = """---
type: Log
title: "Log"
---

# History

## 2026-08-01

- Captured the ledger rebuild.
"""


class Bookkeeping(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.projects = Path(self.dir) / "projects"
        self.projects.mkdir()
        (self.projects / "index.md").write_text(INDEX, encoding="utf-8")
        (Path(self.dir) / "log.md").write_text(LOG, encoding="utf-8")

    def test_index_entry_is_appended_in_order(self):
        text = bookkeeping.index_entry(
            self.projects / "index.md", "care-platform.md", "Care platform",
            "Multi-tenant platform for aged-care providers.")
        self.assertIn("- [Ledger rebuild](ledger-rebuild.md)", text)
        self.assertIn("- [Care platform](care-platform.md) - Multi-tenant platform",
                      text)
        self.assertLess(text.index("Ledger rebuild"), text.index("Care platform"))

    def test_an_entry_already_present_is_not_duplicated(self):
        once = bookkeeping.index_entry(
            self.projects / "index.md", "ledger-rebuild.md", "Ledger rebuild", "x")
        self.assertEqual(once.count("ledger-rebuild.md"), 1)

    def test_log_row_is_appended_under_a_dated_heading(self):
        text = bookkeeping.log_entry(Path(self.dir) / "log.md",
                                     "Added the care platform project.", "2026-08-31")
        self.assertIn("## 2026-08-31", text)
        self.assertIn("- Added the care platform project.", text)

    def test_log_keeps_what_was_already_there(self):
        text = bookkeeping.log_entry(Path(self.dir) / "log.md", "New thing.",
                                     "2026-08-31")
        self.assertIn("- Captured the ledger rebuild.", text)
        self.assertLess(text.index("2026-08-01"), text.index("2026-08-31"))

    def test_a_second_entry_on_one_day_reuses_the_heading(self):
        first = bookkeeping.log_entry(Path(self.dir) / "log.md", "One.", "2026-08-31")
        (Path(self.dir) / "log.md").write_text(first, encoding="utf-8")
        second = bookkeeping.log_entry(Path(self.dir) / "log.md", "Two.", "2026-08-31")
        self.assertEqual(second.count("## 2026-08-31"), 1)
        self.assertIn("- One.\n- Two.", second)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_authoring.py -k Bookkeeping -q`
Expected: FAIL — `No module named 'authoring.bookkeeping'`

- [ ] **Step 3: Implement bookkeeping**

Create `plugins/jsk/skills/jsk/scripts/authoring/bookkeeping.py`:

```python
"""The companions a concept write implies, derived rather than remembered.

mode-braindump.md instructs five files in one sentence and nothing makes them
atomic. Two of the five are mechanical - the directory's index entry and the
log row - so they are computed here from what the command already knows, and
staged alongside the concept rather than left to be remembered.

Every function returns the whole new text of one file. Nothing here writes;
stage.py does that, because a function that both decides and writes cannot be
dry-run.
"""

import os
import re


def index_entry(path, filename, title, description):
    """`index.md` with this concept listed, appended and never duplicated.

    Appended rather than sorted: these files are hand-maintained, some are
    deliberately ordered by importance rather than alphabetically, and a command
    that reorders somebody's index has changed something it was not asked to.
    """
    text = open(str(path), encoding="utf-8").read()
    if f"({filename})" in text:
        return text
    entry = f"- [{title}]({filename})"
    if description:
        entry += f" - {description}"
    if not text.endswith("\n"):
        text += "\n"
    return text + entry + "\n"


HEADING = "## %s"


def log_entry(path, message, today):
    """`log.md` with one line appended under today's heading.

    The heading is reused where it exists, so a day's work reads as a day's work
    rather than as one entry per command.
    """
    text = open(str(path), encoding="utf-8").read()
    heading = HEADING % today
    line = f"- {message}"
    if heading in text:
        # Append after the last line already under this heading, so ordering
        # inside a day matches the order things actually happened.
        block = re.search(re.escape(heading) + r"\n(?:.*\n)*?(?=\n*##\s|\Z)", text)
        end = block.end()
        prefix = text[:end].rstrip("\n")
        return prefix + "\n" + line + "\n" + text[end:]
    if not text.endswith("\n"):
        text += "\n"
    return text + f"\n{heading}\n\n{line}\n"


def index_path(bundle, directory):
    """The index.md a concept in `directory` belongs to."""
    return os.path.join(str(bundle), directory, "index.md")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_authoring.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/jsk/skills/jsk/scripts/authoring/bookkeeping.py tests/test_authoring.py
git commit -m "Write core: derive the index entry and the log row"
```

---

### Task 7: `okf project add`, end to end

The command that proves the core. It writes the concept, the index entry and the
log row as one changeset, and refuses a role that does not resolve or a
capability that is not in the vocabulary.

**Files:**
- Create: `plugins/jsk/skills/jsk/scripts/authoring/commands.py`
- Modify: `plugins/jsk/skills/jsk/scripts/okf.py`
- Modify: `tests/fixtures.py`
- Test: `tests/test_authoring.py`

- [ ] **Step 1: Add a bundle builder to `tests/fixtures.py`**

Append to `tests/fixtures.py`:

```python
def bundle_with(root, roles=("lead-engineer",), capabilities=("ai-platform-architecture",)):
    """A minimal bundle the write commands can act on.

    Built by hand rather than by init_bundle.py: these tests are about what a
    command refuses, so the fixture needs to be able to omit the thing being
    refused for.
    """
    root = Path(root)
    for directory in ("projects", "roles", "framework"):
        (root / directory).mkdir(parents=True, exist_ok=True)
        (root / directory / "index.md").write_text(
            '---\ntype: Index\ntitle: "Index"\n---\n\n# Contents\n',
            encoding="utf-8")
    (root / "index.md").write_text(
        '---\ntype: Index\ntitle: "Bundle"\nokf_bundle: 7\n---\n\n# Purpose\n',
        encoding="utf-8")
    (root / "log.md").write_text(
        '---\ntype: Log\ntitle: "Log"\n---\n\n# History\n', encoding="utf-8")
    for role in roles:
        (root / "roles" / f"{role}.md").write_text(
            f'---\ntype: Role\ntitle: "{role}"\norganisation: acme\n'
            f'state: ongoing\n---\n\n# Tenure\n', encoding="utf-8")
    vocab = "# Vocabulary\n\n## Platform\n\n" + "".join(
        f"- `{value}`\n" for value in capabilities)
    (root / "framework" / "capability-vocabulary.md").write_text(
        '---\ntype: Vocabulary\ntitle: "Capabilities"\n---\n\n' + vocab,
        encoding="utf-8")
    return str(root)
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_authoring.py`:

```python
import json

from fixtures import SCRIPTS, bundle_with, run

OKF = SCRIPTS / "okf.py"


class ProjectAdd(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.bundle = bundle_with(self.dir)

    def add(self, *extra, body="# The problem\n\nIt was slow.\n"):
        args = ["project", "add", "--bundle", self.bundle,
                "--title", "Care platform", "--role", "lead-engineer"] + list(extra)
        import subprocess, sys as _sys
        proc = subprocess.run([_sys.executable, str(OKF)] + args,
                              input=body, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def test_a_project_is_written(self):
        code, output = self.add()
        self.assertEqual(code, 0, output)
        path = Path(self.bundle) / "projects" / "care-platform.md"
        self.assertTrue(path.exists(), output)
        text = path.read_text(encoding="utf-8")
        self.assertIn("type: Project", text)
        self.assertIn('title: "Care platform"', text)
        self.assertIn("role: lead-engineer", text)
        self.assertIn("# The problem", text)

    def test_the_index_and_log_are_updated_in_the_same_run(self):
        self.add()
        index = (Path(self.bundle) / "projects" / "index.md").read_text(encoding="utf-8")
        log = (Path(self.bundle) / "log.md").read_text(encoding="utf-8")
        self.assertIn("care-platform.md", index)
        self.assertIn("Care platform", log)

    def test_a_role_that_does_not_resolve_is_refused(self):
        code, output = self.add("--role", "nobody")
        self.assertEqual(code, 1)
        self.assertIn("nobody", output)
        self.assertFalse((Path(self.bundle) / "projects" / "care-platform.md").exists())

    def test_a_capability_outside_the_vocabulary_is_refused(self):
        code, output = self.add("--capability", "made-up-thing")
        self.assertEqual(code, 1)
        self.assertIn("made-up-thing", output)
        self.assertIn("capability-vocabulary.md", output)

    def test_a_capability_in_the_vocabulary_is_accepted(self):
        code, output = self.add("--capability", "ai-platform-architecture")
        self.assertEqual(code, 0, output)
        text = (Path(self.bundle) / "projects" / "care-platform.md").read_text(
            encoding="utf-8")
        self.assertIn("capabilities: [ai-platform-architecture]", text)

    def test_new_capability_adds_it_to_the_vocabulary_in_the_same_change(self):
        code, output = self.add("--new-capability", "edge-inference",
                                "--theme", "Platform")
        self.assertEqual(code, 0, output)
        vocab = (Path(self.bundle) / "framework" / "capability-vocabulary.md").read_text(
            encoding="utf-8")
        self.assertIn("- `edge-inference`", vocab)

    def test_an_unknown_flag_is_refused_rather_than_written(self):
        code, output = self.add("--set", "startDate=2026")
        self.assertEqual(code, 1)
        self.assertIn("start", output)

    def test_dry_run_writes_nothing(self):
        code, output = self.add("--dry-run")
        self.assertEqual(code, 0, output)
        self.assertFalse((Path(self.bundle) / "projects" / "care-platform.md").exists())

    def test_json_reports_what_it_wrote(self):
        code, output = self.add("--json")
        self.assertEqual(code, 0, output)
        payload = json.loads(output)
        self.assertEqual(payload["ids"]["project"], "care-platform")
        self.assertTrue(any("care-platform.md" in p for p in payload["changed"]))

    def test_refusing_to_overwrite_an_existing_concept(self):
        self.add()
        code, output = self.add()
        self.assertEqual(code, 1)
        self.assertIn("already exists", output)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m pytest tests/test_authoring.py -k ProjectAdd -q`
Expected: FAIL — `unknown command: project`

- [ ] **Step 4: Implement the command**

Create `plugins/jsk/skills/jsk/scripts/authoring/commands.py`:

```python
"""One function per noun-verb. Assembles the other modules and decides nothing.

A validation rule here is a rule in the wrong place: schema.py owns what is
legal, concept.py owns how it is written, stage.py owns when it lands. What is
left for this module is which of them to call, and in what order.
"""

import argparse
import datetime
import json
import os
import re
import sys

from . import bookkeeping, concept, schema, stage

VOCABULARY = os.path.join("framework", "capability-vocabulary.md")
# bundle-spec.md: only list items count as vocabulary; prose and fenced examples
# are ignored. The same rule as validate_bundle.py reads it by.
TERM = re.compile(r"^\s*[-*]\s+`([^`]+)`", re.M)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def vocabulary(bundle):
    """Every capability the bundle declares. Empty means unchecked, not empty."""
    path = os.path.join(bundle, VOCABULARY)
    if not os.path.exists(path):
        return None
    terms = TERM.findall(open(path, encoding="utf-8").read())
    return set(terms) if terms else None


def add_vocabulary(bundle, term, theme):
    """The vocabulary file with `term` listed under `theme`, created if absent."""
    path = os.path.join(bundle, VOCABULARY)
    text = open(path, encoding="utf-8").read()
    heading = f"## {theme}"
    if heading not in text:
        if not text.endswith("\n"):
            text += "\n"
        return path, text + f"\n{heading}\n\n- `{term}`\n"
    block = re.search(re.escape(heading) + r"\n(?:.*\n)*?(?=\n*##\s|\Z)", text)
    end = block.end()
    return path, text[:end].rstrip("\n") + f"\n- `{term}`\n" + text[end:]


def project_add(args):
    """Write one Project concept, its index entry and its log row, as one change."""
    bundle = args.bundle
    if not os.path.isdir(os.path.join(bundle, "projects")):
        raise stage.Refused(
            f"not a bundle: {bundle}\n"
            f"fix:  --bundle takes a directory holding projects/ and roles/")

    stem = args.slug or slug(args.title)
    path = os.path.join(bundle, "projects", f"{stem}.md")
    if os.path.exists(path):
        raise stage.Refused(
            f"{path} already exists\n"
            f"fix:  `okf project set {stem}` changes a concept that is already "
            f"there; add writes a new one")

    role_path = os.path.join(bundle, "roles", f"{args.role}.md")
    if not os.path.exists(role_path):
        raise stage.Refused(
            f"no such role: {args.role}\n"
            f"fix:  --role takes a Role file's stem, and {role_path} is not "
            f"there. A project whose role cannot be placed cannot go on a resume.")

    change = stage.Changeset()

    capabilities = list(args.capability or [])
    known = vocabulary(bundle)
    if args.new_capability:
        if not args.theme:
            raise stage.Refused(
                "--new-capability needs --theme\n"
                "fix:  the vocabulary is grouped by theme, and an ungrouped term "
                "is one nobody will find when they go looking for a synonym")
        for term in args.new_capability:
            vocab_path, vocab_text = add_vocabulary(bundle, term, args.theme)
            change.write(vocab_path, vocab_text, kind="companion")
            capabilities.append(term)
            if known is not None:
                known.add(term)
    if known is not None:
        unknown = [c for c in capabilities if c not in known]
        if unknown:
            raise stage.Refused(
                f"not in the capability vocabulary: {', '.join(unknown)}\n"
                f"fix:  capabilities compare as exact strings, so a synonym "
                f"silently stops matching. Either use an existing term from "
                f"{VOCABULARY}, or add this one with "
                f"--new-capability {unknown[0]} --theme \"<theme>\"")

    extensions = {}
    for pair in args.set or []:
        if "=" not in pair:
            raise stage.Refused(f"--set takes key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        extensions[key] = value

    now = datetime.datetime.now(datetime.timezone.utc)
    values = {
        "title": args.title,
        "description": args.description,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": args.status,
        "role": args.role,
        "strength": args.strength,
        "recency": args.recency,
        "seniority": args.seniority,
        "domains": list(args.domain or []) or None,
        "capabilities": capabilities or None,
        "technologies": list(args.technology or []) or None,
        "headline_metric": args.headline_metric,
    }
    values = {k: v for k, v in values.items() if v is not None}
    values.update(extensions)

    problems = schema.check("Project", values, extensions=tuple(extensions))
    if problems:
        raise stage.Refused("\n".join(problems))

    body = args.body
    if body == "-":
        body = sys.stdin.read()
    change.write(path, concept.new("Project", values, body or ""), kind="concept")

    index = bookkeeping.index_path(bundle, "projects")
    change.write(index,
                 bookkeeping.index_entry(index, f"{stem}.md", args.title,
                                         args.description or ""),
                 kind="companion")

    log = os.path.join(bundle, "log.md")
    if os.path.exists(log):
        change.write(log,
                     bookkeeping.log_entry(log, f"Added project {args.title}.",
                                           now.strftime("%Y-%m-%d")),
                     kind="log")

    change.record_id("project", stem)
    return change


def parser():
    root = argparse.ArgumentParser(prog="okf project", add_help=True)
    verbs = root.add_subparsers(dest="verb", required=True)

    add = verbs.add_parser("add", help="write a new Project concept")
    add.add_argument("--bundle", required=True)
    add.add_argument("--title", required=True)
    add.add_argument("--slug")
    add.add_argument("--description")
    add.add_argument("--role", required=True)
    add.add_argument("--strength", type=int)
    add.add_argument("--recency", type=int)
    add.add_argument("--seniority")
    add.add_argument("--domain", action="append")
    add.add_argument("--capability", action="append")
    add.add_argument("--new-capability", action="append")
    add.add_argument("--theme")
    add.add_argument("--technology", action="append")
    add.add_argument("--headline-metric", dest="headline_metric")
    add.add_argument("--status", default="confirmed")
    add.add_argument("--body", default="-",
                     help="the concept body; `-` reads stdin")
    add.add_argument("--set", action="append",
                     help="an extension key, as key=value")
    add.add_argument("--dry-run", action="store_true")
    add.add_argument("--json", action="store_true")
    add.set_defaults(build=project_add)
    return root


def main(argv):
    args = parser().parse_args(argv)
    try:
        change = args.build(args)
        payload = stage.commit(change, dry_run=args.dry_run)
    except (stage.Refused, concept.Unsplicable) as exc:
        print(f"FAIL  {exc}")
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for path in payload["changed"]:
            print(f"{'would write' if args.dry_run else 'wrote'}  {path}")
        for name, value in payload["ids"].items():
            print(f"{name}: {value}")
    return 0
```

- [ ] **Step 5: Route it from `okf.py`**

In `plugins/jsk/skills/jsk/scripts/okf.py`, add a handler beside the existing ones.
Put `cmd_project` next to `cmd_score`:

```python
def cmd_project(args):
    """The write half: typed commands that change a bundle.

    Imported rather than spawned, unlike the read commands above. These are the
    only subcommands that write, and a write that reports success from a child
    process nobody checked is exactly the failure mode this layer exists to
    remove.
    """
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from authoring import commands              # noqa: PLC0415 - only when asked
    return commands.main(list(args))
```

Then add it to `HANDLERS`:

```python
HANDLERS = {
    "doctor": cmd_doctor,
    "validate": cmd_validate,
    "check": cmd_check,
    "gates": cmd_gates,
    "score": cmd_score,
    "project": cmd_project,
}
```

And add one line to the module docstring's command list, after the `okf pipeline`
line, so `okf --help` lists it:

```
    okf project add --bundle B --title T --role R   write a Project concept
```

- [ ] **Step 6: Pin the new subcommand in the surface test**

`tests/test_okf.py:20` lists the subcommands `--help` must name. Add `project`,
so the surface stays pinned rather than merely happening to work:

```python
SUBCOMMANDS = ["doctor", "new", "validate", "render", "check", "gates", "score",
               "fit", "project"]
```

Run: `python -m pytest tests/test_okf.py -q`
Expected: PASS. If `test_help_lists_every_subcommand` fails, the docstring line
from Step 5 is missing or misspelled.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_authoring.py -q`
Expected: PASS, all classes including `ProjectAdd`

- [ ] **Step 8: Run the whole suite**

Run: `python -m pytest tests -q`

**The baseline on this branch, measured before any of this work, is `595 passed,
2 skipped`.** Expected now: 595 plus the new tests, still 2 skipped, zero
failures. A third skip means a test started skipping itself for a reason worth
understanding, not a pass.

`test_okf.py` and `test_plugin_surface.py` are the ones most likely to notice a
new subcommand — if either fails, read what it asserts before changing anything,
because those two pin the documented surface on purpose.

- [ ] **Step 9: Commit**

```bash
git add plugins/jsk/skills/jsk/scripts/authoring/commands.py plugins/jsk/skills/jsk/scripts/okf.py tests/test_authoring.py tests/test_okf.py tests/fixtures.py
git commit -m "okf project add: the write core, proven end to end"
```

---

## Self-review notes for the executor

After Task 7, before reporting the plan complete, confirm each of these by running
something rather than by reading:

1. `python -m pytest tests -q` is green, with no more skips than the baseline.
2. `python plugins/jsk/skills/jsk/scripts/okf.py --help` lists `project`.
3. `python plugins/jsk/skills/jsk/scripts/okf.py project add --help` prints the flags.
4. A `--dry-run` against a real scaffolded bundle leaves `git status` clean:

```bash
python plugins/jsk/skills/jsk/scripts/init_bundle.py /tmp/okf-check --name "Test Person"
echo "# The problem" | python plugins/jsk/skills/jsk/scripts/okf.py project add \
  --bundle /tmp/okf-check --title "A project" --role missing-role
# expect: exit 1, naming missing-role
```

## What this plan deliberately does not build

Named so a reviewer does not report them as gaps:

- `project set`, `retire`, `rm`, and every other tranche-1 verb — the next plan.
- `bullet`, `skill`, `credential`, `metric` and the `blocks()` emitter — the next plan,
  along with the bullet-id materialisation and the `validate_urs.py` warning.
- Tailoring and archive commands — tranches 2 and 3.
- The enforcement edits to `SKILL.md`, the mode files and the two agent definitions.
  Those land last, because instructing an agent to use a command that does not exist
  yet is worse than leaving the instruction alone.
