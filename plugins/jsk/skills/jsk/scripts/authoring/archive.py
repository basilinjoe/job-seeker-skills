"""`application file` and `application event` - the archive, frozen and appended to.

Two verbs, and they are opposites. `file` writes eight or more files once and
never again; `event` adds one line to one of them, over and over, for as long as
a process is live. Nothing here edits a row that is already written: a correction
is a new row, for the same reason `log.md` records mistakes rather than hiding
them, so there is deliberately no `set` verb in this module.

`application file` is the reason this tranche exists. `bundle-spec.md` and
`mode-ship.md` enumerate it by hand for a person to follow - copy three files,
set two keys on each copy, add one `../` to every relative path that leaves the
directory, write a concept, write a timeline row, create two index rows, copy the
documents that were sent, append a log row - and the path arithmetic is the part
a reader gets wrong. It is the fiddliest write in the repo and the one with the
least reason to be performed by a model.

## Why exactly one `../`

The working copies sit in `tailoring/targets/`; the frozen copies land in
`tailoring/applications/<yyyy>/`. That is one segment deeper, and both share
`tailoring/` as the parent of the old directory - so a reference that already
leaves its own directory needs one more `..` and nothing else. Worked through:
`../../projects/x.md` resolves from `tailoring/targets` to `projects/x.md`, and
`../../../projects/x.md` resolves from `tailoring/applications/2026` to the same
file. The arithmetic holds for every depth, which is why this counts a prefix
rather than recomputing a path the way `migrate_bundle.rebase_target` does: that
function has to answer for files moving between arbitrary directories, and this
one has a single known move.

A reference that does NOT leave its directory is left exactly as written. The
three companions move together and keep sharing a stem, so a sibling reference
still resolves; rewriting it would be this command changing a path that was
already right. A slug is left alone for a related reason: a gap assessment's
`posting: acme-engineer` names the target it answered, which is still true of the
frozen copy, and it was never a path.

## Why the archive is safe to freeze at all

`frozen: true` on a `.view.md` was once a record-gate failure on every run: the
compile read `tailoring/applications/` and the frozen view shadowed the live one
it was copied from. Two independent things fixed it - `okf_compile.concepts()`
no longer enters the archive, and a View that does reach URS has `frozen`,
`frozen_date`, `superseded_by`, `title`, `description` and `timestamp` stripped
first. Both are load-bearing here, and `tests/test_authoring_archive.py` pins the
second half of it by compiling the bundle after a filing.
"""

import os
import re
import sys

from . import body, bookkeeping, common, concept, stage

# The archive's root, bundle-relative. Spelt with forward slashes because that is
# what bookkeeping.index_path and os.path.join both take, and what a `--json`
# payload should show whatever the platform is.
ARCHIVE = "tailoring/applications"

TIMELINE = "Timeline"
SENT = "Sent"

# The timeline's columns, per bundle-spec.md's "The application timeline".
HEADER = ("| Date | Event | Channel | Note | Due |", "|---|---|---|---|---|")

# The three working files a filing freezes, and the Application key that names
# each copy. validate_bundle.py resolves all three against the application's own
# directory and errors when a named one is not there.
COMPANIONS = ((".posting.md", "posting"),
              (".gaps.md", "assessment"),
              (".view.md", "view_file"))

# A stem's date, and a timeline date. `unknown` is admitted for a timeline row -
# it is what a migration writes when it could not establish one - and refused for
# a submission, because a stem with no day in it has nowhere to be filed.
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UNKNOWN = "unknown"

# One frontmatter line's key and value, nested entries included: a view's
# `target.ref` is written two spaces in, and `requirements` entries three. Not
# migrate_bundle.FM_SCALAR, which is anchored at column 0 and would miss both.
FRONTMATTER_VALUE = re.compile(
    r"^(\s*(?:-\s+)?[A-Za-z_][A-Za-z0-9_./-]*:[ \t]+)(\S.*)$")

# validate_bundle.py's own LINK regex, with the label captured.
MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Which flag owns each key this command writes, so `--set` cannot supply a second
# value for one. None means the command stamps it and no flag offers it.
FLAG_FOR = {
    "title": "--title",
    "description": "--description",
    "timestamp": None,
    "posting": None,
    "assessment": None,
    "view_file": None,
    "target_working_copy": None,
    "company_ref": "--company",
    # Stamped from the posting's own `company:`, so there is one source for it.
    # `role` is deliberately NOT here: nothing in the bundle carries the role as
    # text - a Job Posting has a title and a seniority and no role key - so
    # `--set role="Senior Engineer"` is the only way to fill the second column of
    # `pipeline.py`'s board, and the schema now models it so that `--set` checks
    # it as a real key rather than tolerating it as an extension.
    "company": None,
    "view": None,
    "submitted": "--submitted",
    "channel": "--channel",
    "frozen": None,
    "frozen_date": None,
}


