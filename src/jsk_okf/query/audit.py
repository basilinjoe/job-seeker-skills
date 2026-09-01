"""The three questions a whole-bundle read was for.

`okf list unconfirmed`, `okf list orphans` and `okf stats` are one file because they
are one reading of a bundle asked three things. `jsk-bundle-auditor.md` is specified
as *"reads every concept"* and `mode-gaps.md` sends a session to it for the same
reason: nothing could answer "what is still inferred?", "what does nothing point at?"
or "what is actually in here?" without opening every file and holding all of it at
once. That read costs a model its context and produces an answer nobody can check.
These three produce the same answer as rows.

**One survey, three answers.** `Survey` is the spine, and it is not tidiness. The
three questions overlap almost completely - every one of them needs the claims, their
provenance, and the concept each claim sits in - and three functions each doing their
own walk would be three chances to disagree about how many bullets a bundle holds.
`okf stats` saying twelve confirmed claims while `okf list unconfirmed` shows four of
sixteen is the failure, and it is invisible: both numbers look fine alone. So the
walk happens once per command, in one place, and each entry point is a question put
to it.

The ids come out of that same walk, and this module derives none: `ids.of()` for each
concept, `ids.engagements_of()` for the engagements the roles imply, and
`ids.metrics()` for the table - the three `ids.index()` is itself built from. An id
derived here that differed from the compile's by a character would send somebody to
edit the wrong claim, or print one `okf view include` then refuses. Calling `index()`
is the obvious spelling and the wrong one for a module that already holds the concepts
- `of()`'s docstring records what that cost a listing which did it: *"1.8 times the
compile it was written to be cheaper than"*. The walk is here
rather than inside `index()` because `Located` carries no frontmatter and a *count* of
a view's includes rather than its refs, and the capabilities, strengths, `role:` keys
and view selections are all frontmatter.

How much of `tailoring/` that walk reads is the one knob each entry point sets for
itself. `walk`'s default - the compile's - reads only `*.view.md` there, which is right
for `unconfirmed`: a posting's provenance is the advertisement's and not a claim about
anybody. `orphans` and `stats` both need what that narrowing hides, the first for the
postings and the second for the type counts, so both ask for `"all"`. Getting this
wrong is invisible in the worst way, and it happened here: with the default, the
posting check found nothing on every real bundle and passed.

**What the walk count costs, measured.** On a bundle of a hundred projects, a hundred
answered postings and a hundred filed applications - 735 files - against
`okf_compile.load` as 1.00:

                                    cost    read  parsed
    bare walk(tailoring="views")   ~1.0      235     235
    okf list unconfirmed           ~1.0      235     235   one walk, nothing else
    okf list orphans               ~1.8      435     435   one walk, tailoring/ too
    okf stats                      ~2.4      735     535   + the archive count
    okf_compile.census alone       ~1.6      435     435

The first line is the finding that bounds everything else: **a compile is one walk.**
`load()` is `concepts()` plus dictionary building, and the building is nearly free -
so no question that has to read every concept gets materially under a compile, and one
that claimed to would be reading fewer files than the compile reads. Per file these
are *cheaper* than the compile; they are slower only where they read files a compile
deliberately skips.

`stats` is the expensive one, and what is left of it is asked for. It was ~3.4 while it
called `okf_compile.census()` beside its own walk - two walks over the same 435 files
for a number the survey already had. It now counts types off that walk and
**`Survey.census()` is asserted to equal `okf_compile.census()`**, which is the
property that function exists for; read its docstring before touching the boundary,
because the test is the only thing holding the two together now. The remaining ~0.6 is
the application count, a walk pruned to `tailoring/applications/` and pre-filtered on a
literal, because how many applications a bundle holds is a fact only the archive has.

What the layer buys is not the whole-bundle question being fast. It is that the answer
is four rows rather than thirty kilobytes of concepts in a model's context, and that
the narrow questions - `okf show`, a scoped listing - read a directory instead of a
bundle.

## Where provenance comes from

`unconfirmed` exists to catch an `inferred` claim before it reaches a resume, so it may
not be one status behind the compile - and a claim's status is not always the field it
looks like. Three rules, none of them written here: `ids.claim_status` applies them,
because provenance belongs beside the id it is attached to.

  - **A bullet with no `status:` is `inferred`,** not its concept's status.
    `okf_compile.bullets()` defaults it that way, so a status-less bullet inside a
    `status: confirmed` project is inferred in the record - and reading it as confirmed
    would call a claim signed off that `provenance_floor: confirmed` then withholds.
  - **A `# Held` item's `status:` is validity, not provenance** - `active`, `expired`.
    Its provenance is the concept's. Reading validity as provenance puts a permanent
    row in this queue that confirming cannot clear.
  - **A `# Skills` item carries no provenance of its own.** `body.SKILL_KEYS` has no
    `status` key and `build_skills` emits none, so the Skill Set is what has to be
    confirmed and every skill in it follows.

This module had its own copy of all three, written when `ids` applied one fallback to
every kind. The copy is gone; what is left is a test per rule, asserted against a row
of this command's own output, so that a change to either module surfaces here rather
than quietly moving what the queue reports.

## Why `orphans` refuses to report a missing capability

The first thing a future contributor will want to add to `orphans` is the other half
of the capability check: a term a project carries that the vocabulary does not list.
Do not add it. `validate_bundle.py` already raises that as an **error** - *"capability
'x' is not in framework/capability-vocabulary.md"* - and it is an error because an
unlisted term silently breaks matching in the scorer, which compares exact strings.

A query that repeats a gate's finding teaches people the gate is optional. Two
commands reporting one problem means the one that is *only* a report is the one they
read, and it exits 0; the gate that exits 1 becomes the noisy duplicate. So `orphans`
reports the direction nothing else covers - a listed term no project carries - and
stays silent about the direction a gate owns. Every check in it earns its place the
same way: it is here because no gate says it.

## Nothing here is a finding

All three exit 0, and `unconfirmed` finding an inferred bullet is the temptation
`query/__init__.py` names and refuses. An inferred claim is a legitimate state - it is
what a draft looks like before its owner has read it - and a command that exited 1 on
one would read as a failed check, which is how somebody comes to clear the queue by
deleting rather than by asking. The judgement belongs to a view's `provenance_floor`,
which is a gate, and it is already made.
"""

