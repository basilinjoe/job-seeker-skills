"""The career concepts: `project`, `role`, `org`, `education` - add, set, retire, rm.

Sixteen verbs, four of each, and one implementation of each verb. What differs
between a Project and an Education is *data* - which keys the type takes, which of
them gets a flag, what that flag is called - so it is written down as data, in
`SPECS` below, and the four verb functions read it.

Four copies of `add` was the alternative and it was rejected on measurement rather
than on taste: `project add` alone carries nine refusals, and the fourth copy of a
refusal is where two of them start disagreeing about the same rule. The cost of the
table is that the flag list is one indirection away from `--help`; the cost of the
copies would be that `okf education add` refuses a stem `okf role add` accepts.

**The table says which keys get a flag. It does not say what a value may be.** That
is `schema.TYPES`, and the two are joined rather than duplicated: whether a flag is
`required` on `add` is read off `schema.TYPES`, so a key that becomes required in the
schema becomes a required flag here without anybody editing this file.

Nothing here validates or formats. `schema.py` judges a value, `concept.py` and
`body.py` write one, `common.py` owns every rule that needs the bundle on disk. What
is this module's is the assembly, and the one refusal that genuinely needs the whole
tree: `rm` has to know whether anything still points at what it is about to delete.
"""

import os
import re

from . import body, bookkeeping, common, concept, schema, stage


class Flag:
    """One frontmatter key, and the command-line flag that writes it.

    `flag=None` means the key exists on the type and no flag writes it - this layer
    stamps it. `common.extension_keys` reads that distinction out of `FLAG_FOR` to
    decide whether `--set timestamp=...` should be told to pass a flag instead or
    told the command does it itself.
    """

    def __init__(self, key, flag, help_text, repeatable=False, number=False):
        self.key = key
        self.flag = flag
        self.help = help_text
        self.repeatable = repeatable
        self.number = number

    @property
    def dest(self):
        """The attribute argparse puts this flag's value on."""
        return self.flag.lstrip("-").replace("-", "_")

    def declare(self, parser, required, default=None):
        """Add this flag to one verb's parser."""
        if self.flag is None:
            return
        options = {"help": self.help}
        if self.repeatable:
            # The contract's shape for every repeatable flag: an empty list rather
            # than None, so `common.first_appearance` has something to iterate and
            # no call site has to guard for it.
            options.update(action="append", default=[])
        else:
            options["default"] = default
        if self.number:
            options["type"] = int
        if required:
            options["required"] = True
        parser.add_argument(self.flag, **options)

    def read(self, args):
        """This flag's value, or None when it was not given.

        Repeats are dropped and the order given is kept - `common.first_appearance`
        rather than a rule per flag, because `--capability` deduped and `--domain`
        did not, and two repeatable flags on one command behaving differently is
        what nobody notices until they are debugging something else.

        An empty repeatable list reads back as None rather than `[]`, so an absent
        list key is absent: `common.without_none` drops it and `schema.check` then
        reports the required ones as missing, which is the message worth having.
        """
        if self.flag is None:
            return None
        value = getattr(args, self.dest, None)
        if self.repeatable:
            return common.first_appearance(value) or None
        return value


class Labelled:
    """One fact a type keeps in the BODY as a labelled row, not in frontmatter.

    Education's institute and period, and nothing else so far.
    `okf_compile.build_education` reads both out of the body -
    `- **Institute:** Mahatma Gandhi University` - so a key written into frontmatter
    for either is a value somebody typed that no resume shows. schema.py says the
    same thing in its own comment on the type.
    """

    def __init__(self, label, flag, help_text):
        self.label = label
        self.flag = flag
        self.help = help_text

    @property
    def dest(self):
        return self.flag.lstrip("-").replace("-", "_")


class Relation:
    """A key that must name a concept of another type that is actually there.

    Two of the three rules `schema.py` declines because it has no bundle in hand,
    and the expensive pair - see `common.require_relation`.
    """

    def __init__(self, type_name, flag):
        self.type_name = type_name
        self.flag = flag

    @property
    def dest(self):
        return self.flag.lstrip("-").replace("-", "_")


class Spec:
    """One concept type's whole command surface."""

    def __init__(self, name, help_text, flags, relation=None, capabilities=False,
                 labelled=(), id_prefixes=(), referring_keys=()):
        self.name = name
        self.help = help_text
        self.flags = flags
        self.relation = relation
        self.capabilities = capabilities
        self.labelled = labelled
        # The prefixes `okf_compile.ident()` derives this type's record id with. A
        # view names a compiled id, never a filename, so `rm` cannot see a view's
        # reference without them.
        self.id_prefixes = id_prefixes
        # The frontmatter keys in *other* concepts that name a concept of this type
        # by its stem. `role:` on a Project names a Role; `organisation:` on a Role
        # names an Organisation; nothing points at a Project or an Education by key.
        self.referring_keys = referring_keys

    @property
    def noun(self):
        """What this type is called on the command line - `org`, not Organisation."""
        return NOUN_FOR[self.name]

    @property
    def directory(self):
        return common.directory_of(self.name)


