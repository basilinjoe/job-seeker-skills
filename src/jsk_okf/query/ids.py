"""Every id in a bundle, and the file it came from - without compiling.

`okf view include` names a compiled id. So does a gap assessment, and so does anyone
reading a record. Nothing exposed them: the only way to see
`ach_projects_care_platform_md_2` was to dump the whole record, which is a second of
work and thirty kilobytes to answer "what is this bullet called".

The rule this module lives under is that it **derives no id itself**. Every shape below
is composed out of the helper that already owns it:

| Id | Owned by |
|---|---|
| `prj_` `org_` `pos_` `edu_` `cred_` (concept) | `okf_compile.ident()` - which honours a declared `id:` |
| `eng_` `nar_` `view_` | `okf_compile.slug()`, at the f-strings in `build_engagements`, `build_narratives` and `build_views` |
| `met_` | `okf_compile.metrics_table()`, whole |
| `ach_` `cred_<n>` `skill_` | `authoring.body.derived_bullet_id` · `derived_credential_id` · `derived_skill_id` |

That is not fastidiousness. An id this layer derived differently from the compile would
send somebody to the wrong file with no way to notice - and worse, `okf list bullets`
would print an id `okf view include` then refuses. `tests/test_query.py` pins both
directions: every id in a compiled record resolves here, and the claim ids here are the
ones `authoring.common.item_ids` accepts.

**Reproducing the id is only half of it. The other half is minting none the record does
not carry**, and that half is where the bugs were. Two branches exist only to refuse an
id that would otherwise resolve: `cred_<stem>` for a concept that has a `# Held` block,
and `eng_<org>` for a company no role points at. Both are offered by the obvious
per-concept reading and neither exists in a compiled record, so both would have been
written into a view's `include[].ref` by somebody who trusted `okf show` - after which
the view renders nothing and no gate can say which id was the phantom.

One id here is deliberately not in the record and is not a phantom: a `met_` row that no
bullet cites. A view cannot reference a metric, so it cannot be misused that way, and
`okf list orphans` exists precisely to report those rows.

Blocks are read with `authoring.body.parse` rather than `okf_compile.blocks`, because
the write layer is what a caller acts against and `Block.claims()` is where the one
divergence between the two parsers - an entry with fields and no sentence, which
consumes no position - is already written down.
"""

import difflib

from .. import okf_compile
from ..authoring import body
from . import walk

# type -> (id prefix, kind). The kind is what a person is told they found; the prefix
# is what the compile mints.
#
# `eng_` is not here, though it also lands on an Organisation's file. An engagement is
# built from the *roles* that name a company, so it is minted by `engagements_of()`
# from those - see the comment in `of()`. An organisation nobody worked for has an
# `org_` id and no `eng_` id, and that asymmetry is the record's, not a gap here.
CONCEPTS = {
    "Project": ("prj", "project"),
    "Role": ("pos", "role"),
    "Organisation": ("org", "organisation"),
    "Education": ("edu", "education"),
    "Certification Status": ("cred", "credential"),
}

# type -> the claim block inside it. Type-driven, as the compile is: `build_projects`
# reads `# Bullets`, `build_skills` reads `# Skills`, `build_credentials` reads
# `# Held`, and each keys off the concept's type rather than its directory.
#
# `Certification Status` appears here *and* in CONCEPTS, and both label their ids
# `credential`, so **`Located.kind` alone cannot tell a `cred_<stem>` concept from a
# `cred_<stem>_<n>` claim.** The invariant that separates them is in `detail`: a concept
# carries `type`, a claim carries `in` (the stem it lives in). Written down because a
# caller found it by reading the code, which means the next one would too.
CLAIMS = {
    "Project": ("bullet", "bullet"),
    "Skill Set": ("skill", "skill"),
    "Certification Status": ("credential", "credential"),
}

TYPES = tuple(set(CONCEPTS) | set(CLAIMS) | {"View", "Positioning"})

# How many near misses a refusal offers. Three is enough to recognise a typo and few
# enough that the `fix:` line stays one sentence.
SUGGESTIONS = 3


class Located:
    """One id, and everything needed to point at what it names."""

    __slots__ = ("id", "kind", "name", "rel", "line", "status", "frozen", "detail")

    def __init__(self, ident, kind, name, rel, line=None, status=None, frozen=False,
                 detail=None):
        self.id = ident
        self.kind = kind
        self.name = name
        self.rel = rel
        self.line = line
        self.status = status
        self.frozen = frozen
        self.detail = detail or {}

    @property
    def at(self):
        return f"{self.rel}:{self.line}" if self.line else self.rel

    def as_dict(self):
        out = {"id": self.id, "kind": self.kind, "name": self.name, "file": self.rel,
               "line": self.line, "status": self.status}
        if self.frozen:
            out["frozen"] = True
        out.update(self.detail)
        return out


