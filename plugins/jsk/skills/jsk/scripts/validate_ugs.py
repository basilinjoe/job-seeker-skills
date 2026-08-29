#!/usr/bin/env python3
"""Validate a UGS document against references/ugs-spec.md.

Usage: python3 validate_ugs.py gaps.json [--recompute] [--report]
                               [--carry prev.gaps.json] [--strict] [--level N]
       --recompute    re-derive every derivable field and fail on disagreement
       --report       print the readable checkpoint, and the loop's own status
       --carry FILE   the previous round, to catch a question being re-asked
       --strict       treat warnings as failures
       --level N      assert conformance level N (0, 1 or 2)

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = valid. Exit 1 = do not act on this. Exit 2 = called wrong.

Standard library only. This is the auditor for a document a model wrote, so the
division of labour matters and is worth stating:

  RECOMPUTED, and a disagreement fails the document
    * group verdicts, from their members - the case a flat list gets wrong in
      both directions, and the one thing here that is pure boolean algebra
    * score.aggregate.value, from its own stated formula over its own
      components - an aggregate nothing recomputed is the failure UGS design
      rule 8 exists to prevent
    * both subject checksums - a verdict recomputed against an edited posting is
      a different verdict
    * that no eligibility requirement reached a score component

  CHECKED but NOT recomputed
    * component `value` per axis. The spec blesses three different computations
      - summed evidence credit, a group verdict, and an axis with no assessments
      at all - so a single mechanical rule would reject correct documents. What
      is enforced instead: `of` resolves, `normalized` is in range, and the
      aggregate built from them recomputes exactly.
    * surface[] and surplus[] entries. Both carry vocabulary judgements - an
      alias the record uses instead of the posting's term, a strength the
      posting never asked about - which no set difference produces. What is
      enforced instead is the *obligation*: evidence that never reached the
      rendered view must be reported as a surface gap.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.normpath(os.path.join(HERE, "..", "schema"))

SATISFACTION = {"satisfied", "partial", "stale"}
GROUP_VERDICTS = {"satisfied", "partial", "unsatisfied", "indeterminate"}

# Question.priority, in the order the queue is worked. `unmet-requirement` is
# UGS 1.1 and sits second: a posting requirement the record does not answer
# outranks record hygiene, because it is the reason this round is happening.
PRIORITY_ORDER = ["blocking", "unmet-requirement", "inferred-claim",
                  "missing-metric", "unexplored"]

# Hard filters. UJD keeps these out of `requirements`; UGS keeps them out of the
# score. Restated here because the assessment side is where the leak would show.
HARD_FILTER_KINDS = {"work-authorization", "clearance", "location",
                     "applicant-location", "security-clearance"}

RESOLVED = {"confirmed", "corrected", "cut", "answered", "unavailable", "deferred"}
PARKED = {"unavailable", "deferred"}


class Report:
    def __init__(self):
        self.fails = []
        self.warns = []

    def fail(self, msg):
        self.fails.append(msg)

    def warn(self, msg):
        self.warns.append(msg)


def resolve_ref(ref, gaps_path):
    """Find a subject document named relative to something.

    Refs in the wild are written relative to the gap file, to the skill directory
    above it, or to wherever the tool was run. Trying each and taking the first
    that exists beats making the author guess which one this tool assumes.
    """
    if not ref:
        return None
    base = os.path.dirname(os.path.abspath(gaps_path))
    for candidate in (os.path.join(base, ref),
                      os.path.join(os.path.dirname(base), ref),
                      os.path.abspath(ref)):
        if os.path.exists(candidate):
            return candidate
    return None


def checksum(raw):
    """sha256 over the document with line endings normalised.

    Not over the bytes as they sit on disk. A bundle is version-controlled and moves
    between machines, and a Windows checkout with core.autocrlf rewrites every LF to
    CRLF - which would invalidate every past assessment on clone, for a change that
    is not an edit to the posting in any sense a person would recognise.

    The purpose of the checksum is to catch a subject document being *changed* after a
    verdict was computed against it. Normalising here keeps it answering that question
    and only that one.
    """
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_subject(subjects, key, gaps_path, rep):
    """The subject document, plus the sha256 of the bytes actually read."""
    entry = (subjects or {}).get(key) or {}
    ref = entry.get("ref")
    if not ref:
        return None, None
    path = resolve_ref(ref, gaps_path)
    if not path:
        rep.warn(f"subjects.{key}.ref {ref!r} could not be found - cross-document "
                 f"checks for it are skipped, which is not the same as passing")
        return None, None
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return json.loads(raw.decode("utf-8")), checksum(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        rep.fail(f"subjects.{key}.ref {ref!r} is not readable JSON: {error}")
        return None, None


def collect_ids(doc):
    ids = set()
    for key in ("assessments", "group_assessments", "surplus", "surface", "questions",
                "methods"):
        for item in doc.get(key) or []:
            if isinstance(item, dict) and item.get("id"):
                ids.add(item["id"])
    for component in (doc.get("score") or {}).get("components") or []:
        if isinstance(component, dict) and component.get("id"):
            ids.add(component["id"])
    return ids


def check_subjects(doc, rep, posting, record, level):
    subjects = doc.get("subjects") or {}
    if not subjects.get("record"):
        rep.fail("subjects.record is required - a gap document with no record side "
                 "is not an assessment of anything")
    purpose = (doc.get("meta") or {}).get("purpose")
    if not subjects.get("posting"):
        if purpose != "self-assessment":
            rep.fail("subjects.posting is absent, which is only valid for a record "
                     f"audit - meta.purpose is {purpose!r}, expected 'self-assessment'")
        if doc.get("assessments"):
            rep.fail("assessments reference posting requirements, but no posting is "
                     "pinned in subjects")
    if level >= 2:
        for key in ("posting", "record"):
            entry = subjects.get(key)
            if entry and not entry.get("checksum"):
                rep.warn(f"subjects.{key}.checksum is absent - conformance level 2 "
                         f"asks for both subjects checksummed")


def record_entity_ids(record):
    """Every id in the URS document, at any depth.

    Collected generically rather than from a list of known keys: `pos_` ids live
    two levels down under engagements[].positions[], and a collector that has to
    be told about each nesting will silently stop resolving whichever one gets
    added next - reporting real evidence as a dangling reference.
    """
    ids = set()

    def walk(node):
        if isinstance(node, dict):
            ident = node.get("id")
            if isinstance(ident, str):
                ids.add(ident)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(record or {})
    return ids


def check_assessments(doc, rep, posting, record):
    """Verdicts are evidenced, and both sides of the join resolve."""
    requirement_ids = set()
    if posting:
        requirement_ids = {r["id"] for r in (posting.get("requirements") or [])
                           if isinstance(r, dict) and r.get("id")}
    record_ids = record_entity_ids(record)

    seen = {}
    question_ids = {q["id"] for q in doc.get("questions") or []
                    if isinstance(q, dict) and q.get("id")}

    for assessment in doc.get("assessments") or []:
        if not isinstance(assessment, dict):
            continue
        aid = assessment.get("id", "(unnamed)")
        req = assessment.get("requirement")
        verdict = assessment.get("verdict")

        if req in seen:
            rep.fail(f"{aid}: requirement {req} is assessed twice, also by {seen[req]} - "
                     f"two verdicts on one demand is not an answer")
        seen[req] = aid

        if requirement_ids and req not in requirement_ids:
            rep.fail(f"{aid}: requirement {req!r} does not exist in the pinned posting")

        evidence = assessment.get("evidence") or []
        if verdict in SATISFACTION and not evidence:
            rep.fail(f"{aid}: verdict {verdict!r} with no evidence - an unevidenced "
                     f"verdict is an assertion wearing a verdict's clothes")
        if verdict == "partial" and not (assessment.get("shortfalls") or []):
            rep.fail(f"{aid}: partial on no named axis is a hedge, not a finding")
        if verdict == "unevidenced" and not assessment.get("question"):
            rep.fail(f"{aid}: unevidenced with no question - recording one without "
                     f"asking leaves it in the resume")

        named = assessment.get("question")
        if named and question_ids and named not in question_ids:
            rep.fail(f"{aid}: names question {named!r}, which is not in questions[]")

        for item in evidence:
            if not isinstance(item, dict):
                continue
            rid = item.get("record_id")
            if record_ids and rid not in record_ids:
                rep.fail(f"{aid}: evidence names record_id {rid!r}, which does not exist "
                         f"in the pinned record")
        if (verdict == "satisfied" and evidence
                and all(e.get("relation") == "asserted-only" for e in evidence
                        if isinstance(e, dict))):
            rep.warn(f"{aid}: satisfied on asserted-only evidence - it is identical to "
                     f"a real match in a keyword scan and is the single most dangerous "
                     f"thing here to score")

    if requirement_ids:
        unexamined = requirement_ids - set(seen)
        for req in sorted(unexamined):
            rep.warn(f"requirement {req} has no assessment - unexamined is not the "
                     f"same as satisfied")
    return seen


def recompute_groups(doc, rep, posting):
    """Group verdicts, re-derived from their members.

    This is the case UJD models groups for and the case a flat list gets wrong in
    both directions: flattened to independent must-haves a master's holder reads
    as unqualified; flattened to one `any` a bare bachelor's passes.
    """
    if not posting:
        return
    groups = {g["id"]: g for g in (posting.get("requirement_groups") or [])
              if isinstance(g, dict) and g.get("id")}
    by_requirement = {a.get("requirement"): a for a in doc.get("assessments") or []
                      if isinstance(a, dict)}
    by_group = {g.get("group"): g for g in doc.get("group_assessments") or []
                if isinstance(g, dict)}

    def verdict_of(member):
        if member in by_group:
            return by_group[member].get("verdict")
        assessment = by_requirement.get(member)
        return assessment.get("verdict") if assessment else None

    for stored in doc.get("group_assessments") or []:
        if not isinstance(stored, dict):
            continue
        gid = stored.get("id", "(unnamed)")
        group = groups.get(stored.get("group"))
        if not group:
            rep.fail(f"{gid}: group {stored.get('group')!r} does not exist in the "
                     f"pinned posting")
            continue

        if stored.get("satisfy") != group.get("satisfy"):
            rep.fail(f"{gid}: satisfy {stored.get('satisfy')!r} disagrees with the "
                     f"posting's {group.get('satisfy')!r} - denormalised, so it must match")

        members = group.get("members") or []
        verdicts = [verdict_of(m) for m in members]
        if any(v is None for v in verdicts):
            rep.warn(f"{gid}: a member has no assessment, so its verdict cannot be "
                     f"recomputed")
            continue

        satisfied = sum(1 for v in verdicts if v == "satisfied")
        partial = sum(1 for v in verdicts if v in ("partial", "stale"))
        indeterminate = sum(1 for v in verdicts if v == "indeterminate")
        satisfy = group.get("satisfy")
        need = group.get("n", 1) if satisfy == "at-least" else (
            len(members) if satisfy == "all" else 1)

        if satisfied >= need:
            expected = "satisfied"
        elif satisfied + partial >= need:
            expected = "partial"
        elif indeterminate and satisfied + partial + indeterminate >= need:
            expected = "indeterminate"
        else:
            expected = "unsatisfied"

        if stored.get("verdict") != expected:
            rep.fail(f"{gid}: verdict {stored.get('verdict')!r} but its members "
                     f"({', '.join(f'{m}={v}' for m, v in zip(members, verdicts))}) "
                     f"under `{satisfy}` give {expected!r}")

        branches = [b.get("member") for b in stored.get("branches") or []
                    if isinstance(b, dict)]
        if branches != list(members):
            rep.fail(f"{gid}: branches {branches} are not the group's own members in "
                     f"the group's own order {list(members)}")

        if expected in ("partial", "unsatisfied") and not stored.get("closest_branch"):
            rep.fail(f"{gid}: {expected} with no closest_branch - 'five months short on "
                     f"the degree arm' is advice, 'you fail the clause' is not")


def recompute_score(doc, rep, posting):
    """The aggregate, re-derived from its own formula over its own components."""
    score = doc.get("score") or {}
    components = {c["id"]: c for c in score.get("components") or []
                  if isinstance(c, dict) and c.get("id")}
    assessment_ids = {a["id"] for a in doc.get("assessments") or []
                      if isinstance(a, dict) and a.get("id")}

    if score.get("eligibility_excluded") is False:
        rep.fail("score.eligibility_excluded is false - eligibility is a gate and can "
                 "never be a score component")

    eligibility_reqs = set()
    if posting:
        eligibility_reqs = {r["id"] for r in (posting.get("requirements") or [])
                            if isinstance(r, dict) and r.get("kind") in HARD_FILTER_KINDS}
    by_id = {a.get("id"): a for a in doc.get("assessments") or [] if isinstance(a, dict)}

    for cid, component in components.items():
        of = component.get("of") or []
        if not of:
            rep.warn(f"{cid}: no `of` - a component that cannot name the assessments it "
                     f"was computed from cannot be checked")
        for aid in of:
            if aid not in assessment_ids:
                rep.fail(f"{cid}: `of` names {aid!r}, which is not an assessment here")
            elif by_id[aid].get("requirement") in eligibility_reqs:
                rep.fail(f"{cid}: `of` names {aid!r}, whose requirement is a hard "
                         f"filter - no skills overlap may offset a visa bar")
        normalized = component.get("normalized")
        if normalized is not None and not 0 <= normalized <= 1:
            rep.fail(f"{cid}: normalized {normalized} is outside 0-1")

    aggregate = score.get("aggregate")
    if not aggregate:
        return
    included = aggregate.get("components_included") or []
    missing = [c for c in included if c not in components]
    if missing:
        rep.fail(f"score.aggregate.components_included names {missing}, which are not "
                 f"components here")
        return
    if not aggregate.get("formula"):
        rep.fail("score.aggregate has no formula - an aggregate that cannot say how it "
                 "was computed is refused")
        return

    weights = [components[c].get("weight") for c in included]
    norms = [components[c].get("normalized") for c in included]
    if any(w is None for w in weights) or any(n is None for n in norms):
        rep.warn("score.aggregate cannot be recomputed - a component is missing weight "
                 "or normalized")
        return
    denominator = sum(weights)
    if not denominator:
        rep.fail("score.aggregate: component weights sum to zero")
        return
    expected = sum(w * n for w, n in zip(weights, norms)) / denominator
    stated = aggregate.get("value")
    if stated is None or abs(stated - expected) > 0.005:
        rep.fail(f"score.aggregate.value is {stated}, but sum(weight x normalized) / "
                 f"sum(weight) over its own components_included is {expected:.4f} - "
                 f"the number and the formula do not describe each other")


def check_surface(doc, rep, record):
    """Surface gaps require a view, and evidence outside the view requires one."""
    subjects = doc.get("subjects") or {}
    view_id = ((subjects.get("record") or {}).get("view"))
    surface = doc.get("surface") or []

    if surface and not view_id:
        rep.fail("surface[] is populated but subjects.record.view names nothing - a "
                 "keyword is always missing *from* something, and during a gap round "
                 "nothing has been sent yet")
    if not view_id or not record:
        return

    view = next((v for v in record.get("views") or []
                 if isinstance(v, dict) and v.get("id") == view_id), None)
    if not view:
        rep.fail(f"subjects.record.view {view_id!r} is not a view in the pinned record")
        return

    included = {entry.get("ref") for entry in view.get("include") or []
                if isinstance(entry, dict)}
    for entry in view.get("include") or []:
        for ach in (entry or {}).get("achievements") or []:
            included.add(ach)

    reported = set()
    for gap in surface:
        if isinstance(gap, dict):
            reported.update(gap.get("record_ids") or [])

    for assessment in doc.get("assessments") or []:
        if not isinstance(assessment, dict):
            continue
        if assessment.get("verdict") not in SATISFACTION:
            continue
        evidence_ids = [e.get("record_id") for e in assessment.get("evidence") or []
                        if isinstance(e, dict)]
        if not evidence_ids:
            continue
        # Skills, credentials and education are rendered by section rather than by
        # the include list, so only engagement- and project-scoped evidence can be
        # said to have been left out of a view.
        scoped = [r for r in evidence_ids
                  if r and r.split("_")[0] in ("eng", "prj", "ach")]
        if scoped and not any(r in included for r in scoped) and not (
                set(scoped) & reported):
            rep.fail(f"{assessment.get('id')}: satisfied on evidence {scoped} that the "
                     f"rendered view does not include, and no surface[] entry reports "
                     f"it - held in the record and absent from what is being sent is a "
                     f"different failure from not having it")


def check_questions(doc, rep, carried):
    """The queue is ordered, and a parked question does not come back unasked."""
    seen_rank = -1
    for question in doc.get("questions") or []:
        if not isinstance(question, dict):
            continue
        qid = question.get("id", "(unnamed)")
        priority = question.get("priority")
        if priority not in PRIORITY_ORDER:
            rep.fail(f"{qid}: priority {priority!r} is not one of {PRIORITY_ORDER}")
            continue
        rank = PRIORITY_ORDER.index(priority)
        if rank < seen_rank:
            rep.warn(f"{qid}: priority {priority!r} appears after a lower-priority "
                     f"question - questions[] is worked in order")
        seen_rank = max(seen_rank, rank)
        resolution = question.get("resolution")
        if resolution and resolution not in RESOLVED:
            rep.fail(f"{qid}: resolution {resolution!r} is not a known outcome")

    if not carried:
        return
    parked = {q.get("id"): q.get("resolution") for q in carried.get("questions") or []
              if isinstance(q, dict) and q.get("resolution") in PARKED}
    for question in doc.get("questions") or []:
        if not isinstance(question, dict):
            continue
        if question.get("id") in parked and not question.get("resolution"):
            rep.warn(f"{question.get('id')}: was {parked[question['id']]!r} last round "
                     f"and is unresolved again - re-asking what was already parked is "
                     f"how a loop stops ending")


def loop_status(doc):
    """Why the round loop should stop, or None if it should continue.

    Computed here rather than in the mode file because these are properties of
    this document, and a rule stated in prose in two places is a rule that will
    be applied differently in each.
    """
    questions = [q for q in doc.get("questions") or [] if isinstance(q, dict)]
    open_questions = [q for q in questions if not q.get("resolution")]
    if not open_questions:
        return ("stop", "questions[] is empty - nothing is worth asking")
    if all(q.get("priority") == "unexplored" for q in open_questions):
        return ("stop", "every open question is `unexplored` - that improves the record "
                        "in general, not this application, and belongs in /jsk:gaps")
    fresh = [q for q in open_questions if not q.get("asked")]
    if not fresh:
        return ("stop", "no new answerable question this round - every one is already "
                        "carried, which is where a loop starts spinning")
    return ("continue", f"{len(fresh)} new question(s) worth a round")


def conformance(doc):
    """The highest level the document actually reaches."""
    subjects = doc.get("subjects") or {}
    if not subjects.get("record"):
        return 0
    assessments = [a for a in doc.get("assessments") or [] if isinstance(a, dict)]
    if not assessments or not all(a.get("requirement") and a.get("verdict")
                                  for a in assessments):
        return 0

    evidenced = all(a.get("evidence") for a in assessments
                    if a.get("verdict") in SATISFACTION)
    typed = all(a.get("shortfalls") for a in assessments if a.get("verdict") == "partial")
    decomposed = bool((doc.get("score") or {}).get("components"))
    if not (evidenced and typed and decomposed):
        return 0

    all_prov = all((a.get("provenance") or {}).get("method")
                   and (a.get("provenance") or {}).get("stage") for a in assessments)
    spans = all(any(e.get("span") for e in a.get("evidence") or [])
                for a in assessments if a.get("verdict") in SATISFACTION)
    reviewed = bool((doc.get("review") or {}).get("state"))
    checksummed = all((subjects.get(k) or {}).get("checksum")
                      for k in ("posting", "record") if subjects.get(k))
    if all_prov and spans and reviewed and checksummed:
        return 2
    return 1


def schema_check(doc, rep):
    try:
        import jsonschema
    except ImportError:
        return "jsonschema not installed - structural rules checked, full schema skipped"
    path = os.path.join(SCHEMA_DIR, "ugs-v1.schema.json")
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


def render_report(doc, status):
    """The readable checkpoint that the retired Job Target file used to be."""
    out = ["", "# Assessment", "", "| Requirement | Verdict | Evidence | Shortfall |",
           "|---|---|---|---|"]
    for assessment in doc.get("assessments") or []:
        if not isinstance(assessment, dict):
            continue
        label = assessment.get("label") or assessment.get("requirement") or ""
        evidence = ", ".join(e.get("record_id", "") for e in assessment.get("evidence") or []
                             if isinstance(e, dict)) or "-"
        shortfall = "; ".join(
            f"{s.get('dimension')}: {s.get('evidenced')} vs {s.get('required')}"
            for s in assessment.get("shortfalls") or [] if isinstance(s, dict)) or "-"
        out.append(f"| {label} | {assessment.get('verdict')} | {evidence} | {shortfall} |")

    groups = doc.get("group_assessments") or []
    if groups:
        out += ["", "# Requirement groups", ""]
        for group in groups:
            if isinstance(group, dict):
                out.append(f"- **{group.get('group')}** (`{group.get('satisfy')}`): "
                           f"{group.get('verdict')}"
                           + (f" - closest: {group['closest_branch']}"
                              if group.get("closest_branch") else ""))

    surplus = doc.get("surplus") or []
    if surplus:
        out += ["", "# Surplus - held, and never asked for", ""]
        for item in surplus:
            if isinstance(item, dict):
                out.append(f"- {item.get('label')} ({item.get('relevance')})")

    surface = doc.get("surface") or []
    if surface:
        out += ["", "# Surface - held, and not in what is being sent", ""]
        for item in surface:
            if isinstance(item, dict):
                out.append(f"- {item.get('term')}: {item.get('remedy')}")

    open_questions = [q for q in doc.get("questions") or []
                      if isinstance(q, dict) and not q.get("resolution")]
    if open_questions:
        out += ["", "# Questions, in order", ""]
        for question in sorted(open_questions,
                               key=lambda q: PRIORITY_ORDER.index(q["priority"])
                               if q.get("priority") in PRIORITY_ORDER else 99):
            out.append(f"- **[{question.get('priority')}]** {question.get('text')}")

    score = (doc.get("score") or {}).get("aggregate")
    if score:
        out += ["", f"# Score: {score.get('value')}", "", score.get("formula", "")]

    out += ["", f"# Loop: {status[0].upper()} - {status[1]}", ""]
    return "\n".join(out)


def main(argv):
    if len(argv) < 2:
        print("usage: validate_ugs.py gaps.json [--recompute] [--report] "
              "[--carry prev.gaps.json] [--strict] [--level N]")
        return 2
    path = argv[1]
    strict = "--strict" in argv
    recompute = "--recompute" in argv
    want_report = "--report" in argv
    want_level = None
    if "--level" in argv:
        try:
            want_level = int(argv[argv.index("--level") + 1])
        except (IndexError, ValueError):
            print("--level needs a number: 0, 1 or 2")
            return 2
    carry_path = None
    if "--carry" in argv:
        try:
            carry_path = argv[argv.index("--carry") + 1]
        except IndexError:
            print("--carry needs a file")
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
        print("\nDO NOT ACT ON THIS - fix the failures above")
        return 1

    rep = Report()
    if not isinstance(doc, dict):
        print("FAIL 1   WARN 0\n  FAIL  top level is not an object")
        return 1

    for key in ("ugs", "meta", "subjects"):
        if key not in doc:
            rep.fail(f"missing required top-level key {key!r}")
    version = doc.get("ugs", "")
    if not re.match(r"^1\.\d+\.\d+", str(version)):
        rep.fail(f"unsupported ugs version {version!r} - this tool implements 1.x")

    carried = None
    if carry_path:
        if not os.path.exists(carry_path):
            print(f"file not found: {carry_path}")
            return 2
        with open(carry_path, encoding="utf-8") as fh:
            carried = json.load(fh)

    subjects = doc.get("subjects") or {}
    posting, posting_sum = load_subject(subjects, "posting", path, rep)
    record, record_sum = load_subject(subjects, "record", path, rep)

    level = conformance(doc)
    check_subjects(doc, rep, posting, record, level)
    check_assessments(doc, rep, posting, record)
    check_surface(doc, rep, record)
    check_questions(doc, rep, carried)
    note = schema_check(doc, rep)

    if recompute:
        recompute_groups(doc, rep, posting)
        recompute_score(doc, rep, posting)
        for key, actual in (("posting", posting_sum), ("record", record_sum)):
            stated = (subjects.get(key) or {}).get("checksum")
            # `sha256:<hex>` and a bare `<hex>` are both in use and both name the
            # same thing. Rejecting one of them would be a formatting opinion
            # dressed up as an integrity failure.
            if stated and ":" in stated:
                stated = stated.split(":", 1)[1]
            if stated and actual and stated.lower() != actual:
                rep.fail(f"subjects.{key}.checksum does not match the file as read - a "
                         f"verdict recomputed against an edited {key} is a different "
                         f"verdict")

    if want_level is not None and level < want_level:
        rep.fail(f"conformance level {level}, asserted {want_level}")

    if strict:
        rep.fails.extend(rep.warns)
        rep.warns = []

    status = loop_status(doc)
    print(f"checking: {os.path.basename(path)}   ugs: {version}   "
          f"conformance: level {level}")
    print(note + ("   recomputed" if recompute else "   (no --recompute: derived "
                                                    "fields taken on trust)"))
    print(f"\nFAIL {len(rep.fails)}   WARN {len(rep.warns)}")
    for failure in rep.fails:
        print("  FAIL  " + failure)
    for warning in rep.warns:
        print("  warn  " + warning)
    if want_report:
        print(render_report(doc, status))
    else:
        print(f"\nloop: {status[0].upper()} - {status[1]}")
    print("\nPASS" if not rep.fails else "\nDO NOT ACT ON THIS - fix the failures above")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
