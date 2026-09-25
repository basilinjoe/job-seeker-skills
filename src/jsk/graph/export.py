"""career/kb.ttl as a draft resume.json: the parts of a record that are copied, copied
by the program.

Hand transcription is where record defects came from - a number from a replaced version,
a bullet marked confirmed that the career holds as inferred, a bullet under the wrong
employer. Here every id, provenance, metric and period comes out of kb.ttl as it stands,
so the draft passes the record gate and the claims gate before anyone touches it; the
author retunes the words and the view, and the gates check what changed.

What `select` narrows is the experience: a project brings its bullets, a bullet brings
only itself (and its project), a role brings itself. An employer comes with every role
held there, so a promotion history is never cut in half. The rest - the person, rights to
work, languages, skills, education, credentials, the positioning - comes across whole:
it is short, and the view decides what renders.
"""
import difflib
import os

from ..paths import SCHEMA_DIR
from . import ontology as O
from .writer import Subjects

URS_VERSION = "1.0.0"
CONTACTS = ("email", "phone", "linkedin", "github", "website")
# kb.ttl's language scheme is "reported"; URS spells the same thing "self-reported".
SCHEME = {"reported": "self-reported"}
SELECTS = ("Project", "Achievement", "Position")


class ExportError(Exception):
    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


def local(iri):
    return iri[len(O.K):]


def enum(value):
    return value[len(O.J):] if value and value.startswith(O.J) else value


def number(term):
    text = term.value
    if term.datatype.value == O.XSD + "integer":
        return int(text)
    n = float(text)
    return int(n) if n.is_integer() else n


def instant(value):
    if not value:
        return None
    precision = {4: "year", 7: "month", 10: "day"}.get(len(value), "day")
    return {"value": value, "precision": precision}


def period(start, end, state):
    out = {}
    if start:
        out["start"] = instant(start)
    if end:
        out["end"] = instant(end)
    out["state"] = state
    return out


def provenance(sub, s):
    return {"status": enum(sub.get(s, "provenance"))}


class Career:
    def __init__(self, triples):
        self.sub = Subjects(triples)

    def live(self, name):
        """Subjects of a class, retired ones left out."""
        return [s for s in self.sub.of(name) if not self.sub.get(s, "retired")]

    def get(self, s, pred, default=None):
        return self.sub.get(s, pred, default)

    def all(self, s, pred):
        return self.sub.props.get(s, {}).get(pred, [])


def chosen(career, select):
    """(projects, bullets, roles) to export: sets of iris, or None for all of them."""
    if not select:
        return None
    projects, bullets, roles = set(), set(), set()
    known = set(career.sub.cls)
    for text in select:
        iri = O.K + text.removeprefix("k:")
        if iri not in known:
            near = difflib.get_close_matches(iri, sorted(known), n=1)
            raise ExportError(f"{text} is not in career/kb.ttl",
                              f"did you mean {local(near[0])}?" if near
                              else "`jsk kb view` lists the ids")
        cls = career.sub.cls[iri].name
        if cls == "OpenSource":
            # URS has no open-source section. On the ElevenLabs run the refusal below
            # sent the author to rewrite a confirmed bullet around the repo's URL.
            raise ExportError(f"{text} is open source ({career.get(iri, 'url')}), and a "
                              "resume.json has no section for it",
                              "the person's contacts carry their github profile already; the "
                              "repo link goes in a bullet's words only if the person confirms "
                              "that wording - a changed bullet drops to inferred")
        if cls not in SELECTS:
            raise ExportError(f"{text} is a {cls}, and selects nothing: export selects "
                              "projects (prj_), bullets (ach_) and roles (pos_)",
                              "select the bullets that cite it, or their project")
        if career.get(iri, "retired"):
            raise ExportError(f"{text} was retired on {career.get(iri, 'retired')} "
                              f"({career.get(iri, 'reason', 'no reason given')})",
                              "leave it out: a retired entry does not belong on a resume")
        {"Project": projects, "Achievement": bullets, "Position": roles}[cls].add(iri)
    return projects, bullets, roles


