"""A concept's body: the authored blocks and the prose sections, addressed by name.

Frontmatter is mechanical and concept.py splices it. The body is not: almost
everything in a bundle is a frontmatter key, and the two things that are *written*
- a project's `# Bullets`, a Skill Set's `# Skills`, a Certification Status's
`# Held` - live here. So does the prose under each `#` heading.

This module parses and emits and does not judge. Whether a field value is allowed
is schema.py's question.

**The claim is the atom, and that is a necessity rather than a taste.** Every
addressable unit in a bundle carries a `status`. Change half a sentence of a
`status: confirmed` bullet and the status now asserts that a person signed off on
text that no longer exists - so a writer has to know where a claim begins and
ends in order to reset provenance across it, and a line-level patch by definition
does not. Below the item, the floor is the section: fixing a typo mid-paragraph
means restating the section, which the caller had to read anyway to know what to
fix.

## Faithful to the compiler, including where the compiler is crude

`okf_compile.blocks()` is the definition of this shape - *the one shape in the
bundle a script cannot derive, so it is written down plainly and parsed the same
way wherever it appears*. The parsing rules here are its rules, character for
character, and the two that look like defects are copied deliberately:

  - **A block ends at the next level-one heading and nowhere else.** blocks()
    terminates on `(?=^#\\s|\\Z)`, so `## Anything` does not end a block. A `#`
    section written under `# Bullets` is therefore inside the bullets, to both
    readers.
  - **Neither the heading search nor the item split knows about ``` fences.** A
    fenced example containing `# Bullets` is found as the real heading, by the
    compiler and by this module alike.

Diverging on either would be worse than the crudeness: a writer that read a
concept differently from the compiler would put a claim where the compile does
not see it, or edit the one it does not read. `ItemsMatchTheCompiler` in
tests/test_authoring_body.py pins the agreement over every shape, so a change to
blocks() breaks a test here rather than silently splitting the two readers.

## What a write preserves

An item the caller did not touch keeps its own bytes - its wrapping, its field
order, its spacing. Only an item that changed is restated in canonical form,
because its text is new text. That is the same trade concept.py makes on
frontmatter, for the same reason: a tool that reflows somebody's file once is a
tool they never run again.
"""

import re

from .. import markup
from . import bookkeeping, concept

# blocks()' own three patterns, as this module needs them.
#
# The heading is `#+` at any level, the name matched literally: a name with a
# regex character in it - `C# / .NET` is a real skill name, though not a real
# heading - would otherwise compile to a pattern matching something else.
ITEM = re.compile(r"^\s*-\s+")

# A level-one heading, and the only thing that ends a block. Not `#{1,6}`: see the
# module docstring on why the compiler's crudeness is copied rather than fixed.
TERMINATOR = re.compile(r"^#\s")

# Any heading, for naming what a body actually holds when a caller asks for a
# section that is not there. `#+` with the level captured, so a section's own
# extent can be measured the way vocabulary_with() measures a theme's.
ANY_HEADING = re.compile(r"^(#+)\s*(.*?)\s*$")

# Two spaces, which is what bundle-spec.md writes and what every item in a
# scaffolded bundle wears. blocks() strips each line before reading it, so the
# indent is for a person rather than for the parser - which is the argument for
# matching the file that a person already has open.
INDENT = "  "

# The three authored blocks: what the compiler parses, and the order this module
# writes them in.
#
# Two tuples per kind, deliberately. `_KEYS` is okf_compile's own argument to
# blocks() and must stay identical to it - a key missing from it is a field that
# becomes part of the sentence. `_ORDER` is the shape the file wears, which is
# bundle-spec.md's, and is nothing to do with the parser: the compiler strips each
# line before reading it and has no opinion about which comes first.
#
# `id` leads every kind. bundle-spec.md's one example carrying an id puts it first,
# and an item's id is its name - a name written under the claim it names reads like
# an afterthought. Consistency across the three matters more than either argument,
# because these files are read side by side.
BULLET_KEYS = ("status", "metric", "for", "id")
BULLET_ORDER = ("id", "metric", "for", "status")