def _model():
    """pipeline_model, imported on demand.

    Three scripts already agree that this module alone decides what an event
    signifies, so `application event` asks it rather than carrying a fourth copy
    of the vocabulary and a fifth timeline parser. Imported inside the call and
    not at the top of the file for the reason common.item_ids imports body that
    way: an `okf project add` should not pay for a module it never reaches.

    The sys.path guard is the one validate_bundle.py and pipeline_model.py both
    carry: the scripts directory is not reliably importable, because these are
    CLIs rather than an installed package.
    """
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts not in sys.path:                          # pragma: no cover - path
        sys.path.insert(0, scripts)
    import pipeline_model                                # noqa: PLC0415 - see above
    return pipeline_model


# --- the path arithmetic --------------------------------------------------------

def deeper(target):
    """`target` as it reads from one directory further down, or None if unchanged.

    Exactly one `../`, and only where the reference already leaves its own
    directory - see the module docstring for why that is the whole rule. A
    sibling, a URL, an anchor, an absolute path and a Windows-separated path are
    all returned as None, which is this function declining rather than failing:
    leaving a reference alone can only preserve what somebody wrote, where
    rewriting one this move does not understand would move a dangle somewhere
    harder to find.
    """
    if not target or "://" in target or target.startswith(("mailto:", "#", "/")):
        return None
    bare, sep, anchor = target.partition("#")
    if bare != ".." and not bare.startswith("../"):
        return None
    return "../" + bare + (sep + anchor if sep else "")


def _bare(value):
    """A frontmatter line's value, without its quotes or a trailing comment.

    Split on " #" rather than on "#", which is what migrate_bundle.scalar does:
    a `#` with no space before it is inside the value, and a link carrying an
    anchor - `../../projects/x.md#metrics` - is exactly that case. Truncating
    there would hand deeper() half a path.
    """
    value = value.strip()
    if value[:1] in ('"', "'"):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end != -1 else value[1:]
    return value.split(" #")[0].strip()


def deepened(text, path):
    """One copy's whole new text, seen from one directory further down.

    Frontmatter values and body links both, because `target_working_copy:` and a
    link in an advertisement are the same promise and break the same way.
    Line by line rather than through a YAML round trip: a dump would erase the
    comments, the key order and the quoting style of a file somebody wrote by
    hand, in the one directory whose whole purpose is to preserve what was there.
    """
    doc = concept.parse(text, path)
    lines = []
    for line in doc.lines:
        match = FRONTMATTER_VALUE.match(line)
        if match:
            was = _bare(match.group(2))
            now = deeper(was)
            if now:
                # Replaced inside the value rather than rewriting the line, so
                # the quoting and any trailing comment survive.
                line = match.group(1) + match.group(2).replace(was, now, 1)
        lines.append(line)

    def one(match):
        label, target = match.group(1), match.group(2)
        now = deeper(target)
        if not now:
            return match.group(0)
        # A link whose text is its own path is showing the reader a path, so the
        # shown one has to be the one that resolves. migrate_bundle.rebase_text
        # makes the same allowance.
        return "[%s](%s)" % (now if label == target else label, now)

    doc.body = MARKDOWN_LINK.sub(one, doc.body)
    return doc.text(lines)


def frozen(text, path, when):
    """One copy's text with `frozen: true` and the date it was frozen.

    mode-ship.md: the files in `tailoring/targets/` stay editable, and every one
    of those edits would silently rewrite what a past application appears to have
    answered. The freeze is what makes the archive answerable.
    """
    for key, value in (("frozen", True), ("frozen_date", when)):
        text = concept.set_key(concept.parse(text, path), key, value)
    return text


# --- the timeline ---------------------------------------------------------------

def cell(value, what):
    """One table cell: whitespace collapsed, and no pipe in it.

    A newline splits the row across two lines and shifts every column after it,
    which bookkeeping._one_line exists to prevent in an index entry. A `|` is
    worse: pipeline_model.parse_timeline splits on it with no escape handling, so
    `\\|` inside a note reads as a column boundary and every cell after it lands
    one place to the left - a `Due` date read as a `Note`, silently.
    """
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    if "|" in text:
        raise stage.Refused(
            f"{what} contains a `|`, which is the timeline table's column "
            f"separator\n"
            f"fix:  write it without the pipe - pipeline_model.py splits a row "
            f"on `|` and honours no escape, so a cell holding one shifts every "
            f"column after it and the stage derived from the row is wrong")
    return text


