"""Everything in the bundle that still points at one thing.

`authoring.career.references()` has answered this question since the write layer was
built, and answered it for exactly one caller: `okf project rm` needs to know whether a
delete would leave a dangling reference, so it refuses while anything still points at
what it is about to remove. Nobody could *ask* it. The person deciding whether a
concept is safe to delete, whether a metric is still cited, whether a posting can be
tidied away, had one route to that answer - type the delete and read the refusal - and
that route works only for the four types that have a `rm`.

So this command exposes the question, and the rule it lives under is that it **does not
answer it twice**. For a Project, Role, Organisation or Education it calls
`career.references()` unchanged and parses the lines that come back. That parse is
ugly; a second implementation would be worse. Two readers of "what points at this" is
how `rm` comes to refuse a delete this command called safe - or, far worse, how this
command comes to permit one `rm` would have stopped. The same argument sends the claim
scan through `claims._selected()`, which is what `okf bullet rm` refuses on, and the
link and path readers through `career._link_targets()` and `career._resolves_to()`,
which are what `validate_bundle.py` reports a broken link on.

## What counts as a reference

Six shapes, and the target's kind only decides which of them are possible:

| Target | What can point at it |
|---|---|
| Project · Role · Organisation · Education | `career.references()` - whole |
| a claim (`ach_` `skill_` `cred_<n>`) | `claims._selected`, and a malformed `include[].ref` |
| a metric (`met_`) | a bullet whose `metric:` field names it |
| a posting, or any other whole concept | a markdown link, a `career.PATH_KEYS` path |
| a view (`view_`) | an application's `view_file:` path and its `view:` id |
| a narrative (`nar_`) | a view's `narrative:` |

A target with **nothing** pointing at it is the answer worth having, not a failure:
`okf refs` exits 0 and says so, and says which delete would therefore be permitted.
That sentence is what the command is for.

## The archive is read, by default, and that is deliberate

Every other command in this layer skips `tailoring/applications/` unless `--archive`
asks for it, because the compile skips it and because a frozen copy is a file nobody
may edit. This one reads it always, and the tension is genuine enough to write down.

An archived application is *where most references to a posting or a view live*. It
names the posting it answered, the assessment it answered it with, the view it
rendered from and the company's concept - four of the seven `PATH_KEYS` - and it is the
only concept in the bundle that names a view by id. `okf refs view_kestrel_staff`
answering "nothing points at this, deleting it would leave nothing dangling" while a
sent application points at it is not a narrow answer. It is a wrong one, and it is
wrong in the direction that loses somebody's record.

There is a harder argument too: `career.references()` walks the archive
unconditionally, and `claims._refuse_selected()` reads frozen views on purpose. If
this command skipped the archive by default it would disagree with the refusals it
exists to predict - and the disagreement would show up as `okf refs` saying a concept
is unreferenced and `okf org rm` refusing it, which is the one failure this file is
written to prevent.

What makes the decision safe is that admitting an archived row cannot mislead anyone
into editing one: every such row is marked FROZEN and says so. `--archive` is still
accepted, because `add_common()` puts it on every read verb and a flag that errored
here would be a flag whose meaning depended on the verb - it simply changes nothing,
and `Result.notes` says both halves of that out loud.

## The one hole, named

`walk.py` skips every `index.md`, always, and so does the scan below. A directory
index's rows are generated - `bookkeeping.py` writes them and `okf reindex` repairs
them - so a link in one is bookkeeping rather than a reference somebody wrote, and it
goes away by itself when the concept does. `career.references()` reads indexes and
skips only the target's own, so a career concept linked from *another* directory's
index is reported here through that function and would not be reported for a posting.
The asymmetry is worth knowing about and is not worth a second walk to remove.
"""

import os

from .. import okf_compile
from ..authoring import career, claims
from . import ids, render, walk

# The sentence `ids.show` prints over a frozen row, spelt the same way. There is no
# constant to share yet, and the two read commands in this layer describing an
# unwritable file differently would be worse than the duplicate.
FROZEN = "FROZEN - an archived copy beside a sent application; do not edit it"

# The frontmatter keys in other concepts that name something by its *compiled id*
# rather than by a path. `view:` on an Application names the view it was rendered
# from; `narrative:` on a View names the summary it prints. Neither is a path, so
# `career.PATH_KEYS` cannot see them, and neither is a link.
ID_KEYS = ("view", "narrative")

