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
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

POSTING = "posting.md"
USAGE = ("usage: jsk posting fetch <url>|<file> <application-dir>\n"
         "       jsk posting extract <application-dir>\n"
         "       jsk posting build <application-dir> [<decisions-file>] [--replace]")
TIMEOUT = 30
BROWSER_FIX = ("fix:  fetch it with a browser tool and write posting.md with the Write "
               "tool - the advertisement verbatim, the URL on its first line")


class Refused(Exception):
    """A refusal: its message, then the fix line. `problems` is every (message, fix) it
    holds - several when `jsk posting build` found more than one, since a build that
    stopped at the first cost Schneider's run six builds."""

    def __init__(self, message, fix, problems=None):
        super().__init__(message)
        self.fix = fix
        self.problems = problems or [(message, fix)]

    @classmethod
    def every(cls, problems):
        """One refusal holding every (message, fix): the problem itself when there is one,
        else the count, each problem keeping its own fix."""
        if len(problems) == 1:
            return cls(*problems[0])
        return cls(f"{len(problems)} problems", "fix:  each problem above has its own fix",
                   problems)


class NotOnBoard(Exception):
    """The board answered, and this posting is not on it."""


# --- which board -----------------------------------------------------------------

# (provider, host pattern, path pattern). Anything after the id - Ashby's
# `/application`, Lever's `/apply`, a query string - is the same posting.
BOARDS = (
    ("ashby", re.compile(r"^jobs\.ashbyhq\.com$"),
     re.compile(r"^/(?P<org>[^/]+)/(?P<job>[0-9a-fA-F-]{36})(?:/.*)?$")),
    ("greenhouse", re.compile(r"^(?:job-)?boards(?:\.eu)?\.greenhouse\.io$"),
     re.compile(r"^/(?P<org>[^/]+)/jobs/(?P<job>\d+)(?:/.*)?$")),
    ("lever", re.compile(r"^jobs(?P<eu>\.eu)?\.lever\.co$"),
     re.compile(r"^/(?P<org>[^/]+)/(?P<job>[0-9a-fA-F-]{36})(?:/.*)?$")),
)


def recognise(url):
    """(provider, org, job id, API URL) for a posting URL a board serves, else None."""
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower()
    for provider, host_re, path_re in BOARDS:
        at = host_re.match(host)
        found = path_re.match(parts.path) if at else None
        if not found:
            continue
        org, job = found.group("org"), found.group("job")
        quoted = urllib.parse.quote(org, safe="")
        if provider == "ashby":
            api = (f"https://api.ashbyhq.com/posting-api/job-board/{quoted}"
                   f"?includeCompensation=true")
        elif provider == "greenhouse":
            api = f"https://boards-api.greenhouse.io/v1/boards/{quoted}/jobs/{job}"
        else:
            region = ".eu" if at.group("eu") else ""
            api = f"https://api{region}.lever.co/v0/postings/{quoted}/{job}"
        return provider, org, job, api
    return None


