"""How a bundle's Markdown is read - the primitives, in one place.

A bundle is Markdown with YAML frontmatter, and five things have to be read out of it
over and over: the frontmatter block, whether a line is inside a fence, a link, a list
item, and a backticked term. Every layer needs them, so every layer had grown its own.

Counted before this module existed: the frontmatter split in 4 modules, the fence
toggle in 3, the link pattern in 4 and the term pattern in 5. `authoring/common.py`'s
own docstring already named the problem - *"a fifth idiom for one rule is how four of
them come to disagree"* - and then borrowed a fourth idiom rather than having somewhere
to put a first one. This is that place.

The copies had already drifted, which is the argument made concrete:

  - `okf_compile.read_frontmatter` handles CRLF and the other three do not. It is
    reachable by nothing: every caller in the package opens with `encoding="utf-8"` and
    the default `newline=None`, so universal-newline translation has already turned any
    `\\r\\n` into `\\n` before the text arrives. The branch is kept here because it costs
    two lines and is correct for a caller that reads with `newline=""`, but it is no
    longer four different answers to one question.
  - `okf_compile.read_frontmatter`'s docstring claimed it was *"the parser pipeline.py
    uses, so a concept reads the same way everywhere"*. `pipeline.py` had its own copy
    and had done all along. The sentence is true now.

**Standard library only, and it imports nothing else in this package** - not even
pyyaml. That is load bearing: `authoring/` reaches for it on the hot path of every
write, a write is meant to cost about the interpreter floor, and pyyaml is precisely
the dependency that layer defers. So the frontmatter split comes in two halves:
`split_frontmatter` needs no parser, and `load_frontmatter` takes one from the caller.

What is deliberately *not* here:

  - `authoring.common.slug` and `id_slug` below are two different rules and must stay
    two. `common.slug` makes a file stem - NFKD-folded, hyphenated - and `id_slug`
    makes an id fragment, underscored and unfolded. They were nearly merged once.
  - `migrate_bundle.MARKDOWN_LINK` matches `[]()` with an empty label where `LINK`
    requires one. A migration reads files written by older versions of everything, so
    it is right to be laxer than the gate.
"""
import re

__all__ = ["FENCE", "LINK", "LIST_ITEM", "TERM", "HEADING", "scan", "unfenced",
           "terms", "split_frontmatter", "load_frontmatter", "read_frontmatter",
           "id_slug"]

FENCE = "```"

# A markdown link: `[label](target)`. The label is required - `validate_bundle` treats
# a link as a reference worth resolving, and `[](x)` references nothing.
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# A list item, at any indent, under either bullet character.
LIST_ITEM = re.compile(r"^\s*[-*]\s+")

# A term inside backticks, as every vocabulary file writes one.
TERM = re.compile(r"`([a-z0-9-]+)`")

HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")


def scan(lines):
    """Yield `(index, line, inside_a_fence)` for every line.

    The fence *opener* reports as inside, so a caller splicing into a file cannot
    write between the opener and its content. Readers that only want content call
    `unfenced()` instead, which skips the opener for the same reason.
    """
    fenced = False
    for index, line in enumerate(lines):
        opener = line.lstrip().startswith(FENCE)
        yield index, line, fenced or opener
        if opener:
            fenced = not fenced


def unfenced(lines):
    """Every line outside a fenced block, openers excluded.

    `lines` may be a list or an open file - the three call sites this replaces were
    two of each.
    """
    fenced = False
    for line in lines:
        if line.lstrip().startswith(FENCE):
            fenced = not fenced
            continue
        if not fenced:
            yield line


def terms(text_or_lines):
    """Every backticked term in a list item outside a fence.

    The rule the capability and pipeline vocabularies are both read by. `init_bundle`
    scaffolds those files with their example values *inside* a fence, so a fresh bundle
    yields nothing - and both gates then leave the vocabulary unchecked, which is the
    behaviour being matched rather than a bug being preserved. Rejecting every value on
    a fresh bundle and accepting every value on a populated one are the same defect
    wearing opposite signs.
    """
    lines = (text_or_lines.split("\n") if isinstance(text_or_lines, str)
             else text_or_lines)
    found = set()
    for line in unfenced(lines):
        if LIST_ITEM.match(line):
            found.update(TERM.findall(line))
    return found


def split_frontmatter(text):
    """`(frontmatter_text, body)` or `(None, text)`. No YAML parser involved.

    The CRLF arm is unreachable through every caller in this package - they all open
    with universal newlines - and is kept only because it is two lines and correct.
    """
    for opener, closer in (("---\n", "\n---\n"), ("---\r\n", "\r\n---\r\n")):
        if not text.startswith(opener):
            continue
        end = text.find(closer, 3)
        if end == -1:
            continue
        return text[len(opener):end], text[end + len(closer):]
    return None, text


def load_frontmatter(text, yaml):
    """`(mapping, body)`, parsed with the `yaml` module the caller hands in - strict.

    A non-mapping block - a list, a bare string - comes back as `None`, which every
    caller already treats as "no usable frontmatter". **A parse error propagates.**
    That is for `validate_bundle`, whose whole job is to report the error against the
    file that has it; swallowing one there would turn a broken concept into a silent
    omission from the count it prints.
    """
    raw, body = split_frontmatter(text)
    if raw is None:
        return None, text
    meta = yaml.safe_load(raw)
    return (meta if isinstance(meta, dict) else None), body


def read_frontmatter(text, yaml):
    """The same, but a parse error yields `(None, body)` instead of raising.

    For the readers rather than the gate. `okf_compile` and `pipeline` both walk every
    file in a bundle, and one unparseable concept must not take the run down: the
    bundle gate is the thing that reports it, and a compile that died on it would hide
    every other finding behind a traceback.
    """
    raw, body = split_frontmatter(text)
    if raw is None:
        return None, text
    try:
        meta = yaml.safe_load(raw)
    except Exception:                       # noqa: BLE001 - see the docstring
        return None, body
    return (meta if isinstance(meta, dict) else None), body


# `id_slug` is okf_compile's rule for turning anything into an id fragment, and
# `authoring/body.py` carried a copy of it under the name `compile_slug`. The copy was
# deliberate and its comment said so: an id the write layer records that differs by one
# character from the one the compile derives would repoint every view naming it, and
# importing a 1,000-line CLI to get one regex was the wrong price for a write that must
# cost about the interpreter floor. Both halves of that argument are satisfied by
# putting it in a module with no imports of its own.
_ID_SEPARATORS = re.compile(r"[^a-z0-9]+")


def id_slug(text):
    """An id fragment: lowercased, non-alphanumerics collapsed to underscores.

    Not `authoring.common.slug`, which makes a *file stem* - hyphens, and NFKD folding
    so that "Café" keeps its final letter. Two rules, two names, and merging them would
    rename either every file or every id.
    """
    return _ID_SEPARATORS.sub("_", str(text).lower()).strip("_")
