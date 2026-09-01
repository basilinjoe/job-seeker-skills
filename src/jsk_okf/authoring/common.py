"""What every command needs before it can decide anything.

Moved out of commands.py when the catalogue grew past one verb. The reason is
mechanical: `commands.py` is the CLI and imports the modules that implement the
verbs, so a verb module importing `commands` for `bundle_root` would be a cycle.
The reason it is worth its own file is not: forty-odd commands each finding the
bundle, deriving a stem, stamping a timestamp and appending a log row is forty
chances for two of them to do it differently, in a bundle a person then has to
read.

Nothing here judges a value - that is schema.py - and nothing here formats one -
that is concept.py and body.py. This layer owns exactly the rules that need the
bundle in hand, which schema.py's docstring names and declines.
"""

import datetime
import os
import re
import sys
import unicodedata

from .. import markup
from . import bookkeeping, concept, schema, stage

# A file stem: lowercase words joined by hyphens, which is the shape bookkeeping.py
# names in its own refusal and the shape every concept in a scaffolded bundle wears.
# Deliberately not okf_compile.slug(), which joins with `_` because it is deriving an
# id (`prj_aged_care`) rather than naming a file.
SEPARATORS = re.compile(r"[^a-z0-9]+")


def first_appearance(values):
    """`values` with repeats dropped, keeping the order they were given in.

    One helper rather than one rule per flag. `--capability` deduped and `--domain`
    did not, so `--domain ops --domain ops` wrote `[ops, ops]` while the same
    mistake on the flag beside it wrote `[ops]`. Two repeatable flags on one command
    behaving differently is the kind of thing nobody notices until they are
    debugging something else.

    Order is the caller's, not sorted: `capabilities` and `domains` are read by a
    person as well as by the scorer, and the first term is the one they led with.
    """
    out = []
    for value in values or ():
        if value not in out:
            out.append(value)
    return out


def slug(text):
    """A file stem from a title.

    Decomposed first so an accent is dropped and its letter kept: folding on the
    composed character turned "Café" into "caf", losing a letter the person typed
    rather than a mark they did not.
    """
    plain = unicodedata.normalize("NFKD", str(text))
    plain = plain.encode("ascii", "ignore").decode("ascii")
    return SEPARATORS.sub("-", plain.lower()).strip("-")


