"""The verbs that write the claims - the authored content inside a concept's body.

Almost everything in a bundle is a frontmatter key and compiles without anybody
transcribing anything. Four things are *written*: a project's `# Bullets`, a Skill
Set's `# Skills`, a Certification Status's `# Held`, and the rows of
`achievements/metrics.md`. This module holds the fourteen verbs that write them.

The three blocks are one implementation, generic over `body.KINDS`, because they
are one shape to the compiler: `okf_compile.blocks()` parses all three with the
same twelve lines. Writing them three times would be the fourth, fifth and sixth
place the shape of an item is written down.

## The id materialisation, which is the point of this module

`okf_compile.py` mints an item's id positionally where the concept did not write
one:

    "id": fields.get("id") or f"ach_{slug(where)}_{n}"     # projects/<stem>.md

So the first bullet of `projects/care.md` is `ach_projects_care_md_1`, and
`cred_<slug(stem)>_<n>` in build_credentials() has the identical shape.
**Inserting a bullet above it renumbers every bullet below, and a view naming
`..._1` silently starts rendering a different sentence.** The id still resolves,
so `validate_urs.py` passes; it resolves to the wrong claim. Reproduced live
before this was written.

So **every item mutation - add, set, rm, mv - first materialises explicit ids for
every item in that block**, writing down the id the compile was already deriving.
That changes no meaning and leaves every existing view reference pointing at the
same sentence. Then it mutates. After one write the concept is immune, and there
is deliberately no migration - so a bundle nobody writes to stays exposed, and
`validate_urs.py`'s warning about an unmaterialised reference is what makes that
visible rather than a surprise.

A new item mints a content-derived id from its own text - `ach_event_latency` -
never a positional one, because a positional id for a new item means "third from
the top" and the next insertion moves it. Uniqueness is checked against
`common.item_ids`, which includes the ids the compile currently derives, so a
minted id cannot collide with an implicit one either.

## What is not here

Whether a field value is allowed is `schema.py`'s question, and how an item is
written is `body.py`'s. What is only in this layer is the class of rule that needs
the bundle in hand: does this concept exist, is it the type whose block the
compile actually reads, is `--metric M` a row in the table, does a view still
select the id being removed.
"""

import functools
import os

from . import body, bookkeeping, common, concept, schema, stage

# Where each kind of claim lives, and what to say about it. `type` is the concept
# type okf_compile reads that block from *and no other* - build_projects calls
# bullets(), build_skills reads Skill Set, build_credentials reads Certification
# Status - so a block written into the wrong type compiles to nothing, silently.
# That is the refusal `_require_type` exists for.
#
# `creates` says whether this module may write the owning concept when it is
# absent. A Project is `okf project add`'s to write and carries five selection
# keys nobody can guess; a Skill Set and a Certification Status take a title and
# nothing else, no verb in the catalogue creates either, and init_bundle.py
# scaffolds neither - so a claim addressed at one would have nowhere to live.
#
# `provenance` is where this kind of claim's `status` lives, and it is the fact
# two branches here turn on. A bullet carries its own, so a `set` resets it
# across the claim. A skill and a held credential do not: build_skills attaches
# none at all and build_credentials takes it from the *concept's* frontmatter,
# shared with every sibling item. That is why those two kinds get
# `--concept-status` instead of an automatic re-stamp - see item_set.
CLAIMS = {
    "bullet": {
        "type": "Project",
        "flag": "--project",
        "attribute": "project",
        "default": None,
        "creates": False,
        "provenance": "item",
        "help": "a resume line on a project, written rather than derived",
        "flag_help": "the projects/ concept stem this bullet belongs to",
        "text_help": "the sentence itself - what a resume prints",
        "description": None,
    },
    "skill": {
        "type": "Skill Set",
        "flag": "--concept",
        "attribute": "concept",
        # bundle-spec.md's layout names this file: `skills/competencies.md`.
        "default": "competencies",
        "creates": True,
        "provenance": "concept",
        "help": "a competency as a reader should see it",
        "flag_help": "the skills/ concept stem (default: competencies)",
        "text_help": "the competency's display name - \"C# / .NET\"",
        "description": "Grouped competency taxonomy used as the keyword block.",
    },
    "credential": {
        "type": "Certification Status",
        "flag": "--concept",
        "attribute": "concept",
        # No default. A bundle holds one Skill Set and any number of
        # Certification Status concepts - one per awarding body, one per gap - so
        # there is no file to guess at.
        "default": None,
        "creates": True,
        "provenance": "concept",
        "help": "a certification actually held",
        "flag_help": "the education/ concept stem holding the `# Held` block",
        "text_help": "the certification's name, as the issuer writes it",
        "description": "Certifications held, and whether each is still current.",
    },
}

