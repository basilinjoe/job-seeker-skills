"""The bundle's own housekeeping: the vocabulary, the questions, the log, the indexes.

Five verbs over four nouns, and none of them writes a concept. `capability add`
lists one term in `framework/capability-vocabulary.md`; `question add|resolve` work
`resume-generation/open-questions.md`, which mode-gaps.md and mode-refresh.md read
as their agenda; `log` dates something the catalogue has no verb for, which both
mode-refresh.md and mode-ship.md instruct as a step of their own; and `reindex` is
the repair for the one failure mode stage.py documents and no gate reports.

Nothing here judges a value - that is schema.py - and nothing here formats one -
that is concept.py and body.py. What belongs to this layer is the class of rule
that needs the bundle in hand: does the vocabulary already list this term, is there
a heading to file it under, does the concept a question points at exist, and does
an index still agree with the directory beside it.
"""

import datetime
import os

from . import body, bookkeeping, common, schema, stage

# The section a question lands in when nobody says. `# Blocking` is the one
# mode-gaps.md works first, and a question whose section was guessed wrong is
# still read - where a question written to a section that does not exist is not
# written at all.
DEFAULT_SECTION = "Blocking"

# The file both question verbs work through. Not in common.DIRECTORIES: that map
# is type -> directory, and `Open Questions` is one file rather than a directory
# of concepts - the same way achievements/metrics.md is.
QUESTIONS = ("resume-generation", "open-questions.md")

QUESTIONS_FIX = ("fix:  init_bundle.py scaffolds it with # Blocking, # Missing "
                 "metrics and # Not yet explored, and `okf migrate` adds it to an "
                 "older bundle. It is the file mode-gaps.md works through, so a "
                 "bundle without one has no agenda")


def _questions(bundle):
    return os.path.join(str(bundle), *QUESTIONS)


def _relative(bundle, path):
    """A path as a log row and a report name it: bundle-relative, `/` separated.

    Backslashes are not written into a log or an index. bundle-spec.md's own
    paths are `/` separated, and a bundle is portable by design - so a row
    naming a path the Windows way is a row that reads as one filename on the
    machine that wrote it and as another on the machine that opens it next.
    """
    return os.path.relpath(str(path), str(bundle)).replace(os.sep, "/")


def _no_extension_keys(args, noun):
    """`--set` has nowhere to go on any of these five verbs.

    common.add_verb gives every verb the same four flags, which is what stops
    them drifting apart - and one of them writes an extension key into a
    concept's frontmatter. None of these commands writes frontmatter at all, so
    a `--set` here would be accepted and dropped, which is worse than being
    refused: the person is left believing a key landed.
    """
    if common.extension_keys(args.set):
        raise stage.Refused(
            f"--set: `okf {noun}` writes no frontmatter, so there is no key to "
            f"set\n"
            f"fix:  drop it. --set adds an extension key to a concept - "
            f"`okf project set --set client_reference=...`. This command changes "
            f"a vocabulary, the open questions, the log or an index")


def _body_text(lines):
    """A spliced body from its lines, ending in exactly one newline.

    concept.Concept.text() puts the body straight after the frontmatter's gap
    and adds nothing of its own, so a body that lost or gained a trailing
    newline here is a byte this command changed and nobody asked about. A
    trailing blank line the author wrote is theirs and is left alone.
    """
    text = "\n".join(lines)
    if not text or text.endswith("\n"):
        return text
    return text + "\n"


# --- capability add -------------------------------------------------------------

def _readable_term(term):
    """True when the row this would write reads back as exactly this term.

    Round-tripped through common.vocabulary_terms - which is validate_bundle.py's
    own reader, list-item regex and fence toggle included - rather than checked
    against a second regex spelt here.

    This refusal is load-bearing rather than tidy. The gate extracts a term with
    `` `([a-z0-9-]+)` ``, so `Data_Sovereignty` in backticks parses as no term at
    all: the row lands, the file looks right to a person reading it, and the gate
    lists nothing from it. Capabilities are the primary matching axis and compare
    as exact strings, so from then on every concept naming the term is
    unchecked - and a synonym does not fail, it silently stops matching. Both
    halves of that are invisible, which is why the shape is refused at the point
    the row is written rather than reported later.
    """
    return common.vocabulary_terms("- `%s`" % term) == {term}