import os

from .. import markup, okf_compile
from . import filters, ids, render, walk

# Provenance the record recognises, worst-first. This is the order rows come back in
# and it is `mode-gaps.md`'s, not a judgement made here: its priority list puts
# **inferred claims** above everything else a record audit can find, and
# `bundle-spec.md` says why - *inferred text is the dangerous kind. It reads well,
# which is exactly why it must never reach a resume before you agree with it.* A
# `needs-verification` claim is a known gap and reads as one; an inferred claim reads
# as a fact.
UNCONFIRMED = ("inferred", "needs-verification")

CONFIRMED = "confirmed"

# The `Located.kind`s whose status is a provenance claim about the person's record.
# Listed rather than derived, because the three that are absent are absent for
# reasons:
#
#   engagement - located at an Organisation's file, whose status it carries, so that
#                file already has a row. Two rows for one file reads as two findings,
#                which is why `walk.py` skips `index.md` as well.
#   view       - a view makes its claim with `provenance_floor`, which is a gate. Its
#                own `status:` is bookkeeping about the file, and reporting it would
#                put every working view in a tailoring-heavy bundle in the queue.
#   metric     - a row in `achievements/metrics.md` is a verified number by
#                construction; the table has no status column and `ids.metrics` carries
#                None for one.
CLAIM_KINDS = ("bullet", "skill", "credential", "project", "role", "organisation",
               "education", "narrative")

# The five things `orphans` looks for, in the order they cost you something: a project
# that reaches no employer, a written bullet no resume renders, a verified number
# nothing rests on, a vocabulary term nothing carries, a posting nothing answered.
ORPHAN_KINDS = ("project", "bullet", "metric", "capability", "posting")

# `framework/capability-vocabulary.md`, and the underscored spelling
# `validate_bundle.py` falls back to - in its order, which is
# `authoring.common.VOCABULARY_NAMES`' order too. A bundle written against the older
# name is still read by the gate, so it has to be read here.
#
# Read with `markup.terms`, which is what the gate calls and what
# `authoring.common.vocabulary_terms` delegates to: only list items outside a fence
# count. That matters rather than being pedantry - `init_bundle` scaffolds this file
# with its examples *inside* a fence, and a backtick regex of our own would report
# every illustrative term as an unused one. `markup` directly rather than through
# `authoring.common`, because `commands.py` states the rule: reaching into the write
# layer from here would make every read command load it, and `markup` imports nothing
# at all.
VOCABULARY = (("framework", "capability-vocabulary.md"),
              ("framework", "capability_vocabulary.md"))

# What a posting's stem carries and its companions do not. `.target` is the revision-2
# spelling of a frozen posting, kept because a bundle is never obliged to migrate.
POSTING_SUFFIXES = (".posting", ".target")

# The two files `bundle-spec.md` says sit beside a posting: the assessment of it
# against the record, and the view that renders from it.
COMPANIONS = (".gaps.md", ".view.md")

# `walk(must_contain=...)` pre-filters on this before paying for a YAML parse, which
# is what keeps the archive walk in `applications()` off the two hundred frozen
# postings and views sitting beside a hundred applications. Sound rather than
# heuristic, and for a reason worth stating: a concept whose parsed `type` is
# `Application` has the characters `Application` somewhere in its raw text, whatever
# quoting its author chose - so the literal cannot exclude a file the type check would
# have kept. `filters.prefilter` makes the same argument, and the failure it protects
# against is the only one a query must not have: quietly reading fewer files than it
# says it did.
APPLICATION_LITERAL = ("Application",)

# `bundle-spec.md`: *values appearing on three or more projects are the ones safe to
# claim as a through-line in a summary.* That sentence is the only reason the
# histogram is worth printing - a count nobody can act on is a count, and this one
# says which words a summary may use.
THROUGH_LINE = 3

