"""The artefacts a tailoring run writes: the posting, the assessment, the view.

Three files share a stem and sit together in `tailoring/targets/` -
`<slug>.posting.md`, `<slug>.gaps.md`, `<slug>.view.md`. That is not a naming
convention, it is a rule with a gate behind it: validate_bundle.py:311 makes a
`.gaps.md` or a `.view.md` with no `.posting.md` beside it a hard **error**, so a
command here that wrote one without the other would produce a bundle that fails
its own check. Both verbs that write a companion therefore refuse on the missing
posting before they decide anything else.

The view is the load-bearing one. A `.view.md` is an OKF concept whose
frontmatter *is* a URS view: okf_compile.build_views() strips the bundle's own
bookkeeping (CONCEPT_KEYS) and passes every remaining key through untranslated,
and validate_urs.py **fails any key it does not know**. So a misspelt key here is
not a typo that degrades gracefully - it is a permanent record-gate failure on
every run from the day it is written, and `provenance_floor` misspelt is a view
with no floor at all. That is what makes schema.TYPES["View"] load-bearing: it is
the write-time copy of validate_urs.VIEW_KEYS, and this module never invents a
key it does not name.

Nothing here validates a value or formats one. schema.py judges, concept.py
formats, and what is left for this layer is the class of rule that needs the
bundle on disk: does the posting exist, is that achievement id real, is that
capability in the vocabulary, does this stem already have a predecessor.
"""

import os

from . import body, common, concept, schema, stage

# --- where the three files sit ---------------------------------------------------

# The suffix each of the three wears. validate_bundle.TARGET_COMPANIONS is this
# same tuple read the other way round - it splits a filename on these to recover
# the stem it then demands a posting for - so a fourth spelling here would write a
# file that gate cannot pair with anything.
SUFFIXES = {
    "Job Posting": ".posting.md",
    "Gap Assessment": ".gaps.md",
    "View": ".view.md",
}


def target_path(bundle, type_name, stem):
    """Where the `<stem>` file of this type sits, suffix and all."""
    return common.path_of(bundle, type_name, stem, SUFFIXES[type_name])


def filename(type_name, stem):
    """Its name alone - what an index row links to, and what a log row names."""
    return f"{stem}{SUFFIXES[type_name]}"


def relative(type_name, stem):
    """Its path from the bundle root, for a log row a person reads."""
    return f"{common.directory_of(type_name)}/{filename(type_name, stem)}"


# --- what a `--set` may not name ------------------------------------------------

# The keys each verb writes itself, mapped to the flag that writes them, or to
# None where the command stamps the key. common.extension_keys refuses a `--set`
# naming one: two sources for a single key is two answers to one question, and
# which wins would be decided by dict ordering rather than by anything a person
# could predict.
FLAG_FOR = {
    "Job Posting": {
        "title": "--title",
        "description": "--description",
        "company": "--company",
        "url": "--url",
        "seniority": "--seniority",
        "domains": "--domain",
        "status": "--status",
        "timestamp": None,
        "requirements": "--value on `okf posting requirement add`",
    },
    "Gap Assessment": {
        "title": "--title",
        "description": "--description",
        "posting": "--posting",
        "assessed": "--assessed",
        "fit": "--fit",
        "status": "--status",
        "timestamp": None,
    },
    "View": {
        "description": "--description",
        "label": "--label",
        "format_profile": "--format-profile",
        "region_profile": "--region-profile",
        "locale": "--locale",
        "narrative": "--narrative",
        "redact": "--redact",
        "provenance_floor": "--provenance-floor",
        "budget": "--pages / --ats-max-pages",
        "status": "--status",
        "title": None,
        "id": None,
        "target": None,
        "include": None,
        "timestamp": None,
        "x": None,
    },
}

# Every other key schema.TYPES["View"] models: `sections`, `skills`, `tags`,
# `resource`, `frozen`, `frozen_date`, `superseded_by`. Derived from the schema
# rather than listed, so a view key added there cannot quietly become writable
# here as an extension.
#
# They need their own refusal because `--set` on a view writes under `x` - see
# _view_extensions - so one of these falling through would land in `x.sections`,
# where nothing reads it and no gate reports it. A silent no-op is the worst of
# the three possible outcomes.
VIEW_KEYS_WITHOUT_A_FLAG = frozenset(
    key.name for key in schema.TYPES["View"]) - frozenset(FLAG_FOR["View"])

# The length at which validate_urs.py:256 calls an unknown view key's value free
# text. Borrowed rather than chosen, because the gate's number is the one that
# decides whether a view passes - but applied only to a value that also contains
# whitespace: a URL, a profile token and an id are all routinely longer than this
# and none of them is prose. What view-format.md forbids is *content text*.
CONTENT_TEXT = 40


