#!/usr/bin/env python3
"""Validate a URS document against references/urs-spec.md.

Usage: jsk validate <resume.json> [--strict] [--max-findings N]
       python -m jsk.gates.validate_urs <resume.json> [--strict] [--max-findings N]
       --strict            treat warnings as failures
       --max-findings N    print at most N failures and N warnings (default 25;
                           0 prints every one)

Exit 0 = valid. Exit 1 = do not render this. Exit 2 = usage error.

Standard library only. **This record is edited by hand** - `jsk kb export --urs` drafts
it from career/kb.ttl, ids and metrics as held, and the skill then retunes the summary,
the view and the bullets for one posting - so this gate is the only thing between a slip
in that editing and a resume somebody sends. `check_shape` is the rule the editing
needs: a key nobody recognises is a field that renders as nothing, and reads on the page
as an omission. The claims gate (claims.py) is the other half, joining what the record
says with what the career holds.

The rules that matter are still the ones no schema can express:

  * a numeral in a bullet that appears in no metric - the check that stops a
    rewritten bullet from quietly inflating a number
  * content text inside a view - a view selects, it never writes

Both are structural guarantees rather than style preferences, which is why they
fail the document rather than warning about it.
"""
import json
import os
import re
import sys

from ..cliutil import docstring_usage, wants_help
from ..paths import SCHEMA_DIR

# This gate is what jsk-verifier runs and reports back verbatim, so its output lands
# in an agent's context on every check. Nothing is hidden by the cap: the header keeps
# printing the true totals and the last line says how many were not listed.
MAX_FINDINGS = 25

# Flags that consume the token after them, so a value can never be read as the path.
VALUE_FLAGS = {"--max-findings"}

ID_PREFIX = {
    "organizations": "org", "engagements": "eng", "education": "edu",
    "credentials": "cred", "projects": "prj", "skills": "skill",
    "narratives": "nar", "referees": "ref", "views": "view",
}

# Every key a URS 1.x document may carry at the top level, and the two it must.
#
# This is the check that replaced the old conservation check, and it is checking the
# same thing from the only side this gate reads. Conservation compared the record
# against the source it was built from: a section present there and absent from the
# record meant it had been dropped. This gate reads the record alone, so the question
# becomes the one a hand-edited document can actually be asked - is every key here
# one the renderer knows?
#
# It has to be a failure rather than a warning. `resolve.py` reads the keys it knows
# and ignores the rest, so `experience:` written where `engagements:` belongs renders
# a resume with no jobs on it, silently, and the mistake is invisible in the PDF
# precisely because the section is simply not there. An unrecognised key is the one
# defect in this file that looks like nothing at all.
TOP_LEVEL_KEYS = {
    "urs", "meta", "person", "work_authorization", "languages", "organizations",
    "engagements", "education", "credentials", "skills", "projects", "narratives",
    "referees", "availability", "compensation", "identity_documents", "views",
}

REQUIRED_TOP_LEVEL = ("urs", "person")

# Keys whose value must be a list if it is present at all. A dict where a list belongs
# is the other half of the same slip, and it fails the same way: `resolve.py` iterates
# it, gets its keys back as strings, and renders nothing anybody wrote.
LIST_KEYS = ("work_authorization", "languages", "organizations", "engagements",
             "education", "credentials", "skills", "projects", "narratives",
             "referees", "views")

# Keys whose value must be an object if it is present at all.
DICT_KEYS = ("meta", "person", "availability", "compensation")


