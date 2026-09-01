"""`okf search` - find the line, or find the concepts a filter leaves.

This answers the question a session asks before it writes anything: *have I already
recorded this?* Nothing answered it. `grep -r` came closest and is wrong in three ways
that matter here - it cannot see that a hit landed in an `inferred` bullet, it cannot
see that a hit landed in a *frozen* archived copy nobody may edit, and it reads
`index.md`, so searching for a project's title returns the project and two rows of
bookkeeping generated from it. A compile can see all three and costs about a second and
thirty kilobytes to answer four words.

So this is grep that knows what a bundle is: every row is a location plus the text found
there, and the two facts a person acts on differently - provenance, and frozen - travel
with the row rather than having to be looked up afterwards.

## Two answers, one verb

With text, a row is one matched line. Without text, `--capability X --strength 4+` is
still a question - *which projects could this posting select?* - and its answer is one
row per concept. That is the tailoring call, and giving it a verb of its own would mean
`okf search --strength 4+` and `okf list --strength 4+` disagreeing about what `4+`
selects the first time either changed. `filters.Metadata` is the one definition and both
shapes go through it unchanged; nothing below re-reads a filter flag.

## The line number is the whole product

A row whose line number opens somewhere other than the match is worse than no row: it
sends somebody to edit the wrong sentence and nothing tells them. So the arithmetic is
done in two places and neither of them is here - `walk.body_offset` for where the body
starts, `Concept.line_of` for which file line a body line is. Frontmatter needs no
arithmetic at all, and that is a fact about the format rather than a convenience:
`markup.split_frontmatter` requires `---` to be the first bytes of the file, so the nth
line of the head *is* file line n and the searchable content is lines 2 to `offset - 1`.

## A claim's status, not its concept's

A hit inside a `# Bullets`, `# Skills` or `# Held` item reports that item's id and that
item's own status. The concept's status is the wrong answer there and confidently wrong:
`projects/care-platform.md` is `status: confirmed` and holds an `inferred` bullet, so a
search for the sentence in that bullet that printed `confirmed` would tell somebody a
claim is signed off when nobody has signed it off - and they would put it on a resume.
The spans come from `ids.claims`, which is the derivation the compile uses; an id
derived a second way here would be an id `okf view include` then refuses.

Untyped files are searched, and are listed by a filter they satisfy. `walk.Concept` has
the argument: a person's own notes are still text they wrote, and a search that cannot
see them is a search they stop trusting. `okf list` is the typed view.

## It reads no Markdown of its own

There is not one regular expression in this file, and that is the point. `markup.py`
counted the frontmatter split in four modules, the fence toggle in three and the term
pattern in five, and exists so there is no sixth. So the frontmatter split is `walk`'s,
which is `markup.split_frontmatter`; the heading lookup is `authoring.body.headings`,
which composes `markup.scan`'s fence toggle with the write layer's own heading pattern;
the claim shape is `authoring.body.parse`, which is the compiler's. Nothing here matches
a line except through a predicate `filters.py` built. A pattern of this module's own
would be a sixth idiom for something already defined, and the way two commands come to
disagree about what a heading is.
"""

from ..authoring import body
from . import filters, ids, render, walk

# Where a hit was, as the row records it. Two values rather than a bool, because the
# `--json` consumer of a row should not have to know which way round `in_body` reads.
FRONTMATTER = "frontmatter"
BODY = "body"

# The one sentence every command prints about an archived row, kept under the local name
# the rest of this file reads. It lives in `render.py` because four commands can surface
# such a row and each had grown its own wording - and this sentence is the only thing
# between a caller and editing the record of what was already posted, so four spellings
# meant learning it in one answer and not recognising it in the next. Aliased rather than
# used inline so a reader of `block()` below sees a name and not a module path.
FROZEN = render.FROZEN

# The filters-only listing. `file` leads because a filtered listing is read in order to
# go and open something; `title` is last and therefore untruncated - see `render.Column`
# - because it is the sentence being read. `strength` and `recency` are shown even
# though the caller usually named them: `--strength 4+` selects a band, and which end of
# it a project sits at is what decides whether it leads the resume.
LISTING = (render.Column("file", "file", 34),
           render.Column("type", "type", 14),
           render.Column("status", "status", 18),
           render.Column("strength", "strength", 8),
           render.Column("recency", "recency", 7),
           render.Column("title", "title", None))


def prefilter(args):
    """The test `walk` may skip a whole file on, or None where there is none.

    One line, because the soundness condition now lives in `filters.prefilter` where a
    caller cannot bypass it. It used to live here: `filters.literals(needle, regex)` took
    no `case_sensitive`, so the exact-case test was the only one on offer and a folded
    search had to give up the pre-filter entirely - which is the *default* search, and
    therefore almost every search anybody runs. `"Latency" in raw` is false for a file
    whose only spelling is `latency`, and a search that quietly skips a file is the one
    failure a search must not have.

    Folding both sides is sound and costs a fraction of the parse it avoids, so the
    default case keeps the optimisation. A regex still gets none: there is no literal a
    pattern is guaranteed to contain.
    """
    return filters.prefilter(args.text, regex=args.regex,
                             case_sensitive=args.case_sensitive)