# Each kind's field flags: the flag, the argparse attribute, the key written in
# the file, what `add` defaults it to, and the help.
#
# `id` is deliberately absent from all three. On `add` it is the caller's optional
# override; on `set` it is the *locator*, and an item's id is never a value a
# `set` changes - that would repoint every view naming it, which is the whole
# defect this module exists to close.
FLAGS = {
    "bullet": (
        # Anything authored during tailoring is inferred until a person confirms
        # it, and a view carrying `provenance_floor: confirmed` is what stops one
        # rendering before then.
        ("--status", "status", "status", "inferred",
         "confirmed, inferred or needs-verification - authored content is "
         "inferred until a person confirms it"),
        ("--metric", "metric", "metric", None,
         "the row in achievements/metrics.md this rests on, by its name"),
        # `for` is a Python keyword, so the attribute cannot be `args.for`.
        ("--for", "for_", "for", None,
         "the posting this sentence was written for - how a person tells a "
         "tailored bullet from one that was always true"),
    ),
    "skill": (
        ("--category", "category", "category", None,
         "how the block groups it - language, cloud-platform, practice"),
        ("--aliases", "aliases", "aliases", None,
         "a comma-separated string, NOT a list - okf_compile.build_skills "
         "splits it on commas itself"),
        ("--last-used", "last_used", "last_used", None,
         "2024, 2024-06 or 2024-06-01 - precision is read from what is written"),
    ),
    "credential": (
        ("--issuer", "issuer", "issuer", None, "who awarded it - Microsoft"),
        ("--issued", "issued", "issued", None, "when it was awarded"),
        ("--expires", "expires", "expires", None,
         "when it lapses, where it does"),
        # Not the concept's provenance. okf_compile.build_credentials keeps the
        # two apart by name: this says whether the certification is current, and
        # the concept's frontmatter `status` says how well the bundle knows it.
        ("--status", "status", "status", None,
         "the certification's own currency: active, expired, lapsed or "
         "in-progress - not the concept's provenance"),
    ),
}


def _terminated(text):
    """A body ending in a newline, and otherwise exactly the bytes handed in.

    Not `rstrip` and one newline back: trailing blank lines at the end of a
    concept are the author's, and this layer's rule is that a byte nobody asked
    about does not move. The only case that needs fixing is a body that never
    ended in one, which no splice here produces and a hand-edited file can.
    """
    return text if text.endswith("\n") else text + "\n"


def _plural(n, noun):
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


# --- finding the concept a claim lives in ----------------------------------------

def _where(kind, stem):
    """The concept's path relative to the bundle, for a message or a log row."""
    return f"{common.directory_of(CLAIMS[kind]['type'])}/{stem}.md"


def _stem(kind, args):
    """The stem the locator flag names, checked for shape.

    `given=` rather than deriving one: a locator names a file that is already
    there, and silently slugging `My_Notes` into `my-notes` would open a
    different concept from the one that was typed.
    """
    claim = CLAIMS[kind]
    value = getattr(args, claim["attribute"], None)
    if not value:
        raise stage.Refused(
            f"{claim['flag']} is required\n"
            f"fix:  {claim['flag']} names the "
            f"{common.directory_of(claim['type'])}/ concept this {kind} belongs "
            f"to, without its .md")
    return common.stem_of(value, value, common.directory_of(claim["type"]))


def _require_type(doc, kind, where):
    """Refuse a concept whose type does not hold this kind of block.

    The failure this prevents is silent rather than loud. `okf_compile.load()`
    buckets concepts by type and reads a `# Held` block only out of a
    Certification Status, a `# Skills` block only out of a Skill Set, and calls
    bullets() from exactly one place - inside build_projects. A block in the
    wrong type is parsed by nothing, reported by nothing, and shows up as an
    absence nobody can trace back to a file.
    """
    claim = CLAIMS[kind]
    found = doc.meta.get("type")
    if found == claim["type"]:
        return
    raise stage.Refused(
        f"{where}: this is a {found!r} concept, not a {claim['type']!r}\n"
        f"fix:  name a {claim['type']} concept. okf_compile reads a "
        f"`# {body.KINDS[kind]['heading']}` block out of nothing else, so a "
        f"{kind} written here compiles to no {kind} at all - and no gate "
        f"reports it, because the block is well-formed markdown that nothing "
        f"goes looking for")


def _refuse_missing(kind, bundle, stem, where):
    """Say no to a locator naming a concept that is not there.

    The role case is named on its own because it is the mistake the layout
    invites: `roles/` and `projects/` both hold work, and a `# Bullets` block in
    a Role compiles to nothing.
    """
    if kind == "bullet" and os.path.exists(common.path_of(bundle, "Role", stem)):
        raise stage.Refused(
            f"{where}: no such project - but roles/{stem}.md is there\n"
            f"fix:  bullets are projects' alone. okf_compile calls bullets() "
            f"from one place, inside build_projects, so a `# Bullets` block in "
            f"a Role compiles to nothing and reports nothing. Name the project "
            f"the work was done on, or `okf project add` it first")
    raise stage.Refused(
        f"{where}: no such concept\n"
        f"fix:  name a concept that is there, without its .md - `okf project "
        f"add` writes a new one")


def _refuse_extensions(args, kind):
    """`--set key=value` has no meaning inside an item, and is dangerous in one.

    Every other verb in the catalogue takes extension keys because a concept's
    frontmatter is open. An item's is closed: `okf_compile.blocks()` is handed a
    fixed tuple of keys and **reads anything else as part of the sentence**. So
    `--set audience=recruiters` would not be ignored, it would be printed on a
    resume.
    """
    if not getattr(args, "set", None):
        return
    raise stage.Refused(
        f"--set is not something an item takes\n"
        f"fix:  an item's keys are closed - "
        f"{', '.join(body.KINDS[kind]['keys'])} - because "
        f"okf_compile.blocks() is handed exactly those and reads any other "
        f"line as part of the sentence. An extension key written here would be "
        f"printed on a resume. Put it on the concept instead")


# --- materialising the ids the compile derives -----------------------------------

def _derived(kind, stem, text, position):
    """The id okf_compile would give this item where the concept wrote none."""
    if kind == "bullet":
        return body.derived_bullet_id(stem, position)
    if kind == "credential":
        return body.derived_credential_id(stem, position)
    return body.derived_skill_id(text)