def row(date, event, channel, note, due):
    """One timeline row, in bundle-spec.md's own spacing."""
    cells = (date, event, channel, note, due)
    return "|" + "".join(f" {value} |" if value else " |" for value in cells)


def timeline_with(text, appended):
    """The body with one row added to its `# Timeline`, and nothing else touched.

    A pipe table rather than a body.py block, so this appender is local to the
    module that needs it. The row goes after the last unfenced line under the
    heading that starts with `|`, which is the last row of the real table.

    Fence-aware where parse_timeline is not, deliberately: that function reads any
    `|` line under the heading, fence or not, so it would count a fenced example
    as rows - but appending *into* somebody's fenced block is wrong however it is
    later read. The disagreement only exists for a file holding a fenced table
    under `# Timeline`, which is documentation rather than a timeline.
    """
    span = body.section(text, TIMELINE)
    if span is None:
        # An Application with no `# Timeline` is already a validate_bundle.py
        # error - its stage and outcome cannot be derived - so writing the
        # section is the repair rather than a second opinion about the file.
        return body.add_section(text, TIMELINE, "\n".join(HEADER + (appended,)))
    _, start, end = span
    lines = body.lines_of(text)
    end = min(end, len(lines))
    last = None
    for index, line, fenced in bookkeeping._scan(lines):
        if start <= index < end and not fenced and line.lstrip().startswith("|"):
            last = index
    if last is None:
        # A heading with prose and no table under it. The header goes in with the
        # row, after the last line that says anything - the same blank-line rule
        # bookkeeping.log_entry applies to a day with no entries yet.
        at = start - 1
        for index in range(start, end):
            if lines[index].strip():
                at = index
        lines[at + 1:at + 1] = ["", *HEADER, appended]
    else:
        lines[last + 1:last + 1] = [appended]
    out = "\n".join(lines)
    return out if out.endswith("\n") else out + "\n"


# --- what the bundle has to say before anything is decided ----------------------

def _listed(names):
    """(the names as a phrase, `is` or `are`).

    So that a refusal naming two files reads as a sentence rather than as a list
    with a singular verb after it.
    """
    if len(names) == 1:
        return names[0], "is"
    return ", ".join(names[:-1]) + f" and {names[-1]}", "are"


def _day(value, flag, allow_unknown=False):
    """One date, or a refusal naming the flag that carried it."""
    text = str(value).strip()
    if allow_unknown and text.lower() == UNKNOWN:
        return UNKNOWN
    if DAY.match(text):
        return text
    extra = " or the literal `unknown`" if allow_unknown else ""
    raise stage.Refused(
        f"{flag} {value!r}: not a date\n"
        f"fix:  write it as YYYY-MM-DD{extra} - validate_bundle.py rejects any "
        f"other shape, and pipeline_model.py reads a date it cannot parse as no "
        f"date at all, which drops the row out of every staleness calculation")


def _submission(args):
    """(what `submitted:` says, the day the stem is filed under).

    The design's refusals table: `application file` refuses when the stem's year
    cannot be established, because the alternative is a guessed year or a flat
    file. `--submitted` establishes it; a partial date and the literal `unknown`
    do not, and both are refused rather than rounded to January.
    """
    given = args.submitted
    held = bool(args.held_back) or (given is not None
                                    and str(given).strip().lower() == "false")
    if held:
        if given is not None and str(given).strip().lower() != "false":
            raise stage.Refused(
                f"--held-back was given with --submitted {given!r}\n"
                f"fix:  drop one - an application was either sent on a date or "
                f"deliberately held back, and this command cannot record both")
        # The stem still carries a day, because the archive is partitioned by
        # year and a stem with no date is not addressable. It is the day the
        # filing happened, which is a fact this command has rather than a
        # submission date it would be inventing.
        return False, common.today()
    if given is None:
        return common.today(), common.today()
    text = str(given).strip()
    if text.lower() == UNKNOWN:
        raise stage.Refused(
            f"--submitted unknown: the stem's year cannot be established\n"
            f"fix:  pass the day it was sent, as --submitted 2026-08-26. "
            f"`undated/` is a directory a migration writes when a bundle never "
            f"recorded a date, and a fresh filing has one or it has nothing - a "
            f"year nobody recorded and a year somebody invented look identical a "
            f"month later, and only one of them can be corrected")
    if not DAY.match(text):
        raise stage.Refused(
            f"--submitted {given!r}: not a whole day, so the stem cannot be built\n"
            f"fix:  write it as YYYY-MM-DD. The stem is "
            f"<yyyy-mm-dd>-<company>-<role> and the date in it is what makes a "
            f"second round at the same posting addressable, so a year or a month "
            f"on its own is not enough")
    return text, text


