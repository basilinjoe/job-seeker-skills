"""The terms gate's rules: which of the posting's own words the rendered page carries.

`jsk tailor match` matches by concept, which is right for judging evidence: "Kubernetes"
and "K8s" are one thing the person did or did not do. A recruiter's ATS search is not -
it matches the string typed, and recruiters type the posting's words. Nothing measured
whether those words reached the page, so a resume could carry the evidence for every
requirement under the career's own names and still be found by no search for them.

Every finding is a warning. A requirement missing from the page is often a gap the person
has, and the fix for a gap is never a word on the page; a reworded bullet goes through the
career and its confirmation like any other. So this says what a search would and would not
find, and the author decides.

  WARN  the posting's title is not on the page
  WARN  a required term is not on the page
  WARN  a term is not on the page, but another name of its concept is - the posting's
        string is the one to use where it is true
  WARN  the preferred terms not on the page, in one line
  WARN  a term on the page more than STUFFED times
"""
import re

from ..render.formatting import fold_ascii
from .report import Report

# Past this many uses a term reads as repetition to the person reading the page, and as
# stuffing to a screener that counts. Two pages of honest bullets name a core technology
# three or four times; six is past what the work itself says.
STUFFED = 5

# The necessities whose words a recruiter searches for. An implicit requirement is the
# analyst's reading between the lines; the advert never wrote it as a term.
SEARCHED = ("required", "preferred")


def occurrences(term, text):
    """How often `term` appears in `text` as a whole term, ignoring case.

    A plain substring would find "Go" in "Google" and "Java" in "JavaScript". The edges
    are tested as "not a letter or digit" rather than \\b, because a term can begin or end
    in punctuation - "C#", ".NET", "Node.js" - where \\b does not fall.
    """
    term = " ".join((fold_ascii(term) or "").split()).casefold()
    if not term:
        return 0
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return len(re.findall(pattern, text))


def page_text(text):
    """The page as the rules search it: folded to ASCII, whitespace collapsed, casefolded -
    a term wrapped across a line end still counts."""
    return " ".join((fold_ascii(text) or "").split()).casefold()


def judge(text, title, requirements):
    """Every terms-gate rule over one rendered page.

    Args:
        text: the page's text (the render's plain text, emitted from its plan).
        title: the posting's j:title.
        requirements: [(asked, necessity, other names)] - the term as the advert wrote it,
            required, preferred or implicit, and the labels of the concepts it resolves to.

    Returns:
        (counts, report): counts is {necessity: (on the page, asked)} for the searched
        necessities; the Report holds warnings only.
    """
    page = page_text(text)
    report = Report()
    if title and not occurrences(title, page):
        report.warn(f"the posting's title {title!r} is not on the page - a recruiter's search "
                    "by title will not find it; set `headline` in resume.json and confirm it "
                    "with the person (`jsk kb confirm --headline`)")
    counts = {n: [0, 0] for n in SEARCHED}
    missing_preferred = []
    seen = set()
    for asked, necessity, others in requirements:
        if necessity not in SEARCHED or asked.casefold() in seen:
            continue
        seen.add(asked.casefold())
        counts[necessity][1] += 1
        found = occurrences(asked, page)
        if found:
            counts[necessity][0] += 1
            if found > STUFFED:
                report.warn(f"{asked!r} is on the page {found} times - past {STUFFED} it reads "
                            "as keyword stuffing; cut the repeats that add nothing")
            continue
        said = [o for o in others if o.casefold() != asked.casefold() and occurrences(o, page)]
        if said:
            report.warn(f"{necessity} {asked!r} is not on the page, but {said[0]!r} is - a "
                        "parser matches the string, so use the posting's word where it is "
                        "true: a skill's alias in `names`, or a bullet reworded in the career")
        elif necessity == "required":
            report.warn(f"required {asked!r} is not on the page - a search for it will not "
                        "find this resume; if the person has it, the evidence belongs in a "
                        "bullet, and if not, it is a gap - a short: line in gaps.txt")
        else:
            missing_preferred.append(asked)
    if missing_preferred:
        report.warn(f"{len(missing_preferred)} preferred term(s) not on the page: "
                    + ", ".join(repr(t) for t in missing_preferred))
    return {n: tuple(c) for n, c in counts.items()}, report