def _view_extensions(pairs):
    """`--set key=value` on a view: under `x`, and never content text.

    validate_urs.py names `x` as where a view's extensions belong and checks
    nothing inside it, so a scalar written there is right by construction - and
    `x` is therefore also the one place a paragraph of prose could reach a view
    and pass every gate. view-format.md's normative rule is that a view MUST NOT
    contain content text, so the write layer is where that gets refused.

    The length rule is about a value with no bundle in hand, so its proper home
    is schema.py's `extensions` kind. It is here because that module is not this
    one's to change - reported rather than smuggled.
    """
    values = common.extension_keys(pairs, FLAG_FOR["View"])
    for key in sorted(values):
        if key in VIEW_KEYS_WITHOUT_A_FLAG:
            raise stage.Refused(
                f"--set {key}=...: `{key}` is a view's own key, not an "
                f"extension\n"
                f"fix:  `--set` on a view writes under `x`, where validate_urs.py "
                f"permits anything and nothing reads it - so this would look "
                f"written and change nothing. No flag writes `{key}` yet, so it "
                f"is a hand edit if the view really needs it - and check "
                f"view-format.md first, because `tags` and `resource` are concept "
                f"keys a view may not carry at all")
        value = values[key]
        if len(value) > CONTENT_TEXT and any(c.isspace() for c in value):
            raise stage.Refused(
                f"--set {key}=...: {len(value)} characters of prose\n"
                f"fix:  view-format.md is normative - \"a view MUST NOT contain "
                f"content text\". It may carry references, ordering, redaction "
                f"and presentation settings and nothing else, which is the rule "
                f"that makes tailoring auditable by construction. Prose belongs "
                f"in the concept it is about - a project's `# Bullets`, or the "
                f"gap assessment")
    return values


# --- the shape of an amend -------------------------------------------------------

def _checked_update(type_name, doc, updates, extensions=()):
    """`updates`, checked against the type, with the file's required keys in hand.

    Deliberately not the whole of `doc.meta` merged: a pre-existing problem in a
    key nobody touched would refuse a change that had nothing to do with it, and
    the refusal would name a key the person did not type. Deliberately not
    `updates` alone either: `format_profile` is required on a View, and a `set`
    that is not changing it must not be told it is missing. So the file's own
    value stands in for the keys the type requires, and nothing else is read.
    """
    values = dict(updates)
    for key in schema.TYPES[type_name]:
        if key.required:
            values.setdefault(key.name, doc.meta.get(key.name))
    return common.checked(type_name, values, extensions)


def _spliced(doc, path, structures=None, scalars=None):
    """The file's whole new text with these keys set, one splice at a time.

    Re-parsed between splices because each of concept.py's setters works from the
    frontmatter lines it was handed and returns text - so applying two to the same
    Concept would compute the second one's insertion point against the file as it
    was before the first.
    """
    text = doc.text()
    for key, value in (structures or {}).items():
        text = concept.set_structured(concept.parse(text, path), key, value)
    for key, value in (scalars or {}).items():
        text = concept.set_key(concept.parse(text, path), key, value)
    return text


def _existing(doc, path, key, shape):
    """What the file already holds under `key`, as `shape`, or a refusal.

    Every verb here that adds to a key has to read what is there first, and these
    files are hand-editable by design: a `budget: 2` or an `include: acme` would
    otherwise reach dict() or list() and leave a TypeError where a sentence
    belongs. Not schema.py's rule - that module judges what a command is about to
    write, and this is about what somebody already wrote.
    """
    value = doc.meta.get(key)
    if value is None:
        return shape()
    if not isinstance(value, shape):
        word = "mapping" if shape is dict else "list"
        raise stage.Refused(
            f"{path}: `{key}` is a {type(value).__name__}, and this command adds "
            f"to it\n"
            f"fix:  make it a {word} by hand, or delete the key and let the "
            f"command write it - references/view-format.md and bundle-spec.md give "
            f"the shape of each")
    return shape(value)


def _refuse_blank(text, what, why):
    """A body that says nothing, in a file whose whole job is to say it."""
    if text.strip():
        return text
    raise stage.Refused(
        f"--body is empty, so this {what} would say nothing\n"
        f"fix:  {why}. `--body -` reads it from stdin, which is how a real run "
        f"passes prose")


def _shown(names, cap=8):
    """A few of `names`, capped and named.

    Capped for the reason okf_compile.select_views caps its own list at eight: the
    bundles this exists for hold a hundred ids, and a hundred of them scrolling
    past is not an answer to a typo.
    """
    listed = sorted(names)
    if not listed:
        return "none at all"
    shown = ", ".join(listed[:cap])
    if len(listed) > cap:
        shown += f", ... and {len(listed) - cap} more"
    return shown


# --- posting add ----------------------------------------------------------------