def stamp():
    """The `timestamp:` every concept carries, in the one format the format uses."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today(when=None):
    """The date a log row is filed under. `when` is for a caller that has one."""
    return (when or stamp())[:10]


# The two directories that make a path a bundle: the evidence, and what it was done
# under. Checked rather than assumed, because `--bundle` pointing at a parent
# directory, or at a file, produced a FileNotFoundError from somewhere three modules
# down instead of a sentence naming the argument.
REQUIRED_DIRECTORIES = ("projects", "roles")


def bundle_root(path):
    """The bundle, or a refusal naming what is not one about it."""
    path = str(path)
    if not os.path.isdir(path):
        raise stage.Refused(
            f"{path}: not a directory\n"
            f"fix:  --bundle takes a bundle's root - the folder holding projects/ "
            f"and roles/. `okf new <path> --name \"Full Name\"` scaffolds one")
    missing = [name for name in REQUIRED_DIRECTORIES
               if not os.path.isdir(os.path.join(path, name))]
    if missing:
        raise stage.Refused(
            f"{path}: not a bundle - {', '.join(name + '/' for name in missing)} "
            f"is missing\n"
            f"fix:  --bundle takes the bundle's root, not a directory inside it. "
            f"`okf migrate <path>` brings an older layout up to the current one")
    return path


# Where each concept type lives, and what to call it in a refusal. One map rather
# than a directory named at each call site: bundle-spec.md's layout is the rule, and
# a command that spelt its own directory would be the second place it is written
# down. `Metric Set` and `Skill Set` name a file rather than a directory of them,
# because a bundle has one of each - achievements/metrics.md, skills/competencies.md.
DIRECTORIES = {
    "Project": "projects",
    "Role": "roles",
    "Organisation": "organisations",
    "Education": "education",
    "Certification Status": "education",
    "Skill Set": "skills",
    "Metric Set": "achievements",
    "Job Posting": "tailoring/targets",
    "Gap Assessment": "tailoring/targets",
    "View": "tailoring/targets",
}

# The noun each type is called on the command line, and back again. `org` rather
# than `organisation` because it is typed by hand a hundred times in a session, and
# `credential` is not here at all: a credential is an item inside a Certification
# Status concept, not a concept.
NOUNS = {
    "project": "Project",
    "role": "Role",
    "org": "Organisation",
    "education": "Education",
    "certification": "Certification Status",
    "skills": "Skill Set",
    "metrics": "Metric Set",
    "posting": "Job Posting",
    "gaps": "Gap Assessment",
    "view": "View",
}


def directory_of(type_name):
    """The directory a concept of this type belongs in."""
    try:
        return DIRECTORIES[type_name]
    except KeyError:                                     # pragma: no cover - guard
        raise stage.Refused(
            f"{type_name}: this layer does not know where that type lives\n"
            f"fix:  bundle-spec.md's Layout section says - and DIRECTORIES in "
            f"authoring/common.py is where it is written down for the commands")


def stem_of(text, given=None, directory="projects"):
    """The file stem for a new concept: what was asked for, or derived from a title."""
    stem = given or slug(text)
    if not stem:
        raise stage.Refused(
            f"{text!r}: no filename can be derived from this\n"
            f"fix:  pass --slug <stem> - a stem is lowercase words joined by "
            f"hyphens, and a title written entirely in characters a filename "
            f"cannot carry leaves nothing to derive one from")
    if "/" in stem or "\\" in stem:
        # schema.SLUG admits `/` because an `id` may carry one. A *stem* that did
        # would write outside its own directory, which is not a concept any of
        # these commands is being asked to add.
        raise stage.Refused(
            f"{stem!r}: a stem names one file inside {directory}/, not a path\n"
            f"fix:  drop the separator - a command writes into the directory its "
            f"type belongs to and nowhere else")
    if not schema.SLUG.match(stem):
        raise stage.Refused(
            f"{stem!r}: not a file stem\n"
            f"fix:  a stem is lowercase words joined by hyphens - `care-platform`. "
            f"Leave --slug out and it is derived from the title")
    return stem


def path_of(bundle, type_name, stem, suffix=".md"):
    """Where a concept of this type with this stem sits."""
    directory = directory_of(type_name)
    return os.path.join(str(bundle), *directory.split("/"), f"{stem}{suffix}")


def refuse_existing(path, noun, verb="set"):
    """Say no to overwriting a file that is already there."""
    if os.path.exists(path):
        raise stage.Refused(
            f"{path}: already exists\n"
            f"fix:  `okf {noun} {verb}` changes a concept that is already there. "
            f"This command writes a new one, and overwriting somebody's file to "
            f"add one is not a thing it will do")


def require_file(path, what, fix):
    """The path, or a refusal saying what is not there and what to do."""
    if not os.path.exists(path):
        raise stage.Refused(f"{path}: no such {what}\n{fix}")
    return path


def require_relation(bundle, type_name, value, flag):
    """Refuse a relational key naming a concept that is not there.

    Two of the three rules schema.py cannot check, and the expensive pair.
    `validate_bundle.py` checks neither `role:` nor `organisation:`, so the first
    thing that notices a dangling one is `okf_compile.load()` - which `okf score`
    calls on the tailor-analyst's hot path. A dangling relation written today
    surfaces as a crash in the middle of a tailoring run, not as a red line at
    ship time. That is why this is load-bearing rather than a nicety.
    """
    path = path_of(bundle, type_name, value)
    if not os.path.exists(path):
        raise stage.Refused(
            f"{path}: no such {type_name.lower()}\n"
            f"fix:  {flag} names a concept file in "
            f"{directory_of(type_name)}/, without its .md. No gate reports a "
            f"dangling relation: okf_compile.py refuses on it, and `okf score` "
            f"compiles, so this would abort the next tailoring run rather than "
            f"fail a check")
    return path


# --- the capability vocabulary --------------------------------------------------

# Both spellings validate_bundle.py:399-401 looks for, in its order. A bundle written
# against the older name is still read by the gate, so it has to be read here too -
# otherwise this layer sees an empty vocabulary, switches its check off, and writes a
# capability the gate then rejects.
VOCABULARY_NAMES = ("capability-vocabulary.md", "capability_vocabulary.md")

# validate_bundle.py:84's regex, character for character, and NOT bookkeeping.LIST_ITEM
# - which admits `+` bullets and a bullet with no space after it. A term this layer
# read and the gate did not would be a capability accepted here and refused there,
# which is the one failure mode a write-time check must not have.
VOCABULARY_ITEM = markup.LIST_ITEM

# The term inside backticks, as the gate extracts it.
TERM = markup.TERM

HEADING = markup.HEADING


def vocabulary_path(bundle):
    """The vocabulary file, under whichever of the two names is on disk."""
    for name in VOCABULARY_NAMES:
        path = os.path.join(bundle, "framework", name)
        if os.path.exists(path):
            return path
    return os.path.join(bundle, "framework", VOCABULARY_NAMES[0])


def vocabulary_terms(text):
    """Every capability the file lists - list items outside a fence, and nothing else.

    markup.terms, under the name this layer's callers already use. The fence toggle
    inside it was borrowed from bookkeeping, which borrowed it from validate_bundle,
    which had it twice - "a fifth idiom for one rule is how four of them come to
    disagree", said this docstring, correctly, while adding the fifth.

    init_bundle.py scaffolds this file with its example values INSIDE a fence, so a
    fresh bundle yields nothing here - and yields nothing to the gate either, whose
    `if vocab and c not in vocab` then leaves capabilities unchecked. Matching that is
    the whole point: rejecting every value on a fresh bundle and accepting every value
    on a populated one are the same bug wearing opposite signs.
    """
    return markup.terms(text)


def vocabulary_with(path, terms, theme):
    """The vocabulary file's whole new text, with `terms` listed under `theme`.

    Returns text and writes nothing, matching bookkeeping.py: a function that both
    decides and writes cannot be dry-run.
    """
    text, newline = bookkeeping._read(path)
    lines = bookkeeping._newline_terminated(text).split("\n")
    marks = list(bookkeeping._scan(lines))

    wanted = theme.strip().lower()
    headings, found, level = [], None, 1
    for index, line, fenced in marks:
        if fenced:
            continue
        match = HEADING.match(line)
        if not match:
            continue
        headings.append(match.group(2))
        if found is None and match.group(2).strip().lower() == wanted:
            found, level = index, len(match.group(1))
    if found is None:
        known = ", ".join(repr(name) for name in headings) or "none at all"
        raise stage.Refused(
            f"{path}: no heading named {theme!r} - it has {known}\n"
            f"fix:  --theme names a theme heading already in the file, or add the "
            f"heading by hand first. A term filed under a heading nobody uses is a "
            f"term nobody finds when they go looking for one to reuse")

    # A heading at this level or shallower ends the section. A deeper one is the
    # author's own structure inside the theme, and breaking there would put the term
    # above it - the same rule bookkeeping.log_entry applies to a day's entries.
    boundary = re.compile(r"^#{1,%d}[ \t]" % level)
    last = found
    for index, line, fenced in marks[found + 1:]:
        if not fenced and boundary.match(line):
            break
        if line.strip():
            last = index

    rows = [f"- `{term}`" for term in terms]
    joining = last != found and VOCABULARY_ITEM.match(lines[last])
    lines[last + 1:last + 1] = rows if joining else [""] + rows
    return bookkeeping._restore("\n".join(lines), newline)


def existing_capabilities(bundle):
    """Every term the vocabulary lists, and the file it was read from."""
    path = vocabulary_path(bundle)
    if not os.path.exists(path):
        return set(), path
    with open(path, encoding="utf-8", newline="") as handle:
        return vocabulary_terms(handle.read().replace("\r\n", "\n")), path


def resolve_capabilities(bundle, given, minted, theme, required=True):
    """(the concept's capabilities, the vocabulary's new text or None).

    The vocabulary is written in the same changeset as the concept that first uses a
    term, because bundle-spec.md says "add new values there in the same edit" and this
    is the CLI enforcing a rule the spec could only instruct. Two commands would leave
    a window in which the bundle fails its own gate.

    `required=False` is for a command amending a concept that already has
    capabilities and is not being asked to change them.
    """
    if minted and not theme:
        raise stage.Refused(
            f"--new-capability {minted[0]} needs --theme\n"
            f"fix:  --theme \"Architecture & design\" - the vocabulary is grouped by "
            f"theme, and a term appended to no heading is one nobody reads before "
            f"inventing a synonym for it")
    if theme and not minted:
        raise stage.Refused(
            f"--theme {theme!r} was given with no --new-capability\n"
            f"fix:  --theme only says where a new term is filed. Drop it, or name "
            f"the term with --new-capability")

    existing, path = existing_capabilities(bundle)
    if minted and not os.path.exists(path):
        raise stage.Refused(
            f"{path}: does not exist, so there is nowhere to add "
            f"{minted[0]!r}\n"
            f"fix:  create it with a theme heading per group, or drop "
            f"--new-capability and reuse a term that is already in use")

    # A term already listed is not minted again: the file is right and the flag is
    # merely redundant, and adding a second row for it would be this command putting
    # a duplicate into the one file whose whole job is to be the canonical list.
    fresh = []
    for term in minted or ():
        if term not in existing and term not in fresh:
            fresh.append(term)

    # `--capability` is checked against the vocabulary as it will be after this
    # command, so `--capability x --new-capability x` is a redundant pair rather than
    # a contradiction.
    after = existing | set(minted or ())
    for term in given or ():
        # `if existing and ...`, exactly as validate_bundle.py:411 has it: an empty
        # vocabulary switches the check off rather than rejecting every value.
        if existing and term not in after:
            raise stage.Refused(
                f"capability {term!r} is not in {path}\n"
                f"fix:  reuse a term that is there - capabilities are the primary "
                f"matching axis and compare as exact strings, so a synonym does not "
                f"fail, it silently stops matching. If it really is new, "
                f"--new-capability {term} --theme \"<heading>\" adds it in this same "
                f"change")

    capabilities = first_appearance(list(given or ()) + list(minted or ()))
    if required and not capabilities:
        raise stage.Refused(
            "a Project needs at least one capability\n"
            "fix:  --capability <term>, or --new-capability <term> --theme "
            "\"<heading>\". The schema tolerates an empty list because "
            "validate_bundle.py does, so this is the command's own rule: a project "
            "with no capabilities is invisible to every job it actually matches")

    text = vocabulary_with(path, fresh, theme) if fresh else None
    return capabilities, text


# --- extension keys -------------------------------------------------------------

def extension_keys(pairs, flag_for=None):
    """`--set key=value`, as a dict, or a refusal naming the pair that is not one.

    Values stay strings. concept.scalar quotes one that YAML would read back as a
    number or a keyword, so `--set client_reference=007` survives the round trip as
    the string it was typed as.

    `flag_for` maps a key this command already has a flag for to that flag's name -
    or to None where the command stamps the key itself. A `--set` naming one of them
    is two sources for a single key, and which one wins would be decided by dict
    ordering rather than by anything a person could predict.
    """
    flag_for = flag_for or {}
    out = {}
    for pair in pairs or ():
        key, separator, value = pair.partition("=")
        key = key.strip()
        if not separator or not key:
            raise stage.Refused(
                f"--set {pair!r}: not a key=value pair\n"
                f"fix:  write --set key=value - the first `=` separates them, so a "
                f"value may contain more")
        if key in flag_for:
            flag = flag_for[key]
            instead = f"pass {flag}" if flag else "this command stamps it itself"
            raise stage.Refused(
                f"--set {key}=...: `{key}` is not an extension key\n"
                f"fix:  {instead} - two sources for one key is two answers to one "
                f"question, and which wins is not something a person can predict")
        if key in out:
            raise stage.Refused(
                f"--set {key}=...: given twice\n"
                f"fix:  set each key once - a command holding two values for one key "
                f"cannot know which was meant")
        out[key] = value
    return out


# --- reading and writing --------------------------------------------------------

def line_convention(bundle, directory="projects"):
    """The line ending this bundle's own files use.

    concept.new() emits LF and says the caller owns the file's convention; this is the
    caller. init_bundle.py scaffolds through plain text mode, so on Windows every file
    in a fresh bundle is CRLF - and an LF concept written beside them is the one file
    in the bundle that disagrees, which concept.parse() then resolves by rewriting the
    whole file the first time anybody edits one key of it.

    Read off the directory index, which is the nearest file a command was going to
    open anyway. Falls back to the bundle's own root index, then to LF.
    """
    for candidate in (bookkeeping.index_path(bundle, directory),
                      os.path.join(str(bundle), "index.md")):
        if os.path.exists(candidate):
            return bookkeeping._read(candidate)[1]
    return "\n"


def read_body(source):
    """`-` means stdin. Anything else is the body itself.

    The design's own example passes the body on stdin: frontmatter is mechanical and
    belongs in flags, prose is prose.
    """
    return sys.stdin.read() if source == "-" else source


def emit(bundle, type_name, values, body, directory=None):
    """A whole new concept's text, in the bundle's own line convention."""
    newline = line_convention(bundle, directory or directory_of(type_name))
    return bookkeeping._restore(concept.new(type_name, values, body), newline)


def without_none(values):
    """`values` with every None dropped.

    None is absent, not a value: concept.frontmatter() drops it and schema.check()
    reads it as missing, so a required key left None must not reach the file.
    """
    return {key: value for key, value in values.items() if value is not None}


def checked(type_name, values, extensions=()):
    """`values`, or a refusal carrying every problem the schema found."""
    problems = schema.check(type_name, values, extensions=tuple(extensions))
    if problems:
        raise stage.Refused("\n".join(problems))
    return values


def stage_index(change, bundle, type_name, filename, title, description,
                directory=None):
    """Stage the directory index entry for a concept being added.

    Staged only when there is an index to enter into. A bundle missing one is
    already a `BROKEN LINK` error from the root index's map table, so refusing to
    write the concept over it would withhold the authored half over a fault the
    gate is already reporting.
    """
    directory = directory or directory_of(type_name)
    index = bookkeeping.index_path(bundle, directory)
    if not os.path.exists(index):
        return
    change.write(index,
                 bookkeeping.index_entry(index, filename, title, description),
                 kind="companion")


def stage_index_removal(change, bundle, type_name, filenames, directory=None):
    """Stage the removal of a concept's index rows. Returns what it dropped."""
    directory = directory or directory_of(type_name)
    index = bookkeeping.index_path(bundle, directory)
    if not os.path.exists(index):
        return []
    text, dropped = bookkeeping.index_without(index, filenames)
    if dropped:
        change.write(index, text, kind="companion")
    return dropped


