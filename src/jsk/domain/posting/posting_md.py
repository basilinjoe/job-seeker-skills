"""posting.md as jsk writes it: the source on its first line, the title, the facts, then
the advertisement verbatim."""
import re


def posting_md(url, title, facts, description):
    """The URL on line 1, then the title, the facts and the description verbatim."""
    lines = [url.strip(), "", f"# {title.strip()}", ""]
    if facts:
        lines += [" · ".join(facts), ""]
    lines.append(description.rstrip())
    return "\n".join(lines) + "\n"


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
