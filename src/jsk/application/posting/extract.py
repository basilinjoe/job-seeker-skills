"""`jsk posting extract`: the decisions.txt header, ready to copy, then every advert line a
requirement could quote - numbered, with its section, its flag and the concepts its labels
name. It prints nothing; adapters/cli/posting.py prints the text.
"""
import os
import re

from ...domain import ontology as O
from ...domain.posting.advert import advert_lines
from ...domain.posting.decide import DATED, SHORT, advert_header, seniority_hint
from ...domain.posting.errors import POSTING, Refused


def dir_stem(app_dir):
    """post_<this>: the directory's name without a leading date, `-` as `_`.

    Args:
        app_dir: the application's directory.

    Returns:
        The stem.
    """
    name = DATED.sub("", os.path.basename(os.path.abspath(app_dir))).lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def read_advert(app_dir, *, folder):
    """posting.md's text.

    Args:
        app_dir: the application's directory.
        folder: the application's folder and record (compose.posting.PostingFolder).

    Returns:
        The advert, normalised.

    Raises:
        Refused: there is no posting.md, or it is not UTF-8.
    """
    from ...domain.record.parsed import Missing, Unreadable

    path = os.path.join(app_dir, POSTING)
    try:
        return folder.read_text(path)
    except Missing:
        raise Refused(f"no {POSTING} in {app_dir}",
                      f"fix:  jsk posting fetch <url> {app_dir}, or write the advert verbatim "
                      f"to {path}") from None
    except Unreadable as e:
        raise Refused(str(e), f"fix:  {e.fix}") from None


def workspace(app_dir, vocabulary, *, folder):
    """(root, store) for the workspace above the application, or (None, None).

    Args:
        app_dir: the application's directory.
        vocabulary: the vocabulary file to load, or None for the shipped one.
        folder: the application's folder and record (compose.posting.PostingFolder).

    Returns:
        The workspace root and its loaded Store.
    """
    root = folder.find_root(app_dir)
    if root is None:
        return None, None
    return root, folder.load(root, vocabulary)


def posting_stem(app_dir, root, store, *, folder):
    """The stem of the Posting already in the posting graph - the application points at it -
    else the directory's.

    Args:
        app_dir: the application's directory.
        root: the workspace root.
        store: the loaded workspace, or None.
        folder: the application's folder and record (compose.posting.PostingFolder).

    Returns:
        The stem.
    """
    if store is not None:
        _, stem = folder.posting_of(store, folder.file_name(os.path.abspath(app_dir), root))
        if stem:
            return stem
    return dir_stem(app_dir)


def extract(app_dir, vocabulary, today, *, folder):
    """The decisions.txt header, ready to copy, then every advert line numbered with its
    section, its flag and the concepts its labels name.

    Args:
        app_dir: the application's directory.
        vocabulary: the vocabulary file to load, or None for the shipped one.
        today: the `captured:` day the header proposes.
        folder: the application's folder and record (compose.posting.PostingFolder).

    Returns:
        The text to print.

    Raises:
        Refused: there is no readable posting.md.
    """
    advert = read_advert(app_dir, folder=folder)
    title, company, url = advert_header(advert)
    root, store = workspace(app_dir, vocabulary, folder=folder)
    named = folder.labels_in(store) if store is not None else (lambda line: ())
    word, level = seniority_hint(title)
    out = []
    if root is None:
        out.append(f"# no workspace (career/store/) above {app_dir}: no concepts proposed")
    out += [f"# {title or '?'} at {company or '?'}",
            f"# posting id: post_{posting_stem(app_dir, root, store, folder=folder)}"]
    if word:
        out.append(f"# seniority hint: {word} -> {level}")
    out += [f"company: {company}", f"title: {title}", f"url: {url}",
            f"seniority: {level or ''}", "domain:",
            f"captured: {today.isoformat()}"]
    lines = advert_lines(advert)
    width = len(str(len(lines)))
    out.append("# every qual line is used or dropped; other and responsibility lines need no row")
    out.append(f"# {'n':<{width}} section flag line")
    for x in lines:
        flag = "elig" if x.elig else "opt" if x.optional else ""
        out.append(f"{x.n:<{width}} {SHORT[x.section]:<5} {flag:<4} {x.text}")
        found = named(x.text)
        if found:
            out.append(f"{'':<{width}} concepts: {', '.join('c:' + c[len(O.C):] for c in found)}")
    return "\n".join(out) + "\n"