def open_concept(path, what="concept"):
    """One concept file, parsed for splicing, or a refusal naming it.

    Reading needs pyyaml where writing does not - see concept.py - so this is the
    boundary where a `set`, a `retire` or an item mutation costs the dependency
    and an `add` does not.
    """
    require_file(path, what,
                 "fix:  name a concept that is there, without its .md - `add` "
                 "writes a new one")
    return concept.read(path)


def stage_concept(change, path, text):
    """Stage a concept's whole new text. It publishes before its companions."""
    change.write(str(path), text, kind="concept")


def add_common(parser):
    """The flags every write carries, per the design's cross-cutting set.

    One function rather than one copy per verb: forty verbs each declaring
    `--dry-run` is forty chances for one of them to spell it `--dryrun`, and the
    flag that writes nothing is a poor one to get wrong.
    """
    parser.add_argument("--bundle", required=True,
                        help="the bundle's root directory")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="an extension key, repeatable")
    parser.add_argument("--dry-run", action="store_true",
                        help="decide everything, write nothing")
    parser.add_argument("--json", action="store_true",
                        help="print the files changed and the ids minted")
    return parser


def verb(nouns, noun, help_text):
    """One noun's parser and its verb subparsers.

    `parser=` is set on both levels so main() can print the help for whichever
    level the caller got wrong, rather than the top-level usage for a mistake
    three words in.
    """
    parser = nouns.add_parser(noun, help=help_text)
    parser.set_defaults(parser=parser)
    verbs = parser.add_subparsers(dest="verb", metavar="<verb>")
    return parser, verbs