def _working_copies(bundle, slug):
    """The three working files, or a refusal naming every one that is not there."""
    paths = {}
    missing = []
    for suffix, key in COMPANIONS:
        path = common.path_of(bundle, "Job Posting", slug, suffix=suffix)
        paths[key] = path
        if not os.path.exists(path):
            missing.append(f"{slug}{suffix}")
    if missing:
        named, verb = _listed(missing)
        raise stage.Refused(
            f"tailoring/targets/: {named} {verb} not there\n"
            f"fix:  a filing freezes all three - the posting, the assessment it "
            f"answered and the view it rendered from. An application that cannot "
            f"say what it was answering is the one thing the archive exists to "
            f"prevent, so this command will not file a partial set. `okf posting "
            f"add`, `okf gaps write` and `okf view create` write the missing one")
    return paths


def _company(bundle, args, posting):
    """(the organisations/ stem for `company_ref`, the company's name), or a refusal.

    Two different things, and conflating them is why the name used to be missing.
    The stem names a file and is slugged; the name is the employer as the posting
    wrote it, and it is what `pipeline.py --company NAME` matches on before it
    falls back to `title`. So both are derived from the posting's own `company:`
    before either is asked for, because the posting already had to carry it:
    schema.py makes it required so that the application stem can be built from it.
    """
    given = args.company or common.slug(posting.meta.get("company") or "")
    if not given:
        raise stage.Refused(
            f"{posting.path}: has no `company:`, so `company_ref` cannot be "
            f"derived\n"
            f"fix:  pass --company <stem>, naming a concept in organisations/. "
            f"The application is the only side that links - `pipeline.py "
            f"--company NAME` derives the rest - so a filing with no company is "
            f"one no report can group")
    path = common.path_of(bundle, "Organisation", given)
    if not os.path.exists(path):
        raise stage.Refused(
            f"{path}: no such organisation\n"
            f"fix:  --company names a concept in organisations/, without its "
            f".md, or `okf org add` writes one first. Nothing derives the "
            f"organisation back out of an archive, so a `company_ref` pointing "
            f"at a file that is not there is a link that stays broken: the "
            f"compile does not read the archive at all, and validate_bundle.py "
            f"resolves only `posting`, `assessment` and `view_file`")
    named = posting.meta.get("company")
    if not named:
        # `--company <stem>` was passed against a posting that names no employer.
        # The organisation concept is the thing that IS the company, so its title
        # is the better fallback than nothing: without it `pipeline --company`
        # would be matching on this application's title by accident.
        try:
            named = concept.read(path).meta.get("title")
        except concept.Unsplicable:
            # A concept this layer cannot parse is one somebody has to fix by
            # hand, and a filing is not the command that should say so - the same
            # trade common.concept_bodies makes. The key is left absent, and
            # pipeline.py falls back to the title as it does for every
            # application written before the key existed.
            named = None
    return given, (str(named) if named else None)


def _view_id(view, slug):
    """The view id that was rendered, read out of the view rather than asked for.

    `okf_compile.build_views` defaults an absent `id` to `view_<slug(stem)>` over
    the file's stem, which for a working copy includes the `.view` suffix. So the
    default is derived the same way here: an id this layer wrote down that
    differed by one character from the one the compile derives would name a view
    nobody can render.
    """
    if view.meta.get("type") != "View":
        raise stage.Refused(
            f"{view.path}: `type` is {view.meta.get('type')!r}, not View\n"
            f"fix:  the third frozen copy is the view the resume rendered from. "
            f"A concept of another type filed here would put a `view:` in the "
            f"application naming something that renders nothing")
    declared = view.meta.get("id")
    if declared:
        return str(declared)
    derived = body.compile_slug(f"{slug}.view")
    if not derived:
        raise stage.Refused(
            f"{view.path}: has no `id` and none can be derived from its "
            f"filename\n"
            f"fix:  add `id: view_<something>` to the view. `view:` on the "
            f"application records which view the resume was rendered from, and "
            f"an application that cannot name it cannot say what was selected")
    return f"view_{derived}"