def _materialised(kind, stem, items):
    """(`items` with every implicit id written down, how many were written).

    This is the fix, and it is the first thing every mutation here does. An item
    that already carries an `id:` is returned untouched, bytes and all; one that
    does not is restated with the id the compile was deriving for it, which
    changes no meaning and leaves every view reference pointing at the same
    sentence.

    Positions count only items with text, which is what `Block.claims()` names:
    `blocks()` drops a text-less entry, so such an entry consumes no position and
    the compile derives no id for it at all. Counted inline rather than over
    claims() because every item has to be put back, touched or not - claims() is
    the definition this agrees with, not a list this can iterate instead.
    """
    order = body.KINDS[kind]["order"]
    out, position, written = [], 0, 0
    for entry in items:
        if entry.text:
            position += 1
        if entry.id or not entry.text:
            out.append(entry)
            continue
        fields = dict(entry.fields)
        fields["id"] = _derived(kind, stem, entry.text, position)
        out.append(body.item(entry.text, fields, order))
        written += 1
    return out, written


def _block_of(doc, kind, where, verb):
    """The concept's block, or a refusal for a verb that needs one to be there."""
    spec = body.KINDS[kind]
    block = body.parse(doc.body, spec["heading"], spec["keys"])
    if block is None:
        raise stage.Refused(
            f"{where}: no `# {spec['heading']}` block, so there is no {kind} "
            f"to {verb}\n"
            f"fix:  `okf {kind} add` writes the block as well as the item")
    return block


def _index_of(items, wanted, kind, where):
    """Where `wanted` sits in `items`, or a refusal naming the ids that are there."""
    for index, entry in enumerate(items):
        if entry.id == wanted:
            return index
    known = ", ".join(entry.id for entry in items if entry.id) or "none at all"
    raise stage.Refused(
        f"{where}: no {kind} with id {wanted!r} - it holds {known}\n"
        f"fix:  name an id that is there. Every id in that block is written "
        f"down as of this command, so one that is absent is absent - `--json` "
        f"on the write that created an item reports the id it minted")


def _refuse_insert(at, count, what):
    """Refuse an `--at` outside the list, rather than clamping into it.

    `Block.inserted` clamps, which is right for a library and wrong for a
    command: `--at 40` on a block of three would silently append, and a caller
    who miscounted would be told nothing.
    """
    if at is None:
        return
    if not 1 <= at <= count + 1:
        raise stage.Refused(
            f"--at {at}: {what} holds {_plural(count, 'item')}, so a position "
            f"is 1 to {count + 1}\n"
            f"fix:  --at is 1-based and counts items in the block. Leave it "
            f"out to append")


def _refuse_move(to, count, what):
    """Refuse a `--to` outside the list."""
    if not 1 <= to <= count:
        raise stage.Refused(
            f"--to {to}: {what} holds {_plural(count, 'item')}, so a position "
            f"is 1 to {count}\n"
            f"fix:  --to is 1-based and counts items in the block")


# --- the fields a verb was given -------------------------------------------------

def _fields(kind, args, base=None):
    """`base` with every field flag that was given written over it.

    An empty string is a value: `--metric ""` clears the field, because
    `body.item` drops a field whose value is empty. That is the only way to unset
    one, and it is deliberate - a flag left out has to mean "leave it", which is
    what a `set` amending one field of five needs it to mean.
    """
    fields = dict(base or {})
    for _, attribute, key, _, _ in FLAGS[kind]:
        value = getattr(args, attribute, None)
        if value is not None:
            fields[key] = value
    return fields


def _given(kind, args):
    """The field keys this invocation actually passed, for the log row."""
    return [key for _, attribute, key, _, _ in FLAGS[kind]
            if getattr(args, attribute, None) is not None]


def _checked_item(kind, fields):
    """`fields`, or a refusal carrying every problem the schema found.

    Empty values are dropped before checking rather than after: `--metric ""` is
    a request to remove the field, and an empty string is not a value the schema
    is being asked to approve.
    """
    problems = schema.check_item(
        kind, {key: value for key, value in fields.items() if value != ""})
    if problems:
        raise stage.Refused("\n".join(problems))
    return fields


# --- staging one changed concept -------------------------------------------------

def _log_row(head, detail, materialised):
    """One log row: what happened, and how many implicit ids it wrote down.

    The materialisation is recorded because it is a change to somebody's file
    they did not ask for by name, and a change with no log row is a change nobody
    can date.
    """
    message = f"{head} - {detail}" if detail else head
    if materialised:
        message += f"; wrote down {_plural(materialised, 'implicit id')}"
    return message


def _spliced(change, doc, path, bundle, kind, ident, message, keys=None):
    """Stage the concept, its log row and its id. `doc.body` is already the new one.

    The concept's own `timestamp:` is re-stamped because its body now says
    something else, and a timestamp that did not move is one every reader trusts
    to mean "unchanged since". `keys` is anything else in the frontmatter this
    command was asked to change - `--concept-status`, and nothing else today.

    Re-parsed between keys because `concept.set_key` returns the file's text
    rather than a Concept, and the next splice has to measure the lines it cuts
    against what the last one produced. Same reason career.py's `_spliced` does.
    """
    doc.body = _terminated(doc.body)
    text = doc.text()
    changes = dict(keys or {})
    changes["timestamp"] = common.stamp()
    for key, value in changes.items():
        text = concept.set_key(concept.parse(text, path), key, value)
    common.stage_concept(change, path, text)
    common.stage_log(change, bundle, message)
    change.record_id(kind, ident)
    return change


