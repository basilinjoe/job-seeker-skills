#!/usr/bin/env python3
"""Score every project in a bundle against a job target, per references/mode-tailor.md

Usage: python3 score_projects.py <bundle-path> <tailoring/targets/foo.md>
                                 [--markdown] [--as-of YEAR]
                                 [--assume-technologies a,b,c]

On Windows use `python` or `py -3` in place of `python3`.

    score =  capability_overlap x 3     # primary axis, a count
           + technology_overlap  x 2    # a count
           + domain_match        x 2    # binary
           + seniority_match     x 2    # 0.0-1.0, see SENIORITY below
           + strength                   # 1-5
           + recency_bonus              # +2 within 3 years, +1 within 6

Requirements come from the target's own frontmatter, so the document a human reviews
is the document that drove the ranking.

Requires: pyyaml  (pip install pyyaml)
Exit 0 = scored. Exit 1 = nothing to score. Exit 2 = usage error.
"""
import argparse
import datetime
import os
import re
import sys

try:
    import yaml
except ImportError:
    print("score_projects.py needs pyyaml:  pip install pyyaml")
    sys.exit(2)

# Most senior first. Ranks are positions in this list, counted from the bottom.
SENIORITY = ["architecture-ownership", "product-ownership", "platform-design",
             "team-leadership", "technical-ownership", "hands-on-senior",
             "hands-on", "junior"]
RANK = {name: len(SENIORITY) - 1 - i for i, name in enumerate(SENIORITY)}

LIST_ITEM = re.compile(r"^\s*[-*]\s+")
RECENT_BONUS = ((3, 2), (6, 1))


def frontmatter(path):
    """The YAML block at the top of a concept file, as a dict. {} if there is none."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 3)
    if end == -1:
        return {}
    meta = yaml.safe_load(text[4:end])
    return meta if isinstance(meta, dict) else {}


def as_set(value):
    """Frontmatter lists are lists, but a single value written bare is a string."""
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


def recency_bonus(recency, as_of):
    try:
        age = as_of - int(recency)
    except (TypeError, ValueError):
        return 0
    for within, bonus in RECENT_BONUS:
        if age <= within:
            return bonus
    return 0


def score_one(project, target, as_of, technologies):
    caps = as_set(project.get("capabilities"))
    techs = as_set(project.get("technologies"))
    domains = as_set(project.get("domains"))
    want_caps = as_set(target.get("required_capabilities"))

    matched = sorted(caps & want_caps)
    unmatched = sorted(want_caps - caps)
    tech_hits = sorted(techs & technologies)
    # Binary, not a count: multiplying a count rewards concepts that happen to carry
    # more domain tags, which is a tagging artefact rather than a signal.
    domain = 1 if (domains & as_set(target.get("domains"))) else 0
    seniority = seniority_match(project.get("seniority"), target.get("seniority_sought"))
    strength = project.get("strength") or 0
    recent = recency_bonus(project.get("recency"), as_of)

    total = (len(matched) * 3 + len(tech_hits) * 2 + domain * 2
             + seniority * 2 + strength + recent)
    return {
        "score": total, "matched": matched, "unmatched": unmatched,
        "tech": tech_hits, "domain": domain, "seniority": seniority,
        "strength": strength, "recency": recent,
        "want_caps": len(want_caps), "want_tech": len(technologies),
    }


def read_vocabulary(bundle):
    """Capability values from framework/capability-vocabulary.md. Only list items count."""
    for name in ("capability-vocabulary.md", "capability_vocabulary.md"):
        path = os.path.join(bundle, "framework", name)
        if os.path.exists(path):
            break
    else:
        return set()
    vocab, fenced = set(), False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if not fenced and LIST_ITEM.match(line):
                vocab.update(re.findall(r"`([a-z0-9-]+)`", line))
    return vocab


def read_projects(bundle):
    """[(name, frontmatter)] for every Project concept, index files excluded."""
    directory = os.path.join(bundle, "projects")
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".md") or name == "index.md":
            continue
        try:
            meta = frontmatter(os.path.join(directory, name))
        except yaml.YAMLError as e:
            print(f"  WARN  {name}: YAML parse error, skipped - {e}")
            continue
        if meta.get("type") == "Project":
            out.append((os.path.splitext(name)[0], meta))
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
        description="Rank a bundle's projects against a job target's frontmatter.")
    ap.add_argument("bundle")
    ap.add_argument("target")
    ap.add_argument("--markdown", action="store_true",
                    help="emit the ranked table as Markdown, to paste under "
                         "'# Evidence ranking' in the target file")
    ap.add_argument("--as-of", type=int, default=datetime.date.today().year,
                    help="year the recency bonus is measured from")
    ap.add_argument("--assume-technologies", default="",
                    help="comma-separated stack to score against when the posting "
                         "names none; the assumption is labelled in the output")
    a = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not os.path.isdir(a.bundle):
        print(f"bundle not found: {a.bundle}")
        return 2
    if not os.path.exists(a.target):
        print(f"target not found: {a.target}")
        return 2
    try:
        target = frontmatter(a.target)
    except yaml.YAMLError as e:
        print(f"target frontmatter is not valid YAML: {e}")
        return 2
    if not target:
        print(f"no frontmatter in {a.target} - see references/target-template.md")
        return 2

    projects = read_projects(a.bundle)
    notes, warns = [], []

    want_caps = as_set(target.get("required_capabilities"))
    technologies = as_set(target.get("required_technologies"))
    assumed = as_set([t for t in a.assume_technologies.split(",") if t.strip()])
    if assumed:
        if technologies:
            warns.append("--assume-technologies ignored: the target already names "
                         "required_technologies")
        else:
            technologies = assumed
            notes.append(f"technologies ASSUMED, not from the posting: "
                         f"{', '.join(sorted(assumed))} - the posting named none, so "
                         f"this is your inference and it moves a x2 term")
    elif not technologies:
        notes.append("the posting names no technologies - the technology term is inert "
                     "for every project, so the ranking rests on capabilities, domain "
                     "and seniority. Pass --assume-technologies to explore an implied "
                     "stack rather than writing one into the target file")

    vocab = read_vocabulary(a.bundle)
    for capability in sorted(want_caps):
        if vocab and capability not in vocab:
            warns.append(f"required capability {capability!r} is not in "
                         f"framework/capability-vocabulary.md - matching is exact-string, "
                         f"so a typo scores zero on every project and is invisible")
    if not want_caps:
        warns.append("the target names no required_capabilities - the primary axis is "
                     "empty and this ranking means very little")

    label = " - ".join(str(target[k]) for k in ("company", "role") if target.get(k))
    print(f"target: {label or os.path.basename(a.target)}   ({a.target})")
    print(f"requirements: {len(want_caps)} capabilities, {len(technologies)} technologies, "
          f"domains {', '.join(sorted(as_set(target.get('domains')))) or 'none'}, "
          f"seniority {target.get('seniority_sought') or 'unspecified'}")
    print(f"projects scored: {len(projects)}   recency measured from {a.as_of}")
    for n in notes:
        print(f"\n  NOTE  {n}")
    for w in warns:
        print(f"\n  WARN  {w}")

    if not projects:
        print(f"\nnothing to score - no Project concepts in {a.bundle}/projects/")
        return 1

    scored = [(name, score_one(meta, target, a.as_of, technologies))
              for name, meta in projects]
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