# Bar width, so a term on forty projects does not wrap the terminal.
BAR = 24

ARCHIVE_NOTE = ("tailoring/applications/ was not read - --archive includes the sent "
                "applications and the copies frozen beside them")


def _stem(rel):
    """The file stem of a bundle-relative path. Not an id - see the module docstring."""
    return os.path.basename(rel)[:-3] if rel.endswith(".md") else os.path.basename(rel)


def _is_claim(located):
    """Whether an id names a claim inside a concept rather than the concept itself.

    `detail["in"]` is what `ids.of` puts on a `# Bullets`/`# Skills`/`# Held` item
    and on nothing else, which is the only way to tell a held certification -
    `cred_<stem>_1` - from the `cred_<stem>` that a Certification Status concept with
    no block mints. Both wear the kind `credential`, and counting one as the other
    would put the concepts/claims split in `okf stats` out by however many
    certifications a bundle holds.
    """
    return located.kind == "narrative" or "in" in located.detail


def _rank(status):
    """Where a status sorts. Anything the record does not recognise sorts last.

    An unrecognised value is reported rather than dropped - `validate_bundle.py` is
    what refuses `status: verified`, and a query that silently omitted the claim
    wearing it would hide the one file most in need of attention.
    """
    return UNCONFIRMED.index(status) if status in UNCONFIRMED else len(UNCONFIRMED)


