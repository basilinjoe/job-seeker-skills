"""`okf list <noun>` - an inventory of one kind of thing, for twelve kinds of thing.

Every one of these was already answerable and none of them was already answered. The
projects were in `record.json` behind a compile, the bullet ids were in it and nowhere
else, the open questions were in a Markdown table two mode files read by eye, and the
capability histogram - which term is on three projects and therefore safe to claim as a
through-line - existed only as a thing somebody counted by hand and got wrong.

**Twelve nouns, one shape.** Each is one `@answers(...)` block, carrying its columns,
the filter axes its rows can honestly be narrowed by, and the function that answers
it - plus one row in `SCOPES`, which is where the walk it may do is written down and
is deliberately a table you can read all twelve of at once. Nothing dispatches on a
noun's name and nothing switches on it: the argument checking, the archive note, the
frozen warning and the summary are written once, below. A thirteenth noun is that one
block and that one row, and a noun missing from `SCOPES` fails on import rather than
walking the whole bundle. The alternative - a `run()` with twelve branches - is how
the fourth noun quietly ignores a filter the third honours, and how the ninth prints a
truncated sentence because somebody forgot the column width is `None` on the last one.

**A filter that cannot apply is refused, never dropped.** `--capability` narrows
projects because a Project carries `capabilities:`; it cannot narrow a metrics table
row, which carries no selection keys at all. Accepting it there and returning every row
would answer a question nobody asked and read as though the filter had run - so each
noun declares the axes it accepts and anything else is a `filters.Bad` naming the noun
and the flag. `--type` is accepted by none of them, because the noun *is* the type; the
flag belongs to `okf search`, which crosses types.

**No id is derived here.** Every id printed comes from `ids.of()`, which composes each
shape out of the helper the compile mints it with. That matters most for `bullets`
and is the reason the noun exists: `okf view include` names a bullet id, nothing
exposed those ids before it, and an id this module derived a character differently from
the write layer would be an id `okf list` prints and `view include` then refuses.
`tests/test_query_listing.py` pins the agreement against
`authoring.common.item_ids(bundle, "bullet")` directly, in both directions.

**One walk, and only over what can hold an answer.** Both halves of that were
measured, and both were wrong first. Calling `ids.index()` for the ids on top of this
module's own walk read the bundle twice, and an unscoped walk opened every file in it
to discard most of them by type - together they made `okf list projects` cost 1.8
times the compile this whole layer exists to be cheaper than. So the ids come from
`ids.of(concept)`, which mints them for a concept already in hand; each noun declares
the subtrees its concepts live in, and directories no scope reaches are pruned rather
than traversed; and the walk carries a literal pre-filter - the type's own name -
because reading a file is cheap and parsing its frontmatter is almost all of what a
listing costs. On a bundle of a hundred projects and a hundred answered postings every
noun now costs between a five-hundredth and two thirds of the compile, `list postings`
having come down from just over it.

**Order is declared, never incidental.** A listing whose order is arbitrary is one
people read a ranking into, so each noun sorts on something it can defend and says
what: strongest first for projects, most recent first for roles and credentials, most
cited first for metrics, file order for the open questions because that is the order
`okf question add` appended them and the order mode-gaps.md works them.
"""

import os

from .. import markup, okf_compile
from . import filters, ids, render, walk

# --- the table -------------------------------------------------------------------

NOUNS = {}

# The filter flags, by the argparse destination that carries each one. Read off the
# raw arguments rather than off `filters.Metadata`, so that `list metrics --strength
# nonsense` says the flag does not apply here rather than that the number is malformed:
# the first is the caller's actual mistake and the second is a detail of a flag they
# should not have reached for.
AXES = ("status", "capability", "technology", "domain", "seniority", "strength",
        "recency")

# What a metadata filter narrows by default, where a noun does not say otherwise.
# `status` is provenance and every concept carries it, so it is the one axis that is
# always honest.
DEFAULT_AXES = ("status",)

# `bundle-spec.md`: "Values appearing on three or more projects are the ones safe to
# claim as a through-line in a summary." The number is the whole reason `list
# capabilities` counts rather than merely listing, so it is named here rather than
# written into the comparison.
THROUGH_LINE = 3


# Where each noun's concepts live, so a walk reads the directories that can hold an
# answer and prunes the rest. Measured: unscoped, `list projects` read 217 files on a
# hundred-target bundle and cost 1.8 times the compile it exists to be cheaper than;
# scoped to `projects/` it reads 102 and prunes the other directories rather than
# opening every file in them to throw it away.
#
# This is `authoring.common.DIRECTORIES` for the types the two share, and it is
# duplicated rather than imported for the reason `commands.REQUIRED` is: reaching into
# `authoring` from here loads the write layer - schema.py alone is 53KB - on a command
# whose whole promise is that it is cheap. `tests/test_query_listing.py` asserts the
# two maps agree wherever both speak, so the copy cannot drift silently.
#
# The trade: a Project filed outside `projects/` compiles into the record and does not
# appear here. That is the layout `bundle-spec.md` requires, `validate_bundle.py`
# reports a misfiled concept, and `authoring.common.item_ids` already reads `projects/`
# alone - so this listing agrees with the write layer it hands ids to.
SCOPES = {
    "projects": ("projects",),
    "roles": ("roles",),
    "orgs": ("organisations",),
    "education": ("education",),
    "skills": ("skills",),
    "bullets": ("projects",),
    "credentials": ("education",),
    "metrics": ("projects",),           # the bullets whose `metric:` cites a row
    "views": ("tailoring",),            # targets/, plus applications/ under --archive
    "postings": ("tailoring",),
    "questions": (),                    # one file; no walk at all
    "capabilities": ("projects",),      # the projects carrying each term
}


