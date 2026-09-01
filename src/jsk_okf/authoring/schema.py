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
    # A posting's requirements. `kind` is what the ranking matches on and
    # `necessity` is the distinction the Markdown posting exists to make - see
    # bundle-spec.md, "Postings on disk". score_projects.py excludes `implicit` by
    # default, so a requirement invented as `required` makes a good fit look bad.
    "kind": ("capability", "technology"),
    "necessity": ("required", "preferred", "implicit"),
    # A Gap Assessment's own verdict, from jsk-tailor-analyst.md.
    "fit": ("strong", "partial", "poor"),
    # A view's `format_profile`, matching the four variants in ats-rules.md.
    # validate_urs.py requires the key and checks nothing about its value, so a
    # typo here rendered under rules nobody chose.
    "format_profile": ("presentation", "ats-maximal", "plaintext", "web"),
    # Whether a certification is current. Deliberately not `status` above: a
    # `# Held` entry's `status` is about the certification and the concept's
    # frontmatter `status` is about how well the bundle knows the claim.
    # okf_compile.build_credentials defaults this to `active`.
    "credential": ("active", "expired", "lapsed", "in-progress"),
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
    # `frozen:` by name, so refusing it here would refuse what the skill instructs.
    Key("frozen", "flag"),
    Key("frozen_date", "date"),
    Key("superseded_by", "text"),
)

