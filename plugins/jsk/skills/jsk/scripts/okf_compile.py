#!/usr/bin/env python3
"""okf_compile - build the record from the bundle, deterministically.

Usage: python3 okf_compile.py BUNDLE [--dump-record FILE|-] [--quiet]

The bundle is the source of truth. This reads its concepts and returns the record
that `urs/resolve.py` already consumes - the same dict it used to be handed as a
`record.json` written by a model.

Nothing is written unless --dump-record asks for it, and what it writes is for
reading, never for editing: the next compile overwrites whatever you changed. A
record on disk is a cache, and a cache of a file you can regenerate in under a
second is a liability rather than an asset.

    from okf_compile import load
    doc = load(bundle_root)          # -> the dict resolve.build() takes

Why this is a script and not an agent: every field here is a frontmatter key or a
table cell. A model transcribing them adds no judgement, and a transcription that
can drift is what checksums, conformance levels and a reconcile pass all existed to
police. None of that is needed once the mapping is mechanical.

What is NOT compiled: achievement prose. Bullets are written, not derived, so they
live in their concept's `# Bullets` block with their own provenance and are read
from there - see `references/bundle-spec.md`.

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = compiled. Exit 1 = the bundle is missing something required. Exit 2 = called wrong.

Needs pyyaml, like every other script that reads the bundle rather than a document.
"""
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    # Same message as validate_bundle.py: a traceback here reads as a broken install
    # rather than a missing package.
    print("okf_compile.py needs pyyaml:  pip install pyyaml")
    sys.exit(2)

SKIP_DIRS = {".git", "node_modules", "out", "resume-archive", ".build"}
# Concept types that carry no resume content. Listed rather than inferred so that a
# new type is a deliberate decision here, not silently dropped.
NON_CONTENT = {"Index", "Log", "Guide", "Vocabulary", "Rule Set", "Schema", "Template",
               "Decision Log", "Open Questions", "Source Document", "Source Interview",
               "Application", "Positioning", "Career Progression", "Preference", "Method"}

DATE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


class Problem(Exception):
    """Something the bundle must say and does not."""


def read_frontmatter(text):
    """The parser pipeline.py uses, so a concept reads the same way everywhere."""
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None, text
    end = text.find("\n---\n", 3)
    if end == -1:
        end = text.find("\r\n---\r\n", 3)
        if end == -1:
            return None, text
        head, body = text[4:end], text[end + 7:]
    else:
        head, body = text[4:end], text[end + 5:]
    try:
        meta = yaml.safe_load(head)
    except Exception:
        return None, body
    return (meta if isinstance(meta, dict) else None), body


