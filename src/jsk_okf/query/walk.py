"""The one walk the read layer does.

Four walks over a bundle already exist: `okf_compile.concepts()` builds the record,
`authoring.common.concept_bodies()` reads one directory, `authoring.career._markdown_files()`
finds what references a concept, and `pipeline.collect()` finds applications. None of
them can answer a query, for one reason each: the first returns no path so a hit has
nowhere to point, the second reads a single directory, the third parses no frontmatter,
the fourth reads only the archive.

So this is a fifth, and the thing that makes it worth its own file is that it does not
restate any of their rules. `SKIP_DIRS`, the archive path and the tailoring path come
from `okf_compile`, and the frontmatter split is `okf_compile.read_frontmatter`. A
second copy of "which directories are not career record" is how two commands start
disagreeing about what is in a bundle.

What it adds is three things a query needs and no existing walk carries:

* **`offset`** - the file line the body starts at, so a match inside the body can be
  reported as `file:line` that opens where the match is.
* **`frozen`** - whether the file is an archived copy beside a sent application. A hit
  in one must say so: the copy may not be edited, and somebody sent there to fix a
  sentence would be editing the record of what was already posted.
* **`raw`** - the file as read, so a caller can pre-filter on a literal before paying
  for the YAML parse.
"""

import os

from .. import okf_compile

# Where the record's own rules are written down. Imported rather than restated - see
# the module docstring.
SKIP_DIRS = okf_compile.SKIP_DIRS
ARCHIVE = okf_compile.ARCHIVE
TAILORING = okf_compile.TAILORING

# What to read under `tailoring/`, spelt exactly as `okf_compile.concepts()` spells it,
# because it is the same decision and getting it wrong costs the same way.
#
# This is the most expensive knob in the read layer and it was measured, not guessed.
# On a bundle of a hundred answered postings there are three files per target - the
# posting, the gap assessment and the view - and only the view is career record. Reading
# all three took a walk from 216 concepts to 419: a posting and an assessment each
# opened, YAML-parsed, and then wanted by nobody. That is the identical waste
# `concepts()`' own docstring records removing from the compile ("408ms of a 946ms
# compile"), and this module reintroduced it by defaulting to breadth.
#
# So the default is "views", the same as the compile's, and a caller that genuinely
# wants a posting's text - `okf search`, and only `okf search` - asks for "all". The
# failure mode of the wrong value here is the one `concepts()` warns about: it makes a
# walk read less, and every check written about what it found still passes.
TAILORING_MODES = okf_compile.TAILORING_MODES

# `index.md` is skipped, always, and there is no flag to include it. Its rows are
# generated from the concepts they point at - `bookkeeping.py` writes them and `okf
# reindex` repairs them - so every hit in one is a duplicate of a hit the caller
# already has, attached to a file nobody should edit by hand. Including them made a
# search for a project title return the project, its directory index and the bundle
# index, in that order, which reads as three pieces of evidence.
INDEX = "index.md"

# The copies an application froze at submission, which may not be edited. Named by
# suffix rather than by directory, because the application's own `<stem>.md` sits in
# the same directory and is the opposite case - see `Scope.frozen`. `.target.md` is the
# r2-era spelling of the posting and is kept because a bundle is never obliged to
# migrate. The same four `pipeline.py` skips as COMPANIONS, for the same reason.
FROZEN_COMPANIONS = (".posting.md", ".gaps.md", ".view.md", ".target.md")


class Concept:
    """One file in a bundle, as a query needs to see it.

    `type` and `meta` are None for a file carrying no parseable frontmatter. That is
    deliberately not skipped the way `okf_compile.concepts()` skips it: a person's own
    notes in a bundle are still text they wrote, and a text search that cannot see
    them is a search they will not trust. Type-driven callers filter with
    `typed_only=True`.
    """

    __slots__ = ("stem", "type", "meta", "body", "raw", "path", "rel", "directory",
                 "offset", "frozen")

    def __init__(self, stem, ctype, meta, body, raw, path, rel, directory, offset,
                 frozen):
        self.stem = stem
        self.type = ctype
        self.meta = meta
        self.body = body
        self.raw = raw
        self.path = path
        self.rel = rel
        self.directory = directory
        self.offset = offset
        self.frozen = frozen

    @property
    def status(self):
        """The concept's own provenance, defaulted the way the compile defaults it.

        `okf_compile.provenance()` reads an absent `status` as `needs-verification`,
        so a query that reported it as blank would disagree with the record about the
        same file.
        """
        return str((self.meta or {}).get("status") or "needs-verification")

    def line_of(self, body_line):
        """The file line a body line sits on. 1-based, both sides."""
        return self.offset + body_line

    def at(self, line):
        """`projects/care.md:34` - what a caller prints so an editor can open it."""
        return f"{self.rel}:{line}"


