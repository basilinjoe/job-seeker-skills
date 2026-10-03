"""The short resume.json's dict as data: its shape, its ids against the career, its summary
and headline.

Pure: the dict arrives as a selection graph gives it (domain/resume/selection.py) and the
career as a loaded store; reading them is application/render/load_resume.py's. The shape
is resume.json's, kept as the interchange shape when 6.0 stopped reading the file (Ruling 3
of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md); its parser went with the
file.
"""
import difflib
import hashlib
import re

VERSION = 2
FORMATS = ("presentation", "ats-maximal")
STATUSES = ("confirmed", "inferred")
FLOORS = ("confirmed", "inferred", "needs-verification", "disputed")
LISTS = {"bullets": "ach_", "roles": "pos_", "skills": "skill_"}
KEYS = {"resume": int, "bullets": list, "roles": list, "skills": list, "format": str,
        "region": str, "pages": int, "ats_pages": int, "floor": str, "summary": dict,
        "headline": dict, "names": dict}
SUMMARY_KEYS = ("text", "status", "answer", "text_sha256")
# The two pieces of prose the file holds itself, each confirmed the same way. The headline
# is the posting's title when the person stands behind it: the line a recruiter's title
# search matches, which the career's one j:headline cannot be for every posting.
PROSE = ("summary", "headline")


def confirm_hint(key, target=None):
    """How a `key` block ("summary" or "headline") is confirmed, as the findings say it.

    Args:
        key: the block.
        target: the selection's name (`<stem>` or `resumes/<name>`), whose block is
            confirmed through the `career_confirm` tool; None when the caller has none to
            name, and the hint names the target form.
    """
    if target is not None:
        return (f'confirm it with `career_confirm` (target "{target}", block "{key}") and '
                "the person's own answer")
    return (f'confirm it with `jsk kb confirm --{key} <stem> --answer "their words"`, or '
            "`career_confirm` with the target and the block")


CONFIRM = confirm_hint("summary")


def digest(text):
    """The summary text's hash as confirm records it: the first 12 hex digits of sha256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def confirmed(summary, answer):
    """The summary confirmed with `answer`, its keys in the order they already had."""
    out = dict(summary)
    out.update(status="confirmed", answer=answer, text_sha256=digest(summary["text"]))
    return out


def unearned(summary, key="summary", target=None):
    """Why a `"status": "confirmed"` summary (or headline) has not earned it - [] when it has.

    Flipping the status by hand confirmed a summary with no answer and no audit, and a
    later edit to the text kept it confirmed: the answer and the text's hash are what
    only `jsk kb confirm --summary` (or `--headline`) writes, and a changed text drops out
    of confirmed as a changed claim does in the career."""
    from ..record.rules import DENIAL, PLACEHOLDER

    if summary.get("status") != "confirmed" or not isinstance(summary.get("text"), str):
        return []
    hint = confirm_hint(key, target)
    answer = summary.get("answer")
    if not isinstance(answer, str) or PLACEHOLDER.fullmatch(answer) or DENIAL.fullmatch(answer):
        return [f"{key} is confirmed but records no answer from the person - {hint}"]
    if summary.get("text_sha256") != digest(summary["text"]):
        if "text_sha256" not in summary:
            return [f"{key} is confirmed but holds no text_sha256 - {hint}"]
        return [f"the {key} changed since it was confirmed - read it to the person and "
                f"{hint}"]
    return []


def summary_status(summary, key="summary"):
    """The status a summary (or headline) renders at: inferred when its confirmation does
    not hold."""
    return "inferred" if unearned(summary, key) else summary.get("status")


class ShortError(Exception):
    """A selection that cannot be used: the message says why, `.fix` what to do."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