def _item_lines(block):
    """Each claim's 0-based line index within the body, in the block's own order.

    `Block` carries where its content starts and the raw lines of every item, so a
    position is preamble plus everything above - the only arithmetic that can put a
    reported line on the wrong claim, which is why it is done once here.

    Iterates `items` and yields only for `claims()`, because a fields-only entry
    occupies lines in the file and consumes no id position. Counting one way for the
    lines and the other way for the numbering is the whole point.
    """
    at = block.start + len(block.preamble)
    for item in block.items:
        if item.text:
            yield item, at
        at += len(item.lines)


def claims(concept, kind):
    """(item, id, body-line) for every claim of `kind` in this concept."""
    # Public because `search.py` needs a claim's *span* to say which claim a hit landed
    # in, and the span is `item.lines`, which only this generator hands back.
    spec = body.KINDS[kind]
    block = body.parse(concept.body, spec["heading"], spec["keys"])
    if block is None:
        return
    derive = {"bullet": lambda n: body.derived_bullet_id(concept.stem, n),
              "credential": lambda n: body.derived_credential_id(concept.stem, n),
              "skill": None}[kind]
    for n, (item, at) in enumerate(_item_lines(block), 1):
        if item.id:
            found = item.id
        elif derive is None:
            found = body.derived_skill_id(item.text)
        else:
            found = derive(n)
        yield item, found, at


def _view_id(concept):
    """A view declares its own id far more often than a concept does - it is URS
    frontmatter, so `id:` is part of the document rather than bookkeeping."""
    return str((concept.meta or {}).get("id") or f"view_{okf_compile.slug(concept.stem)}")


def _narratives(concept):
    """A Positioning concept's `# Summary ...` sections, by the id the compile mints.

    The heading is the label and the label is the id, so this reads headings rather
    than re-implementing `build_narratives`' quote extraction: what a caller wants
    from `okf show nar_keyword_dense` is the section, and the section is where the
    quote is.
    """
    import re                                             # noqa: PLC0415 - one caller
    for n, line in enumerate(concept.body.splitlines()):
        match = re.match(r"^#+\s*(Summary[^\n]*)$", line)
        if not match:
            continue
        head = match.group(1).strip()
        label = re.sub(r"^summary\s*(variant)?\s*", "", head, flags=re.I)
        ident = f"nar_{okf_compile.slug(label) or okf_compile.slug(concept.stem)}"
        yield ident, (label.strip(" -") or head), n + 1


# Provenance for one claim, by the rule the compile applies to that kind of claim.
# Three kinds, three rules, and a single fallback got two of them wrong.
#
# **A bullet with no `status` is `inferred`, not its concept's status.**
# `okf_compile.bullets` writes `fields.get("status") or "inferred"`. Falling back to the
# concept meant a status-less bullet inside a `status: confirmed` project read as
# confirmed - so `okf show` called a claim signed off while the renderer withheld it
# under `provenance_floor: confirmed`, which is the exact direction that must never be
# wrong.
#
# **A credential's own `status` is not provenance at all.** It is whether the
# certification is current - `active`, `expired` - and `build_credentials` carries a
# comment saying the two "must not be conflated". Reading it as provenance reported
# `active` where a caller expected one of the three provenance words. The concept's
# frontmatter is the provenance, which is what `provenance(meta)` uses there.
#
# **A skill has no provenance in the record.** `build_skills` emits none, so the
# concept's status is the only honest answer and is what a reader of `okf list skills`
# is being shown.
CLAIM_STATUS = {"bullet": "inferred", "skill": None, "credential": None}


def claim_status(kind, item, concept_status):
    fallback = CLAIM_STATUS[kind]
    if kind == "credential":
        return concept_status
    return item.fields.get("status") or fallback or concept_status


def single_credential(concept):
    """Whether a Certification Status concept compiles to `cred_<stem>`.

    `build_credentials` mints that id from **one** shape: no `# Held` block, *and* an
    `- **Issuer:**` line in the body. A concept recording a certification gap - "none
    held", or a list of ones somebody is considering - matches neither and compiles to no
    credential at all, which that function says out loud in its notes.

    Checking only for the absent `# Held` block was the third phantom of this kind. A
    concept saying nothing is held got an id that resolved in `okf show`, existed nowhere
    in the record, and was one copy-paste from a view's `include[].ref`.
    """
    if body.parse(concept.body, body.KINDS["credential"]["heading"],
                  body.KINDS["credential"]["keys"]):
        return False
    return bool(okf_compile.labelled(concept.body).get("issuer"))