def frontmatter_lines(concept):
    """Each searchable frontmatter line as `(file line, text)`, in file order.

    The two `---` fences are excluded, and not for tidiness: they are the only lines in
    the block nobody wrote, so a search for `---` would return every concept in the
    bundle and say nothing about any of them.

    The head is sliced out of `raw` with the same subtraction `walk.body_offset` counts
    its newlines over, so the two cannot disagree about where the body begins - and
    `offset` is therefore both the number of head lines and the file line of the closing
    fence.
    """
    if not concept.offset:
        return
    head = concept.raw[:len(concept.raw) - len(concept.body)]
    lines = head.split("\n")
    for number in range(2, concept.offset):
        yield number, lines[number - 1]


def body_lines(concept):
    """The body as the file's own lines - 0-based, and aligned with `authoring.body`.

    `split("\\n")` rather than `splitlines()`, which also breaks on `\\x0c` and `\\u2028`
    and would then disagree with `body_offset`'s newline count; a disagreement there
    moves every reported line number in the file. The empty string a trailing newline
    leaves behind is dropped instead, because it is not a line of the file - and
    dropping the *last* element cannot move any index, so `authoring.body.parse`'s
    positions still line up.
    """
    lines = concept.body.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def claim_spans(concept):
    """`(first body line, one past the last, id, status)` for every claim in a concept.

    Spans rather than each claim's own line, because a bullet occupies three or four
    lines and the interesting hit is often not the first of them - `metric: Event
    propagation latency` sits under the sentence it belongs to. A hit there that carried
    no id would be a hit whose claim the caller has to go and find by eye, which is the
    lookup this command exists to remove.

    Fence-blind, unlike `heading_at` below, and deliberately so: `ids.claims` reads
    blocks the way `okf_compile.blocks` reads them, and that parser does not know about
    ``` fences either. A claim this layer decided was not real because it sat in a fence
    would be a claim the compile still renders, with no id printed for it anywhere.
    """
    kind = ids.CLAIMS.get(concept.type)
    if kind is None:
        return ()
    return tuple((at, at + len(item.lines), ident,
                  item.fields.get("status") or concept.status)
                 for item, ident, at in ids.claims(concept, kind[0]))


def claim_at(spans, index):
    """The claim a body line sits inside, as `(id, status)`, or `(None, None)`."""
    for start, end, ident, status in spans:
        if start <= index < end:
            return ident, status
    return None, None


def heading_at(headings, index):
    """The `#` heading a body line sits under, or None above the first one.

    `authoring.body.headings` rather than a pattern of this module's own, and not only to
    avoid a sixth heading idiom: it is the reader `set_section` addresses a section with,
    so the section a hit is reported under is the section a write would edit. It is also
    fence-aware, via `markup.scan` - a `# Bullets` inside a fenced example must not be
    named as the section somebody's hit is in.
    """
    found = None
    for at, _, title in headings:
        if at > index:
            break
        found = title
    return found


def hit(concept, line, where, text, heading=None, claim=None, status=None):
    """One matched line, as a row.

    `frozen` is always present rather than only when true - `ids.Located.as_dict` omits
    it, correctly, because that is a single-row detail view where an absent key reads as
    "not applicable". These rows are a list a parser walks, and `row["frozen"]` should
    not raise on the common case.
    """
    return {"file": concept.rel, "line": line, "where": where,
            "concept": concept.stem, "type": concept.type,
            "heading": heading, "claim": claim,
            "status": status or concept.status,
            "frozen": concept.frozen, "text": text.strip()}


def hits(concept, matcher, where):
    """Every matched line in one concept, in file order.

    The headings and the claim spans are derived only once a line has actually matched.
    Both cost a parse of the body, and paying for them on every file in the bundle to
    annotate the two that matched would undo what `must_contain` bought.
    """
    rows = []
    if where != BODY:
        for line, text in frontmatter_lines(concept):
            if matcher(text):
                rows.append(hit(concept, line, FRONTMATTER, text))
    if where == FRONTMATTER:
        return rows

    lines = body_lines(concept)
    matched = [index for index, text in enumerate(lines) if matcher(text)]
    if not matched:
        return rows
    headings = body.headings(concept.body)
    spans = claim_spans(concept)
    for index in matched:
        claim, status = claim_at(spans, index)
        rows.append(hit(concept, concept.line_of(index + 1), BODY, lines[index],
                        heading=heading_at(headings, index), claim=claim,
                        status=status))
    return rows