def _documents(args, year_dir, taken):
    """[(source, destination)] for `--document`, or a refusal naming the clash."""
    out = []
    seen = {}
    for source in common.first_appearance(args.document):
        name = os.path.basename(str(source).rstrip("/\\"))
        if not name:
            raise stage.Refused(
                f"--document {source!r}: names no file\n"
                f"fix:  pass the path to one of the documents that was sent")
        if name in taken:
            raise stage.Refused(
                f"--document {source!r}: would land on {name}, which this filing "
                f"already writes\n"
                f"fix:  rename the file before filing it - the four Markdown "
                f"files sharing the application's stem are the archive's own, "
                f"and a document written over one of them would destroy the "
                f"half of the record that cannot be regenerated")
        if name in seen:
            raise stage.Refused(
                f"--document {source!r} and --document {seen[name]!r} share the "
                f"filename {name}\n"
                f"fix:  rename one - both would be filed beside the same "
                f"application under one name, and which of the two documents was "
                f"actually sent is not something this command can know")
        destination = os.path.join(year_dir, name)
        if os.path.exists(destination):
            raise stage.Refused(
                f"{destination}: already there\n"
                f"fix:  rename the copy being filed. This directory holds what "
                f"was sent, byte for byte, and overwriting last time's document "
                f"with this time's would leave the archive claiming the wrong "
                f"file was sent to the earlier application")
        seen[name] = source
        out.append((str(source), destination))
    return out


def _refuse_filed(bundle, year_dir, stem):
    """Say no to filing over a submission already recorded under this stem."""
    already = [name for name in
               [f"{stem}.md"] + [f"{stem}{suffix}" for suffix, _ in COMPANIONS]
               if os.path.exists(os.path.join(year_dir, name))]
    if already:
        rel = f"{ARCHIVE}/{os.path.basename(year_dir)}"
        named, verb = _listed(already)
        raise stage.Refused(
            f"{rel}/: {named} {verb} already there\n"
            f"fix:  `okf application event {stem}` appends to the application "
            f"that is filed. A second round at the same posting is ordinary and "
            f"gets its own stem from its own date, which is what the date in the "
            f"stem is for - but overwriting the first round is not something "
            f"this command will do")


# --- the two indexes the archive keeps ------------------------------------------

def _index_row(filename, title, description=None):
    """One index row, written the way bookkeeping.index_entry would write it.

    Borrowed rather than reimplemented, including the refusal on a filename no
    plain markdown link can carry: a row this module wrote by hand that differed
    from an appended one would make the first entry in a year's index the odd one
    out forever.
    """
    bookkeeping._refuse_unlinkable(filename)
    entry = f"- [{bookkeeping._one_line(title)}]({filename})"
    if description:
        entry += f" - {bookkeeping._one_line(description)}"
    return entry


def _stage_index(change, bundle, directory, filename, title, description, seed):
    """Add one row to an index, creating the index when it is not there yet.

    common.stage_index returns silently when the index is absent, which is right
    for a directory the scaffolder made and wrong for a year directory that comes
    into existence with the first application filed into it. `seed` is the whole
    file for that case, with this row already in it.
    """
    index = bookkeeping.index_path(bundle, directory)
    if os.path.exists(index):
        change.write(index,
                     bookkeeping.index_entry(index, filename, title, description),
                     kind="companion")
    else:
        change.write(index, seed, kind="companion")
    return index


def _year_index(bundle, year, entry):
    """A year directory's whole new index.md, listing the first thing filed in it."""
    return common.emit(bundle, "Index", {
        "title": f"Applications {year}",
        "description": f"Applications submitted in {year}.",
        "timestamp": common.stamp(),
    }, entry + "\n", directory=ARCHIVE)


def _archive_index(bundle, entry):
    """The archive root's whole new index.md, in the shape init_bundle.py gives it."""
    return common.emit(bundle, "Index", {
        "title": "Applications",
        "description": "Submissions, evidence selected, and outcomes, in one "
                       "directory per submission year.",
        "timestamp": common.stamp(),
    }, "One directory per submission year, created the first time something is "
       "sent that year.\n\n# Years\n\n" + entry + "\n", directory=ARCHIVE)


# --- application file -----------------------------------------------------------