def of(concept):
    """Every id one already-walked concept mints, as `Located` records.

    The entry point for a caller that is *already* walking. `index()` below is this
    function over a walk of its own, and a module that called `index()` on top of its
    own walk paid for two - which is how `okf list projects` came to cost 1.8 times
    the compile it was written to be cheaper than. A listing that has a concept in
    hand needs its ids, not the bundle's.

    Metrics are not here: `met_` ids come from a Markdown table rather than from a
    concept, so `index()` reads them separately through `metrics_table()`.
    """
    out = []
    put = out.append
    meta = concept.meta or {}
    title = str(meta.get("title") or concept.stem).strip('"')
    status = concept.status

    if concept.type in CONCEPTS:
        prefix, kind = CONCEPTS[concept.type]
        # A Certification Status concept mints `cred_<stem>` **only** where it has
        # no `# Held` block: `build_credentials` returns before the single-
        # certification branch as soon as the block yields anything. Registering it
        # anyway would have been the one mistake this module cannot make - an id
        # that resolves here, does not exist in the record, and would be written
        # into a view's `include[].ref` by somebody who trusted `okf show`. The
        # view then renders nothing and no gate says which id was the phantom.
        if concept.type != "Certification Status" or single_credential(concept):
            put(Located(okf_compile.ident(meta, concept.stem, prefix), kind, title,
                        concept.rel, 1, status, concept.frozen,
                        {"type": concept.type}))
        # `eng_` is deliberately NOT minted here, and the reason is measured. An
        # engagement is derived from the *roles*: `build_engagements` groups roles by
        # their `organisation:` key, so a company with no role pointing at it compiles
        # to no engagement at all - and a bundle holds one such company per employer
        # ever applied to, every `relationship: prospect`. Minting it per organisation
        # resolved `eng_kestrel_systems` against a record carrying no such entity,
        # which is the same phantom the `cred_` branch above refuses and reaches the
        # same place: a view's `include[].ref`, rendering nothing, with no gate able to
        # name which id was wrong. `engagements_of()` mints them from the roles.

    if concept.type in CLAIMS:
        kind, label = CLAIMS[concept.type]
        for item, ident, at in claims(concept, kind):
            put(Located(ident, label, item.text, concept.rel,
                        concept.line_of(at + 1),
                        claim_status(kind, item, status), concept.frozen,
                        {"in": concept.stem, **{k: v for k, v in item.fields.items()
                                                if k != "id"}}))

    if concept.type == "View":
        put(Located(_view_id(concept), "view", title, concept.rel, 1, status,
                    concept.frozen,
                    {"target": meta.get("target") or meta.get("posting"),
                     "provenance_floor": meta.get("provenance_floor"),
                     "includes": len(meta.get("include") or ())}))

    if concept.type == "Positioning":
        for ident, label, at in _narratives(concept):
            put(Located(ident, "narrative", label, concept.rel,
                        concept.line_of(at), status, concept.frozen))

    return out


def engagements_of(roles, orgs):
    """The `eng_` ids, minted the way `build_engagements` mints them.

    `roles` is an iterable of Role concepts and `orgs` maps an organisation stem to its
    concept. An engagement exists for an organisation **that a role points at**, and for
    no other: the compile groups roles by their `organisation:` key and reads the
    organisation only to name the result. So a company with no role - every
    `relationship: prospect`, which is one per employer ever applied to - has an
    `org_` id and no `eng_` id, and saying otherwise offers a reference the record
    cannot satisfy.

    Located at the organisation's file, because that is what the engagement names and
    what a person asking `okf show eng_x` wants to open.
    """
    out = []
    for role in roles:
        meta = role.meta or {}
        # Both spellings, as `build_projects` reads both, for bundles written before the
        # spelling settled.
        stem = meta.get("organisation") or meta.get("organization")
        if not stem:
            continue
        org = orgs.get(str(stem))
        if org is None:
            # A dangling relation. `okf_compile.load()` refuses the whole bundle on one
            # and `okf validate` reports it; a query names what it can and stays quiet
            # about what it cannot, rather than inventing a location for an
            # organisation that is not there.
            continue
        title = str((org.meta or {}).get("title") or org.stem).strip('"')
        out.append(Located(f"eng_{okf_compile.slug(org.stem)}", "engagement", title,
                           org.rel, 1, org.status, org.frozen, {"type": "Engagement"}))
    return out


