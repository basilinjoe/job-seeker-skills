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


def urs(store, select=None, today=None):
    """The draft record, as a dict. Raises ExportError for a selection it cannot honour."""
    from . import record as R

    career = Career(store.graph(R.KB))
    picked = chosen(career, select)
    bullets_of = {}
    for a in career.live("Achievement"):
        bullets_of.setdefault(career.get(a, "project"), []).append(a)
    for p in bullets_of:
        bullets_of[p].sort(key=lambda a: (int(career.get(a, "rank", 0)), a))

    projects = [p for p in career.live("Project")]
    if picked is not None:
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
    if picked is None:
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
    add(doc, "skills", skills(career))
    narrative = positioning(career)
    add(doc, "narratives", [narrative] if narrative else [])
    doc["views"] = [view(career, doc, engagements, narrative)]
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


def skills(career):
    out = []
    for s in career.live("Skill"):
        item = {"id": local(s), "name": career.get(s, "name"),
                "category": career.get(s, "category")}
        aliases = sorted(t.value for t in career.all(s, "alias"))
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
    """The region profile for a country, or the default one when none ships for it."""
    token = (country or "").lower()
    if token and os.path.exists(os.path.join(SCHEMA_DIR, "profiles", f"{token}.json")):
        return f"urs:profile:{token}/1"
    return "urs:profile:default/1"


def view(career, doc, engagements, narrative):
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
    return out