def application_file(args):
    """Freeze one submission into `tailoring/applications/<yyyy>/`."""
    bundle = common.bundle_root(args.bundle)
    slug = common.stem_of(args.slug, args.slug, "tailoring/targets")
    submitted, filed = _submission(args)
    if submitted is False and args.channel:
        raise stage.Refused(
            f"--channel {args.channel!r} was given with --held-back\n"
            f"fix:  drop it - `channel` records how a submission was sent, and "
            f"an application deliberately held back was not sent through one")

    year = filed[:4]
    stem = f"{filed}-{slug}"
    year_directory = f"{ARCHIVE}/{year}"
    year_dir = os.path.join(str(bundle), *year_directory.split("/"))
    _refuse_filed(bundle, year_dir, stem)

    working = _working_copies(bundle, slug)
    # Opened once each and reused: the frontmatter decides the company and the
    # view id, and the whole text is what gets frozen, so a second read would be
    # a second chance for the two to disagree about the same file.
    docs = {key: common.open_concept(path, "working copy")
            for key, path in working.items()}
    company, company_name = _company(bundle, args, docs["posting"])
    view_id = _view_id(docs["view_file"], slug)

    extensions = common.extension_keys(args.set, FLAG_FOR)
    values = common.without_none({
        "title": args.title or docs["posting"].meta.get("title") or stem,
        # The posting's own description says which job this was, which is the one
        # thing a reader of the year's index wants from the row. Copied rather
        # than composed: this command has no prose of its own to write.
        "description": args.description or docs["posting"].meta.get("description"),
        "timestamp": common.stamp(),
        "posting": f"{stem}.posting.md",
        "assessment": f"{stem}.gaps.md",
        "view_file": f"{stem}.view.md",
        "target_working_copy": f"../../targets/{slug}.posting.md",
        "company_ref": f"../../../organisations/{company}.md",
        # The employer as text, beside the link to its concept. pipeline.py reads
        # this key and falls back to `title`, so writing it is the difference
        # between `pipeline --company Acme` grouping every application to one
        # employer and it matching whatever happens to be in a title.
        "company": company_name,
        "view": view_id,
        "submitted": submitted,
        "channel": args.channel,
    })
    values.update(extensions)
    # There is deliberately no `outcome:` here and there must not be one. The
    # outcome is derived from the timeline below, because a status word and the
    # prose beneath it stop agreeing the moment one is edited.
    common.checked("Application", values, extensions=extensions)

    taken = {f"{stem}.md"} | {f"{stem}{suffix}" for suffix, _ in COMPANIONS}
    documents = _documents(args, year_dir, taken)

    note = args.note
    if submitted is False:
        # Never a `submitted` row. bundle-spec.md makes `submitted: false` the one
        # exemption from validate_bundle.py's demand for one, and writing the row
        # anyway to clear the error would trade an accurate red for a false green -
        # every stage derived from that timeline afterwards would be a lie about
        # an application nobody sent. A `note` is the honest row: it advances
        # nothing and restarts no clock, so `pipeline.py` reports the application
        # as having no stage, which is exactly what is true of it.
        first = row(filed, "note", "",
                    cell(note or "Prepared and deliberately held back.", "--note"),
                    "")
    else:
        first = row(submitted, "submitted", cell(args.channel, "--channel"),
                    cell(note, "--note"), "")

    sent = ["# %s" % SENT, ""]
    for _, destination in documents:
        name = os.path.basename(destination)
        # A markdown link where the filename can carry one, and inline code where
        # it cannot. validate_bundle.py strips inline code before it checks links,
        # so a name holding a space is recorded in the one form that cannot become
        # a broken link in the file whose findings are errors rather than
        # warnings. The link is worth having where it is possible:
        # `migrate_bundle.attribute` reads exactly this - "a link in the
        # application's log" - to work out which application a loose document
        # belongs to, and these copies keep the name they were sent under rather
        # than gaining the application's stem.
        try:
            bookkeeping._refuse_unlinkable(name)
        except stage.Refused:
            sent.append(f"- `{name}`")
        else:
            sent.append(f"- [{name}]({name})")
    section = "\n".join(sent) + "\n\n" if documents else ""
    text = common.emit(bundle, "Application", values,
                       section + "# %s\n\n%s\n%s\n%s\n"
                       % (TIMELINE, HEADER[0], HEADER[1], first),
                       directory=year_directory)

    change = stage.Changeset()
    # Every one of these is `kind="concept"`, and they are staged in the order
    # they must publish in. stage.py orders by kind and is stable within one, so
    # the three frozen copies and the documents land before `<stem>.md`. That is
    # the repairable direction: an application naming a copy that is not there is
    # a validate_bundle.py ERROR and a link in it that resolves to nothing is
    # another, while copies with no application yet are warnings in files the
    # gate demotes anyway. A PDF is not a concept - the kind here is a publish
    # position, which is what stage.ORDER's names mean.
    for suffix, key in COMPANIONS:
        source = working[key]
        change.write(os.path.join(year_dir, f"{stem}{suffix}"),
                     frozen(deepened(docs[key].text(), source), source, filed),
                     kind="concept")
    for source, destination in documents:
        change.copy(source, destination, kind="concept")
    concept_path = os.path.join(year_dir, f"{stem}.md")
    common.stage_concept(change, concept_path, text)

    row_title = values["title"]
    _stage_index(change, bundle, year_directory, f"{stem}.md", row_title,
                 values.get("description"),
                 _year_index(bundle, year,
                             _index_row(f"{stem}.md", row_title,
                                        values.get("description"))))
    _stage_index(change, bundle, ARCHIVE, f"{year}/index.md", f"{year}/", None,
                 _archive_index(bundle, _index_row(f"{year}/index.md", f"{year}/")))

    # Under today, not under the submission date. log.md is the history of
    # changes to the bundle and this change is being made now - a filing recorded
    # a week late, backdated, would open a day heading below one already dated
    # after it. The submission date is in the stem the row names anyway.
    common.stage_log(change, bundle, f"Filed {year_directory}/{stem}.md - {row_title}")
    change.record_id("application", stem)
    change.record_id("view", view_id)
    change.record_id("year", year)
    # The year directory is not created here. stage.commit makes each target's
    # parent as part of the transaction, so it comes into existence with the files
    # that land in it and a dry run leaves nothing behind - which is what lets
    # this function keep the contract that it decides everything and writes
    # nothing.
    return change


