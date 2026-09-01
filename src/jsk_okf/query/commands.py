"""The five read subcommands: parse, dispatch, print.

This module decides nothing about a bundle. It resolves the arguments, hands them to
the module that answers the question, and gives what came back to `render.emit`. That
split is what lets a listing be tested by reading its rows instead of parsing a table,
and it is why every query module has the same shape:

    run(bundle, args) -> render.Result

Nothing here returns 1. The exit codes are `0` it ran and `2` you called it wrong -
`query/__init__.py` has the argument.
"""

import argparse
import os
import sys

from . import filters, ids, render

VERBS = ("search", "list", "show", "refs", "stats")

# The nouns `okf list` answers to, in the order they are worth reading: the career
# concepts, then the claims inside them, then the tailoring artefacts, then the two
# cross-cutting audits. `listing.py` owns what each one shows.
NOUNS = ("projects", "roles", "orgs", "education",
         "skills", "bullets", "credentials", "metrics",
         "views", "postings", "questions", "capabilities",
         "unconfirmed", "orphans")

# The two nouns `audit.py` answers rather than `listing.py`. Listed here rather than
# guessed at by name, so that adding a third is a decision made in one place.
AUDITS = {"unconfirmed": "unconfirmed", "orphans": "orphans"}

# The two directories that make a path a bundle - `authoring.common.REQUIRED_DIRECTORIES`
# says the same thing for the write layer. Duplicated deliberately rather than imported:
# reaching into `authoring` from here would make every read command load the write
# layer, and the read layer's whole promise is that it is cheap.
REQUIRED = ("projects", "roles")


def bundle_root(path):
    """The bundle, or a sentence naming what is not one about it."""
    if not os.path.isdir(path):
        raise filters.Bad(
            f"{path}: not a directory\n"
            f"fix:  pass the bundle's root - the folder holding projects/ and roles/. "
            f"`okf new <path> --name \"Full Name\"` scaffolds one")
    missing = [name for name in REQUIRED
               if not os.path.isdir(os.path.join(path, name))]
    if missing:
        raise filters.Bad(
            f"{path}: not a bundle - {', '.join(name + '/' for name in missing)} "
            f"is missing\n"
            f"fix:  pass the bundle's root, not a directory inside it")
    return path


def add_common(parser, top=True):
    # `okf refs` reads the archive whichever way this is passed - a sent application is
    # where most references to a posting or a view live, so "what still points at this"
    # has no useful narrow reading. The flag is still accepted there rather than
    # refused, because a caller adding it to every query should not have one command
    # fail, and `refs` says in its own output that it changes nothing.
    parser.add_argument("--archive", action="store_true",
                       help="also read tailoring/applications/ - the frozen copies "
                            "beside sent applications, which may not be edited. "
                            "`okf refs` reads them either way")
    parser.add_argument("--json", dest="as_json", action="store_true",
                       help="the whole answer as JSON, never truncated")
    if top:
        parser.add_argument("--top", type=int, default=render.DEFAULT_TOP, metavar="N",
                           help=f"rows before the remainder is summarised "
                                f"(default {render.DEFAULT_TOP}; 0 for every row)")