def check_shape(doc, rep):
    """Top-level keys the renderer knows, and the two the document cannot omit.

    Returns whether the document can be walked at all. Every later check reads each
    list key as a list of objects and each dict key as an object, so a string where
    either belongs would crash them - and a gate that raises is a gate that did not
    answer.
    """
    walkable = True
    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            rep.fail(f"top-level {key!r} is missing - a URS document cannot omit it")
    for key in sorted(k for k in doc if k not in TOP_LEVEL_KEYS):
        near = [k for k in sorted(TOP_LEVEL_KEYS) if k.startswith(key[:4].lower())]
        rep.fail(f"unknown top-level key {key!r} - nothing reads it, so everything "
                 f"under it renders as nothing"
                 + (f" (did you mean {near[0]!r}?)" if near else ""))
    for key in LIST_KEYS:
        if key not in doc or doc[key] is None:
            continue
        if not isinstance(doc[key], list):
            rep.fail(f"{key!r} must be a list, got "
                     f"{type(doc[key]).__name__} - the renderer iterates it")
            walkable = False
            continue
        for i, item in enumerate(doc[key]):
            if not isinstance(item, dict):
                rep.fail(f"'{key}[{i}]' must be an object, got {type(item).__name__}")
                walkable = False
    for key in DICT_KEYS:
        if doc.get(key) is not None and not isinstance(doc[key], dict):
            rep.fail(f"{key!r} must be an object, got {type(doc[key]).__name__}")
            walkable = False
    return walkable


# The strength at or above which a project with no evidence fails rather than warns.
# Keyed to strength because that is the person's own assertion that a project is worth
# putting on a resume - which makes the floor self-scaling, and non-retroactive without
# needing a revision gate: a record of low-strength stubs warns, a record claiming
# strong work with nothing behind it fails.
COVERAGE_FAIL_STRENGTH = 4

VIEW_KEYS = {
    "id", "label", "format_profile", "region_profile", "locale", "target",
    "narrative", "sections", "include", "skills", "redact",
    "provenance_floor", "budget", "x",
}

SCALE = {"k": 1e3, "m": 1e6, "bn": 1e9, "b": 1e9}


NUMBER = re.compile(r"(?<![A-Za-z0-9.])(\d[\d,]*(?:\.\d+)?)\s*(bn|[kmb%])?(?![A-Za-z0-9])")
ACRONYM = re.compile(r"([A-Z]{2,})\s*$")


def numerals(text):
    """Standalone quantities in prose, with their multiplier suffix if any.

    Three classes of number are designators rather than claims, and counting
    them would make this check useless through noise:

      * glued to letters - p95, S3, H100, IPv6
      * a four-digit year
      * preceded by an all-caps acronym - ISO 27001, SOC 2, IEC 62304, RFC 7231

    The acronym rule costs a real detection: 'reduced MTTR 40' is skipped. That
    trade is deliberate, because this check *fails* a document. A missed number
    is a gap in coverage; a false accusation makes the gate something people
    learn to route around. A percentage keeps its suffix and is always counted,
    which is how most such claims are actually written.
    """
    found = []
    for m in NUMBER.finditer(text):
        raw, suffix = m.group(1), (m.group(2) or "").lower()
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix in ("", "%") and 1900 <= value <= 2100 and value == int(value) and "." not in raw:
            continue                      # a year, not a claim
        if suffix != "%" and ACRONYM.search(text[:m.start()]):
            continue                      # a standard's number, not a quantity
        found.append((value, suffix, m.group(0).strip()))
    return found


def metric_values(metrics):
    out = set()
    for m in metrics or []:
        for key in ("quantity", "baseline"):
            q = m.get(key) or {}
            if isinstance(q.get("value"), (int, float)):
                out.add(float(q["value"]))
        # A metric whose `value` is a string carries the number as the person wrote it -
        # "5 min to under 1 s", "2,000+", "-30%" - because that is how a person records
        # a number they verified. Every numeral in it counts as recorded, which is what
        # the check is asking: does this number appear in something someone wrote down.
        if isinstance(m.get("value"), str):
            out.update(value for value, _suffix, _shown in numerals(m["value"]))
    return out