def _present(bundle, scope):
    """The subtrees of `scope` this bundle actually has - see `Reading.concepts`."""
    return tuple(one for one in scope
                 if os.path.isdir(os.path.join(bundle, *one.split("/"))))


class Noun:
    """One inventory: what it shows, what may narrow it, and what answers it."""

    __slots__ = ("name", "one", "many", "columns", "axes", "archive", "answer",
                 "tally", "refusals", "scope", "tailoring", "contains")

    def __init__(self, name, one, many, columns, axes, archive, answer, tally,
                 refusals, scope, tailoring, contains):
        self.name = name
        self.one = one                  # "project" - for a summary counting exactly 1
        self.many = many                # "projects"
        self.columns = columns
        self.axes = axes
        self.archive = archive          # whether the archive is a boundary for it
        self.answer = answer
        self.tally = tally
        # The subtrees this noun's concepts live in, and what to read under
        # `tailoring/`. Both are `walk.walk`'s arguments and both are measured
        # rather than guessed - see the module docstring.
        self.scope = scope
        self.tailoring = tailoring
        # The literals a file must hold before its YAML is worth parsing, or () for
        # "the type names themselves" - see `Reading.concepts`.
        self.contains = contains
        # `{axis: why not}` for a flag whose generic refusal would be untrue. Two
        # nouns need one: `credentials` prints a `status` column that is not
        # provenance, and every row of `capabilities` *is* a capability.
        self.refusals = refusals

    def counted(self, rows):
        return f"{len(rows)} {self.one if len(rows) == 1 else self.many}"


def answers(name, one, many, columns, axes=DEFAULT_AXES, archive=True, tally=None,
            refusals=None, tailoring="views", contains=()):
    """Register the function that answers one noun. The whole registration surface.

    The scope comes from `SCOPES[name]` rather than from a keyword here, and a noun
    missing from that table is a `KeyError` on import rather than a walk of the whole
    bundle - which is the failure scoping exists to prevent and the one that would
    never be noticed, because an unscoped walk answers correctly and slowly.
    """
    def register(answer):
        NOUNS[name] = Noun(name, one, many, columns, tuple(axes), archive, answer,
                           tally, dict(refusals or {}), SCOPES[name], tailoring,
                           tuple(contains))
        return answer
    return register


def _c(key, width=None, header=None):
    """One column. The header is the key as a person reads it, unless it is not.

    A width below the header's own length would leave the header wider than the
    column and every row under it out of line, because `render.table` pads to
    `min(want, width)` and never shortens a header - so the widths below are all at
    least their header's length, and the last column of each listing is `None` where
    the value is a sentence somebody is reading rather than a field they are scanning.
    """
    return render.Column(header or key.replace("_", " "), key, width)


# --- what a noun is handed -------------------------------------------------------

class Reading:
    """One question, and the two reads that answer all twelve of them.

    A noun's answer function is handed this and nothing else. Both reads are lazy and
    both are cached, so `list orgs` pays for the walk it needs and `list questions`
    pays for neither - it opens one file.
    """

    __slots__ = ("bundle", "args", "spec", "archive", "select", "missing", "_walked")

    def __init__(self, bundle, spec, args):
        self.bundle = str(bundle)
        self.args = args
        self.spec = spec
        self.archive = bool(getattr(args, "archive", False))
        self.select = filters.Metadata(args)
        # Files a noun went looking for and did not find. Reported as a note rather
        # than as an empty answer: "nothing matched" and "this bundle has no
        # achievements/metrics.md" are different facts, and only one of them is
        # something to do something about.
        self.missing = []
        self._walked = {}

    def concepts(self, *types):
        """Every concept of the named types, in walk order. One walk, cached.

        Narrowed three ways, all declared once per noun and none of them changing
        what is true:

        * **the subtrees** the noun's concepts live in, so the rest of the bundle is
          pruned rather than traversed and discarded;
        * **`tailoring`**, which decides whether `tailoring/targets/` is read whole
          or narrowed to the `*.view.md` files the compile reads;
        * **the literal pre-filter**, defaulting to *the type names themselves*. A
          file whose raw text does not contain the string `Job Posting` cannot
          declare `type: Job Posting`, however it is spaced or quoted, so the skip is
          sound rather than heuristic - and it is what stops `list postings` paying
          to YAML-parse three hundred gap assessments, views and applications to find
          a hundred postings. Reading a file is cheap; parsing its frontmatter is
          almost all of what a listing costs.

        A directory the bundle does not have is dropped rather than refused:
        `walk.walk` rejects a scope naming a missing directory, which is right for a
        `--scope` a person typed and wrong for one this module chose from a type - a
        bundle with no `organisations/` has no Organisation concepts, and `okf list
        orgs` must answer "nothing matched" rather than exit 2 over a directory
        nobody named.
        """
        key = tuple(types)
        if key not in self._walked:
            scope = _present(self.bundle, self.spec.scope)
            if self.spec.scope and not scope:
                self._walked[key] = []
            else:
                self._walked[key] = walk.by_type(
                    self.bundle, *types, archive=self.archive,
                    scope=scope or None, tailoring=self.spec.tailoring,
                    must_contain=self.spec.contains or types)
        return self._walked[key]

    def matching(self, *types):
        """The same, narrowed by the metadata filters the caller passed."""
        return [c for c in self.concepts(*types) if self.select.matches(c)]

    def with_ids(self, *types):
        """`(concept, every id it mints)` for each concept of these types.

        `ids.of()` and never `ids.index()`. The difference is one whole walk of the
        bundle: `index()` does its own, and a module that calls it on top of a walk it
        has already done pays twice - which `ids.py` records as the reason `of()`
        exists, having watched `okf list projects` come to cost 1.8 times the compile
        it was written to be cheaper than. Nothing here is filtered, because the claim
        nouns filter on the *claim's* provenance rather than the concept's.
        """
        for concept in self.concepts(*types):
            yield concept, ids.of(concept)

    def read(self, *parts):
        """One bundle file's text, or None - and a note saying it was not there.

        Unreadable is treated as absent, which is `walk.walk`'s rule and for its
        reason: `okf validate` is where a file this layer cannot open is a finding,
        and a listing that refused because of one would be unusable in the bundle
        that has it.
        """
        path = os.path.join(self.bundle, *parts)
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
        except (OSError, UnicodeDecodeError):
            self.missing.append("/".join(parts))
            return None