# The noun each type answers to, read back out of common.NOUNS rather than restated.
# Two spellings of one map is how they come to disagree about `org`.
NOUN_FOR = {type_name: noun for noun, type_name in common.NOUNS.items()}


def _vocab(name):
    """One closed vocabulary as a help line, so the flag lists its own values."""
    return "one of " + ", ".join(schema.VOCABULARIES[name])


# The four keys every concept in a bundle wears, in the order it wears them.
# `timestamp` has no flag: it is when the concept was written, which is not a thing
# a caller gets to assert. Shared as a function rather than a constant because a
# Flag is stateless but a tuple shared between four Specs reads as though it were
# not.
def _leading():
    return (
        Flag("title", "--title", "the concept's title"),
        Flag("description", "--description", "one line, for the directory index"),
        Flag("timestamp", None, "stamped by the command"),
        Flag("status", "--status", _vocab("status")),
    )


SPECS = (
    Spec(
        "Project",
        "the evidence: one project, one file",
        _leading() + (
            Flag("role", "--role", "the roles/ concept this project was done under"),
            Flag("strength", "--strength", "1-5; 5 is flagship evidence",
                 number=True),
            Flag("recency", "--recency", "the year the work was last touched",
                 number=True),
            Flag("seniority", "--seniority", _vocab("seniority")),
            Flag("domains", "--domain", "a domain term, repeatable",
                 repeatable=True),
            # Written from --capability and --new-capability together, which is why
            # its value is supplied by the verb rather than read off the flag - see
            # common.resolve_capabilities. The flag name is here so `--set
            # capabilities=...` is told which flag to pass instead.
            Flag("capabilities", "--capability",
                 "a capability already in the vocabulary, repeatable",
                 repeatable=True),
            Flag("technologies", "--technology", "a technology term, repeatable",
                 repeatable=True),
            Flag("headline_metric", "--headline-metric",
                 "the one number this project is for"),
            Flag("url", "--url", "where the work can be seen, if it can"),
        ),
        relation=Relation("Role", "--role"),
        capabilities=True,
        id_prefixes=("prj",),
    ),
    Spec(
        "Role",
        "one job title held, and who it was for",
        _leading() + (
            Flag("organisation", "--organisation",
                 "the organisations/ concept this role was for"),
            Flag("start", "--start", "2019, 2019-04 or 2019-04-01"),
            Flag("end", "--end", "omit entirely while the role is ongoing"),
            Flag("state", "--state", _vocab("state")),
            Flag("seniority", "--seniority", _vocab("seniority")),
            Flag("change", "--change", _vocab("change")),
            Flag("functional_title", "--functional-title",
                 "what the work actually was, where the official title does not "
                 "say; renders in parentheses and never replaces the title"),
        ),
        relation=Relation("Organisation", "--organisation"),
        # A Role compiles to a *position* inside an engagement, so `pos_` is the
        # prefix a view would name - not `role_`, which nothing derives.
        id_prefixes=("pos",),
        referring_keys=("role",),
    ),
    Spec(
        "Organisation",
        "one employer or prospect",
        _leading() + (
            Flag("relationship", "--relationship", _vocab("relationship")),
            Flag("industry", "--industry", "an industry term, repeatable",
                 repeatable=True),
            Flag("sector", "--sector", "public, private, not-for-profit"),
            Flag("size", "--size", "headcount or a band, as prose"),
            Flag("employment", "--employment", _vocab("engagement")),
            Flag("url", "--url", "the company's own site"),
        ),
        # An Organisation compiles to an org record *and* to the engagement built
        # from the roles under it, and `eng_<stem>` is derived from the stem no
        # matter what `id:` says - okf_compile.build_engagements. Both are ids a
        # view can name, so `rm` looks for both.
        id_prefixes=("org", "eng"),
        # okf_compile.py reads `organization` too, for bundles written before the
        # spelling settled. A reference this layer could not see is a link `rm`
        # would break, so both spellings are looked for even though only one is
        # written.
        referring_keys=("organisation", "organization"),
    ),
    Spec(
        "Education",
        "a degree or a qualification",
        _leading() + (
            Flag("level", "--level", "bachelor, master, diploma - as prose"),
            Flag("field", "--field", "what it was in"),
            Flag("location", "--location", "where it was taken"),
        ),
        labelled=(
            Labelled("Institute", "--institute",
                     "the awarding institution; written into the body, which is "
                     "where the compile reads it"),
            Labelled("Period", "--period",
                     "\"July 2011 - April 2014\"; written into the body beside "
                     "the institute"),
        ),
        id_prefixes=("edu",),
    ),
)

