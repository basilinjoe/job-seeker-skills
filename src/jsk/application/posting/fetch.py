"""`jsk posting fetch`: a posting on a public job board, or in a file, written as an
application's posting.md. It prints nothing; adapters/cli/posting.py says what it wrote.
"""
import os
import urllib.parse
from dataclasses import dataclass

from ...domain.posting.boards import READERS, recognise
from ...domain.posting.errors import BROWSER_FIX, POSTING, NotOnBoard, Refused
from ...domain.posting.posting_md import file_md, posting_md


@dataclass(frozen=True)
class Fetched:
    """What one fetch wrote."""

    path: str                   # the posting.md written
    title: str
    chars: int                  # posting.md's length


def fetch(url, app_dir, *, get, read_file, write):
    """Write `app_dir`/posting.md from the board's API, or from a file there is at `url`.

    Args:
        url: the posting's URL as a person would open it, or a file's path.
        app_dir: the application's directory, created if missing.
        get: api url -> the board's JSON answer (ports.posting_source.PostingSource.get).
        read_file: path -> (title, text) of a .docx, .html or text file.
        write: (app_dir, target, text) -> the path written; never over a file there is.

    Returns:
        The Fetched.

    Raises:
        Refused: a board this does not know, a posting not on its board, a network
            failure, a file it cannot read, or a posting.md already there; nothing written.
    """
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
        return Fetched(write(app_dir, target, text), title, len(text))
    provider, org, job, api = known
    try:
        data = get(api)
        title, facts, description = READERS[provider](data, org, job)
    except NotOnBoard:
        raise Refused(f"job {job} is not on the {provider} board for {org!r}",
                      "fix:  the posting may be closed - check the URL in a browser") from None
    if not description.strip():
        raise Refused(f"the {provider} posting {job} came back with no description",
                      BROWSER_FIX)
    title = title.strip()
    text = posting_md(url, title, facts, description)
    return Fetched(write(app_dir, target, text), title, len(text))
