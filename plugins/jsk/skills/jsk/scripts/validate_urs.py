#!/usr/bin/env python3
"""Validate a URS document against references/urs-spec.md.

Usage: python3 validate_urs.py <bundle-dir | resume.json> [--strict]
       --strict            treat warnings as failures
       --max-findings N    print at most N failures and N warnings (default 25;
                           0 prints every one)

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = valid. Exit 1 = do not render this. Exit 2 = usage error.

Standard library only. There is no schema check: nothing hand-writes this record
any more, so a structural check on it would only be re-checking `okf_compile.py`.
The rules that matter are the ones a schema
cannot express:

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

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.normpath(os.path.join(HERE, "..", "schema"))

# The same cap, flag name and default as validate_bundle.py. This gate is what
# jsk-verifier runs and reports back verbatim, so its output lands in an agent's
# context on every check - a bundle answering a hundred postings printed 381 lines
# and ~10,600 tokens of it. Nothing is hidden by the cap: the header keeps printing
# the true totals and the last line says how many were not listed.
MAX_FINDINGS = 25

# Flags that consume the token after them, so a value can never be read as the path.
VALUE_FLAGS = {"--max-findings"}

ID_PREFIX = {
    "organizations": "org", "engagements": "eng", "education": "edu",
    "credentials": "cred", "projects": "prj", "skills": "skill",
    "narratives": "nar", "referees": "ref", "views": "view",
}

# Concept type -> the record key it feeds, for the conservation check.
#
# Cardinality is deliberately NOT asserted. The relation is not 1:1 and the places it
# is not are all correct: Role 9 -> 4 engagements (roles group by organisation),
# Skill Set 1 -> 83 skills (one `# Skills` block flattens), Positioning 2 -> 4
# narratives. What holds for every type is weaker and sufficient: a type present on
# disk must produce something.
TYPE_TO_KEY = {
    "Organisation": "organizations", "Role": "engagements", "Project": "projects",
    "Education": "education", "Skill Set": "skills", "Positioning": "narratives",
    "View": "views",
}

# "Certification Status" is deliberately absent from that map: "none held" is a
# legitimate status that evidences no credential, so 1 concept -> 0 credentials is the
# compiler working (okf_compile.build_credentials), not a type being dropped.

# The strength at or above which a project with no evidence fails rather than warns.
# Keyed to strength because that is the person's own assertion that a project is worth
# putting on a resume - which makes the floor self-scaling, and non-retroactive without
# needing a bundle-revision gate: a bundle of low-strength stubs warns, a bundle
# claiming strong work with nothing behind it fails.
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
        # A metric compiled from `achievements/metrics.md` carries the row as written -
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
                     (" (this achievement carries no metrics at all: add the row to "
                      "achievements/metrics.md and name it in the bullet's `metric:`)"
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


def check_conservation(root, doc, rep):
    """What the bundle holds on disk, against what the compiler emitted.

    Every other check in this file iterates a record key and verifies the shape of
    what it finds. None of them can fail on an empty list, because an empty list
    satisfies every statement you can make about its elements - which is how
    `views: []` passed the record gate for months while `provenance_floor` never ran
    on anything at all.

    This is the only check that can see a type go missing, and it needs the bundle,
    so it does not run against an archived document.
    """
    import okf_compile
    counts = okf_compile.census(root)
    for ctype, key in TYPE_TO_KEY.items():
        n = counts.get(ctype, 0)
        if n and not (doc.get(key) or []):
            rep.fail(f"{n} {ctype!r} concept(s) on disk and record[{key!r}] is empty - "
                     f"the compiler read them and emitted nothing")


def check_backrefs(doc, rep):
    """Every project that names an engagement appears in that engagement's projects[].

    resolve.py walks `engagement["projects"]` and nothing else to reach a project's
    bullets, so a project missing from that list is silently absent from every
    rendered document while the record stays perfectly valid - a missing
    back-reference is not an invalid reference, which is why nothing caught it when
    okf_compile never populated the list at all.
    """
    listed = {pid for e in doc.get("engagements") or [] for pid in (e.get("projects") or [])}
    for p in doc.get("projects") or []:
        eng = p.get("engagement")
        if eng and p.get("id") not in listed:
            rep.fail(f"project {p.get('id')}: names engagement {eng!r} and appears in no "
                     f"engagement's projects[] - its bullets reach no rendered document")


def positional_bullet_ids(doc):
    """{derived id: project id} for every bullet whose id the compiler numbered.

    A project's id is `prj_<slug(stem)>` (okf_compile.ident) and the id its nth bullet
    gets when the concept wrote none down is `ach_<slug("projects/<stem>.md")>_<n>`
    (okf_compile.bullets) - so the stem slug recovered from the project id
    reconstructs the exact string the compiler would have minted. That makes this an
    equality test rather than a pattern guess. Measured on a compiled bundle:
    `prj_care` with two bullets yields `ach_projects_care_md_1` and `..._2`, and
    inserting a bullet above them moves `..._1` onto the sentence that was `..._2`.

    Only `projects[]` is walked. Engagement achievements exist in the record, but
    okf_compile calls bullets() from one place - build_projects - and gives every
    engagement `achievements: []`, so no engagement bullet can carry a derived id.

    A concept that declares its own `id:` in frontmatter breaks the reconstruction
    and is skipped: under-reporting is the right way to be wrong here, because the
    alternative is naming a bullet that was never at risk.
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

    The write layer materialises explicit ids before it mutates a concept's bullets,
    so a bundle that has been written to is immune. There is no migration, which
    leaves a bundle nobody has written to exposed: insert a bullet above one that a
    view names positionally and every id below it shifts down a sentence. Nothing
    fails, because the id still resolves - check_references is satisfied either way -
    and the view quietly starts quoting different work.

    Only ids a view actually names are reported. An unmaterialised id nobody points
    at is not yet a hazard, and warning on every numbered bullet in the bundle would
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
                         f"{positional[aid]}, an id the compiler derived from that "
                         f"bullet's position - inserting a bullet above it renumbers "
                         f"the rest and this view points at a different sentence "
                         f"(write the id down under the bullet in that concept's "
                         f"`# Bullets` block)")