BY_NAME = {spec.name: spec for spec in SPECS}

# What `commands.py` imports, and what `common.extension_keys` needs: every key one
# of these commands writes through a flag, mapped to that flag. A `--set` naming one
# of them is two sources for a single key, and which one wins would be decided by
# dict ordering rather than by anything a person could predict.
FLAG_FOR = {spec.name: {flag.key: flag.flag for flag in spec.flags}
            for spec in SPECS}

# What `set` stamps when nobody said otherwise. Rule 2 of the write layer, and the
# one worth reading the spec's paragraph on - see `_restamped` below.
INFERRED = "inferred"

# The two keys `retire` writes. Named once because three verbs reach for them.
RETIRE_KEYS = ("retired", "retired_reason")


def _required_keys(type_name):
    """Every key `schema.TYPES` requires on this type.

    Read off the schema rather than restated, so a key that becomes required there
    becomes a required flag here in the same commit. A type lists a key twice to
    sharpen it - `title` is optional in COMMON and required on all four of these -
    and `_assert_no_conflicting_duplicates` in schema.py forbids a repeat that
    relaxes `required`, so taking any entry that says required is the same answer as
    "the last entry wins".
    """
    return {key.name for key in schema.TYPES[type_name] if key.required}


def _modelled_keys(type_name):
    """Every key this type has a definition for, required or not."""
    return {key.name for key in schema.TYPES[type_name]}


def _reason_required(type_name, key_name):
    """The schema's own sentence for why this key is required."""
    for key in schema.TYPES[type_name]:
        if key.name == key_name and key.because:
            return key.because
    return "the schema requires it"                      # pragma: no cover - guard


# --- the labelled rows Education keeps in its body -------------------------------
#
# okf_compile.labelled()'s own regex, character for character (okf_compile.py:322).
# Copied rather than re-derived, for the reason common.VOCABULARY_ITEM copies
# validate_bundle.py's: a row this layer wrote that the compile read differently
# would be an institution nobody's resume shows, and that is the one failure a
# write-time helper must not have.
#
# It belongs in body.py, beside section() and set_section(), and it is here because
# body.py is not this module's to change - reported rather than moved.
LABELLED = re.compile(r"^\s*[-*]\s+\*\*([^:*]+):?\*\*:?\s*(.+)$", re.M)


def labelled_rows(text):
    """Every labelled row in a body: {label lowercased: the value as written}."""
    return {match.group(1).strip().lower(): match.group(2).strip()
            for match in LABELLED.finditer(text)}


def _with_labelled(text, label, value):
    """`text` with one labelled row set, and every other byte where it was.

    Only the value's own span is replaced where the row is already there, so the row
    keeps the author's indentation and their choice of `**Institute:**` over
    `**Institute**:`. The same trade concept.set_key makes on a frontmatter key, for
    the same reason: a tool that reflows somebody's file once is a tool they never
    run again.
    """
    wanted = label.strip().lower()
    last = None
    for match in LABELLED.finditer(text):
        if match.group(1).strip().lower() == wanted:
            return text[:match.start(2)] + str(value) + text[match.end(2):]
        last = match
    row = f"- **{label}:** {value}"
    if last is not None:
        # Joining the labelled block that is already there rather than opening a
        # second one above it: two blocks read as two answers, and labelled() would
        # merge them silently.
        return text[:last.end()] + "\n" + row + text[last.end():]
    body_text = text.lstrip("\n")
    return row + "\n" + ("\n" + body_text if body_text.strip() else "")


def _labelled_body(spec, args, text):
    """The body a new concept gets, with its labelled rows above the prose."""
    rows = []
    for entry in spec.labelled:
        value = getattr(args, entry.dest, None)
        if value:
            rows.append(f"- **{entry.label}:** {value}")
    if not rows:
        return text
    prose = text.lstrip("\n")
    return "\n".join(rows) + "\n" + ("\n" + prose if prose.strip() else "")


# --- the values a concept is written with ----------------------------------------

def _values(spec, args, overrides):
    """The frontmatter a new concept carries, in the order the file wears it."""
    out = {}
    for flag in spec.flags:
        out[flag.key] = (overrides[flag.key] if flag.key in overrides
                         else flag.read(args))
    return common.without_none(out)


def _stem(spec, args, from_title):
    """The concept's file stem, checked.

    `from_title` on `add`, where `--slug` is optional and derived from the title.
    The other three verbs name an existing concept, so the stem is the flag itself -
    passed as `given` so it goes through the same `/` and shape refusals rather than
    being re-slugged into something the person did not type.
    """
    if from_title:
        return common.stem_of(args.title, args.slug, spec.directory)
    return common.stem_of(args.slug, args.slug, spec.directory)