def concepts(root):
    """Every concept in the bundle, as (stem, type, meta, body)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(filenames):
            if not name.endswith(".md") or name == "index.md":
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as fh:
                meta, body = read_frontmatter(fh.read())
            if not meta or not meta.get("type"):
                continue
            out.append((name[:-3], meta.get("type"), meta, body))
    return out


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def ident(meta, stem, prefix):
    """The concept's id: what it declares, else derived from its filename.

    Derivation keeps ids stable without anyone maintaining them, and the override
    exists so a bundle that already published an id can keep it.
    """
    return str(meta.get("id") or f"{prefix}_{slug(stem)}")


def date(value, where):
    """A URS date. Precision is read from what was written, never assumed."""
    if value is None:
        return None
    m = DATE.match(str(value).strip())
    if not m:
        raise Problem(f"{where}: {value!r} is not a date - write 2019, 2019-04 or 2019-04-01")
    year, month, day = m.groups()
    if day:
        return {"value": f"{year}-{month}-{day}", "precision": "day"}
    if month:
        return {"value": f"{year}-{month}", "precision": "month"}
    return {"value": year, "precision": "year"}


def period(meta, where):
    """start/end/state as URS wants them, with ongoing and ended kept distinct."""
    state = str(meta.get("state") or ("ongoing" if not meta.get("end") else "ended"))
    out = {"state": state}
    start = date(meta.get("start"), f"{where}.start")
    if start:
        out["start"] = start
    end = date(meta.get("end"), f"{where}.end")
    if end and state == "ongoing":
        raise Problem(f"{where}: state is ongoing but an end date is set - one of them is wrong")
    if end:
        out["end"] = end
    if state == "ended" and not end:
        raise Problem(f"{where}: state is ended but no end date is set")
    return out


def provenance(meta):
    return {"status": str(meta.get("status") or "needs-verification")}


def metrics_table(root):
    """achievements/metrics.md, one row per verified number.

    Keyed by a slug of the metric name so a bullet can name the number it rests on
    rather than restating it, which is what stops a rewritten clause inflating it.
    """
    path = os.path.join(root, "achievements", "metrics.md")
    if not os.path.exists(path):
        return {}
    rows = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith("|") or "---" in line[:8]:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3 or not cells[0] or cells[0].lower() == "metric":
                continue
            name, value = cells[0], cells[1]
            link = LINK.search(cells[2])
            target = link.group(2) if link else cells[2]
            rows[slug(name)] = {
                "id": f"met_{slug(name)}",
                "label": name,
                "value": re.sub(r"\*\*", "", value),
                "project": os.path.basename(str(target)).replace(".md", ""),
                "source": cells[3] if len(cells) > 3 else "",
            }
    return rows


def blocks(body, heading, keys):
    """The `- item` entries under one heading, each with its own `key: value` lines.

    Authored content - bullets and skills - reads this way. It is the one shape in the
    bundle a script cannot derive, so it is written down plainly and parsed the same way
    wherever it appears.
    """
    out = []
    match = re.search(r"^#+\s*%s\s*$(.*?)(?=^#\s|\Z)" % heading, body, re.M | re.S)
    if not match:
        return out
    for block in re.split(r"^\s*-\s+", match.group(1), flags=re.M)[1:]:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        fields, text = {}, []
        for line in lines:
            kv = re.match(r"^(%s)\s*:\s*(.+)$" % "|".join(keys), line)
            if kv:
                fields[kv.group(1)] = kv.group(2).strip()
            else:
                text.append(line)
        if text:
            out.append((" ".join(text), fields))
    return out


def bullets(body, where, metrics):
    """A concept's `# Bullets` block: written, never derived.

    Each item carries its own provenance, because a bullet authored for a posting is
    `inferred` until the person has confirmed it - and `provenance_floor` on a view is
    what stops an unconfirmed one rendering.
    """
    out = []
    for n, (text, fields) in enumerate(
            blocks(body, "Bullets", ("status", "metric", "for", "id")), 1):
        item = {
            "id": fields.get("id") or f"ach_{slug(where)}_{n}",
            "text": text,
            "provenance": {"status": fields.get("status") or "inferred"},
        }
        key = slug(fields["metric"]) if fields.get("metric") else None
        if key and key in metrics:
            item["metrics"] = [{"id": metrics[key]["id"],
                                "label": metrics[key]["label"],
                                "value": metrics[key]["value"]}]
        elif key:
            raise Problem(f"{where}: bullet names metric {fields['metric']!r}, "
                          f"which is not a row in achievements/metrics.md")
        out.append(item)
    return out


def build_organizations(items):
    out = []
    for stem, meta, _ in items:
        out.append({k: v for k, v in {
            "id": ident(meta, stem, "org"),
            "name": meta.get("title") or stem,
            "description": meta.get("description"),
            "industry": meta.get("industry"),
            "sector": meta.get("sector"),
            "size": meta.get("size"),
            "url": meta.get("url"),
        }.items() if v is not None})
    return out


def build_engagements(roles, orgs_by_stem):
    """Roles grouped by organisation, each becoming a position in one history.

    The grouping is what puts a promotion on the resume as progression inside one
    employer rather than as two unrelated jobs.
    """
    groups = {}
    for stem, meta, _ in roles:
        org = meta.get("organisation") or meta.get("organization")
        if not org:
            raise Problem(f"roles/{stem}.md: no organisation - see bundle-spec.md, "
                          f"'The relational keys'")
        if org not in orgs_by_stem:
            raise Problem(f"roles/{stem}.md: organisation {org!r} has no concept in "
                          f"organisations/ - a role cannot be for a company the bundle "
                          f"does not know")
        groups.setdefault(org, []).append((stem, meta))

    out = []
    for org, members in groups.items():
        members.sort(key=lambda m: str(m[1].get("start") or ""))
        positions = []
        org_name = str(orgs_by_stem[org][1].get("title") or "")
        for stem, meta in members:
            title = str(meta.get("title") or stem).strip().strip('"')
            # A bundle often writes the employer into the role title. The engagement
            # already names the organisation, so repeating it renders as "Lead Engineer -
            # Experion" under a heading that says Experion. Stripped only when it matches
            # the organisation this role is already known to belong to - a comparison
            # against a known value, not a guess at what a dash means.
            if org_name and title.lower().endswith(" - " + org_name.lower()):
                title = title[: -(len(org_name) + 3)].strip()
            pos = {
                "id": ident(meta, stem, "pos"),
                "title": title,
                "period": period(meta, f"roles/{stem}.md"),
            }
            if meta.get("functional_title"):
                pos["functional_title"] = meta["functional_title"]
            if meta.get("seniority"):
                pos["seniority"] = meta["seniority"]
            pos["change"] = meta.get("change") or ("hire" if not positions else "promotion")
            positions.append(pos)
        span = {"state": positions[-1]["period"]["state"]}
        if positions[0]["period"].get("start"):
            span["start"] = positions[0]["period"]["start"]
        if positions[-1]["period"].get("end"):
            span["end"] = positions[-1]["period"]["end"]
        eng_meta = orgs_by_stem[org][1]
        out.append({k: v for k, v in {
            "id": f"eng_{slug(org)}",
            "organization": ident(eng_meta, org, "org"),
            "period": span,
            "location": eng_meta.get("location"),
            "employment": eng_meta.get("employment"),
            "positions": positions,
            "achievements": [],
        }.items() if v is not None})
    return out


def build_projects(items, roles_by_stem, metrics):
    out = []
    for stem, meta, body in items:
        role = meta.get("role")
        if role and role not in roles_by_stem:
            raise Problem(f"projects/{stem}.md: role {role!r} has no concept in roles/")
        entry = {
            "id": ident(meta, stem, "prj"),
            "title": meta.get("title") or stem,
            "description": meta.get("description"),
            "provenance": provenance(meta),
        }
        if role:
            org = roles_by_stem[role].get("organisation") or roles_by_stem[role].get("organization")
            entry["engagement"] = f"eng_{slug(org)}"
        for key in ("strength", "seniority", "domains", "capabilities", "technologies", "url"):
            if meta.get(key) is not None:
                entry[key] = meta[key]
        if meta.get("recency"):
            entry["period"] = {"state": "ended", "end": date(meta["recency"], f"projects/{stem}.md")}
        entry["achievements"] = bullets(body, f"projects/{stem}.md", metrics)
        out.append({k: v for k, v in entry.items() if v is not None})
    return out


def build_skills(items):
    """A Skill Set concept's `# Skills` block.

    Written, not derived, and deliberately so: naming a competency "C# / .NET" rather
    than "dotnet", and deciding that ASP.NET Core is an alias of it rather than a skill
    beside it, is editorial judgement. The project frontmatter's `capabilities` and
    `technologies` are the matching vocabulary and a different thing - they compare as
    exact strings, where these are read by a person.
    """
    out, seen = [], set()
    for stem, meta, body in items:
        for name, fields in blocks(body, "Skills", ("id", "category", "aliases", "last_used")):
            sid = fields.get("id") or f"skill_{slug(name)}"
            if sid in seen:
                continue
            seen.add(sid)
            entry = {"id": sid, "name": name}
            if fields.get("category"):
                entry["category"] = fields["category"]
            if fields.get("aliases"):
                entry["aliases"] = [a.strip() for a in fields["aliases"].split(",") if a.strip()]
            if fields.get("last_used"):
                entry["last_used"] = date(fields["last_used"], f"{stem}.md skill {sid}")
            out.append(entry)
    return out


def build_narratives(items):
    """Positioning concepts, and any summary authored beside them.

    A narrative is prose about the whole person rather than about one engagement, so it
    has no other concept to live in.
    """
    out = []
    for stem, meta, body in items:
        text = "\n".join(ln for ln in body.strip().splitlines()
                         if ln.strip() and not ln.startswith("#")).strip()
        if not text:
            continue
        entry = {
            "id": ident(meta, stem, "nar"),
            "text": text,
            "provenance": provenance(meta),
        }
        for key in ("kind", "audience"):
            if meta.get(key):
                entry[key] = meta[key]
        out.append(entry)
    return out


def simple(items, prefix, fields):
    out = []
    for stem, meta, _ in items:
        entry = {"id": ident(meta, stem, prefix), "provenance": provenance(meta)}
        for key in fields:
            if meta.get(key) is not None:
                entry[key] = meta[key]
        if meta.get("start") or meta.get("end"):
            entry["period"] = period(meta, f"{stem}.md")
        out.append(entry)
    return out


def load(root):
    """The bundle, as the record every downstream tool already reads."""
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise Problem(f"not a directory: {root}")
    by_type = {}
    for stem, ctype, meta, body in concepts(root):
        by_type.setdefault(ctype, []).append((stem, meta, body))

    metrics = metrics_table(root)
    orgs_by_stem = {stem: (stem, meta) for stem, meta, _ in by_type.get("Organisation", [])}
    roles_by_stem = {stem: meta for stem, meta, _ in by_type.get("Role", [])}

    person_items = by_type.get("Person", [])
    person = person_items[0][1] if person_items else {}

    doc = {
        "urs": "1.0.0",
        "meta": {
            "id": f"urn:urs:{slug(os.path.basename(root))}",
            "lang": person.get("lang", "en"),
            "generator": "okf_compile",
            "bundle": os.path.basename(root),
        },
        "person": {k: v for k, v in {
            "name": person.get("name"),
            "headline": person.get("headline"),
            "location": person.get("location"),
            "contacts": person.get("contacts"),
        }.items() if v is not None},
        "organizations": build_organizations(by_type.get("Organisation", [])),
        "engagements": build_engagements(by_type.get("Role", []), orgs_by_stem),
        "projects": build_projects(by_type.get("Project", []), roles_by_stem, metrics),
        "education": simple(by_type.get("Education", []), "edu",
                            ("institution", "qualification", "level", "field", "location")),
        "credentials": simple(by_type.get("Certification Status", []), "cred",
                              ("name", "issuer", "expires")),
        "skills": build_skills(by_type.get("Skill Set", [])),
        "narratives": build_narratives(by_type.get("Positioning", [])),
        "views": [],
    }
    for key in ("languages", "work_authorization", "availability"):
        if person.get(key) is not None:
            doc[key] = person[key]
    return doc


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: okf_compile.py BUNDLE [--dump-record FILE|-]")
        return 2
    quiet = "--quiet" in argv
    try:
        doc = load(args[0])
    except Problem as exc:
        print(f"FAIL  {exc}")
        return 1

    dump = None
    if "--dump-record" in argv:
        i = argv.index("--dump-record")
        dump = argv[i + 1] if len(argv) > i + 1 else "-"
    if dump == "-":
        json.dump(doc, sys.stdout, indent=2, ensure_ascii=False)
        return 0
    if dump:
        with open(dump, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
        if not quiet:
            print(f"wrote {dump}  (a cache - edit the concept, not this)")
    if not quiet:
        counts = ", ".join(f"{len(v)} {k}" for k, v in doc.items()
                           if isinstance(v, list) and v)
        print(f"compiled {os.path.basename(os.path.abspath(args[0]))}: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