def capability_add(args):
    """List one or more terms in the capability vocabulary, under an existing theme.

    Standalone, because until now a term could only be added as a side effect of
    `okf project add --new-capability` - so extending the vocabulary ahead of the
    evidence meant hand-editing the one file whose whole job is to be canonical.
    """
    bundle = common.bundle_root(args.bundle)
    _no_extension_keys(args, "capability add")
    terms = common.first_appearance(args.term)
    path = common.require_file(
        common.vocabulary_path(bundle), "capability vocabulary",
        "fix:  create it with a theme heading per group - bundle-spec.md names "
        "it, and `okf migrate` writes one into an older bundle. While it lists "
        "nothing, validate_bundle.py leaves capabilities unchecked")
    existing, _ = common.existing_capabilities(bundle)
    for term in terms:
        if not _readable_term(term):
            raise stage.Refused(
                f"capability {term!r}: not the shape a capability takes\n"
                f"fix:  lowercase words joined by hyphens - `data-sovereignty`. "
                f"validate_bundle.py extracts a term with `([a-z0-9-]+)` inside "
                f"backticks, so a capital or an underscore is not read back as a "
                f"term at all: the row lands and the vocabulary still lists "
                f"nothing from it")
        if term in existing:
            raise stage.Refused(
                f"capability {term!r} is already in {_relative(bundle, path)}\n"
                f"fix:  nothing to do - it is already there to reuse. This file "
                f"is the canonical list, and a term listed twice is the one thing "
                f"it must not have: two rows to keep in step, and a reader who "
                f"cannot tell which theme owns the term")
    # Refuses a theme that is not a heading in the file, and names the ones that
    # are - so the splice is where that rule lives rather than repeated here.
    text = common.vocabulary_with(path, terms, args.theme)

    change = stage.Changeset()
    # kind="concept", not "companion": in this one command the vocabulary IS the
    # authored half. Nothing regenerates it from the tree, so it is the file that
    # must publish before the log row that describes it.
    common.stage_concept(change, path, text)
    # Logged because a change to this file is a change to what every future
    # ranking sees: capabilities are the primary matching axis and compare as
    # exact strings, so the day a term entered the vocabulary is the day the
    # scoring of everything naming it changed.
    listed = ", ".join("`%s`" % term for term in terms)
    common.stage_log(
        change, bundle,
        'Added capability %s to %s under "%s"'
        % (listed, _relative(bundle, path), args.theme))
    change.record_id("capability", ", ".join(terms))
    return change


# --- question add ---------------------------------------------------------------

# Where `--about` looks for the concept a question is about: every directory a
# concept type lives in, plus the two holding concepts no type in that map names.
# Ordered, so a refusal names them in the order they were searched.
ABOUT_DIRECTORIES = common.first_appearance(
    list(common.DIRECTORIES.values()) + ["profile", "open-source"])


