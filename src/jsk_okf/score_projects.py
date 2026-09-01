#!/usr/bin/env python3
"""Rank a URS record's projects against a UJD posting, per references/mode-tailor.md

Usage: python3 score_projects.py <record.json> <posting.json>
                                 [--markdown] [--as-of YEAR] [--include-implicit]
                                 [--assume-technologies a,b,c]

On Windows use `python` or `py -3` in place of `python3`.

    score =  capability_overlap x 3     # primary axis, a count
           + technology_overlap  x 2    # a count
           + domain_match        x 2    # binary
           + seniority_match     x 2    # 0.0-1.0, see SENIORITY below
           + strength                   # 1-5
           + recency_bonus              # +2 within 3 years, +1 within 6

Both sides are JSON. Requirements come from the posting's `requirements[]`, and
projects from the record's `projects[]`, so the document a gap analysis assesses
is the document this ranking was computed over. When the scorer read the bundle
and the assessor read the record they could disagree about what the record held,
and nothing would have said so.

Standard library only.
Exit 0 = scored. Exit 1 = nothing to score. Exit 2 = usage error.
"""
import argparse
import datetime
import difflib
import json
import os
import re
import sys

# Most senior first. Ranks are positions in this list, counted from the bottom.
SENIORITY = ["architecture-ownership", "product-ownership", "platform-design",
             "team-leadership", "technical-ownership", "hands-on-senior",
             "hands-on", "junior"]
RANK = {name: len(SENIORITY) - 1 - i for i, name in enumerate(SENIORITY)}

RECENT_BONUS = ((3, 2), (6, 1))

# `implicit` requirements are ones the posting never stated. Naming them lets a
# scorer drop them in one predicate, and dropping them is the default: an
# inference that moves a x3 term is an invented requirement.
#
# `must-have` is UJD's word for `required`. It is here because a posting migrated
# out of an archived UJD document still carries it, and because the alternative -
# an unrecognised word falling through to `implicit` - drops the whole primary
# axis without saying so. That is exactly the failure this mapping exists to stop.
LEGACY_NECESSITY = {"must-have": "required", "nice-to-have": "preferred"}
SCORED_NECESSITY = {"required", "preferred"}
KNOWN_NECESSITY = SCORED_NECESSITY | {"implicit"} | set(LEGACY_NECESSITY)

YEAR = re.compile(r"^(\d{4})")


def near_terms(term, pool, limit=2):
    """Terms in `pool` that plausibly name the same thing as `term`.

    Deliberately conservative, because a wrong suggestion here is worse than none:
    it reads as "tag this project with that capability", and tagging a project with
    a capability it does not have is the one thing the exact-match rule exists to
    prevent. String similarity alone is not enough - 'engineer-mentoring' and
    'data-engineering' score 0.65 on SequenceMatcher and share no whole word.

    So: two shared words, or near-identical spelling. 'event-streaming-architecture'
    and 'event-driven-architecture' clear the first; a typo clears the second;
    'regulated-systems-design' and 'api-design', which share only the generic tail
    'design', clear neither.
    """
    words = set(term.split("-"))
    scored = []
    for other in pool:
        shared = words & set(other.split("-"))
        ratio = difflib.SequenceMatcher(None, term, other).ratio()
        if len(shared) >= 2 or ratio >= 0.8:
            scored.append((len(shared), round(ratio, 3), other))
    scored.sort(reverse=True)
    return [other for _, _, other in scored[:limit]]


