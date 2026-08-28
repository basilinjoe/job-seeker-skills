"""Resolve a URS document and one of its views into a render plan.

Every content decision happens here, exactly once: which evidence is included,
in what order, what is gated away by the region profile, how a date reads, and
whether the text is folded to ASCII. The emitters receive finished strings and
decide nothing.

That is the guarantee the pipeline exists to provide. The PDF and the plain
text built from the same view cannot disagree, because neither of them chose
what to say.
"""
import re

from . import profiles
from .formatting import (fold_ascii, fmt_grade, fmt_instant, fmt_period,
                         fmt_quantity, period_key)

PROVENANCE_RANK = {"confirmed": 3, "inferred": 2, "needs-verification": 1, "disputed": 0}

# Architecture-level rows first, then stacks - the ordering in bundle-spec.md.
# .title() would render these as "Ai" / "Api" / "Ml"; a skills row is the most
# scanned line on a resume and a miscased acronym reads as carelessness.
CATEGORY_ACRONYMS = {"ai": "AI", "api": "API", "ml": "ML", "ui": "UI",
                     "ux": "UX", "qa": "QA", "devops": "DevOps"}

CATEGORY_ORDER = [
    "architecture", "platform", "cloud-platform", "ai", "data", "language",
    "framework", "infrastructure", "database", "tooling", "practice", "domain",
]

# Enough to cover the markets that actually ask for nationality. Anything not
# listed falls through to the string as written, which is why the schema accepts
# a name as readily as a code: 'Nationality: IN' is worse than no line at all.
DEMONYM = {
    "AE": "Emirati", "AU": "Australian", "BD": "Bangladeshi", "CA": "Canadian",
    "CN": "Chinese", "DE": "German", "EG": "Egyptian", "ES": "Spanish",
    "FR": "French", "GB": "British", "IE": "Irish", "IN": "Indian",
    "IT": "Italian", "JO": "Jordanian", "JP": "Japanese", "KE": "Kenyan",
    "LB": "Lebanese", "LK": "Sri Lankan", "MY": "Malaysian", "NG": "Nigerian",
    "NP": "Nepali", "NZ": "New Zealand", "PH": "Filipino", "PK": "Pakistani",
    "SA": "Saudi", "SG": "Singaporean", "US": "American", "ZA": "South African",
}

def _index(items):
    return {i["id"]: i for i in (items or []) if isinstance(i, dict) and "id" in i}


