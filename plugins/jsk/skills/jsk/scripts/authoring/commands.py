"""One function per noun-verb: where user input meets the schema, the emitter and
the transaction.

This module assembles the other four and decides nothing itself. Whether a value is
allowed is schema.py's question; how it is written is concept.py's; when a file lands
is stage.py's. If a validation rule appears here it belongs in schema.py, and if a
quoting decision appears here it belongs in concept.py.

**What is only here is the class of rule that needs the bundle in hand.** schema.py
takes values and nothing else - no path, no filesystem - so a rule about whether some
other file exists or says something cannot live in it. Its docstring names exactly
three, and this is the layer that owns them:

  - a `capabilities` value must appear in `framework/capability-vocabulary.md`, and
    only when that file lists any values at all;
  - a Project's `role` must name a concept in `roles/`;
  - a Role's `organisation` must name a concept in `organisations/`.

The referential pair is the expensive one to miss. `validate_bundle.py` checks
neither, so the first thing that notices is `okf_compile.load()` - which `okf score`
calls on the tailor-analyst's hot path. A dangling `role` written today surfaces as a
crash in the middle of a tailoring run, not as a red line at ship time. That is why
the `--role` existence check is load-bearing rather than a nicety.

Referential checks are local by construction: `--role X` is a stat on one file and
`--capability c` parses one vocabulary. Nothing here walks the tree, so a write costs
about the interpreter floor rather than the ~1,024 ms a full compile costs. A whole
`okf validate` still runs once at the end of a mode, as the mode files already say.
"""

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

from . import bookkeeping, concept, schema, stage

# A file stem: lowercase words joined by hyphens, which is the shape bookkeeping.py
# names in its own refusal and the shape every concept in a scaffolded bundle wears.
# Deliberately not okf_compile.slug(), which joins with `_` because it is deriving an
# id (`prj_aged_care`) rather than naming a file.
SEPARATORS = re.compile(r"[^a-z0-9]+")


def slug(text):
    """A file stem from a title.

    Decomposed first so an accent is dropped and its letter kept: folding on the
    composed character turned "Café" into "caf", losing a letter the person typed
    rather than a mark they did not.
    """
    plain = unicodedata.normalize("NFKD", str(text))
    plain = plain.encode("ascii", "ignore").decode("ascii")
    return SEPARATORS.sub("-", plain.lower()).strip("-")


# The two directories a Project write needs to exist before it can mean anything: its
# own, and the one holding the role it must name. Checked rather than assumed, because
# `--bundle` pointing at a parent directory, or at a file, produced a FileNotFoundError
# from somewhere three modules down instead of a sentence naming the argument.
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
VOCABULARY_ITEM = re.compile(r"^\s*[-*]\s+")

# The term inside backticks, as the gate extracts it.
TERM = re.compile(r"`([a-z0-9-]+)`")

HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")


def vocabulary_path(bundle):
    """The vocabulary file, under whichever of the two names is on disk."""
    for name in VOCABULARY_NAMES:
        path = os.path.join(bundle, "framework", name)
        if os.path.exists(path):
            return path
    return os.path.join(bundle, "framework", VOCABULARY_NAMES[0])


def vocabulary_terms(text):
    """Every capability the file lists - list items outside a fence, and nothing else.

    The fence toggle is bookkeeping's, which is validate_bundle.py's, which is
    pipeline_model.py's: borrowed rather than reinvented because a fifth idiom for one
    rule is how four of them come to disagree.

    init_bundle.py scaffolds this file with its example values INSIDE a fence, so a
    fresh bundle yields nothing here - and yields nothing to the gate either, whose
    `if vocab and c not in vocab` then leaves capabilities unchecked. Matching that is
    the whole point: rejecting every value on a fresh bundle and accepting every value
    on a populated one are the same bug wearing opposite signs.
    """
    terms = set()
    for _, line, fenced in bookkeeping._scan(text.split("\n")):
        if not fenced and VOCABULARY_ITEM.match(line):
            terms.update(TERM.findall(line))
    return terms


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