def gate_failures(store, doc, today=None):
    """What the record gate and the claims gate refuse in a draft exactly as exported -
    each a line naming the bullet. Nothing an author wrote is in it yet, so every one
    is a fault in kb.ttl: a number no metric holds, a number its metric no longer does.
    On the Everforth run the author found four of these one gate at a time, three
    changesets deep; every later application selecting those bullets would again."""
    from ..gates import claims, validate_urs

    out = list(validate_urs.check_doc(doc).fails)
    # findings(), not check(): check() hands back a Report's strings, and `.focus` on
    # one raised AttributeError on every draft the claims gate failed - the drafts
    # this function exists to name.
    out += [f"{f.focus} - {f.detail}" for f in claims.findings(doc, store, today=today)
            if f.severity == "FAIL"]
    return out


def urs(store, select=None, today=None, selection=None, notes=None):
    """The draft record, as a dict. Raises ExportError for a selection it cannot honour.

    `selection` is select.py's choice for one posting (or refresh's, the record's own):
    its projects and bullets, in its order, are the experience, and `select` adds only
    roles. What was left out on the way - an alias no project holds - is appended to
    `notes`, as lines to print."""
    from ..gates import claims
    from . import record as R

    career = Career(store.graph(R.KB))
    picked = chosen(career, select)
    bullets_of = {}
    for a in career.live("Achievement"):
        bullets_of.setdefault(career.get(a, "project"), []).append(a)
    for p in bullets_of:
        bullets_of[p].sort(key=lambda a: (int(career.get(a, "rank", 0)), a))

    projects = [p for p in career.live("Project")]
    if selection is not None:
        projects = list(selection.projects)
        bullets_of = {p: list(bs) for p, bs in selection.bullets.items()}
        roles = picked[2] if picked is not None else set()
    elif picked is not None:
        want, bullets, roles = picked
        with_bullets = {career.get(a, "project") for a in bullets}
        projects = [p for p in projects if p in want or p in with_bullets]
        for p in projects:
            mine = [a for a in bullets_of.get(p, []) if a in bullets]
            if mine:                                   # a bullet named narrows its project
                bullets_of[p] = mine
    else:
        roles = set()
    roles = roles | {career.get(p, "position") for p in projects if career.get(p, "position")}
    orgs = {career.get(r, "organisation") for r in roles}
    if picked is None and selection is None:
        orgs |= {career.get(r, "organisation") for r in career.live("Position")}
    # An employer comes with every role held there, so a promotion history stays whole.
    roles = {r for r in career.live("Position") if career.get(r, "organisation") in orgs}

    engagements = engagement_list(career, roles, projects)
    doc = {
        "urs": URS_VERSION,
        "meta": {"lang": "en", "updated": (today.isoformat() if today else None),
                 "generator": "jsk kb export"},
        "person": person(career),
    }
    if doc["meta"]["updated"] is None:
        del doc["meta"]["updated"]
    add(doc, "work_authorization", [authorization(career, s)
                                    for s in career.live("WorkAuthorization")])
    add(doc, "languages", [language(career, s) for s in career.live("Language")])
    add(doc, "organizations", [organisation(career, o) for o in sorted(orgs)])
    add(doc, "engagements", [e for e, _ in engagements])
    add(doc, "education", [education(career, s) for s in career.live("Education")])
    add(doc, "credentials", [credential(career, s) for s in career.live("Credential")])
    shown = [p for _, ps in engagements for p in ps] + \
        [p for p in projects if p not in {q for _, ps in engagements for q in ps}]
    add(doc, "projects", [project(career, p, bullets_of.get(p, []), engagements) for p in shown])
    add(doc, "skills", skills(career, claims.Career(store), notes))
    narrative = positioning(career)
    add(doc, "narratives", [narrative] if narrative else [])
    doc["views"] = [view(career, doc, engagements, narrative, selection)]
    return doc


def add(doc, key, items):
    if items:
        doc[key] = items


def person(career):
    s = O.K + "person"
    name = {"full": career.get(s, "fullName", "")}
    for pred, key in (("givenName", "given"), ("familyName", "family")):
        if career.get(s, pred):
            name[key] = career.get(s, pred)
    out = {"name": name}
    if career.get(s, "headline"):
        out["headline"] = career.get(s, "headline")
    location = {k: career.get(s, p) for p, k in (("city", "city"), ("region", "region"),
                                                ("country", "country")) if career.get(s, p)}
    if career.get(s, "workMode"):
        location["mode"] = enum(career.get(s, "workMode"))
    if location:
        out["location"] = location
    primary = career.get(s, "primary")
    contacts = []
    for kind in CONTACTS:
        for term in sorted(career.all(s, kind), key=lambda t: t.value):
            c = {"kind": kind, "value": term.value}
            if term.value == primary:
                c["primary"] = True
            contacts.append(c)
    if contacts:
        out["contacts"] = contacts
    return out