def metrics(bundle):
    """The `met_` ids, which come from a table rather than from a concept.

    Separate from `of()` because `metrics_table()` parses `achievements/metrics.md`
    as a Markdown table, and reusing it whole is the only way this agrees with the
    compile on what a metric is called.
    """
    return [Located(row["id"], "metric", row["label"], "achievements/metrics.md",
                    None, None, False,
                    {"value": row["value"], "project": row["project"]})
            for row in okf_compile.metrics_table(str(bundle)).values()]


def index(bundle, archive=False, scope=None, types=None, tailoring="views"):
    """{id: Located} for every id the record would carry.

    One walk, and it is narrowable. A caller that wants the project ids should say
    so - `index(bundle, scope="projects", types=("Project",))` reads a hundred files
    where the unnarrowed call reads two hundred and seventeen. A caller that is
    already walking should not call this at all; `of()` is for them.

    `types` narrows within the id-bearing set rather than replacing it: asking for a
    type that mints no id would otherwise return an empty index and read as a bundle
    with nothing in it.
    """
    found = {}
    wanted = tuple(t for t in (types or TYPES) if t in TYPES) or TYPES

    def put(located):
        # First writer wins, matching `build_views` and `build_skills`, both of which
        # skip a duplicate id rather than letting the later one shadow the earlier.
        found.setdefault(located.id, located)

    roles, orgs = [], {}
    for concept in walk.walk(bundle, archive=archive, scope=scope, typed_only=True,
                             types=wanted, tailoring=tailoring):
        # Held rather than re-walked: an engagement needs a role and the organisation it
        # names, and those are two concepts in two directories. Collecting them on the
        # way past is what keeps this to one walk.
        if concept.type == "Role":
            roles.append(concept)
        elif concept.type == "Organisation":
            orgs[concept.stem] = concept
        for located in of(concept):
            put(located)

    for located in engagements_of(roles, orgs):
        put(located)

    # Skipped when no scope can reach the table, so a scoped index does not pay to
    # parse a file it was narrowed away from.
    reaches = (not scope) or any(
        str(one).split("/")[0] == "achievements"
        for one in ((scope,) if isinstance(scope, str) else scope))
    if reaches:
        for located in metrics(bundle):
            put(located)
    return found

class Unknown(Exception):
    """An id nothing in the bundle mints. Carries the sentence to print."""


def candidates(concept, wanted):
    """Whether this file could possibly mint `wanted`. A superset test, deliberately.

    The fast path behind `resolve()`, and the only thing that makes it safe is that it
    is allowed to say yes too often and never no too rarely. Whatever it admits is then
    put through `of()` - the real derivation - so a false positive costs one parse and a
    wrong answer is impossible. Nothing here is a second implementation of an id.

    Two ways a file can mint an id, and this tests for both:

    * **Declared.** The id is written in the file, so it is in the raw text.
    * **Derived.** The id is built out of the filename - `prj_<slug(stem)>`,
      `ach_<slug("projects/<stem>.md")>_<n>` - so the slugged stem is a substring of it.

    Two shapes it cannot see: `skill_` comes from the skill's own text and `nar_` from a
    heading, neither of which is in the filename. `resolve()` therefore falls back to
    the full index rather than reporting those missing, which it must do anyway to
    offer near misses on a typo.
    """
    stem_slug = okf_compile.slug(concept.stem)
    if stem_slug and stem_slug in wanted:
        return True
    path_slug = okf_compile.slug(f"{concept.directory}/{concept.stem}.md"
                                 if concept.directory else f"{concept.stem}.md")
    if path_slug and path_slug in wanted:
        return True
    return wanted in concept.raw


def declares(bundle, wanted, archive=False):
    """A concept that *declares* this id, or None. Parses no YAML it does not have to.

    Only the declared case: a derived id is built out of a filename and is not in the
    file, so this cannot see one and is not asked to. It exists so `resolve()` can try
    the free metrics table first without giving up the rule that a concept outranks it -
    see the comment there for why that rule is only reachable by declaration.
    """
    for concept in walk.walk(bundle, archive=archive, typed_only=True, types=TYPES,
                             tailoring="all", must_contain=(wanted,)):
        for located in of(concept):
            if located.id == wanted:
                return located
    return None