SKILL_KEYS = ("id", "category", "aliases", "last_used")
SKILL_ORDER = ("id", "category", "aliases", "last_used")

HELD_KEYS = ("issuer", "issued", "expires", "status", "id")
HELD_ORDER = ("id", "issuer", "issued", "expires", "status")

# One place naming all three, so a command says which kind of claim it is writing
# and gets the heading, the parser's keys, the file's order and the id prefix
# together. A command that assembled these itself would be the fifth place the
# shape of a bullet is written down.
KINDS = {
    "bullet": {"heading": "Bullets", "keys": BULLET_KEYS, "order": BULLET_ORDER,
               "prefix": "ach", "noun": "bullet"},
    "skill": {"heading": "Skills", "keys": SKILL_KEYS, "order": SKILL_ORDER,
              "prefix": "skill", "noun": "skill"},
    "credential": {"heading": "Held", "keys": HELD_KEYS, "order": HELD_ORDER,
                   "prefix": "cred", "noun": "credential"},
}


def heading_pattern(name):
    """blocks()' heading regex for one block name, at any level."""
    return re.compile(r"^#+\s*%s\s*$" % re.escape(name))


class Item:
    """One `- item` and the lines beneath it.

    `lines` is the item exactly as written, so an item nobody edited can be put
    back byte for byte. `text` and `fields` are the same item as the compiler
    reads it, which is what a caller decides against.
    """

    def __init__(self, lines, text, fields):
        self.lines = list(lines)
        self.text = text
        self.fields = dict(fields)

    @property
    def id(self):
        """The id written in the item, or None where it is still implicit."""
        return self.fields.get("id")

    def __repr__(self):                                  # pragma: no cover - debugging
        return f"Item({self.text!r}, {self.fields!r})"


class Block:
    """One named block: where it sits, and the items in it.

    `preamble` is whatever sits between the heading and the first item - a blank
    line, or a sentence introducing the list. `postamble` is the blank lines
    trailing the block before whatever ends it. Both are carried rather than
    regenerated, for the same reason concept.Concept carries `gap`: a byte nobody
    asked about is a byte this layer must not move.
    """

    def __init__(self, heading, start, end, preamble, items, postamble):
        self.heading = heading          # index of the heading line
        self.start = start              # first content line, after the heading
        self.end = end                  # one past the last content line
        self.preamble = list(preamble)
        self.items = list(items)
        self.postamble = list(postamble)

    def content(self, items=None):
        """The block's content lines, with `items` in place of the ones read.

        Mechanical on purpose: preamble, items, postamble, and not one byte
        invented. `parse(body, name, keys)` then `replace(body, block, block.items)`
        must return the body unchanged, and a fixup here - a blank line this
        thought the source was missing - is exactly what would break that.
        """
        items = self.items if items is None else items
        out = list(self.preamble)
        for item in items:
            out.extend(item.lines)
        out.extend(self.postamble)
        return out

    def claims(self):
        """The items the compile actually reads.

        `items` is every entry the block holds, because a writer has to put back
        the lines it did not touch. `claims` is the subset okf_compile.blocks()
        yields, and the two differ in exactly one case: an entry with fields and
        no sentence. blocks() ends with

            if text:
                out.append((" ".join(text), fields))

        so a `- ` with only `status: confirmed` under it is dropped there and
        **consumes no position**. Anything numbering items - the derived ids, which
        are positional - has to count this way or its numbers are off by however
        many text-less entries sit above.

        Found by claims.py, which matched the compiler locally while
        common.item_ids did not. The divergence is now named in one place instead
        of being rediscovered in each caller.
        """
        return [item for item in self.items if item.text]

    def inserted(self, new, at=None):
        """`items` with `new` placed at `at` (1-based), or appended.

        The blank line a first item needs is added here rather than in content(),
        because it is a consequence of *adding* rather than a fact about the
        block: a block whose preamble is a sentence with a list already under it
        is written that way by its author, and content() must hand it back as it
        found it.
        """
        if not self.items and self.preamble and self.preamble[-1].strip():
            self.preamble = self.preamble + [""]
        items = list(self.items)
        if at is None:
            items.append(new)
        else:
            items.insert(max(0, min(at - 1, len(items))), new)
        return items


