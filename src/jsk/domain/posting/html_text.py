"""A board's or a saved page's HTML as text: paragraphs, `- ` list items, entities, and
nothing else rewritten."""
import re
from html.parser import HTMLParser

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
    """The text of `markup` as a browser would lay it out; "" for None."""
    parser = _Text()
    parser.feed(markup or "")
    parser.close()
    return parser.text()


def spaced(value):
    """`FullTime` -> `Full time`, `OnSite` -> `On site`: the board's enum, readable."""
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(value)).replace("_", " ").split()
    if not words:
        return ""
    return " ".join([words[0][:1].upper() + words[0][1:]] + [w.lower() for w in words[1:]])