# --- values, read the way the record reads them ----------------------------------

def _one(value):
    """A frontmatter value as one stripped string. `None` and `2019` both survive."""
    return "" if value is None else str(value).strip().strip('"')


def _num(value):
    """A value as a number for sorting, or -1 - which sorts last, descending."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return -1


def _count(value):
    """How many entries a list-valued key holds. A key nobody wrote counts zero."""
    return len(value) if isinstance(value, (list, tuple)) else (1 if value else 0)


def _period(meta):
    """`2019-04 - 2021-12`, and `2022-01 - present` where it has not ended.

    An absent end with no `state: ongoing` prints `unknown` rather than nothing:
    `2019-04 - ` reads as a rendering bug, and the truthful answer is that nobody
    wrote down when it stopped. Precision is whatever was written, as
    `okf_compile.date` reads it - a bare year stays a year.
    """
    start, end = _one(meta.get("start")), _one(meta.get("end"))
    if not start and not end:
        return None
    if end:
        tail = end
    else:
        tail = "present" if _one(meta.get("state")).lower() == "ongoing" else "unknown"
    return f"{start or 'unknown'} - {tail}"


def _bullet_status(found):
    """A bullet's provenance, defaulted the way `okf_compile.bullets` defaults it.

    The compile reads a bullet with no `status:` as **inferred** -
    `fields.get("status") or "inferred"` - because anything authored during tailoring
    arrives unconfirmed and a view's `provenance_floor` is what stops it rendering.
    `ids.Located.status` falls back to the *concept's* status instead, which for a
    status-less bullet inside a `status: confirmed` project reports confirmed for a
    claim the renderer will withhold. That is the one number on this row somebody
    acts on, so it is read from the item's own field here and defaulted the
    compile's way.
    """
    return found.detail.get("status") or "inferred"


def _sorted(rows, *passes):
    """`rows` sorted by each key function in turn, last pass most significant.

    Python's sort is stable, so this is how a descending sort on a number can carry
    an ascending tie-break on a name without either being expressed as its own
    negation. Each caller reads bottom-up and says what the order means.
    """
    for key, reverse in passes:
        rows.sort(key=key, reverse=reverse)
    return rows


def _by(key):
    """Fold a row's value for an alphabetical tie-break."""
    return lambda row: _one(row.get(key)).lower()


# --- markdown a noun reads out of one file ---------------------------------------

# `okf_compile.metrics_table`'s own test for a table's separator row, so that a
# question table and a metrics table are read by the same rule.
def _cells(line):
    """A markdown table row as its cells, or None where the line is not one."""
    text = line.strip()
    if not text.startswith("|") or "---" in text[:8]:
        return None
    return [cell.strip() for cell in text.strip("|").split("|")]


def _sections(text):
    """`(line index, line, the heading it sits under)` for every line worth reading.

    `markup.HEADING` and `markup.scan` - the package's one heading pattern and its one
    fence toggle - so the vocabulary's themes and the open questions' sections are
    found by the same rule rather than by a second regex each. `markup.py`'s own
    docstring counted the fence toggle in three modules and the term pattern in five
    before it existed; a sixth idiom here would be the thing it was written to stop.

    Heading lines are not yielded, and neither is anything inside a fence: a fenced
    heading names no section and a fenced list item is somebody showing what the
    shape looks like.
    """
    section = None
    for index, line, fenced in markup.scan(text.split("\n")):
        if fenced:
            continue
        heading = markup.HEADING.match(line)
        if heading:
            section = heading.group(2).strip()
            continue
        yield index, line, section


# --- the twelve ------------------------------------------------------------------

def _located_row(found):
    """The three keys every row built from an id shares, plus the one warning.

    `frozen` is set only where it is true, so it stays out of `--json` for the
    ordinary case and the note that fires off it cannot be triggered by a `False`.
    Assembled here rather than in each of the four nouns that reads ids directly,
    because "where is this and may I edit it" is one answer.
    """
    row = {"id": found.id, "file": found.rel, "line": found.line}
    if found.frozen:
        row["frozen"] = True
    return row


def _of_kind(located, kind, claim=False):
    """The ids of one kind out of what `ids.of()` returned for one concept.

    `ids.CONCEPTS` and `ids.CLAIMS` both label a Certification Status `credential`,
    so the kind alone does not separate the concept from the entries inside it. A
    claim carries `in` - the stem it was found in - and a concept does not, which is
    the one distinction and is therefore made once, here.
    """
    return [found for found in located
            if found.kind == kind and ("in" in found.detail) == claim]


def _concept_rows(reading, ctype, kind):
    """`(concept, row)` for every concept of one type that passed the filters.

    The four keys every concept-level listing shares - the compiled id, the file, the
    title and the provenance - assembled once. `frozen` is set only where it is true,
    so it stays out of `--json` for the ordinary case and out of the frozen note's
    way when it is not.
    """
    for concept, located in reading.with_ids(ctype):
        if not reading.select.matches(concept):
            continue
        found = _of_kind(located, kind)
        row = {"id": found[0].id if found else None,
               "title": _one((concept.meta or {}).get("title")) or concept.stem,
               "status": concept.status,
               "file": concept.rel, "line": 1}
        if concept.frozen:
            row["frozen"] = True
        yield concept, row