# --- application event ----------------------------------------------------------

def _application(bundle, stem):
    """The one application with this stem, wherever in the archive it sits.

    Searched rather than asked for, because the caller should not have to know
    which year a submission was filed under - the stem already carries the date.
    """
    stem = str(stem)
    if stem.endswith(".md"):
        stem = stem[: -len(".md")]
    root = os.path.join(str(bundle), *ARCHIVE.split("/"))
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        if f"{stem}.md" in filenames:
            found.append(os.path.join(dirpath, f"{stem}.md"))
    if not found:
        raise stage.Refused(
            f"{stem}: no application with that stem under {ARCHIVE}/\n"
            f"fix:  name it as it is filed, without its .md - the stem is "
            f"<yyyy-mm-dd>-<company>-<role>. `okf application file <slug>` files "
            f"a submission that has not been archived yet")
    if len(found) > 1:
        rows = ", ".join(sorted(os.path.relpath(path, str(bundle)).replace(os.sep, "/")
                                for path in found))
        raise stage.Refused(
            f"{stem}: filed more than once - {rows}\n"
            f"fix:  two year directories hold the same stem, so which timeline "
            f"this row belongs to is not something this command can know. Move "
            f"or rename one by hand - the stem's own date says which year it "
            f"belongs in")
    return found[0]


def _event(bundle, given):
    """One event value, checked the way validate_bundle.py checks a written one.

    The vocabulary is read with common.vocabulary_terms, which is
    validate_bundle.py's own list-item regex and fence toggle: a term this layer
    read and the gate did not would be an event accepted here and refused there,
    which is the one failure mode a write-time check must not have.

    An absent or empty vocabulary switches the gate's check off - `if
    pipeline_vocab and ...` - and falls back here to pipeline_model.ALL_EVENTS
    rather than to nothing. That file ships full, unlike the capability
    vocabulary, and pipeline_model.py is the module allowed to decide what an
    event signifies: a row outside its sets is one nothing can compute a stage
    from, whatever the bundle's own file does or does not list.
    """
    path = os.path.join(str(bundle), "framework", "pipeline-vocabulary.md")
    listed = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as handle:
            listed = common.vocabulary_terms(handle.read().replace("\r\n", "\n"))
    allowed = listed or set(_model().ALL_EVENTS)
    if given not in allowed:
        where = ("framework/pipeline-vocabulary.md" if listed
                 else "pipeline_model.py, since this bundle's "
                      "framework/pipeline-vocabulary.md lists nothing")
        raise stage.Refused(
            f"event {given!r} is not in {where}\n"
            f"fix:  one of {', '.join(sorted(allowed))}. These compare as exact "
            f"strings, so a synonym does not fail - it is a row that stops "
            f"counting, and validate_bundle.py rejects it")
    return given