# A View's bookkeeping is exactly what okf_compile.build_views() strips before the view
# reaches URS - `okf_compile.CONCEPT_KEYS`. COMMON is wider than that by two keys, and
# neither `tags` nor `resource` is in `validate_urs.VIEW_KEYS` either: a view carrying
# one reaches the record as an unknown view key and **fails the record gate on every run
# from the day it is written**, because the gate compiles the whole bundle and an
# never gets better.
#
# So a View gets COMMON minus those two rather than COMMON. Found by tailoring.py's
# author reading VIEW_KEYS against this table; `ViewKeysMatchTheRecordGate` in
# tests/test_authoring_schema.py now asserts it, which is what stops the next key added
# to COMMON reopening it silently.
VIEW_COMMON = tuple(key for key in COMMON if key.name not in ("tags", "resource"))

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
        # The other three career types carried these and this one did not, which
        # made `org retire` write two keys the schema would then refuse on the next
        # `org set`. Found by career.py's author, who had to declare them as
        # extensions to work around it.
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    # okf_compile.build_education reads `institute` and `period` out of the BODY as a
    # labelled list - `- **Institute:** Mahatma Gandhi University` - not out of
    # frontmatter. So they are absent here on purpose: a key named in frontmatter that
    # the compile never reads is a value somebody wrote and no resume shows.
    # education.py writes those two lines into the body instead.
    "Education": COMMON + (
        Key("title", "text", required=True,
            because="okf_compile.build_education reads the qualification off `title`, "
                    "falling back to the filename - so a degree with no title renders "
                    "on a resume as its own stem"),
        Key("id", "slug"),
        # All three pass through to the record untranslated (build_education), and none
        # is a closed vocabulary anywhere in the format.
        Key("level", "text"),
        Key("field", "text"),
        Key("location", "text"),
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    # The type name is the whole point: it reports a *status*, and "none held" is a
    # legitimate one that evidences no credential. Nothing here is required beyond a
    # title, because a concept recording a certification gap is a valid concept.
    "Certification Status": COMMON + (
        Key("title", "text", required=True,
            because="a Certification Status with no title is a document nobody can "
                    "find, and okf_compile.build_credentials uses it as the "
                    "credential name for a single-certification concept"),
        Key("id", "slug"),
        Key("retired", "date"),
        Key("retired_reason", "text"),
    ),
    "Skill Set": COMMON + (
        Key("title", "text", required=True,
            because="it is the document's name in skills/index.md, and a Skill Set "
                    "with no title is one nobody opens"),
        Key("id", "slug"),
    ),
    "Metric Set": COMMON + (
        Key("title", "text", required=True,
            because="it is the document's name in achievements/index.md"),
        Key("id", "slug"),
    ),
    "Job Posting": COMMON + (
        Key("title", "text", required=True,
            because="score_projects.py labels the ranking with it, and a posting with "
                    "no title cannot say which job was ranked"),
        Key("id", "slug"),
        Key("company", "text", required=True,
            because="the application stem is <date>-<company>-<role>, and an archive "
                    "that cannot say who a posting was for cannot be searched"),
        Key("url", "text"),
        # The two the ranking runs on besides the requirements themselves.
        Key("seniority", "vocab:seniority"),
        Key("domains", "slugs"),
        Key("requirements", "requirements"),
        # mode-ship.md instructs this on the frozen copy beside an application.
        Key("superseded_by", "text"),
    ),
    "Gap Assessment": COMMON + (
        Key("id", "slug"),
        # The stem of the posting this answered. Not `slug`-shaped by accident: the
        # gaps file sits beside `<stem>.posting.md` and validate_bundle.py requires
        # that neighbour, so this names it.
        Key("posting", "slug", required=True,
            because="validate_bundle.py rejects a .gaps.md with no .posting.md beside "
                    "it - an assessment that cannot say what it was answering is not "
                    "an assessment"),
        Key("assessed", "date"),
        Key("fit", "vocab:fit"),
    ),
    # A View is the one concept whose frontmatter IS the document it compiles to.
    # Every key below is in validate_urs.VIEW_KEYS, and `ViewKeysMatchTheRecordGate`
    # in tests/test_authoring_schema.py asserts that both ways: a key here that the
    # gate does not know fails the record gate on every run from the day it is
    # written, and a key the gate knows and this refuses is a view nobody can author.
    "View": VIEW_COMMON + (
        Key("id", "slug"),
        Key("label", "text"),
        Key("format_profile", "vocab:format_profile", required=True,
            because="validate_urs.py fails a view with no format_profile - it is "
                    "which of ats-rules.md's four variants the render obeys"),
        Key("region_profile", "text"),
        Key("locale", "text"),
        Key("narrative", "slug"),
        Key("target", "target"),
        Key("include", "include"),
        Key("sections", "slugs"),
        Key("skills", "slugs"),
        Key("redact", "paths"),
        Key("provenance_floor", "vocab:status"),
        Key("budget", "budget"),
        # The URS extension point. validate_urs.py fails any unknown view key and
        # names this as where an extension belongs, so `--set` on a view writes here
        # rather than at the top level - which is why this is a writable mapping
        # where `location` is not: the gate defines this one and checks nothing
        # inside it, so a scalar written here is right by construction.
        Key("x", "extensions"),
    ),
    "Application": COMMON + (
        Key("title", "text", required=True,
            because="it is the row in the year's index.md, and an archive of "
                    "untitled applications is one nobody reads back"),
        Key("id", "slug"),
        # The three frozen companions and the two paths that leave the directory.
        # All five are relative paths rather than slugs - `../../targets/x.posting.md`
        # is not a stem - and validate_bundle.py resolves each against the
        # application's own directory.
        Key("posting", "text"),
        Key("assessment", "text"),
        Key("view_file", "text"),
        Key("target_working_copy", "text"),
        Key("company_ref", "text"),
        # The id inside the view, not the file: what was rendered.
        Key("view", "slug"),
        # A date, or the literal false for an application deliberately held back.
        # bundle-spec.md makes `submitted: false` the one exemption from the
        # timeline's `submitted` row, so the key has to carry both.
        Key("submitted", "date-or-false"),
        Key("channel", "text"),
        # Both read by pipeline.py:55-56 off the Application's own frontmatter -
        # `company` is what `pipeline --company NAME` matches on, falling back to
        # `title`, and `role` is the second column of the weekly board. Neither is
        # a slug: they are display names, and the concepts they describe are named
        # by `company_ref` and by the posting beside them.
        #
        # Modelled because they were reachable and refused: `--set company=Ashby`
        # came back as a near-miss of `company_ref`, so the one route to a key a
        # shipped reader reads was the escape hatch calling it a typo. Found by
        # archive.py's author.
        Key("company", "text"),
        Key("role", "text"),
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
                               "moment", "flag", "unwritable", "requirements",
                               "target", "include", "budget", "paths",
                               "date-or-false", "extensions"})


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

    if kind == "date-or-false":
        # `submitted:` on an Application. bundle-spec.md: a date, or the literal
        # false for one deliberately held back - which is the only thing that
        # exempts it from validate_bundle.py's demand for a `submitted` timeline
        # row. `true` is not in the set: it would claim a submission with no date,
        # and the row beneath it is what records that anyway.
        if value is False:
            return None
        if isinstance(value, bool) or not DATE.match(str(value).strip()):
            return (f"`{name}` must be a date, or false - not {value!r}\n"
                    f"fix:  write the day it was sent, as 2026-08-26. `false` is for "
                    f"an application worked through and deliberately held back, and "
                    f"is the only thing that excuses a timeline with no `submitted` "
                    f"row")
        return None

    if kind == "paths":
        # A view's `redact`: dotted paths into the record - `person.phone`. Not
        # `slugs`: a dot is the separator, and SLUG admits one, so the shape would
        # pass while saying nothing about whether the path is one.
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            return (f"`{name}` must be a list, not a {type(value).__name__}\n"
                    f"fix:  write it as [person.phone] - one dotted path per entry")
        for item in value:
            if not isinstance(item, str) or not REDACTION.match(item):
                return (f"`{name}` takes dotted paths - not {item!r}\n"
                        f"fix:  `person.phone`, `person.address.city` - the path into "
                        f"the record of the thing to leave out")
        return None

    if kind == "extensions":
        if not isinstance(value, dict):
            return (f"`{name}` must be a mapping, not a {type(value).__name__}\n"
                    f"fix:  --set key=value writes into it - it is where "
                    f"validate_urs.py says a view's extensions belong")
        for key_name, item in value.items():
            if not isinstance(key_name, str):
                return (f"`{name}`: {key_name!r} is not a key - a key is text\n"
                        f"fix:  --set key=value")
            if isinstance(item, (dict, list, tuple)):
                return (f"`{name}.{key_name}` is a {type(item).__name__}, and this "
                        f"layer writes one level\n"
                        f"fix:  write a scalar - a nested extension is a document "
                        f"only this command would understand")
        return None

    if kind in STRUCTURED:
        return _structured_problem(name, kind, value)

    # Unreachable through TYPES, and deliberately loud rather than silently clean: a
    # kind nobody implemented would otherwise make every value of that key legal.
    raise ValueError(f"{name}: no such kind {kind!r}")


