"""The career and a short resume.json, as the render plan the emitters take.

Every content decision happens here, exactly once: which evidence is shown, in what
order, whether a line clears the provenance floor, how a date reads, and whether the
text is folded to ASCII. The emitters receive finished strings and decide nothing, so
the PDF and the plain text built from one resume cannot disagree.

This was `urs/resolve.py`, which read a URS record copied out of career/kb.ttl. It reads
the career itself now. What the resolver rendered from data kb.ttl cannot hold - date of
birth, a photo, referees, compensation, an engagement's location - is gone with the
copy: a feature comes back by giving its data a home in the ontology first.
"""
import datetime

from ..graph import ontology as O
from ..graph import record as R
from ..urs import profiles
from ..urs.formatting import fmt_grade, fmt_instant, fmt_period, fold_ascii, period_key
from .career import CONTACTS, Career, employers, enum, local, number, period

PROVENANCE_RANK = {"confirmed": 3, "inferred": 2, "needs-verification": 1, "disputed": 0}

# .title() would render these as "Ai" / "Api" / "Ml"; a skills row is the most scanned
# line on a resume and a miscased acronym reads as carelessness.
CATEGORY_ACRONYMS = {"ai": "AI", "api": "API", "ml": "ML", "ui": "UI",
                     "ux": "UX", "qa": "QA", "devops": "DevOps"}

# Architecture-level rows first, then stacks: the order a reader scanning for fit
# wants, the shape of the work before the tools it was done with.
CATEGORY_ORDER = [
    "architecture", "platform", "cloud-platform", "ai", "data", "language",
    "framework", "infrastructure", "database", "tooling", "practice", "domain",
]

# The location line rendered "Kochi, Kerala, IN" - a bare code where a recruiter abroad
# expects a country, on the line that tells them where the candidate is. Anything not
# listed renders as written.
COUNTRY = {
    "AE": "United Arab Emirates", "AU": "Australia", "BD": "Bangladesh", "CA": "Canada",
    "CN": "China", "DE": "Germany", "EG": "Egypt", "ES": "Spain",
    "FR": "France", "GB": "United Kingdom", "IE": "Ireland", "IN": "India",
    "IT": "Italy", "JO": "Jordan", "JP": "Japan", "KE": "Kenya",
    "LB": "Lebanon", "LK": "Sri Lanka", "MY": "Malaysia", "NG": "Nigeria",
    "NP": "Nepal", "NZ": "New Zealand", "PH": "Philippines", "PK": "Pakistan",
    "SA": "Saudi Arabia", "SG": "Singapore", "US": "United States", "ZA": "South Africa",
}

# Contact kinds on the first contact line, beside the place; linkedin, github and a
# website go on the second. One line holding all of them wrapped mid-way in every
# template and left a profile URL orphaned on a line of its own.
DIRECT_CONTACTS = ("email", "phone")

# A skills row longer than this stops being scanned. The ATS render of the Everforth
# application filled 45% of page 1 with its skills block while page 2 was half empty;
# ten names is what a recruiter reads in one pass of a row.
MAX_SKILLS_PER_ROW = 10

# Kinds of work said beside the employer; employment goes unsaid.
SAID_KINDS = ("contract", "freelance", "internship", "volunteer")

# The sections a career can fill, in the order a profile does not override.
SECTIONS = ("summary", "skills", "experience", "education", "credentials")
FILLABLE = SECTIONS + ("languages",)

LANGUAGE = {"en": "English", "hi": "Hindi", "ml": "Malayalam", "ta": "Tamil", "te": "Telugu",
            "kn": "Kannada", "ar": "Arabic", "fr": "French", "de": "German", "es": "Spanish",
            "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "pt": "Portuguese",
            "it": "Italian", "nl": "Dutch", "ru": "Russian", "ur": "Urdu", "bn": "Bengali",
            "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi"}


def role_title(title, functional):
    """The title, with its functional gloss when one adds something.

    A title that is internal-only, niche or simply misleading - "Member of Technical
    Staff" - tells a reader outside that employer nothing, and the reader is spending
    six seconds. The gloss goes in parentheses beside the official title rather than in
    place of it, because the official title is the one a reference check confirms.
    Suppressed when the two match case-insensitively: "Senior Engineer (Senior
    Engineer)" is worse than either alone.
    """
    title, functional = (title or "").strip(), (functional or "").strip()
    if functional and functional.lower() != title.lower():
        return f"{title} ({functional})"
    return title