def as_set(value):
    """A list, a bare string, or nothing, as a set of trimmed strings."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.strip()} if value.strip() else set()
    return {str(v).strip() for v in value if str(v).strip()}


def seniority_match(project, sought):
    """1.0 at or above the level sought, decaying linearly to 0.0 at junior.

    mode-tailor.md left this undefined, so every session decided it again. Evidence
    from a more senior engagement than the posting asks for is not worth less - the
    penalty is for falling short, not for overshooting.
    """
    if not sought or sought not in RANK:
        return 1.0
    want = RANK[sought]
    if want == 0:
        return 1.0
    have = RANK.get(project, 0)
    return 1.0 if have >= want else max(0.0, 1.0 - (want - have) / want)


def project_year(project):
    """The year a project last ran, for the recency bonus.

    URS carries a Period rather than the bundle's bare `recency:` year. An ongoing
    project is as recent as it gets; one with no end and no ongoing state is dated
    from its start, which is the conservative reading.
    """
    period = project.get("period") or {}
    if period.get("state") == "ongoing":
        return None  # scored as current
    for key in ("end", "start"):
        value = (period.get(key) or {}).get("value")
        if value:
            match = YEAR.match(str(value))
            if match:
                return int(match.group(1))
    return None


def recency_bonus(project, as_of):
    year = project_year(project)
    if year is None:
        # Ongoing, or undated. Ongoing earns the full bonus; undated cannot be
        # distinguished from it here and the record gate is where that is caught.
        return RECENT_BONUS[0][1] if (project.get("period") or {}).get(
            "state") == "ongoing" else 0
    age = as_of - year
    for within, bonus in RECENT_BONUS:
        if age <= within:
            return bonus
    return 0


def score_one(project, want, as_of, technologies):
    caps = as_set(project.get("capabilities"))
    techs = as_set(project.get("technologies"))
    domains = as_set(project.get("domains"))

    matched = sorted(caps & want["capabilities"])
    unmatched = sorted(want["capabilities"] - caps)
    tech_hits = sorted(techs & technologies)
    # Binary, not a count: multiplying a count rewards projects that happen to carry
    # more domain tags, which is a tagging artefact rather than a signal.
    domain = 1 if (domains & want["domains"]) else 0
    seniority = seniority_match(project.get("seniority"), want["seniority"])
    strength = project.get("strength") or 0
    recent = recency_bonus(project, as_of)

    total = (len(matched) * 3 + len(tech_hits) * 2 + domain * 2
             + seniority * 2 + strength + recent)
    return {
        "score": total, "matched": matched, "unmatched": unmatched,
        "tech": tech_hits, "domain": domain, "seniority": seniority,
        "strength": strength, "recency": recent,
        "want_caps": len(want["capabilities"]), "want_tech": len(technologies),
    }


def read_json(path, label):
    """A JSON document, or None with the reason already printed."""
    if not os.path.exists(path):
        print(f"{label} not found: {path}")
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as error:
        print(f"{label} is not valid JSON: {error}")
        return None


def requirements(posting, include_implicit):
    """The scored axes, read from the posting's own requirement objects.

    `value` is the vocabulary term the score runs on, never `label`: the resume
    mirrors the posting's wording, the ranking matches on the vocabulary term, and
    conflating them scores a synonym as absent evidence.
    """
    capabilities, technologies = set(), set()
    dropped, unknown = 0, set()
    for requirement in posting.get("requirements") or []:
        if not isinstance(requirement, dict):
            continue
        necessity = requirement.get("necessity")
        necessity = LEGACY_NECESSITY.get(necessity, necessity)
        if necessity not in KNOWN_NECESSITY:
            unknown.add(str(necessity))
        if necessity not in SCORED_NECESSITY and not include_implicit:
            dropped += 1
            continue
        value = requirement.get("value")
        if not value:
            continue
        if requirement.get("kind") == "capability":
            capabilities.add(str(value).strip())
        elif requirement.get("kind") == "technology":
            technologies.add(str(value).strip())
    role = posting.get("role") or {}
    return {
        "capabilities": capabilities,
        "technologies": technologies,
        "domains": as_set(role.get("domains")),
        "seniority": role.get("seniority"),
        "dropped_implicit": dropped,
        "unknown_necessity": sorted(unknown),
    }


def read_projects(record):
    """[(label, project)] for every project in the record.

    Projects are a root array in URS; `engagements[].projects` holds ids that point
    back at them. The selection keys - strength, seniority, domains, capabilities,
    technologies - live only on Project, which is why this is the unit that ranks.
    """
    out = []
    for project in record.get("projects") or []:
        if not isinstance(project, dict):
            continue
        label = project.get("title") or project.get("id") or "(untitled)"
        out.append((label, project))
    return out


def render_table(rows, markdown):
    header = ("rank", "score", "project", "cap", "tech", "dom", "sen", "str", "rec")
    body = []
    for i, (name, r) in enumerate(rows, 1):
        body.append((
            str(i), f"{r['score']:.1f}", name,
            f"{len(r['matched'])}/{r['want_caps']}" if r["want_caps"] else "-",
            f"{len(r['tech'])}/{r['want_tech']}" if r["want_tech"] else "-",
            "yes" if r["domain"] else "no",
            f"{r['seniority']:.2f}", str(r["strength"]), f"+{r['recency']}",
        ))
    if markdown:
        yield "| " + " | ".join(header) + " |"
        yield "|" + "|".join("---" for _ in header) + "|"
        for row in body:
            yield "| " + " | ".join(row) + " |"
        return
    widths = [max(len(h), *(len(row[i]) for row in body)) if body else len(h)
              for i, h in enumerate(header)]
    fmt = "  ".join(f"{{:{'<' if i == 2 else '>'}{w}}}" for i, w in enumerate(widths))
    yield fmt.format(*header)
    for row in body:
        yield fmt.format(*row)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Rank a URS record's projects against a UJD posting.")
    ap.add_argument("record", help="the URS career record, resume-generation/record.json")
    ap.add_argument("posting", help="the UJD posting, tailoring/targets/<slug>.posting.json")
    ap.add_argument("--markdown", action="store_true",
                    help="emit the ranked table as Markdown")
    ap.add_argument("--as-of", type=int, default=datetime.date.today().year,
                    help="year the recency bonus is measured from")
    ap.add_argument("--include-implicit", action="store_true",
                    help="score requirements the posting never stated; the fact is "
                         "printed, because an inference that moves a x3 term is an "
                         "invented requirement")
    ap.add_argument("--assume-technologies", default="",
                    help="comma-separated stack to score against when the posting "
                         "names none; the assumption is labelled in the output")
    a = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    record = read_json(a.record, "record")
    if record is None:
        return 2
    posting = read_json(a.posting, "posting")
    if posting is None:
        return 2

    want = requirements(posting, a.include_implicit)
    projects = read_projects(record)
    notes, warns = [], []

    technologies = want["technologies"]
    assumed = as_set([t for t in a.assume_technologies.split(",") if t.strip()])
    if assumed:
        if technologies:
            warns.append("--assume-technologies ignored: the posting already names "
                         "technology requirements")
        else:
            technologies = assumed
            notes.append(f"technologies ASSUMED, not from the posting: "
                         f"{', '.join(sorted(assumed))} - the posting named none, so "
                         f"this is your inference and it moves a x2 term")
    elif not technologies:
        notes.append("the posting names no technologies - the technology term is inert "
                     "for every project, so the ranking rests on capabilities, domain "
                     "and seniority. Pass --assume-technologies to explore an implied "
                     "stack rather than writing one into the posting")

    if want["unknown_necessity"]:
        warns.append("necessity value(s) this scorer does not know: %s - each one's "
                     "requirement was treated as implicit and dropped. The vocabulary is "
                     "required | preferred | implicit."
                     % ", ".join(want["unknown_necessity"]))

    if want["dropped_implicit"]:
        notes.append(f"{want['dropped_implicit']} implicit requirement(s) excluded - the "
                     f"posting never stated them. Pass --include-implicit to score them, "
                     f"which makes your inference part of the ranking")
    elif a.include_implicit:
        notes.append("--include-implicit: requirements the posting never stated are "
                     "part of this ranking")

    if not want["capabilities"]:
        warns.append("the posting names no capability requirements - the primary axis "
                     "is empty and this ranking means very little")

    # A capability no project carries is either absent evidence or an under-tagged
    # project, and the two need opposite responses. Naming it here beats leaving it
    # to be noticed in the per-project lists below.
    everywhere = set()
    for _, project in projects:
        everywhere |= as_set(project.get("capabilities"))
    missing = sorted(want["capabilities"] - everywhere)
    for capability in missing:
        near = near_terms(capability, everywhere)
        hint = ""
        if near:
            # The two responses this warning could not previously distinguish. A near
            # miss is almost always the posting's term and the bundle's term for one
            # thing - `event-streaming-architecture` against `event-driven-architecture`
            # - which is a tagging job, not missing evidence.
            hint = (f"; the record carries {', '.join(repr(n) for n in near)}"
                    f" - if that is the same thing, tag the project with"
                    f" {capability!r} rather than renaming the requirement")
        warns.append(f"required capability {capability!r} appears on no project in the "
                     f"record - it scores zero everywhere, which looks identical to "
                     f"absent evidence{hint}")

    # Every requirement missing its term means the ranking below was decided entirely
    # by strength, recency and seniority. That can still order the projects correctly,
    # which is exactly why it needs saying: the column of zeroes looks like a verdict
    # on the evidence, and it is a verdict on the vocabulary.
    if want["capabilities"] and not (want["capabilities"] & everywhere):
        warns.append(f"none of the {len(want['capabilities'])} required capabilities "
                     f"matches any term in the record, so capability scoring "
                     f"contributed nothing to this ranking - read the order as "
                     f"strength and recency alone until the tagging is reconciled")

    title = (posting.get("posting") or {}).get("title") or ""
    organization = (posting.get("organization") or {}).get("name") or ""
    label = " - ".join(part for part in (organization, title) if part)
    print(f"posting: {label or os.path.basename(a.posting)}   ({a.posting})")
    print(f"requirements: {len(want['capabilities'])} capabilities, "
          f"{len(technologies)} technologies, "
          f"domains {', '.join(sorted(want['domains'])) or 'none'}, "
          f"seniority {want['seniority'] or 'unspecified'}")
    print(f"projects scored: {len(projects)}   recency measured from {a.as_of}")
    for note in notes:
        print(f"\n  NOTE  {note}")
    for warning in warns:
        print(f"\n  WARN  {warning}")

    if not projects:
        print(f"\nnothing to score - no projects[] in {a.record}. The selection keys "
              f"live on Project, so a record without them cannot be ranked.")
        return 1

    scored = [(name, score_one(project, want, a.as_of, technologies))
              for name, project in projects]
    scored.sort(key=lambda pair: (-pair[1]["score"], pair[0]))

    print()
    for line in render_table(scored, a.markdown):
        print(line)

    print("\ncapability match per project:")
    for name, r in scored:
        print(f"  {name}")
        print(f"    matched:   {', '.join(r['matched']) or '(none)'}")
        print(f"    unmatched: {', '.join(r['unmatched']) or '(none)'}")
    print("\nAn unmatched value is either evidence that is genuinely absent or a project "
          "that is\nunder-tagged. Those need different responses, and only the person "
          "whose work it was knows\nwhich it is - so show them this before writing "
          "anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