class Survey:
    """One reading of a bundle, which all three answers are drawn from.

    Built per command and thrown away. Nothing is cached across calls, because the
    question these commands are asked most is asked *while a bundle is being edited* -
    which is the same reason nothing here compiles.
    """

    def __init__(self, bundle, archive=False, tailoring="views"):
        self.bundle = str(bundle)
        self.archive = bool(archive)
        # What to read under `tailoring/`. "views" for the two listings, which want
        # career record and the views that select from it; "all" for `stats`, whose
        # type counts have to see every concept - see `census()`. It is the most
        # expensive knob in the read layer and `walk.py` says why, so it is a decision
        # each entry point makes rather than a default this class picks.
        self.tailoring = tailoring

        # One walk, unnarrowed by type: the ids need `ids.TYPES` and the metadata
        # needs Project, Role, View and Job Posting, and `walk` parses a file's
        # frontmatter before it can filter on type anyway - so narrowing would save
        # nothing and would leave `by_rel` unable to answer for a concept a later
        # check asks about.
        self.concepts = list(walk.walk(self.bundle, archive=self.archive,
                                       tailoring=self.tailoring, typed_only=True))
        self.by_rel = {concept.rel: concept for concept in self.concepts}
        self.by_type = {}
        for concept in self.concepts:
            self.by_type.setdefault(concept.type, []).append(concept)

        # Every id the record would carry, out of the walk that already happened.
        # First writer wins, which is `ids.index()`'s rule and `build_views`' and
        # `build_skills`' before it: a duplicate id is skipped rather than shadowing
        # the earlier one.
        #
        # Three calls rather than one because an id has three sources, and `index()`
        # is exactly these three over a walk of its own: a concept mints its own,
        # `metrics_table` mints the table's, and an engagement is minted from the
        # *roles* that name a company rather than from the company - which is why an
        # organisation nothing points at has an `org_` id and no `eng_` id.
        orgs = {c.stem: c for c in self.by_type.get("Organisation", ())}
        self.located = {}
        for concept in self.concepts:
            for located in ids.of(concept):
                self.located.setdefault(located.id, located)
        for located in ids.engagements_of(self.by_type.get("Role", ()), orgs):
            self.located.setdefault(located.id, located)
        for located in ids.metrics(self.bundle):
            self.located.setdefault(located.id, located)

        # The three lookups the coverage checks need, built once rather than scanned
        # per claim: a bundle with four hundred bullets and forty organisations would
        # otherwise do sixteen thousand comparisons to answer one question.
        self.project_of = {loc.rel: loc.id for loc in self.located.values()
                           if loc.kind == "project"}
        self.engagement_of = {_stem(loc.rel): loc.id for loc in self.located.values()
                              if loc.kind == "engagement"}
        # role stem -> its organisation's stem, which is the hop `build_projects`
        # makes to turn a project's `role:` into the engagement it renders under.
        self.org_of_role = {}
        for concept in self.by_type.get("Role", ()):
            meta = concept.meta or {}
            org = meta.get("organisation") or meta.get("organization")
            if org:
                self.org_of_role[concept.stem] = str(org)

    # -- provenance -------------------------------------------------------------

    def provenance(self, located):
        """One id's provenance, as the record reads it - which is `Located.status`.

        This computed it here for a while, out of `Located.detail` and the owning
        concept, because `ids` applied one fallback to all three claim kinds and two of
        them wanted a different rule. `ids.claim_status` applies the compile's rule per
        kind now, so the two copies became one and this is the copy that went.

        Deleting it rather than keeping it as a cross-check was the right way round.
        The rule belongs beside the id it is attached to; a second implementation here
        would have to be kept in step by whoever next reads `okf_compile.bullets`, and
        the value it decides is the one `provenance_floor` gates a resume on. The
        agreement is asserted instead - `ProvenanceComesFromTheIdIndex` in
        `tests/test_query_audit.py` pins each of the three rules against a row of this
        command's own output, so a change to either module fails there rather than
        quietly moving what `okf list unconfirmed` reports.
        """
        if located.status:
            return str(located.status)
        # Unreachable through `CLAIM_KINDS`: only a metric has no status, and a metric
        # is not a claim. Falls back to the concept rather than to `confirmed`, because
        # an absent provenance has to make a claim *appear* in this queue rather than
        # vanish from it - `walk.Concept.status` defaults the same way and for the same
        # reason.
        concept = self.by_rel.get(located.rel)
        return concept.status if concept is not None else UNCONFIRMED[-1]

    def claims(self):
        """(Located, provenance, owning concept) for every provenance-bearing id."""
        for located in self.located.values():
            if located.kind not in CLAIM_KINDS:
                continue
            yield located, self.provenance(located), self.by_rel.get(located.rel)

    def mix(self):
        """The provenance mix, and how it splits between concepts and claims."""
        out = {status: 0 for status in (CONFIRMED,) + UNCONFIRMED}
        concepts = claims = 0
        for located, status, _ in self.claims():
            out[status] = out.get(status, 0) + 1
            if _is_claim(located):
                claims += 1
            else:
                concepts += 1
        return out, concepts, claims

    # -- what points at what ----------------------------------------------------

    def cited_metrics(self):
        """Every metric a bullet cites, in the slug space `metrics_table` keys on.

        Compared as slugs rather than as `met_` ids so that nothing here composes an
        id: `okf_compile.bullets()` resolves `metric: Event propagation latency` by
        `slug(...) in metrics`, and this is the same comparison against the same
        helper.
        """
        return {okf_compile.slug(str(loc.detail["metric"]))
                for loc in self.located.values()
                if loc.kind == "bullet" and loc.detail.get("metric")}

    def view_selection(self):
        """(every id a view names, every owner a view includes *without* narrowing).

        Two answers because `resolve.achievements_of` asks two questions. An include
        entry naming an owner - an engagement, a project - renders **every**
        achievement under it, so the owner's id is enough to reach a bullet nobody
        named. Unless that entry carries an `achievements` list, which narrows it to
        exactly those ids and is precisely how a tailored view says "this bullet and
        not that one".

        The view's own top-level `skills:` list is deliberately not read. It names
        skill claims and this check asks only about bullets, so folding it in would
        widen `named` with ids nothing here compares against.

        Reading the two as one is wrong in both directions and both directions matter.
        Treating every owner include as wholesale hides a bullet a view deliberately
        left out - and a bullet nothing renders is the one thing this check exists to
        find. Treating none of them as wholesale reports every bullet under an
        engagement a view included in full, which is a page of false findings against
        exactly the claims somebody just tailored.
        """
        named, wholesale = set(), set()
        for concept in self.by_type.get("View", ()):
            for entry in (concept.meta or {}).get("include") or ():
                if not isinstance(entry, dict):
                    if entry:
                        # A bare string is a ref with nothing narrowing it -
                        # `resolve` builds its selection only from dicts, so such an
                        # entry reaches `achievements_of` as no selection at all.
                        named.add(str(entry))
                        wholesale.add(str(entry))
                    continue
                chosen = entry.get("achievements") or ()
                if entry.get("ref"):
                    named.add(str(entry["ref"]))
                    if not chosen:
                        wholesale.add(str(entry["ref"]))
                for one in chosen:
                    named.add(str(one))
        return named, wholesale

    def covers(self, located):
        """The owner ids a view could name to reach a claim without naming the claim.

        A bullet's project, and the engagement that project's `role:` reaches - the
        hop `build_projects` makes. Only meaningful against the *wholesale* half of
        `view_selection`: naming an owner and then choosing between its bullets does
        not reach the ones it did not choose.
        """
        out = set()
        project = self.project_of.get(located.rel)
        if project:
            out.add(project)
        concept = self.by_rel.get(located.rel)
        role = str((concept.meta or {}).get("role") or "") if concept is not None else ""
        engagement = self.engagement_of.get(self.org_of_role.get(role, ""))
        if engagement:
            out.add(engagement)
        return out

    def vocabulary(self):
        """(the capability vocabulary, the file it came from), read as the gate reads it.

        Absent, the set is empty and the capability check reports nothing rather than
        reporting every term - the same fallback both gates make, and the same reason:
        a bundle scaffolded with its examples inside a fence yields no vocabulary, and
        a fresh bundle is not a bundle full of orphans.

        The path comes back with the terms rather than being assumed, because a bundle
        written against the underscored spelling would otherwise get rows pointing at
        `capability-vocabulary.md`, which is a file it does not have. A row whose `file`
        column names nothing is worse than no row.
        """
        for parts in VOCABULARY:
            rel = "/".join(parts)
            path = os.path.join(self.bundle, *parts)
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    return markup.terms(handle), rel
            except (OSError, UnicodeDecodeError):
                # `walk.py`'s rule: a file this layer cannot read is not a query's
                # business to fail on. `okf validate` is where that is a finding.
                return set(), rel
        return set(), "/".join(VOCABULARY[0])

    def capabilities(self):
        """term -> how many projects carry it.

        Projects only, matching `validate_bundle.py`, which counts the same way and
        prints the same through-lines. Counting a posting's requirements here would
        make a term look like a through-line because it was *asked for* three times.
        """
        counts = {}
        for concept in self.by_type.get("Project", ()):
            for term in filters.listed(concept.meta, "capabilities"):
                counts[term] = counts.get(term, 0) + 1
        return counts

    def postings(self):
        """Every `Job Posting` the bundle holds.

        A method rather than `by_type["Job Posting"]` at the call site, because that
        lookup is only right on a `tailoring="all"` survey and the wrongness is
        invisible: `walk`'s default reads only `*.view.md` under `tailoring/`, which is
        where every posting lives, so a narrow survey answers `[]` on every real bundle
        and the companion check silently never runs. This module shipped that bug once
        already. Guarded here, once, rather than remembered at each call site.

        It used to be a second walk, pruned to `tailoring/` and pre-filtered on a
        literal so the gap assessments and views were never parsed. That was measured
        against reading `tailoring/` whole in the main walk and the two came out a dead
        heat - 420ms against 419ms on the hundred-posting bundle, because the pruned
        walk reads a hundred more files and parses a hundred fewer. Given a tie the
        simpler shape wins: one walk, no second code path, and `orphans` now has the
        same shape as `stats`.
        """
        if self.tailoring != "all":
            raise ValueError(
                "Survey.postings() needs tailoring='all' - walk's default reads only "
                "*.view.md under tailoring/, which is where every posting lives")
        return sorted(self.by_type.get("Job Posting", ()), key=lambda c: c.rel)

    def missing_companions(self, concept):
        """The `.gaps.md` / `.view.md` names that are not beside this posting."""
        base = concept.stem
        for suffix in POSTING_SUFFIXES:
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
        directory = os.path.dirname(concept.path)
        return [base + ext for ext in COMPANIONS
                if not os.path.exists(os.path.join(directory, base + ext))]

    # -- counts -----------------------------------------------------------------

    def counted(self, kind):
        return sum(1 for loc in self.located.values() if loc.kind == kind)

    def census(self):
        """How many concepts of each type. **Must equal `okf_compile.census()`.**

        Counted off this survey's own walk rather than by calling that function, and
        the equality is the whole contract:
        `test_query_audit.py::Stats::test_the_type_counts_are_the_census` asserts these
        are its counts, and **that test is now the only thing holding the two
        together.** Anyone changing this walk's boundary has to keep it passing.

        Why it matters more than a count usually does. `census()` exists because a
        compiler that drops a whole type cannot be caught by any check written about
        the survivors - every one of those checks iterates a list that is empty, and
        passes. `views` was a hardcoded `[]` for months for exactly that reason. So a
        hand-rolled type count that quietly stopped agreeing would break the one
        property the number is for, and would break it silently.

        Reused whole until it was measured: on a bundle of a hundred answered postings
        `census()` parses 435 files where the compile's own walk parses 235, so calling
        it beside this survey made `okf stats` cost three times a full compile to
        produce a number this walk already had. Reusing the function bought the wording
        of a docstring; the assertion buys the property.

        `tailoring="all"` is required, and the archive is excluded whatever `--archive`
        said, because those two are exactly `concepts(root, tailoring="all")`'
        boundaries and this is `concepts()`' number.
        """
        if self.tailoring != "all":
            # A narrower walk would undercount by every posting and assessment in the
            # bundle and there would be nothing in the output to say so - which is the
            # failure `walk.py`'s comment on this knob warns about. Refused rather than
            # silently answered.
            raise ValueError(
                "Survey.census() needs tailoring='all' - okf_compile.census() walks "
                "tailoring/, and a survey that did not would undercount it silently")
        archived = "/".join(walk.ARCHIVE) + "/"
        out = {}
        for concept in self.concepts:
            if concept.rel.startswith(archived):
                continue
            out[concept.type] = out.get(concept.type, 0) + 1
        return out

    def applications(self):
        """How many applications have been filed.

        Counted from `tailoring/applications/` whichever way `--archive` was passed,
        by a walk narrowed to that directory when it was not. "How many have I sent"
        is the one question about a bundle whose answer lives entirely in the archive,
        and reporting 0 because the archive was skipped would be a lie rather than a
        boundary - `notes` says the difference.

        `must_contain` matters here rather than being a micro-optimisation: an archive
        of a hundred applications holds three hundred files, and two of every three
        are the frozen posting and view beside them. Pre-filtering skips their YAML
        entirely.
        """
        if self.archive:
            return len(self.by_type.get("Application", ()))
        scope = "/".join(walk.ARCHIVE)
        if not os.path.isdir(os.path.join(self.bundle, *walk.ARCHIVE)):
            return 0
        return sum(1 for _ in walk.walk(self.bundle, archive=True, scope=scope,
                                        must_contain=APPLICATION_LITERAL,
                                        types=("Application",)))

    def span(self):
        """Earliest role start to latest project recency, as the bundle wrote them.

        `loose_date` rather than `date`: it reads "July 2011", `2011-07` and a YAML
        date object alike and returns None for anything else, where `date` raises. A
        stats line is not the place a malformed date should end a run - `okf validate`
        is.
        """
        starts = [okf_compile.loose_date((c.meta or {}).get("start"))
                  for c in self.by_type.get("Role", ())]
        ends = [okf_compile.loose_date((c.meta or {}).get("recency"))
                for c in self.by_type.get("Project", ())]
        # Compared as strings, which is sound for ISO prefixes: `2019` sorts below
        # `2019-04` and both below `2020`, so the earliest and latest are right even
        # where two concepts wrote their dates to different precision.
        first = min([value for value in starts if value], default=None)
        last = max([value for value in ends if value], default=None)
        years = None
        if first and last:
            years = int(last[:4]) - int(first[:4])
        return {"from": first, "to": last, "years": years}