class Builder:
    def __init__(self, career, doc, profile, ascii_only, today):
        self.career = career
        self.doc = doc
        self.profile = profile
        self.ascii_only = ascii_only
        self.today = today
        self.warnings = []
        self.sent = []
        self.floor = PROVENANCE_RANK.get(doc.get("floor", "confirmed"), 3)
        self.me = O.K + "person"

    # -- text -------------------------------------------------------------

    def t(self, text):
        if text is None:
            return None
        if "[" in text or "]" in text:
            self.warnings.append(
                f"bracket in rendered text - almost always a leftover placeholder: {text[:60]!r}")
        return fold_ascii(text) if self.ascii_only else text

    def sep(self):
        return " | " if self.ascii_only else " · "

    def keep(self, status, what):
        if PROVENANCE_RANK.get(status, 0) < self.floor:
            self.warnings.append(f"withheld {what} - provenance '{status}' is below the floor")
            return False
        return True

    def iri(self, ident):
        return O.K + ident

    # -- header -----------------------------------------------------------

    def header(self):
        c, me = self.career, self.me
        name = c.get(me, "fullName", "")
        lines = []
        self.headline = self.t(c.get(me, "headline")) if c.get(me, "headline") else None
        if self.headline:
            lines.append(self.headline)
        place = []
        for key in ("city", "region", "country"):
            value = c.get(me, key)
            if value:
                place.append(COUNTRY.get(value.strip().upper(), value) if key == "country"
                             else value)
        direct = [", ".join(place)] if place else []
        web = []
        for kind in CONTACTS:
            for term in sorted(c.all(me, kind), key=lambda t: t.value):
                if kind in DIRECT_CONTACTS:
                    direct.append(f"{kind.capitalize()}: {term.value}" if self.ascii_only
                                  else term.value)
                else:
                    web.append(term.value)
        for contact in (direct, web):
            if contact:
                lines.append(self.t(self.sep().join(contact)))
        auth = self.authorization_line()
        if auth:
            lines.append(auth)
        return name, [line for line in lines if line]

    def authorization_line(self):
        """Work rights, only where the market's profile puts them on the page.

        "Work rights: IN citizen" rendered on an application to a US posting, against the
        person's own record, which says the portal asks it on the form. Where a profile
        sets `work_rights` (au, ae) a recruiter screens on it first; anywhere else it is a
        line spent on a question nobody asked.
        """
        if not self.profile.get("work_rights"):
            return None
        c, bits = self.career, []
        for a in sorted(c.live("WorkAuthorization")):
            kind = (enum(c.get(a, "kind")) or "").replace("-", " ")
            label = f"{c.get(a, 'jurisdiction', '')} {kind}".strip()
            extra = []
            if enum(c.get(a, "authorization")) == "requires-sponsorship":
                extra.append("sponsorship required")
            if c.get(a, "validUntil"):
                extra.append(f"to {fmt_instant({'value': c.get(a, 'validUntil')[:7], 'precision': 'month'})}")
            bits.append(label + (f" ({', '.join(extra)})" if extra else ""))
        return self.t("Work rights: " + self.sep().join(bits)) if bits else None

    # -- sections ---------------------------------------------------------

    def summary(self):
        s = self.doc.get("summary")
        if s:
            text, status = s["text"], s["status"]
        else:
            text, status = self.career.get(self.me, "positioning"), self.career.status(self.me)
        if not text or not self.keep(status, "summary"):
            return None
        return {"kind": "text", "heading": "Professional Summary", "paragraphs": [self.t(text)]}

    def skills_section(self):
        """The skills block: each name once, in the order the file chose.

        Aliases are never rendered. The ATS variant used to expand them, and the
        Everforth render read "C# / .NET, .NET, C#, ... dotnet": a modern ATS matches
        those variants itself, and a recruiter reads repetition as keyword stuffing.
        A name repeated across categories shows once, first occurrence winning. When the
        file lists skills they were ordered by relevance to the posting, so a category
        comes where its first skill does; CATEGORY_ORDER is only the fallback.
        """
        c = self.career
        chosen = self.doc.get("skills")
        if chosen:
            items = [self.iri(s) for s in chosen]
        else:
            items = sorted(c.live("Skill"), key=lambda s: (
                c.get(s, "category") or "", int(c.get(s, "rank", 10 ** 6)), c.get(s, "name") or ""))
        if not items:
            return None
        groups = {}
        for s in items:
            groups.setdefault(c.get(s, "category") or "other", []).append(s)

        def rank(cat):
            key = cat.lower()
            return (CATEGORY_ORDER.index(key), key) if key in CATEGORY_ORDER \
                else (len(CATEGORY_ORDER), key)

        order = list(groups) if chosen else sorted(groups, key=rank)
        rows, seen = [], set()
        for cat in order:
            names = []
            for s in groups[cat]:
                name = (c.get(s, "name") or "").strip()
                if name and name.casefold() not in seen:
                    seen.add(name.casefold())
                    names.append(name)
            if not names:
                continue
            label = cat.replace("-", " ").replace("_", " ").title()
            label = " ".join(CATEGORY_ACRONYMS.get(w.lower(), w) for w in label.split())
            if len(names) > MAX_SKILLS_PER_ROW:
                dropped = names[MAX_SKILLS_PER_ROW:]
                names = names[:MAX_SKILLS_PER_ROW]
                self.warnings.append(
                    f"skills row {label!r} holds {len(names) + len(dropped)} skills; the "
                    f"first {MAX_SKILLS_PER_ROW} render and these were dropped: "
                    f"{', '.join(dropped)} (order the resume's skills to choose which stay)")
            rows.append({"label": self.t(label), "items": [self.t(n) for n in names]})
        return {"kind": "rows", "heading": "Technical Skills" if self.ascii_only else "Skills",
                "rows": rows}

    def experience(self):
        """One block per employer and kind of work, latest first; each role on its own
        dated line; each bullet under the role its project was done in, in the order
        the file lists them.

        The Experion engagement listed six positions, 2016 to 2025, then every project's
        bullets in one block after them. An ATS credits a bullet to the title directly
        above it, so 2016 work belonged to the 2025 title. A project's role says which
        role it was.
        """
        c = self.career
        placed = {}                                   # role iri -> [(bullet iri, text)]
        roles = []
        for ident in self.doc["bullets"]:
            a = self.iri(ident)
            project = c.get(a, "project")
            role = c.get(project, "position")
            roles.append(role)
            if not self.keep(c.status(project), f"project {local(project)}"):
                continue
            if not self.keep(c.status(a), f"bullet {ident}"):
                continue
            placed.setdefault(role, []).append((ident, self.t(c.get(a, "text"))))
        roles += [self.iri(r) for r in self.doc.get("roles") or []]
        blocks = employers(c, [r for r in roles if r])
        if not blocks:
            return None
        # Latest first, always: every profile shipped said reverse-chronological, and the
        # `order` key that could have said otherwise went with the profiles' slimming.
        entries = [self.employer_entry(e, placed) for e in blocks]
        return {"kind": "entries", "heading": "Professional Experience", "entries": entries}

    def employer_entry(self, e, placed):
        c = self.career
        org_name = c.get(e.org, "name") or ""
        entry = {"org_line": None, "org_right": None, "roles": [], "lines": [], "bullets": []}
        for r in e.roles:
            shown = role_title(c.get(r, "title"), c.get(r, "functionalTitle"))
            if self.ascii_only:
                shown = f"{shown}, {org_name}" if org_name else shown
            bullets = placed.get(r, [])
            self.sent += [ident for ident, _ in bullets]
            entry["roles"].append({"left": self.t(shown), "right": fmt_period(c.role_period(r)),
                                   "bullets": [text for _, text in bullets]})
        if not self.ascii_only:
            entry["org_line"] = self.t(org_name)
            entry["org_right"] = fmt_period(e.span)
        if e.kind in SAID_KINDS:
            entry["lines"].append(self.t(e.kind.capitalize()))
        return entry

    def education(self):
        c = self.career
        items = [s for s in c.live("Education") if self.keep(c.status(s), f"education {local(s)}")]
        if not items:
            return None
        items.sort(key=lambda s: period_key(self.span(s)), reverse=True)
        entries = []
        for s in items:
            title = c.get(s, "qualification") or ""
            if c.get(s, "field"):
                title = f"{title}, {c.get(s, 'field')}" if title else c.get(s, "field")
            entry = {"org_line": self.t(title or c.get(s, "institution")),
                     "org_right": fmt_period(self.span(s)),
                     "roles": [], "lines": [], "bullets": []}
            detail = [c.get(s, "institution")] if title else []
            grade = None
            if c.all(s, "gradeValue"):
                term = c.all(s, "gradeValue")[0]
                value = term.value if term.datatype.value == O.XSD + "string" else number(term)
                grade = fmt_grade({"scheme": c.get(s, "gradeScheme"), "value": value})
            if grade:
                detail.append(grade)
            if detail:
                entry["lines"].append(self.t(self.sep().join(d for d in detail if d)))
            entries.append(entry)
        return {"kind": "entries", "heading": "Education", "entries": entries}

    def span(self, s):
        start, end = self.career.get(s, "start"), self.career.get(s, "end")
        return period(start, end, "ended" if end else "unknown")

    def credentials(self):
        c = self.career
        lines = []
        for s in sorted(c.live("Credential")):
            if not self.keep(c.status(s), f"credential {local(s)}"):
                continue
            bits = [c.get(s, "name")]
            if c.get(s, "issuer"):
                bits.append(c.get(s, "issuer"))
            if c.get(s, "issued"):
                issued = c.get(s, "issued")
                bits.append(fmt_instant({"value": issued,
                                         "precision": "year" if len(issued) == 4 else "month"}))
            lines.append(self.t(self.sep().join(bits)))
        if not lines:
            return None
        return {"kind": "lines", "heading": "Certifications", "lines": lines}

    def languages(self):
        c = self.career
        items = sorted(c.live("Language"))
        if not items:
            return None
        lines = []
        for s in items:
            tag = c.get(s, "language") or ""
            name = LANGUAGE.get(tag.split("-")[0].lower(), tag)
            detail = "Native" if c.get(s, "native") == "true" else (c.get(s, "level") or "")
            lines.append(self.t(f"{name} - {detail}" if detail else name))
        return {"kind": "lines", "heading": "Languages", "lines": lines}

    def declaration(self):
        if not self.profile.get("declaration"):
            return None
        where = self.career.get(self.me, "city")
        text = ("I hereby declare that the information given above is true and correct "
                "to the best of my knowledge and belief.")
        lines = [self.t(text)]
        stamp = self.sep().join(b for b in (
            f"Place: {where}" if where else None, f"Date: {self.today.isoformat()}") if b)
        lines.append(self.t(stamp))
        return {"kind": "lines", "heading": None, "lines": lines}


