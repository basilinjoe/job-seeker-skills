"""An advert read off a public job board or out of a file, as the text `posting_capture`
numbers into lines (application/posting/capture.py). It writes nothing and prints nothing.

It was `jsk posting fetch`, which wrote the text to an application's posting.md; that verb
retired in 6.0 with the file-made pipeline (docs/superpowers/plans/
2026-10-03-retire-file-pipeline.md, P2), and capture kept the reading: `source` says which
board a URL is on, `advert` reads it. The text keeps posting.md's layout - the source on its
first line, the title, the facts, then the advertisement verbatim - because advert_lines
numbers exactly that layout, and a frozen application's posting.md still reads the same way.
"""
import os
import re
import urllib.parse

from ...domain.posting.boards import READERS, recognise
from ...domain.posting.errors import BROWSER_FIX, NotOnBoard, Refused


def advert_text(url, title, facts, description):
    """The advert as one text: the URL on line 1, then the title, the facts and the
    description verbatim."""
    lines = [url.strip(), "", f"# {title.strip()}", ""]
    if facts:
        lines += [" · ".join(facts), ""]
    lines.append(description.rstrip())
    return "\n".join(lines) + "\n"


def file_advert(name, title, text):
    """(title, the advert's text) for a file: `Source: <file name>` on line 1, then the
    title and the text as advert_text lays them out. With no title, the text's first line
    is the title, unless the text has a `# ` heading of its own."""
    lines = text.split("\n")
    own = next((m.group(1).strip() for m in map(re.compile(r"# (\S.*)").match, lines) if m),
               None)
    if not title and own is not None:
        return own, "Source: " + name + "\n\n" + text.strip("\n") + "\n"
    if not title:
        first = next((i for i, x in enumerate(lines) if x.strip()), 0)
        title = re.sub(r"^(#+|[-*•])\s+", "", lines[first].strip())
        text = "\n".join(lines[first + 1:])
    return title, advert_text(f"Source: {name}", title, [], text.strip("\n"))


def source(url):
    """The board `url` is on, or None for a file there is.

    Args:
        url: the posting's URL as a person would open it, or a file's path.

    Returns:
        boards.recognise's (provider, org, job, api), or None for a file.

    Raises:
        Refused: neither a board this knows nor a file there is.
    """
    if os.path.isfile(url):
        return None
    known = recognise(url)
    if known is None:
        if urllib.parse.urlsplit(url.strip()).scheme in ("http", "https"):
            raise Refused(f"{url} is not an Ashby, Greenhouse or Lever posting URL",
                          BROWSER_FIX)
        raise Refused(f"{url} is neither a posting URL nor a file there is",
                      "fix:  check the path, or give the posting's URL")
    return known


def advert(url, known, *, get, read_file):
    """(title, the advert's text) for the board posting or file at `url`.

    Args:
        url: the posting's URL, or a file's path.
        known: source(url).
        get: api url -> the board's JSON answer (ports.posting_source.PostingSource.get).
        read_file: path -> (title, text) of a .docx, .html or text file.

    Raises:
        Refused: a posting not on its board, a network failure, or a file with no text.
    """
    if known is None:
        name = os.path.basename(url)
        title, text = read_file(url)
        if not text.strip():
            raise Refused(f"{name} holds no text",
                          "fix:  check it is the posting, or capture the advertisement "
                          "verbatim as text (`posting_capture` with text)")
        return file_advert(name, title, text)
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
    return title, advert_text(url, title, facts, description)