# `ids.engagements_of()` labels an organisation's second id `Engagement`, because that
# is the record entity the roles under it compile to, and locates it at the
# organisation's own file. The file is still the Organisation, so `okf refs
# eng_meridian_health` is the same question as `okf refs org_meridian_health` and has to
# give the same answer - `career.references()` already looks for both prefixes.
TYPE_FOR = {"Engagement": "Organisation"}

NOTE = (
    "note: the frozen archive is read here, unlike every other okf query - a sent\n"
    "      application is where most references to a posting or a view live. Rows\n"
    "      from it are marked FROZEN and may not be edited. --archive is accepted\n"
    "      and changes nothing."
)


class Subject:
    """What `okf refs` was asked about, in the terms the scans need.

    Four fields decide which references are even possible, and resolving the target
    does nothing but populate them: `spec` where the question is `career`'s to answer,
    `file` where the target is a whole concept a link or a relative path could name,
    `ids` where it has compiled ids a view could name, `metric_key` where it is a row
    of the metrics table. A reference kind added later fills one of these in rather
    than growing a scan of its own.
    """

    __slots__ = ("name", "kind", "rel", "stem", "file", "ids", "metric_key",
                 "spec", "concept", "rm")

    def __init__(self, name, kind, rel, file=None, ids=(), metric_key=None,
                 spec=None, concept=None, rm=None):
        self.name = name
        self.kind = kind
        self.rel = rel
        self.stem = os.path.basename(rel)[:-3] if rel.endswith(".md") else rel
        self.file = file
        self.ids = frozenset(ids)
        self.metric_key = metric_key
        self.spec = spec
        self.concept = concept
        # The command that would delete it, where one exists. `refs` is asked in order
        # to decide whether a delete is safe, so the answer names the delete.
        self.rm = rm


def _normal(path):
    """A path in the shape `career._resolves_to` compares against.

    `career.references()` normalises its target exactly this way. Comparing a
    differently-shaped path would make the path-key scan miss on one platform and
    not the other, which is the class of bug that only ever reproduces on somebody
    else's machine.
    """
    return os.path.normpath(os.path.abspath(str(path)))


def _files_named(bundle, stem):
    """Every file in the bundle with this stem, bundle-relative, in walk order.

    Nothing is read: a stem is a question about filenames, and answering it by
    filename is what lets `okf refs <bundle> care-platform` - the common call - resolve
    without paying for the id index at all. The directory rules come from
    `walk.Scope` rather than from a second list of what is not career record.

    Deliberately not `walk()`, and not only for the reads. `walk()` narrows
    `tailoring/targets/` to `*.view.md` by default, and a posting and a gap assessment
    are two of the five things this command is *asked about*. A stem lookup that
    inherited that narrowing would refuse `okf refs <bundle> acme-staff.posting` as an
    unknown id.
    """
    name = f"{stem}.md"
    if name == walk.INDEX:
        # `index` is not a stem this command resolves. Every directory has one, so the
        # answer would be arbitrary, and an index is generated bookkeeping rather than
        # a concept anything points at.
        return
    scope = walk.Scope(bundle, archive=True)
    for dirpath, dirnames, filenames in os.walk(scope.root):
        dirnames[:] = sorted(d for d in dirnames if scope.keep_directory(dirpath, d))
        if name in filenames:
            yield os.path.relpath(os.path.join(dirpath, name),
                                  scope.root).replace(os.sep, "/")


def _read(bundle, rel):
    """One named file as a `walk.Concept`, without walking the tree to find it.

    Built out of `walk`'s own pieces - `read_frontmatter`, `body_offset`,
    `Scope.frozen` - because the scan below and `ids.py` both read a `Concept`, and a
    second shape here would be a third opinion about what `offset` and `frozen` mean.
    """
    path = os.path.join(str(bundle), *rel.split("/"))
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise ids.Unknown(
            f"{rel}: this layer cannot read that file - {exc}\n"
            f"fix:  `okf validate` is where an unreadable concept is a finding") from exc
    meta, body = okf_compile.read_frontmatter(raw)
    return walk.Concept(stem=os.path.basename(rel)[:-3],
                        ctype=(meta or {}).get("type"), meta=meta, body=body, raw=raw,
                        path=path, rel=rel, directory=os.path.dirname(rel),
                        offset=walk.body_offset(raw, body),
                        frozen=walk.Scope(bundle, archive=True).frozen(rel))


def _names_a_file(located):
    """Whether an id names a whole concept, which is what a link can point at.

    `ids.of()` records the concept's own `type` in the detail of every file-level id
    and records `in` on every claim, so the two are told apart by what the derivation
    already wrote down rather than by a second list of which kinds are which - which
    matters, because `credential` is both the kind of a `cred_<stem>` concept and the
    kind of a `cred_<stem>_<n>` claim. A view carries neither and is named by its
    kind: a view is one file, always.
    """
    return "type" in located.detail or located.kind == "view"