def _container_status(kind, args, doc, stem):
    """(the frontmatter keys to splice, what to say about it in the log).

    `--concept-status` is the resolution for the one thing a claim verb otherwise
    cannot reach. A skill and a held credential have no provenance of their own -
    build_credentials takes it from the *concept's* `status` and build_skills
    attaches none - so before this flag existed, a credential written by command
    was stuck at whatever the concept said and could never clear a view's
    `provenance_floor: confirmed`. Explicit rather than a default, because
    demoting a shared marker would withhold entries nobody touched: see item_set.

    Checked through `common.checked` on the one key being written plus the title
    the type requires, so the refusal is schema.py's words rather than a second
    opinion about what a status may be. Only those two keys are handed over: the
    file's others are not this command's to be judged on, and a hand-written key
    the schema does not model would otherwise make every `--concept-status` on
    that file refuse over a line it did not touch.
    """
    value = getattr(args, "concept_status", None)
    if value is None:
        return {}, None
    common.checked(CLAIMS[kind]["type"],
                   {"title": (doc.meta.get("title") if doc else None) or stem,
                    "status": value})
    return {"status": value}, f"concept status: {value}"


# --- bullet | skill | credential -------------------------------------------------

def item_add(kind, args):
    """Write a new item into its concept's block, minting its id from its text."""
    bundle = common.bundle_root(args.bundle)
    _refuse_extensions(args, kind)
    spec, claim = body.KINDS[kind], CLAIMS[kind]
    stem = _stem(kind, args)
    path = common.path_of(bundle, claim["type"], stem)
    where = _where(kind, stem)

    fields = _fields(kind, args)
    _refuse_metric(bundle, fields.get("metric"))

    # Checked against every id of this kind in the bundle, including the ones the
    # compile derives - so a minted id cannot collide with an implicit one
    # either. An `--id` the caller passed is refused rather than numbered past:
    # they named a specific id, and a command that quietly wrote `_2` instead
    # would hand back an id nobody asked for.
    existing = common.item_ids(bundle, kind)
    if args.id and args.id in existing:
        holder, position = existing[args.id]
        raise stage.Refused(
            f"--id {args.id}: already the id of item {position} of "
            f"{common.directory_of(claim['type'])}/{holder}.md\n"
            f"fix:  two items with one id is a view selecting whichever the "
            f"compile read first. Leave --id out and one is derived from the "
            f"sentence, or name an id nothing holds")
    ident = args.id or body.mint_id(spec["prefix"], args.text, set(existing))
    fields["id"] = ident
    _checked_item(kind, fields)
    new = body.item(args.text, fields, spec["order"])

    change = stage.Changeset()
    if not os.path.exists(path):
        if not claim["creates"]:
            _refuse_missing(kind, bundle, stem, where)
        _refuse_insert(args.at, 0, "a new block")
        title = getattr(args, "concept_title", None) or _titled(stem)
        status = getattr(args, "concept_status", None) or "inferred"
        common.stage_concept(change, path,
                             _new_concept(bundle, kind, title, new, status))
        common.stage_index(change, bundle, claim["type"], f"{stem}.md", title,
                           claim["description"])
        common.stage_log(
            change, bundle,
            f"Added {where} - {title}, status {status}, holding "
            f"{kind} {ident}")
        change.record_id(kind, ident)
        change.record_id("concept", where)
        return change

    doc = common.open_concept(path, claim["type"].lower())
    _require_type(doc, kind, where)
    keys, told = _container_status(kind, args, doc, stem)
    block = body.parse(doc.body, spec["heading"], spec["keys"])
    if block is None:
        _refuse_insert(args.at, 0, "a new block")
        doc.body = body.add_block(doc.body, spec["heading"], new.lines)
        written = 0
    else:
        block.items, written = _materialised(kind, stem, block.items)
        _refuse_insert(args.at, len(block.items), "the block")
        doc.body = body.replace(doc.body, block,
                                block.inserted(new, args.at))
    detail = args.text if told is None else f"{args.text} ({told})"
    return _spliced(change, doc, path, bundle, kind, ident,
                    _log_row(f"Added {kind} {ident} to {where}", detail,
                             written),
                    keys=keys)


def item_set(kind, args):
    """Restate one item: its text, its fields, or both.

    The status re-stamp is the load-bearing half. A `status: confirmed` bullet
    whose sentence has been half rewritten asserts that a person signed off on
    text that no longer exists - so provenance is reset across the claim unless
    the caller passed `--status` explicitly, which makes confirmation something
    an agent had to ask for rather than something it inherits by not touching a
    line.

    A skill and a held credential have no provenance of their own: build_skills
    attaches none at all, and build_credentials takes it from the *concept's*
    frontmatter, which every other item in that concept shares. Demoting that
    automatically would withhold entries nobody touched from any view with a
    `confirmed` floor - a resume quietly shorter because a sibling's issuer was
    corrected. So it is `--concept-status` instead: the same reasoning that says
    it must not be a default is the reasoning that says it has to be reachable,
    because otherwise a credential written by command can never clear a floor.
    A credential's `--status` is the certification's own currency and is never
    touched here.
    """
    bundle = common.bundle_root(args.bundle)
    _refuse_extensions(args, kind)
    spec = body.KINDS[kind]
    stem, path, where = _existing(kind, args, bundle)

    doc = common.open_concept(path, CLAIMS[kind]["type"].lower())
    _require_type(doc, kind, where)
    keys, told = _container_status(kind, args, doc, stem)
    block = _block_of(doc, kind, where, "set")
    block.items, written = _materialised(kind, stem, block.items)
    index = _index_of(block.items, args.id, kind, where)
    entry = block.items[index]

    touched = _given(kind, args)
    if args.text is not None:
        touched.insert(0, "text")
    if not touched and told is None:
        raise stage.Refused(
            f"{where}: nothing to set on {args.id}\n"
            f"fix:  pass --text, or one of the item's own field flags. A `set` "
            f"that changed nothing would still re-stamp provenance, which is a "
            f"claim about a person's confirmation that nobody made")

    changed = list(touched)
    if told is not None:
        changed.append(told)
    # An item is restated only where the item changed. A `set` given nothing but
    # `--concept-status` is amending the concept's provenance and has not touched
    # the claim, so the claim keeps its own bytes - which is the same rule
    # _materialised follows for an item it left alone.
    if touched:
        fields = _fields(kind, args, base=entry.fields)
        if CLAIMS[kind]["provenance"] == "item" and args.status is None:
            fields["status"] = "inferred"
            changed.append("status: inferred")
        _refuse_metric(bundle, fields.get("metric"))
        # The id is the locator here and never a value: changing it would
        # repoint every view naming it, which is the defect the materialisation
        # closes.
        fields["id"] = args.id
        _checked_item(kind, fields)
        text = entry.text if args.text is None else args.text
        block.items[index] = body.item(text, fields, spec["order"])
    doc.body = body.replace(doc.body, block, block.items)
    return _spliced(stage.Changeset(), doc, path, bundle, kind, args.id,
                    _log_row(f"Set {kind} {args.id} in {where}",
                             ", ".join(changed), written),
                    keys=keys)