def _notes(survey, *extra):
    """What this answer did not look at. The archive leads, because it is the one
    boundary that makes an empty answer read as "there is nothing there"."""
    notes = [] if survey.archive else [ARCHIVE_NOTE]
    notes.extend(note for note in extra if note)
    return notes


# --- okf list unconfirmed -------------------------------------------------------

# What `unconfirmed` does not judge, said once. mode-gaps.md orders five bands and
# this command answers one of them: the other four are a person's reading of a record,
# not a property of it. Printed so that an empty answer is not read as "the record has
# been audited".
BANDS_NOTE = ("this is mode-gaps.md's provenance band only - blocking gaps, "
              "illegible titles and unexplored territory are a person's judgement")


def unconfirmed(bundle, args):
    """Every claim and concept whose provenance is not `confirmed`.

    Ordered inferred before needs-verification, then by the strength of the concept
    the claim sits in. Both halves come from `mode-gaps.md`'s priority list rather
    than from a judgement made here - it puts inferred claims above every other band
    and orders the band below it *"highest-strength projects first"* - so the queue
    this prints is the queue that file already tells a session to work.

    The metadata filters narrow it, and `--status` is answered by the *row's* own
    provenance rather than by its concept's. On any other listing those are the same
    value; here they are the whole point, and `--status inferred` meaning "in an
    inferred concept" would hide every inferred bullet in a confirmed project.
    """
    survey = Survey(bundle, archive=getattr(args, "archive", False))
    selection = filters.Metadata(args)
    wanted = selection.status
    selection.status = None

    ordered = []
    for located, status, concept in survey.claims():
        if status == CONFIRMED:
            continue
        if wanted and status != wanted:
            continue
        if selection and (concept is None or not selection.matches(concept)):
            continue
        strength = (concept.meta or {}).get("strength") if concept is not None else None
        try:
            weight = int(strength)
        except (TypeError, ValueError):
            weight = 0
        row = {"file": located.at, "id": located.id, "status": status,
               "kind": located.kind, "says": located.name, "strength": strength}
        if located.frozen:
            row["frozen"] = True
        ordered.append(((_rank(status), -weight, located.rel, located.line or 0), row))

    ordered.sort(key=lambda pair: pair[0])
    rows = [row for _, row in ordered]

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    if rows:
        parts = [f"{counts[status]} {status}" for status in UNCONFIRMED
                 if counts.get(status)]
        # Built as a list rather than appended to a joined string, because a bundle
        # whose only unconfirmed claims wear a status the record does not recognise
        # gives an empty first half - and `", 3 with a status..."` reads as a bug in
        # the command rather than as a finding about the bundle.
        other = sum(n for status, n in counts.items() if status not in UNCONFIRMED)
        if other:
            parts.append(f"{other} with a status the record does not recognise")
        summary = f"{len(rows)} unconfirmed - {', '.join(parts)}"
    else:
        summary = "nothing unconfirmed - every claim in the bundle is confirmed"

    # `render.FROZEN_NOTE` rather than a sentence of our own. Four commands can
    # surface an archived row, and this one is the only thing between a caller and
    # editing the record of what was already posted - a person who learns it in one
    # answer has to recognise it in the next. `walk.Scope.frozen` decides which files
    # it is true of, and it is narrower than "in the archive": an application's own
    # file is appended to for as long as the process is live.
    note = (render.FROZEN_NOTE
            if any(row.get("frozen") for row in rows) else None)

    return render.Result(
        rows,
        columns=(render.Column("file", "file", 44),
                 render.Column("id", "id", 41),
                 render.Column("status", "status", 18),
                 render.Column("kind", "kind", 12),
                 render.Column("what it says", "says")),
        summary=summary,
        notes=_notes(survey, BANDS_NOTE, note))