def _metric_key(bundle, ident):
    """The metrics-table key this `met_` id was minted from.

    Read back out of `okf_compile.metrics_table()` rather than by stripping the
    prefix. That table is what decides what a metric is called, and
    `okf_compile.bullets()` matches a bullet's `metric:` against it with
    `okf_compile.slug`. Re-deriving either half here is how `okf refs met_x` and the
    compile come to disagree about which bullet rests on which number.
    """
    for key, row in okf_compile.metrics_table(str(bundle)).items():
        if row["id"] == ident:
            return key
    return None                                # pragma: no cover - resolve() minted it


def _from_file(concept):
    """A subject resolved from a bare file stem."""
    spec = career.BY_NAME.get(concept.type)
    if spec is not None:
        # Named by its compiled id rather than by the stem that was typed, so that
        # `okf refs care-platform` and `okf refs prj_care_platform` answer with the
        # same sentence as well as the same rows. `ident()` is the compile's own.
        name = okf_compile.ident(concept.meta or {}, concept.stem, spec.id_prefixes[0])
        return Subject(name, spec.noun, concept.rel, file=_normal(concept.path),
                       spec=spec, concept=concept,
                       rm=f"okf {spec.noun} rm --slug {concept.stem}")
    if concept.type == "View":
        # A view is named by id everywhere anything refers to it, so a stem is resolved
        # through to that id and both scans run. `ids._view_id` is the one derivation of
        # it - a declared `id:`, else `view_<slug(stem)>` - and a second copy here
        # would answer `okf refs` about a view no application had ever named.
        ident = ids._view_id(concept)
        return Subject(ident, "view", concept.rel, file=_normal(concept.path),
                       ids=(ident,), concept=concept)
    return Subject(concept.stem, str(concept.type or "file").lower(), concept.rel,
                   file=_normal(concept.path), concept=concept)


def _from_id(bundle, located):
    """A subject resolved from a compiled id."""
    declared = located.detail.get("type")
    spec = career.BY_NAME.get(TYPE_FOR.get(declared, declared))
    if spec is not None:
        concept = _read(bundle, located.rel)
        return Subject(located.id, spec.noun, located.rel, file=_normal(concept.path),
                       spec=spec, concept=concept,
                       rm=f"okf {spec.noun} rm --slug {concept.stem}")
    if located.kind == "metric":
        # A metric is a row of a table, not a file. A link to `achievements/metrics.md`
        # points at the table and at no one number in it, so the file scan is off and
        # the only reference is a citation.
        return Subject(located.id, "metric", located.rel,
                       metric_key=_metric_key(bundle, located.id))
    claim = claims.CLAIMS.get(located.kind) if "in" in located.detail else None
    remove = (f"okf {located.kind} rm {claim['flag']} {located.detail['in']} "
              f"--id {located.id}") if claim else None
    return Subject(located.id, located.kind, located.rel, ids=(located.id,), rm=remove,
                   file=(_normal(os.path.join(str(bundle), *located.rel.split("/")))
                         if _names_a_file(located) else None))


def _subject(bundle, target):
    """What `target` names - a stem first, then a compiled id.

    An unresolvable target raises `ids.Unknown`, whose refusal already names the near
    misses; `commands.py` turns it into exit 2. A typo is the overwhelmingly likely
    cause of one of these not resolving, and silence would send somebody looking for a
    concept they never wrote.
    """
    named = list(_files_named(bundle, target))
    if len(named) > 1:
        # Answering about one of them would be the wrong answer of exactly the shape
        # this command must not give: "nothing points at this, the delete is
        # permitted", about a file the caller did not mean.
        raise ids.Unknown(
            f"more than one file in {bundle} has the stem {target}\n"
            f"      {', '.join(named)}\n"
            f"fix:  pass the compiled id of the one you mean - `okf list {bundle} "
            f"projects` and its siblings print the ids that exist")
    if named:
        return _from_file(_read(bundle, named[0]))
    # `resolve()` hands back an index only where it had to build one, and this module
    # deliberately does not take it: a by-product a caller reaches for because it
    # happened to be lying around is the coupling that made every `refs` call pay for
    # the whole id table. The one branch that needs bullet ids asks for them itself.
    located, _index = ids.resolve(bundle, target, archive=True)
    return _from_id(bundle, located)