def item_rm(kind, args):
    """Remove one item, and refuse while a view still selects it."""
    bundle = common.bundle_root(args.bundle)
    _refuse_extensions(args, kind)
    stem, path, where = _existing(kind, args, bundle)

    doc = common.open_concept(path, CLAIMS[kind]["type"].lower())
    _require_type(doc, kind, where)
    block = _block_of(doc, kind, where, "remove")
    block.items, written = _materialised(kind, stem, block.items)
    index = _index_of(block.items, args.id, kind, where)
    _refuse_selected(bundle, args.id, kind)
    gone = block.items.pop(index)
    doc.body = body.replace(doc.body, block, block.items)
    return _spliced(stage.Changeset(), doc, path, bundle, kind, args.id,
                    _log_row(f"Removed {kind} {args.id} from {where}",
                             gone.text, written))


def item_mv(kind, args):
    """Reorder one item within its block.

    Ids stay where they are, which is what the materialisation bought: after it,
    a position is presentation and nothing downstream reads one.
    """
    bundle = common.bundle_root(args.bundle)
    _refuse_extensions(args, kind)
    stem, path, where = _existing(kind, args, bundle)

    doc = common.open_concept(path, CLAIMS[kind]["type"].lower())
    _require_type(doc, kind, where)
    block = _block_of(doc, kind, where, "move")
    block.items, written = _materialised(kind, stem, block.items)
    index = _index_of(block.items, args.id, kind, where)
    _refuse_move(args.to, len(block.items), "the block")
    block.items.insert(args.to - 1, block.items.pop(index))
    doc.body = body.replace(doc.body, block, block.items)
    return _spliced(stage.Changeset(), doc, path, bundle, kind, args.id,
                    _log_row(f"Moved {kind} {args.id} in {where}",
                             f"position {index + 1} to {args.to}", written))


def _existing(kind, args, bundle):
    """(stem, path, where) for a verb that cannot create the concept it needs."""
    stem = _stem(kind, args)
    path = common.path_of(bundle, CLAIMS[kind]["type"], stem)
    where = _where(kind, stem)
    if not os.path.exists(path):
        _refuse_missing(kind, bundle, stem, where)
    return stem, path, where


def _titled(stem):
    """A stem as a document title. First letter up, hyphens out, nothing else.

    Not `.title()`, which turns `aws-certifications` into `Aws Certifications`.
    """
    words = str(stem).replace("-", " ").replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def _new_concept(bundle, kind, title, first, status):
    """A whole new owning concept, holding the block and its first item.

    Created rather than refused because the catalogue has no verb that creates
    either of these two types - `career.py` covers Project, Role, Organisation
    and Education - and `init_bundle.py` scaffolds neither, so on a fresh bundle
    a claim addressed at one would have nowhere to live. It is the
    `--new-capability` precedent: the thing and the file that legitimises it land
    in one changeset, because two commands leave a window in which the bundle
    fails its own gate.

    `status` defaults to `inferred` rather than confirmed. For a Certification
    Status this is the provenance of every credential in it, and a command cannot
    know that a person has confirmed anything - so confirmation is something the
    caller has to ask for, with `--concept-status confirmed`.
    """
    claim = CLAIMS[kind]
    values = common.without_none({
        "title": title,
        "description": claim["description"],
        "timestamp": common.stamp(),
        "status": status,
    })
    common.checked(claim["type"], values)
    text = body.add_block("", body.KINDS[kind]["heading"], first.lines)
    return common.emit(bundle, claim["type"], values, text)


# --- what a view still selects ---------------------------------------------------

# A view is `<stem>.view.md`, which is the suffix okf_compile.concepts() itself
# filters tailoring/ on - so this reads exactly the files that reach the record.
VIEW_SUFFIX = ".view.md"


def _view_files(bundle):
    """Every view on disk: the working copies, and the frozen ones in the archive.

    Both are read. A frozen view is the record of what was actually sent, and an
    id it names must not stop resolving because the working copy moved on.
    """
    out = []
    for parts in (("tailoring", "targets"), ("tailoring", "applications")):
        root = os.path.join(str(bundle), *parts)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(name for name in dirnames
                                 if not name.startswith("."))
            for name in sorted(filenames):
                if name.endswith(VIEW_SUFFIX):
                    out.append(os.path.join(dirpath, name))
    return out


def _selected(meta):
    """Every item id a view's frontmatter names.

    Three places, all of them slug lists: `include[].achievements`,
    `include[].skills` and the view's own top-level `skills`. `include[].ref` is
    a project or engagement id rather than an item's, so it is not one of them.
    """
    out = []
    for entry in meta.get("include") or ():
        if not isinstance(entry, dict):
            continue
        for key in ("achievements", "skills"):
            value = entry.get(key)
            if isinstance(value, (list, tuple)):
                out.extend(str(item) for item in value)
    value = meta.get("skills")
    if isinstance(value, (list, tuple)):
        out.extend(str(item) for item in value)
    return out