class Resolver:
    def __init__(self, doc, gate, view, ascii_only):
        self.doc = doc
        self.gate = gate
        self.view = view
        self.ascii_only = ascii_only
        self.warnings = []
        self.orgs = _index(doc.get("organizations"))
        self.skills = _index(doc.get("skills"))
        self.projects = _index(doc.get("projects"))
        self.narratives = _index(doc.get("narratives"))
        self.floor = PROVENANCE_RANK.get(view.get("provenance_floor", "confirmed"), 3)
        self.chronological = gate.setting("order") == "chronological"
        self.selection = {
            inc["ref"]: inc for inc in (view.get("include") or []) if "ref" in inc
        }

    # -- text -------------------------------------------------------------

    def t(self, text):
        if text is None:
            return None
        if "[" in text or "]" in text:
            self.warnings.append(
                f"bracket in rendered text - almost always a leftover placeholder: {text[:60]!r}"
            )
        return fold_ascii(text) if self.ascii_only else text

    def sep(self):
        return " | " if self.ascii_only else " · "

    # -- filtering --------------------------------------------------------

    def keep(self, node, what):
        status = ((node or {}).get("provenance") or {}).get("status", "confirmed")
        if PROVENANCE_RANK.get(status, 0) < self.floor:
            self.warnings.append(
                f"withheld {what} - provenance '{status}' is below the view floor"
            )
            return False
        return True

    def achievements_of(self, owner, owner_id):
        chosen = (self.selection.get(owner_id) or {}).get("achievements")
        items = [a for a in (owner.get("achievements") or []) if self.keep(a, f"bullet {a.get('id')}")]
        if chosen:
            order = {aid: n for n, aid in enumerate(chosen)}
            items = [a for a in items if a["id"] in order]
            items.sort(key=lambda a: order[a["id"]])
        else:
            items.sort(key=lambda a: -(a.get("weight") or 0))
        return [self.t(a["text"]) for a in items]

    # -- sections ---------------------------------------------------------

    def header(self):
        person = self.doc.get("person") or {}
        name = (person.get("name") or {}).get("full", "")
        lines = []
        if person.get("headline"):
            lines.append(self.t(person["headline"]))

        loc = person.get("location") or {}
        place = []
        for key in ("locality", "city", "region", "country"):
            if loc.get(key) and self.gate.permits(f"person.location.{key}"):
                place.append(loc[key])
        contact = [", ".join(place)] if place else []

        labelled = self.ascii_only
        for c in person.get("contacts") or []:
            if not self.gate.permits(f"person.contacts.{c.get('kind')}"):
                continue
            value = c.get("value", "")
            if labelled and c.get("kind") in ("phone", "email"):
                contact.append(f"{c['kind'].capitalize()}: {value}")
            else:
                contact.append(value)
        if contact:
            lines.append(self.t(self.sep().join(contact)))

        auth = self.authorization_line()
        if auth:
            lines.append(auth)
        return name, [l for l in lines if l]

    def authorization_line(self):
        if not self.gate.permits("work_authorization"):
            return None
        bits = []
        for a in self.doc.get("work_authorization") or []:
            label = a.get("label")
            if not label:
                kind = (a.get("kind") or "").replace("-", " ")
                label = f"{a.get('jurisdiction', '')} {kind}".strip()
            extra = []
            if a.get("status") == "requires-sponsorship":
                extra.append("sponsorship required")
            if a.get("transferable"):
                extra.append("transferable")
            if a.get("expires"):
                extra.append(f"to {fmt_instant(a['expires'])}")
            bits.append(label + (f" ({', '.join(extra)})" if extra else ""))
        return self.t("Work rights: " + self.sep().join(bits)) if bits else None

    def summary(self):
        nid = self.view.get("narrative")
        nar = self.narratives.get(nid) if nid else None
        if nar is None:
            nar = next((n for n in self.doc.get("narratives") or []
                        if n.get("kind") == "summary"), None)
        if nar is None or not self.keep(nar, "summary"):
            return None
        return {"kind": "text", "heading": "Professional Summary",
                "paragraphs": [self.t(nar["text"])]}

    def skills_section(self):
        chosen = self.view.get("skills")
        items = [self.skills[s] for s in chosen if s in self.skills] if chosen \
            else list(self.doc.get("skills") or [])
        if not items:
            return None
        groups = {}
        for s in items:
            groups.setdefault(s.get("category") or "other", []).append(s)

        def rank(cat):
            return (CATEGORY_ORDER.index(cat), cat) if cat in CATEGORY_ORDER else (len(CATEGORY_ORDER), cat)

        rows = []
        for cat in sorted(groups, key=rank):
            names = []
            for s in groups[cat]:
                names.append(s["name"])
                if self.ascii_only:
                    names.extend(s.get("aliases") or [])
            label = cat.replace("-", " ").replace("_", " ").title()
            # .title() lowercases acronyms - an "AI" row must not render as "Ai".
            label = " ".join(CATEGORY_ACRONYMS.get(w.lower(), w) for w in label.split())
            rows.append({"label": self.t(label), "items": [self.t(n) for n in names]})
        heading = "Technical Skills" if self.ascii_only else "Skills"
        return {"kind": "rows", "heading": heading, "rows": rows}

    def experience(self):
        engagements = [e for e in self.doc.get("engagements") or []
                       if self.gate.permits("engagements") and self.keep(e, f"engagement {e.get('id')}")]
        if self.selection:
            engagements = [e for e in engagements if e["id"] in self.selection] or engagements
        chronological = self.gate.setting("order") == "chronological"
        engagements.sort(key=lambda e: period_key(e.get("period")), reverse=not chronological)
        if self.selection:
            engagements.sort(key=lambda e: (self.selection.get(e["id"], {}).get("order", 10 ** 6)))
            engagements.sort(key=lambda e: period_key(e.get("period")), reverse=not chronological)

        entries = []
        for e in engagements:
            entries.append(self.engagement_entry(e))
        if not entries:
            return None
        return {"kind": "entries", "heading": "Professional Experience", "entries": entries}

    def engagement_entry(self, e):
        org = self.orgs.get(e.get("organization")) or {}
        org_name = org.get("name") or ("Career break" if e.get("kind") == "break" else "")
        # Current role first under a reverse-chronological convention, which is
        # the whole reason the profile carries an order setting.
        positions = sorted(e.get("positions") or [],
                           key=lambda p: period_key(p.get("period")),
                           reverse=not self.chronological)
        entry = {"org_line": None, "org_right": None, "roles": [], "lines": [], "bullets": []}

        if self.ascii_only:
            # ATS-maximal: name the employer on every role line.
            for p in positions:
                left = f"{p['title']}, {org_name}" if org_name else p["title"]
                entry["roles"].append({"left": self.t(left), "right": fmt_period(p.get("period"))})
            if not positions:
                entry["roles"].append({"left": self.t(org_name), "right": fmt_period(e.get("period"))})
        else:
            entry["org_line"] = self.t(org_name)
            entry["org_right"] = fmt_period(e.get("period"))
            for p in positions:
                entry["roles"].append({"left": self.t(p["title"]),
                                       "right": fmt_period(p.get("period"))})

        context = []
        loc = e.get("location") or {}
        where = ", ".join([v for v in (loc.get("city"), loc.get("region")) if v])
        if where:
            context.append(where + (f" ({loc['mode']})" if loc.get("mode") else ""))
        if e.get("kind") in ("contract", "freelance", "internship", "volunteer"):
            context.append(e["kind"].capitalize())
        via = (e.get("employment") or {}).get("via")
        if via and via in self.orgs:
            context.append(f"via {self.orgs[via]['name']}")
        if e.get("domains"):
            context.append("Domains: " + ", ".join(e["domains"]))
        if context:
            entry["lines"].append(self.t(self.sep().join(context)))

        promotions = [p for p in positions if p.get("change") == "promotion"]
        if len(positions) > 2 and promotions:
            # A sentence, never an arrow chain. ats-rules.md: if the glyph is
            # stripped, four job titles fuse into one phantom title. The
            # progression is stated oldest-first because that is the direction
            # a promotion runs, whatever order the roles are listed in above.
            oldest_first = sorted(positions, key=lambda p: period_key(p.get("period")))
            titles = ", ".join(p["title"] for p in oldest_first)
            entry["lines"].append(self.t(
                f"Promoted through {len(positions)} roles: {titles}."))
        if e.get("summary"):
            entry["lines"].append(self.t(e["summary"]))

        entry["bullets"] = self.achievements_of(e, e["id"])
        for pid in e.get("projects") or []:
            project = self.projects.get(pid)
            if project and self.keep(project, f"project {pid}"):
                entry["bullets"].extend(self.achievements_of(project, pid))
        return entry

    def education(self):
        items = [e for e in self.doc.get("education") or [] if self.keep(e, f"education {e.get('id')}")]
        if not items:
            return None
        items.sort(key=lambda e: period_key(e.get("period")), reverse=True)
        entries = []
        for e in items:
            title = e.get("qualification") or ""
            if e.get("field"):
                title = f"{title}, {e['field']}" if title else e["field"]
            entry = {"org_line": self.t(title or e.get("institution")),
                     "org_right": fmt_period(e.get("period")),
                     "roles": [], "lines": [], "bullets": []}
            detail = [e.get("institution")] if title else []
            if e.get("board"):
                detail.append(e["board"])
            grade = fmt_grade(e.get("grade"))
            if grade:
                detail.append(grade)
            if detail:
                entry["lines"].append(self.t(self.sep().join(d for d in detail if d)))
            entries.append(entry)
        return {"kind": "entries", "heading": "Education", "entries": entries}

    def credentials(self):
        items = self.doc.get("credentials") or []
        lines = []
        for c in items:
            if not self.keep(c, f"credential {c.get('id')}"):
                continue
            bits = [c["name"]]
            if c.get("issuer"):
                bits.append(c["issuer"])
            if c.get("issued"):
                bits.append(fmt_instant(c["issued"]))
            if c.get("status") == "in-progress":
                bits.append("in progress")
            for att in c.get("attestation") or []:
                bits.append(f"attested by {att['authority']}")
            lines.append(self.t(self.sep().join(bits)))
        if not lines:
            return None
        return {"kind": "lines", "heading": "Certifications", "lines": lines}

    def languages(self):
        items = self.doc.get("languages") or []
        if not items or not self.gate.permits("languages"):
            return None
        lines = []
        for l in items:
            name = l.get("language", "")
            if l.get("native"):
                detail = "Native"
            elif l.get("modalities"):
                detail = ", ".join(f"{k.capitalize()} {v}" for k, v in l["modalities"].items() if v)
            else:
                detail = l.get("overall") or ""
            lines.append(self.t(f"{name} - {detail}" if detail else name))
        return {"kind": "lines", "heading": "Languages", "lines": lines}

    def personal(self):
        """Demographics and documents, for the markets that expect them.

        Nothing here renders unless a region profile lists the field, so the
        same record is lawful in Sydney and conventional in Dubai. A required
        field with no emitter is a field that vanishes silently, which is why
        this section exists rather than the header carrying the load.
        """
        person = self.doc.get("person") or {}
        demo = person.get("demographics") or {}
        lines = []

        nationalities = demo.get("nationality") or []
        if nationalities and self.gate.permits("person.demographics.nationality"):
            named = [DEMONYM.get(n, n) for n in nationalities]
            lines.append(f"Nationality: {', '.join(named)}")
        if demo.get("date_of_birth") and self.gate.permits("person.demographics.date_of_birth"):
            lines.append(f"Date of birth: {fmt_instant(demo['date_of_birth'])}")
        if demo.get("marital_status") and self.gate.permits("person.demographics.marital_status"):
            lines.append(f"Marital status: {demo['marital_status'].capitalize()}")
        if demo.get("gender") and self.gate.permits("person.demographics.gender"):
            lines.append(f"Gender: {demo['gender']}")

        if self.gate.permits("person.name.related_names"):
            for rel in (person.get("name") or {}).get("related_names") or []:
                lines.append(f"{rel['relation'].capitalize()}'s name: {rel['name']}")

        for d in self.doc.get("identity_documents") or []:
            if not self.gate.permits("identity_documents"):
                break
            label = d.get("label") or d["kind"].replace("-", " ").capitalize()
            bits = [label]
            if d.get("number"):
                bits.append(d["number"])
            if d.get("expires"):
                bits.append(f"valid to {fmt_instant(d['expires'])}")
            lines.append(": ".join([bits[0], ", ".join(bits[1:])]) if len(bits) > 1 else bits[0])

        if not lines:
            return None
        return {"kind": "lines", "heading": "Personal Details",
                "lines": [self.t(l) for l in lines]}

    def logistics(self):
        lines = []
        av = self.doc.get("availability") or {}
        if self.gate.permits("availability"):
            if av.get("notice_period_days") is not None:
                lines.append(f"Notice period: {av['notice_period_days']} days")
            if av.get("earliest_start"):
                lines.append(f"Available from {fmt_instant(av['earliest_start'])}")
        comp = self.doc.get("compensation") or {}
        for key, label in (("current", "Current"), ("expected", "Expected")):
            figure = comp.get(key)
            if figure and self.gate.permits(f"compensation.{key}"):
                basis = figure.get("basis", "")
                basis_label = "CTC" if basis == "ctc" else basis.replace("-", " ")
                per = figure.get("period")
                text = f"{label} {basis_label}: {fmt_quantity(figure.get('amount'))}"
                lines.append(self.t(text + (f" per {per}" if per else "")))
        if not lines:
            return None
        return {"kind": "lines", "heading": "Availability", "lines": [self.t(l) for l in lines]}

    def referees(self):
        mode = self.gate.setting("referees", "omit")
        if mode == "omit":
            return None
        if mode == "on-request":
            return None
        items = [r for r in self.doc.get("referees") or [] if self.gate.permits("referees")]
        if not items:
            return None
        entries = []
        for r in items:
            if r.get("consent") is False:
                self.warnings.append(f"referee {r.get('name')!r} has not consented - omitted")
                continue
            head = ", ".join(b for b in (r.get("name"), r.get("title"), r.get("organization")) if b)
            detail = self.sep().join(c.get("value", "") for c in r.get("contacts") or [])
            entry = {"org_line": self.t(head), "org_right": None, "roles": [],
                     "lines": [self.t(detail)] if detail else [], "bullets": []}
            entries.append(entry)
        if not entries:
            return None
        return {"kind": "entries", "heading": "Referees", "entries": entries}

    def declaration(self):
        if not self.gate.setting("declaration"):
            return None
        loc = (self.doc.get("person") or {}).get("location") or {}
        where = loc.get("city")
        when = (self.doc.get("meta") or {}).get("updated")
        text = ("I hereby declare that the information given above is true and correct "
                "to the best of my knowledge and belief.")
        lines = [self.t(text)]
        stamp = self.sep().join(b for b in (
            f"Place: {where}" if where else None, f"Date: {when}" if when else None) if b)
        if stamp:
            lines.append(self.t(stamp))
        return {"kind": "lines", "heading": None, "lines": lines}