def build(store, doc, *, region=None, fmt=None, today=None):
    """The plan for `doc` (a short resume.json, already checked) over the career in
    `store`. `region` and `fmt` override the file's own, so one resume can be rendered
    for another market without editing it."""
    career = Career(store.graph(R.KB))
    today = today or datetime.date.today()
    fmt = fmt or doc.get("format") or "presentation"
    country = career.get(O.K + "person", "country")
    profile = profiles.load(region or doc.get("region") or (country or "").lower() or None)
    ascii_only = fmt in ("ats-maximal", "plaintext")
    b = Builder(career, doc, profile, ascii_only, today)
    name, header_lines = b.header()

    order = [s for s in (profile.get("sections") or SECTIONS) if s in FILLABLE]
    builders = {"summary": b.summary, "skills": b.skills_section, "experience": b.experience,
                "education": b.education, "credentials": b.credentials,
                "languages": b.languages}
    sections = []
    for key in dict.fromkeys(order):
        section = builders[key]()
        if section:
            sections.append(section)
    declaration = b.declaration()
    if declaration:
        sections.append(declaration)

    # ATS-maximal is deliberately longer - the employer on every role line, the contact
    # fields labelled - so it carries its own budget and falls back to the shared one.
    pages = doc.get("ats_pages") if fmt == "ats-maximal" else None
    pages = pages or doc.get("pages") or profile.get("pages") or 2
    return {
        "view": "resume",
        "format": fmt,
        "profile": profile["id"],
        # The profile's own region is a family - "XX" covers the US, the UK and much of
        # Europe - so it cannot answer paper size. A region named explicitly is the more
        # specific answer, and it wins: without it a US resume rendered A4. The file's
        # region, else the person's country, is the next most specific - "us" in the
        # file rendered A4 too until the final review.
        "region": (region or doc.get("region") or country or "").strip().upper()
                  or profile.get("region"),
        "pages": pages,
        "name": name,
        "header_lines": header_lines,
        "headline": getattr(b, "headline", None),
        "sections": sections,
        "warnings": b.warnings,
        "sent": b.sent,
    }


def load(path):
    """(store, doc, root) for the resume.json at `path`, checked. Raises
    short.ShortError for a file that cannot be read, sits outside a workspace, or fails
    its checks - loaded once, so a render building two variants reads the career once."""
    from ..graph import store as S
    from . import short

    doc = short.read(path)
    root = short.workspace(path)
    store = S.load(root)
    fails = short.shape(doc) or short.ids(doc, store)
    if fails:
        raise short.ShortError(f"{path}: " + "; ".join(fails),
                               "`jsk validate` it and fix what it names")
    return store, doc, root


def from_path(path, *, region=None, fmt=None, today=None):
    """(plan, workspace root) for the resume.json at `path`."""
    store, doc, root = load(path)
    return build(store, doc, region=region, fmt=fmt, today=today), root