def _refuse_unmarked_predecessor(bundle, stem):
    """The pre-revision-5 `<stem>.md` a posting replaces, with nothing to say so.

    validate_bundle.py:301-310 reads it as an error at revision 6 and above -
    "superseded by <stem>.posting.md and not marked" - but only once the posting is
    actually beside it. So the file is clean today and this write is what breaks
    it, which is exactly the class of rule that has to live in this layer: no gate
    can warn about a state nobody has created yet.
    """
    bare = common.path_of(bundle, "Job Posting", stem)
    if not os.path.exists(bare):
        return
    if common.open_concept(bare, "posting").meta.get("superseded_by"):
        return
    raise stage.Refused(
        f"{bare}: already describes this job, and says nothing about which "
        f"document is live\n"
        f"fix:  add `superseded_by: {stem}.posting.md` to it, or choose a "
        f"different --slug. Two documents for one job with nothing to order them "
        f"is how a scorer reads the wrong requirements, and validate_bundle.py "
        f"makes it an error the moment the posting lands beside it")


def posting_add(args):
    """`tailoring/targets/<slug>.posting.md` - the advertisement, verbatim.

    The advertisement goes in the **body** and never into frontmatter.
    jsk-tailor-analyst.md says so in as many words - "it is already in the body,
    verbatim, which is what the archive keeps and what a person re-reads" - and
    okf_compile.posting() agrees: it lifts the frontmatter the ranking runs on and
    hands the whole body over as `source.raw_text`.

    `requirements[]` is written empty rather than left out. okf_compile.posting()
    reads `meta.get("requirements")`, so an absent key and an empty list compile
    the same; the key exists so that the next verb has an extent to splice into
    and so that a person opening the file can see what is missing.
    """
    bundle = common.bundle_root(args.bundle)
    advertisement = _refuse_blank(
        common.read_body(args.body), "posting",
        "paste the advertisement - the archive's whole job is to keep the text "
        "the application was answering, and a posting with none is one nobody "
        "can re-read")
    extensions = common.extension_keys(args.set, FLAG_FOR["Job Posting"])
    values = common.without_none({
        "title": args.title,
        "description": args.description,
        "company": args.company,
        "url": args.url,
        "timestamp": common.stamp(),
        "status": args.status,
        "seniority": args.seniority,
        "domains": common.first_appearance(args.domain) or None,
        "requirements": [],
    })
    values.update(extensions)
    # Checked before the stem is derived, because the stem is derived FROM
    # `company` and `title`: with either missing, slug() would name the file after
    # the word "None" and the refusal a person got would be about a filename.
    common.checked("Job Posting", values, extensions)
    stem = common.stem_of(f"{args.company} {args.title}", args.slug,
                          common.directory_of("Job Posting"))
    path = target_path(bundle, "Job Posting", stem)
    common.refuse_existing(path, "posting", "requirement add")
    _refuse_unmarked_predecessor(bundle, stem)

    change = stage.Changeset()
    common.stage_concept(change, path,
                         common.emit(bundle, "Job Posting", values,
                                     advertisement))
    common.stage_index(change, bundle, "Job Posting",
                       filename("Job Posting", stem), args.title,
                       args.description)
    common.stage_log(change, bundle,
                     f"Added {relative('Job Posting', stem)} - {args.title}")
    change.record_id("posting", stem)
    return change


# --- posting requirement add ----------------------------------------------------