def _about_link(bundle, stem):
    """A relative markdown link from the questions file to one concept.

    Written rather than merely named, because the answer needs somewhere to land
    and a stem in prose is not somewhere. The file sits in `resume-generation/`,
    so every link out of it starts `../`.

    Refused when nothing is there: validate_bundle.py reports a broken link as a
    hard error, so a guessed stem does not fail this command, it fails the whole
    bundle at the next gate - and the person who typed it is not the one who
    runs that.
    """
    if not stem.strip() or os.path.basename(stem) != stem or stem in (".", ".."):
        # A path here would write a link out of the bundle, or into a directory
        # this command never searched. schema.SLUG admits `/` because an `id` may
        # carry one; a stem naming a file may not, which is the same line
        # common.stem_of draws for a new concept.
        raise stage.Refused(
            f"--about {stem!r}: not a concept stem - a stem names one file, not "
            f"a path\n"
            f"fix:  pass the file's stem without its directory and without its "
            f".md - `--about care-platform`")
    filename = stem + ".md"
    # The gate reads a link with `\\[([^\\]]+)\\]\\(([^)]+)\\)`, so a filename
    # carrying a space or a parenthesis reaches it as a different target. One
    # refusal for that, in bookkeeping, and this is the second caller of it.
    bookkeeping._refuse_unlinkable(filename)
    found = [directory for directory in ABOUT_DIRECTORIES
             if os.path.isfile(os.path.join(str(bundle), *directory.split("/"),
                                            filename))]
    if not found:
        searched = ", ".join(name + "/" for name in ABOUT_DIRECTORIES)
        raise stage.Refused(
            f"--about {stem!r}: no concept named {filename} in {searched}\n"
            f"fix:  name a concept that is there, without its .md. A question "
            f"linking to a file that is not there is a BROKEN LINK error from "
            f"validate_bundle.py, so the guess fails the bundle rather than this "
            f"command")
    if len(found) > 1:
        raise stage.Refused(
            f"--about {stem!r}: {filename} is in "
            f"{' and '.join(name + '/' for name in found)}\n"
            f"fix:  two concepts share the stem, so nothing here can know which "
            f"the question is about. Rename one, or ask the question without "
            f"--about and name the concept in the text")
    return "[%s](../%s/%s)" % (stem, found[0], filename)


def _section_titles(text):
    """{line index: the heading's title as written}, for every section."""
    return {index: title for index, _, title in body.headings(text)}


def question_add(args):
    """Append one question as a list row under an existing section."""
    bundle = common.bundle_root(args.bundle)
    _no_extension_keys(args, "question add")
    path = common.require_file(_questions(bundle), "open questions file",
                               QUESTIONS_FIX)
    doc = common.open_concept(path, "open questions file")

    # A newline in the question would split the row and leave its second half as
    # loose prose outside the list - the defect bookkeeping._one_line exists for
    # in an index entry and a log row, and a markdown list row has no escape for
    # a newline either.
    text = bookkeeping._one_line(args.text)
    if not text:
        raise stage.Refused(
            "--text is empty, so there is no question to record\n"
            "fix:  pass the question as one sentence - `--text \"What was p95 "
            "before the rewrite?\"`. An empty row in this file is a question "
            "nobody can answer and nobody can resolve")

    span = body.section(doc.body, args.section)
    if span is None:
        known = (", ".join(repr(title) for title in
                           _section_titles(doc.body).values()) or "none at all")
        raise stage.Refused(
            f"{_relative(bundle, path)}: no section named {args.section!r} - it "
            f"has {known}\n"
            f"fix:  --section names a heading already in the file, or add the "
            f"heading by hand first. mode-gaps.md works these sections in order, "
            f"so a question filed under a heading nobody reads is one nobody "
            f"answers")
    heading, start, end = span
    # The heading's title as the file spells it, read before the splice: the log
    # row says which section the question was filed under, and --section matches
    # case-insensitively, so what was typed is not necessarily what is written.
    section = _section_titles(doc.body).get(heading, args.section)

    row = "- " + text
    # `is not None`, not truthiness: `--about ""` was given and names no concept,
    # so it is refused rather than quietly writing a row with no link.
    if args.about is not None:
        row += " - " + _about_link(bundle, args.about)

    lines = body.lines_of(doc.body)
    # Appended under whatever the section already says, at its last line with
    # content - bookkeeping.log_entry's rule for a day's entries, applied to a
    # section. Prepending would put the newest question first in a file two mode
    # files read top to bottom.
    last = heading
    for index in range(start, end):
        if lines[index].strip():
            last = index
    joining = last != heading and bookkeeping.LIST_ITEM.match(lines[last])
    lines[last + 1:last + 1] = [row] if joining else ["", row]
    doc.body = _body_text(lines)

    change = stage.Changeset()
    common.stage_concept(change, path, doc.text())
    # The row goes into log.md as it is written here. An upward link in it -
    # `--about` writes one, and it resolves from resume-generation/ and nowhere
    # else - would be a BROKEN LINK error from the root. bookkeeping.log_entry
    # flattens it, so the rule lives with the file it protects.
    common.stage_log(change, bundle,
                     "Added an open question under %s - %s" % (section, text))
    # The row's text, which is the only handle this file gives a question: it has
    # no id, and `question resolve --match` takes a substring of exactly this.
    change.record_id("question", text)
    return change