def covered(value, suffix, pool):
    candidates = {value}
    if suffix in SCALE:
        candidates.add(value * SCALE[suffix])
    for c in candidates:
        for p in pool:
            if abs(p - c) < 1e-9 or (c and abs(p - c) / max(abs(c), 1e-9) < 0.005):
                return True
            if p and abs(p * 60 - c) < 1e-9:          # minutes stated as seconds
                return True
            if c and abs(c * 60 - p) < 1e-9:
                return True
    return False


class Report:
    def __init__(self):
        self.fails = []
        self.warns = []

    def fail(self, msg):
        self.fails.append(msg)

    def warn(self, msg):
        self.warns.append(msg)


def walk_achievements(doc):
    for e in doc.get("engagements") or []:
        for a in e.get("achievements") or []:
            yield a, f"engagement {e.get('id')}"
    for p in doc.get("projects") or []:
        for a in p.get("achievements") or []:
            yield a, f"project {p.get('id')}"


def check_ids(doc, rep):
    seen = {}
    for key, prefix in ID_PREFIX.items():
        for item in doc.get(key) or []:
            if not isinstance(item, dict):
                continue
            ident = item.get("id")
            if not ident:
                rep.fail(f"{key}: an entry has no id")
                continue
            if ident in seen:
                rep.fail(f"duplicate id {ident!r} in {key} and {seen[ident]}")
            seen[ident] = key
            if not ident.startswith(prefix + "_"):
                rep.warn(f"id {ident!r} in {key} does not use the {prefix}_ prefix")
    for a, where in walk_achievements(doc):
        ident = a.get("id")
        if not ident:
            rep.fail(f"achievement without an id in {where}")
        elif ident in seen:
            rep.fail(f"duplicate id {ident!r} - achievement in {where} and {seen[ident]}")
        else:
            seen[ident] = where
    for e in doc.get("engagements") or []:
        for p in e.get("positions") or []:
            if p.get("id") and p["id"] in seen:
                rep.fail(f"duplicate id {p['id']!r} in positions and {seen[p['id']]}")
            elif p.get("id"):
                seen[p["id"]] = "positions"
    return seen


def check_periods(doc, rep):
    def one(period, where):
        if not period:
            return
        state = period.get("state")
        if state is None:
            rep.fail(f"{where}: period has no state - ongoing and unknown must be distinguishable")
            return
        if state == "ended" and not period.get("end"):
            rep.fail(f"{where}: state 'ended' requires an end date")
        if state == "ongoing" and period.get("end"):
            rep.fail(f"{where}: state 'ongoing' must not carry an end date")
        start, end = period.get("start") or {}, period.get("end") or {}
        if start.get("value") and end.get("value") and end["value"] < start["value"]:
            rep.fail(f"{where}: period ends before it starts")

    for key in ("engagements", "education", "projects"):
        for item in doc.get(key) or []:
            one(item.get("period"), f"{key} {item.get('id')}")
            for p in item.get("positions") or []:
                one(p.get("period"), f"position {p.get('id')}")


def check_references(doc, ids, rep):
    def ref(target, where):
        if target and target not in ids:
            rep.fail(f"{where}: reference to unknown id {target!r}")

    for e in doc.get("engagements") or []:
        ref(e.get("organization"), f"engagement {e.get('id')}")
        ref((e.get("employment") or {}).get("via"), f"engagement {e.get('id')} employment.via")
        for pid in e.get("projects") or []:
            ref(pid, f"engagement {e.get('id')} projects")
    for s in doc.get("skills") or []:
        for ev in s.get("evidence") or []:
            ref(ev, f"skill {s.get('id')} evidence")
    for a, where in walk_achievements(doc):
        for sid in a.get("skills") or []:
            ref(sid, f"achievement {a.get('id')} in {where}")
    for v in doc.get("views") or []:
        ref(v.get("narrative"), f"view {v.get('id')} narrative")
        for sid in v.get("skills") or []:
            ref(sid, f"view {v.get('id')} skills")
        for inc in v.get("include") or []:
            ref(inc.get("ref"), f"view {v.get('id')} include")
            for aid in inc.get("achievements") or []:
                ref(aid, f"view {v.get('id')} include.achievements")