def lines_of(body):
    """The body as lines, without inventing or dropping a trailing newline."""
    return body.split("\n")


def find(body, name):
    """`name`'s block, or None. Nothing is parsed into items yet.

    (heading index, first content line, one past the last) - the span the
    compiler reads, so a caller can splice inside exactly it.
    """
    pattern = heading_pattern(name)
    lines = lines_of(body)
    for index, line in enumerate(lines):
        if not pattern.match(line):
            continue
        end = len(lines)
        for below in range(index + 1, len(lines)):
            if TERMINATOR.match(lines[below]):
                end = below
                break
        return index, index + 1, end
    return None


def field_pattern(keys):
    """blocks()' field regex for one set of keys.

    `keys` is closed per block kind and comes from the compiler - the same tuple
    it passes to blocks() - so a key this does not know is text, both here and
    there. That is why a misspelt `statuss:` becomes part of a bullet's sentence
    rather than a field nobody set: the compiler reads it that way, and a writer
    that hid it would be hiding what will actually be rendered.
    """
    return re.compile(r"^(%s)\s*:\s*(.+)$" % "|".join(re.escape(k) for k in keys))


def parse(body, name, keys):
    """`name`'s block with its items, or None where there is no such heading.

    Item boundaries are the compiler's: any line that is optional whitespace, a
    `-`, then whitespace. That includes a nested list item, which blocks() also
    treats as the start of a new entry - so a bullet with a sub-list is two
    entries to both readers, and this module does not pretend otherwise.
    """
    span = find(body, name)
    if span is None:
        return None
    heading, start, end = span
    lines = lines_of(body)
    content = lines[start:end]

    starts = [n for n, line in enumerate(content) if ITEM.match(line)]
    if not starts:
        return Block(heading, start, end, _without_trailing_blanks(content), [],
                     _trailing_blanks(content))

    preamble = content[:starts[0]]
    items = []
    field = field_pattern(keys)
    bounds = starts + [len(content)]
    for n in range(len(starts)):
        raw = content[bounds[n]:bounds[n + 1]]
        if n == len(starts) - 1:
            postamble = _trailing_blanks(raw)
            raw = _without_trailing_blanks(raw)
        items.append(_item(raw, field))
    return Block(heading, start, end, preamble, items, postamble)


def _item(raw, field):
    """One item's raw lines, read the way blocks() reads them."""
    text, fields = [], {}
    for line in raw:
        stripped = line.strip()
        if not stripped:
            continue
        if ITEM.match(line):
            # blocks() splits on the bullet marker, so the marker itself is not
            # part of the text. Split rather than lstrip: `- - a` is one item
            # whose text is `- a`, which is what the compiler's split yields.
            stripped = ITEM.sub("", line, count=1).strip()
            if not stripped:
                continue
        match = field.match(stripped)
        if match:
            fields[match.group(1)] = match.group(2).strip()
        else:
            text.append(stripped)
    return Item(raw, " ".join(text), fields)


def _trailing_blanks(lines):
    at = len(lines)
    while at and not lines[at - 1].strip():
        at -= 1
    return list(lines[at:])


def _without_trailing_blanks(lines):
    at = len(lines)
    while at and not lines[at - 1].strip():
        at -= 1
    return list(lines[:at])