# --- question resolve -----------------------------------------------------------

def _rows(text):
    """Every question the file lists: (line index, the row's own text).

    A markdown list item outside a fence - bookkeeping's rule for an index row
    and validate_bundle.py's for a vocabulary term. This file is one people paste
    examples into, and a fenced example of what a question looks like is not a
    question.
    """
    out = []
    for index, line, fenced in bookkeeping._scan(text.split("\n")):
        if fenced:
            continue
        match = bookkeeping.LIST_ITEM.match(line)
        if match:
            out.append((index, line[match.end():].strip()))
    return out


def _enclosing_section(text, index):
    """The title of the heading a row sits under, or None.

    Recorded in the log row because the section is the only thing this file says
    about a question besides its text, and the log row is the whole of what
    survives the strike.
    """
    title = None
    for at, _, name in body.headings(text):
        if at < index:
            title = name
    return title


def question_resolve(args):
    """Strike one answered question from the file, and record it in log.md.

    The row is removed rather than struck through or marked resolved, and that is
    a decision recorded in the plan. `log.md` is the bundle's record of what
    changed; a resolved question kept in the file with a marker is a second place
    for the same fact to be wrong - and the file's whole job is to be the list of
    what is still open, which a resolved row makes false.

    Matched on a substring rather than a position. A row number changes the
    moment somebody adds a question above it, and the wrong question struck from
    the record is a question nobody asks again.
    """
    bundle = common.bundle_root(args.bundle)
    _no_extension_keys(args, "question resolve")
    path = common.require_file(_questions(bundle), "open questions file",
                               QUESTIONS_FIX)
    doc = common.open_concept(path, "open questions file")

    wanted = str(args.match).strip().lower()
    if not wanted:
        raise stage.Refused(
            "--match is empty, so it matches every open question\n"
            "fix:  pass a substring of the question's own text - enough of it to "
            "pick out one row")
    rows = _rows(doc.body)
    hits = [(index, text) for index, text in rows if wanted in text.lower()]
    if not hits:
        raise stage.Refused(
            f"--match {args.match!r}: no open question says that - "
            f"{_relative(bundle, path)} lists {len(rows)}\n"
            f"fix:  match on a substring of the row's own text, case does not "
            f"matter. Nothing was changed, so the question is still open - open "
            f"the file if it is not clear which row was meant")
    if len(hits) > 1:
        listing = "\n".join("  - " + text for _, text in hits)
        raise stage.Refused(
            f"--match {args.match!r}: matches {len(hits)} open questions\n"
            f"{listing}\n"
            f"fix:  pass a longer substring that picks out one of them. This "
            f"command will not resolve by position, and striking the wrong "
            f"question leaves one nobody asks again while the record says it was "
            f"answered")

    at, text = hits[0]
    section = _enclosing_section(doc.body, at)
    lines = body.lines_of(doc.body)
    # The blank line above goes with the row when the row was the only thing in
    # its section, because that blank line is the one `question add` inserted
    # ahead of it. Without this, add-then-resolve leaves a file that differs from
    # the one it started as by a blank line nobody typed.
    drop = [at]
    above, below = at - 1, at + 1
    if (above > 0 and below < len(lines)
            and not lines[above].strip() and not lines[below].strip()):
        drop.append(above)
    lines = [line for index, line in enumerate(lines) if index not in set(drop)]
    doc.body = _body_text(lines)

    change = stage.Changeset()
    common.stage_concept(change, path, doc.text())
    # The struck row is copied verbatim, upward link and all, and
    # bookkeeping.log_entry flattens it on the way in. That link resolves from
    # resume-generation/ and from nowhere else, and log.md is at the bundle root:
    # copying it as a link turned the bundle red over the one file this command
    # had just tidied.
    message = ("Resolved an open question under %s - %s" % (section, text)
               if section else "Resolved an open question - %s" % text)
    if args.answer:
        # How it was resolved is the part worth keeping: the question is about to
        # leave the file, and the log row is where the answer stays.
        message += " - answer: " + bookkeeping._one_line(args.answer)
    common.stage_log(change, bundle, message)
    change.record_id("question", text)
    return change