def check_views(doc, rep):
    """A view selects. It MUST NOT contain content text."""
    for v in doc.get("views") or []:
        extra = set(v) - VIEW_KEYS
        for key in sorted(extra):
            value = v[key]
            if isinstance(value, str) and len(value) > 40:
                rep.fail(
                    f"view {v.get('id')}: unknown field {key!r} holds free text - "
                    "a view references content, it never contains it")
            else:
                # With no schema behind this, an unknown key is caught only here.
                # 'startDate' for 'start' is the failure it exists for: a typo that
                # loses a date with nobody noticing. Extensions go under 'x'.
                rep.fail(f"view {v.get('id')}: unknown field {key!r} - "
                         "extensions belong under x")
        if not v.get("format_profile"):
            rep.fail(f"view {v.get('id')}: no format_profile")
        region = v.get("region_profile")
        if region:
            token = region.split(":")[-1].split("/")[0].lower()
            # The same aliases profiles.load() honours, and only those. Calling
            # profiles.load() here instead would pass every token, because it falls
            # back to default.json for anything it cannot find - so a typo
            # would validate and then render under rules nobody chose.
            if token in ("xx", "", "none"):
                token = "default"
            if not os.path.exists(os.path.join(SCHEMA_DIR, "profiles", f"{token}.json")):
                rep.fail(f"view {v.get('id')}: no profile file for {region!r}")


def check_metrics(doc, rep):
    for a, where in walk_achievements(doc):
        text = a.get("text") or ""
        found = numerals(text)
        pool = metric_values(a.get("metrics"))
        scope = a.get("scope") or {}
        for key in ("team_size", "reports", "users_affected"):
            if isinstance(scope.get(key), (int, float)):
                pool.add(float(scope[key]))
        budget = (scope.get("budget") or {}).get("value")
        if isinstance(budget, (int, float)):
            pool.add(float(budget))
        if not found:
            continue
        # An achievement carrying no metrics at all used to warn here and skip the
        # check. That inverted the threat: a bullet whose number disagrees with its
        # own metric failed, while a bullet that invented a number and attached
        # nothing passed and rendered. The second is what tailoring produces - prose
        # written fresh against a posting - so it is the case worth failing.
        #
        # Dropping the branch also lets `scope` back the number. A bullet saying
        # "led a team of 12" against scope.team_size 12 was warned about rather than
        # checked, because it carried no `metrics` list.
        missing = not a.get("metrics")
        for value, suffix, shown in found:
            if covered(value, suffix, pool):
                continue
            rep.fail(f"achievement {a.get('id')} in {where}: {shown!r} appears in the text "
                     "but in no metric - the number cannot be verified" +
                     (" (this achievement carries no metrics at all: record the number "
                      "as a metric in career/kb.ttl with `jsk kb apply`, then cite it in "
                      "the bullet's `metrics` - `jsk kb export --urs` writes them as held)"
                      if missing else ""))


def check_provenance(doc, rep):
    for a, where in walk_achievements(doc):
        if not (a.get("provenance") or {}).get("status"):
            rep.fail(f"achievement {a.get('id')} in {where}: no provenance status")
    for n in doc.get("narratives") or []:
        if not (n.get("provenance") or {}).get("status"):
            rep.fail(f"narrative {n.get('id')}: no provenance status")


def check_placeholders(doc, rep):
    """A bracket inside a *string value* is a leftover placeholder.

    Checked per string rather than over the serialised document, because JSON
    array syntax is made of the same brackets and matching that reports every
    list in the file as a defect.
    """
    def walk(node, path):
        if isinstance(node, str):
            if re.search(r"\[[^\[\]]{0,60}\]|\[", node):
                rep.fail(f"bracketed placeholder at {path}: {node[:60]!r}")
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for n, v in enumerate(node):
                walk(v, f"{path}[{n}]")

    walk(doc, "")