def authorization(career, s):
    out = {"jurisdiction": career.get(s, "jurisdiction"), "kind": enum(career.get(s, "kind")),
           "status": enum(career.get(s, "authorization"))}
    if career.get(s, "validUntil"):
        out["expires"] = instant(career.get(s, "validUntil"))
    out["provenance"] = provenance(career.sub, s)
    return out


def language(career, s):
    out = {"language": career.get(s, "language")}
    native = career.get(s, "native")
    if native is not None:
        out["native"] = native == "true"
    if career.get(s, "scheme"):
        scheme = enum(career.get(s, "scheme"))
        out["scheme"] = SCHEME.get(scheme, scheme)
    if career.get(s, "level"):
        out["overall"] = career.get(s, "level")
    out["provenance"] = provenance(career.sub, s)
    return out


def organisation(career, o):
    return {"id": local(o), "name": career.get(o, "name"),
            "provenance": provenance(career.sub, o)}


def role_period(career, r):
    return period(career.get(r, "start"), career.get(r, "end"),
                  enum(career.get(r, "state")))


def latest_first(p):
    """Sort key: ongoing first, then the latest end, then the latest start."""
    end = p.get("end", {}).get("value") if p.get("state") != "ongoing" else "9999"
    return (end or "", p.get("start", {}).get("value", ""))


def engagement_list(career, roles, projects):
    """[(engagement, [project iris under it])]: one per employer and kind of work,
    latest first, its roles latest first."""
    groups = {}
    for r in roles:
        kind = enum(career.get(r, "engagementKind")) or "employment"
        groups.setdefault((career.get(r, "organisation"), kind), []).append(r)
    kinds = {}
    for org, kind in groups:
        kinds.setdefault(org, set()).add(kind)
    out = []
    for (org, kind), rs in groups.items():
        slug = local(org).removeprefix("org_")
        ident = f"eng_{slug}" if len(kinds[org]) == 1 else f"eng_{slug}_{kind.replace('-', '_')}"
        positions = []
        for r in rs:
            p = {"id": local(r), "title": career.get(r, "title")}
            if career.get(r, "functionalTitle"):
                p["functional_title"] = career.get(r, "functionalTitle")
            p["period"] = role_period(career, r)
            if career.get(r, "change"):
                p["change"] = enum(career.get(r, "change"))
            p["seniority"] = enum(career.get(r, "seniority"))
            p["provenance"] = provenance(career.sub, r)
            positions.append(p)
        positions.sort(key=lambda p: latest_first(p["period"]), reverse=True)
        periods = [p["period"] for p in positions]
        ongoing = any(p["state"] == "ongoing" for p in periods)
        ends = [p["end"]["value"] for p in periods if "end" in p]
        known = all(p["state"] != "unknown" for p in periods)
        start = min(p["start"]["value"] for p in periods)
        state = "ongoing" if ongoing else ("ended" if known and ends else "unknown")
        span = period(start, None if ongoing or not ends else max(ends), state)
        if state == "unknown":
            span.pop("end", None)
        under = [p for p in projects if career.get(p, "position") in rs]
        under.sort(key=lambda p: (-int(career.get(p, "recency", 0)), p))
        out.append(({"id": ident, "kind": kind, "organization": local(org), "period": span,
                     "positions": positions, "projects": [local(p) for p in under],
                     "achievements": []}, under))
    out.sort(key=lambda e: latest_first(e[0]["period"]), reverse=True)
    return out