def posting_requirement_add(args):
    """One entry appended to a posting's `requirements[]`.

    One call per requirement, because one call is one thing to check: `value`
    against the vocabulary, `value` against what the posting already asks for, and
    `necessity` against the reason it exists. Several `--value` are allowed under
    one `--kind` and one `--necessity` - three preferred technologies in one call
    is a real thing to want - and the four flags are deliberately NOT four
    parallel repeatable lists paired by position, because a `necessity` paired
    with the wrong `value` is the exact defect this key exists to prevent.

    `--label` is refused alongside several values for the same reason: a label is
    the posting's own wording for one requirement, so there is no correct way to
    spread one across three.
    """
    bundle = common.bundle_root(args.bundle)
    path = target_path(bundle, "Job Posting", args.posting)
    common.require_file(
        path, "posting",
        f"fix:  --posting names the stem the three target files share, without "
        f"`{SUFFIXES['Job Posting']}`. `okf posting add` writes a new one")
    doc = common.open_concept(path, "posting")

    if args.necessity is None:
        # jsk-tailor-analyst.md: "necessity is the one distinction that earns this
        # file. A posting that says 'expert in Terraform' and one that says
        # 'Terraform a plus' are different postings, and the ranking treats them
        # differently. When the advertisement genuinely does not say, write
        # `implicit` rather than promoting a guess to `required` - the scorer
        # excludes implicit requirements by default, and a requirement invented as
        # `required` makes a good fit look like a bad one."
        #
        # Which is why the key has no default here. Defaulting it either way would
        # be this command inventing exactly that: `required` invents a demand the
        # advertisement never made, and `implicit` silently drops a real one out of
        # the ranking (score_projects.py:168 excludes it unless --include-implicit).
        raise stage.Refused(
            "--necessity is not optional and has no default\n"
            "fix:  --necessity required | preferred | implicit. `required` and "
            "`preferred` are different postings and the ranking treats them "
            "differently; `implicit` is the honest answer when the advertisement "
            "does not say, because score_projects.py leaves it out of the score "
            "rather than counting a guess as a demand")

    values = common.first_appearance(args.value)
    minted = common.first_appearance(args.new_capability)
    vocabulary = None
    if args.kind == "capability":
        # The same check and the same resolution `project add` offers, from the
        # same helper: `--capability` is compared against the vocabulary as it will
        # be *after* this command, and `--new-capability x --theme "<heading>"`
        # adds the term in this same changeset. An empty vocabulary switches the
        # check off, exactly as validate_bundle.py:411 does - rejecting every value
        # on a fresh bundle and accepting every value on a populated one are the
        # same bug wearing opposite signs.
        values, vocabulary = common.resolve_capabilities(
            bundle, values, minted, args.theme, required=False)
    elif minted or args.theme:
        raise stage.Refused(
            f"--kind {args.kind} with --new-capability\n"
            f"fix:  framework/capability-vocabulary.md lists capabilities, not "
            f"technologies - a project's `technologies:` is a separate axis with "
            f"no closed vocabulary behind it. Drop --new-capability, or write "
            f"--kind capability if the term really is one")

    if not values:
        # Not argparse's `required=True`, because `--new-capability x --theme "Y"`
        # on its own is a complete instruction - it is how `project add` reads the
        # pair, and a term minted here is a term this requirement uses: the
        # vocabulary is not a place to park a word.
        raise stage.Refused(
            "no requirement was named\n"
            "fix:  --value <term> - the vocabulary term the ranking matches on, "
            "as an exact string. `--new-capability <term> --theme \"<heading>\"` "
            "names one that is not in the vocabulary yet and adds it in this same "
            "change")

    if args.label and len(values) > 1:
        raise stage.Refused(
            f"--label with {len(values)} values\n"
            f"fix:  `label` is the posting's own wording for one requirement - "
            f"jsk-tailor-analyst.md keeps it because that phrasing is what belongs "
            f"in prose later. Add the labelled one on its own call")

    existing = _existing(doc, path, "requirements", list)
    already = {str(entry.get("value")) for entry in existing
               if isinstance(entry, dict)}
    for value in values:
        if value in already:
            raise stage.Refused(
                f"{path}: already asks for {value!r}\n"
                f"fix:  a requirement listed twice is counted twice by "
                f"score_projects.py, so one posting would weigh it double against "
                f"every project. Change the entry that is there, or add the term "
                f"the advertisement actually uses for the second demand")

    entries = list(existing)
    for value in values:
        entry = {"value": value, "kind": args.kind, "necessity": args.necessity}
        if args.label:
            # `value` is vocabulary and `label` is the advertisement. The score
            # matches `value` as an exact string, so a synonym does not fail - it
            # silently scores as absent evidence.
            entry["label"] = args.label
        entries.append(entry)

    extensions = common.extension_keys(args.set, FLAG_FOR["Job Posting"])
    _checked_update("Job Posting", doc, dict(extensions, requirements=entries),
                    extensions)

    change = stage.Changeset()
    common.stage_concept(change, path,
                         _spliced(doc, path, {"requirements": entries},
                                  extensions))
    if vocabulary is not None:
        # Staged after the posting, so a torn publish loses the vocabulary row
        # rather than the requirement. Both are authored, and the one that cannot
        # be reconstructed from the other is the requirement.
        common.stage_concept(change, common.vocabulary_path(bundle), vocabulary)
    common.stage_log(
        change, bundle,
        f"Set {relative('Job Posting', args.posting)} - requirement "
        f"{', '.join(values)} ({args.necessity} {args.kind})")
    change.record_id("posting", args.posting)
    change.record_id("requirement", ", ".join(values))
    return change


# --- gaps write -----------------------------------------------------------------