def listed(concept):
    """One concept that carried every filter, as a row.

    `line` is 1 for the same reason `ids.Located` uses 1 for a concept: the row is still
    a location, and a concept's location is the top of its file.
    """
    meta = concept.meta or {}
    return {"file": concept.rel, "line": 1, "concept": concept.stem,
            "type": concept.type, "status": concept.status,
            "strength": meta.get("strength"), "recency": meta.get("recency"),
            "title": str(meta.get("title") or concept.stem).strip('"'),
            "frozen": concept.frozen}


def notes(args, where):
    """What this search did not read.

    Required rather than decorative. An empty answer whose boundaries are invisible
    reads as "there is nothing there", and the two boundaries a caller did not choose
    on purpose are exactly the ones that produce that: the archive, which is off by
    default, and a `--scope` typed once and then forgotten about.
    """
    out = []
    if not args.archive:
        out.append("not read: tailoring/applications/ - the frozen copies beside sent "
                   "applications. --archive reads them too")
    if args.scope:
        out.append(f"read only {args.scope} - the rest of the bundle was not searched")
    if where:
        out.append(f"matched against {where} only - the rest of each file was not read")
    return out


def hit_summary(rows, args, metadata):
    """What was found, or - as carefully - that nothing was and that this is an answer.

    `render.emit` prints this in place of the table when there are no rows, so the empty
    wording has to stand on its own. It says nothing about failure on purpose: a search
    that matched nothing has answered the question it was asked, and `query/__init__.py`
    is why that exits 0.
    """
    if rows:
        files = len({row["file"] for row in rows})
        frozen = sum(1 for row in rows if row["frozen"])
        found = f"{len(rows)} hit(s) in {files} file(s)"
        return found + (f", {frozen} in the frozen archive" if frozen else "")
    if metadata:
        return (f"nothing matches {args.text!r} in the concepts the filters left - "
                f"loosen the text or loosen the filters")
    return f"nothing matches {args.text!r} - no line in the bundle holds it"


def listing_summary(rows):
    if rows:
        return f"{len(rows)} concept(s) carry every filter given"
    return ("no concept carries every filter given - `okf list capabilities` prints the "
            "terms that are actually used, with how many concepts use each")


def block(row):
    """One hit as a stanza: where it is, what it is, then the line itself.

    A table was the other option and is wrong here, because the last column would be the
    matched line and a matched line is a sentence somebody reads. Columns would either
    truncate it - throwing away the thing they were asked to find - or set every other
    column's width against the longest sentence in the bundle.
    """
    lines = [f"  {row['file']}:{row['line']}   {row['type'] or 'untyped'}   "
             f"{row['status']}"]
    where = ("in frontmatter" if row["where"] == FRONTMATTER
             else f"in # {row['heading']}" if row["heading"] else "")
    second = "   ".join(part for part in (row["claim"] or "", where) if part)
    if second:
        lines.append(f"  {second}")
    if row["frozen"]:
        lines.append(f"  {FROZEN}")
    # The matched line, whole. Never shortened: a search that truncated the text it was
    # asked to find would be hiding the answer inside the answer.
    lines.append("")
    lines.append(f"  {row['text']}")
    return lines


def run(bundle, args):
    """Text, filters, or both - as `render.Result` rows. Reads, and compiles nothing."""
    metadata = filters.Metadata(args)
    matcher = filters.text_matcher(args.text, args.regex, args.case_sensitive)
    if matcher is None and not metadata:
        raise filters.Bad(
            "okf search needs text to find or a filter to select on\n"
            "fix:  `okf search <bundle> latency`, or filters alone - `okf search "
            "<bundle> --capability event-driven-architecture --strength 4+`")

    where = (FRONTMATTER if args.frontmatter else BODY if args.body else None)

    rows = []
    # `tailoring="all"` - the one caller that asks for it, and `walk.TAILORING_MODES`
    # says why the default is narrower. A `*.posting.md` is a job advertisement somebody
    # pasted in, which is text they will search for: "did I already apply somewhere that
    # wanted event-driven experience?" is a question only these files answer. The default
    # "views" would skip them, and the failure would be silent - the search would report
    # nothing matched, which is a sentence this command is trusted about.
    for concept in walk.walk(bundle, archive=args.archive, scope=args.scope,
                             tailoring="all", must_contain=prefilter(args)):
        if not metadata.matches(concept):
            continue
        if matcher is None:
            rows.append(listed(concept))
        else:
            rows.extend(hits(concept, matcher, where))

    told = notes(args, where)
    if matcher is None:
        return render.Result(rows, columns=LISTING, notes=told,
                             summary=listing_summary(rows))
    return render.Result(rows, block=block, notes=told,
                         summary=hit_summary(rows, args, metadata))
