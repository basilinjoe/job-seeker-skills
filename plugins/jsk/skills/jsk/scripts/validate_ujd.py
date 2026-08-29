#!/usr/bin/env python3
"""Validate a UJD document against references/ujd-spec.md.

Usage: python3 validate_ujd.py posting.json [--strict] [--level N] [--bundle DIR]
       --strict      treat conformance warnings as failures
       --level N     assert conformance level N (0, 1 or 2)
       --bundle DIR  check capability values against the bundle's vocabulary

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = valid. Exit 1 = do not score against this. Exit 2 = called wrong.

Standard library only. If `jsonschema` happens to be installed the full schema
is checked as well, but the rules that matter most here are the ones a schema
cannot express:

  * a provenance span that is not actually a substring of source.raw_text - the
    check that stops an extraction from claiming a traceability it does not have
  * a requirement group whose members do not resolve, or that contains itself
  * a capability value absent from the bundle's vocabulary, which scores zero on
    every project while looking exactly like absent evidence

The first two fail the document. The third warns, because the vocabulary is the
person's own file and may legitimately be behind the posting.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.normpath(os.path.join(HERE, "..", "schema"))

ID_PREFIX = {
    "requirements": "req", "requirement_groups": "grp", "responsibilities": "rsp",
    "benefits": "ben", "locations": "loc", "emphasis": "emp", "concerns": "cnc",
}

# Seniority is shared with URS verbatim. It is repeated here rather than imported
# because the two documents must agree, and a copy that drifts is caught by the
# test that compares them - an import would hide the coupling instead.
SENIORITY = ["architecture-ownership", "product-ownership", "platform-design",
             "team-leadership", "technical-ownership", "hands-on-senior",
             "hands-on", "junior"]

# Hard filters. These live in `eligibility` and are never scored, so a requirement
# claiming one of these kinds has put a visa bar on the same axis as a keyword.
HARD_FILTER_KINDS = {"work-authorization", "clearance", "location"}

VOCAB_ITEM = re.compile(r"^\s*[-*]\s+`([^`]+)`")


class Report:
    def __init__(self):
        self.fails = []
        self.warns = []

    def fail(self, msg):
        self.fails.append(msg)

    def warn(self, msg):
        self.warns.append(msg)


def provenances(doc):
    """Every provenance-shaped object in the document, with the id that owns it.

    Keyed on shape rather than on field name because `role.seniority_provenance`
    is a provenance that is not called `provenance`, and a walker looking for the
    name would skip the one claim the entire seniority axis rests on.
    """
    found = []

    def walk(node, owner):
        if isinstance(node, dict):
            owner = node.get("id", owner)
            if "status" in node and isinstance(node.get("source"), dict):
                found.append((node, owner))
            for value in node.values():
                walk(value, owner)
        elif isinstance(node, list):
            for value in node:
                walk(value, owner)

    walk(doc, "(root)")
    return found


def read_vocabulary(bundle):
    """Capability values from framework/capability-vocabulary.md.

    Only backticked list items count, matching score_projects.py. Prose and
    fenced examples are ignored, and an absent file means the check is skipped
    rather than every value being rejected.
    """
    path = os.path.join(bundle, "framework", "capability-vocabulary.md")
    if not os.path.exists(path):
        return None
    values = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            match = VOCAB_ITEM.match(line)
            if match:
                values.add(match.group(1).strip())
    return values or None


def check_ids(doc, rep):
    """Ids are unique and prefixed by kind."""
    ids = {}
    for key, prefix in ID_PREFIX.items():
        for item in doc.get(key) or []:
            if not isinstance(item, dict):
                continue
            ident = item.get("id")
            if not ident:
                rep.fail(f"{key}: an entry has no id - referencing beats copying")
                continue
            if ident in ids:
                rep.fail(f"duplicate id {ident!r} in {key} and {ids[ident]}")
            ids[ident] = key
            if not ident.startswith(prefix + "_"):
                rep.fail(f"{ident!r} in {key} should be prefixed {prefix}_")
    return ids


def check_groups(doc, rep):
    """Members resolve, and the graph does not contain itself.

    A cycle is not hypothetical. Two levels of nesting is the documented shape and
    it is written by hand or by a model, either of which can point a group at its
    own parent - at which point every evaluator recurses until it dies.
    """
    groups = {g["id"]: g for g in (doc.get("requirement_groups") or [])
              if isinstance(g, dict) and g.get("id")}
    reqs = {r["id"] for r in (doc.get("requirements") or [])
            if isinstance(r, dict) and r.get("id")}

    for gid, group in groups.items():
        members = group.get("members") or []
        if not members:
            rep.fail(f"group {gid} has no members - a choice with no arms is not a requirement")
        for member in members:
            if member not in groups and member not in reqs:
                rep.fail(f"group {gid} names member {member!r}, which is neither a "
                         f"requirement nor a group in this document")
        if group.get("satisfy") == "at-least":
            n = group.get("n")
            if isinstance(n, int) and n > len(members):
                rep.fail(f"group {gid} asks for at least {n} of {len(members)} members")

    # Cycle detection over group-to-group edges only; requirements are leaves.
    colour = {}

    def visit(gid, trail):
        state = colour.get(gid)
        if state == "done":
            return
        if state == "open":
            rep.fail("requirement group cycle: " + " -> ".join(trail + [gid]))
            return
        colour[gid] = "open"
        for member in groups.get(gid, {}).get("members") or []:
            if member in groups:
                visit(member, trail + [gid])
        colour[gid] = "done"

    for gid in groups:
        visit(gid, [])

    for req in doc.get("requirements") or []:
        if not isinstance(req, dict):
            continue
        named = req.get("group")
        if named and named not in groups:
            rep.fail(f"requirement {req.get('id')} names group {named!r}, which does not exist")
    return groups


def check_requirements(doc, rep, vocabulary):
    """The matching axis. A value that cannot be matched on is the failure here."""
    for req in doc.get("requirements") or []:
        if not isinstance(req, dict):
            continue
        rid = req.get("id", "(unnamed)")
        kind = req.get("kind")
        value = req.get("value")

        if kind == "capability":
            if not value:
                rep.warn(f"{rid}: capability requirement has no `value` - it can be read "
                         f"but not scored")
            elif vocabulary is not None and value not in vocabulary:
                rep.warn(f"{rid}: capability {value!r} is not in the bundle vocabulary - "
                         f"it scores zero on every project, which looks identical to "
                         f"absent evidence")

        if kind in HARD_FILTER_KINDS:
            rep.fail(f"{rid}: kind {kind!r} belongs in `eligibility`, not `requirements` - "
                     f"no amount of skills overlap may offset a visa bar")

        exp = req.get("experience") or {}
        low, high = exp.get("min_months"), exp.get("max_months")
        if isinstance(low, int) and isinstance(high, int) and low > high:
            rep.fail(f"{rid}: experience min_months {low} exceeds max_months {high}")

        # The schema enforces this for `implicit`; restated as a readable message
        # because it is the rule that stops a guess being promoted to a demand.
        if req.get("necessity") == "implicit":
            source = (req.get("provenance") or {}).get("source") or {}
            if source.get("kind") != "inferred":
                rep.fail(f"{rid}: necessity `implicit` requires source.kind `inferred` - "
                         f"the posting never stated it")


def check_provenance(doc, rep):
    """No inferred source may carry a confirmed status, at any depth."""
    for prov, owner in provenances(doc):
        kind = (prov.get("source") or {}).get("kind")
        if kind == "inferred" and prov.get("status") == "confirmed":
            rep.fail(f"{owner}: status `confirmed` on an `inferred` source - laundering "
                     f"a guess into a fact is the failure this format exists to prevent")


def check_spans(doc, rep, strict_spans):
    """A posting-text span must be traceable to the text it was read from."""
    raw = (doc.get("source") or {}).get("raw_text")
    for prov, owner in provenances(doc):
        source = prov.get("source") or {}
        if source.get("kind") != "posting-text":
            continue
        span = source.get("span")
        if not span:
            if strict_spans:
                rep.fail(f"{owner}: posting-text extraction with no span - an extraction "
                         f"nobody can trace back to a span is an assertion")
            continue
        if raw and span not in raw:
            rep.fail(f"{owner}: span is not a substring of source.raw_text - {span[:60]!r}")


def check_role(doc, rep):
    role = doc.get("role") or {}
    seniority = role.get("seniority")
    if seniority and seniority not in SENIORITY:
        rep.fail(f"role.seniority {seniority!r} is not one of the eight URS values - the "
                 f"seniority axis breaks if the two vocabularies diverge")
    for code in role.get("occupation") or []:
        if isinstance(code, dict) and code.get("scheme") and not code.get("scheme_version"):
            rep.warn(f"occupation code {code.get('code')!r} has no scheme_version - a code "
                     f"without its vintage is undecodable")
        if isinstance(code, dict) and code.get("match_type") == "related":
            rep.warn(f"occupation code {code.get('code')!r} is match_type `related`, which "
                     f"the spec says not to score as a match")


def conformance(doc):
    """The highest level the document actually reaches."""
    posting = doc.get("posting") or {}
    organization = doc.get("organization") or {}
    if not posting.get("title") or not organization.get("name"):
        return 0

    reqs = [r for r in (doc.get("requirements") or []) if isinstance(r, dict)]
    structured = (bool(reqs)
                  and all(r.get("kind") and r.get("necessity") for r in reqs)
                  and bool((doc.get("role") or {}).get("seniority")))
    if not structured:
        return 0

    groups = [g for g in (doc.get("requirement_groups") or []) if isinstance(g, dict)]
    raw = (doc.get("source") or {}).get("raw_text")
    all_prov = (all((r.get("provenance") or {}).get("status") for r in reqs)
                and all((g.get("provenance") or {}).get("status") for g in groups))
    spans_present = all(
        (prov.get("source") or {}).get("span")
        for prov, _ in provenances(doc)
        if (prov.get("source") or {}).get("kind") == "posting-text")
    if raw and all_prov and spans_present:
        return 2
    return 1


def schema_check(doc, rep):
    try:
        import jsonschema
    except ImportError:
        return "jsonschema not installed - structural rules checked, full schema skipped"
    path = os.path.join(SCHEMA_DIR, "ujd-v1.schema.json")
    with open(path, encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    for error in errors[:20]:
        where = "/".join(str(p) for p in error.path) or "(root)"
        rep.fail(f"schema: {where}: {error.message}")
    if len(errors) > 20:
        rep.fail(f"schema: +{len(errors) - 20} further violations")
    return f"schema validated against {os.path.basename(path)}"


def main(argv):
    if len(argv) < 2:
        print("usage: validate_ujd.py posting.json [--strict] [--level N] [--bundle DIR]")
        return 2
    path = argv[1]
    strict = "--strict" in argv
    want_level = None
    if "--level" in argv:
        try:
            want_level = int(argv[argv.index("--level") + 1])
        except (IndexError, ValueError):
            print("--level needs a number: 0, 1 or 2")
            return 2
    bundle = None
    if "--bundle" in argv:
        try:
            bundle = argv[argv.index("--bundle") + 1]
        except IndexError:
            print("--bundle needs a directory")
            return 2
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2

    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except json.JSONDecodeError as error:
        print(f"checking: {os.path.basename(path)}\n\nFAIL 1   WARN 0")
        print(f"  FAIL  not valid JSON: {error}")
        print("\nDO NOT SCORE - fix the failures above")
        return 1

    rep = Report()
    if not isinstance(doc, dict):
        print("FAIL 1   WARN 0\n  FAIL  top level is not an object")
        return 1

    for key in ("ujd", "meta", "posting"):
        if key not in doc:
            rep.fail(f"missing required top-level key {key!r}")
    version = doc.get("ujd", "")
    if not re.match(r"^1\.\d+\.\d+", str(version)):
        rep.fail(f"unsupported ujd version {version!r} - this tool implements 1.x")
    if not (doc.get("posting") or {}).get("title"):
        rep.fail("posting.title is required - it is the one thing every posting has")

    vocabulary = read_vocabulary(bundle) if bundle else None
    if bundle and vocabulary is None:
        rep.warn(f"no capability vocabulary under {bundle} - capability values unchecked")

    check_ids(doc, rep)
    check_groups(doc, rep)
    check_requirements(doc, rep, vocabulary)
    check_provenance(doc, rep)
    check_role(doc, rep)
    note = schema_check(doc, rep)

    level = conformance(doc)
    check_spans(doc, rep, strict_spans=(want_level == 2 or level == 2))
    if want_level is not None and level < want_level:
        rep.fail(f"conformance level {level}, asserted {want_level}")

    if strict:
        rep.fails.extend(rep.warns)
        rep.warns = []

    print(f"checking: {os.path.basename(path)}   ujd: {version}   conformance: level {level}")
    print(note)
    print(f"\nFAIL {len(rep.fails)}   WARN {len(rep.warns)}")
    for failure in rep.fails:
        print("  FAIL  " + failure)
    for warning in rep.warns:
        print("  warn  " + warning)
    print("\nPASS - safe to score against" if not rep.fails
          else "\nDO NOT SCORE - fix the failures above")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
