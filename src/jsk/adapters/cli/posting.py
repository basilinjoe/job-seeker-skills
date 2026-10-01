"""A posting on a public job board, written as an application's posting.md - and then
its requirements, written into the record as the application's posting.

Usage: jsk posting fetch <url>|<file> <application-dir>
       jsk posting extract <application-dir>
       jsk posting build <application-dir> [<decisions-file>] [--replace]

  <url>              the posting as a person would open it:
                       https://jobs.ashbyhq.com/<org>/<job-uuid>
                       https://boards.greenhouse.io/<org>/jobs/<id>  (or job-boards.)
                       https://jobs.lever.co/<org>/<id>
  <file>             the posting as a file: .docx, .html/.htm (a saved page) or .txt/.md
  <application-dir>  applications/<stem>, created if missing

Reads the board's public JSON API - no key, no browser - and writes
<application-dir>/posting.md: the URL on its first line, the title, one line of the
facts the board states, then the description verbatim. A board that serves HTML has it
turned into text - paragraphs, `- ` list items, entities - and nothing else rewritten.
A file is read where it is: `Source: <file name>` on the first line, then its text. A
.docx gives one line per paragraph, `## ` for a Heading style, `- ` for a list
paragraph, its Title as the title; .html is turned into text as a board's is; .txt and
.md are taken as they are. posting.md is never overwritten.

extract prints the header decisions.txt starts with, then every line of posting.md a
requirement could quote: numbered, with its section (qual, resp, other), a flag (opt:
optional-worded; elig: eligibility, never a requirement) and the concepts its labels name.

build reads decisions.txt (default <application-dir>/decisions.txt) - `n | slug | asked |
concepts | need` rows and `n | - | reason` drops - and writes the posting into
career/store/, each quote the extracted line itself. Every qual and resp line must be used
or dropped. An existing posting is replaced only with --replace, and its assessment goes
with it in the same write. WARNs past 20 requirements, and on a responsibility made
required that its line does not call required.

Exit 0 written or printed; 1 refused - a board this does not know, a posting not on its
board, a network failure, a file it cannot read, a posting.md already there, a decisions
file that does not hold - each with its fix, nothing written; 2 called wrong.

Written after the ElevenLabs run (2026-09-25), where the posting came off Ashby's API
through hand-written curl and inline Python and posting.md was assembled by hand: the
one input every requirement quotes, made by the least repeatable step of the run. The
file argument came after the Arrow run (2026-09-29), where a .docx was unzipped with
inline Python and posting.md typed back out through the context.
Only urllib at import: extract and build load graph.postingbuild when they run, and a
.docx loads zipfile and xml.etree when it is read.
"""
import datetime

USAGE = ("usage: jsk posting fetch <url>|<file> <application-dir>\n"
         "       jsk posting extract <application-dir>\n"
         "       jsk posting build <application-dir> [<decisions-file>] [--replace]")


def main(args, *, fetch):
    """`jsk posting fetch|extract|build`: one verb run, what it wrote said.

    Args:
        args: the arguments after `jsk posting`.
        fetch: (url, app_dir) -> (path, title, characters); the entry point binds its own,
            so the board's API is the one jsk.posting names.

    Returns:
        The exit code: 0 written or printed, 1 refused, 2 called wrong.
    """
    from ...cliutil import wants_help
    from ...domain.posting.errors import Refused

    args = list(args)
    if wants_help(args):
        print((__doc__ or "").split("\n\nWritten after", 1)[0])
        return 0
    verb = args[0] if args else None
    replace = verb == "build" and "--replace" in args
    if replace:
        args.remove("--replace")
    if not ((verb == "fetch" and len(args) == 3) or (verb == "extract" and len(args) == 2)
            or (verb == "build" and len(args) in (2, 3))) \
            or any(a.startswith("--") for a in args):
        print(USAGE)
        return 2
    try:
        if verb == "fetch":
            target, title, count = fetch(args[1], args[2])
            print(f"wrote  {target}   {title}   {count} chars")
        elif verb == "extract":
            print(extracted(args[1], datetime.date.today()), end="")
        else:
            done = built(args[1], args[2] if len(args) == 3 else None, replace,
                         datetime.date.today())
            print(f"wrote {done.target}  {done.count} requirements")
            for w in done.warnings:
                print(f"WARN - {w}")
    except Refused as exc:
        print(f"REFUSED - {exc}")
        if len(exc.problems) == 1:
            print(exc.fix)
        else:
            for message, fix in exc.problems:
                print(message)
                print(fix)
        return 1
    return 0


def extracted(app_dir, today):
    """`jsk posting extract`'s text (application.posting.extract) over the folder on disk.

    Raises:
        Refused: there is no readable posting.md.
    """
    from ...application.posting.extract import extract
    from ...graph.postingbuild import PostingFolder

    return extract(app_dir, None, today, folder=PostingFolder())


def built(app_dir, decisions_path, replace, today):
    """`jsk posting build` (application.posting.build) inside the workspace's turn, with
    graph.postingbuild's triples as they are at the call.

    Returns:
        The Built.

    Raises:
        Refused: every problem, and nothing written.
    """
    from ...application.posting.build import build
    from ...graph import postingbuild as PB
    from ...infra.files import find_root
    from ...infra.oxigraph import record as R

    root = find_root(app_dir)
    with R.turn(root, dry_run=root is None):
        return build(app_dir, decisions_path, replace, None, today,
                     folder=PB.PostingFolder(), triples=PB.triples)