def check_renderable(doc, rep):
    """A record with nothing to render, said out loud rather than passed.

    Every other check here iterates a record key and verifies the shape of what it
    finds. None of them can fail on an empty list, because an empty list satisfies
    every statement you can make about its elements - which is how `views: []` passed
    the record gate for months while `provenance_floor` never ran on anything at all.

    The old conservation check caught that by comparing the record against its source.
    Reading the record alone, the weaker statement is still worth failing on: a record with
    no views renders no document, and a record with no engagements and no projects
    renders a page with a name at the top of it.
    """
    if not (doc.get("views") or []):
        rep.fail("views[] is empty - a view is what selects the evidence, so there is "
                 "nothing here to render and every provenance rule has nothing to run on")
    if not (doc.get("engagements") or []) and not (doc.get("projects") or []):
        rep.fail("engagements[] and projects[] are both empty - this record would "
                 "render a header and no experience")


def check_backrefs(doc, rep):
    """Every project that names an engagement appears in that engagement's projects[].

    resolve.py walks `engagement["projects"]` and nothing else to reach a project's
    bullets, so a project missing from that list is silently absent from every
    rendered document while the record stays perfectly valid - a missing
    back-reference is not an invalid reference, which is why nothing caught it when
    the record never populated the list at all.
    """
    listed = {pid for e in doc.get("engagements") or [] for pid in (e.get("projects") or [])}
    for p in doc.get("projects") or []:
        eng = p.get("engagement")
        if eng and p.get("id") not in listed:
            rep.fail(f"project {p.get('id')}: names engagement {eng!r} and appears in no "
                     f"engagement's projects[] - its bullets reach no rendered document")


def check_project_positions(doc, rep):
    """A project's `position` names a position of its own engagement.

    The renderer puts a project's bullets under the role line `position` names.
    One that names a role the engagement does not hold would render them under
    the latest title instead - the exact misattribution the key exists to stop
    (the Experion draft credited 2016 work to the 2025 role) - while looking
    like a record that had said where the work belonged.
    """
    by_id = {e.get("id"): e for e in doc.get("engagements") or [] if isinstance(e, dict)}
    listing = {pid: e.get("id") for e in by_id.values() for pid in (e.get("projects") or [])}
    for p in doc.get("projects") or []:
        role = p.get("position")
        if not role:
            continue
        eng = p.get("engagement") or listing.get(p.get("id"))
        held = [q.get("id") for q in (by_id.get(eng) or {}).get("positions") or []]
        if role not in held:
            where = f"engagement {eng!r}" if eng in by_id else "no engagement"
            rep.fail(f"project {p.get('id')}: position {role!r} is not a position of {where} "
                     f"- its bullets would render under the wrong role (fix: set position to "
                     f"one of {', '.join(repr(h) for h in held) or 'its engagement positions'}, "
                     f"or remove it)")


def positional_bullet_ids(doc):
    """{derived id: project id} for every bullet whose id was numbered by position.

    The retired bundle compiler gave a bullet with no id of its own the id
    `ach_<slug("projects/<stem>.md")>_<n>`, derived from its project's `prj_<slug>`, so
    the slug recovered from the project id reconstructs the exact string it minted.
    That makes this an equality test rather than a pattern guess: `prj_care` with two
    bullets yields `ach_projects_care_md_1` and `..._2`, and inserting a bullet above
    them moves `..._1` onto the sentence that was `..._2`.

    A record drafted by `jsk kb export --urs` carries the career's own bullet ids and
    never one of these. This stays for a record edited by hand from an older one, which
    can still hold them.

    Only `projects[]` is walked: bullets are written in one place - inside the project -
    and every engagement carries `achievements: []`, so no engagement bullet can carry
    a derived id. A project whose id does not reconstruct is skipped: under-reporting is
    the right way to be wrong here, because the alternative is naming a bullet that was
    never at risk.
    """
    out = {}
    for p in doc.get("projects") or []:
        pid = p.get("id") or ""
        if not pid.startswith("prj_"):
            continue
        stem_slug = pid[len("prj_"):]
        for n, a in enumerate(p.get("achievements") or [], 1):
            if isinstance(a, dict) and a.get("id") == f"ach_projects_{stem_slug}_md_{n}":
                out[a["id"]] = pid
    return out