@answers("projects", "project", "projects",
         columns=(_c("id", 30), _c("title", 34), _c("strength", 8), _c("recency", 7),
                  _c("seniority", 22), _c("role", 22), _c("capabilities", 34),
                  _c("status", 18)),
         axes=("status", "capability", "technology", "domain", "seniority", "strength",
               "recency"))
def projects(reading):
    """The evidence, strongest first - which is the order a tailoring run reads it in.

    Every selection key `bundle-spec.md` declares Project-only is a column here,
    because the answer to "why did the scorer not pick this one" is almost always a
    key nobody filled in, and it is visible as a `-` in a row rather than by opening
    the file.
    """
    rows = []
    for concept, row in _concept_rows(reading, "Project", "project"):
        meta = concept.meta or {}
        row.update({"strength": meta.get("strength"), "recency": meta.get("recency"),
                    "seniority": _one(meta.get("seniority")) or None,
                    "role": _one(meta.get("role")) or None,
                    "capabilities": filters.listed(meta, "capabilities"),
                    "technologies": filters.listed(meta, "technologies"),
                    "domains": filters.listed(meta, "domains")})
        rows.append(row)
    # Strongest first, then most recently touched, then alphabetical - the ranking
    # `score_projects.py` runs on, so the top of this listing is what a posting is
    # likely to be answered with. A project with no `strength:` sorts last rather
    # than first: an unscored project is not a flagship.
    return _sorted(rows, (_by("title"), False),
                   (lambda row: (_num(row["strength"]), _num(row["recency"])), True))


@answers("roles", "role", "roles",
         columns=(_c("id", 30), _c("title", 30), _c("org", 24), _c("period", 22),
                  _c("state", 7), _c("seniority", 22)),
         axes=("status", "seniority"))
def roles(reading):
    """The employment history, most recent first.

    `org` is the Organisation file's *stem*, which is what the key holds and what the
    compile joins on - printing the display name here would hide the one thing that
    can be wrong with it. `functional_title` is shown beside the title in parentheses
    the way the renderer shows it, because a role whose official title says nothing
    about the work is exactly the row somebody is scanning for.
    """
    rows = []
    for concept, row in _concept_rows(reading, "Role", "role"):
        meta = concept.meta or {}
        bridge = _one(meta.get("functional_title"))
        if bridge:
            row["title"] = f"{row['title']} ({bridge})"
        row.update({"org": _one(meta.get("organisation")
                                or meta.get("organization")) or None,
                    "period": _period(meta),
                    "state": _one(meta.get("state")) or None,
                    "seniority": _one(meta.get("seniority")) or None,
                    "start": _one(meta.get("start")) or None,
                    "change": _one(meta.get("change")) or None})
        rows.append(row)
    # Latest start first - the order a resume lists them and the order a promotion
    # reads as progression. A role with no `start:` sorts last; the compile refuses
    # it anyway, and putting it at the top would make the newest job look oldest.
    return _sorted(rows, (_by("title"), False), (_by("start"), True))


@answers("orgs", "organisation", "organisations",
         columns=(_c("id", 30), _c("title", 30), _c("relationship", 12),
                  _c("location", 28)))
def orgs(reading):
    """Who the work was for and who is being applied to, employers first.

    One file per company whether they worked there, applied there, or both - so
    `relationship` is the column that says which, and it leads the sort. The
    engagement id built from the Roles pointing here is carried in `--json` as
    `engagement`: it is the id a view selects, and it is not `org_<stem>`.
    """
    rows = []
    for concept, row in _concept_rows(reading, "Organisation", "organisation"):
        meta = concept.meta or {}
        engagement = _of_kind(ids.of(concept), "engagement")
        row.update({"relationship": _one(meta.get("relationship")) or None,
                    "location": _one(meta.get("location")) or None,
                    "engagement": engagement[0].id if engagement else None})
        rows.append(row)
    # Employers first, then both, then prospects, then alphabetically inside each -
    # the record before the pipeline, because that is the half of this file people
    # come to read. An unrecognised relationship sorts after the three named ones
    # rather than being silently grouped with one of them.
    known = ("employer", "both", "prospect")
    return _sorted(rows, (_by("title"), False),
                   (lambda row: (known.index(_one(row["relationship"]))
                                 if _one(row["relationship"]) in known else len(known)),
                    False))


@answers("education", "qualification", "qualifications",
         columns=(_c("id", 30), _c("title", 34), _c("period", 22), _c("status", 18)))
def education(reading):
    """Degrees, most recent first.

    `Education` concepts only. `education/` also holds the `Certification Status`
    concepts, and those are `list credentials` - one directory, two types, and the
    compile builds them into two different arrays.
    """
    rows = []
    for concept, row in _concept_rows(reading, "Education", "education"):
        meta = concept.meta or {}
        row.update({"period": _period(meta),
                    "institution": _one(meta.get("institution")) or None,
                    "end": _one(meta.get("end")) or _one(meta.get("start")) or None})
        rows.append(row)
    # Finished most recently first, falling back to when it started for a
    # qualification still in progress.
    return _sorted(rows, (_by("title"), False), (_by("end"), True))


@answers("skills", "skill", "skills",
         columns=(_c("id", 30), _c("name", 30), _c("category", 20), _c("aliases")))
def skills(reading):
    """The competency taxonomy, grouped by category.

    A skill's id is derived from its *name*, not its position, so inserting one above
    another moves nobody's id - and renaming one moves its own. That is why the id
    column is worth reading here: a view that selected `skill_dotnet` keeps selecting
    it, and a view that selected a skill somebody has since renamed does not.
    """
    rows = []
    for _, located in reading.with_ids("Skill Set"):
        for found in _of_kind(located, "skill", claim=True):
            # A `# Skills` entry carries no `status:` field, so a skill's provenance
            # is its Skill Set concept's - which is what `Located.status` already
            # resolves to here, and the only axis this noun can honestly narrow by.
            if reading.select.status and found.status != reading.select.status:
                continue
            row = _located_row(found)
            row.update({"name": found.name, "category": found.detail.get("category"),
                        "aliases": found.detail.get("aliases"),
                        "last_used": found.detail.get("last_used"),
                        "status": found.status, "in": found.detail.get("in")})
            rows.append(row)
    # Alphabetical within category, categories alphabetical - a taxonomy reads
    # grouped, and neither axis is a ranking.
    return _sorted(rows, (_by("name"), False), (_by("category"), False))


