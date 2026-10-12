"""Where an advertisement is read from: a board's public JSON API over the network, or a
file - .docx, .html or text - on disk. zipfile and xml.etree load only when a .docx is
read."""
import json
import os
import re
import urllib.error
import urllib.request

from ..domain.posting.errors import BROWSER_FIX, NotOnBoard, Refused
from ..domain.posting.json_ld import page_advert

TIMEOUT = 30
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FILE_KINDS = (".docx", ".html", ".htm", ".txt", ".md")


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
        raise Refused(f"{name}: a {kind or 'extensionless'} file is not one posting_capture "
                      f"reads",
                      "fix:  save the posting as .docx, .html or .txt and capture that file, "
                      "or capture the advertisement verbatim as text")
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
                          "as .txt and capture that") from None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Refused(f"{name} is not UTF-8 text",
                      "fix:  save it again as UTF-8 and capture it again") from None
    if kind in (".html", ".htm"):
        return page_advert(text)
    return "", text.replace("\r\n", "\n").strip("\n")