def _row(rel, reference, frozen=False, line=None):
    return {"file": rel, "line": line, "frozen": bool(frozen), "reference": reference}


def _deduped(rows):
    """Two identical references in one file are one reference.

    `career.references()` ends with `common.first_appearance` for the same reason:
    `achievements/metrics.md` links to the same project once per table row, and an
    answer that counted three of them reads as three things to remove.
    """
    seen, out = set(), []
    for row in rows:
        key = (row["file"], row["reference"])
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def _career_rows(bundle, subject):
    """`career.references()`, as rows.

    Called unchanged, and its lines parsed back apart rather than the function being
    forked - see the module docstring. The split is safe because a line is
    `<rel>: <what>` and `rel` is a bundle-relative posix path, which cannot contain
    `": "`, while `what` routinely does.
    """
    scope = walk.Scope(bundle, archive=True)
    rows = []
    for line in career.references(bundle, subject.spec, subject.concept.stem,
                                  subject.concept.path, subject.concept.meta or {}):
        rel, _, what = line.partition(": ")
        rows.append(_row(rel, what, frozen=scope.frozen(rel)))
    return rows


def _metric_rows(bundle, subject):
    """Every bullet whose `metric:` field cites this row of the metrics table.

    One walk of its own, narrowed to the concepts that can hold a bullet, with
    `ids.of()` doing the derivation - it is the entry point for a caller that is
    already walking, and it is what keeps every bullet id, line and field this
    module reports identical to the one `okf show` reports. `ids.index()` is that
    same function over a walk of its own, so asking it for the whole table would
    pay for every id in the bundle to answer a question about bullets.

    `Project` is the only type asked for because `build_projects` is the only reader
    of a `# Bullets` block. A `metric:` written under some other type's block is not
    a citation the record makes, and reporting one would say a number is still
    relied on when nothing relies on it.

    The pre-filter is `metric` without its colon, and that is deliberate rather than
    careless: `body.py` matches a field with optional whitespace before the colon, so
    `metric : x` is a citation and a literal carrying the colon would miss it. What
    is left is still sound and still skips every posting, view, role and organisation
    in the bundle.

    Both sides are compared through `okf_compile.slug` because that is what
    `okf_compile.bullets()` compares - a number written "Event propagation latency" in
    the table and "event propagation latency" in the bullet is one citation to the
    record, and has to be one here or the two disagree about which bullet may be cut.
    """
    rows = []
    for concept in walk.walk(bundle, archive=True, tailoring="all", typed_only=True,
                             types=("Project",), must_contain=("metric",)):
        for located in ids.of(concept):
            if located.kind != "bullet":
                continue
            cited = located.detail.get("metric")
            if cited and okf_compile.slug(cited) == subject.metric_key:
                rows.append(_row(located.rel, f"{located.id}: metric: {cited}",
                                 frozen=located.frozen, line=located.line))
    return rows


def _file_rows(concept, target):
    """Links and relative path keys in `concept` that resolve to `target`.

    `career._link_targets` and `career._resolves_to` are called rather than restated.
    The first is `validate_bundle.py`'s own link reader, fences and inline code
    stripped, so this command refuses over exactly the links that gate would report;
    the second is the only answer in the codebase to "does this relative path name
    that file", and a second one would be a second answer to the only question `refs`
    asks.

    `PATH_KEYS` is taken whole rather than narrowed to the two keys an application
    uses for a posting. A posting can equally be named by `snapshot_of:` or
    `superseded_by:`, and the constant is where that list is maintained.
    """
    text = concept.body if concept.meta is not None else concept.raw
    meta = concept.meta or {}
    rows = []
    for link in career._link_targets(text):
        if career._resolves_to(concept.path, link, target):
            rows.append(_row(concept.rel, f"a markdown link to {link}",
                             frozen=concept.frozen))
    for key in career.PATH_KEYS:
        value = meta.get(key)
        if value and career._resolves_to(concept.path, value, target):
            rows.append(_row(concept.rel, f"{key}: {value}", frozen=concept.frozen))
    return rows