@answers("bullets", "bullet", "bullets",
         columns=(_c("id", 34), _c("project", 24), _c("status", 18), _c("metric", 30),
                  _c("text")))
def bullets(reading):
    """The resume lines the projects earned, and the ids a view may include.

    This is the noun with a live blocker behind it. `okf view include --ref` names a
    bullet id, `authoring.common.item_ids(bundle, "bullet")` is the set it validates
    against, and until this existed the only way to see one was to compile the bundle
    and read the achievements out of the record. The ids printed here come from
    `ids.index()`, which derives them through `authoring.body.derived_bullet_id` -
    the same function the write layer checks against - so what is printed is what
    `view include` accepts. `tests/test_query_listing.py` asserts the two sets are
    equal rather than trusting that they are.

    The sentence is the last column and is never truncated. It is the claim; a
    truncated claim is one somebody reads the wrong half of.
    """
    wanted = reading.select.status
    rows = []
    for _, located in reading.with_ids("Project"):
        for found in _of_kind(located, "bullet", claim=True):
            status = _bullet_status(found)
            if wanted and status != wanted:
                continue
            row = _located_row(found)
            row.update({"project": found.detail.get("in"), "status": status,
                        "metric": found.detail.get("metric"), "text": found.name,
                        "for": found.detail.get("for")})
            rows.append(row)
    # By project, then in the order the file lists them - which is the order they
    # render in and the order the ids number in. Not by status: an `inferred` bullet
    # is a legitimate state rather than a finding, and sorting them to the top would
    # make this listing read as the audit `okf list unconfirmed` is.
    return _sorted(rows, (lambda row: _num(row["line"]), False), (_by("project"), False))


@answers("credentials", "credential", "credentials",
         columns=(_c("id", 30), _c("name", 40), _c("issuer", 20), _c("issued", 10),
                  _c("status", 12)),
         axes=(),
         refusals={"status": "the `status` column here is the certification's own "
                             "currency - active, expired - and --status selects "
                             "provenance, which is a different fact wearing the same "
                             "word"})
def credentials(reading):
    """What is held, most recently issued first.

    Two shapes count, because `okf_compile.build_credentials` counts two: a `# Held`
    block with one entry per certification, and - for a concept about a single
    certification - an `- **Issuer:**` line in the body. A concept evidencing neither
    yields nothing at all, and that is the point of the type name: a
    `Certification Status` concept reports a *status*, and "none held" is a
    legitimate one. Listing it as a credential put "Certifications - none held" on a
    resume once.

    `status` here is the certification's own currency - `active`, `expired` - and not
    provenance, which is why this noun accepts no `--status`: one flag meaning two
    different things across two nouns is the drift `filters.py` exists to prevent.

    `ids.index()` mints the concept-level `cred_<stem>` whenever there is no `# Held`
    block, where the compile also requires the `- **Issuer:**` line. So the second
    shape is checked here with `okf_compile.labelled` - the compile's own reader -
    rather than taken on the index's word, and a "none held" concept prints no row.
    """
    rows = []
    for concept, located in reading.with_ids("Certification Status"):
        for found in _of_kind(located, "credential", claim=True):
            row = _located_row(found)
            row.update({"name": found.name, "issuer": found.detail.get("issuer"),
                        "issued": found.detail.get("issued"),
                        "expires": found.detail.get("expires"),
                        # An entry with no `status:` is read as active, as
                        # `build_credentials` reads it.
                        "status": found.detail.get("status") or "active",
                        "in": found.detail.get("in"), "provenance": found.status})
            rows.append(row)
        # The single-certification shape. `ids.of()` mints the concept-level id
        # whenever there is no `# Held` block; the compile also requires the
        # `- **Issuer:**` line, so its own reader is asked before a row is written.
        labelled = okf_compile.labelled(concept.body)
        for found in _of_kind(located, "credential"):
            if not labelled.get("issuer"):
                continue
            row = _located_row(found)
            row.update({"name": found.name, "issuer": labelled["issuer"],
                        "issued": labelled.get("issued"),
                        "expires": labelled.get("expires"),
                        "status": labelled.get("status") or "active",
                        "in": concept.stem, "provenance": concept.status})
            rows.append(row)
    # Most recently issued first - a certification's currency is the question being
    # asked of this listing, and an undated one sorts last rather than newest.
    return _sorted(rows, (_by("name"), False), (_by("issued"), True))


def _uncited(rows):
    """The count worth putting in the summary: numbers no bullet rests on."""
    idle = [row for row in rows if not row["cited"]]
    if not idle:
        return ()
    return (f"{len(idle)} cited by nothing",)


@answers("metrics", "metric", "metrics",
         columns=(_c("id", 30), _c("name", 34), _c("value", 30), _c("cited", 5)),
         axes=(), tally=_uncited,
         # Narrower than the type name: this noun wants the projects whose bullets
         # cite a number, and a project with no `metric:` anywhere in it cites none.
         # Sound for the same reason the default is - a file that does not contain
         # the string cannot hold the field.
         contains=("metric:",))