def gaps_write(args):
    """`tailoring/targets/<stem>.gaps.md` - the assessment, beside its posting.

    Refuses when the posting is not there, because validate_bundle.py:311 makes
    that a hard error: an assessment with no posting cannot say what it was
    answering, and writing one would produce a bundle that fails its own gate.

    Overwriting is legitimate - mode-tailor.md runs the analyst a second time when
    an answer moved a verdict, and it revises the assessment rather than writing a
    second one - so `--replace` exists to make the re-run deliberate rather than
    accidental. The whole file is rewritten, which is why it has to be asked for:
    anything hand-edited into the old one goes.
    """
    bundle = common.bundle_root(args.bundle)
    stem = args.posting
    common.require_file(
        target_path(bundle, "Job Posting", stem), "posting",
        f"fix:  --posting names the stem the three target files share. "
        f"validate_bundle.py makes a `.gaps.md` with no `.posting.md` beside it "
        f"an error, so writing this one would leave a bundle that fails its own "
        f"gate - `okf posting add` writes the posting first")
    path = target_path(bundle, "Gap Assessment", stem)
    replacing = os.path.exists(path)
    if replacing and not args.replace:
        raise stage.Refused(
            f"{path}: already exists\n"
            f"fix:  pass --replace to rewrite it. A second assessment of the same "
            f"posting is an ordinary thing to want - mode-tailor.md asks for one "
            f"when an answer moved a verdict - but the whole file is rewritten, so "
            f"anything edited into this one by hand goes with it")
    assessment = _refuse_blank(
        common.read_body(args.body), "assessment",
        "write the account the verdicts came from - jsk-tailor-analyst.md writes "
        "this file to be read aloud to a person, and a verdict with nothing "
        "behind it is one nobody can check")

    extensions = common.extension_keys(args.set, FLAG_FOR["Gap Assessment"])
    # A title so the index row has something to say. Derived rather than left out:
    # bundle-spec.md recommends the key on every concept, and an index of untitled
    # rows is one nobody reads back.
    title = args.title or f"Gap assessment - {stem}"
    values = common.without_none({
        "title": title,
        "description": args.description,
        "posting": stem,
        "assessed": args.assessed or common.today(),
        "fit": args.fit,
        "timestamp": common.stamp(),
        "status": args.status,
    })
    values.update(extensions)
    common.checked("Gap Assessment", values, extensions)

    change = stage.Changeset()
    common.stage_concept(change, path,
                         common.emit(bundle, "Gap Assessment", values,
                                     assessment))
    common.stage_index(change, bundle, "Gap Assessment",
                       filename("Gap Assessment", stem), title,
                       args.description)
    detail = f"fit {args.fit}" if args.fit else "assessment written"
    common.stage_log(
        change, bundle,
        f"{'Replaced' if replacing else 'Added'} "
        f"{relative('Gap Assessment', stem)} - {detail}")
    change.record_id("gaps", stem)
    return change


# --- the view -------------------------------------------------------------------

def minted_view_id(stem):
    """The id `view create` writes down.

    Derived through body.compile_slug, which is okf_compile.slug, so the id reads
    like every other id in the record - `view_acme_engineer` beside
    `prj_care_platform`.
    """
    return f"view_{body.compile_slug(stem)}"


def compiled_view_id(stem, meta):
    """The id a view on disk actually answers to, declared or derived.

    okf_compile.concepts() hands build_views() the *filename* stem, which for
    `acme.view.md` is `acme.view` - so a view that never wrote an `id:` down
    compiles to `view_acme_view`, trailing noun and all. That is why `view create`
    materialises the id, and why this is what `render_resume.py --view` has to be
    given for a view somebody wrote by hand.
    """
    declared = meta.get("id")
    if declared:
        return str(declared)
    return f"view_{body.compile_slug(stem + '.view')}"


def _open_view(bundle, stem, verb):
    """One view and its path, or a refusal naming what is not there."""
    path = target_path(bundle, "View", stem)
    common.require_file(
        path, "view",
        f"fix:  --view names the stem the three target files share, without "
        f"`{SUFFIXES['View']}`. `okf view create --posting <stem>` writes a new "
        f"one, and `okf view {verb}` changes it afterwards")
    return path, common.open_concept(path, "view")


def _budget(existing, pages, ats_max_pages):
    """The view's whole new `budget`, with the key that was not passed kept.

    Merged rather than replaced because the two are independent budgets: ATS-maximal
    is deliberately longer - it repeats the employer on every role line and expands
    the skills block with aliases - and urs/resolve.py falls back to `pages` only
    when `ats_maximal_pages` is absent. Setting one and silently dropping the other
    would change the length of a document nobody asked about.
    """
    out = dict(existing)
    if pages is not None:
        out["pages"] = pages
    if ats_max_pages is not None:
        out["ats_maximal_pages"] = ats_max_pages
    return out or None


def view_create(args):
    """`tailoring/targets/<stem>.view.md` - the selection, beside its posting.

    `target.ref` is the path to the posting **from the view's own directory**, and
    they are siblings, so it is the bare filename with no `../`. Nothing checks a
    frontmatter path - validate_bundle.py's link checker reads Markdown links and
    this is not one - so the body carries the same string as a Markdown link. It is
    one line, it is the same value by construction, and it turns a silent
    frontmatter path into one the gate verifies on every run.
    """
    bundle = common.bundle_root(args.bundle)
    stem = args.posting
    posting = target_path(bundle, "Job Posting", stem)
    common.require_file(
        posting, "posting",
        f"fix:  --posting names the stem the three target files share. "
        f"validate_bundle.py makes a `.view.md` with no `.posting.md` beside it "
        f"an error, and the view's own `target.ref` points at that file - "
        f"`okf posting add` writes it first")
    path = target_path(bundle, "View", stem)
    common.refuse_existing(path, "view", "set")

    advertised = common.open_concept(posting, "posting").meta
    title = advertised.get("title")
    company = advertised.get("company")
    # "Principal Engineer @ Acme", which is view-format.md's own example. Read off
    # the posting rather than retyped, so the two cannot disagree about which job
    # this is. `label` and `target` are metadata about the application and are
    # never rendered into the document body - view-format.md is explicit - which
    # is what makes them legal in a format that carries no content text.
    label = args.label or " @ ".join(str(v) for v in (title, company) if v) or stem
    reference = filename("Job Posting", stem)

    extensions = _view_extensions(args.set)
    values = common.without_none({
        "title": args.title or label,
        "description": args.description,
        "timestamp": common.stamp(),
        "status": args.status,
        "id": minted_view_id(stem),
        "label": label,
        "format_profile": args.format_profile,
        "region_profile": args.region_profile,
        "locale": args.locale,
        "narrative": args.narrative,
        "target": {"title": title, "ref": reference},
        # An empty `include` and an absent one mean the same thing to
        # urs/resolve.py, which reads `if self.selection:` and selects everything
        # when it is falsy. The key is written for the writer, not the reader:
        # `view include` splices into an extent, and a person opening the file can
        # see that nothing has been selected yet.
        "include": [],
        "redact": common.first_appearance(args.redact) or None,
        "provenance_floor": args.provenance_floor,
        "budget": _budget({}, args.pages, args.ats_max_pages),
        "x": extensions or None,
    })
    common.checked("View", values)

    change = stage.Changeset()
    common.stage_concept(
        change, path,
        common.emit(bundle, "View", values,
                    f"# Renders against\n\n[{reference}]({reference})\n"))
    common.stage_index(change, bundle, "View", filename("View", stem),
                       values["title"], args.description)
    common.stage_log(change, bundle,
                     f"Added {relative('View', stem)} - {values['id']}")
    change.record_id("view", values["id"])
    return change


