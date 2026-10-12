"""The job boards jsk reads: which board a URL is on, and a board's answer as a posting."""
import datetime
import html
import re
import urllib.parse

from .errors import NotOnBoard
from .html_text import html_to_text, spaced

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
        if not (at and found):
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