def item(text, fields, order):
    """One item, in canonical form: `- text` and its fields, two spaces in.

    Only an item whose content changed is written this way. `order` is the field
    order for this block kind, so two commands writing the same kind of item
    produce the same file rather than two files that differ by a line's position.
    """
    text = bookkeeping._one_line(text)
    if not text:
        raise concept.Unsplicable(
            "an item needs text\n"
            "fix:  the sentence is the claim - a field-only item compiles to an "
            "empty achievement, which renders as a blank line on a resume")
    lines = [f"- {text}"]
    written = set()
    for key in order:
        value = fields.get(key)
        if value is None or value == "":
            continue
        written.add(key)
        lines.append(f"{INDENT}{key}: {bookkeeping._one_line(value)}")
    for key in sorted(set(fields) - written):
        # Unreachable through the commands, whose flags are the closed set
        # `order` lists. Kept so that a field a caller passes is never silently
        # dropped: a field this layer discarded would be a value a person typed
        # and no file holds.
        value = fields[key]
        if value is None or value == "":
            continue
        lines.append(f"{INDENT}{key}: {bookkeeping._one_line(value)}")
    return Item(lines, text, {k: v for k, v in fields.items() if v not in (None, "")})


def replace(body, block, items):
    """The whole body, with `block` rebuilt from `items`."""
    lines = lines_of(body)
    return "\n".join(lines[:block.start] + block.content(items) + lines[block.end:])


def add_block(body, name, lines):
    """The whole body, with a new `# name` block holding `lines`, appended.

    Appended rather than placed: nothing here knows where in somebody's concept a
    new block belongs, and a heading inserted between two sections of their prose
    is a change they did not ask for.
    """
    text = body if body.endswith("\n") or not body else body + "\n"
    if text and not text.endswith("\n\n"):
        text += "\n"
    return text + f"# {name}\n\n" + "\n".join(lines) + "\n"


# --- sections -------------------------------------------------------------------
#
# A section is a heading and the prose under it. Sections are fence-aware where
# blocks are not, and the difference is deliberate: a block's shape is the
# compiler's and must be read its way, while a section is prose this module alone
# addresses - and prose is exactly where a fenced example lives. bookkeeping._scan
# is the toggle, which is validate_bundle.py's, which is pipeline_model.py's.


def headings(body):
    """Every heading outside a fence: (line index, level, title)."""
    out = []
    for index, line, fenced in bookkeeping._scan(lines_of(body)):
        if fenced:
            continue
        match = ANY_HEADING.match(line)
        if match and match.group(2):
            out.append((index, len(match.group(1)), match.group(2)))
    return out


def section(body, title):
    """(heading index, first content line, one past the last), or None.

    A heading at the same level or shallower ends the section; a deeper one is the
    author's own structure inside it. The same rule vocabulary_with() applies to a
    theme, and bookkeeping.log_entry to a day.
    """
    wanted = title.strip().lower()
    found = None
    for index, level, name in headings(body):
        if name.strip().lower() == wanted:
            found = (index, level)
            break
    if found is None:
        return None
    index, level = found
    boundary = re.compile(r"^#{1,%d}\s" % level)
    end = len(lines_of(body))
    for below, line, fenced in bookkeeping._scan(lines_of(body)):
        if below <= index or fenced:
            continue
        if boundary.match(line):
            end = below
            break
    return index, index + 1, end


def set_section(body, title, text):
    """The body with `title`'s prose replaced. Refuses when no such heading.

    Refused rather than created, and the resolution is the caller's `--new-section`
    - the shape `--capability` and `--new-capability` already set. A typo that
    silently created a second section would leave the real one holding the old
    prose and the resume rendering from it.
    """
    span = section(body, title)
    if span is None:
        known = ", ".join(repr(name) for _, _, name in headings(body)) or "none at all"
        raise concept.Unsplicable(
            f"no section named {title!r} - this concept has {known}\n"
            f"fix:  name a heading that is there, or pass --new-section to write a "
            f"new one. A section created by a typo leaves the real one holding the "
            f"prose a resume then renders")
    heading, start, end = span
    lines = lines_of(body)
    trailing = _trailing_blanks(lines[start:end])
    return "\n".join(lines[:start] + [""] + prose_lines(text)
                     + (trailing or [""]) + lines[end:])