def view_set(args):
    """Amend a view's presentation keys, and re-stamp what that costs.

    `status` goes back to `inferred` unless `--status` says otherwise, per the
    spec: "Confirmation is then something the agent had to ask for, rather than
    something it inherits by not touching a line." A view whose format profile or
    page budget just changed is a view somebody has to look at again.
    """
    bundle = common.bundle_root(args.bundle)
    path, doc = _open_view(bundle, args.view, "set")
    extensions = _view_extensions(args.set)

    scalars = common.without_none({
        "label": args.label,
        "format_profile": args.format_profile,
        "region_profile": args.region_profile,
        "locale": args.locale,
        "narrative": args.narrative,
        "provenance_floor": args.provenance_floor,
        "redact": common.first_appearance(args.redact) or None,
        "title": args.title,
        "description": args.description,
    })
    structures = {}
    if args.pages is not None or args.ats_max_pages is not None:
        structures["budget"] = _budget(_existing(doc, path, "budget", dict),
                                       args.pages, args.ats_max_pages)
    if extensions:
        # Merged over what is there, so `--set a=1` twice in two calls leaves both.
        structures["x"] = dict(_existing(doc, path, "x", dict), **extensions)
    if not scalars and not structures:
        raise stage.Refused(
            f"{path}: nothing to set\n"
            f"fix:  name a key - --format-profile, --region-profile, --locale, "
            f"--narrative, --provenance-floor, --label, --pages, "
            f"--ats-max-pages, --redact, or --set key=value. A command that "
            f"wrote nothing and re-stamped the status would have un-confirmed a "
            f"view in exchange for nothing")

    changed = sorted(list(scalars) + list(structures))
    scalars["status"] = args.status or "inferred"
    _checked_update("View", doc, dict(scalars, **structures))

    change = stage.Changeset()
    common.stage_concept(change, path, _spliced(doc, path, structures, scalars))
    common.stage_log(
        change, bundle,
        f"Set {relative('View', args.view)} - {', '.join(changed)}")
    change.record_id("view", compiled_view_id(f"{args.view}.view", doc.meta))
    return change


def _selectable_ids(bundle):
    """{id: the concept it comes from} for every id a view's `include.ref` may name.

    Derived rather than compiled. urs/resolve.py reads `include[].ref` as either an
    engagement id - which filters and orders the experience section - or a project
    id, which selects achievements inside the engagement that project belongs to.
    Both derivations are okf_compile's and both are cheap, where a compile is about
    a second on a real bundle and this runs on the hot path of a tailoring run.

      * a project's id is `ident(meta, stem, "prj")` - what the concept declares,
        else `prj_<slug(stem)>`.
      * an engagement's id is `f"eng_{slug(org)}"` off the role's `organisation:`,
        and NOT ident(): an organisation's own `id:` renames the *organization* it
        compiles to and never the engagement, so honouring one here would offer an
        id the record does not hold.
    """
    out = {}
    for stem, _, meta, _ in common.concept_bodies(bundle, "projects"):
        if meta.get("type") != "Project":
            continue
        out[str(meta.get("id") or f"prj_{body.compile_slug(stem)}")] = (
            f"projects/{stem}.md")
    for stem, _, meta, _ in common.concept_bodies(bundle, "roles"):
        if meta.get("type") != "Role":
            continue
        org = meta.get("organisation") or meta.get("organization")
        if org:
            out[f"eng_{body.compile_slug(str(org))}"] = f"roles/{stem}.md"
    return out