def _refuse_selected(bundle, ident, kind):
    """Say no while a view still selects the item being removed.

    This is the refusal that pays for `rm`. `urs/resolve.py` keeps only the ids a
    view names and drops the rest, so removing a selected one fails nowhere: the
    view renders with one bullet fewer, or - while ids were positional - with its
    neighbour's sentence in place of the one that was chosen.

    Every kind is scanned against all three lists rather than only the one that
    can hold it today. An id is an id, and a check that knew credentials are not
    selectable is the line that goes stale when they become so.
    """
    holders = []
    for path in _view_files(bundle):
        try:
            doc = concept.read(path)
        except concept.Unsplicable:
            # A view this layer cannot parse is one somebody has to fix by hand.
            # Refusing here would make `bullet rm` unusable over an unrelated
            # file's duplicate key; skipping it means an id in it is not seen,
            # which is the honest weakness of a local check.
            continue
        if ident in _selected(doc.meta):
            holders.append(
                os.path.relpath(path, str(bundle)).replace(os.sep, "/"))
    if not holders:
        return
    raise stage.Refused(
        f"{ident}: still selected by {', '.join(holders)}\n"
        f"fix:  drop it from the view first. urs/resolve.py keeps only the ids "
        f"a view names and drops the rest, so removing this one does not fail - "
        f"the resume simply renders one {kind} fewer than the person chose")


# --- achievements/metrics.md, the one authored shape that is a table -------------
#
# Every other authored shape in the bundle is a blocks() block and body.py owns
# those. A metric is a row of a pipe table, so its splicer lives here rather than
# there: one row-level reader used by two verbs in one module is not a shape worth
# a second parser in the layer below.
#
# `okf_compile.metrics_table()` is the reader, and _rows() below is its conditions
# character for character - a line starting with `|`, no `---` in its first eight
# characters, three cells or more, a non-empty first cell that is not the word
# `metric`. A row this module could not see is a duplicate it would happily add.

METRICS_STEM = "metrics"


