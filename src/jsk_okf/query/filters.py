"""What a filter flag means, for every command that takes one.

`okf search --capability X --strength 4+` and `okf list projects --strength 4+` have to
agree about what `4+` selects, and about whether `--capability` compares exactly or
loosely. Two commands answering the same flag differently is the kind of thing nobody
notices until a project is missing from a ranking.

The one rule worth stating: **the matching axes compare as exact strings.**
`capabilities` is the primary matching axis, `bundle-spec.md` says it compares as exact
strings and that a synonym silently breaks matching, and `validate_bundle.py` errors on
a term absent from the vocabulary. A filter here that quietly matched a substring would
hand back a project that the *scorer* will not match, which is worse than handing back
nothing: it reads as evidence the ranking is about to use.

Free text is the opposite case and is folded, because a person typing `latency` into a
search is not asserting a case.
"""

import re

# `--strength 4+`, `--recency 2023+`, `--strength 3-`, `--strength 5`. A bare number is
# equality, because "strength 5" is how somebody asks for the flagship projects.
BOUND = re.compile(r"^(\d+)([+-])?$")


class Bad(Exception):
    """A flag value this layer will not guess at. Carries the sentence to print."""


def bound(value, flag):
    """`"4+"` -> a predicate over a number. Refuses anything else by name."""
    match = BOUND.match(str(value).strip())
    if not match:
        raise Bad(f"{flag} takes a number, optionally with + or -, got {value!r}\n"
                  f"fix:  {flag} 4   {flag} 4+   {flag} 4-")
    number, direction = int(match.group(1)), match.group(2)

    def test(found):
        if found is None:
            return False
        try:
            found = int(str(found).strip())
        except (TypeError, ValueError):
            return False
        if direction == "+":
            return found >= number
        if direction == "-":
            return found <= number
        return found == number

    return test


def listed(meta, key):
    """A frontmatter key as a list of strings, however it was written.

    `capabilities: [a, b]` is a list, `capabilities: a` is a string somebody wrote in a
    hurry, and both have to be searchable. `validate_bundle.py` reports the second as a
    problem; a query is not the place to also refuse it.
    """
    value = (meta or {}).get(key)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def has_all(meta, key, wanted):
    """Whether every named term is on this concept, compared exactly.

    Every term, not any: `--capability a --capability b` reads as "carries both", which
    is what a person narrowing a search means. `--capability a` alone is unaffected.
    """
    if not wanted:
        return True
    found = set(listed(meta, key))
    return all(term in found for term in wanted)


def text_matcher(needle, regex=False, case_sensitive=False):
    """A predicate over a line, or a `Bad` naming what is wrong with the pattern.

    Returns None for no pattern at all, which is how a filters-only query - the tailor
    call, `--capability X --strength 4+` with no text - says "every concept that passed
    the metadata filters".
    """
    if not needle:
        return None
    if regex:
        try:
            compiled = re.compile(needle, 0 if case_sensitive else re.I)
        except re.error as exc:
            raise Bad(f"--regex given a pattern Python cannot compile: {exc}\n"
                      f"fix:  drop --regex to search for {needle!r} literally") from exc
        return compiled.search
    if case_sensitive:
        return lambda line: needle in line
    folded = needle.lower()
    return lambda line: folded in line.lower()


def prefilter(needle, regex=False, case_sensitive=False):
    """A test over a file's raw text: could it hold a match? Or None for "cannot say".

    Handed to `walk(must_contain=...)`, which skips the YAML parse for any file this
    rejects. That is worth having precisely: the parse is five sixths of a walk, and on
    a 235-file bundle skipping it takes the walk from 645ms to 122ms.

    **The soundness condition is the whole of this function**, and it used to be stated
    in a docstring that the signature could not enforce. `literals(needle, regex)` took
    no `case_sensitive`, so a caller who trusted the shape of the call got the exact-case
    pre-filter applied to a folded search - and `"Latency" in raw` is false for a file
    whose only spelling is `latency`. A search that quietly skips files is the one
    failure a search must not have, and the second caller was about to make the same
    mistake, so the condition now lives where it cannot be bypassed.

    A folded search is still pre-filtered, just folded on both sides. Lowercasing the
    raw text costs a fraction of parsing it, so the case that gave up the optimisation
    entirely - which is the *default* case, and therefore almost every search anybody
    runs - keeps most of it.

    A regex gets no pre-filter. There is no literal a pattern is guaranteed to contain,
    and inventing one from its non-metacharacter runs is how a search comes to miss a
    file for a reason nobody can see.
    """
    if not needle or regex:
        return None
    if case_sensitive:
        return lambda raw: needle in raw
    folded = needle.lower()
    return lambda raw: folded in raw.lower()


class Metadata:
    """The selection-key filters, resolved once and applied per concept.

    Built from the parsed arguments so that `search` and `list` cannot drift: each
    hands over the same namespace and gets the same predicate.
    """

    __slots__ = ("capabilities", "technologies", "domains", "seniority", "status",
                 "strength", "recency", "types")

    def __init__(self, args):
        self.capabilities = tuple(getattr(args, "capability", None) or ())
        self.technologies = tuple(getattr(args, "technology", None) or ())
        self.domains = tuple(getattr(args, "domain", None) or ())
        self.seniority = getattr(args, "seniority", None)
        self.status = getattr(args, "status", None)
        self.types = tuple(getattr(args, "type", None) or ())
        self.strength = (bound(args.strength, "--strength")
                         if getattr(args, "strength", None) else None)
        self.recency = (bound(args.recency, "--recency")
                        if getattr(args, "recency", None) else None)

    def __bool__(self):
        return any((self.capabilities, self.technologies, self.domains, self.seniority,
                    self.status, self.types, self.strength, self.recency))

    def matches(self, concept):
        meta = concept.meta or {}
        if self.types and concept.type not in self.types:
            return False
        if self.status and concept.status != self.status:
            return False
        if not has_all(meta, "capabilities", self.capabilities):
            return False
        if not has_all(meta, "technologies", self.technologies):
            return False
        if not has_all(meta, "domains", self.domains):
            return False
        if self.seniority and str(meta.get("seniority") or "") != self.seniority:
            return False
        if self.strength and not self.strength(meta.get("strength")):
            return False
        if self.recency and not self.recency(meta.get("recency")):
            return False
        return True