# --- okf list orphans -----------------------------------------------------------

# Why the bullet check stands down. Before a bundle's first tailoring run there are no
# views, so "no view includes it" is true of every bullet in it - and an answer that
# reported all of them would be a page of rows saying nothing except that nobody has
# tailored yet.
NO_VIEWS_NOTE = ("no views in the bundle, so no bullet was checked for inclusion - "
                 "before the first tailoring run every bullet would be reported")

FILTERS_REFUSED = (
    "okf list orphans takes no selection filters\n"
    "fix:  drop {flags}. Orphans is a question about the whole bundle - what nothing "
    "points at - and a narrowed answer reads as 'nothing is orphaned' when the "
    "answer is 'you did not ask about it'. `okf list <bundle> projects "
    "--capability X` is the listing that filters")


def orphans(bundle, args):
    """What nothing in the bundle points at, and only what no gate already reports.

    Five checks, and each is here because it is nobody else's: a capability the
    vocabulary lists that no project carries, a metric row no bullet cites, a bullet
    no view renders, a `Project` with no `role:` so it reaches no engagement, and a
    posting missing the companions `bundle-spec.md` says sit beside it.

    Frozen copies are never reported, even under `--archive`. An orphan in the archive
    is a finding nobody is permitted to clear - the copy is the record of what was
    already sent - and a row directing somebody there would be a row directing them to
    edit history. They still count as *references*: a frozen view that included a
    bullet is evidence that bullet reached a resume.
    """
    selection = filters.Metadata(args)
    if selection:
        flags = ", ".join(sorted(
            flag for flag, value in (("--type", selection.types),
                                     ("--status", selection.status),
                                     ("--capability", selection.capabilities),
                                     ("--technology", selection.technologies),
                                     ("--domain", selection.domains),
                                     ("--seniority", selection.seniority),
                                     ("--strength", selection.strength),
                                     ("--recency", selection.recency)) if value))
        raise filters.Bad(FILTERS_REFUSED.format(flags=flags))

    # `tailoring="all"`, because the posting check needs the postings and they live
    # exactly where `walk`'s default narrowing bites. Measured against a narrow walk
    # plus a pruned second one for them: a dead heat, so this is the one that has
    # fewer moving parts - `Survey.postings()` has the numbers.
    survey = Survey(bundle, archive=getattr(args, "archive", False), tailoring="all")
    rows = []

    def add(kind, name, file, nothing):
        rows.append({"kind": kind, "name": name, "file": file, "nothing": nothing})

    # A project with no `role:`. `build_projects` only attaches an engagement where
    # the key is set, so the work renders under no employer - and `validate_bundle.py`
    # checks a Project's five selection keys and not this one.
    for concept in survey.by_type.get("Project", ()):
        if concept.frozen or (concept.meta or {}).get("role"):
            continue
        add("project", survey.project_of.get(concept.rel) or concept.stem, concept.rel,
            "no role: key - it reaches no engagement, so nothing renders it under an "
            "employer")

    # A bullet no view names, and none of whose owners a view names either.
    if survey.by_type.get("View"):
        named, wholesale = survey.view_selection()
        for located in survey.located.values():
            if located.kind != "bullet" or located.frozen:
                continue
            if located.id in named or (survey.covers(located) & wholesale):
                continue
            add("bullet", located.id, located.at,
                "no view names it, and none includes what it sits in without "
                "choosing between the bullets")

    # A metric row no bullet cites. The number is verified and rests under nothing,
    # which is the shape of a claim that was softened away and left its evidence
    # behind.
    cited = survey.cited_metrics()
    for located in survey.located.values():
        if located.kind != "metric" or located.frozen:
            continue
        if okf_compile.slug(str(located.name)) in cited:
            continue
        add("metric", located.id, located.rel,
            f"no bullet cites it - `metric: {located.name}` is what cites one")

    # A vocabulary term no project carries. The other direction is
    # `validate_bundle.py`'s error and is deliberately absent - see the module
    # docstring.
    carried = survey.capabilities()
    in_vocabulary, vocabulary_file = survey.vocabulary()
    for term in sorted(in_vocabulary - set(carried)):
        add("capability", term, vocabulary_file, "no project carries it")

    # A posting with nothing beside it. The assessment and the view are what say what
    # a posting was answered with; a posting with neither is one nobody worked.
    for concept in survey.postings():
        if concept.frozen:
            continue
        missing = survey.missing_companions(concept)
        if missing:
            add("posting", concept.stem, concept.rel,
                "no " + ", no ".join(missing) + " beside it")

    rows.sort(key=lambda row: (ORPHAN_KINDS.index(row["kind"]), row["name"]))

    if rows:
        counts = {}
        for row in rows:
            counts[row["kind"]] = counts.get(row["kind"], 0) + 1
        summary = f"{len(rows)} orphaned - " + ", ".join(
            f"{counts[kind]} {kind}" for kind in ORPHAN_KINDS if counts.get(kind))
    else:
        summary = "nothing orphaned - everything in the bundle is pointed at"

    return render.Result(
        rows,
        columns=(render.Column("kind", "kind", 12),
                 render.Column("id/term", "name", 41),
                 render.Column("file", "file", 44),
                 render.Column("what does not point at it", "nothing")),
        summary=summary,
        notes=_notes(survey,
                     None if survey.by_type.get("View") else NO_VIEWS_NOTE))