def metrics(reading):
    """The verified numbers, and how many bullets rest on each.

    The number lives in `achievements/metrics.md` once and a bullet names it rather
    than restating it, which is what stops a rewritten clause inflating it. The
    consequence nobody could see is the other direction: a row nothing names is a
    number somebody verified and no resume uses - either a bullet is missing or the
    row is stale, and both are worth knowing.

    The table is read by `okf_compile.metrics_table` whole, not re-parsed, because
    that function owns the one thing the count depends on: how a metric's *name*
    becomes the key a bullet's `metric:` field is matched against. A second parser
    here would disagree about a name with punctuation in it and the count would be
    silently zero.
    """
    try:
        table = okf_compile.metrics_table(reading.bundle)
    except OSError:
        table = {}
    if not table:
        reading.missing.append("achievements/metrics.md")
        return []

    # The same slug the compile matches on - `bullets()` does `slug(fields["metric"])`
    # against these keys - so a bullet naming a row this listing calls uncited is a
    # bullet the compile would refuse outright.
    #
    # `ids.claims()` rather than `ids.of()`: the count needs a bullet's `metric:`
    # field and not its id, and asking for the ids of every bullet in the bundle to
    # throw all of them away is the cost this noun cannot justify.
    cited = {}
    for concept in reading.concepts("Project"):
        for item, _, _ in ids.claims(concept, "bullet"):
            named = item.fields.get("metric")
            if named:
                key = okf_compile.slug(named)
                cited[key] = cited.get(key, 0) + 1

    rows = [{"id": row["id"], "name": row["label"], "value": row["value"],
             "cited": cited.get(key, 0), "project": row["project"],
             "source": row["source"], "file": "achievements/metrics.md"}
            for key, row in table.items()]
    # Most cited first, so the workhorse numbers lead and the ones nothing rests on
    # sink to the bottom, where they read as the gap they are.
    return _sorted(rows, (_by("name"), False),
                   (lambda row: row["cited"], True))


@answers("views", "view", "views",
         columns=(_c("id", 30), _c("target", 34), _c("provenance_floor", 18),
                  _c("includes", 8)))
def views(reading):
    """The selections a resume renders from.

    `target` is what the view answers. A view usually does not say: the posting is
    beside it under the same stem - `bundle-spec.md`'s rule for `tailoring/targets/`
    - so where no `target:` or `posting:` key names one, the companion
    `<stem>.posting.md` is looked for on disk and reported. A view with neither is a
    view nobody can trace to a job.

    `provenance_floor` is the guardrail that stops an unconfirmed bullet reaching a
    document, so a view showing `-` here is one that will render anything.
    """
    rows = []
    for _, located in reading.with_ids("View"):
        for found in _of_kind(located, "view"):
            if reading.select.status and found.status != reading.select.status:
                continue
            target = _one(found.detail.get("target")) or None
            beside = _companion(reading.bundle, found.rel, ".view.md", ".posting.md")
            if not target and beside:
                # The companion's stem rather than its path, so this column and the
                # first column of `list postings` are the same string and the two
                # listings can be read against each other. The path stays in --json
                # for a caller that wants to open it.
                target = os.path.basename(beside)[:-len(".posting.md")]
            row = _located_row(found)
            row.update({"title": found.name, "target": target, "target_file": beside,
                        "provenance_floor": found.detail.get("provenance_floor"),
                        "includes": found.detail.get("includes"),
                        "status": found.status})
            rows.append(row)
    # Alphabetical by id, which is deliberately not a ranking: a view is chosen by
    # the posting it answers, and there is no order in which one is better.
    return _sorted(rows, (_by("id"), False))


def _companion(bundle, rel, suffix, wanted):
    """The bundle-relative `<stem><wanted>` beside `rel`, where it exists.

    One function for both directions - a view looking for its posting and a posting
    looking for its gaps and its view - because the stem rule is one rule, and a
    second copy is how the two start disagreeing about what a companion is called.
    """
    base = rel[:-len(suffix)] if rel.endswith(suffix) else rel[:-3]
    found = base + wanted
    return found if os.path.exists(os.path.join(bundle, *found.split("/"))) else None


@answers("postings", "posting", "postings",
         columns=(_c("stem", 34), _c("company", 24), _c("role", 28),
                  _c("requirements", 12), _c("gaps", 5), _c("view", 5)),
         axes=("status", "seniority", "domain"), tailoring="all")
def postings(reading):
    """The jobs being answered, and whether each one has been worked through.

    The first column is the stem rather than an id, and that is not an omission: a
    `Job Posting` compiles to nothing - the record reads only `*.view.md` under
    `tailoring/` - so there is no compiled id to print and the stem is the handle.

    `gaps` and `view` are the two companions a posting is supposed to acquire:
    `<stem>.gaps.md` is the assessment of it against the record and `<stem>.view.md`
    is the selection that renders from it. A posting with neither is one nobody has
    started; one with gaps and no view is one somebody stopped halfway through. That
    pair is the whole reason to list postings rather than read the directory.
    """
    rows = []
    # This noun declares `tailoring="all"` above, because a posting is one of the two
    # files per target that the default read skips: the compile reads only `*.view.md`
    # under `tailoring/`, and `postings` is the one listing that wants the others.
    for concept in reading.matching("Job Posting"):
        meta = concept.meta or {}
        stem = concept.stem[:-len(".posting")] if concept.stem.endswith(".posting") \
            else concept.stem
        row = {"stem": stem,
               "company": _one(meta.get("company")) or None,
               "role": _one(meta.get("title")) or None,
               "requirements": _count(meta.get("requirements")),
               "gaps": _companion(reading.bundle, concept.rel, ".posting.md",
                                  ".gaps.md") is not None,
               "view": _companion(reading.bundle, concept.rel, ".posting.md",
                                  ".view.md") is not None,
               "seniority": _one(meta.get("seniority")) or None,
               "status": concept.status, "file": concept.rel, "line": 1}
        if concept.frozen:
            row["frozen"] = True
        rows.append(row)
    # Alphabetical by stem, which is also chronological for anything in the archive -
    # those stems begin with the submission date. Explicitly not a ranking: which
    # posting matters most is the scorer's answer, not this listing's.
    return _sorted(rows, (_by("stem"), False))