def check_unmaterialised_ids(doc, rep):
    """A view pointing at a bullet id nobody wrote down.

    A record carrying positional ids is exposed: insert a bullet above one that a view
    names positionally and every id below it shifts down a sentence. Nothing fails,
    because the id still resolves - check_references is satisfied either way - and the
    view quietly starts quoting different work.

    Only ids a view actually names are reported. An unmaterialised id nobody points
    at is not yet a hazard, and warning on every numbered bullet in the record would
    bury the ones that are.
    """
    positional = positional_bullet_ids(doc)
    if not positional:
        return
    seen = set()
    for v in doc.get("views") or []:
        for inc in v.get("include") or []:
            for aid in inc.get("achievements") or []:
                if aid not in positional or (v.get("id"), aid) in seen:
                    continue
                # One finding per view and id, not per mention: the same id named in
                # two include blocks of one view is one hole, and printing it twice
                # spends the finding cap saying so.
                seen.add((v.get("id"), aid))
                rep.warn(f"view {v.get('id')}: names achievement {aid!r} in project "
                         f"{positional[aid]}, an id derived from that bullet's "
                         f"position - inserting a bullet above it renumbers the rest "
                         f"and this view points at a different sentence (use the "
                         f"bullet's id in career/kb.ttl - `jsk kb export --urs` "
                         f"writes the career's ids)")


def check_coverage(doc, rep):
    """A project the person called resume-worthy must have something to quote.

    Nothing else here reads a body for evidence, so a record of 15 projects and no
    bullet anywhere validates clean and then costs whoever tailors against it the
    authoring pass the career should already have had.
    """
    empty = [p for p in doc.get("projects") or [] if not (p.get("achievements") or [])]
    for p in sorted(empty, key=lambda p: -(p.get("strength") or 0)):
        strength = p.get("strength") or 0
        msg = (f"project {p.get('id')}: strength {strength}, no evidence - no bullet "
               f"under it for a resume to quote")
        if strength >= COVERAGE_FAIL_STRENGTH:
            rep.fail(msg)
        else:
            rep.warn(msg)

    by_id = {p.get("id"): p for p in doc.get("projects") or []}
    for e in doc.get("engagements") or []:
        if e.get("achievements"):
            continue
        if any((by_id.get(pid) or {}).get("achievements") for pid in e.get("projects") or []):
            continue
        rep.warn(f"engagement {e.get('id')}: no achievements of its own and no project "
                 f"under it carries any - this employer renders with nothing beneath it")


def load_target(path):
    """The record to check.

    One shape: the URS document written for one application, live in `applications/<stem>/resume.json` or frozen there after it
    was sent. Both are the same file read the same way, which is the point of freezing
    it - a document sent two years ago is still re-checkable by this command.
    """
    with open(path, encoding="utf8") as fh:
        return json.load(fh), os.path.basename(path)


def parse(argv):
    """(positional arguments, {flag: value}) - a flag's value is never a positional."""
    args, flags, pending = [], {}, None
    for token in argv:
        if pending:
            flags[pending] = token
            pending = None
        elif token.startswith("-"):
            flags.setdefault(token, None)
            pending = token if token in VALUE_FLAGS else None
        else:
            args.append(token)
    return args, flags


def show(items, mark, limit):
    """At most `limit` findings, then the count of what was not listed.

    Truncating a gate's output is only safe while the total is still visible, so
    the caller prints the real counts in the header and this says how many it left
    out. The header keeps printing the true totals, so nothing is hidden by the cap.
    """
    for item in items[:limit or len(items)]:
        print(f"  {mark}  {item}")
    if limit and len(items) > limit:
        print(f"  {mark}  ... and {len(items) - limit} more")