def _capabilities(spec, bundle, args, required):
    """(the value for `capabilities`, the vocabulary's new text) or (None, None).

    Called on `add` and on `set`, and on `set` only when one of the three flags was
    given: a `set` that says nothing about capabilities must not rewrite the list.
    """
    if not spec.capabilities:
        return None, None
    asked = bool(args.capability or args.new_capability or args.theme)
    if not required and not asked:
        return None, None
    capabilities, vocabulary = common.resolve_capabilities(
        bundle, args.capability, args.new_capability, args.theme, required=required)
    return capabilities, vocabulary


# --- add -------------------------------------------------------------------------

def concept_add(args):
    """A new concept, its index entry, its log row, and any vocabulary it minted.

    Builds and returns a changeset; it does not commit. `commands.main` commits, so
    `--dry-run` runs every decision this function makes and skips only the write. A
    dry run that skipped the derivation would be a dry run of half the command.
    """
    spec = BY_NAME[args.type_name]
    bundle = common.bundle_root(args.bundle)
    stamp = common.stamp()

    stem = _stem(spec, args, from_title=True)
    filename = f"{stem}.md"
    path = common.path_of(bundle, spec.name, stem)
    common.refuse_existing(path, spec.noun)
    if spec.relation:
        common.require_relation(bundle, spec.relation.type_name,
                                getattr(args, spec.relation.dest),
                                spec.relation.flag)

    capabilities, vocabulary = _capabilities(spec, bundle, args, required=True)
    extra = common.extension_keys(args.set, FLAG_FOR[spec.name])

    overrides = {"timestamp": stamp}
    if capabilities is not None:
        overrides["capabilities"] = capabilities
    values = _values(spec, args, overrides)
    values.update(extra)
    common.checked(spec.name, values, extensions=tuple(extra))

    text = common.emit(bundle, spec.name, values,
                       _labelled_body(spec, args, common.read_body(args.body)))

    change = stage.Changeset()
    common.stage_concept(change, path, text)
    common.stage_index(change, bundle, spec.name, filename, args.title,
                       args.description)
    if vocabulary is not None:
        change.write(common.vocabulary_path(bundle), vocabulary, kind="companion")
    common.stage_log(change, bundle,
                     f"Added {spec.directory}/{filename} - {args.title}",
                     when=stamp)
    change.record_id(spec.noun, stem)
    return change


# --- set -------------------------------------------------------------------------

def _restamped(changes, given):
    """`set` re-stamps `status: inferred` unless a status was passed explicitly.

    The rule most worth understanding in this layer, and the spec states the reason:
    *"Confirmation is then something the agent had to ask for, rather than something
    it inherits by not touching a line."* Change half a sentence of a `confirmed`
    claim and the status now asserts that a person signed off on text that no longer
    exists - so provenance has to reset across every amendment, and the default has
    to be the conservative one.

    `--unset status` is honoured over this rather than fought: the compile reads a
    concept with no status as `needs-verification`, which is more conservative still,
    so somebody asking for the key to go is not asking for a weaker claim.
    """
    if given is not None:
        return
    if "status" in changes:
        return
    changes["status"] = INFERRED


def _body_change(spec, args, current):
    """The concept's whole new body, or None where nothing asked for one.

    Returns the second element as the words for the log row, because the row has to
    say what changed and only this function knows.
    """
    told = []
    if args.section and args.new_section:
        raise stage.Refused(
            "--section and --new-section were both given\n"
            "fix:  --section names a heading that is there and --new-section "
            "writes one that is not. A command holding both cannot know whether "
            "the heading already existing is the thing it was told about")
    heading = args.section or args.new_section
    if heading and args.body is None:
        raise stage.Refused(
            f"--section {heading!r} was given with no --body\n"
            f"fix:  --body - reads the section's new prose from stdin. The section "
            f"is the floor and there is nothing below it: restating it is how a "
            f"typo mid-paragraph is fixed, and you had to read it anyway to know "
            f"what to fix")
    if args.body is not None and not heading:
        raise stage.Refused(
            "--body was given with no --section\n"
            "fix:  name the heading - --section \"What I decided\" --body -. A "
            "body with no section named is not a whole-body replacement: the rest "
            "of this concept's prose is somebody's, and a command that replaced it "
            "because one flag was ambiguous would take it away silently")

    new_body = None
    if heading:
        prose = common.read_body(args.body)
        if args.new_section:
            new_body = body.add_section(current, args.new_section, prose)
            told.append(f"new section {args.new_section!r}")
        else:
            new_body = body.set_section(current, args.section, prose)
            told.append(f"section {args.section!r}")

    for entry in spec.labelled:
        value = getattr(args, entry.dest, None)
        if not value:
            continue
        new_body = _with_labelled(current if new_body is None else new_body,
                                  entry.label, value)
        told.append(entry.label.lower())
    return new_body, told