def body_offset(raw, body):
    """The number of lines before the body starts.

    Derived from the split `read_frontmatter` already made rather than by parsing the
    file a second time: `body` is a suffix slice of `raw` in every one of that
    function's four return paths, so the text before it is `raw[:len(raw) - len(body)]`
    and the lines in it are the offset.

    This is why it holds for a bundle written with CRLF endings too. The two branches
    slice at different widths - `end + 5` for `\\n---\\n` and `end + 7` for
    `\\r\\n---\\r\\n` - and neither width is spelt here; the length of what survived is.
    Counting `\\n` is enough for the same reason: every CRLF contains one.
    """
    return raw[:len(raw) - len(body)].count("\n")


def _relative(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def _scope_check(root, scope):
    """The absolute path `--scope` names, or a sentence saying why it is not one.

    Same flag name, same shape and the same refusals as `validate_bundle.py --scope`,
    which had it first. A caller who has learnt one has learnt both.
    """
    cleaned = str(scope).replace("\\", "/").strip("/")
    if not cleaned or cleaned == "." or cleaned.startswith("..") or os.path.isabs(scope):
        return None, (f"not a subdirectory of the bundle: {scope}\n"
                      f"fix:  --scope projects   - a path inside the bundle, not an "
                      f"absolute one")
    full = os.path.join(root, *cleaned.split("/"))
    if not os.path.isdir(full):
        return None, (f"no such directory in the bundle: {cleaned}\n"
                      f"fix:  --scope <a subdirectory of {root}>")
    return cleaned, None


class Scope:
    """What a walk is allowed to read. Resolved once, then asked per directory.

    `scope` takes one subtree or several. Several matters more than it looks: a query
    over `projects/` and `skills/` and `education/` is one question, and answering it
    with three walks costs three times the directory traversal to read the same files.
    `okf list orphans` is exactly that query.
    """

    def __init__(self, root, archive=False, scope=None):
        self.root = os.path.abspath(str(root))
        self.archive = bool(archive)
        self.scopes = ()
        self.problem = None
        if scope:
            wanted = (scope,) if isinstance(scope, str) else tuple(scope)
            resolved = []
            for one in wanted:
                cleaned, problem = _scope_check(self.root, one)
                if problem:
                    self.problem = problem
                    return
                resolved.append(cleaned)
            self.scopes = tuple(resolved)
        self._archive_dir = os.path.normcase(os.path.join(self.root, *ARCHIVE))

    def keep_directory(self, dirpath, name):
        """Whether to descend into `name` under `dirpath`."""
        if name in SKIP_DIRS or name.startswith("."):
            return False
        child = os.path.normcase(os.path.abspath(os.path.join(dirpath, name)))
        return self.archive or child != self._archive_dir

    def wanted(self, rel):
        """Whether a bundle-relative file path is inside any requested subtree."""
        if not self.scopes:
            return True
        return any(rel == one or rel.startswith(one + "/") for one in self.scopes)

    def prunable(self, rel):
        """Whether a directory can be skipped outright because no scope reaches it.

        Without this, `scope="projects"` still traverses every other directory in the
        bundle and discards each file by name. That is most of what scoping was meant
        to save - on the hundred-target bundle it is 200 postings still being opened
        to be thrown away.
        """
        if not self.scopes or not rel:
            return False
        return not any(one == rel or one.startswith(rel + "/")
                       or rel.startswith(one + "/") for one in self.scopes)

    def frozen(self, rel):
        """Whether this file is one the archive froze - not merely one filed in it.

        The distinction is `bundle-spec.md`'s and it is not a nicety. Beside a sent
        application sit its frozen inputs - `<stem>.posting.md`, `<stem>.gaps.md`,
        `<stem>.view.md`, and the r2-era `<stem>.target.md` - which may not be edited,
        because an application that links to a mutable posting cannot say what it was
        answering. **The application's own `<stem>.md` is not one of them.** Its
        `# Timeline` is appended to for as long as the process is live, which is how a
        rejection or a follow-up gets recorded at all.

        Marking the whole directory frozen told somebody the one file in it they are
        supposed to write to was off limits. `validate_bundle.py` draws the same line
        for the same reason - a problem in a frozen copy is a warning there, and a
        problem in the application's own file is still an error.
        """
        if not rel.startswith("/".join(ARCHIVE) + "/"):
            return False
        return rel.endswith(FROZEN_COMPANIONS)


def walk(root, archive=False, scope=None, types=None, typed_only=False,
         must_contain=None, tailoring="views"):
    """Every concept a query may read, as `Concept` records.

    `archive` admits `tailoring/applications/` - excluded by default because the
    compile excludes it, and for the stronger reason that a frozen copy is a file
    nobody may edit. Every record from it carries `frozen`.

    `tailoring` says what to read under `tailoring/targets/` and defaults to "views",
    which is what the compile defaults to. See `TAILORING_MODES` above: this is the
    knob that decides whether a walk reads 216 concepts or 419, and the wrong value is
    invisible in either direction. `okf search` passes "all" because a job
    advertisement is text somebody may want to search; everything else wants the
    narrow read. `True` and `False` are accepted as "all" and "none" so a caller
    written against the earlier signature still means what it said.

    `scope` takes one bundle-relative subtree or several, and directories no scope
    reaches are pruned rather than traversed and discarded.

    `must_contain` skips a file's YAML parse when its raw text cannot hold what the
    caller is looking for. This is `career.references()`'s pre-filter and it is the
    difference between a fast query and a slow one: the parse is five sixths of a walk,
    so skipping it took a 645ms walk to 122ms here, and the same trick took the walk
    behind `okf project rm` from 911ms to 194ms.

    It takes either a collection of literals - a file holding none of them is skipped -
    or a callable over the raw text, which is what `filters.prefilter()` returns. The
    callable form exists because the soundness condition is not "is this string in the
    file": a folded search has to fold both sides, and a regex cannot be pre-filtered at
    all. Deciding that here, per caller, is how a search comes to skip a file for a
    reason nobody can see, so the decision belongs to `filters.prefilter` and this
    parameter only carries it.

    `types` and `typed_only` are for the type-driven callers. A file with no parseable
    frontmatter is yielded by default - see `Concept`.
    """
    if tailoring is True:
        tailoring = "all"
    elif tailoring is False:
        tailoring = "none"
    if tailoring not in TAILORING_MODES:
        raise ValueError(f"walk(tailoring={tailoring!r}): one of {TAILORING_MODES}")
    scoped = Scope(root, archive=archive, scope=scope)
    if scoped.problem:
        raise ValueError(scoped.problem)
    wanted_types = frozenset(types) if types else None
    # Either form, normalised to one predicate so the loop below has one shape.
    if must_contain is None:
        holds = None
    elif callable(must_contain):
        holds = must_contain
    else:
        literals = tuple(must_contain)
        holds = (lambda raw: any(term in raw for term in literals)) if literals else None
    tailored = os.path.normcase(os.path.join(scoped.root, TAILORING))

    for dirpath, dirnames, filenames in os.walk(scoped.root):
        here = os.path.normcase(os.path.abspath(dirpath))
        rel_dir = _relative(dirpath, scoped.root)
        rel_dir = "" if rel_dir == "." else rel_dir
        if scoped.prunable(rel_dir):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames
                            if scoped.keep_directory(dirpath, d))
        under_tailoring = here == tailored or here.startswith(tailored + os.sep)
        if tailoring == "none" and under_tailoring:
            dirnames[:] = []
            continue
        # `views` narrows tailoring/targets/ and must not narrow the archive. A caller
        # that passed `archive=True` asked for the sent applications, and an
        # `Application` concept is `<stem>.md` - not a `.view.md` - so applying the
        # same filter there would honour the flag by walking into the directory and
        # then skipping everything the flag was for. `okf refs` reads the archive by
        # default and would have found no application at all.
        in_archive = here.startswith(
            os.path.normcase(os.path.join(scoped.root, *ARCHIVE)))
        views_only = tailoring == "views" and under_tailoring and not in_archive
        for name in sorted(filenames):
            if not name.endswith(".md") or name == INDEX:
                continue
            # The 200 files per hundred targets that nothing downstream reads. Skipped
            # by name before the open, which is the only place it is cheap to skip
            # them: `concepts()` does the same and for the same measured reason.
            if views_only and not name.endswith(".view.md"):
                continue
            path = os.path.join(dirpath, name)
            rel = _relative(path, scoped.root)
            if not scoped.wanted(rel):
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    raw = handle.read()
            except (OSError, UnicodeDecodeError):
                # A file this layer cannot read is not a query's business to fail on.
                # `okf validate` is where an unreadable concept is a finding; a search
                # that refused because of one would be unusable in the bundle that has
                # it.
                continue
            if holds is not None and not holds(raw):
                continue
            meta, body = okf_compile.read_frontmatter(raw)
            ctype = (meta or {}).get("type")
            if typed_only and not ctype:
                continue
            if wanted_types is not None and ctype not in wanted_types:
                continue
            directory = os.path.dirname(rel)
            yield Concept(stem=name[:-3], ctype=ctype, meta=meta, body=body, raw=raw,
                          path=path, rel=rel, directory=directory,
                          offset=body_offset(raw, body), frozen=scoped.frozen(rel))


def by_type(root, *types, **kwargs):
    """Every concept of the named types, as a list. The common shape of a listing."""
    kwargs.setdefault("typed_only", True)
    return list(walk(root, types=types, **kwargs))