def check_coverage(doc, rep):
    """A project the person called resume-worthy must have something to quote.

    Nothing else here reads a body for evidence, so a bundle of 15 projects and no
    `# Bullets` block anywhere validates clean and then costs whoever tailors against
    it the authoring pass the bundle should already have had.
    """
    empty = [p for p in doc.get("projects") or [] if not (p.get("achievements") or [])]
    for p in sorted(empty, key=lambda p: -(p.get("strength") or 0)):
        strength = p.get("strength") or 0
        msg = (f"project {p.get('id')}: strength {strength}, no evidence - nothing in "
               f"its `# Bullets` block for a resume to quote")
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
    """The record to check: a bundle compiled, or a document read.

    A bundle is the ordinary case now. A document is an archived application, frozen
    at submission and still worth being able to re-check years later.
    """
    if not os.path.isdir(path):
        with open(path, encoding="utf8") as fh:
            return json.load(fh), os.path.basename(path)
    sys.path.insert(0, HERE)
    import okf_compile
    return okf_compile.load(path), os.path.basename(os.path.abspath(path)) + " (compiled)"


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
    out. Same wording as validate_bundle.py - two gates answering the same question
    should not answer it differently.
    """
    for item in items[:limit or len(items)]:
        print(f"  {mark}  {item}")
    if limit and len(items) > limit:
        print(f"  {mark}  ... and {len(items) - limit} more")


def main(argv):
    args, flags = parse(argv[1:])
    if not args:
        print("usage: validate_urs.py <bundle-dir | resume.json> [--strict] "
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
        # A bundle that will not compile cannot be checked, and saying which concept
        # is wrong is more use than a stack trace about a dict that was never built.
        print(f"checking: {os.path.basename(path)}\n\nFAIL 1   WARN 0")
        print(f"  FAIL  {e}")
        print("\nDO NOT RENDER - fix the concept named above")
        return 1

    rep = Report()
    if not isinstance(doc, dict):
        print("FAIL 1   WARN 0\n  FAIL  top level is not an object")
        return 1

    for key in ("urs", "meta", "person"):
        if key not in doc:
            rep.fail(f"missing required top-level key {key!r}")
    version = doc.get("urs", "")
    if not re.match(r"^1\.\d+\.\d+", str(version)):
        rep.fail(f"unsupported urs version {version!r} - this tool implements 1.x")
    if not ((doc.get("person") or {}).get("name") or {}).get("full"):
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
    check_unmaterialised_ids(doc, rep)
    if os.path.isdir(path):
        check_conservation(path, doc, rep)

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