# The section whose rows are answered rather than open. Excluded wholesale: a bundle
# that files resolved questions rather than striking them keeps them under a heading,
# and `okf question resolve` removes the row entirely - so both shapes have to leave
# this listing, and neither should turn it into a to-do list of settled things.
RESOLVED = "resolved"

# The question table's columns, by what the header calls them. A file written by hand
# uses this shape; a file written by `okf question add` is a list of `- row` items with
# no header at all, and both are read below.
QUESTION_HEADERS = {"question": "question", "why it matters": "why", "why": "why",
                    "asked": "asked", "resolved": "resolved"}
QUESTION_KEYS = ("question", "why", "asked", "resolved")


@answers("questions", "open question", "open questions",
         columns=(_c("section", 18), _c("asked", 10), _c("question")),
         axes=(), archive=False)
def questions(reading):
    """What the resume is still waiting on - the unresolved ones only.

    `resume-generation/open-questions.md` is read by two mode files as their agenda,
    and it exists in two shapes in real bundles. `init_bundle` scaffolds `# Blocking`,
    `# Missing metrics` and `# Not yet explored`, and `okf question add` appends a
    Markdown list row under one of them - so the row's own text, link and all, is the
    only handle the file gives a question and is exactly what `question resolve
    --match` takes a substring of. Written by hand, the same file is a table under
    `# Open` and `# Resolved`. Both are parsed, because parsing only the documented
    one would silently report no questions in whichever bundle wrote the other.

    A question leaves this listing two ways: its section is `# Resolved`, or its own
    `Resolved` cell has been filled in. `okf question resolve` strikes the row
    instead, which needs no rule here.
    """
    raw = reading.read("resume-generation", "open-questions.md")
    if raw is None:
        return []

    # The body alone, and the file line it starts at. Frontmatter is skipped rather
    # than scanned: a YAML sequence there - `tags:` under two `- ` entries - is a
    # Markdown list item to any reader that does not know where the body begins, and
    # would be reported as two open questions nobody wrote. `walk.body_offset` is
    # what puts the reported line back on the file rather than on the body.
    _, text = okf_compile.read_frontmatter(raw)
    offset = walk.body_offset(raw, text)
    keys, at, rows = None, None, []
    for index, line, section in _sections(text):
        if section != at:
            # A new heading, so whatever header row the last section declared no
            # longer describes this one.
            keys, at = None, section
        if _one(section).lower().startswith(RESOLVED):
            continue
        cells = _cells(line)
        if cells:
            if _one(cells[0]).lower() == "question":
                keys = tuple(QUESTION_HEADERS.get(_one(cell).lower())
                             for cell in cells)
                continue
            row = dict(zip(keys or QUESTION_KEYS, cells))
            if _one(row.get("resolved")):
                continue
            question = _one(row.get("question"))
            if not question:
                continue
            rows.append({"question": question, "why": _one(row.get("why")) or None,
                         "asked": _one(row.get("asked")) or None, "section": section,
                         "file": "resume-generation/open-questions.md",
                         "line": offset + index + 1})
            continue
        item = markup.LIST_ITEM.match(line)
        if item:
            rows.append({"question": line[item.end():].strip(), "why": None,
                         "asked": None, "section": section,
                         "file": "resume-generation/open-questions.md",
                         "line": offset + index + 1})
    # File order, deliberately unsorted. `question add` appends, so the file is
    # oldest-first inside each section, and mode-gaps.md works the sections in the
    # order they are written - `# Blocking` first. Sorting this would reorder
    # somebody's agenda.
    return rows


def _vocabulary(rows):
    """Two counts worth a sentence: the terms nothing carries, and the through-lines."""
    idle = sum(1 for row in rows if not row["projects"])
    strong = sum(1 for row in rows if row["through_line"])
    out = []
    if idle:
        out.append(f"{idle} on no project")
    if strong:
        out.append(f"{strong} on {THROUGH_LINE} or more")
    return tuple(out)


@answers("capabilities", "capability", "capabilities",
         columns=(_c("term", 34), _c("theme", 20), _c("projects", 8),
                  _c("through_line", 12)),
         axes=(), tally=_vocabulary,
         refusals={"capability": "every row here is a capability, so there is nothing "
                                 "on one to compare a term against"})
def capabilities(reading):
    """The primary matching axis, and how much evidence each term actually has.

    `capabilities` compares as exact strings, so the vocabulary is the thing that
    keeps two spellings of one idea from splitting the graph - and the count beside
    each term is what says whether a term is a claim or an aspiration.
    `bundle-spec.md`: values on three or more projects are the ones safe to claim as
    a through-line in a summary. Counting them by hand across a dozen projects is how
    a summary comes to assert one that is on two.

    What counts as vocabulary is `authoring.common.vocabulary_terms` - Markdown list
    items in backticks, outside a fence, and nothing else. Reused rather than
    restated: `init_bundle` scaffolds this file with its examples *inside* a fence, so
    a fresh bundle yields no vocabulary and the gate leaves capabilities unchecked. A
    reader here that admitted the fenced examples would report a dozen terms nobody
    wrote and call every one of them unused.

    A term carried by a project and absent from the vocabulary is still listed, with
    no theme. It is a validation error - `validate_bundle.py` reports it - and hiding
    it here would make this listing disagree with the projects it is counting.
    """
    from ..authoring import common                        # noqa: PLC0415 - one caller

    # The whole file, frontmatter and all - which is what `validate_bundle.py` and
    # `archive.py` both hand it. A term is a backticked list item, and frontmatter
    # holds none, so the two readings cannot differ; passing the body instead would
    # be a third convention for one file.
    text = reading.read("framework", "capability-vocabulary.md")
    listed = common.vocabulary_terms(text) if text else set()

    # The theme each term is listed under. `listed` above is the authority on what a
    # term *is* and this pass only labels one - `vocabulary_terms` again, a line at a
    # time, so the rule is not restated and a fenced example still names no theme.
    themes = {}
    for _, line, theme in _sections(text or ""):
        for term in common.vocabulary_terms([line]):
            themes.setdefault(term, theme)

    carried = {}
    for concept in reading.concepts("Project"):
        for term in filters.listed(concept.meta, "capabilities"):
            carried[term] = carried.get(term, 0) + 1

    rows = []
    for term in sorted(set(listed) | set(carried)):
        count = carried.get(term, 0)
        rows.append({"term": term, "theme": themes.get(term),
                     "projects": count, "through_line": count >= THROUGH_LINE,
                     "in_vocabulary": term in listed})
    # Most evidenced first: the through-lines lead, and the terms nothing carries
    # sit at the bottom where they read as the gap they are.
    return _sorted(rows, (_by("term"), False), (lambda row: row["projects"], True))


