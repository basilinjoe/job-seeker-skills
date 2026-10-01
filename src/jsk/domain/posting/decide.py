"""A posting's decisions as data: decisions.txt's name, the seniority a title hints at,
the header posting.md states, the necessity a line defaults to, and the posting graph's
triples. Nothing here reads a file or the store: application/posting/ does.
"""
import re

from .advert import FIRST_LINE, REQUIRED_WORDS, squash
from .errors import POSTING

DECISIONS = "decisions.txt"
SOFT_CAP = 20
DATED = re.compile(r"\A\d{4}-\d{2}-\d{2}-")
# Ruling 11: a title word, as a hint only - the analyst decides.
SENIORITY_HINTS = (
    (re.compile(r"\b(principal|staff|architect)\b", re.I), "architecture-ownership"),
    (re.compile(r"\b(lead|manager)\b", re.I), "team-leadership"),
    (re.compile(r"\bsenior\b", re.I), "hands-on-senior"),
    (re.compile(r"\b(junior|graduate)\b", re.I), "junior"),
)
SHORT = {"qualification": "qual", "responsibility": "resp", "other": "other"}


def seniority_hint(title):
    """(the title word, the seniority it hints at), or (None, None): a hint only - the
    analyst decides.

    Args:
        title: the posting's title.

    Returns:
        The first SENIORITY_HINTS pattern the title matches, as (word, level).
    """
    for pattern, level in SENIORITY_HINTS:
        found = pattern.search(title or "")
        if found:
            return found.group(0).lower(), level
    return None, None


def advert_header(advert):
    """(title, company, url) as posting.md states them: the `# ` heading, the first fact
    of the `a · b · c` line under it, and a URL on line 1. With no `# ` heading the title
    is the first line that is not the URL or `Source:`, and the company is blank - a guess extract
    prints for the analyst to correct, where a blank title only made them type it."""
    lines = advert.split("\n")
    first = next((x.strip() for x in lines if x.strip()), "")
    url = first if re.fullmatch(r"https?://\S+", first) else ""
    title = company = ""
    for i, line in enumerate(lines):
        heading = re.match(r"# (.+)", line)
        if heading:
            title = heading.group(1).strip()
            facts = next((x.strip() for x in lines[i + 1:] if x.strip()), "")
            if " · " in facts:
                company = facts.split(" · ", 1)[0].strip()
            return title, company, url
    body = re.sub(r"\A---\n.*?\n---\n", "", advert, flags=re.S).split("\n")    # frontmatter
    title = next((squash(x.strip().lstrip("#")) for x in body
                  if x.strip().lstrip("#").strip() and not FIRST_LINE.fullmatch(x.strip())), "")
    return title, company, url


def default_need(line):
    """Rulings 2 and 6. A qualification is preferred when optional-worded, else required;
    anything else is implicit - unless its own words say required, which is what the
    necessity-wording check would hold an implicit one to."""
    if line.section == "qualification":
        return "preferred" if line.optional else "required"
    return "required" if REQUIRED_WORDS.search(line.text) else "implicit"


def triples(post, stem, head, seniority, domains, captured, reqs):
    """The posting graph's triples: the Posting, then each requirement.

    Args:
        post: the posting's iri.
        stem: its stem, which the requirements' ids carry.
        head: decisions.txt's header (company, title, url).
        seniority: the level, or empty.
        domains: the domains' iris.
        captured: the day the advert was saved, ISO.
        reqs: (slug, asked, need, concept iris, quote) per requirement.

    Returns:
        [Triple].
    """
    import pyoxigraph as ox

    from .. import ontology as O

    def j(name):
        return ox.NamedNode(O.J + name)

    s = ox.NamedNode(post)
    out = [ox.Triple(s, j("company"), ox.Literal(head["company"])),
           ox.Triple(s, j("title"), ox.Literal(head["title"])),
           ox.Triple(s, j("captured"), ox.Literal(captured, datatype=ox.NamedNode(O.XSD + "date"))),
           ox.Triple(s, j("advert"), ox.Literal(POSTING))]
    if head.get("url"):
        out.append(ox.Triple(s, j("url"), ox.Literal(head["url"])))
    if seniority:
        out.append(ox.Triple(s, j("seniority"), j(seniority)))
    out += [ox.Triple(s, j("domain"), ox.NamedNode(c)) for c in domains]
    for slug, asked, need, iris, quote in reqs:
        r = ox.NamedNode(f"{O.K}req_{stem}_{slug}")
        out += [ox.Triple(r, j("posting"), s), ox.Triple(r, j("asked"), ox.Literal(asked)),
                ox.Triple(r, j("necessity"), j(need)), ox.Triple(r, j("quote"), ox.Literal(quote))]
        out += [ox.Triple(r, j("concept"), ox.NamedNode(c)) for c in iris]
    return out
