"""What each concept type takes, and what each value must satisfy.

This is the only machine-readable statement of the format's *shape* - which keys a type
takes, and what each value must satisfy. `references/bundle-spec.md` is its prose
counterpart and the two are meant to be read together; a rule in one and not the other
is a defect in whichever is missing it.

**One class of rule is deliberately not here: anything that needs the bundle.** This
module takes values and nothing else - no path, no filesystem, no cross-file lookup -
so a rule about whether some *other* file exists or says something cannot live in it.
Three rules are in that class, and they are the complete list:

  - whether a `capabilities` value is in `framework/capability-vocabulary.md`.
    `validate_bundle.py` enforces it, and only when that file has values outside a
    fence; the resolution is `--new-capability foo --theme "Data"`, which writes a file.
  - whether a Project's `role` names a concept in `roles/`.
  - whether a Role's `organisation` names a concept in `organisations/`.

The last two are the more expensive to miss: `validate_bundle.py` does not check them
at all, `okf_compile.py` refuses outright, and `okf score` calls okf_compile.load() -
so a dangling reference aborts a tailoring run rather than failing a gate. All three
belong to the command layer, which has the bundle path. **Every other rule either gate
applies is meant to be predicted from values alone**, and `SchemaAgreesWithTheGate` in
tests/test_authoring.py asserts that end to end, with the capability vocabulary
populated so the gate's own check is switched on rather than silently skipped.

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

# The slug-shaped keys that name a file on disk. The rest of them - `capabilities`,
# `domains`, `tags` - name a vocabulary term and name no file at all, so they need a
# different `fix:` line: "name the concept's filename" sent a person looking for a file
# that does not exist for five of the six keys that were being told to find one.
RELATIONAL = frozenset({"role", "organisation"})

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
    """One frontmatter key: what it is called, what it holds, whether it is required.

    `because` is the reason a required key is required, and it is per-key rather than
    one sentence for all of them because no single sentence is true. Removing each
    required key in turn and compiling: only `Role.organisation` stops the compile. Of
    the nine, five are hard errors in validate_bundle.py and four are neither - they
    are required here because what they produce without a value is a bad record rather
    than a broken one. A `fix:` line stating a reason that does not hold sends the
    person to the wrong file, so each says its own.
    """

    def __init__(self, name, kind, required=False, because=None):
        self.name = name
        self.kind = kind
        self.required = required
        self.because = because


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
    # Slug-shaped by this layer's choice, not by anybody's rule: nothing in
    # bundle-spec.md or the scripts says what a tag may look like. The format leaves it
    # open and the write layer closes it, so that a bundle's tags stay one shape and a
    # future `okf list --tag` can match them. Recorded as a decision, not a finding.
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

# Said once because five keys share it verbatim, and five copies of a sentence drift.
SELECTION_KEY = ("validate_bundle.py makes this a hard error on every Project - "
                 "\"missing selection key\" - so a bundle carrying one without it "
                 "does not go green")

TYPES = {
    "Project": COMMON + (
        Key("title", "text", required=True,
            because="okf_compile.py falls back to the filename, so a project with no "
                    "title renders on a resume as its own stem"),
        Key("id", "slug"),
        Key("role", "slug", required=True,
            because="a project with no role compiles to no engagement, so it belongs "
                    "to no employer and renders nowhere"),
        # The five selection keys. Required because validate_bundle.py makes each a
        # hard error on every Project - "Project missing selection key" - so a Project
        # this layer called clean without them is one the bundle gate then rejects,
        # and the person finds out at ship time instead of at write time. The compiler
        # tolerates their absence; the gate does not, and the gate is what runs.
        Key("strength", "rank", required=True, because=SELECTION_KEY),
        Key("recency", "year", required=True, because=SELECTION_KEY),
        Key("seniority", "vocab:seniority", required=True, because=SELECTION_KEY),
        Key("domains", "slugs", required=True, because=SELECTION_KEY),
        Key("capabilities", "slugs", required=True, because=SELECTION_KEY),
        Key("technologies", "slugs"),
        # Read by no script, and correct to list: it is authored data a model reads
        # when writing a summary. Not dead, so do not delete it as dead.
        Key("headline_metric", "text"),
        Key("url", "text"),
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    "Role": COMMON + (
        Key("title", "text", required=True,
            because="okf_compile.py falls back to the filename, so a role with no "
                    "title renders on a resume as its own stem"),
        Key("id", "slug"),
        Key("functional_title", "text"),
        Key("organisation", "slug", required=True,
            because="okf_compile.py refuses outright - a role that cannot say who it "
                    "was for cannot be placed on a resume. This is the only required "
                    "key whose absence stops the compile"),
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
        Key("title", "text", required=True,
            because="okf_compile.py falls back to the filename, so the employer's "
                    "name on the resume becomes its own stem"),
        Key("id", "slug"),
        # Required though no script reads it. bundle-spec.md's Organisations section
        # presents it as the type's defining key, and an organisation that cannot say
        # whether they were an employer or a prospect is a record nobody can use.
        Key("relationship", "vocab:relationship", required=True,
            because="bundle-spec.md makes it the type's defining key - an "
                    "organisation that cannot say whether they were an employer or a "
                    "prospect is a record nobody can search"),
        # A list, not text. build_organizations passes it straight through to URS,
        # where schema/example.resume.json writes `"industry": ["healthcare",
        # "aged-care"]` - so a bare string reached the record as a string where every
        # consumer expects an array. `sector` and `size` beside it really are strings.
        Key("industry", "slugs"),
        Key("sector", "text"),
        Key("size", "text"),
        Key("url", "text"),
        # Both read off the organisation by okf_compile.build_engagements.
        Key("employment", "vocab:engagement"),
        Key("location", "unwritable"),
    ),
}


def _role_period_contradictions(values):
    """`state` against `end`, which okf_compile.period() refuses to reconcile.

    The first rule in this module that spans two keys, and the reason CROSS_CHECKS
    exists. A `Key` describes one key and has nowhere to put a rule about a pair, so
    the comment on `state` used to cite period()'s derivation and stop one line short
    of the two contradictions it raises on:

        if end and state == "ongoing":   raise Problem(...)
        if state == "ended" and not end: raise Problem(...)

    Both are decidable from values already in hand - no bundle, no filesystem, no
    cross-file lookup - and neither is a distant gate. `okf score` calls
    okf_compile.load(), so an unnoticed contradiction aborts a tailoring run, not just
    a ship.
    """
    state, end = values.get("state"), values.get("end")
    problems = []
    if state == "ongoing" and end is not None:
        problems.append(
            "state is ongoing but an end date is set - one of them is wrong\n"
            "fix:  drop `end` if the role is current, or write `state: ended` if it "
            "is not. okf_compile.py refuses to guess which, and so does this")
    if state == "ended" and end is None:
        problems.append(
            "state is ended but no end date is set\n"
            "fix:  write `end`, or `state: unknown` if the date is genuinely not "
            "known - an ended role with no end date stops the compile")
    return problems


# Rules that span two keys live here, because a Key describes one key and cannot hold
# one. Narrow on purpose: only rules decidable from the values passed in. Anything
# needing the bundle belongs to the command layer - see the module docstring.
CROSS_CHECKS = {"Role": (_role_period_contradictions,)}

# Every kind `_value_problem` implements. Asserted against TYPES at import, which is
# what makes its trailing `no such kind` raise provably unreachable rather than merely
# commented as such - and catches a typo'd kind, which would otherwise make every
# value of that key legal, at import instead of never.
IMPLEMENTED_KINDS = frozenset({"text", "slug", "slugs", "rank", "year", "date",
                               "moment", "flag", "unwritable"})


def _assert_kinds_are_implemented():
    for type_name, keys in TYPES.items():
        for key in keys:
            if key.kind.startswith("vocab:"):
                if key.kind.split(":", 1)[1] in VOCABULARIES:
                    continue
                raise ValueError(
                    f"{type_name}.{key.name}: no vocabulary named "
                    f"{key.kind.split(':', 1)[1]!r} in VOCABULARIES")
            if key.kind not in IMPLEMENTED_KINDS:
                raise ValueError(
                    f"{type_name}.{key.name}: no such kind {key.kind!r} - "
                    f"_value_problem implements {', '.join(sorted(IMPLEMENTED_KINDS))}")


def _assert_no_conflicting_duplicates():
    """A type may repeat a key only to sharpen it, never to redefine what it holds.

    Repeating a name is how a type sharpens a COMMON key - `title` is optional in
    COMMON and required on all three types, and _kinds() lets the later entry win. The
    same mechanism silently disables a kind if the later entry names a different one,
    and no test could see it: every value of that key would simply be checked against
    the wrong rule and most would pass. Raised at import so the tuple cannot ship wrong.

    `required` is guarded in one direction only, and that is the whole claim: a repeat
    may turn a key on and never off. A later entry silently *loosening* an earlier
    `required=True` is the same invisible defect wearing the other sign - the key stops
    being demanded and nothing says so - and this used to compare `kind` alone, so the
    docstring promised a rule the code did not check.
    """
    for type_name, keys in TYPES.items():
        seen = {}
        for key in keys:
            prior = seen.get(key.name)
            if prior is not None and prior.kind != key.kind:
                raise ValueError(
                    f"{type_name} declares `{key.name}` as both {prior.kind!r} and "
                    f"{key.kind!r} - a repeat may sharpen `required`, never the kind")
            if prior is not None and prior.required and not key.required:
                raise ValueError(
                    f"{type_name} repeats `{key.name}` to make it optional again - a "
                    f"repeat may sharpen `required`, never relax it")
            seen[key.name] = key


_assert_kinds_are_implemented()
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
    """A slug-shaped value, with a `fix:` line that fits what the key actually holds.

    One line used to serve all six: "name the concept's filename without its .md". It
    is right for `role` and `organisation`, which do name a file, and actively
    misleading for `capabilities`, `domains`, `technologies`, `tags` and `id`, none of
    which name one - a person told to find a file for a capability goes looking for a
    file that was never going to exist.
    """
    if isinstance(value, str) and SLUG.match(value):
        return None
    shape = "letters, digits, `-`, `.`, `_` or `/`"
    if name in RELATIONAL:
        return (f"`{name}` must be a file stem - {shape} - not {value!r}\n"
                f"fix:  name the concept's filename without its .md, not its title")
    if name == "id":
        return (f"`{name}` must be an identifier - {shape} - not {value!r}\n"
                f"fix:  give the id this concept already published, in the shape "
                f"okf_compile.py derives - `prj_aged_care` - or leave it out and let "
                f"it be derived")
    return (f"`{name}` takes vocabulary terms - {shape} - not {value!r}\n"
            f"fix:  write it the way framework/capability-vocabulary.md does, "
            f"lowercase and hyphenated - `data-sovereignty`, not prose. These compare "
            f"as exact strings, so a value with a space in it matches nothing")


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

    if kind == "unwritable":
        # A kind that exists to refuse, and is not dead code - do not delete it.
        # urs-spec.md:169 and schema/example.resume.json both define `location` as
        # {city, region, country, mode}; concept.py emits scalars and flow lists and
        # deliberately not mappings; and validate_urs.py checks the shape nowhere -
        # the string "location" does not appear in it. So a location written through
        # this layer would be wrong URS that nothing would catch, and writing a value
        # known to be the wrong shape is worse than not offering the key.
        #
        # The key stays listed so it is neither reported as unknown nor offered as a
        # near-miss of something else, and so `--set` cannot loosen it: an extension
        # declaration is ignored for any key this schema models.
        return (f"`{name}` is a mapping this layer cannot write\n"
                f"fix:  set it by hand in the concept - urs-spec.md has the shape, "
                f"{{city, region, country, mode}}")

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
        #
        # This is a deliberate divergence in the stricter direction, and the only one:
        # validate_bundle.py tests `isinstance(s, int)` and so accepts `strength: true`
        # as a 1. That acceptance is a Python artefact rather than an intention -
        # nobody means "true" when they rank evidence - so this layer refuses it and
        # the gate still passes whatever it writes.
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
        # Says what this layer can write, not what the format has. bundle-spec.md lists
        # twenty-six concept types; three of them have a definition here. Offering the
        # three as "the types" told somebody writing an Education concept that they had
        # invented a near-synonym, and handed them three alternatives, none of which
        # was what they wanted. The refusal is right and that explanation was not.
        return [f"`{type_name}` is not a concept type this layer can write yet\n"
                f"fix:  it can write {', '.join(sorted(TYPES))}. bundle-spec.md lists "
                f"the rest, and one of those is written by hand until a command "
                f"exists for it - check the spelling there before adding a type, "
                f"because a near-synonym fragments the graph"]

    # `or ()` rather than trusting the caller: a CLI writing
    # `extensions=args.set or None` is one plausible slip from a TypeError here, and
    # the empty case is exactly what None means.
    declared = set(extensions or ())
    problems = []

    for key in kinds.values():
        # `None` counts as absent, not as a value: concept.frontmatter() drops a None
        # rather than writing it, and set_key(key, None) deletes the line. A required
        # key reported clean here would then not be in the file this call approved.
        if key.required and values.get(key.name) is None:
            article = "an" if type_name[:1].upper() in "AEIOU" else "a"
            problems.append(
                f"{key.name} is required on {article} {type_name}\n"
                f"fix:  {key.because}")

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

    # Last, so that a rule about a pair of keys reads after whatever is wrong with
    # either one on its own.
    for rule in CROSS_CHECKS.get(type_name, ()):
        problems.extend(rule(values))
    return problems