# --- run -------------------------------------------------------------------------

ARCHIVE_SKIPPED = ("the frozen archive was not read - --archive includes "
                   "tailoring/applications/")
ARCHIVE_READ = ("--archive: the frozen copies beside sent applications are included "
                "below")
ARCHIVE_MOOT = ("--archive changes nothing here - this listing reads one file, and "
                "the archive holds no copy of it")

# The frozen warning is `render.FROZEN_NOTE` and not a sentence of this module's own.
# Four commands can surface an archived row, and this sentence is the only thing
# between a caller and editing the record of what was already posted - so four
# spellings of it means somebody learns it in one answer and does not recognise it in
# the next. `walk.Scope.frozen` is the other half: only the `.posting.md` /
# `.gaps.md` / `.view.md` companions are frozen, because an application's own
# `<stem>.md` is appended to for as long as the process is live.


def _refuse_unusable(spec, args):
    """A `filters.Bad` for every flag this noun cannot honestly apply.

    The alternative is to accept the flag and ignore it, which hands back every row
    and reads as though the filter ran. That is worse than an empty answer: somebody
    narrowed a listing, got it back unnarrowed, and has no way to tell.
    """
    if getattr(args, "type", None):
        raise filters.Bad(
            f"--type does not apply to `list {spec.name}` - the noun already names "
            f"the type\n"
            f"fix:  drop it, or `okf search <bundle> --type T` to select across "
            f"concept types")
    for axis in AXES:
        if not getattr(args, axis, None) or axis in spec.axes:
            continue
        usable = ", ".join(f"--{name}" for name in AXES if name in spec.axes)
        why = spec.refusals.get(axis, f"its rows carry no {axis}")
        raise filters.Bad(
            f"--{axis} does not apply to `list {spec.name}` - {why}\n"
            f"fix:  " + (f"`list {spec.name}` narrows by {usable}" if usable else
                         f"`list {spec.name}` takes no filters") +
            f". `okf search <bundle> --{axis} ...` searches every concept that "
            f"carries one")


def _notes(spec, reading, rows):
    """What the answer did not read. A boundary nobody can see is one nobody allows for.

    An empty listing with no note reads as "there is nothing there", and for eight of
    these nouns the archive alone is a directory the answer never opened.
    """
    out = []
    if spec.archive:
        out.append(ARCHIVE_READ if reading.archive else ARCHIVE_SKIPPED)
    elif reading.archive:
        # `--archive` was passed to a noun it cannot widen. Said rather than dropped,
        # for the reason a refused filter is refused: a flag that appeared to run and
        # did not is a boundary the caller now believes they have crossed.
        out.append(ARCHIVE_MOOT)
    # The subtree this noun reads, named out loud. `SCOPES` is what makes a listing
    # cheap and it is also a blindness: a Project filed in `work/` compiles and is not
    # listed here. `walk.py`'s own comment is that the failure mode of reading less is
    # silence - every check written about what was found still passes - so the cure is
    # not to widen the walk but to say where it looked. Somebody who filed a concept
    # somewhere else can then see why it is absent, instead of concluding it was lost.
    # `okf search --type Project` reads the whole bundle and is the way to find it.
    if spec.scope:
        out.append("read from " + ", ".join(f"{one}/" for one in spec.scope)
                   + " - a concept filed elsewhere compiles but is not listed here")
    for name in reading.missing:
        out.append(f"{name} is not in this bundle - so there is nothing to read")
    if any(row.get("frozen") for row in rows):
        out.append(render.FROZEN_NOTE)
    return out


def _summary(spec, rows, tally):
    """`12 bullets`, plus whatever the noun counted that a row cannot show.

    None where nothing matched, so `render.emit` prints its own "nothing matched" -
    which is the honest answer, and is not an error. A tally is a sentence and not a
    `--json` key: every count here is derivable from the rows themselves, and a
    second copy in the envelope is a second place for it to be wrong.
    """
    if not rows:
        return None
    counted = spec.counted(rows)
    return f"{counted} - {', '.join(tally)}" if tally else counted


def run(bundle, noun, args):
    """One listing, as a `render.Result`. Reads, never writes, never compiles."""
    spec = NOUNS.get(noun)
    if spec is None:
        # Unreachable through the CLI - `commands.NOUNS` is the parser's own choice
        # list - so this is a caller inside the package, and it gets the names rather
        # than a KeyError.
        raise ValueError(f"okf list has no noun {noun!r}\n"
                         f"fix:  one of {', '.join(sorted(NOUNS))}")
    _refuse_unusable(spec, args)
    reading = Reading(bundle, spec, args)
    rows = list(spec.answer(reading))
    tally = spec.tally(rows) if spec.tally else ()
    return render.Result(rows, columns=spec.columns,
                         summary=_summary(spec, rows, tally),
                         notes=_notes(spec, reading, rows))
