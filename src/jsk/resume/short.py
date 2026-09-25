"""The short resume.json: one application's choices, and nothing the career holds.

It replaced a 30-47KB URS record copied out of career/kb.ttl, of which the parts anyone
authored - the view and the summary - were 3KB (ElevenLabs, 2026-09-25). The copy is
what needed a spec, a refresh command and a gate for drift; a file that holds only ids
and settings can go stale in one way only, an id the career no longer holds, and that
is what `ids` checks.
"""
import difflib
import json
import os

VERSION = 2
FORMATS = ("presentation", "ats-maximal")
STATUSES = ("confirmed", "inferred")
FLOORS = ("confirmed", "inferred", "needs-verification", "disputed")
LISTS = {"bullets": "ach_", "roles": "pos_", "skills": "skill_"}
KEYS = {"resume": int, "bullets": list, "roles": list, "skills": list, "format": str,
        "region": str, "pages": int, "ats_pages": int, "floor": str, "summary": dict}


class ShortError(Exception):
    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


def read(path):
    """The file as a dict, or ShortError naming what to do."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise ShortError(f"{path}: no such file", "pass the application's resume.json") from None
    except (OSError, ValueError) as err:
        raise ShortError(f"{path}: not readable JSON ({err})",
                         "fix the file, or write it again with `jsk kb export`") from None
    if not isinstance(doc, dict):
        raise ShortError(f"{path}: not a resume.json", "write one with `jsk kb export`")
    if "urs" in doc:
        # A full record from before the career built the resume: the choices in it are
        # still good, and migrate carries them over.
        raise ShortError(f"{path} is a full URS record, which jsk no longer reads",
                         "convert it with `jsk migrate` - it keeps the view's choices")
    if doc.get("resume") != VERSION:
        raise ShortError(f"{path}: \"resume\" is {doc.get('resume')!r}, not {VERSION}",
                         "write it again with `jsk kb export`")
    return doc


def workspace(path):
    """The workspace root above the file. Walked up, never worked out: the real one is
    a folder named `career` holding career/kb.ttl."""
    from ..graph.kbcli import find_root

    root = find_root(os.path.dirname(os.path.abspath(path)))
    if root is None:
        raise ShortError(f"{path} is not inside a workspace",
                         "keep resume.json under the folder holding career/kb.ttl - "
                         "the resume is built from it")
    return root


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
        for key in sorted(set(summary) - {"text", "status"}):
            out.append(f"summary: unknown key {key!r}")
    return out


def ids(doc, store):
    """FAIL lines for ids the career does not hold as the file uses them: unknown (with
    the near one), retired (with its reason), of another kind, or a bullet whose project
    names no role - it would render under no employer."""
    from ..graph import ontology as O
    from ..graph import record as R
    from .career import Career

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
                out.append(f"{key}: {ident} is not in career/kb.ttl{hint}")
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
                if not career.get(project, "position"):
                    out.append(f"bullets: {ident}'s project {project[len(O.K):]} names no "
                               "role (j:position), so it would render under no employer")
    return out


def main(argv):
    """`python -m jsk.resume.short <resume.json>`: shape and ids, PASS or FAIL.

    doctor spawns it over the example workspace: the record gate (jsk.gates.record)
    replaces it there once it lands, and this stays the check with no gate behind it."""
    import sys

    args = argv[1:]
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: python -m jsk.resume.short <resume.json>")
        return 2
    path = args[0]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    print(f"checking: {path}")
    try:
        doc = read(path)
        root = workspace(path)
    except ShortError as e:
        print(f"FAIL  {e}\n      fix: {e.fix}")
        return 1
    from ..graph import store as S

    fails = shape(doc) or ids(doc, S.load(root))
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
