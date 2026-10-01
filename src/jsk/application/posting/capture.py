"""`posting_capture`: an advert fetched or pasted, stored as a draft posting's lines.

Ruling 1 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: a
graph-native posting keeps no posting.md. The advert comes through `jsk posting fetch`'s
machinery (application/posting/fetch.py: a board's API or a file) or as pasted text, is
numbered by advert_lines exactly as `jsk posting extract` numbers it, and is written as the
posting graph `{Posting (j:state draft), AdvertLine*}` - no requirement yet; posting_decide
adds those (application/posting/decide.py).

It creates no directory and writes no file: the directory is the first render's (Ruling
12). It refuses, each with its fix: a stem that gives no id; no advert (neither `url` nor
`text`, or both); an advert whose company or title neither the board, its header nor the
arguments give; a posting already captured, unless `replace`, which drops the review and
the assessment with it, since they answered another advert; an application made from files
(Ruling 11); a sent application. It prints nothing.
"""
from dataclasses import dataclass

from ...domain.posting.errors import Refused
from . import native as N


@dataclass(frozen=True)
class Captured:
    """What one capture wrote."""

    target: str                 # the posting graph's name
    stem: str                   # the application's stem
    company: str
    title: str
    lines: int                  # the advert's lines stored
    qualifications: int         # of them, the qualification lines a decision must answer
    replaced: tuple             # the graphs a replace dropped, by name


def capture(root, stem, *, url=None, text=None, company=None, title=None, captured=None,
            replace=False, today, get, read_file, ports):
    """Store the advert at `url`, or the pasted `text`, as `applications/<stem>`'s draft
    posting. The caller holds the workspace's turn.

    Args:
        root: the workspace root.
        stem: the application's name, `applications/<stem>`.
        url: a board posting's URL, or a file's path; or None with `text`.
        text: the advert, pasted; or None with `url`.
        company: the employer, when the advert does not say it in a way it can be read.
        title: the advertised title, likewise.
        captured: the day the advert was saved, ISO; `today` when None.
        replace: write over a posting already captured, dropping its review and assessment.
        today: the day it is captured when `captured` is None.
        get: api url -> the board's JSON answer (ports.posting_source.PostingSource.get).
        read_file: path -> (title, text) of a .docx, .html or text file.
        ports: the bound ports (compose.native.Ports).

    Returns:
        The Captured.

    Raises:
        Refused: every reason above, and nothing is written.
    """
    from ...domain.posting.advert import advert_lines
    from ...domain.posting.decide import advert_header
    from .fetch import advert, source

    app = N.app_of(root, stem)
    if (url is None) == (text is None):
        raise Refused("posting_capture takes the advert's url or its text, one of them",
                      "fix:  pass `url` for a board posting or a file, or `text` pasted")
    store = N.loaded(app, ports)
    found = N.kind(store, app, ports.is_file)
    if found == "legacy":
        raise N.legacy_refusal(app)
    N.refuse_if_sent(app, store, ports)
    if found == "native" and not replace:
        raise Refused(f"{app.graph('posting')} already holds its advert",
                      "fix:  pass replace to capture it again - its requirements, review "
                      "and assessment go with it")
    board_title = None
    if url is not None:
        board_title, text = advert(url, source(url), get=get, read_file=read_file)
    text = (text or "").replace("\r\n", "\n")
    said_title, said_company, said_url = advert_header(text or "")
    head = {"company": (company or said_company or "").strip(),
            "title": (title or board_title or said_title or "").strip(),
            "url": (url if url and url.startswith(("http://", "https://")) else said_url)}
    missing = [key for key in ("company", "title") if not head[key]]
    if missing:
        raise Refused(f"the advert does not say its {' or '.join(missing)} in a way jsk can "
                      "read", f"fix:  pass {' and '.join(missing)} with the advert")
    lines = advert_lines(text or "")
    if not lines:
        raise Refused("the advert holds no line a requirement could quote",
                      "fix:  check it is the advertisement, verbatim")
    s = N.Stored(head, "", [], captured or today.isoformat(), "draft", lines, {}, {})
    graphs: dict = {"posting": N.triples(app, s, "draft")}
    dropped = [k for k in ("review", "gaps") if app.graph(k) in store.parsed]
    for kind in dropped:
        graphs[kind] = None
    names, broken = N.write(app, store, graphs, ports)
    if broken:
        raise Refused.every([(text_, fix) for _, text_, fix in broken])
    return Captured(names[0], stem, head["company"], head["title"], len(lines),
                    sum(x.section == "qualification" and not x.elig for x in lines),
                    tuple(app.graph(k) for k in dropped))