# A dotted path into the record. Deliberately not SLUG: `person..phone` and
# `.phone` are both slug-shaped and neither is a path.
REDACTION = re.compile(r"^[A-Za-z_][\w-]*(\.[A-Za-z_][\w-]*)*\Z")


class Field:
    """One key inside a structured value, or inside an authored item.

    The same three questions a Key answers, one level down. Separate from Key
    because a Field has no `because`: a structured value is written whole by a
    command, so what is missing is named by the command's own flag rather than by
    a reason about the format.
    """

    def __init__(self, name, kind, required=False):
        self.name = name
        self.kind = kind
        self.required = required


# The four keys whose value is a mapping or a list of mappings, and what each
# holds. concept.structured() writes them; okf_compile.posting() and
# validate_urs.py read them.
#
# `mapping` means one mapping, `sequence` means a list of them.
STRUCTURED = {
    "requirements": ("sequence", (
        # value/kind are what okf_compile.posting() refuses without, by name.
        Field("value", "slug", required=True),
        Field("kind", "vocab:kind", required=True),
        # Optional to the compiler and required by the ranking's meaning:
        # score_projects.py excludes `implicit` by default, so an absent necessity
        # is a requirement counted as though the posting demanded it.
        Field("necessity", "vocab:necessity", required=True),
        # The posting's own wording, kept because that is what belongs in prose
        # later. Never the vocabulary term.
        Field("label", "text"),
    )),
    "include": ("sequence", (
        Field("ref", "slug", required=True),
        # Not `rank`. A rank is 1-5 and its refusal talks about flagship evidence,
        # which is `strength`'s subject and not this one - and a view selecting
        # eight engagements has to be able to number the sixth. urs/resolve.py
        # defaults an absent order to 10**6 and then re-sorts engagements by date
        # anyway, so there is no ceiling to enforce here at all.
        Field("order", "position"),
        Field("achievements", "slugs"),
        Field("skills", "slugs"),
        # Read by nothing. Listed because jsk-resume-author.md's own example view
        # carries it, so a view written against that instruction - which is every
        # view a real run has produced - would otherwise be refused by the first
        # `view set` that touched it. The same tolerance okf_compile.py extends to
        # the `organization` spelling, for the same reason: this layer arrived
        # after the bundles did.
        Field("treatment", "text"),
    )),
    # Either shape. view-format.md defines the mapping - {title, ref} - and
    # jsk-resume-author.md's example writes a bare posting stem. Nothing reads
    # either: `target` is metadata about the application, and view-format.md
    # states outright that it is never rendered into the document body. So both
    # are tolerated and `view create` writes the mapping, which is the one the
    # specification actually defines.
    "target": ("mapping-or-text", (
        Field("title", "text"),
        Field("ref", "text"),
    )),
    "budget": ("mapping", (
        # Pages, and not `rank`: a resume budget is 1-5 pages by coincidence of
        # range, and a rank's `fix:` line talks about flagship evidence.
        Field("pages", "pages"),
        # ATS-maximal is deliberately longer - it repeats the employer on every
        # role line and expands the skills block with aliases - so it carries its
        # own budget and falls back to `pages` when a view does not set it.
        # urs/resolve.py:536 reads it, which is what makes it a real key rather
        # than one somebody wrote once.
        Field("ats_maximal_pages", "pages"),
    )),
}


def _field_problem(prefix, field, value):
    """What is wrong with one field of a structured value or an item."""
    if field.kind == "pages":
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            return (f"`{prefix}.{field.name}` must be a whole number of pages, not "
                    f"{value!r}\n"
                    f"fix:  --pages 2 - the budget the view asks the render for")
        return None
    if field.kind == "position":
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            return (f"`{prefix}.{field.name}` must be a whole number from 1 up, not "
                    f"{value!r}\n"
                    f"fix:  --order 1 puts this entry first. Within an entry it is "
                    f"the achievements' own order that decides which bullet leads; "
                    f"engagements always render by date, whatever this says")
        return None
    # Every other field kind is a value kind, so it is checked by the same code
    # that checks a frontmatter key. A second implementation here is how the two
    # would come to disagree about what a slug is.
    return _value_problem(Key(f"{prefix}.{field.name}", field.kind), value)