def shape(doc, target=None):
    """FAIL lines for the file's own shape. Empty is clean. `target` names a graph-native
    selection, so a confirmation's hint names the tool (confirm_hint)."""
    out = []
    for key in sorted(k for k in doc if k not in KEYS):
        out.append(f"unknown key {key!r} - a resume.json holds only "
                   f"{', '.join(KEYS)}")
    for key, kind in KEYS.items():
        if key in doc and (not isinstance(doc[key], kind) or isinstance(doc[key], bool)):
            out.append(f"{key!r} must be {'a number' if kind is int else 'a ' + kind.__name__}")
    if not isinstance(doc.get("bullets"), list) or not doc.get("bullets"):
        out.append("'bullets' must name at least one ach_ id - they are the resume")
    for key, prefix in LISTS.items():
        items = doc.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, str) or not item.startswith(prefix):
                out.append(f"{key}: {item!r} is not an {prefix} id")
        dupes = sorted({i for i in items if isinstance(i, str) and items.count(i) > 1})
        for item in dupes:
            out.append(f"{key}: {item} is listed twice")
    for key in ("pages", "ats_pages"):
        if isinstance(doc.get(key), int) and doc[key] < 1:
            out.append(f"{key!r} must be at least 1")
    # A two-letter code, or xx for the default profile. "aus" validated and rendered the
    # default profile - two pages, no work-rights line - over the person's AU country
    # that would have been right (final review); a code with no profile of its own still
    # means the default one, and sets the paper.
    if isinstance(doc.get("region"), str) and not re.fullmatch(r"[A-Za-z]{2}", doc["region"]):
        out.append(f"region {doc['region']!r} is not a two-letter country code - au, in, "
                   "us, ... or xx for the default profile")
    if isinstance(doc.get("format"), str) and doc["format"] not in FORMATS:
        out.append(f"format {doc['format']!r} is not one of {', '.join(FORMATS)}")
    if isinstance(doc.get("floor"), str) and doc["floor"] not in FLOORS:
        out.append(f"floor {doc['floor']!r} is not one of {', '.join(FLOORS)}")
    for block in PROSE:
        summary = doc.get(block)
        if not isinstance(summary, dict):
            continue
        if not isinstance(summary.get("text"), str) or not summary["text"].strip():
            out.append(f"{block} needs its text")
        elif block == "headline" and "\n" in summary["text"]:
            out.append("headline is one line - it renders under the name")
        if summary.get("status") not in STATUSES:
            out.append(f"{block} status must be one of {', '.join(STATUSES)}")
        for key in sorted(set(summary) - set(SUMMARY_KEYS)):
            out.append(f"{block}: unknown key {key!r}")
        out += unearned(summary, block, target)
    names = doc.get("names")
    if isinstance(names, dict):
        for ident, name in names.items():
            if not ident.startswith("skill_"):
                out.append(f"names: {ident!r} is not a skill_ id")
            if not isinstance(name, str) or not name.strip():
                out.append(f"names: {ident} needs the name it renders under")
    return out


def ids(doc, store):
    """FAIL lines for ids the career does not hold as the file uses them: unknown (with
    the near one), retired (with its reason), of another kind, or a bullet whose project
    names no role - it would render under no employer - and a `names` entry the skill does
    not answer to (renamed)."""
    from .. import ontology as O
    from ..record.career import Career
    from ..record.state import KB

    career = Career(store.graph(KB))
    known = {iri: c.name for iri, c in career.sub.cls.items()}
    want = {"bullets": "Achievement", "roles": "Position", "skills": "Skill"}
    out = []
    for key, cls in want.items():
        for ident in doc.get(key) or []:
            if not isinstance(ident, str):
                continue
            iri = O.K + ident
            if iri not in known:
                near = difflib.get_close_matches(
                    iri, sorted(i for i, c in known.items() if c == cls), n=1)
                hint = f" - did you mean {near[0][len(O.K):]}?" if near else ""
                out.append(f"{key}: {ident} is not in the career{hint}")
                continue
            if known[iri] != cls:
                out.append(f"{key}: {ident} is a {known[iri]}, not a {cls}")
                continue
            if career.get(iri, "retired"):
                out.append(f"{key}: {ident} was retired on {career.get(iri, 'retired')} "
                           f"({career.get(iri, 'reason', 'no reason given')}) - drop it, "
                           "or name what replaced it")
                continue
            if key == "bullets":
                project = career.get(iri, "project")
                role = career.get(project, "position")
                if not role:
                    out.append(f"bullets: {ident}'s project {project[len(O.K):]} names no "  # pyright: ignore[reportOptionalSubscript]
                               "role (j:position), so it would render under no employer")
                # A retired project or role takes its live bullet off the page with it:
                # the final review retired a role, and the bullet under it vanished from
                # the render without a warning, and from what freeze carried.
                for held, what in ((project, "project"), (role, "role")):
                    if held and career.get(held, "retired"):
                        out.append(f"bullets: {ident}'s {what} {held[len(O.K):]} was retired "
                                   f"on {career.get(held, 'retired')} "
                                   f"({career.get(held, 'reason', 'no reason given')}) - drop "
                                   "the bullet, or move it to a live one in the career")
    out += renamed(doc, career, known)
    return out


def renamed(doc, career, known):
    """FAIL lines for `names`: each must be a skill the career holds, under its own name or
    one of its j:alias - the posting's spelling of it, never a word the career lacks.

    "Adobe Creative Cloud" and "Adobe Creative Suite" are two strings to a parser; the
    alias says the person answers to both, and `names` picks which one this resume shows.
    """
    from .. import ontology as O

    out = []
    names = doc.get("names")
    if not isinstance(names, dict):
        return out
    for ident, name in names.items():
        iri = O.K + ident
        if not isinstance(name, str) or not ident.startswith("skill_"):
            continue
        if known.get(iri) != "Skill":
            out.append(f"names: {ident} is not a skill in the career")
            continue
        allowed = [career.get(iri, "name") or ""] + [t.value for t in career.all(iri, "alias")]
        if name not in allowed:
            out.append(f"names: {ident} renders as {name!r}, which is neither its name nor an "
                       f"alias ({', '.join(repr(a) for a in allowed if a)}) - add the alias "
                       "to the skill with `jsk kb apply` first")
    return out