def metric(career, m):
    """A cited metric as URS writes one: its current version, or None when every
    version has been replaced."""
    versions = [v for v in career.sub.of("MetricVersion")
                if career.get(v, "of") == m and not career.get(v, "validUntil")]
    if not versions:
        return None
    v = max(versions, key=lambda v: int(v.rsplit(".v", 1)[1]))
    unit = career.get(m, "unit")
    out = {"id": local(m)}
    if career.get(v, "kind"):
        out["kind"] = enum(career.get(v, "kind"))
    out["subject"] = career.get(m, "subject")

    def amount(pred):
        q = {"value": number(career.all(v, pred)[0])}
        if unit:
            q["unit"] = unit
        return q

    if career.all(v, "baseline"):
        out["baseline"] = amount("baseline")
    out["quantity"] = amount("value")
    upper, qualifier = career.all(v, "upper"), enum(career.get(v, "qualifier"))
    if upper or qualifier:
        # URS has no range or qualifier on a quantity: the number as the person stated it
        # rides beside it, and the record gate counts every numeral in it as recorded.
        out["value"] = O.stated(career.all(v, "value")[0].value,
                                upper[0].value if upper else None, qualifier)
    if career.get(m, "direction"):
        out["direction"] = enum(career.get(m, "direction"))
    out["confidence"] = enum(career.get(v, "confidence"))
    return out


def project(career, p, bullets, engagements):
    out = {"id": local(p), "name": career.get(p, "name")}
    for e, under in engagements:
        if p in under:
            out["engagement"] = e["id"]
            # The role the work was done in, so the renderer can put its bullets
            # under that role's line: without it the Experion draft credited all
            # six roles' work to the latest title. Written only when it is one of
            # this engagement's positions - the one thing the record gate checks.
            role = career.get(p, "position")
            if role and local(role) in {q["id"] for q in e["positions"]}:
                out["position"] = local(role)
    out["strength"] = int(career.get(p, "strength"))
    out["achievements"] = []
    for a in bullets:
        cited = sorted(m.value for m in career.all(a, "cites"))
        metrics = [x for x in (metric(career, m) for m in cited) if x]
        out["achievements"].append({"id": local(a), "text": career.get(a, "text"),
                                    "metrics": metrics, "provenance": provenance(career.sub, a)})
    out["provenance"] = provenance(career.sub, p)
    return out


def education(career, s):
    out = {"id": local(s), "institution": career.get(s, "institution")}
    if career.get(s, "level"):
        out["level"] = enum(career.get(s, "level"))
    out["qualification"] = career.get(s, "qualification")
    if career.get(s, "field"):
        out["field"] = career.get(s, "field")
    start, end = career.get(s, "start"), career.get(s, "end")
    if start or end:
        out["period"] = period(start, end, "ended" if end else "unknown")
    if career.get(s, "gradeScheme") or career.all(s, "gradeValue"):
        grade = {}
        if career.get(s, "gradeScheme"):
            grade["scheme"] = career.get(s, "gradeScheme")
        if career.all(s, "gradeValue"):
            term = career.all(s, "gradeValue")[0]
            grade["value"] = term.value if term.datatype.value == O.XSD + "string" \
                else number(term)
        out["grade"] = grade
    out["provenance"] = provenance(career.sub, s)
    return out


def credential(career, s):
    out = {"id": local(s), "name": career.get(s, "name"), "issuer": career.get(s, "issuer"),
           "kind": "certification"}
    if career.get(s, "issued"):
        out["issued"] = instant(career.get(s, "issued"))
    if career.get(s, "expires"):
        out["expires"] = instant(career.get(s, "expires"))
    out["status"] = enum(career.get(s, "credentialState"))
    if career.get(s, "url"):
        out["url"] = career.get(s, "url")
    out["provenance"] = provenance(career.sub, s)
    return out


def skills(career, gate, notes=None):
    """The skills, less each alias the claims gate would warn of: one naming a concept no
    project holds reads to an ATS as a claim of that experience. Copied anyway, every
    draft shipped the warning and someone hand-edited it away (ElevenLabs, 2026-09-25)."""
    from ..gates import claims

    anywhere = claims.held_anywhere(gate)
    out = []
    for s in career.live("Skill"):
        item = {"id": local(s), "name": career.get(s, "name"),
                "category": career.get(s, "category")}
        aliases = []
        for alias in sorted(t.value for t in career.all(s, "alias")):
            concepts = claims.unheld(alias, gate, anywhere)
            if not concepts:
                aliases.append(alias)
            elif notes is not None:
                names = ", ".join(sorted(claims.curie(c) for c in concepts))
                notes.append(f"NOTE  {local(s)} alias {alias!r} left out: no project in kb.ttl "
                             f"holds {names}, and an ATS reads it as a claim of that experience")
        if aliases:
            item["aliases"] = aliases
        out.append((career.get(s, "category"), int(career.get(s, "rank", 10 ** 6)),
                    item["name"], item))
    return [item for *_, item in sorted(out, key=lambda x: x[:3])]