def _cells(line):
    """One row's cells, as metrics_table splits them."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _rows(text):
    """{slug: (line index, cells)} - every row okf_compile.metrics_table reads.

    Keyed on `body.compile_slug`, which is okf_compile.slug: that is what makes
    two rows collide, so it is what a duplicate has to be judged on.
    """
    out = {}
    for index, line in enumerate(text.split("\n")):
        if not line.startswith("|") or "---" in line[:8]:
            continue
        cells = _cells(line)
        if len(cells) < 3 or not cells[0] or cells[0].lower() == "metric":
            continue
        out[body.compile_slug(cells[0])] = (index, cells)
    return out


def _table(text):
    """(the header's line index, one past the table's last line, its width).

    (None, None, 0) where there is no header row. Separate from _rows() because
    the two answer different questions: _rows is what the compile reads and has
    to be exact, this is where a new row goes and only has to be right about the
    one table this file holds.
    """
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if not cells or cells[0].lower() != "metric":
            continue
        end = index + 1
        while end < len(lines) and lines[end].startswith("|"):
            end += 1
        return index, end, len(cells)
    return None, None, 0


def _rendered(cells):
    """One row. metrics_table strips each cell, so the padding is for a reader."""
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def _cell(flag, value, required=False):
    """One caller-supplied cell: whitespace collapsed, emptiness refused.

    Collapsed the same way `body.item` collapses an item's text and
    `bookkeeping.index_entry` an index row's title, for the same reason: a
    markdown line has no escape for a newline, so the only repair available is
    to not have one.

    Applied to what a caller passed and never to a cell read back out of the
    file. `metrics_table` strips a cell but does not collapse inside it, so
    re-collapsing somebody's `5  s` would change a byte this command was not
    asked about.
    """
    if value is None:
        return None
    value = bookkeeping._one_line(value)
    if required and not value:
        raise stage.Refused(
            f"{flag}: empty\n"
            f"fix:  okf_compile.metrics_table skips a row whose first two "
            f"cells are not both filled in, so this would write a row nothing "
            f"reads and no bullet can name")
    return value


def _sized(values, width):
    """`values` as exactly `width` cells - padded, or trimmed to the table."""
    return (list(values) + [""] * width)[:width]


def _refuse_pipes(pairs):
    """A `|` in a cell ends it, and there is no escape a naive split honours.

    Refused rather than escaped: metrics_table splits the row on `|` with no
    notion of `\\|`, so an escaped pipe would still split it and every cell after
    the value would shift by one. A value this cannot write is one the command
    must not accept.
    """
    for flag, value in pairs:
        if value is not None and "|" in str(value):
            raise stage.Refused(
                f"{flag} {value!r}: a `|` ends a cell\n"
                f"fix:  drop it. okf_compile.metrics_table splits the row on "
                f"`|` and honours no escape, so this value would be read as "
                f"two columns and every cell after it would shift by one")


def _metrics_path(bundle):
    """achievements/metrics.md, or a refusal naming what writes it."""
    return common.require_file(
        common.path_of(bundle, "Metric Set", METRICS_STEM), "metrics file",
        "fix:  init_bundle.py scaffolds achievements/metrics.md with its "
        "`| Metric | Value | Evidence | Source |` header. `okf migrate <path>` "
        "brings an older bundle up to the current layout")


def _refuse_metric(bundle, name):
    """Refuse a bullet naming a metric that is not a row in the table.

    Without this the mistake surfaces as a crash. `okf_compile.bullets()` raises
    `Problem` on it - *"bullet names metric X, which is not a row in
    achievements/metrics.md"* - in the middle of the next compile, which is what
    `okf score` calls on a tailoring run's hot path.

    Read raw rather than through concept.read: this needs the slugs and nothing
    else, and metrics_table itself scans the whole file line by line.
    """
    if not name:
        return
    path = _metrics_path(bundle)
    with open(path, encoding="utf-8", newline="") as handle:
        rows = _rows(handle.read().replace("\r\n", "\n"))
    if body.compile_slug(name) in rows:
        return
    known = ", ".join(sorted(repr(cells[0]) for _, cells in rows.values()))
    raise stage.Refused(
        f"--metric {name!r}: not a row in achievements/metrics.md - it holds "
        f"{known or 'no rows at all'}\n"
        f"fix:  `okf metric add --name \"{name}\" --value \"...\"` records the "
        f"number once, or name a row that is there. The number lives in that "
        f"table and a bullet points at it rather than restating it, which is "
        f"what stops a rewritten clause inflating it")


def _evidence(bundle, stem):
    """A project stem as the markdown link the Evidence column holds.

    The link text is the stem rather than the project's title, because a title
    may hold a `|` or a `]` and either would break the row or the link - and the
    stem is what metrics_table reads back out of the target anyway.
    """
    if stem is None:
        return None
    if not str(stem).strip():
        # `--evidence ""` empties the cell, the way `--source ""` does. An
        # unsourced number is worth recording as unsourced; a stem that cannot
        # be derived from an empty string is not the message to give for it.
        return ""
    stem = common.stem_of(stem, stem, "projects")
    common.require_file(
        common.path_of(bundle, "Project", stem), "project",
        "fix:  --evidence names a concept in projects/, without its .md. "
        "validate_bundle.py resolves every link in the bundle and reports a "
        "missing target as `BROKEN LINK`, so this would go red at ship time")
    return f"[{stem}](../projects/{stem}.md)"


def _refuse_metric_extensions(args):
    """`--set` on a table row, which has four columns and no room for a fifth."""
    if not getattr(args, "set", None):
        return
    raise stage.Refused(
        "--set is not something a metric row takes\n"
        "fix:  the table's columns are Metric, Value, Evidence and Source, and "
        "okf_compile.metrics_table reads those and no others. A fifth would be "
        "a column nothing reads. Put an extension key on the concept instead")


def metric_add(args):
    """Add a row to achievements/metrics.md - one number, recorded once."""
    bundle = common.bundle_root(args.bundle)
    _refuse_metric_extensions(args)
    path = _metrics_path(bundle)
    _refuse_pipes((("--name", args.name), ("--value", args.value),
                   ("--source", args.source)))
    name = _cell("--name", args.name, required=True)
    value = _cell("--value", args.value, required=True)
    source = _cell("--source", args.source)
    doc = common.open_concept(path, "metrics file")
    header, end, width = _table(doc.body)
    if header is None:
        raise stage.Refused(
            "achievements/metrics.md: no `| Metric | ... |` header, so there "
            "is no table to add a row to\n"
            "fix:  the file holds one pipe table with a header row - "
            "init_bundle.py scaffolds `| Metric | Value | Evidence | Source |`. "
            "Write the header and this command fills it")
    rows = _rows(doc.body)
    key = body.compile_slug(name)
    if key in rows:
        raise stage.Refused(
            f"--name {name!r}: already a row, written {rows[key][1][0]!r}\n"
            f"fix:  `okf metric set --name \"{name}\"` amends it. Two rows "
            f"slugging to `{key}` are one row to okf_compile.metrics_table, "
            f"which keys them by slug - so the second silently replaces the "
            f"first and every bullet pointing at the number gets whichever was "
            f"read last")
    width = max(width, 3)
    if source is not None and width < 4:
        raise stage.Refused(
            f"--source: this table has {_plural(width, 'column')}, so there is "
            f"nowhere to write it\n"
            f"fix:  add a `Source` column to the header first, or drop --source")

    cells = _sized([name, value, _evidence(bundle, args.evidence) or "",
                    source or ""], width)
    lines = doc.body.split("\n")
    lines.insert(end, _rendered(cells))
    doc.body = _terminated("\n".join(lines))

    change = stage.Changeset()
    common.stage_concept(change, path,
                         concept.set_key(doc, "timestamp", common.stamp()))
    common.stage_log(change, bundle,
                     f"Added metric {name!r} to achievements/metrics.md "
                     f"- {value}")
    change.record_id("metric", f"met_{key}")
    return change


def metric_set(args):
    """Amend one row's value, evidence or source. Every other byte stays put."""
    bundle = common.bundle_root(args.bundle)
    _refuse_metric_extensions(args)
    path = _metrics_path(bundle)
    _refuse_pipes((("--value", args.value), ("--source", args.source)))
    name = _cell("--name", args.name, required=True)
    value = _cell("--value", args.value, required=True)
    source = _cell("--source", args.source)
    doc = common.open_concept(path, "metrics file")
    _, _, width = _table(doc.body)
    rows = _rows(doc.body)
    key = body.compile_slug(name)
    if key not in rows:
        known = ", ".join(sorted(repr(cells[0]) for _, cells in rows.values()))
        raise stage.Refused(
            f"--name {name!r}: not a row in achievements/metrics.md - it "
            f"holds {known or 'no rows at all'}\n"
            f"fix:  `okf metric add` writes a new row. The name is the row's "
            f"identity - metrics_table keys on a slug of it and derives "
            f"`met_<slug>` as the metric's id - so this command amends a row "
            f"rather than renaming one")
    index, cells = rows[key]
    new = _sized(cells, max(width, len(cells), 3))
    changed = []
    if value is not None:
        new[1] = value
        changed.append("value")
    if args.evidence is not None:
        new[2] = _evidence(bundle, args.evidence)
        changed.append("evidence")
    if source is not None:
        if len(new) < 4:
            raise stage.Refused(
                f"--source: this table has {_plural(len(new), 'column')}, so "
                f"there is nowhere to write it\n"
                f"fix:  add a `Source` column to the header first, or drop "
                f"--source")
        new[3] = source
        changed.append("source")
    if not changed:
        raise stage.Refused(
            f"--name {name!r}: nothing to set\n"
            f"fix:  pass --value, --evidence or --source. The name itself is "
            f"the row's identity and this command does not rename one - "
            f"okf_compile derives the metric's id from it, so a rename would "
            f"repoint every bullet naming the number")

    lines = doc.body.split("\n")
    lines[index] = _rendered(new)
    doc.body = _terminated("\n".join(lines))

    change = stage.Changeset()
    common.stage_concept(change, path,
                         concept.set_key(doc, "timestamp", common.stamp()))
    common.stage_log(change, bundle,
                     f"Set metric {name!r} in achievements/metrics.md - "
                     f"{', '.join(changed)}")
    change.record_id("metric", f"met_{key}")
    return change