def _require_items(bundle, kind, wanted, flag):
    """Every `wanted` id, or a refusal naming a few of the ids that exist.

    common.item_ids includes the ids the compile *derives* from position, because
    those are the ids a view can name today. Without this the mistake is caught
    after the view is written, if at all: validate_urs.py's check_references would
    report it on the next `okf gates`, by which time the view has been rendered
    from and the id it should have named is no longer obvious.
    """
    known = common.item_ids(bundle, kind)
    for value in wanted:
        if value not in known:
            raise stage.Refused(
                f"{flag} {value}: no {kind} in the bundle has that id\n"
                f"fix:  one of {_shown(known)}. A view selects by id, so an id "
                f"that resolves to nothing is one fewer line in the document with "
                f"no gate to say which - validate_urs.py reports it on the next "
                f"`okf gates`, by which time somebody has rendered from it")
    return wanted


def view_include(args):
    """One entry in a view's `include[]` - the verb that selects the evidence.

    **`order` orders achievements, never employers.** view-format.md: within an
    entry the `achievements` list renders in the order written, which is how a
    bullet earns the top of a role; the entry's own `order` is read and then
    overridden, because engagements always render by date - a resume that reorders
    employers by relevance reads as concealment and breaks the date parsing every
    ATS does first. So the achievement order passed here is meaningful and is
    written exactly as given. Nothing here sorts it.

    An entry for a `ref` that is already listed is amended key by key: a flag that
    was passed replaces that key, and a flag that was not leaves it alone. A
    repeatable flag replaces its whole list rather than appending to it, because
    order is a property of the list and not of its members - appending would put a
    new achievement last by accident rather than by choice.
    """
    bundle = common.bundle_root(args.bundle)
    path, doc = _open_view(bundle, args.view, "include")

    selectable = _selectable_ids(bundle)
    if args.ref not in selectable:
        raise stage.Refused(
            f"--ref {args.ref}: no engagement or project in the bundle has that "
            f"id\n"
            f"fix:  one of {_shown(selectable)}. An engagement's id comes from a "
            f"role's `organisation:` and a project's from its filename, both as "
            f"okf_compile derives them - and a view whose every `ref` resolves to "
            f"nothing does not fail, it silently falls back to selecting every "
            f"engagement in the record")

    achievements = _require_items(
        bundle, "bullet", common.first_appearance(args.achievement),
        "--achievement")
    skills = _require_items(
        bundle, "skill", common.first_appearance(args.skill), "--skill")

    entries = _existing(doc, path, "include", list)
    at = next((n for n, entry in enumerate(entries)
               if isinstance(entry, dict) and entry.get("ref") == args.ref), None)
    entry = dict(entries[at]) if at is not None else {}
    entry["ref"] = args.ref
    if args.order is not None:
        entry["order"] = args.order
    if achievements:
        entry["achievements"] = achievements
    if skills:
        entry["skills"] = skills
    if at is None:
        entries.append(entry)
    else:
        entries[at] = entry

    extensions = _view_extensions(args.set)
    structures = {"include": entries}
    if extensions:
        structures["x"] = dict(_existing(doc, path, "x", dict), **extensions)
    # The same re-stamp `set` makes, and for the same reason: which evidence a
    # document quotes is the largest thing about it, so a view that has just been
    # re-selected is not still the view somebody confirmed.
    scalars = {"status": args.status or "inferred"}
    _checked_update("View", doc, dict(scalars, **structures))

    change = stage.Changeset()
    common.stage_concept(change, path, _spliced(doc, path, structures, scalars))
    common.stage_log(
        change, bundle,
        f"Set {relative('View', args.view)} - "
        f"{'included' if at is None else 'reselected'} {args.ref}")
    change.record_id("view", compiled_view_id(f"{args.view}.view", doc.meta))
    change.record_id("include", args.ref)
    return change


# --- the CLI --------------------------------------------------------------------

def _vocabulary(name):
    """The allowed values, for a flag's help text."""
    return "one of " + ", ".join(schema.VOCABULARIES[name])


def _status(parser, default="inferred"):
    """`--status`, with the note that says which way the default runs.

    `default=None` is for the verbs that amend a view: those re-stamp `inferred`
    themselves, so the flag's job there is to say "and this one is confirmed"
    rather than to supply a value the command would otherwise not have.
    """
    parser.add_argument(
        "--status", default=default,
        help=_vocabulary("status") + (
            f" (default {default})" if default
            else " - without it the view goes back to inferred, because a change "
                 "nobody has looked at is not a change somebody confirmed"))
    return parser


def _titles(parser):
    """The two recommended keys every concept carries, per bundle-spec.md."""
    parser.add_argument("--title", help="the concept's own title")
    parser.add_argument("--description", help="one sentence, for the index row")
    return parser