# --- log ------------------------------------------------------------------------

def _day(value):
    """`value` as a `YYYY-MM-DD` day, or a refusal saying which way it is not one."""
    # schema.DATE admits 2019 and 2019-04 as well, because the format reads
    # precision from what was written. A log heading is a day, so only the full
    # one will do - hence the length beside the shape.
    if not schema.DATE.match(str(value)) or len(str(value)) != 10:
        raise stage.Refused(
            f"--date {value!r}: not a date\n"
            f"fix:  write it as YYYY-MM-DD - `--date 2026-08-29`. The row is "
            f"filed under a `## <date>` heading in log.md, and a heading in any "
            f"other shape is a second heading for a day that already has one")
    try:
        datetime.date.fromisoformat(str(value))
    except ValueError:
        raise stage.Refused(
            f"--date {value!r}: not a day that exists\n"
            f"fix:  check the month and the day. log.md is the bundle's "
            f"chronology, and a heading nobody can put on a calendar makes every "
            f"row under it undatable")
    return str(value)


def log_write(args):
    """Append one row to log.md under a day's heading.

    The simplest verb, and it exists because the catalogue will never cover
    everything: a person or an agent doing something no verb names still has to
    be able to date it. mode-refresh.md and mode-ship.md both instruct a log
    entry as a step of their own, and until now that meant hand-editing the file.
    """
    bundle = common.bundle_root(args.bundle)
    _no_extension_keys(args, "log")
    if not bookkeeping._one_line(args.message):
        raise stage.Refused(
            "--message is empty, so there is nothing to record\n"
            "fix:  say what happened in one line - `--message \"Confirmed the "
            "p95 figure with the platform team\"`. An empty row dates nothing")
    # `is not None`, not truthiness: `--date ""` was given and is not a date, so
    # it is refused rather than quietly treated as today.
    when = _day(args.date) if args.date is not None else None
    # stage_log stages nothing when log.md is absent, which is right for a
    # command whose subject is a concept - and wrong for this one, whose whole
    # subject is the row. Required here so an absent log is said out loud rather
    # than reported as a command that changed no files.
    common.require_file(
        os.path.join(str(bundle), "log.md"), "log.md",
        "fix:  log.md is one of the two reserved filenames bundle-spec.md names, "
        "and init_bundle.py writes it. Create it with a `# <date> - ...` heading, "
        "or run `okf migrate` on an older bundle")
    change = stage.Changeset()
    common.stage_log(change, bundle, args.message, when=when)
    change.record_id("date", common.today(when))
    return change


# --- reindex --------------------------------------------------------------------

# Every directory bundle-spec.md gives an index.md, in the order reindex walks
# them. Built from common.DIRECTORIES rather than retyped, plus the six the
# layout has that no concept type names.
#
# The bundle root is absent on purpose. Its index.md holds a map table linking
# every directory, not a list of concepts, so its rows are not concept rows -
# and the two .md files beside it, getting-started.md and log.md, are not
# concepts either. Treating them as one would list them as evidence.
INDEXED = common.first_appearance(
    list(common.DIRECTORIES.values())
    + ["profile", "framework", "sources", "open-source", "resume-generation",
       "tailoring", "tailoring/applications"])