def add_verb(verbs, name, help_text, build):
    """One verb's parser, with the common flags and its builder attached."""
    parser = verbs.add_parser(name, help=help_text)
    parser.set_defaults(build=build, parser=parser)
    add_common(parser)
    return parser


def leaf_verb(nouns, noun, help_text, build):
    """A noun that is its own verb: `okf log --message`, `okf reindex`.

    Two of the commands have exactly one thing they do, and `okf log add` would be
    a level of grammar that says nothing. So the noun carries the flags directly.
    Same defaults as add_verb, so main() cannot tell the two shapes apart.
    """
    parser = nouns.add_parser(noun, help=help_text)
    parser.set_defaults(build=build, parser=parser)
    add_common(parser)
    return parser


# --- what a body already says ---------------------------------------------------

def concept_bodies(bundle, directory):
    """Every concept in one directory: (stem, path, meta, body).

    Reads rather than compiles. The compile is ~1,024 ms on a hundred-application
    bundle and it walks the whole tree; this reads one directory, which is what
    the two verbs that need to know about ids can afford - `bullet add`, checking
    a minted id is unique, and `view include`, checking a referenced one resolves.
    """
    out = []
    root = os.path.join(str(bundle), *directory.split("/"))
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if not name.endswith(".md") or name == "index.md":
            continue
        path = os.path.join(root, name)
        try:
            doc = concept.read(path)
        except concept.Unsplicable:
            # A concept this layer cannot parse is one somebody has to fix by
            # hand, and it is not this command's business to say so: a `bullet
            # add` that refused because an unrelated file has a duplicate key
            # would be unusable in a real bundle. Skipped, which means an id in
            # it is not seen - and the uniqueness check is the weaker for it,
            # which is the honest trade.
            continue
        out.append((name[:-3], path, doc.meta, doc.body))
    return out