def _view_keys(parser, creating):
    """The presentation keys `view create` and `view set` share.

    One function rather than two copies: a flag spelt differently on the two verbs
    that write the same key is a view a person can create and cannot amend.
    """
    parser.add_argument("--label",
                        help="what this application is, for a person reading the "
                             "file - \"Principal Engineer @ Acme\". Metadata, "
                             "never rendered into the document")
    parser.add_argument(
        "--format-profile",
        help=_vocabulary("format_profile") + " - which of ats-rules.md's four "
             "variants the render obeys" + (" (required)" if creating else ""))
    parser.add_argument("--region-profile",
                        help="urs:profile:au/1 - a profile file the schema has")
    parser.add_argument("--locale", help="en-AU")
    parser.add_argument("--narrative",
                        help="the id of the summary variant to render")
    parser.add_argument("--provenance-floor",
                        default="confirmed" if creating else None,
                        help=_vocabulary("status") + " - the status content must "
                             "reach to render" + (" (default confirmed, which is "
                             "the default for anything a person will actually "
                             "send)" if creating else ""))
    parser.add_argument("--pages", type=int, help="the page budget: budget.pages")
    parser.add_argument("--ats-max-pages", type=int,
                        help="budget.ats_maximal_pages - ATS-maximal runs longer, "
                             "so it carries its own budget")
    parser.add_argument("--redact", action="append", default=[],
                        help="a dotted path to leave out - person.phone. "
                             "Repeatable")
    return parser


def register(nouns):
    """Every verb this module contributes, on three nouns."""
    _, posting_verbs = common.verb(
        nouns, "posting", "a job advertisement, verbatim, and what it asks for")
    add = common.add_verb(posting_verbs, "add",
                          "write a new posting - the advertisement on stdin",
                          posting_add)
    add.add_argument("--company", help="who is hiring")
    add.add_argument("--slug",
                     help="the stem the three target files share (default: the "
                          "company and title, slugged)")
    add.add_argument("--url", help="where the advertisement was read")
    add.add_argument("--seniority", help=_vocabulary("seniority"))
    add.add_argument("--domain", action="append", default=[],
                     help="a domain the role sits in. Repeatable")
    add.add_argument("--body", required=True,
                     help="the advertisement, verbatim. `-` reads stdin")
    _titles(_status(add))

    # A third level, so that `posting requirement add` reads as what it is: one
    # entry in one key of one posting, rather than a second spelling of `add`.
    _, requirement_verbs = common.verb(
        posting_verbs, "requirement",
        "one thing a posting asks for, as the ranking reads it")
    requirement = common.add_verb(
        requirement_verbs, "add", "append a requirement to a posting",
        posting_requirement_add)
    requirement.add_argument("--posting", required=True,
                             help="the posting's stem, without .posting.md")
    requirement.add_argument("--value", action="append", default=[],
                             help="the vocabulary term the ranking matches on, as "
                                  "an exact string. Repeatable under one --kind "
                                  "and one --necessity")
    requirement.add_argument("--kind", required=True, help=_vocabulary("kind"))
    requirement.add_argument("--necessity", help=_vocabulary("necessity") +
                             " - required, and deliberately not defaulted")
    requirement.add_argument("--label",
                             help="the posting's own wording for it, for prose "
                                  "later. One value only")
    requirement.add_argument("--new-capability", action="append", default=[],
                             help="a capability to add to the vocabulary in this "
                                  "same change, and use. Needs --theme")
    requirement.add_argument("--theme",
                             help="the vocabulary heading a new term is filed "
                                  "under")

    _, gaps_verbs = common.verb(
        nouns, "gaps", "an honest account of where the record falls short")
    write = common.add_verb(gaps_verbs, "write",
                            "write the assessment - the prose on stdin",
                            gaps_write)
    write.add_argument("--posting", required=True,
                       help="the posting's stem, which this file sits beside")
    write.add_argument("--assessed", help="the date it was assessed (default today)")
    write.add_argument("--fit", help=_vocabulary("fit"))
    write.add_argument("--body", required=True,
                       help="the assessment, read aloud to a person. `-` reads "
                            "stdin")
    write.add_argument("--replace", action="store_true",
                       help="rewrite an assessment that is already there")
    _titles(_status(write))

    _, view_verbs = common.verb(
        nouns, "view", "which evidence a document renders, and how")
    create = common.add_verb(view_verbs, "create",
                             "write a new view beside its posting", view_create)
    create.add_argument("--posting", required=True,
                        help="the posting's stem - the view sits beside it and "
                             "target.ref points at it")
    _titles(_status(_view_keys(create, creating=True)))

    amend = common.add_verb(view_verbs, "set", "amend a view's settings", view_set)
    amend.add_argument("--view", required=True,
                       help="the view's stem, without .view.md")
    _titles(_status(_view_keys(amend, creating=False), default=None))

    include = common.add_verb(view_verbs, "include",
                              "select the evidence one engagement or project "
                              "contributes", view_include)
    include.add_argument("--view", required=True,
                         help="the view's stem, without .view.md")
    include.add_argument("--ref", required=True,
                         help="an engagement or project id from the record")
    include.add_argument("--order", type=int,
                         help="1-5. Read and then overridden - engagements always "
                              "render by date. See view-format.md")
    include.add_argument("--achievement", action="append", default=[],
                         help="a bullet id, in the order it should render. "
                              "Repeatable")
    include.add_argument("--skill", action="append", default=[],
                         help="a skill id this entry evidences. Repeatable")
    _status(include, default=None)