# --- okf stats ------------------------------------------------------------------

CENSUS_NOTE = ("the type counts read tailoring/ and skip the archive - "
               "okf_compile.census()'s boundary, and asserted to equal its counts")

APPLICATIONS_NOTE = ("applications are counted from tailoring/applications/ either "
                     "way - nothing else in the archive was read")


def _histogram(counts):
    """The capability histogram, commonest first, through-lines marked."""
    return [{"term": term, "projects": counts[term],
             "through_line": counts[term] >= THROUGH_LINE}
            for term in sorted(counts, key=lambda t: (-counts[t], t))]


def _stanza(row, counted, histogram):
    """One section as a small stanza: its heading, its numbers, then its table."""
    lines = [f"  {str(row['section']).upper()}"]
    pairs = [(key, value) for key, value in row.items() if key != "section"]
    if pairs:
        width = max(len(key) for key, _ in pairs)
        # `or "-"` for the empty list: `render.cell` prints a blank for one, and a
        # blank beside a label reads as a value that failed to print rather than as
        # "none of these".
        lines.extend(f"    {key:<{width}}  {render.cell(value, None) or '-'}"
                     for key, value in pairs)
    if row["section"] == "concepts" and counted:
        lines.append("")
        width = max(len(name) for name in counted)
        lines.extend(f"    {name:<{width}}  {counted[name]:>3}" for name in
                     sorted(counted, key=lambda t: (-counted[t], t)))
    if row["section"] == "capabilities" and histogram:
        lines.append("")
        width = max(len(entry["term"]) for entry in histogram)
        for entry in histogram:
            mark = "   through-line" if entry["through_line"] else ""
            lines.append(f"    {entry['term']:<{width}}  {entry['projects']:>3}  "
                         f"{'#' * min(entry['projects'], BAR)}{mark}")
    return lines