def _refuse_new_problems(type_name, before, after, extensions):
    """Refuse a problem this command introduced, and only one it introduced.

    The merged result is checked rather than the flags alone, so a `set` cannot
    leave a concept the schema would have refused at `add` - `--unset title` is
    caught here even though every value the command wrote was fine.

    Only *new* problems are reported, and that is the measured half of the rule. A
    real bundle carries hand-written keys this schema does not model - `organization`
    on a role written before the spelling settled is the one that occurs - and
    checking the merged result flatly would make every future `okf role set` on that
    file refuse over a line the command did not touch. A person cannot fix somebody
    else's key by way of amending their own, and a gate that cannot go green is a
    gate people stop running. So the baseline is the file as it is, and the rule is
    that an amendment may not make a concept worse.
    """
    allowance = tuple(extensions) + tuple(
        key for key in RETIRE_KEYS if key not in _modelled_keys(type_name))
    baseline = set(schema.check(type_name, before, extensions=allowance))
    problems = [problem
                for problem in schema.check(type_name, after,
                                            extensions=allowance)
                if problem not in baseline]
    if problems:
        raise stage.Refused("\n".join(problems))


def _spliced(path, doc, changes, new_body):
    """One concept's whole new text, with each change spliced into it in turn.

    Re-parsed between keys because `concept.set_key` returns the file's text rather
    than a Concept, and the next splice has to measure the lines it is about to cut
    against the text the last one produced. Parsing is `yaml.compose` over one small
    block, and a `set` touches a handful of keys, so the repetition is cheaper than
    a second splicing implementation that tracked line offsets itself.
    """
    text = doc.text()
    for key, value in changes.items():
        text = concept.set_key(concept.parse(text, path), key, value)
    if new_body is not None:
        amended = concept.parse(text, path)
        amended.body = new_body
        text = amended.text()
    return text


def concept_set(args):
    """Amend one concept, surgically: what it was asked to change and nothing else.

    Frontmatter is spliced key by key, so every untouched key keeps its quoting, its
    order, its comments and the file's own line endings. A list-valued key is written
    whole - there is no `--add-domain`, because half a list is not a value and a
    partial edit of one is not expressible.
    """
    spec = BY_NAME[args.type_name]
    bundle = common.bundle_root(args.bundle)
    stem = _stem(spec, args, from_title=False)
    path = common.path_of(bundle, spec.name, stem)
    doc = common.open_concept(path, spec.name.lower())

    if spec.relation and getattr(args, spec.relation.dest):
        common.require_relation(bundle, spec.relation.type_name,
                                getattr(args, spec.relation.dest),
                                spec.relation.flag)

    capabilities, vocabulary = _capabilities(spec, bundle, args, required=False)

    changes, told = {}, []
    for flag in spec.flags:
        if flag.key == "capabilities":
            continue
        value = flag.read(args)
        if value is not None:
            changes[flag.key] = value
            told.append(flag.key)
    if capabilities is not None:
        changes["capabilities"] = capabilities
        told.append("capabilities")

    extra = common.extension_keys(args.set, FLAG_FOR[spec.name])
    changes.update(extra)
    told.extend(sorted(extra))

    required = _required_keys(spec.name)
    for key in common.first_appearance(args.unset):
        if key in changes:
            raise stage.Refused(
                f"--unset {key} was given alongside a value for `{key}`\n"
                f"fix:  drop one of them - a command told both to delete a key and "
                f"to set it cannot know which was meant")
        if key not in doc.meta:
            raise stage.Refused(
                f"{path}: `{key}` is not in this concept, so there is nothing to "
                f"unset\n"
                f"fix:  name a key the file actually carries - it has "
                f"{', '.join(repr(str(name)) for name in doc.meta) or 'none'}")
        if key in required:
            # The same article rule schema.check applies, so a refusal from here
            # and a refusal from there read as one voice.
            article = "an" if spec.name[:1].upper() in "AEIOU" else "a"
            raise stage.Refused(
                f"`{key}` is required on {article} {spec.name}, so it cannot be "
                f"unset\n"
                f"fix:  {_reason_required(spec.name, key)}")
        changes[key] = None
        told.append(f"{key} deleted")

    new_body, body_told = _body_change(spec, args, doc.body)
    told.extend(body_told)

    if not changes and new_body is None:
        raise stage.Refused(
            f"okf {spec.noun} set was given nothing to change\n"
            f"fix:  name at least one flag - `okf {spec.noun} set --help` lists "
            f"them. A `set` that changed nothing would still re-stamp the "
            f"concept's status, which is a change nobody asked for")

    # After the nothing-to-change refusal, so the automatic re-stamp cannot be the
    # only change a command makes.
    _restamped(changes, args.status)
    if "status" in changes and "status" not in told:
        told.append("status")

    merged = dict(doc.meta)
    for key, value in changes.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    _refuse_new_problems(spec.name, doc.meta, merged, extra)

    change = stage.Changeset()
    common.stage_concept(change, path, _spliced(path, doc, changes, new_body))
    if vocabulary is not None:
        change.write(common.vocabulary_path(bundle), vocabulary, kind="companion")
    # The directory index row is deliberately not rewritten when `--title` changes.
    # bookkeeping.index_entry leaves an existing row exactly as written, because the
    # row is the author's - it may have been retitled or reordered on purpose - and
    # a command that rewrote it would be deciding it knows better about a line
    # somebody else wrote. `okf reindex` adds a missing row; it does not restate one.
    common.stage_log(change, bundle,
                     f"Set {spec.directory}/{stem}.md - {', '.join(told)}")
    change.record_id(spec.noun, stem)
    return change