def _warn(message):
    """Say something is odd without failing.

    stderr rather than stdout, so `--json`'s payload stays the whole of what
    stdout says and a caller can parse it. validate_bundle.py warns on both of
    the things this reports and does not fail either, and refusing here would
    block a legitimate backfill or a reopened process.
    """
    print(f"WARN  {message}", file=sys.stderr)


def application_event(args):
    """Append one row to an application's `# Timeline`."""
    bundle = common.bundle_root(args.bundle)
    if args.set:
        raise stage.Refused(
            f"--set {args.set[0]!r}: an event is a row, not a key\n"
            f"fix:  drop it - a timeline row has five columns and none of them "
            f"is an arbitrary key. `--note` is where anything else about the "
            f"event goes")
    path = _application(bundle, args.stem)
    doc = common.open_concept(path, "application")
    if doc.meta.get("type") != "Application":
        raise stage.Refused(
            f"{path}: `type` is {doc.meta.get('type')!r}, not Application\n"
            f"fix:  name the application's own concept - the `<stem>.md` beside "
            f"the frozen copies. The copies are frozen and appending to one "
            f"would be editing what an application was answering")

    event = _event(bundle, args.event)
    date = _day(args.date or common.today(), "--date", allow_unknown=True)
    due = _day(args.due, "--due", allow_unknown=True) if args.due else ""
    appended = row(date, event, cell(args.channel, "--channel"),
                   cell(args.note, "--note"), due)

    model = _model()
    rows = model.parse_timeline(doc.body)
    previous, terminal = None, None
    for entry in rows:
        if entry.date is not None:
            previous = entry.date
        if entry.event in model.TERMINAL:
            terminal = entry.event
        elif entry.event in model.ADVANCING:
            terminal = None
    when = model.parse_date(date)
    if when is not None and previous is not None and when < previous:
        _warn(f"{date}: dated before the row above it - expected when "
              f"backfilling, worth a look otherwise")
    if terminal and event in model.ADVANCING:
        _warn(f"{event!r} follows {terminal!r} - a reopened process, or a mistake")

    # Appended, never edited. A correction is a new row, which is why there is no
    # `set` verb here: an edited row loses the fact that the earlier one was ever
    # written, and the timeline is the only record of how a process actually went.
    doc.body = timeline_with(doc.body, appended)
    change = stage.Changeset()
    common.stage_concept(change, path, doc.text())
    rel = os.path.relpath(path, str(bundle)).replace(os.sep, "/")
    common.stage_log(change, bundle, f"Logged {event} on {rel} - {date}")
    change.record_id("application", os.path.basename(path)[: -len(".md")])
    change.record_id("event", event)
    return change


# --- the CLI --------------------------------------------------------------------

def register(nouns):
    parser, verbs = common.verb(
        nouns, "application", "one submission, frozen into the archive")

    filing = common.add_verb(verbs, "file",
                             "freeze a submission into applications/<yyyy>/",
                             application_file)
    filing.add_argument("slug", help="the target's stem under tailoring/targets/")
    filing.add_argument("--submitted", metavar="DATE",
                        help="the day it was sent (default today), or `false` "
                             "for one deliberately held back")
    filing.add_argument("--held-back", action="store_true",
                        help="same as --submitted false: worked through, not sent")
    filing.add_argument("--channel",
                        help="how it was sent - \"Workday portal\", \"email\"")
    filing.add_argument("--note", help="the timeline row's Note")
    filing.add_argument("--company", metavar="STEM",
                        help="the organisations/ concept stem for company_ref "
                             "(default: the posting's own company, slugged)")
    filing.add_argument("--title", help="default: the posting's own title")
    filing.add_argument("--description",
                        help="default: the posting's own description")
    filing.add_argument("--document", action="append", default=[], metavar="PATH",
                        help="a file that was actually sent, copied byte for "
                             "byte; repeatable")

    event = common.add_verb(verbs, "event", "append one row to a timeline",
                            application_event)
    event.add_argument("stem", help="the application's stem, without its .md")
    event.add_argument("--event", required=True,
                       help="one value from framework/pipeline-vocabulary.md")
    event.add_argument("--date", metavar="DATE",
                       help="YYYY-MM-DD or `unknown` (default today)")
    event.add_argument("--channel", help="how the contact happened")
    event.add_argument("--note", help="what happened, in one line")
    event.add_argument("--due", metavar="DATE",
                       help="what was promised next - YYYY-MM-DD or `unknown`")
    return parser