def build(doc, view_id=None, region=None, fmt=None):
    """Resolve `doc` and one view into a render plan.

    `region` and `fmt` override the view's own settings, so one authored view
    can be rendered for another market without editing the record.
    """
    views = doc.get("views") or []
    view = None
    if view_id:
        view = next((v for v in views if v.get("id") == view_id), None)
        if view is None:
            raise KeyError(f"no view {view_id!r} in this document")
    elif views:
        view = views[0]
    else:
        view = {"id": "view_default", "format_profile": fmt or "presentation"}

    fmt = fmt or view.get("format_profile", "presentation")
    profile = profiles.load(region or view.get("region_profile"))
    gate = profiles.Gate(profile, view.get("redact") or [])
    ascii_only = fmt in ("ats-maximal", "plaintext")

    r = Resolver(doc, gate, view, ascii_only)
    name, header_lines = r.header()

    order = gate.setting("sections") or [
        "summary", "skills", "experience", "education", "credentials"]
    builders = {
        "summary": r.summary,
        "skills": r.skills_section,
        "experience": r.experience,
        "education": r.education,
        "credentials": r.credentials,
        "languages": r.languages,
        "availability": r.logistics,
        "compensation": r.logistics,
        "work_authorization": lambda: None,   # rendered in the header
        "referees": r.referees,
        "personal": r.personal,
    }
    if view.get("sections"):
        order = view["sections"]

    sections, seen = [], set()
    for key in order:
        if key in seen:
            continue
        seen.add(key)
        section = builders.get(key, lambda: None)()
        if section:
            sections.append(section)
    declaration = r.declaration()
    if declaration:
        sections.append(declaration)

    present = _present_paths(doc)
    for missing in gate.missing_required(present):
        r.warnings.append(
            f"profile {profile['id']} requires {missing!r} and the record has nothing for it")

    # ATS-maximal is deliberately longer: it repeats the employer on every role
    # line and expands the skills block with keyword aliases. Holding it to the
    # presentation budget would mean cutting evidence to satisfy a constraint a
    # parser does not have, so it carries its own budget and falls back to the
    # shared one when a view does not set it.
    budget = view.get("budget") or {}
    pages = budget.get("ats_maximal_pages") if fmt == "ats-maximal" else None
    pages = pages or budget.get("pages") or gate.setting("pages", 2)

    photo = (doc.get("person") or {}).get("photo")
    photo_uri = None
    if photo and gate.setting("photo") and gate.permits("person.photo"):
        photo_uri = photo.get("uri")

    return {
        "view": view["id"],
        "format": fmt,
        "profile": profile["id"],
        # The profile's own region is a family - "XX" covers the US, the UK and
        # much of Europe - so it cannot answer a question like paper size. When
        # the caller named a region explicitly that is the more specific answer,
        # and it wins. Without this, --region US loaded the default profile and
        # reported region "XX", so the Letter branch in the emitters was
        # unreachable and a US resume rendered A4.
        "region": (region or "").strip().upper() or profile.get("region"),
        "locale": view.get("locale"),
        "pages": pages,
        "name": name,
        "header_lines": header_lines,
        "photo": photo_uri,
        "sections": sections,
        "warnings": r.warnings,
        "target": view.get("target"),
    }


def _present_paths(doc, prefix="", out=None):
    """Dotted paths that actually carry a value, for the required-field check."""
    out = out if out is not None else set()
    if isinstance(doc, dict):
        for key, value in doc.items():
            path = f"{prefix}.{key}" if prefix else key
            if value in (None, [], {}, ""):
                continue
            out.add(path)
            if isinstance(value, dict):
                _present_paths(value, path, out)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                _present_paths(value[0], path, out)
    return out