def _id_rows(concept, wanted):
    """Every place `concept`'s frontmatter names one of these compiled ids.

    `claims._selected()` is what `okf bullet rm` refuses on - `include[].achievements`,
    `include[].skills` and a view's own `skills` - so it is asked here rather than
    re-read. A view that selects a bullet through one of those and a `refs` that could
    not see it would be `refs` calling a claim safe to cut that `rm` will not cut.

    `include[].ref` is checked separately and reported with its position, in the same
    words `career.references()` uses. `_selected` excludes it correctly - `ref` names
    an *owner*, an engagement or a project, and `urs/resolve.py` keys its selection by
    owner id - so a claim id written there is a malformed view rather than a second
    legitimate spelling. It is still reported, because it is still a mention of the id
    that a delete would strand, and because a view nobody can see is wrong about is a
    view nobody fixes: the row names the position, which is what somebody needs to
    move the id into `achievements:` where it belongs.
    """
    meta = concept.meta or {}
    rows = []
    for key in ID_KEYS:
        value = str(meta.get(key) or "")
        if value in wanted:
            rows.append(_row(concept.rel, f"{key}: {value}", frozen=concept.frozen))
    for n, entry in enumerate(meta.get("include") or (), 1):
        if isinstance(entry, dict) and str(entry.get("ref") or "") in wanted:
            rows.append(_row(concept.rel, f"include[{n}].ref: {entry['ref']}",
                             frozen=concept.frozen))
    for ident in claims._selected(meta):
        if ident in wanted:
            rows.append(_row(concept.rel, f"selected: {ident}", frozen=concept.frozen))
    return rows


def _scan(bundle, subject):
    """One walk, for every reference kind `career.references()` does not answer.

    `must_contain` is the pre-filter that makes this cheap, and it is sound rather
    than heuristic: a reference to a file spells that file's stem, because a relative
    path key and a markdown link both end in `<stem>.md`, and a reference to an id
    spells the id. A file holding none of those strings cannot hold a reference. It is
    the same trick, with the same measured saving, that `career.references()` carries.

    `tailoring="all"` is the one place this module pays for breadth on purpose.
    `walk()` defaults to "views" because a posting and a gap assessment are 200 files
    per hundred targets that the record does not read - but this command is not asking
    what the record reads, it is asking what a delete would break, and a posting
    carries `superseded_by:` and `snapshot_of:` pointing at another posting while a gap
    assessment carries links to the evidence it weighed. `career.references()` reads
    both, through its own walk over every `.md` in the bundle. Narrowing here would
    leave one command with two breadths - the career half seeing a reference the
    posting half cannot - and the pre-filter means the extra files are opened and
    string-searched rather than YAML-parsed, which is the cheap half of the cost the
    narrowing was measured to remove.
    """
    literals = set(subject.ids)
    if subject.file:
        literals.add(subject.stem)
    rows = []
    for concept in walk.walk(bundle, archive=True, tailoring="all",
                             must_contain=tuple(literals)):
        if subject.file and concept.rel == subject.rel:
            # A file does not reference itself, and deleting one takes its own links
            # with it - `career.references()` skips its target for the same reason.
            # Guarded on `file` rather than on `rel` alone, because a claim's `rel` is
            # the concept it lives in: that file is not the target and a reference to
            # the claim written in it would be a real one.
            continue
        if subject.file:
            rows.extend(_file_rows(concept, subject.file))
        if subject.ids:
            rows.extend(_id_rows(concept, subject.ids))
    return _deduped(rows)


def _summary(subject, rows):
    """What the answer means for a delete, which is why the question was asked."""
    if not rows:
        return (f"nothing in the bundle points at {subject.name} - "
                + (f"`{subject.rm}` would permit the delete" if subject.rm
                   else "deleting it would leave nothing dangling"))
    count = len(rows)
    return (f"{count} thing{'' if count == 1 else 's'} still "
            f"point{'s' if count == 1 else ''} at {subject.name} - "
            + (f"`{subject.rm}` refuses until each of them is gone" if subject.rm
               else "deleting it would leave each of them dangling"))


def _block(row):
    """One reference: where it is, whether it may be edited, and what it says."""
    lines = [f"  {row['file']}" + (f":{row['line']}" if row.get("line") else "")]
    if row.get("frozen"):
        lines.append(f"  {FROZEN}")
    lines.append(f"  {row['reference']}")
    return lines


def run(bundle, target, args):
    """Everything that still points at one id or one file stem.

    `args` is the layer's uniform third argument and nothing here reads it: the only
    flag on this verb that could change what is read is `--archive`, and the archive is
    read either way - see the module docstring, and the note the answer prints.
    """
    subject = _subject(bundle, target)
    if subject.spec is not None:
        rows = _career_rows(bundle, subject)
    elif subject.metric_key is not None:
        rows = _metric_rows(bundle, subject)
    else:
        rows = _scan(bundle, subject)
    return render.Result(rows, block=_block, summary=_summary(subject, rows),
                         notes=[NOTE],
                         extra={"target": subject.name, "kind": subject.kind,
                                "target_file": subject.rel})
