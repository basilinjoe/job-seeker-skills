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
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from .domain.posting.boards import BOARDS as BOARDS
from .domain.posting.boards import READERS
from .domain.posting.boards import ashby as ashby
from .domain.posting.boards import day as day
from .domain.posting.boards import distinct as distinct
from .domain.posting.boards import greenhouse as greenhouse
from .domain.posting.boards import lever as lever
from .domain.posting.boards import recognise
from .domain.posting.errors import BROWSER_FIX, POSTING, NotOnBoard, Refused
from .domain.posting.html_text import html_to_text as html_to_text
from .domain.posting.html_text import spaced as spaced
from .domain.posting.posting_md import file_md as file_md
from .domain.posting.posting_md import posting_md as posting_md
from .infra.posting_sources import FILE_KINDS as FILE_KINDS
from .infra.posting_sources import TIMEOUT as TIMEOUT
from .infra.posting_sources import W as W
from .infra.posting_sources import docx_text as docx_text
from .infra.posting_sources import fetch_json
from .infra.posting_sources import read_file

USAGE = ("usage: jsk posting fetch <url>|<file> <application-dir>\n"
         "       jsk posting extract <application-dir>\n"
         "       jsk posting build <application-dir> [<decisions-file>] [--replace]")


# --- the command -----------------------------------------------------------------

def fetch(url, app_dir, get=None):
    """(path written, title, characters). Raises Refused.

    `get` is fetch_json unless a test hands in its own; looked up at call time so a
    patch of the module attribute reaches it too. A `url` that is a file there is is
    read from disk instead."""
    is_file = os.path.isfile(url)
    known = None if is_file else recognise(url)
    if known is None and not is_file:
        if urllib.parse.urlsplit(url.strip()).scheme in ("http", "https"):
            raise Refused(f"{url} is not an Ashby, Greenhouse or Lever posting URL",
                          BROWSER_FIX)
        raise Refused(f"{url} is neither a posting URL nor a file there is",
                      "fix:  check the path, or give the posting's URL")
    target = os.path.join(app_dir, POSTING)
    # Before the network: a posting.md is what an application answered, and a
    # second fetch of a posting since edited would quietly change it.
    if os.path.exists(target):
        raise Refused(f"{target} already exists - posting.md is never overwritten",
                      "fix:  it is what this application answers; a different posting "
                      "is a different application directory")
    if known is None:
        name = os.path.basename(url)
        title, text = read_file(url)
        if not text.strip():
            raise Refused(f"{name} holds no text",
                          "fix:  check it is the posting, or write posting.md with the "
                          "Write tool - the advertisement verbatim")
        title, text = file_md(name, title, text)
        return write(app_dir, target, text), title, len(text)
    provider, org, job, api = known
    try:
        data = (get or fetch_json)(api)
        title, facts, description = READERS[provider](data, org, job)
    except NotOnBoard:
        raise Refused(f"job {job} is not on the {provider} board for {org!r}",
                      "fix:  the posting may be closed - check the URL in a browser") from None
    if not description.strip():
        raise Refused(f"the {provider} posting {job} came back with no description",
                      BROWSER_FIX)
    title = title.strip()
    text = posting_md(url, title, facts, description)
    return write(app_dir, target, text), title, len(text)


def write(app_dir, target, text):
    os.makedirs(app_dir, exist_ok=True)
    with open(target, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return target


def main(argv=None):
    from .cliutil import wants_help

    args = list(sys.argv[1:] if argv is None else argv)
    if wants_help(args):
        print(__doc__.split("\n\nWritten after", 1)[0])
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
            from .graph import postingbuild
            print(postingbuild.extract(args[1]), end="")
        else:
            from .graph import postingbuild
            target, count, warnings = postingbuild.build(
                args[1], args[2] if len(args) == 3 else None, replace=replace)
            print(f"wrote {target}  {count} requirements")
            for w in warnings:
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


if __name__ == "__main__":
    sys.exit(main())