def add_metadata(parser):
    """The selection-key filters. Shared by `search` and `list` so the two cannot
    disagree about what `--capability` selects - see `filters.py`."""
    parser.add_argument("--type", action="append", metavar="T",
                       help="concept type, repeatable (e.g. --type Project)")
    parser.add_argument("--status", metavar="S",
                       help="provenance: confirmed | inferred | needs-verification")
    parser.add_argument("--capability", action="append", metavar="C",
                       help="a capability the concept carries; repeatable, and "
                            "repeats read as 'carries all of these'")
    parser.add_argument("--technology", action="append", metavar="T",
                       help="a technology the concept carries; repeatable")
    parser.add_argument("--domain", action="append", metavar="D",
                       help="a domain the concept carries; repeatable")
    parser.add_argument("--seniority", metavar="S", help="the seniority band")
    parser.add_argument("--strength", metavar="N",
                       help="evidence strength: 4, 4+ or 4-")
    parser.add_argument("--recency", metavar="Y",
                       help="the year last touched: 2023, 2023+ or 2023-")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="okf", description="Ask a career bundle a question. Reads, never writes.")
    verbs = parser.add_subparsers(dest="verb", metavar="<verb>")

    search = verbs.add_parser("search", help="find text or metadata across the bundle")
    search.add_argument("bundle")
    search.add_argument("text", nargs="?",
                       help="what to look for. Omit it and the filters alone select")
    search.add_argument("--scope", metavar="SUBDIR",
                       help="search only this subtree, bundle-relative")
    search.add_argument("--regex", action="store_true",
                       help="read the pattern as a regular expression")
    search.add_argument("--case-sensitive", dest="case_sensitive", action="store_true",
                       help="match case; folded by default")
    where = search.add_mutually_exclusive_group()
    where.add_argument("--frontmatter", action="store_true",
                      help="match only in frontmatter")
    where.add_argument("--body", action="store_true", help="match only in the body")
    add_metadata(search)
    add_common(search)

    listed = verbs.add_parser("list", help="an inventory of one kind of thing")
    listed.add_argument("bundle")
    listed.add_argument("noun", nargs="?", choices=NOUNS, metavar="<noun>",
                       help="one of: " + " ".join(NOUNS))
    add_metadata(listed)
    add_common(listed)

    show = verbs.add_parser("show", help="what one compiled id names, and where")
    show.add_argument("bundle")
    show.add_argument("id", nargs="?", metavar="ID")
    show.add_argument("--path", action="store_true",
                     help="print the bundle-relative path alone, for feeding to a "
                          "reader")
    add_common(show, top=False)

    refs = verbs.add_parser("refs", help="everything that still points at one thing")
    refs.add_argument("bundle")
    refs.add_argument("target", nargs="?", metavar="ID|STEM")
    add_common(refs)

    stats = verbs.add_parser("stats", help="what the bundle holds, counted")
    stats.add_argument("bundle")
    add_common(stats, top=False)

    return parser


def dispatch(args):
    """The verb, as (a Result, the more-flag to print under a cut).

    Each module is imported here and nowhere else, so a query pays for the one that
    answers it. `okf stats` does not load the search matcher.
    """
    bundle = bundle_root(args.bundle)

    if args.verb == "search":
        from . import search                              # noqa: PLC0415
        return search.run(bundle, args), None

    if args.verb == "list":
        if not args.noun:
            raise filters.Bad(
                "okf list needs a noun\n"
                f"fix:  one of {', '.join(NOUNS)}")
        if args.noun in AUDITS:
            from . import audit                           # noqa: PLC0415
            return getattr(audit, AUDITS[args.noun])(bundle, args), None
        from . import listing                             # noqa: PLC0415
        return listing.run(bundle, args.noun, args), None

    if args.verb == "show":
        if not args.id:
            raise filters.Bad(
                "okf show needs an id\n"
                "fix:  `okf list <bundle> projects` prints the ids that exist")
        return ids.show(bundle, args), None

    if args.verb == "refs":
        if not args.target:
            raise filters.Bad(
                "okf refs needs an id or a file stem\n"
                "fix:  `okf refs <bundle> prj_care_platform`, or the stem "
                "`care-platform`")
        from . import refs                                # noqa: PLC0415
        return refs.run(bundle, args.target, args), None

    from . import audit                                   # noqa: PLC0415
    return audit.stats(bundle, args), None


def main(argv):
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit:
        return 2
    if not args.verb:                                     # pragma: no cover - guard
        parser.print_help()
        return 2

    try:
        result, more = dispatch(args)
    except (filters.Bad, ids.Unknown, ValueError) as exc:
        render.console()
        print(str(exc))
        return 2
    except ImportError as exc:
        # Every verb imports its own module lazily, so a broken or partial install
        # surfaces here rather than at startup. Reported the way `cli.run()` reports a
        # missing script: a traceback out of a query reads as a bug in the bundle
        # somebody was asking about, and it exited 1 - which this layer promises never
        # to do, so the promise would have been broken by an install problem.
        render.console()
        print(f"cannot load the module behind `okf {args.verb}`: {exc}")
        print("fix:  the install is incomplete - reinstall with "
              "`pip install 'jsk-okf[all]'`")
        return 2

    # `--path` is the one answer that is not a table: it exists so a caller can put it
    # straight into a reader, and a heading above it would have to be stripped off.
    if args.verb == "show" and getattr(args, "path", False):
        print(result.rows[0]["file"])
        return 0

    return render.emit(result, args.verb, args.bundle,
                       top=getattr(args, "top", None),
                       as_json=args.as_json, more_flag=more)


if __name__ == "__main__":                                # pragma: no cover
    sys.exit(main(sys.argv[1:]))