def positioning(career):
    s = O.K + "person"
    text = career.get(s, "positioning")
    if not text:
        return None
    return {"id": "nar_positioning", "kind": "summary", "text": text,
            "provenance": provenance(career.sub, s)}


def region(country):
    """The region profile for a country, or the default one when none ships for it -
    by the id default.json declares (`urs:profile:xx/1`). "urs:profile:default/1" was
    written here, the validator refuses it as unresolvable, and a record exported for
    a person with no shipped country failed before anything was authored."""
    import json

    token = (country or "").lower()
    if token and os.path.exists(os.path.join(SCHEMA_DIR, "profiles", f"{token}.json")):
        return f"urs:profile:{token}/1"
    with open(os.path.join(SCHEMA_DIR, "profiles", "default.json"), encoding="utf8") as fh:
        return json.load(fh)["id"]


def view(career, doc, engagements, narrative, selection=None):
    include = []
    for n, (e, _) in enumerate(engagements, 1):
        include.append({"ref": e["id"], "order": n})
    for p in doc.get("projects") or []:
        include.append({"ref": p["id"], "achievements": [a["id"] for a in p["achievements"]]})
    out = {"id": "view_draft", "format_profile": "presentation",
           "region_profile": region(career.get(O.K + "person", "country"))}
    if narrative:
        out["narrative"] = narrative["id"]
    out["provenance_floor"] = "confirmed"
    out["budget"] = {"pages": 2}
    out["include"] = include
    if selection is not None:
        out["skills"] = [local(s) for s in selection.skills]
    return out


# --- refresh: the record rebuilt from kb.ttl, what was authored in it kept ----------------

# What export writes. Every other top-level key of a record (referees, availability,
# compensation, identity_documents, x) was written by hand, so refresh keeps it.
EXPORTED = ("urs", "meta", "person", "work_authorization", "languages", "organizations",
            "engagements", "education", "credentials", "projects", "skills", "narratives",
            "views")
POSITIONING = "nar_positioning"


def items(doc, key):
    return [x for x in doc.get(key) or [] if isinstance(x, dict) and isinstance(x.get("id"), str)]


def entries(doc):
    """{id: object} for every entry refresh compares: the ones export writes by id."""
    out = {}
    for key in ("organizations", "engagements", "education", "credentials", "projects",
                "skills"):
        for x in items(doc, key):
            out[x["id"]] = x
    for e in items(doc, "engagements"):
        for p in items(e, "positions"):
            out[p["id"]] = p
    for p in items(doc, "projects"):
        for a in items(p, "achievements"):
            out[a["id"]] = a
    for n in items(doc, "narratives"):
        if n["id"] == POSITIONING:
            out[n["id"]] = n
    return out


def status(x):
    pv = x.get("provenance")
    return pv.get("status") if isinstance(pv, dict) else None


def amounts(m):
    """{part: number} of a metric as the record writes it: its quantity, its baseline,
    and the number as the person stated it, when that rides beside."""
    out = {k: m[k].get("value") for k in ("quantity", "baseline") if isinstance(m.get(k), dict)}
    if m.get("value") is not None:
        out["stated"] = m["value"]
    return out


def moves(mid, was, now):
    """'met_x 400 -> 350', 'met_x baseline 5 -> 4': each number of a metric that moved."""
    a, b = amounts(was), amounts(now)
    out = []
    for k in ("quantity", "baseline", "stated"):
        if a.get(k) != b.get(k):
            label = "" if k == "quantity" else f"{k} "
            out.append(f"{mid} {label}{a.get(k, 'none')} -> {b.get(k, 'none')}")
    return out