def resolve_capabilities(bundle, given, minted, theme):
    """(the concept's capabilities, the vocabulary's new text or None).

    The vocabulary is written in the same changeset as the concept that first uses a
    term, because bundle-spec.md says "add new values there in the same edit" and this
    is the CLI enforcing a rule the spec could only instruct. Two commands would leave
    a window in which the bundle fails its own gate.
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

    path = vocabulary_path(bundle)
    existing = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as handle:
            existing = vocabulary_terms(handle.read().replace("\r\n", "\n"))
    elif minted:
        raise stage.Refused(
            f"{path}: does not exist, so there is nowhere to add "
            f"{minted[0]!r}\n"
            f"fix:  create it with a theme heading per group, or drop "
            f"--new-capability and reuse a term that is already in use")

    # A term already listed is not minted again: the file is right and the flag is
    # merely redundant, and adding a second row for it would be this command putting
    # a duplicate into the one file whose whole job is to be the canonical list.
    fresh = []
    for term in minted:
        if term not in existing and term not in fresh:
            fresh.append(term)

    # `--capability` is checked against the vocabulary as it will be after this
    # command, so `--capability x --new-capability x` is a redundant pair rather than
    # a contradiction.
    after = existing | set(minted)
    for term in given:
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

    capabilities = []
    for term in list(given) + list(minted):
        if term not in capabilities:
            capabilities.append(term)
    if not capabilities:
        raise stage.Refused(
            "a Project needs at least one capability\n"
            "fix:  --capability <term>, or --new-capability <term> --theme "
            "\"<heading>\". The schema tolerates an empty list because "
            "validate_bundle.py does, so this is the command's own rule: a project "
            "with no capabilities is invisible to every job it actually matches")

    text = vocabulary_with(path, fresh, theme) if fresh else None
    return capabilities, text


# --- extension keys -------------------------------------------------------------

# Keys this command already has a flag for. A `--set` naming one of them is two
# sources for a single key, and which one wins would be decided by dict ordering
# rather than by anything a person could predict.
FLAG_FOR = {
    "title": "--title",
    "description": "--description",
    "role": "--role",
    "strength": "--strength",
    "recency": "--recency",
    "seniority": "--seniority",
    "domains": "--domain",
    "capabilities": "--capability",
    "technologies": "--technology",
    "headline_metric": "--headline-metric",
    "status": "--status",
    "timestamp": None,
}


def extension_keys(pairs):
    """`--set key=value`, as a dict, or a refusal naming the pair that is not one.

    Values stay strings. concept.scalar quotes one that YAML would read back as a
    number or a keyword, so `--set client_reference=007` survives the round trip as
    the string it was typed as.
    """
    out = {}
    for pair in pairs or ():
        key, separator, value = pair.partition("=")
        key = key.strip()
        if not separator or not key:
            raise stage.Refused(
                f"--set {pair!r}: not a key=value pair\n"
                f"fix:  write --set key=value - the first `=` separates them, so a "
                f"value may contain more")
        if key in FLAG_FOR:
            flag = FLAG_FOR[key]
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


# --- project add ----------------------------------------------------------------

def line_convention(bundle):
    """The line ending this bundle's own files use.

    concept.new() emits LF and says the caller owns the file's convention; this is the
    caller. init_bundle.py scaffolds through plain text mode, so on Windows every file
    in a fresh bundle is CRLF - and an LF concept written beside them is the one file
    in the bundle that disagrees, which concept.parse() then resolves by rewriting the
    whole file the first time anybody edits one key of it.

    Read off the directory index, which is the nearest file this command was going to
    open anyway.
    """
    index = bookkeeping.index_path(bundle, "projects")
    if os.path.exists(index):
        return bookkeeping._read(index)[1]
    return "\n"


def read_body(source):
    """`-` means stdin. Anything else is the body itself.

    The design's own example passes the body on stdin: frontmatter is mechanical and
    belongs in flags, prose is prose.
    """
    return sys.stdin.read() if source == "-" else source


def project_add(args):
    """A new Project concept, its index entry, its log row - as one changeset.

    Builds and returns; it does not commit. main() commits, so that --dry-run runs
    every decision this function makes and only skips the write. A dry run that
    skipped the derivation would be a dry run of half the command.
    """
    bundle = bundle_root(args.bundle)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    stem = args.slug or slug(args.title)
    if not stem:
        raise stage.Refused(
            f"{args.title!r}: no filename can be derived from this title\n"
            f"fix:  pass --slug <stem> - a stem is lowercase words joined by "
            f"hyphens, and a title written entirely in characters a filename cannot "
            f"carry leaves nothing to derive one from")
    if "/" in stem or "\\" in stem:
        # schema.SLUG admits `/` because an `id` may carry one. A *stem* that did
        # would write outside projects/, which is not a concept this command is being
        # asked to add.
        raise stage.Refused(
            f"{stem!r}: a stem names one file inside projects/, not a path\n"
            f"fix:  drop the separator - `okf project add` writes into the bundle's "
            f"projects/ directory and nowhere else")
    if not schema.SLUG.match(stem):
        raise stage.Refused(
            f"{stem!r}: not a file stem\n"
            f"fix:  a stem is lowercase words joined by hyphens - `care-platform`. "
            f"Leave --slug out and it is derived from --title")

    filename = f"{stem}.md"
    path = os.path.join(bundle, "projects", filename)
    if os.path.exists(path):
        raise stage.Refused(
            f"{path}: already exists\n"
            f"fix:  `okf project set` changes a concept that is already there. This "
            f"command writes a new one, and overwriting somebody's file to add a "
            f"project is not a thing it will do")

    role_path = os.path.join(bundle, "roles", f"{args.role}.md")
    if not os.path.exists(role_path):
        # The refusal that pays for this layer. Nothing else catches it until
        # okf_compile.load(), which `okf score` calls - so without this the mistake
        # surfaces as a crash in the middle of a tailoring run.
        raise stage.Refused(
            f"{role_path}: no such role\n"
            f"fix:  --role names a concept file in roles/, without its .md. No gate "
            f"reports a dangling role: okf_compile.py refuses on it, and `okf score` "
            f"compiles, so this would abort the next tailoring run rather than fail "
            f"a check")

    capabilities, vocabulary = resolve_capabilities(
        bundle, args.capability or [], args.new_capability or [], args.theme)
    extra = extension_keys(args.set)

    values = {
        "title": args.title,
        "description": args.description,
        "timestamp": stamp,
        "status": args.status,
        "role": args.role,
        "strength": args.strength,
        "recency": args.recency,
        "seniority": args.seniority,
        "domains": list(args.domain),
        "capabilities": capabilities,
        "technologies": list(args.technology) if args.technology else None,
        "headline_metric": args.headline_metric,
    }
    values.update(extra)
    # None is absent, not a value: concept.frontmatter() drops it and schema.check()
    # reads it as missing, so a required key left None must not reach the file.
    values = {key: value for key, value in values.items() if value is not None}

    problems = schema.check("Project", values, extensions=tuple(extra))
    if problems:
        raise stage.Refused("\n".join(problems))

    newline = line_convention(bundle)
    text = bookkeeping._restore(
        concept.new("Project", values, read_body(args.body)), newline)

    change = stage.Changeset()
    change.write(path, text, kind="concept")

    index = bookkeeping.index_path(bundle, "projects")
    # Staged only when there is an index to enter into. A bundle missing one is
    # already a `BROKEN LINK` error from the root index's map table, so refusing to
    # write the concept over it would withhold the authored half over a fault the
    # gate is already reporting.
    if os.path.exists(index):
        change.write(index,
                     bookkeeping.index_entry(index, filename, args.title,
                                             args.description),
                     kind="companion")
    if vocabulary is not None:
        change.write(vocabulary_path(bundle), vocabulary, kind="companion")

    log = os.path.join(bundle, "log.md")
    if os.path.exists(log):
        change.write(log,
                     bookkeeping.log_entry(log,
                                           f"Added projects/{filename} - {args.title}",
                                           stamp[:10]),
                     kind="log")

    change.record_id("project", stem)
    return change


# --- the CLI --------------------------------------------------------------------

def add_common(parser):
    """The flags every write carries, per the design's cross-cutting set."""
    parser.add_argument("--bundle", required=True,
                        help="the bundle's root directory")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="an extension key, repeatable")
    parser.add_argument("--dry-run", action="store_true",
                        help="decide everything, write nothing")
    parser.add_argument("--json", action="store_true",
                        help="print the files changed and the ids minted")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="okf project",
        description="Write Project concepts, and everything a write implies.")
    verbs = parser.add_subparsers(dest="verb", metavar="add")
    add = verbs.add_parser("add", help="write a new Project concept")
    add_common(add)
    add.add_argument("--title", required=True, help="the project's title")
    add.add_argument("--slug", help="the file stem; derived from --title if absent")
    add.add_argument("--description", help="one line, for the directory index")
    add.add_argument("--role", required=True,
                     help="the roles/ concept this project was done under")
    add.add_argument("--strength", required=True, type=int,
                     help="1-5; 5 is flagship evidence")
    add.add_argument("--recency", required=True, type=int,
                     help="the year the work was last touched")
    add.add_argument("--seniority", required=True,
                     help="one of " + ", ".join(schema.VOCABULARIES["seniority"]))
    add.add_argument("--domain", action="append", required=True,
                     help="a domain term, repeatable")
    add.add_argument("--capability", action="append", default=[],
                     help="a capability already in the vocabulary, repeatable")
    add.add_argument("--new-capability", action="append", default=[],
                     help="a capability to add to the vocabulary in this same "
                          "change, repeatable; needs --theme")
    add.add_argument("--theme", help="the vocabulary heading --new-capability files "
                                     "its terms under")
    add.add_argument("--technology", action="append", default=[],
                     help="a technology term, repeatable")
    add.add_argument("--headline-metric", help="the one number this project is for")
    add.add_argument("--status", default="confirmed",
                     help="one of " + ", ".join(schema.VOCABULARIES["status"]))
    add.add_argument("--body", default="-",
                     help="the concept's prose; `-` reads stdin")
    add.set_defaults(build=project_add)
    return parser


def main(argv):
    """Parse, build the changeset, commit it, and say what happened."""
    try:
        # A Windows console is cp1252, and everything this command prints can carry a
        # character it has no byte for: a title, a path under a non-ASCII user name, a
        # refusal quoting either. `okf project add --title "項目再構築"` raised a
        # UnicodeEncodeError from inside the `FAIL` print - so the one run that had a
        # refusal worth reading printed a traceback instead of it. `okf gates` carries
        # the same two lines for the same reason.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # pragma: no cover
        pass
    parser = build_parser()
    args = parser.parse_args(list(argv))
    if not getattr(args, "build", None):
        parser.print_help()
        return 2
    try:
        payload = stage.commit(args.build(args), dry_run=args.dry_run)
    except (stage.Refused, concept.Unsplicable) as exc:
        # Both carry their own `fix:` line, so the message is the whole of what a
        # person gets and nothing here paraphrases it.
        print(f"FAIL  {exc}")
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    verb = "would write" if payload["dry_run"] else "wrote"
    for path in payload["changed"]:
        print(f"{verb}  {path}")
    for name, value in sorted(payload["ids"].items()):
        print(f"{name}: {value}")
    if payload["dry_run"]:
        print("dry run - nothing was written")
    return 0
