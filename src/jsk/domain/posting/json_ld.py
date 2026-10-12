"""A saved page's schema.org JobPosting block, read as the advert instead of the page.

A careers site rendered by script puts its chrome in the page body - the nav, "Saved Jobs 0",
the related-jobs list, the footer - and `html_to_text` of the whole page made roughly a hundred
lines the analyst then had to drop by hand (the Wells Fargo page, 2026-10-06). The same page
carries the advertisement once, clean, in `<script type="application/ld+json">`, for search
engines. This module finds that block and returns its title, employer and description; the
page body stays the caller's fallback.

It is pure: the caller reads the file and passes the markup. It never raises on bad input -
a block that is not JSON, or not a JobPosting, or has an empty description, is "no block",
because a capture must not fail on a page that merely has an unreadable extra script. It
does not turn the description into text: `html_text.html_to_text` does, so the lines split
as the page's would.
"""
import json
import re

from .html_text import html_to_text

BLOCK = re.compile(r"<script\b[^>]*\btype\s*=\s*[\"']?application/ld\+json[\"']?[^>]*>(.*?)</script>",
                   re.I | re.S)


def _postings(node):
    """Every JobPosting dict in a decoded block: the block itself, a list's members, and an
    `@graph`'s members, however deep they nest."""
    if isinstance(node, list):
        for member in node:
            yield from _postings(member)
    elif isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            yield node
        yield from _postings(node.get("@graph"))


def _name(value):
    """A name from a string or a `{"name": ...}` object; "" otherwise."""
    if isinstance(value, dict):
        value = value.get("name")
    return value.strip() if isinstance(value, str) else ""


def _place(value):
    """The first `jobLocation` as `Locality, Region`, or the name it gives; "" if neither."""
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, dict):
        return ""
    address = value.get("address")
    if isinstance(address, dict):
        parts = [address.get("addressLocality"), address.get("addressRegion")]
        found = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
        if found:
            return ", ".join(found)
    return _name(value)


def job_posting(markup):
    """(title, facts line, description text) of the first JobPosting block whose description
    holds text, or None.

    The facts line is `Employer · Place` in the layout advert_header reads the company from;
    it is "" when the block gives fewer than two facts, since a lone employer would not parse
    back as one and the caller passes it instead.

    Args:
        markup: the page's HTML.
    """
    for raw in BLOCK.findall(markup or ""):
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        for node in _postings(data):
            description = node.get("description")
            text = html_to_text(description) if isinstance(description, str) else ""
            if not text:
                continue
            facts = [_name(node.get("hiringOrganization")), _place(node.get("jobLocation"))]
            facts = [f for f in facts if f]
            return (_name(node.get("title")), " · ".join(facts) if len(facts) > 1 else "",
                    text)
    return None


def page_advert(markup):
    """(title, text) of a saved page as an advert: the JobPosting block's, with its facts line
    above the description, or ("", the page body as text) when there is no usable block."""
    found = job_posting(markup)
    if found is None:
        return "", html_to_text(markup)
    title, facts, text = found
    return title, f"{facts}\n\n{text}" if facts else text