def stats(bundle, args):
    """What the bundle holds, counted.

    One walk, at `tailoring="all"` so that the type counts see every concept -
    `Survey.census()` has the argument, and the short version is that those counts must
    equal `okf_compile.census()`'s and a test is what holds them to it. Everything a
    parser wants structured is in `Result.extra` - `census` and `capabilities` - rather
    than folded into a sentence, because the histogram is the one thing here somebody
    will want to act on programmatically.
    """
    # `tailoring="all"`, which is what makes this one walk rather than three: the
    # type counts need every concept under `tailoring/` and so does nothing else here,
    # so the survey reads them once and `census()` counts them off it.
    survey = Survey(bundle, archive=getattr(args, "archive", False), tailoring="all")
    counted = survey.census()
    mix, concepts, claims = survey.mix()
    histogram = _histogram(survey.capabilities())
    through = [entry["term"] for entry in histogram if entry["through_line"]]

    # The sections, in the order they answer "what is in here": how much, how
    # trustworthy, what of each kind, over what span, and which words a summary may
    # use. One row per section rather than one row for the lot, so `--json` carries
    # them apart and the human form gets a stanza each.
    rows = [
        {"section": "concepts", "concepts": sum(counted.values()),
         "types": len(counted)},
        {"section": "provenance", "concepts": concepts, "claims": claims, **mix},
        {"section": "record", "projects": survey.counted("project"),
         "bullets": survey.counted("bullet"), "skills": survey.counted("skill"),
         "metrics": survey.counted("metric"), "views": survey.counted("view"),
         # From the type counts, which are the authority for every other count on
         # this page. `survey.postings()` answers the same and merges in a posting
         # misfiled outside `tailoring/`; a number here that disagreed with the census
         # line six rows above it would be the worse outcome of the two. The census
         # excludes the archive, so a frozen posting is not counted even under
         # `--archive` - that is `concepts()`' boundary and the notes name it.
         "postings": counted.get("Job Posting", 0),
         "applications": survey.applications()},
        {"section": "span", **survey.span()},
        {"section": "capabilities", "terms": len(histogram),
         "through_lines": through},
    ]

    # Everything that is not confirmed, rather than the sum of the two statuses the
    # record recognises. A claim wearing `status: verified` is a row `okf list
    # unconfirmed` prints, so counting only `inferred` and `needs-verification` here
    # would have this line say "0 unconfirmed" about a bundle that command has two
    # findings in - which is the exact cross-command disagreement one survey exists to
    # prevent, and it would be invisible because both numbers read fine alone.
    unconfirmed_now = sum(mix.values()) - mix.get(CONFIRMED, 0)
    summary = (f"{sum(counted.values())} concepts in {len(counted)} types | "
               f"{mix.get(CONFIRMED, 0)} confirmed, {unconfirmed_now} unconfirmed | "
               f"{len(through)} through-line(s)")

    return render.Result(
        rows,
        block=lambda row: _stanza(row, counted, histogram),
        summary=summary,
        extra={"census": counted, "capabilities": histogram},
        notes=_notes(survey, CENSUS_NOTE, APPLICATIONS_NOTE))