def add_section(body, title, text, level=1):
    """The whole body with a new section appended. Refuses a heading already there."""
    if section(body, title) is not None:
        raise concept.Unsplicable(
            f"a section named {title!r} is already there\n"
            f"fix:  drop --new-section to replace what it says")
    body = body if body.endswith("\n") or not body else body + "\n"
    if body and not body.endswith("\n\n"):
        body += "\n"
    return body + "#" * level + f" {title}\n\n" + "\n".join(prose_lines(text)) + "\n"


def prose_lines(text):
    """Prose, as the lines it will occupy.

    Unlike a field value, prose keeps its own shape: a paragraph break is
    meaning, and collapsing one would rewrite what the person wrote. Only the
    blank lines at either end go, because the section's own spacing is this
    module's to place.
    """
    return str(text).replace("\r\n", "\n").strip("\n").split("\n")


# --- the ids the compiler derives -----------------------------------------------
#
# Written down here so that a mutation can materialise them - see claims.py. The
# derivation is okf_compile's and must stay identical to it: an id this layer
# wrote down that differed by one character from the one the compile derives
# would repoint every view that named it. It was a copy, because importing
# okf_compile.py - a 1,000-line CLI - was the wrong price for one regex on the
# hot path of every write. markup.py imports nothing at all, so the price is gone
# and there is no copy left to drift.


# One definition now, in markup.py - which imports nothing, so the write layer pays
# no more for it than it did for the copy. `IdsMatchTheCompiler` in
# tests/test_authoring_body.py asserted the two agreed over a corpus of stems; they
# are the same object, so it now asserts identity.
compile_slug = markup.id_slug


def derived_bullet_id(stem, n):
    """The id okf_compile.bullets() gives the nth bullet of projects/<stem>.md."""
    return f"ach_{compile_slug(f'projects/{stem}.md')}_{n}"


def derived_credential_id(stem, n):
    """The id build_credentials() gives the nth entry of a `# Held` block."""
    return f"cred_{compile_slug(stem)}_{n}"


def derived_skill_id(name):
    """The id okf_compile.build_skills() gives a skill named `name`.

    Content-derived rather than positional, so inserting a skill above another
    does not move anybody's id. It moves when the *name* changes, which is why a
    write materialises it anyway: renaming a competency should not silently
    repoint a view that selected it.
    """
    return f"skill_{compile_slug(name)}"


# Words that make an id say nothing. An id is read by a person choosing evidence
# for a posting, and `ach_and_the_of` is worse than a positional one.
NOISE = frozenset("""
a an and are as at be but by for from had has have in into is it its of on or that
the to was were will with we our i my""".split())


def mint_id(prefix, text, taken, words=3):
    """A content-derived id from an item's own text, unique against `taken`.

    Never positional: the whole point of materialising ids is that a new item
    must not be minted with a number that means "third from the top", because the
    next insertion moves it.
    """
    parts = [word for word in compile_slug(text).split("_")
             if word and word not in NOISE]
    if not parts:
        # Every word was noise, or the text carried no letters or digits at all -
        # an item of pure punctuation. There is nothing to derive from, so fall
        # back to the prefix and let the uniqueness loop below number it.
        parts = ["item"]
    base = f"{prefix}_" + "_".join(parts[:words])
    if base not in taken:
        return base
    # Lengthen before numbering: a fourth word from the person's own sentence
    # says more than a `_2`, and the number is only reached when the text has no
    # more words to give.
    for extra in range(words + 1, len(parts) + 1):
        candidate = f"{prefix}_" + "_".join(parts[:extra])
        if candidate not in taken:
            return candidate
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"