# --- retire ----------------------------------------------------------------------

def concept_retire(args):
    """Stop claiming a concept without deleting it.

    `retired:` and `retired_reason:` are set, the file stays on disk and in git, and
    every link to it keeps resolving. That is the whole difference from `rm`, and it
    is why both exist: work that happened and is no longer being claimed is not a
    mistake, and deleting it loses the record of it.

    `status` is deliberately not re-stamped. `status` says how well the bundle knows
    a claim and `retired` says whether the claim is still being made; a retirement
    changes the second and asserts nothing about the first, and nothing in this
    concept's prose has moved.
    """
    spec = BY_NAME[args.type_name]
    bundle = common.bundle_root(args.bundle)
    stem = _stem(spec, args, from_title=False)
    path = common.path_of(bundle, spec.name, stem)
    doc = common.open_concept(path, spec.name.lower())

    already = doc.meta.get("retired")
    if already is not None:
        raise stage.Refused(
            f"{path}: already retired on {already}\n"
            f"fix:  nothing was changed. `okf {spec.noun} set --slug {stem} "
            f"--set retired_reason=\"...\"` corrects the reason, and a second "
            f"retirement date would overwrite the day this was actually stopped")

    when = args.date or common.today()
    changes = {"retired": when, "retired_reason": args.reason}
    merged = dict(doc.meta)
    merged.update(changes)
    _refuse_new_problems(spec.name, doc.meta, merged, ())

    change = stage.Changeset()
    common.stage_concept(change, path, _spliced(path, doc, changes, None))
    common.stage_log(
        change, bundle,
        f"Retired {spec.directory}/{stem}.md - {args.reason}", when=when)
    change.record_id(spec.noun, stem)
    return change


# --- rm --------------------------------------------------------------------------
#
# The one verb in this module that walks the tree, and the only place in the write
# layer besides `reindex` that does. The cost is justified because the alternative
# is a dangling reference: a delete is the one write that cannot be checked locally,
# since what makes it wrong is in files the command was never told about.
#
# Measured, because it turned out to matter. Parsing the frontmatter of every file
# in the bundle cost 911 ms over 525 markdown files - a hundred-application bundle -
# which is the ~1,024 ms a full compile costs, on a layer sold as costing the
# interpreter floor. With the substring gate in references() below the same walk is
# 194 ms, of which 144 ms is reading the 525 files at all, and a scaffolded bundle's
# 24 files are 15 ms. The gate is what makes this affordable; do not remove it
# without re-measuring.

# The frontmatter keys that hold a relative path out of a concept's own directory.
# `bundle-spec.md`'s Applications section enumerates them: an archived application
# names its frozen companions, its working copy and the company's concept this way,
# and none of those is a markdown link - so the link scan below cannot see them.
PATH_KEYS = ("posting", "assessment", "view_file", "target_working_copy",
             "company_ref", "snapshot_of", "superseded_by")

# validate_bundle.py:83's LINK regex, and bookkeeping.ENTRY_LINK is the same
# pattern. Named through bookkeeping so there is one object rather than two
# spellings: the gate is the reader whose opinion decides whether a link is broken,
# and `rm` refuses exactly when a delete would make the gate report one.
LINK = bookkeeping.ENTRY_LINK

FENCE = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")


def _link_targets(text):
    """Every link target a delete could break, as validate_bundle.py reads them.

    Fenced blocks and inline code are stripped first, exactly as the gate does at
    :258-260: an example link in a template is not a real link, and refusing a
    delete over one would refuse it over a reference nothing would ever report.
    """
    text = INLINE_CODE.sub("", FENCE.sub("", text))
    out = []
    for _, target in LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if "://" in target:
            continue
        target = target.split("#")[0]
        if target:
            out.append(target)
    return out


def _markdown_files(bundle):
    """Every `.md` file in the bundle, walked once.

    Hidden directories are skipped - a bundle kept at the root of its own git
    repository would otherwise have `.git` walked on every delete, and nothing in
    it is a reference somebody wrote.
    """
    for root, directories, names in os.walk(str(bundle)):
        directories[:] = sorted(name for name in directories
                                if not name.startswith("."))
        for name in sorted(names):
            if name.endswith(".md"):
                yield os.path.join(root, name)


