"""`jsk kb pack` and `jsk kb merge`: changesets drafted (application/record/pack.py,
merge.py) and printed, or written to --out - never applied."""
import os
import sys

from ..presenters import GUIDE, refuse, refuse_each, usage


def drafted(text, out, what):
    """A drafted changeset to `out`, or to stdout. Returns the exit code."""
    if not out:
        sys.stdout.write(text)
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {out}: {what}")
    print(f"next: `jsk kb apply {out} --dry-run`, read the diff, then apply it")
    return 0


def draft_out(flags):
    """--out FILE for a drafted changeset: (path or None, exit code or None)."""
    out = flags.get("--out")
    if out is not None and not out.endswith(".trig"):
        return None, usage(f"{out}: a changeset is a .trig file")
    return out, None


def unlogged(state):
    """Refuse drafting against a record with no logged revision. Returns the exit code."""
    message, fix = GUIDE.get(state.kind, (state.detail, "`jsk kb check` says what is wrong"))
    return refuse([message or state.detail], fix)


def cmd_pack(args, flags, root, today):
    """jsk kb pack capabilities [--out FILE.trig]

    Drafts a changeset adopting the capability starter pack (data/capabilities.ttl):
    capabilities and domains with the wordings postings use, and the counts-as edges
    true for anyone. The pack is never loaded as vocabulary; it becomes the person's
    once applied, to change like any of their own concepts.

    Only what the record lacks: a concept it has not got comes whole; one it has with the
    same class gets the missing labels and edges. A concept the record has with another
    class, a label that already names another concept, and an edge whose target is
    missing or that would make a cycle or cross a distinct wall are skipped, each one
    said. Nothing is applied: read it with `jsk kb apply FILE --dry-run`, then apply it.
    The changeset goes to stdout, or --out; what was skipped to stderr, or stdout with --out.
    """
    from ....application.record.pack import pack
    from ....application.record.refusals import Unclean
    from ....graph import pack as P
    from ....graph import store as S
    from ....infra.oxigraph import record as R

    out, code = draft_out(flags)
    if code is not None:
        return code
    if len(args) != 1 or args[0] not in P.PACKS:
        return usage(f"jsk kb pack takes one of: {', '.join(P.PACKS)}")
    try:
        d = pack(root, args[0], load=S.load, state=R.state, packs=P)
    except Unclean as err:
        return unlogged(err.state)
    report = sys.stdout if out else sys.stderr
    for line in d.skipped:
        print(f"skipped  {line}", file=report)
    if d.text is None:
        print(f"nothing to add: the record already has all of the {args[0]} pack it can take",
              file=report)
        return 0
    return drafted(d.text, out, d.what)


def cmd_merge(args, flags, root, today):
    """jsk kb merge c:a --into c:b [--out FILE.trig]

    Drafts a changeset making two concepts one. Every career triple pointing at c:a -
    j:uses, j:domain, j:industry, j:shows, another concept's edges - points at c:b; c:a's
    labels, former labels and own edges move to c:b, and c:a's id is added to c:b as a
    label in words, so the wording that found c:a finds c:b.

    c:a is then deleted - or retired, with a reason, when a posting still names it
    through j:concept: a changeset does not edit postings, and deleting it would leave
    the posting dangling.

    Refused: a concept into itself, one either side the record lacks, a c:a the shipped
    vocabulary defines, two classes, and two concepts declared distinct.

    A bullet whose j:shows changes is a changed claim: applying drops it to j:inferred.
    Those bullets are printed as the re-confirm list. Nothing is applied: read it with
    `jsk kb apply FILE --dry-run`, then apply it.
    """
    from ....application.record.merge import merge
    from ....application.record.refusals import Problems, Unclean
    from ....domain.record.writer import curies
    from ....graph import store as S
    from ....infra.oxigraph import record as R

    out, code = draft_out(flags)
    if code is not None:
        return code
    into = flags.get("--into")
    if len(args) != 1 or into is None:
        return usage("jsk kb merge c:a --into c:b - the concept to merge away, and the one "
                     "it becomes")
    try:
        merged = merge(root, args[0], into, load=S.load, state=R.state)
    except Unclean as err:
        return unlogged(err.state)
    except Problems as err:
        return refuse_each(err.problems)
    m, a = merged.draft, merged.a
    report = sys.stdout if out else sys.stderr
    for note in m["notes"]:
        print(f"note     {note}", file=report)
    if m["named_by"]:
        print(f"note     {curies(m['named_by'])} still name {curies([a])}, so it is retired, "
              "not deleted - re-point them to it and delete it later", file=report)
    if m["reconfirm"]:
        print(f"re-confirm {curies(m['reconfirm'])}", file=report)
        print("         applying drops them to inferred: read each again with the person, "
              "then `jsk kb confirm <ids> --answer \"...\"`", file=report)
    return drafted(merged.text, out, merged.summary)