def resolve(bundle, wanted, archive=False):
    """One id, or an `Unknown` naming the near misses.

    A typo is the overwhelmingly likely cause - these ids are long, derived and typed
    from memory - so the refusal offers what it nearly matched. Silence would send
    somebody looking for a concept they never wrote.

    The hit is looked for before the index is built. `index()` parses the YAML of every
    concept in the bundle, which on a 235-file bundle is 569ms against the compile's
    549ms - so `okf show`, the cheap way to answer "what is this id", cost what the
    compile it replaces costs. Skipping the parse for files that cannot mint the id
    takes the same walk to 122ms, because the parse is five sixths of it.

    The full index is still built on a miss, and that is not a fallback bolted on: a
    miss is exactly when the near misses are needed, so the expensive path runs only
    when its expensive product is wanted.

    Returns `(located, index_or_None)`. The second value is None on the fast path -
    a caller that wants the whole index should ask `index()` for it rather than relying
    on a by-product, and `refs` and `show` both only ever wanted the first.
    """
    # The metrics table is one file and one parse - free next to the walk below, so it
    # is tried first. What that would cost if done naively is *precedence*: `index()`
    # registers concepts before metrics and `put` uses `setdefault`, so a concept
    # declaring `id: met_x` beats the table there, and a `resolve()` that answered
    # differently would make `okf show` disagree with `okf list` about the same id.
    #
    # `declares()` buys that precedence back for 38ms instead of 199ms, and it is sound
    # rather than a near-enough: the only way a *concept* can mint a `met_`-prefixed id
    # is to declare one, because every prefix `of()` derives comes from CONCEPTS, CLAIMS,
    # `view_`, `nar_` or `eng_` and none of those is `met_`. A declared id is written in
    # the file, so a literal-only walk - which skips the YAML parse, five sixths of the
    # cost - cannot miss it.
    for located in metrics(bundle):
        if located.id == wanted:
            overriding = declares(bundle, wanted, archive=archive)
            return (overriding or located), None

    for concept in walk.walk(bundle, archive=archive, typed_only=True, types=TYPES,
                             tailoring="all"):
        if not candidates(concept, wanted):
            continue
        for located in of(concept):
            if located.id == wanted:
                return located, None

    found = index(bundle, archive=archive, tailoring="all")
    if wanted in found:
        # Reached by a `skill_` or `nar_` id, whose shape the filename cannot predict,
        # and by an `eng_` id, which is minted from the roles rather than from any one
        # file. Not a failure of the fast path - a case it correctly declines to guess.
        return found[wanted], found
    near = difflib.get_close_matches(wanted, list(found), n=SUGGESTIONS, cutoff=0.6)
    fix = (f"fix:  did you mean {', '.join(near)}?" if near else
           f"fix:  `okf list {bundle} projects` and its siblings print the ids that "
           f"exist; `okf search` finds one by what it says")
    extra = "" if archive else ("\n      the frozen archive was not read - "
                                "--archive includes it")
    raise Unknown(f"no such id in {bundle}: {wanted}{extra}\n{fix}")


# --- okf show -------------------------------------------------------------------

# What a located id is worth printing about itself, beyond where it is. Ordered, and
# short: `show` answers "what is this and where do I read it", and a caller who wants
# the whole concept has just been handed the path to open.
DETAIL = ("type", "in", "status", "metric", "for", "issuer", "issued", "expires",
          "category", "aliases", "value", "project", "target", "provenance_floor",
          "includes")


def show(bundle, args):
    """One id: what it names, where it is, and what the file says about it."""
    from . import render                                  # noqa: PLC0415 - one caller

    found, _ = resolve(bundle, args.id, archive=getattr(args, "archive", False))
    row = found.as_dict()

    def block(entry):
        lines = [f"  {entry['id']}   {entry['kind']}"]
        if entry.get("frozen"):
            # The one thing about a located id that changes what a caller may do with
            # it. A frozen copy is the record of what was already sent; somebody
            # directed here to fix a sentence would be editing history.
            lines.append(f"  {render.FROZEN}")
        lines.append(f"  {entry['file']}" + (f":{entry['line']}" if entry.get("line")
                                             else ""))
        if entry.get("name"):
            lines.append("")
            lines.append(f"  {entry['name']}")
        shown = [(key, entry[key]) for key in DETAIL
                 if entry.get(key) not in (None, "", [], ())]
        if shown:
            lines.append("")
            width = max(len(key) for key, _ in shown)
            lines.extend(f"  {key:<{width}}  {render.cell(value, None)}"
                         for key, value in shown)
        return lines

    return render.Result([row], block=block)
