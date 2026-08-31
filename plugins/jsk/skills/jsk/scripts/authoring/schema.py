"""What each concept type takes, and what each value must satisfy.

This is the only machine-readable statement of the format. `references/bundle-spec.md`
is its prose counterpart and the two are meant to be read together; a rule in one and
not the other is a defect in whichever is missing it.

This module judges and does not format. It returns problems as sentences a person can
act on - never exit codes, never output. What to do about a problem is the caller's.
"""

import datetime
import difflib
import re

# The closed vocabularies. Each compares as an exact string, which is the whole reason
# they are closed: a synonym does not fail, it silently stops matching.
VOCABULARIES = {
    "seniority": ("architecture-ownership", "product-ownership", "platform-design",
                  "team-leadership", "technical-ownership", "hands-on-senior",
                  "hands-on", "junior"),
    "status": ("confirmed", "inferred", "needs-verification"),
    "state": ("ended", "ongoing", "unknown"),
    "change": ("hire", "promotion", "lateral", "title-change"),
    "relationship": ("employer", "prospect", "both"),
    # An Organisation's `employment:` becomes the engagement's `kind` in the compiled
    # record. urs-spec.md states the closed set; nothing enforced it, so a typo
    # reached the record as a kind no renderer knows.
    "engagement": ("employment", "contract", "freelance", "internship", "volunteer",
                   "break", "education-fulltime"),
}

# The same two vocabularies as sets, for validate_bundle.py, which membership-tests
# them. Exposed rather than reshaped at the call site so `assertIs` can prove the two
# modules hold one object: three copies of these words existed - here, in
# validate_bundle.py, and in bundle-spec.md's prose - and a vocabulary that has
# drifted does not fail loudly, it silently stops matching.
STATUS_VALUES = frozenset(VOCABULARIES["status"])
SENIORITY_VALUES = frozenset(VOCABULARIES["seniority"])

# Spellings this codebase does not use, and what it uses instead. okf_compile.py reads
# `organization` as well as `organisation`, but that is a tolerance for bundles written
# before the spelling settled, not a licence for new ones - so this layer names the
# house spelling rather than implying the writer made a mistake.
SPELLINGS = {"organization": "organisation"}

# A file stem, which is what the relational keys hold - `organisation:` names the
# Organisation file, not its display name. Deliberately not lowercase-only: the
# compiler matches these against filenames it found on disk, so rejecting an
# uppercase stem here would refuse a concept that compiles perfectly well. `_` is in
# the set because okf_compile.ident() derives ids as `prj_aged_care`, and a bundle
# that published one keeps it.
SLUG = re.compile(r"^[A-Za-z0-9][\w./-]*\Z")

# The same three precisions okf_compile.date() accepts - 2019, 2019-04, 2019-04-01 -
# because precision is read from what was written and a schema that admitted a fourth
# shape would pass a concept the compile then refuses.
DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?\Z")


class Key:
    """One frontmatter key: what it is called, what it holds, whether it is required."""

    def __init__(self, name, kind, required=False):
        self.name = name
        self.kind = kind
        self.required = required


# Keys every concept may carry. `type` is not here: it is the argument, not a key.
#
# `id` is not here either, because it is per-type: okf_compile.ident() derives it with
# a type-specific prefix and the key exists so a bundle that already published one can
# keep it.
COMMON = (
    Key("title", "text"),
    Key("description", "text"),
    # `resource` is one of the five bundle-spec.md calls recommended on every concept.
    # Read by no script; listed so writing one is not a refusal.
    Key("resource", "text"),
    Key("tags", "slugs"),
    Key("timestamp", "moment"),
    Key("status", "vocab:status"),
    # okf_compile.CONCEPT_KEYS - "bookkeeping every OKF file may carry", stripped from
    # a view rather than admitted into the URS contract. mode-ship.md instructs
    # `frozen:` by name, so refusing it here would refuse an instruction the skill gives.
    Key("frozen", "flag"),
    Key("frozen_date", "date"),
    Key("superseded_by", "text"),
)

