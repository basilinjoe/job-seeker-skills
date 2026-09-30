"""The short resume.json: one application's choices, and nothing the career holds.

It replaced a 30-47KB URS record copied out of career/kb.ttl, of which the parts anyone
authored - the view and the summary - were 3KB (ElevenLabs, 2026-09-25). The copy is
what needed a spec, a refresh command and a gate for drift; a file that holds only ids
and settings can go stale in one way only, an id the career no longer holds, and that
is what `ids` checks.
"""
import difflib
import hashlib
import json
import os
import re

from ..cliutil import utf8_stdout

VERSION = 2
FORMATS = ("presentation", "ats-maximal")
STATUSES = ("confirmed", "inferred")
FLOORS = ("confirmed", "inferred", "needs-verification", "disputed")
LISTS = {"bullets": "ach_", "roles": "pos_", "skills": "skill_"}
KEYS = {"resume": int, "bullets": list, "roles": list, "skills": list, "format": str,
        "region": str, "pages": int, "ats_pages": int, "floor": str, "summary": dict}
SUMMARY_KEYS = ("text", "status", "answer", "text_sha256")
CONFIRM = 'confirm it with `jsk kb confirm --summary <resume.json> --answer "their words"`'


def digest(text):
    """The summary text's hash as confirm records it: the first 12 hex digits of sha256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def confirmed(summary, answer):
    """The summary confirmed with `answer`, its keys in the order they already had."""
    out = dict(summary)
    out.update(status="confirmed", answer=answer, text_sha256=digest(summary["text"]))
    return out


def unearned(summary):
    """Why a `"status": "confirmed"` summary has not earned it - [] when it has.

    Flipping the status by hand confirmed a summary with no answer and no audit, and a
    later edit to the text kept it confirmed: the answer and the text's hash are what
    only `jsk kb confirm --summary` writes, and a changed text drops out of confirmed
    as a changed claim does in the career."""
    from ..graph.rules import DENIAL, PLACEHOLDER

    if summary.get("status") != "confirmed" or not isinstance(summary.get("text"), str):
        return []
    answer = summary.get("answer")
    if not isinstance(answer, str) or PLACEHOLDER.fullmatch(answer) or DENIAL.fullmatch(answer):
        return [f"summary is confirmed but records no answer from the person - {CONFIRM}"]
    if summary.get("text_sha256") != digest(summary["text"]):
        if "text_sha256" not in summary:
            return [f"summary is confirmed but holds no text_sha256 - {CONFIRM}"]
        return [f"the summary changed since it was confirmed - read it to the person and "
                f"{CONFIRM}"]
    return []


def summary_status(summary):
    """The status a summary renders at: inferred when its confirmation does not hold."""
    return "inferred" if unearned(summary) else summary.get("status")


class ShortError(Exception):
    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


def read(path):
    """The file as a dict, or ShortError naming what to do."""
    from ..infra.files import Missing, Unreadable, read_text

    try:
        doc = json.loads(read_text(path))
    except Missing:
        raise ShortError(f"{path}: no such file", "pass the application's resume.json") from None
    except Unreadable as err:
        # An editor's cp1252 save: the bytes are the fault, not the JSON.
        raise ShortError(str(err), err.fix) from None
    except ValueError as err:
        raise ShortError(f"{path}: not readable JSON ({err})",
                         "fix the file, or write it again with `jsk kb export`") from None
    if not isinstance(doc, dict):
        raise ShortError(f"{path}: not a resume.json", "write one with `jsk kb export`")
    if "urs" in doc:
        # A full record from before the career built the resume. A sent one stays as the
        # archive of what was sent; an unsent one is written again from the career.
        raise ShortError(f"{path} is a full URS record, which jsk no longer reads",
                         "write a short one with `jsk kb export --select <id>... --out "
                         f"{path}`")
    if doc.get("resume") != VERSION:
        raise ShortError(f"{path}: \"resume\" is {doc.get('resume')!r}, not {VERSION}",
                         "write it again with `jsk kb export`")
    return doc


def workspace(path):
    """The workspace root above the file. Walked up, never worked out: the real one is
    the folder holding career/store/."""
    from ..infra.files import find_root

    root = find_root(os.path.dirname(os.path.abspath(path)))
    if root is None:
        raise ShortError(f"{path} is not inside a workspace",
                         "keep resume.json under the folder holding career/store/ - "
                         "the resume is built from the career in it")
    return root


def career(root):
    """The workspace at `root`, loaded. A store that will not open is a ShortError with
    its fix, as a file that cannot be read is - never a traceback."""
    from ..graph import store as S
    from ..domain.record.parsed import GraphError

    try:
        return S.load(root)
    except GraphError as e:
        raise ShortError(str(e), e.fix) from None


def shape(doc):
    """FAIL lines for the file's own shape. Empty is clean."""
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
    summary = doc.get("summary")
    if isinstance(summary, dict):
        if not isinstance(summary.get("text"), str) or not summary["text"].strip():
            out.append("summary needs its text")
        if summary.get("status") not in STATUSES:
            out.append(f"summary status must be one of {', '.join(STATUSES)}")
        for key in sorted(set(summary) - set(SUMMARY_KEYS)):
            out.append(f"summary: unknown key {key!r}")
        out += unearned(summary)
    return out


def ids(doc, store):
    """FAIL lines for ids the career does not hold as the file uses them: unknown (with
    the near one), retired (with its reason), of another kind, or a bullet whose project
    names no role - it would render under no employer."""
    from ..domain import ontology as O
    from ..infra.oxigraph import record as R
    from ..domain.record.career import Career

    career = Career(store.graph(R.KB))
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
                    out.append(f"bullets: {ident}'s project {project[len(O.K):]} names no "
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
    return out


def main(argv):
    """`python -m jsk.resume.short <resume.json>`: shape and ids, PASS or FAIL.

    doctor spawns it over the example workspace: the record gate (jsk.gates.record)
    replaces it there once it lands, and this stays the check with no gate behind it."""
    args = argv[1:]
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: python -m jsk.resume.short <resume.json>")
        return 2
    path = args[0]
    utf8_stdout()
    print(f"checking: {path}")
    try:
        doc = read(path)
        root = workspace(path)
        fails = shape(doc) or ids(doc, career(root))
    except ShortError as e:
        print(f"FAIL  {e}\n      fix: {e.fix}")
        return 1
    for line in fails:
        print(f"FAIL  {line}")
    if fails:
        print(f"FAIL {len(fails)}")
        return 1
    print("PASS - safe to render")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv))
