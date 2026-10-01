"""`jsk posting`'s old module path: where its ports are bound until P6.

The command is adapters/cli/posting.py and the fetch application/posting/fetch.py; this
module keeps the path, the names callers and tests reach through it, and the board's API
as `fetch_json`, which a test patches here: `fetch` looks it up at each call (Ruling 4 of
the onion design). Only urllib at import: extract and build load graph.postingbuild when
they run, and a .docx loads zipfile and xml.etree when it is read.
"""
import os
import sys

from .domain.posting.boards import BOARDS as BOARDS
from .domain.posting.boards import READERS as READERS
from .domain.posting.boards import ashby as ashby
from .domain.posting.boards import day as day
from .domain.posting.boards import distinct as distinct
from .domain.posting.boards import greenhouse as greenhouse
from .domain.posting.boards import lever as lever
from .domain.posting.boards import recognise as recognise
from .domain.posting.errors import BROWSER_FIX as BROWSER_FIX
from .domain.posting.errors import POSTING as POSTING
from .domain.posting.errors import NotOnBoard as NotOnBoard
from .domain.posting.errors import Refused as Refused
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


def fetch(url, app_dir, get=None):
    """(path written, title, characters) (application.posting.fetch.fetch). Raises Refused.

    `get` is fetch_json unless a test hands in its own; looked up at call time so a
    patch of the module attribute reaches it too. A `url` that is a file there is is
    read from disk instead."""
    from .application.posting.fetch import fetch as fetched

    done = fetched(url, app_dir, get=get or fetch_json, read_file=read_file, write=write)
    return done.path, done.title, done.chars


def write(app_dir, target, text):
    """Write posting.md, creating the application's directory; never over a file there is.

    Args:
        app_dir: the application's directory.
        target: posting.md's path in it.
        text: posting.md's text.

    Returns:
        `target`.

    Raises:
        FileExistsError: `target` is there.
    """
    os.makedirs(app_dir, exist_ok=True)
    with open(target, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return target


def main(argv=None):
    """`jsk posting` (adapters.cli.posting.main), with this module's fetch."""
    from .adapters.cli.posting import main as posting

    return posting(list(sys.argv[1:] if argv is None else argv), fetch=fetch)


if __name__ == "__main__":
    from .cliutil import retired_path

    sys.exit(retired_path("jsk.posting", "jsk posting"))