def _compiled_ids(spec, stem, meta):
    """Every record id a view could name this concept by.

    A view names a compiled id and never a filename, so without these `rm` would
    delete a project a live view still selects - and the view would then resolve to
    nothing, or to its neighbour, which is the defect the id materialisation exists
    to remove wearing a different hat.
    """
    ids = {f"{prefix}_{body.compile_slug(stem)}" for prefix in spec.id_prefixes}
    declared = meta.get("id")
    if declared:
        # `okf_compile.ident()` prefers a declared id, so a bundle that published
        # one is named by it rather than by the derived form.
        ids.add(str(declared))
    return ids


def _resolves_to(source, value, target):
    """Whether a relative path written in `source` names `target`."""
    try:
        joined = os.path.join(os.path.dirname(source), str(value))
        return os.path.normpath(os.path.abspath(joined)) == target
    except (TypeError, ValueError):                      # pragma: no cover - guard
        return False


def references(bundle, spec, stem, path, meta):
    """Everything in the bundle that still points at this concept.

    Four kinds, which is `write-commands.md`'s own list: a `role:` or
    `organisation:` key, a markdown link, a view's `include[].ref`, and an archived
    application's relative paths. Each is returned as one line naming the file and
    what in it points here, because a refusal that said only "something references
    it" would send somebody grepping for what this function already knows.

    A concept this layer cannot parse is scanned for links and not for keys. That is
    a real hole and it is the honest trade: refusing a delete because some unrelated
    file has a duplicated key would make `rm` unusable in a bundle that has one, and
    the same argument `common.concept_bodies` makes about skipping them applies.
    """
    target = os.path.normpath(os.path.abspath(str(path)))
    ids = _compiled_ids(spec, stem, meta)
    # Every one of the four kinds of reference below needs the stem or one of the
    # compiled ids to appear *literally* in the file: a relational key holds the
    # stem, a path key ends in `<stem>.md`, a link names the same, and an
    # `include[].ref` is one of the ids. So a file holding none of those strings
    # cannot reference this concept, and the yaml parse can be skipped - which is
    # what takes the walk on a hundred-application bundle from 911 ms to 194 ms.
    #
    # The gate is sound rather than heuristic, with one measured exception: a stem
    # written with a YAML escape - `role: "lead\x2Dengineer"` - is a literal the
    # substring test does not see. Nothing writes that shape and it would have to be
    # typed by hand, and the alternative is a delete that costs a full compile.
    wanted = tuple({stem} | ids)
    # The concept's own directory index is skipped: its row is removed in this same
    # changeset by `common.stage_index_removal`, so counting it would make every
    # `rm` refuse itself.
    index = os.path.normpath(os.path.abspath(
        bookkeeping.index_path(bundle, spec.directory)))
    out = []
    for current in _markdown_files(bundle):
        absolute = os.path.normpath(os.path.abspath(current))
        if absolute in (target, index):
            continue
        rel = os.path.relpath(current, str(bundle)).replace(os.sep, "/")
        with open(current, encoding="utf-8", newline="") as handle:
            raw = handle.read().replace("\r\n", "\n")
        if not any(term in raw for term in wanted):
            continue
        doc = None
        if raw.lstrip("\ufeff").startswith("---"):
            try:
                doc = concept.parse(raw, current)
            except concept.Unsplicable:
                doc = None
        for link in _link_targets(doc.body if doc else raw):
            if _resolves_to(current, link, target):
                out.append(f"{rel}: a markdown link to {link}")
        if doc is None:
            continue
        for key in spec.referring_keys:
            if str(doc.meta.get(key) or "") == stem:
                out.append(f"{rel}: {key}: {stem}")
        for key in PATH_KEYS:
            value = doc.meta.get(key)
            if value and _resolves_to(current, value, target):
                out.append(f"{rel}: {key}: {value}")
        for n, entry in enumerate(doc.meta.get("include") or (), 1):
            if isinstance(entry, dict) and str(entry.get("ref") or "") in ids:
                out.append(f"{rel}: include[{n}].ref: {entry['ref']}")
    return common.first_appearance(out)