def item_ids(bundle, kind):
    """Every id of one item kind in the bundle: {id: (stem, position)}.

    Includes the ids the compile *derives*, because those are the ids a view can
    name today - the whole hazard the materialisation exists to remove. So a
    minted id checked against this cannot collide with an implicit one either.
    """
    from . import body                                   # noqa: PLC0415 - see below
    spec = body.KINDS[kind]
    derive = {"bullet": body.derived_bullet_id,
              "credential": body.derived_credential_id}.get(kind)
    out = {}
    for directory in ITEM_DIRECTORIES[kind]:
        for stem, _, _, text in concept_bodies(bundle, directory):
            block = body.parse(text, spec["heading"], spec["keys"])
            if block is None:
                continue
            # claims(), not items(): an entry with fields and no sentence is
            # dropped by okf_compile.blocks() and consumes no position, so
            # numbering over every entry would derive ids the compile never mints.
            # It only ever widened the uniqueness set here, so it was harmless -
            # and it was wrong, which is worse in the one function whose whole job
            # is to say what the compile would call things.
            for n, entry in enumerate(block.claims(), 1):
                if entry.id:
                    out[entry.id] = (stem, n)
                elif derive is not None:
                    out[derive(stem, n)] = (stem, n)
                else:
                    out[body.derived_skill_id(entry.text)] = (stem, n)
    return out


# Where each kind of authored item lives. Bullets are projects' alone -
# okf_compile.py calls bullets() from exactly one place, inside build_projects -
# so a `# Bullets` block written in a Role compiles to nothing, silently. Skills
# and held credentials are read from every concept of their type, which is why
# both lists hold a directory rather than a file.
ITEM_DIRECTORIES = {
    "bullet": ("projects",),
    "skill": ("skills",),
    "credential": ("education",),
}


def stage_log(change, bundle, message, when=None):
    """Stage the `log.md` row for whatever just happened.

    Every verb logs, including the two that remove: a retirement and a deletion are
    both facts worth recording, and a change with no log row is a change nobody can
    date.
    """
    log = os.path.join(str(bundle), "log.md")
    if not os.path.exists(log):
        return
    change.write(log, bookkeeping.log_entry(log, message, today(when)), kind="log")