def check_doc(doc):
    """Every check, over a parsed record (an object at the top level): a Report."""
    rep = Report()
    for key in ("urs", "meta", "person"):
        if key not in doc:
            rep.fail(f"missing required top-level key {key!r}")
    version = doc.get("urs", "")
    if not re.match(r"^1\.\d+\.\d+", str(version)):
        rep.fail(f"unsupported urs version {version!r} - this tool implements 1.x")

    walkable = check_shape(doc, rep)
    if walkable:
        name = (doc.get("person") or {}).get("name")
        if not (isinstance(name, dict) and name.get("full")):
            rep.fail("person.name.full is required and is authoritative")
        ids = check_ids(doc, rep)
        check_periods(doc, rep)
        check_references(doc, ids, rep)
        check_views(doc, rep)
        check_metrics(doc, rep)
        check_provenance(doc, rep)
        check_placeholders(doc, rep)
        check_coverage(doc, rep)
        check_backrefs(doc, rep)
        check_project_positions(doc, rep)
        check_unmaterialised_ids(doc, rep)
        check_renderable(doc, rep)
    else:
        # Named, so a record with one shape failure listed does not read as a record
        # with one defect: nothing that walks it has looked yet.
        rep.fail("the remaining checks were not run - fix the shape first, then re-run")
    return rep


def main(argv):
    if wants_help(argv[1:]):
        # Before parse(), which would read --help as an unknown flag and exit 2.
        print(docstring_usage(__doc__))
        return 0
    args, flags = parse(argv[1:])
    # An ignored flag reads as an honoured one: `--level 2` used to exit 0, which
    # looks like "level 2 confirmed" to anyone who remembers the old gate.
    unknown = sorted(f for f in flags if f != "--strict" and f not in VALUE_FLAGS)
    if not args or unknown or len(args) > 1:
        if unknown:
            print(f"unknown flag: {', '.join(unknown)}")
        elif len(args) > 1:
            print(f"one record at a time, got {len(args)}: {' '.join(args)}")
        print("usage: python -m jsk.gates.validate_urs <resume.json> [--strict] "
              "[--max-findings N]")
        return 2
    path = args[0]
    strict = "--strict" in flags
    limit = MAX_FINDINGS
    if "--max-findings" in flags:
        raw = flags["--max-findings"]
        if raw is None or not raw.isdigit():
            print(f"--max-findings needs a whole number, got {raw!r}")
            print("fix:  --max-findings 50   - or 0 to print every finding")
            return 2
        limit = int(raw) or None
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2

    try:
        doc, label = load_target(path)
    except json.JSONDecodeError as e:
        print(f"checking: {os.path.basename(path)}\n\nFAIL 1   WARN 0")
        print(f"  FAIL  not valid JSON: {e}")
        print("\nDO NOT RENDER - fix the failures above")
        return 1
    except Exception as e:
        # A file that cannot be read - bytes that are not UTF-8, a permission refused -
        # cannot be checked, and saying why is more use than a stack trace.
        print(f"checking: {os.path.basename(path)}\n\nFAIL 1   WARN 0")
        print(f"  FAIL  {e}")
        print("\nDO NOT RENDER - fix the problem named above")
        return 1

    if not isinstance(doc, dict):
        print("FAIL 1   WARN 0\n  FAIL  top level is not an object")
        return 1

    rep = check_doc(doc)
    version = doc.get("urs", "")
    if strict:
        rep.fails.extend(rep.warns)
        rep.warns = []

    print(f"checking: {label}   urs: {version}")
    print(f"\nFAIL {len(rep.fails)}   WARN {len(rep.warns)}")
    show(rep.fails, "FAIL", limit)
    show(rep.warns, "warn", limit)
    print("\nPASS - safe to render" if not rep.fails
          else "\nDO NOT RENDER - fix the failures above")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