def concept_rm(args):
    """Delete one concept, and refuse while anything still points at it."""
    spec = BY_NAME[args.type_name]
    bundle = common.bundle_root(args.bundle)
    stem = _stem(spec, args, from_title=False)
    filename = f"{stem}.md"
    path = common.path_of(bundle, spec.name, stem)
    doc = common.open_concept(path, spec.name.lower())
    if args.set:
        raise stage.Refused(
            f"--set was given to `okf {spec.noun} rm`\n"
            f"fix:  a delete writes no keys. `okf {spec.noun} set --slug {stem} "
            f"--set {args.set[0]}` is the command that does")

    still = references(bundle, spec, stem, path, doc.meta)
    if still:
        listed = "\n".join(f"  {line}" for line in still)
        raise stage.Refused(
            f"{path}: {len(still)} thing"
            f"{'' if len(still) == 1 else 's'} still reference"
            f"{'s' if len(still) == 1 else ''} it\n{listed}\n"
            f"fix:  `okf {spec.noun} retire --slug {stem} --reason \"...\"` keeps "
            f"the file and its links resolving, and is what a concept no longer "
            f"being claimed wants. To delete it, remove each reference above "
            f"first - deleting it now would leave a dangling reference the compile "
            f"refuses on. Git is this command's only undo, which is why it will "
            f"not create one for you")

    title = str(doc.meta.get("title") or stem)
    change = stage.Changeset()
    change.remove(path, kind="concept")
    common.stage_index_removal(change, bundle, spec.name, [filename])
    common.stage_log(change, bundle,
                     f"Removed {spec.directory}/{filename} - {title}")
    change.record_id(spec.noun, stem)
    return change


# --- the CLI ---------------------------------------------------------------------

def _declare(parser, spec, verb):
    """One verb's flags, from the type's own table.

    `required` on `add` is read off `schema.TYPES` rather than restated, so the flag
    list and the schema cannot drift: a key the schema requires is a flag argparse
    demands, and the person is told at the command line rather than by a refusal
    after they have typed the rest of it.

    `capabilities` is the exception, and it is required by `common.
    resolve_capabilities` instead - it is written from two flags, and argparse can
    only demand one of them.
    """
    required = _required_keys(spec.name) if verb == "add" else set()
    for flag in spec.flags:
        default = None
        if flag.key == "status" and verb == "add":
            # `confirmed` on `add`, because a person just told you about the work.
            # `set` leaves it None and `_restamped` writes `inferred` - see there.
            default = "confirmed"
        demanded = flag.key in required and flag.key != "capabilities"
        flag.declare(parser, required=demanded, default=default)
    if spec.capabilities:
        parser.add_argument("--new-capability", action="append", default=[],
                            help="a capability to add to the vocabulary in this "
                                 "same change, repeatable; needs --theme")
        parser.add_argument("--theme",
                            help="the vocabulary heading --new-capability files "
                                 "its terms under")
    for entry in spec.labelled:
        parser.add_argument(entry.flag, help=entry.help)


def _article(type_name):
    """`a` or `an`, so four help lines do not read as three plus a typo."""
    return "an" if type_name[:1].upper() in "AEIOU" else "a"


def _register(nouns, spec):
    """One noun's four verbs."""
    article = _article(spec.name)
    parser, verbs = common.verb(nouns, spec.noun, spec.help)
    parser.set_defaults(type_name=spec.name)

    add = common.add_verb(verbs, "add", f"write a new {spec.name} concept",
                          concept_add)
    add.set_defaults(type_name=spec.name)
    _declare(add, spec, "add")
    add.add_argument("--slug", help="the file stem; derived from --title if absent")
    add.add_argument("--body", default="-",
                     help="the concept's prose; `-` reads stdin")

    amend = common.add_verb(verbs, "set",
                            f"amend {article} {spec.name} that is there",
                            concept_set)
    amend.set_defaults(type_name=spec.name)
    _declare(amend, spec, "set")
    amend.add_argument("--slug", required=True,
                       help="the concept's file stem, without its .md")
    amend.add_argument("--unset", action="append", default=[], metavar="KEY",
                       help="delete a key, repeatable; refuses a required one")
    amend.add_argument("--section", metavar="HEADING",
                       help="the prose section --body replaces")
    amend.add_argument("--new-section", metavar="HEADING",
                       help="a prose section to write that is not there yet")
    amend.add_argument("--body", default=None,
                       help="the section's new prose; `-` reads stdin")

    retire = common.add_verb(
        verbs, "retire",
        f"stop claiming {article} {spec.name}, keeping the file", concept_retire)
    retire.set_defaults(type_name=spec.name)
    retire.add_argument("--slug", required=True,
                        help="the concept's file stem, without its .md")
    retire.add_argument("--reason", required=True,
                        help="why it is no longer claimed - it goes in the file "
                             "and in log.md")
    retire.add_argument("--date", help="the day it was retired; today by default")

    remove = common.add_verb(
        verbs, "rm", f"delete {article} {spec.name}, if nothing references it",
        concept_rm)
    remove.set_defaults(type_name=spec.name)
    remove.add_argument("--slug", required=True,
                        help="the concept's file stem, without its .md")


def register(nouns):
    """Add `project`, `role`, `org` and `education` to the CLI."""
    for spec in SPECS:
        _register(nouns, spec)