# --- registering the verbs -------------------------------------------------------

def register(nouns):
    """Four nouns, fourteen verbs. `commands.py` calls this with its subparsers."""
    for kind in ("bullet", "skill", "credential"):
        _register_claim(nouns, kind)
    _register_metric(nouns)


# Said once because two verbs of two nouns declare it, and because the help is
# the whole of what pre-empts the confusion: `--status` and `--concept-status`
# are two different `status` words meeting in one command, and okf_compile keeps
# them apart by name - a `# Held` entry's `status` says whether the
# certification is current, and the concept's says how well the bundle knows it.
_CONCEPT_STATUS = {
    "help": "the CONCEPT's provenance - confirmed, inferred or "
            "needs-verification. This is how well the bundle knows the claim, "
            "and it is what a view's provenance_floor tests. Not --status, "
            "which is a certification's own currency. Left out, it is unchanged",
}


def _locator(parser, kind):
    """The flag naming the concept a claim lives in.

    Required wherever there is no sensible default, which is bullet and
    credential. A Skill Set defaults to `competencies` because bundle-spec.md's
    layout names that one file.
    """
    claim = CLAIMS[kind]
    parser.add_argument(claim["flag"], dest=claim["attribute"],
                        default=claim["default"],
                        required=claim["default"] is None,
                        help=claim["flag_help"])


def _register_claim(nouns, kind):
    claim = CLAIMS[kind]
    parser, verbs = common.verb(nouns, kind, claim["help"])

    add = common.add_verb(verbs, "add", f"write a new {kind}",
                          functools.partial(item_add, kind))
    _locator(add, kind)
    add.add_argument("--text", required=True, help=claim["text_help"])
    for flag, attribute, _, default, help_text in FLAGS[kind]:
        add.add_argument(flag, dest=attribute, default=default, help=help_text)
    add.add_argument("--id",
                     help="the item's id - derived from its own text when left "
                          "out, and never positional")
    add.add_argument("--at", type=int,
                     help="1-based position to insert at (default: append)")
    if claim["creates"]:
        add.add_argument("--concept-title",
                         help=f"the title for a new {claim['type']} concept, "
                              f"where this command has to create one")

    setter = common.add_verb(verbs, "set", f"restate one {kind}",
                             functools.partial(item_set, kind))
    _locator(setter, kind)
    setter.add_argument("--id", required=True,
                        help=f"which {kind} - its id, never its position")
    setter.add_argument("--text", help="the sentence, restated whole")
    for flag, attribute, _, _, help_text in FLAGS[kind]:
        setter.add_argument(flag, dest=attribute, default=None, help=help_text)

    if claim["provenance"] == "concept":
        # On add and on set both, because this is where a skill's and a
        # credential's provenance lives and no other verb in the catalogue can
        # reach it. Absent, it changes nothing: a shared marker demoted by
        # default would withhold entries nobody touched.
        for parser_of in (add, setter):
            parser_of.add_argument("--concept-status", **_CONCEPT_STATUS)

    remove = common.add_verb(verbs, "rm", f"remove one {kind}",
                             functools.partial(item_rm, kind))
    _locator(remove, kind)
    remove.add_argument("--id", required=True, help=f"which {kind}")

    move = common.add_verb(verbs, "mv", f"reorder one {kind} in its block",
                           functools.partial(item_mv, kind))
    _locator(move, kind)
    move.add_argument("--id", required=True, help=f"which {kind}")
    move.add_argument("--to", type=int, required=True,
                      help="1-based position to move it to")
    return parser


def _register_metric(nouns):
    parser, verbs = common.verb(nouns, "metric",
                                "a verified number, recorded once")
    add = common.add_verb(verbs, "add", "add a row to achievements/metrics.md",
                          metric_add)
    add.add_argument("--name", required=True,
                     help="the metric's name - what a bullet's `metric:` names")
    add.add_argument("--value", required=True,
                     help="the number itself - \"5 min to under 1 s\"")
    add.add_argument("--evidence",
                     help="the projects/ concept stem the number came out of")
    add.add_argument("--source",
                     help="how it was established - a dashboard, an invoice, a "
                          "post-incident review, the person's own recall")

    setter = common.add_verb(verbs, "set",
                             "amend one row of achievements/metrics.md",
                             metric_set)
    setter.add_argument("--name", required=True, help="which row")
    setter.add_argument("--value", help="the number itself")
    setter.add_argument("--evidence",
                        help="the projects/ concept stem the number came from")
    setter.add_argument("--source", help="how it was established")
    return parser