def fetch_json(api_url):
    """The one network call, kept apart so the tests can replace it.

    A 404 is an answer - no such posting, or no such board - and is NotOnBoard; any
    other failure is the network's and is Refused."""
    request = urllib.request.Request(api_url, headers={
        "Accept": "application/json", "User-Agent": "jsk-posting-fetch"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NotOnBoard(api_url) from exc
        raise Refused(f"the board answered HTTP {exc.code} for {api_url}",
                      "fix:  try again later, or " + BROWSER_FIX[6:]) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        raise Refused(f"could not read {api_url}: {reason}",
                      "fix:  check the network and try again, or " + BROWSER_FIX[6:]) from exc


# --- HTML to text ----------------------------------------------------------------

BLOCKS = {"p", "div", "section", "article", "header", "footer", "main", "aside",
          "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "tr",
          "blockquote", "pre", "figure", "hr", "dl", "dt", "dd"}


class _Text(HTMLParser):
    """Paragraphs for blocks, `- ` lines for list items, whitespace as a browser
    collapses it. Nothing else: the words are the advertisement's."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.pending = 0          # newlines owed before the next text
        self.prefix = None        # a list item's "- ", written with its first text
        self.lists = 0
        self.items = 0            # open <li> elements
        self.pre = 0
        self.skip = 0             # <script>, <style>
        self.line_start = True

    def _break(self, n):
        if not self.out:
            return
        if self.items and self.prefix is None:
            n = 1                 # a paragraph inside an item stays in that item
        self.pending = max(self.pending, n)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "br":
            self.out.append("\n")
            self.pending, self.line_start = 0, True
        elif tag == "li":
            self.items += 1
            self.prefix = "  " * max(self.lists - 1, 0) + "- "
            self.pending = max(self.pending, 1) if self.out else 0
        elif tag in BLOCKS:
            if tag in ("ul", "ol"):
                self.lists += 1
            if tag == "pre":
                self.pre += 1
            if self.prefix is None:
                self._break(1 if self.items else 2)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(self.skip - 1, 0)
        elif tag == "li":
            self.items = max(self.items - 1, 0)
            self.prefix = None
            self._break(1)
        elif tag in BLOCKS:
            if tag in ("ul", "ol"):
                self.lists = max(self.lists - 1, 0)
            if tag == "pre":
                self.pre = max(self.pre - 1, 0)
            self._break(1 if self.items or tag in ("tr", "dt") else 2)

    def handle_data(self, data):
        if self.skip:
            return
        text = data if self.pre else re.sub(r"\s+", " ", data)
        if self.line_start or self.pending:
            text = text.lstrip(" ")
        if not text:
            return
        if self.pending:
            self.out.append("\n" * self.pending)
            self.pending, self.line_start = 0, True
        if self.prefix is not None:
            self.out.append(self.prefix)
            self.prefix = None
        self.out.append(text)
        self.line_start = text.endswith("\n")

    def text(self):
        joined = "".join(self.out)
        lines = [line.rstrip() for line in joined.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def html_to_text(markup):
    parser = _Text()
    parser.feed(markup or "")
    parser.close()
    return parser.text()


# --- one posting, per board -------------------------------------------------------

def spaced(value):
    """`FullTime` -> `Full time`, `OnSite` -> `On site`: the board's enum, readable."""
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(value)).replace("_", " ").split()
    if not words:
        return ""
    return " ".join([words[0][:1].upper() + words[0][1:]] + [w.lower() for w in words[1:]])


def day(value):
    """YYYY-MM-DD from an ISO timestamp or epoch milliseconds, or None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.datetime.fromtimestamp(value / 1000, datetime.timezone.utc) \
            .date().isoformat()
    found = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value or ""))
    return found.group(1) if found else None


def distinct(*values):
    seen, kept = set(), []
    for value in values:
        value = (value or "").strip() if isinstance(value, str) else value
        if value and value.lower() not in seen:
            seen.add(value.lower())
            kept.append(value)
    return kept


def ashby(data, org, job):
    """The job whose id is the URL's, off the whole board Ashby's API returns."""
    wanted = job.lower()
    jobs = (data or {}).get("jobs") or []
    posting = next((j for j in jobs if str(j.get("id", "")).lower() == wanted), None)
    if posting is None:
        raise NotOnBoard(job)
    places = [posting.get("location")]
    for other in posting.get("secondaryLocations") or []:
        places.append(other.get("location") if isinstance(other, dict) else other)
    workplace = posting.get("workplaceType")
    remote = spaced(workplace) if workplace else ("Remote" if posting.get("isRemote") else None)
    # Only what the page itself shows: a board can hold a range it does not advertise.
    pay = ((posting.get("compensation") or {}).get("compensationTierSummary")
           if posting.get("shouldDisplayCompensationOnJobPostings") else None)
    facts = distinct(org, posting.get("department"), posting.get("team"),
                     " / ".join(distinct(*places)), remote,
                     spaced(posting.get("employmentType") or ""), pay)
    published = day(posting.get("publishedAt"))
    if published:
        facts.append(f"Published {published}")
    # descriptionPlain is Ashby's own text of the description: preferred, because it
    # is theirs, not a conversion of it.
    description = (posting.get("descriptionPlain") or "").strip() \
        or html_to_text(posting.get("descriptionHtml"))
    return posting.get("title") or "", facts, description


def greenhouse(data, org, job):
    """Greenhouse's content is HTML with its markup escaped once more."""
    data = data or {}
    if not data.get("title"):
        raise NotOnBoard(job)
    departments = [d.get("name") for d in data.get("departments") or [] if isinstance(d, dict)]
    facts = distinct(data.get("company_name") or org, *departments,
                     (data.get("location") or {}).get("name"))
    published, updated = day(data.get("first_published")), day(data.get("updated_at"))
    if published:
        facts.append(f"Published {published}")
    elif updated:
        facts.append(f"Updated {updated}")
    return data["title"], facts, html_to_text(html.unescape(data.get("content") or ""))


def lever(data, org, job):
    """Lever splits a posting into an opening, titled lists, and a closing."""
    data = data or {}
    if not data.get("text"):
        raise NotOnBoard(job)
    cats = data.get("categories") or {}
    places = cats.get("allLocations") or [cats.get("location")]
    facts = distinct(org, cats.get("department"), cats.get("team"),
                     " / ".join(distinct(*places)),
                     spaced(data.get("workplaceType") or "")
                     if data.get("workplaceType") not in (None, "unspecified") else None,
                     cats.get("commitment"))
    published = day(data.get("createdAt"))
    if published:
        facts.append(f"Published {published}")
    parts = [(data.get("descriptionPlain") or "").strip()
             or html_to_text(data.get("description"))]
    for section in data.get("lists") or []:
        body = html_to_text(section.get("content"))
        parts.append("\n\n".join(p for p in ((section.get("text") or "").strip(), body) if p))
    parts.append((data.get("additionalPlain") or "").strip()
                 or html_to_text(data.get("additional")))
    return data["text"], facts, "\n\n".join(p for p in parts if p)


READERS = {"ashby": ashby, "greenhouse": greenhouse, "lever": lever}


def posting_md(url, title, facts, description):
    """The URL on line 1, then the title, the facts and the description verbatim."""
    lines = [url.strip(), "", f"# {title.strip()}", ""]
    if facts:
        lines += [" · ".join(facts), ""]
    lines.append(description.rstrip())
    return "\n".join(lines) + "\n"


# --- a file ----------------------------------------------------------------------

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FILE_KINDS = (".docx", ".html", ".htm", ".txt", ".md")


def _runs(node, out):
    """A paragraph's text in document order: its `w:t` runs, `w:tab` as a space, `w:br`
    and `w:cr` as a line break. A paragraph nested in it (a text box) is its own."""
    for child in node:
        if child.tag == W + "p":
            continue
        if child.tag == W + "t":
            out.append(child.text or "")
        elif child.tag == W + "tab":
            out.append(" ")
        elif child.tag in (W + "br", W + "cr"):
            out.append("\n")
        else:
            _runs(child, out)
    return out


def docx_text(data):
    """(title, text) of a .docx's word/document.xml: one line per paragraph, `## ` for a
    Heading style, `- ` for a numbered or List style paragraph (indented by its level),
    the first Title-style paragraph as the title. Paragraphs are blank-line separated
    and list items are not, as html_to_text writes them. Raises ValueError."""
    import io as _io
    import xml.etree.ElementTree as ET
    import zipfile

    try:
        with zipfile.ZipFile(_io.BytesIO(data)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError(str(exc)) from None
    body = root.find(W + "body")
    title, blocks = "", []           # blocks: (is a list item, line)
    for p in (body.iter(W + "p") if body is not None else ()):
        text = "".join(_runs(p, [])).strip()
        text = "\n".join(re.sub(r"[ \t]+", " ", x).strip() for x in text.split("\n"))
        if not text:
            continue
        style = p.find(f"{W}pPr/{W}pStyle")
        style = (style.get(W + "val") or "") if style is not None else ""
        num = p.find(f"{W}pPr/{W}numPr")
        if style == "Title" and not title:
            title = text.replace("\n", " ")
        elif style.lower().startswith("heading"):
            blocks.append((False, "## " + text.replace("\n", " ")))
        elif num is not None or style.lower().startswith("list"):
            level = num.find(f"{W}ilvl") if num is not None else None
            depth = int(level.get(W + "val") or 0) if level is not None else 0
            blocks.append((True, "  " * depth + "- " + text))
        else:
            blocks.append((False, text))
    lines = []
    for i, (item, line) in enumerate(blocks):
        if lines and not (item and blocks[i - 1][0]):
            lines.append("")
        lines.append(line)
    return title, "\n".join(lines)


def read_file(path):
    """(title, text) of a posting saved as a file. Raises Refused."""
    name = os.path.basename(path)
    kind = os.path.splitext(name)[1].lower()
    if kind not in FILE_KINDS:
        raise Refused(f"{name}: a {kind or 'extensionless'} file is not one posting fetch "
                      f"reads",
                      "fix:  save the posting as .docx, .html or .txt and fetch that file, "
                      "or write posting.md with the Write tool - the advertisement "
                      "verbatim, `Source: <file name>` on its first line")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise Refused(f"could not read {path}: {exc.strerror or exc}",
                      "fix:  check the path, and that the file is not open elsewhere") \
            from None
    if kind == ".docx":
        try:
            return docx_text(data)
        except ValueError as exc:
            raise Refused(f"{name} is not a Word document this can read ({exc})",
                          "fix:  open it in Word and save it again as .docx, or save it "
                          "as .txt and fetch that") from None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Refused(f"{name} is not UTF-8 text",
                      "fix:  save it again as UTF-8 and fetch it again") from None
    if kind in (".html", ".htm"):
        return "", html_to_text(text)
    return "", text.replace("\r\n", "\n").strip("\n")


def file_md(name, title, text):
    """(title, posting.md): `Source: <file name>` on line 1, then the title and the text
    as posting_md writes them. With no title, the text's first line is the title, unless
    the text has a `# ` heading of its own - a .md already written as posting.md is."""
    lines = text.split("\n")
    own = next((m.group(1).strip() for m in map(re.compile(r"# (\S.*)").match, lines) if m),
               None)
    if not title and own is not None:
        return own, "Source: " + name + "\n\n" + text.strip("\n") + "\n"
    if not title:
        first = next((i for i, x in enumerate(lines) if x.strip()), 0)
        title = re.sub(r"^(#+|[-*•])\s+", "", lines[first].strip())
        text = "\n".join(lines[first + 1:])
    return title, posting_md(f"Source: {name}", title, [], text.strip("\n"))


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