TYPES = {
    "Project": COMMON + (
        Key("title", "text", required=True),
        Key("id", "slug"),
        Key("role", "slug", required=True),
        # The five selection keys. Required because validate_bundle.py makes each a
        # hard error on every Project - "Project missing selection key" - so a Project
        # this layer called clean without them is one the bundle gate then rejects,
        # and the person finds out at ship time instead of at write time. The compiler
        # tolerates their absence; the gate does not, and the gate is what runs.
        Key("strength", "rank", required=True),
        Key("recency", "year", required=True),
        Key("seniority", "vocab:seniority", required=True),
        Key("domains", "slugs", required=True),
        Key("capabilities", "slugs", required=True),
        Key("technologies", "slugs"),
        # Read by no script, and correct to list: it is authored data a model reads
        # when writing a summary. Not dead, so do not delete it as dead.
        Key("headline_metric", "text"),
        Key("url", "text"),
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    "Role": COMMON + (
        Key("title", "text", required=True),
        Key("id", "slug"),
        Key("functional_title", "text"),
        Key("organisation", "slug", required=True),
        Key("start", "date"),
        Key("end", "date"),
        # Optional, and deliberately: okf_compile.period() derives it -
        # `state or ("ongoing" if not end else "ended")` - so a Role carrying only
        # start and end is valid, and requiring the key rejected it. Do not re-tighten.
        Key("state", "vocab:state"),
        Key("seniority", "vocab:seniority"),
        Key("change", "vocab:change"),
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    "Organisation": COMMON + (
        Key("title", "text", required=True),
        Key("id", "slug"),
        # Required though no script reads it. bundle-spec.md's Organisations section
        # presents it as the type's defining key, and an organisation that cannot say
        # whether they were an employer or a prospect is a record nobody can use.
        Key("relationship", "vocab:relationship", required=True),
        Key("industry", "text"),
        Key("sector", "text"),
        Key("size", "text"),
        Key("url", "text"),
        # Both read off the organisation by okf_compile.build_engagements.
        Key("employment", "vocab:engagement"),
        Key("location", "text"),
    ),
}


def _assert_no_conflicting_duplicates():
    """A type may repeat a key only to sharpen it, never to redefine what it holds.

    Repeating a name is how a type sharpens a COMMON key - `title` is optional in
    COMMON and required on all three types, and _kinds() lets the later entry win. The
    same mechanism silently disables a kind if the later entry names a different one,
    and no test could see it: every value of that key would simply be checked against
    the wrong rule and most would pass. Raised at import so the tuple cannot ship wrong.
    """
    for type_name, keys in TYPES.items():
        seen = {}
        for key in keys:
            prior = seen.get(key.name)
            if prior is not None and prior.kind != key.kind:
                raise ValueError(
                    f"{type_name} declares `{key.name}` as both {prior.kind!r} and "
                    f"{key.kind!r} - a repeat may sharpen `required`, never the kind")
            seen[key.name] = key


_assert_no_conflicting_duplicates()


def _kinds(type_name):
    """This type's keys by name, or None if the type is not one of ours.

    Built in order so a later entry replaces an earlier one of the same name, which
    is how a type sharpens a COMMON key rather than restating the whole set: `title`
    is listed optional in COMMON and again required on all three types, and only the
    second wins. Not obvious from reading TYPES, which is why it is written here.
    """
    keys = TYPES.get(type_name)
    if keys is None:
        return None
    return {key.name: key for key in keys}


def _nearest(name, candidates):
    """The key `name` was most likely meant to be, or None if nothing is close.

    difflib on its own was not enough. `startDate` scores exactly 0.714 against both
    `start` and `state`, and get_close_matches breaks a tie with nlargest over
    (ratio, candidate) - so the alphabetically later `state` won and the suggestion
    named the wrong key, which is worse than no suggestion. The tie is broken on the
    shared prefix instead: a typo that suffixes - camelCase, a plural, a stray word -
    keeps the prefix, and `startDate` shares five characters with `start` against
    three with `state`. Declaration order settles anything still level, so the
    suggestion never depends on dict iteration luck.
    """
    candidates = list(candidates)
    if not candidates:
        return None
    # A real key with a type word appended - `end_date`, `startDate`, `recency_year` -
    # is a specific and common mistake, and difflib is the wrong instrument for it.
    # Adding `frozen_date` to COMMON made `end_date` score 0.737 against it and only
    # 0.545 against `end`, so the suggestion named the key that merely shared the
    # suffix. Decomposition is exact where a ratio is a guess, so it goes first.
    for suffix in ("_date", "_year", "date", "year"):
        if len(name) > len(suffix) and name.lower().endswith(suffix):
            stem = name[:-len(suffix)].rstrip("_")
            if stem in candidates:
                return stem
    # 0.7 catches every real typo measured - startDate/start 0.714, titel/title 0.800,
    # seniorty/seniority 0.941, capability/capabilities 0.818 - and deliberately
    # catches no abbreviation. Do not lower it. ratio()
    # divides by combined length, so `org`/`organisation` scores 0.400 and `tech`
    # /`technologies` 0.500: no usable cutoff reaches them, and 0.5 makes
    # `tech` suggest `strength` (also 0.500), which is a confidently wrong suggestion
    # and worse than silence. Abbreviations want a hand-written alias table, not a
    # looser cutoff.
    close = difflib.get_close_matches(name, candidates, n=len(candidates), cutoff=0.7)
    if not close:
        return None
    order = {candidate: i for i, candidate in enumerate(candidates)}

    def rank(candidate):
        shared = 0
        for mine, theirs in zip(name.lower(), candidate.lower()):
            if mine != theirs:
                break
            shared += 1
        ratio = difflib.SequenceMatcher(None, name, candidate).ratio()
        return (-ratio, -shared, order[candidate])

    return sorted(close, key=rank)[0]


def _slug_problem(name, value):
    if not isinstance(value, str) or not SLUG.match(value):
        return (f"`{name}` must be a file stem - letters, digits, `-`, `.`, `_` or "
                f"`/` - not {value!r}\n"
                f"fix:  name the concept's filename without its .md, not its title")
    return None


def _value_problem(key, value):
    """What is wrong with this value for this key, as a sentence. None means clean."""
    kind = key.kind
    name = key.name

    if kind == "text":
        if not isinstance(value, str):
            return (f"`{name}` must be text, not a {type(value).__name__}\n"
                    f"fix:  quote it, or pass it as a string")
        if not value.strip():
            return (f"`{name}` is empty\n"
                    f"fix:  give it a value, or leave the key out entirely - an "
                    f"empty key reads as an answered question and is not one")
        return None

    if kind == "slug":
        return _slug_problem(name, value)

    if kind == "moment":
        # Not `text`. `timestamp: 2026-01-01T00:00:00Z` is the form bundle-spec.md
        # prints, and PyYAML resolves it to a datetime - so check() on any concept
        # read back off disk reported a false problem on a correctly written file.
        # The emitter quotes a timestamp, so a freshly written concept carries a
        # string; every hand-written and pre-existing one carries a datetime. Both
        # are valid on disk, so both are valid here.
        if isinstance(value, (datetime.date, datetime.datetime)):
            return None
        if not isinstance(value, str) or not value.strip():
            return (f"`{name}` must be a timestamp, not {value!r}\n"
                    f"fix:  write 2026-01-01T00:00:00Z")
        return None

    if kind == "flag":
        if not isinstance(value, bool):
            return (f"`{name}` must be true or false, not {value!r}\n"
                    f"fix:  write `{name}: true` - a quoted \"true\" reads back as a "
                    f"string and every test of it is then true")
        return None

    if kind == "slugs":
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            return (f"`{name}` must be a list, not a {type(value).__name__}\n"
                    f"fix:  write it as [one, two] - a bare word here compiles to a "
                    f"list of its letters in anything that iterates it")
        # An empty list satisfies this schema, and satisfies validate_bundle.py too -
        # it tests `isinstance(cv, list)` and nothing more. Consistent with the gate
        # rather than divergent from it, which is the property that matters here.
        # Whether an empty `capabilities` *should* pass is a bundle-spec question, and
        # tightening it here alone would put this layer ahead of the gate.
        for item in value:
            problem = _slug_problem(name, item)
            if problem:
                return problem
        return None

    if kind == "rank":
        # `isinstance(True, int)` is True in Python, and `strength: yes` is a real
        # thing to type: without the bool guard it arrives as 1 and passes.
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            return (f"`{name}` must be a whole number from 1 to 5, not {value!r}\n"
                    f"fix:  5 is flagship evidence and 1 is filler - see "
                    f"bundle-spec.md, 'Selection keys'")
        return None

    if kind == "year":
        # A string of four digits is admitted alongside the int because
        # okf_compile.date() reads `str(value)`, so `recency: \"2026\"` compiles.
        # Refusing it here would reject a concept the compiler is happy with, which
        # is the one failure mode a schema must not have.
        if isinstance(value, bool) or not (
                (isinstance(value, int) and 1000 <= value <= 9999)
                or (isinstance(value, str) and re.match(r"^\d{4}\Z", value))):
            return (f"`{name}` must be a four-digit year, not {value!r}\n"
                    f"fix:  write the year the work was last touched, as 2026")
        return None

    if kind == "date":
        # Stringified before matching, for the same reason okf_compile.date() does
        # it: YAML reads `start: 2019` back as an int and `start: 2019-04-01` as a
        # datetime.date, so the value that reaches here is often not the text that
        # was written.
        if isinstance(value, bool) or not DATE.match(str(value).strip()):
            return (f"`{name}` must be a date, not {value!r}\n"
                    f"fix:  write 2019, 2019-04 or 2019-04-01 - precision is read "
                    f"from what you write")
        return None

    if kind.startswith("vocab:"):
        allowed = VOCABULARIES[kind.split(":", 1)[1]]
        if value not in allowed:
            return (f"`{name}` must be one of {', '.join(allowed)} - not {value!r}\n"
                    f"fix:  these compare as exact strings, so a near-synonym does "
                    f"not fail, it silently stops matching")
        return None

    # Unreachable through TYPES, and deliberately loud rather than silently clean: a
    # kind nobody implemented would otherwise make every value of that key legal.
    raise ValueError(f"{name}: no such kind {kind!r}")


def check(type_name, values, extensions=()):
    """Every problem with these values, as sentences. Empty means clean.

    `extensions` are keys the caller declared with --set. They are accepted without a
    kind, because an extension key is by definition one this schema does not model -
    `bundle-spec.md` says `type` is the only key OKF requires.

    What an extension may not be is a near-miss of a real key. `--set startDate=2026`
    is the defect this layer exists to stop, and an escape hatch that swallows it
    silently is not an escape hatch, it is the hole. So the spelling check runs on
    extensions too; only the kind check is skipped.
    """
    kinds = _kinds(type_name)
    if kinds is None:
        return [f"unknown concept type `{type_name}`\n"
                f"fix:  one of {', '.join(sorted(TYPES))} - a near-synonym fragments "
                f"the graph, so this refuses rather than inventing a type"]

    declared = set(extensions)
    problems = []

    for key in kinds.values():
        # `None` counts as absent, not as a value: concept.frontmatter() drops a None
        # rather than writing it, and set_key(key, None) deletes the line. A required
        # key reported clean here would then not be in the file this call approved.
        if key.required and values.get(key.name) is None:
            problems.append(
                f"{key.name} is required on a {type_name}\n"
                f"fix:  a {type_name} without it does not compile - see "
                f"bundle-spec.md")

    for name, value in values.items():
        if not isinstance(name, str):
            # difflib compares strings, so an int key raised TypeError here rather
            # than saying anything. A message beats a traceback.
            problems.append(f"`{name!r}` is not a key - a key is text\n"
                            f"fix:  write it as `key: value`")
            continue
        key = kinds.get(name)
        if key is not None:
            if value is not None:
                problem = _value_problem(key, value)
                if problem:
                    problems.append(problem)
            continue
        house = SPELLINGS.get(name)
        if house and house in kinds:
            # Named rather than reported as a typo. "did you mean" implies the writer
            # erred, and `organization` is not an error - it is the spelling
            # okf_compile.py still accepts for older bundles.
            problems.append(
                f"`{name}` is not a key of {type_name} - this codebase spells it "
                f"`{house}`\n"
                f"fix:  write `{house}` - the compiler reads both, for bundles "
                f"written before the spelling settled, and new ones use one")
            continue
        near = _nearest(name, kinds)
        if near:
            # Reported even when declared as an extension. A key one letter from a
            # real one is a typo far more often than it is a new field, and the
            # declaration is exactly what would hide it.
            problems.append(
                f"`{name}` is not a key of {type_name} - did you mean "
                f"`{near}`?\n"
                f"fix:  correct the spelling, or rename it to something no real key "
                f"is a near-miss of")
        elif name not in declared:
            problems.append(
                f"`{name}` is not a key of {type_name}\n"
                f"fix:  --set {name}=<value> declares it as an extension key, if "
                f"that is what it is")
    return problems