def changed(was, now):
    """What moved in one entry, as the parts of its line; [] when nothing did."""
    parts = []
    if status(was) != status(now):
        parts.append(f"{status(was)} -> {status(now)}")
    if was.get("text") != now.get("text"):
        parts.append("text changed")
    if "metrics" in was or "metrics" in now:
        old = {m.get("id"): m for m in was.get("metrics") or [] if isinstance(m, dict)}
        new = {m.get("id"): m for m in now.get("metrics") or [] if isinstance(m, dict)}
        for mid in sorted(set(old) | set(new), key=str):
            if mid not in new:
                parts.append(f"{mid} left off (no current version of it is cited)")
            elif mid not in old:
                parts.append(f"cites {mid} now")
            elif moves(mid, old[mid], new[mid]):
                parts += moves(mid, old[mid], new[mid])
            elif old[mid] != new[mid]:
                parts.append(f"{mid} changed")
    rest = sorted(k for k in set(was) | set(now) if k not in (
        "id", "provenance", "text", "metrics", "achievements", "positions")
        and was.get(k) != now.get(k))
    if rest:
        parts.append(f"{', '.join(rest)} changed")
    return parts


def refresh(store, old, select=None, today=None, notes=None):
    """(record, lines): `old` rebuilt from kb.ttl as it stands, for the entries it carries.

    On the ElevenLabs run a re-export was an `rm` and a redo: the author's view and
    summary lived only in resume.json, so every changeset applied to kb.ttl after
    exporting cost the view twice, and a confirm was hand-patched in with ad-hoc Python.
    Here the selection is the record's own - its projects, each with exactly the bullets
    it lists in its order, and its roles - plus `select`; what the career holds comes
    from kb.ttl, and the views, the authored narratives, meta and every key export never
    writes come from `old`. `lines` says what changed, one per entry, so nobody diffs.

    Raises ExportError for a `select` it cannot honour."""
    import copy

    from . import record as R
    from .select import Selection

    career = Career(store.graph(R.KB))
    picked = chosen(career, select)                 # a bad --select refuses before anything
    lines, dropped, pruned = [], {}, []

    def gone(ident, cls):
        iri = O.K + ident
        if iri not in career.sub.cls or career.sub.cls[iri].name != cls:
            return "career/kb.ttl no longer holds it"
        if career.get(iri, "retired"):
            return (f"retired on {career.get(iri, 'retired')} "
                    f"({career.get(iri, 'reason', 'no reason given')})")
        return None

    projects, bullets, roles = [], {}, []
    for p in items(old, "projects"):
        why = gone(p["id"], "Project")
        if why:
            dropped[p["id"]] = why
        elif O.K + p["id"] not in bullets:
            projects.append(O.K + p["id"])
            bullets[O.K + p["id"]] = []
    for p in items(old, "projects"):
        for a in items(p, "achievements"):
            why = gone(a["id"], "Achievement")
            home = None if why else career.get(O.K + a["id"], "project")
            if home and home not in bullets:
                if local(home) in dropped:
                    why = f"its project {local(home)} is dropped"
                else:                        # kb.ttl moved it: it goes where kb.ttl has it
                    projects.append(home)
                    bullets[home] = []
                    lines.append(f"added    {local(home)}  kb.ttl holds {a['id']} under it")
            if why:
                dropped[a["id"]] = why
            elif O.K + a["id"] not in bullets[home]:
                bullets[home].append(O.K + a["id"])
    for e in items(old, "engagements"):
        for r in items(e, "positions"):
            why = gone(r["id"], "Position")
            if why:
                dropped[r["id"]] = why
            elif O.K + r["id"] not in roles:
                roles.append(O.K + r["id"])

    added = []                                      # (project, bullet) new through select
    if picked is not None:
        want, named, extra = picked

        def rank(a):
            return (int(career.get(a, "rank", 0)), a)

        for a in sorted(named, key=rank):
            home = career.get(a, "project")
            if home not in bullets:
                projects.append(home)
                bullets[home] = []
            if a not in bullets[home]:
                bullets[home].append(a)
                added.append((home, a))
        # As --select means everywhere: a project brings its bullets, unless a bullet of
        # it is named too - then the bullet narrows it.
        narrowed = {career.get(a, "project") for a in named}
        live = sorted(career.live("Achievement"), key=rank)
        for p in sorted(want - narrowed):
            if p not in bullets:
                projects.append(p)
                bullets[p] = []
            for a in live:
                if career.get(a, "project") == p and a not in bullets[p]:
                    bullets[p].append(a)
                    added.append((p, a))
        roles += sorted(r for r in extra if r not in roles)

    selection = Selection(projects, bullets, [], [])
    doc = urs(store, [local(r) for r in roles], today=today, selection=selection, notes=notes)
    order = {local(p): n for n, p in enumerate(projects)}
    if doc.get("projects"):
        doc["projects"].sort(key=lambda p: order.get(p["id"], len(order)))

    # The positioning is kb.ttl's, so it is refreshed; every other narrative was
    # authored for this application and lives only here.
    fresh = next((n for n in items(doc, "narratives") if n["id"] == POSITIONING), None)
    narratives = []
    for n in old.get("narratives") or []:
        if isinstance(n, dict) and n.get("id") == POSITIONING:
            if fresh:
                narratives.append(fresh)
            else:
                dropped[POSITIONING] = "career/kb.ttl holds no positioning now"
        else:
            narratives.append(n)
    if fresh and fresh not in narratives:
        narratives.insert(0, fresh)
    doc.pop("narratives", None)
    add(doc, "narratives", narratives)

    was, now = entries(old), entries(doc)
    vanished = set(was) - set(now)
    views = copy.deepcopy(old["views"]) if isinstance(old.get("views"), list) else doc["views"]
    for v in views:
        if not isinstance(v, dict):
            continue
        less, include = [], []
        for i in v.get("include") or []:
            if isinstance(i, dict) and i.get("ref") in vanished:
                less.append(i["ref"])
                continue
            if isinstance(i, dict) and isinstance(i.get("achievements"), list):
                less += [a for a in i["achievements"] if a in vanished]
                i["achievements"] = [a for a in i["achievements"] if a not in vanished]
            include.append(i)
        if isinstance(v.get("skills"), list):
            less += [s for s in v["skills"] if s in vanished]
            v["skills"] = [s for s in v["skills"] if s not in vanished]
        for p, a in added:
            entry = next((i for i in include if isinstance(i, dict)
                          and i.get("ref") == local(p)), None)
            if entry is None:
                entry = {"ref": local(p), "achievements": []}
                include.append(entry)
            if not isinstance(entry.get("achievements"), list):
                entry["achievements"] = []
            if local(a) not in entry["achievements"]:
                entry["achievements"].append(local(a))
        if "include" in v or include:
            v["include"] = include
        if less:
            pruned.append(f"view     {v.get('id', 'view')}  include less "
                          f"{', '.join(sorted(set(less)))}")
    doc["views"] = views

    meta = {k: v for k, v in (old.get("meta") or {}).items() if k != "updated"} \
        if isinstance(old.get("meta"), dict) else {}
    if "updated" in doc["meta"]:
        meta["updated"] = doc["meta"]["updated"]
    doc["meta"] = meta or doc["meta"]

    for ident in sorted(was):
        if ident in now:
            parts = changed(was[ident], now[ident])
            if parts:
                lines.append(f"changed  {ident}  {'; '.join(parts)}")
        else:
            lines.append(f"DROPPED  {ident}  "
                         f"{dropped.get(ident, 'the refreshed record has no such entry')}")
    if POSITIONING in dropped and POSITIONING not in was:
        lines.append(f"DROPPED  {POSITIONING}  {dropped[POSITIONING]}")
    by_select = {local(a): local(p) for p, a in added}
    named = [v.get("id", "view") for v in views if isinstance(v, dict)]
    for ident in sorted(set(now) - set(was)):
        if ident in by_select:
            lines.append(f"added    {ident}  by --select, under {by_select[ident]}; appended "
                         f"to {', '.join(named) or 'no view'}")
        elif not any(line.startswith(f"added    {ident}  ") for line in lines):
            lines.append(f"added    {ident}")
    if isinstance(old.get("person"), dict) and old["person"] != doc["person"]:
        keys = sorted(k for k in set(old["person"]) | set(doc["person"])
                      if old["person"].get(k) != doc["person"].get(k))
        lines.append(f"changed  person  {', '.join(keys)} changed")

    # The old record's key order, so a diff of the file shows content, not reshuffling.
    out = {}
    for k in list(old) + [k for k in doc if k not in old]:
        if k in doc:
            out[k] = doc[k]
        elif k not in EXPORTED:
            out[k] = old[k]
    return out, lines + pruned