ARCHIVE = "tailoring/applications"


def _indexed_directories(bundle):
    """INDEXED, plus each year directory the archive has grown.

    Every immediate subdirectory, not those matching `\\d{4}`. A directory
    somebody named otherwise still holds applications and still has an index,
    and silently skipping it is the exact failure mode this command exists to
    repair.
    """
    out = list(INDEXED)
    root = os.path.join(str(bundle), *ARCHIVE.split("/"))
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            if os.path.isdir(os.path.join(root, name)):
                out.append("%s/%s" % (ARCHIVE, name))
    return out


def _broken(index, text):
    """Every link target in this index that resolves to nothing.

    Resolved relative to the file holding the link, which is how
    validate_bundle.py resolves one: the gate is the reader whose opinion decides
    whether a row is broken, and a broken row is the only line this command is
    licensed to delete.
    """
    out = []
    directory = os.path.dirname(str(index))
    for _, _, target in bookkeeping.index_rows(text):
        clean = target.split("#")[0]
        if not clean or "://" in clean or clean.startswith("mailto:"):
            continue
        if os.path.exists(os.path.normpath(os.path.join(directory, clean))):
            continue
        out.append(clean)
    return common.first_appearance(out)


def _unlisted(bundle, directory, text):
    """Every concept in `directory` its index does not list.

    (filename, title, description) - the row's own content, taken from the
    concept's frontmatter rather than invented here.

    Presence is tested exactly as bookkeeping tests it, on the link target in
    parentheses, so this command cannot report having added a row that
    index_repair then declines to add. Its known limits come along with that: a
    row whose link carries an anchor or a title attribute is not recognised as
    present, and the concept gains a second row.

    A .md file with no frontmatter gets no row. common.concept_bodies skips what
    it cannot parse, and a file this layer cannot read is not one it should be
    writing a title for.
    """
    out = []
    for stem, _, meta, _ in common.concept_bodies(bundle, directory):
        filename = stem + ".md"
        if "(%s)" % filename in text:
            continue
        # A row's whole visible text is its title, so a concept with none would
        # be listed as an empty link - a row a reader cannot see or click.
        title = meta.get("title") or stem
        out.append((filename, title, meta.get("description") or ""))
    return out


def _repair(bundle, directory):
    """(index path, its whole new text, filenames added, targets dropped), or None.

    None when there is nothing to repair, and None when the directory has no
    index.md at all. That second case is validate_bundle.py's own warning about a
    missing file - a different fault - and writing one here would answer the
    warning without anybody having decided what the file should say.

    Both jobs are computed from the index as it stands, which is safe because
    they cannot overlap here: a dropped row's target does not exist, so it can
    never be the filename of a concept sitting in the directory.
    index_repair() runs the removals first anyway, so a rename that is both
    stays listed once.

    What it added and dropped is index_repair()'s own answer rather than this
    command's guess, so the report is what landed rather than what was intended.
    """
    index = bookkeeping.index_path(bundle, directory)
    if not os.path.exists(index):
        return None
    text, _ = bookkeeping._read(index)
    broken = _broken(index, text)
    missing = _unlisted(bundle, directory, text)
    if not broken and not missing:
        return None
    text, added, dropped = bookkeeping.index_repair(index, entries=missing,
                                                    drop=broken)
    if not added and not dropped:
        return None
    return index, text, added, dropped