def _entry_problems(prefix, fields, value):
    """Every problem with one mapping, against `fields`."""
    by_name = {field.name: field for field in fields}
    problems = []
    if not isinstance(value, dict):
        return [f"`{prefix}` must be a mapping, not a {type(value).__name__}\n"
                f"fix:  each entry holds "
                f"{', '.join(f.name for f in fields if f.required) or 'named keys'}"]
    for field in fields:
        if field.required and value.get(field.name) is None:
            problems.append(
                f"`{prefix}` needs `{field.name}`\n"
                f"fix:  every entry carries "
                f"{', '.join(f.name for f in fields if f.required)}")
    for name, item in value.items():
        if not isinstance(name, str):
            problems.append(f"`{prefix}`: {name!r} is not a key - a key is text\n"
                            f"fix:  write it as `key: value`")
            continue
        field = by_name.get(name)
        if field is None:
            near = _nearest(name, by_name)
            hint = (f"did you mean `{near}`?" if near
                    else f"it takes {', '.join(sorted(by_name))}")
            problems.append(
                f"`{prefix}` has no `{name}` - {hint}\n"
                f"fix:  a key nothing reads is a value somebody wrote that no "
                f"resume shows")
            continue
        if item is None:
            continue
        problem = _field_problem(prefix, field, item)
        if problem:
            problems.append(problem)
    return problems


def _structured_problem(name, kind, value):
    """The first problem with a mapping or list-of-mappings value. None means clean."""
    shape, fields = STRUCTURED[kind]
    if shape == "mapping-or-text":
        if isinstance(value, str):
            return _value_problem(Key(name, "text"), value)
        shape = "mapping"
    if shape == "mapping":
        problems = _entry_problems(name, fields, value)
        return problems[0] if problems else None
    if isinstance(value, dict) or not isinstance(value, (list, tuple)):
        return (f"`{name}` must be a list of entries, not a "
                f"{type(value).__name__}\n"
                f"fix:  each entry is one mapping - see bundle-spec.md")
    for n, entry in enumerate(value, 1):
        problems = _entry_problems(f"{name}[{n}]", fields, entry)
        if problems:
            return problems[0]
    return None


# --- the authored items ---------------------------------------------------------
#
# body.py knows the shape of a `- item` and its `key: value` lines; this knows
# which keys each kind takes and what each may hold. The split is the module's own:
# concept.py formats and does not judge, and body.py is concept.py's counterpart
# for the body.
#
# Every key here is one okf_compile passes to blocks(), and body.KINDS carries the
# same tuples for the parser. `ItemKeysMatchTheCompiler` in
# tests/test_authoring_schema.py asserts the two lists are the same set - a key
# this schema accepts that the compiler does not parse is a field that silently
# becomes part of the sentence.
ITEMS = {
    "bullet": (
        # A bullet arriving `inferred` is the default the compiler applies, and
        # tailoring writes bullets that way: `provenance_floor: confirmed` on a
        # view is what stops one rendering before a person has said otherwise.
        Field("status", "vocab:status"),
        # Text, not a slug: it names a row in achievements/metrics.md by its
        # label - "Event propagation latency" - which the compiler slugs itself.
        Field("metric", "text"),
        # Which posting the sentence was written for. Read by no script, and
        # authored data worth keeping: it is how a person tells a tailored bullet
        # from one that was always true.
        Field("for", "text"),
        Field("id", "slug"),
    ),
    "skill": (
        Field("id", "slug"),
        Field("category", "text"),
        # A comma-separated string, not a list: okf_compile.build_skills splits it
        # on commas itself. A YAML list here would reach the record as one alias
        # containing brackets.
        Field("aliases", "text"),
        Field("last_used", "date"),
    ),
    "credential": (
        Field("id", "slug"),
        Field("issuer", "text"),
        Field("issued", "date"),
        Field("expires", "date"),
        Field("status", "vocab:credential"),
    ),
}


def check_item(kind, fields):
    """Every problem with one authored item's fields. Empty means clean.

    The item's text is not checked here: whether a sentence is a good sentence is
    references/writing-rules.md's question and a person's, and this module judges
    values.
    """
    known = ITEMS.get(kind)
    if known is None:
        raise ValueError(f"check_item: no such item kind {kind!r} - "
                         f"one of {', '.join(sorted(ITEMS))}")
    return _entry_problems(kind, known, dict(fields))


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