def reindex(args):
    """Make every directory index agree with the directory beside it.

    The repair for the failure mode stage.py documents. A partial publish loses
    the derived half and keeps the authored one, by design - so what a torn write
    leaves is a concept its index.md does not list. **That state is silent**:
    validate_bundle.py checks that an index exists and that its links resolve,
    never that it lists every concept beside it. stage.py says outright that
    nothing reporting the quiet failure is an argument for this command existing.

    Two jobs, both mechanical, and nothing else. It does not reorder, retitle or
    rewrite a row that is already valid - bookkeeping.index_entry declines to for
    the same reason, and a command that reordered somebody's index would have
    changed something nobody asked it to.

    **It writes no log row, and that is the decision rather than an omission.**
    Every row in log.md is a record of a change to what the bundle says; this
    changes nothing it says, it makes a derived file agree with the tree again.
    Worse, a row here would be dated the day of the repair - so the only surviving
    record of a concept whose real `Added` row was lost in the same tear would
    carry the wrong date, in the one file whose whole job is to be a truthful
    chronology. The index diff is the record, and it is reported in full below.
    """
    bundle = common.bundle_root(args.bundle)
    _no_extension_keys(args, "reindex")
    scope = _indexed_directories(bundle)
    # `is not None`, not truthiness: `--directory ""` names no directory, and
    # falling through to the whole bundle would repair thirteen indexes for
    # somebody who asked for one.
    if args.directory is not None:
        wanted = str(args.directory).replace("\\", "/").strip("/")
        if wanted not in scope:
            raise stage.Refused(
                f"--directory {args.directory!r}: not a directory this bundle "
                f"gives an index\n"
                f"fix:  one of {', '.join(scope)} - or leave --directory out and "
                f"every one of them is checked. The bundle root is deliberately "
                f"not among them: index.md there is a map table of directories, "
                f"not a list of the concepts beside it")
        scope = [wanted]

    change = stage.Changeset()
    for directory in scope:
        repair = _repair(bundle, directory)
        if repair is None:
            continue
        index, text, added, dropped = repair
        # kind="companion": an index is derivable from the tree, which is the
        # whole premise of this command.
        change.write(index, text, kind="companion")
        # What it repaired, per directory and per file. A repair that does not
        # say what it repaired is one nobody can check - and these are lines in
        # somebody's file, one class of which was deleted.
        name = _relative(bundle, index)
        if added:
            change.record_id(name + " added", ", ".join(added))
        if dropped:
            change.record_id(name + " dropped", ", ".join(dropped))
    return change


# --- the CLI --------------------------------------------------------------------

def register(nouns):
    parser, verbs = common.verb(nouns, "capability",
                                "the capability vocabulary every match runs on")
    add = common.add_verb(verbs, "add", "list a new capability term",
                          capability_add)
    add.add_argument("--term", action="append", default=[], required=True,
                     metavar="TERM",
                     help="the term - lowercase words joined by hyphens. "
                          "Repeatable")
    add.add_argument("--theme", required=True,
                     help="the theme heading in the vocabulary to file it under")

    parser, verbs = common.verb(nouns, "question",
                               "the open questions a resume is waiting on")
    ask = common.add_verb(verbs, "add", "record an unanswered question",
                          question_add)
    ask.add_argument("--text", required=True, help="the question itself")
    ask.add_argument("--section", default=DEFAULT_SECTION,
                     help="the heading to file it under (default: %(default)s)")
    ask.add_argument("--about", metavar="STEM",
                     help="the stem of the concept the question is about - a "
                          "relative link to it goes in the row")
    resolve = common.add_verb(verbs, "resolve",
                              "strike a question that has been answered",
                              question_resolve)
    resolve.add_argument("--match", required=True,
                         help="a substring of the question's text, case "
                              "insensitive. It must match exactly one row")
    resolve.add_argument("--answer",
                         help="how it was resolved - it goes in the log row, "
                              "which is what survives the strike")

    # `log` and `reindex` have exactly one thing they do, so the noun carries the
    # flags: `okf log add` would be a level of grammar that says nothing.
    entry = common.leaf_verb(nouns, "log", "record a row in log.md", log_write)
    entry.add_argument("--message", required=True, help="the row itself")
    entry.add_argument("--date", metavar="YYYY-MM-DD",
                       help="file it under another day, for backfilling")

    repair = common.leaf_verb(nouns, "reindex",
                              "make every directory index list what is beside it",
                              reindex)
    repair.add_argument("--directory", metavar="D",
                        help="repair only this directory, relative to the bundle")
