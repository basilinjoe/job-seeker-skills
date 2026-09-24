"""The graph record's format, as data: every class, predicate and enum, in one place.

Everything else reads these tables - the writer takes its section order, subject order and
line layout from them, and the tier-1 rules in shapes.py are generated from them - so the
format has exactly one definition. docs/superpowers/specs/2026-09-24-graph-core-design.md
is the prose version.

Standard library only: importing this must not import pyoxigraph.
"""
import re
from dataclasses import dataclass, field

J = "tag:jsk,2026:ns#"
K = "tag:jsk,2026:id/"
C = "tag:jsk,2026:concept/"
OP = "tag:jsk,2026:op#"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# Where derived triples live in the store. Never written to a file.
DERIVED = J + "derived"

# The writer's prefix block, in this order, always complete. `op` only in changesets.
PREFIXES = (("j", J), ("k", K), ("c", C), ("xsd", XSD))
CHANGESET_PREFIXES = PREFIXES + (("op", OP),)

FORMAT = 3

# The reserved graphs of a changeset (TriG). P1 names them; P3 gives them meaning.
OPS = ("set", "add", "retire", "delete")
OP_BASE = "base"


# --- object kinds ----------------------------------------------------------------------

@dataclass(frozen=True)
class Lit:
    """A literal. `types` are the xsd datatypes allowed; `pattern` must match the
    lexical form in full whatever the type; `lo`/`hi` bound a number."""
    types: tuple = ("string",)
    pattern: str = None
    lo: float = None
    hi: float = None


@dataclass(frozen=True)
class Enum:
    """One of ENUMS[name], written as a j: individual."""
    name: str


@dataclass(frozen=True)
class Ref:
    """A k: id of one of these classes; "*" is any class. `may_dangle` for the log,
    whose entries name ids that may since have been deleted - and concepts, since a
    change to the person's vocabulary is a change to the career like any other."""
    classes: tuple
    may_dangle: bool = False


@dataclass(frozen=True)
class Concept:
    """A c: concept of one of these concept classes."""
    classes: tuple = ("Capability", "Domain", "Technology")


@dataclass(frozen=True)
class Pred:
    name: str
    obj: object
    card: str          # "1" required, "?" optional, "*" zero or more, "+" one or more
    doc: str
    claim: bool = False
    section: str = None   # only when the predicate is written in another section than its class


@dataclass(frozen=True)
class Class:
    name: str
    prefix: str        # "prj" for k:prj_x; "=kb" for the singleton k:kb; None for concepts
    kinds: tuple       # the file kinds it may be defined in
    section: str       # None: the file's header subject, written before the first banner
    lines: tuple       # tuples of Pred: each inner tuple is one line of the written subject
    doc: str
    claims: bool = False   # carries j:provenance
    preds: dict = field(init=False, compare=False)

    def __post_init__(self):
        common = [(Pred("retired", DATE, "?", "the day it stopped belonging on a resume"),
                   Pred("reason", STR, "?", "why it was retired; required with retired")),
                  (Pred("note", TEXT, "*", "free text: anything the ontology has no field for"),)]
        if self.claims:
            common.append((Pred("provenance", Enum("provenance"), "1",
                                "confirmed, inferred, needs-verification or disputed"),))
        lines = tuple(self.lines) + tuple(common)
        object.__setattr__(self, "lines", lines)
        object.__setattr__(self, "preds", {p.name: p for line in lines for p in line})


STR = Lit()
TEXT = Lit()                                   # may hold newlines; written """…"""
DATE = Lit(("date",))
INT = Lit(("integer",))
BOOL = Lit(("boolean",))
NUM = Lit(("integer", "decimal"))
YEARMONTH = Lit(("string",), r"\d{4}(-(0[1-9]|1[0-2]))?")
ISO2 = Lit(("string",), r"[A-Z]{2}")
SHA256 = Lit(("string",), r"[0-9a-f]{64}")
URL = Lit(("string",), r"\S+")

# URS values wherever URS defines the thing; kbindex.SENIORITY for seniority.
ENUMS = {
    "provenance": ("confirmed", "inferred", "needs-verification", "disputed"),
    "workMode": ("onsite", "hybrid", "remote"),
    "authKind": ("citizen", "permanent", "employment-visa", "residence", "student",
                 "working-holiday", "none"),
    "authorization": ("held", "expired", "eligible", "requires-sponsorship"),
    "languageScheme": ("cefr", "ilr", "jlpt", "ielts", "reported"),
    "conceptClass": ("Capability", "Domain", "Technology"),
    "relationship": ("employer", "prospect", "both"),
    "state": ("ended", "ongoing", "unknown"),
    "seniority": ("architecture-ownership", "product-ownership", "platform-design",
                  "team-leadership", "technical-ownership", "hands-on-senior", "hands-on",
                  "junior"),
    "change": ("hire", "promotion", "lateral", "title-change"),
    "engagementKind": ("employment", "contract", "freelance", "internship", "volunteer",
                       "break"),
    "direction": ("increase", "decrease"),
    "metricKind": ("absolute", "delta", "ratio", "duration", "rank", "count"),
    "confidence": ("measured", "estimated", "reported"),
    "educationLevel": ("isced-5", "isced-6", "isced-7", "isced-8"),
    "credentialState": ("active", "expired", "lapsed"),
    "openSourceRole": ("maintainer", "contributor", "author"),
    "necessity": ("required", "preferred", "implicit"),
    "eventKind": ("submitted", "acknowledged", "screen-scheduled", "screen-done",
                  "interview-scheduled", "interview-done", "onsite-scheduled", "onsite-done",
                  "offer", "offer-accepted", "rejected", "withdrawn", "no-response",
                  "offer-declined", "follow-up-sent", "note", "referral", "recruiter-contact"),
    "logBy": ("apply", "confirm", "adopt", "migrate", "fmt"),
}

ANY = ("*",)

CLASSES = (
    # --- kb.ttl ------------------------------------------------------------------------
    Class("KB", "=kb", ("kb",), None, (
        (Pred("format", Lit(("integer",), lo=FORMAT, hi=FORMAT), "1", "the format revision"),
         Pred("name", STR, "1", "whose career this is"),
         Pred("updated", DATE, "1", "the day the last change landed"),
         Pred("revision", Lit(("integer",), lo=1), "?", "the log revision it was written at")),
    ), "the file's header"),
    Class("Person", "=person", ("kb",), "Identity", (
        (Pred("fullName", STR, "1", "the name as it heads a resume", claim=True),
         Pred("givenName", STR, "?", "given name"),
         Pred("familyName", STR, "?", "family name")),
        (Pred("headline", STR, "?", "the one-line professional title", claim=True),),
        (Pred("city", STR, "?", "city"), Pred("region", STR, "?", "state or region"),
         Pred("country", ISO2, "?", "ISO 3166-1 alpha-2"),
         Pred("workMode", Enum("workMode"), "?", "onsite, hybrid or remote")),
        (Pred("email", STR, "*", "an email address"),),
        (Pred("phone", STR, "*", "a phone number"),),
        (Pred("linkedin", STR, "*", "a LinkedIn profile"),),
        (Pred("github", STR, "*", "a GitHub profile"),),
        (Pred("website", STR, "*", "a personal site"),),
        (Pred("primary", STR, "?", "the contact value to lead with; one of those above"),),
        (Pred("positioning", TEXT, "?", "what they are for, in their own words",
              section="Positioning"),),
    ), "the person", claims=True),
    Class("WorkAuthorization", "auth", ("kb",), "Work authorization and languages", (
        (Pred("jurisdiction", STR, "1", "where it applies: a country code, or EU and so on"),
         Pred("kind", Enum("authKind"), "1", "the basis", claim=True),
         Pred("authorization", Enum("authorization"), "1", "its status", claim=True),
         Pred("validUntil", DATE, "?", "when it lapses")),
    ), "a right to work", claims=True),
    Class("Language", "lang", ("kb",), "Work authorization and languages", (
        (Pred("language", Lit(("string",), r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*"), "1",
              "a BCP 47 tag"),
         Pred("native", BOOL, "?", "a first language"),
         Pred("scheme", Enum("languageScheme"), "?", "the scale level is on"),
         Pred("level", STR, "?", "the level on that scale")),
    ), "a spoken language", claims=True),
    Class("Concept", None, ("kb", "vocabulary"), "Vocabulary", (
        (Pred("label", STR, "*", "a name it goes by; matched after normalising"),),
        (Pred("former", STR, "*", "a name it used to go by"),),
        (Pred("isA", Concept(), "*", "counts as this broader concept"),
         Pred("partOf", Concept(), "*", "counts as the whole it is part of"),
         Pred("implies", Concept(), "*", "suggests this; never satisfies a required one")),
        (Pred("distinct", Concept(), "*", "never the same thing, whatever the names say"),),
        (Pred("unlabel", STR, "*", "a shipped label or former label this person drops"),),
        (Pred("unlink", Concept(), "*", "a shipped isA or partOf edge to that concept this person drops"),),
    ), "a matching term: capability, domain or technology"),
    Class("Organisation", "org", ("kb",), "Organisations", (
        (Pred("name", STR, "1", "the organisation's name", claim=True),),
        (Pred("relationship", Enum("relationship"), "1", "employer, prospect or both"),
         Pred("industry", Concept(("Domain",)), "*", "its industries"),
         Pred("size", STR, "?", "headcount band, e.g. 1001-5000")),
    ), "an employer or client", claims=True),
    Class("Position", "pos", ("kb",), "Roles", (
        (Pred("organisation", Ref(("Organisation",)), "1", "where"),),
        (Pred("title", STR, "1", "the title as the employer wrote it", claim=True),
         Pred("functionalTitle", STR, "?", "renders in parentheses; never replaces title")),
        (Pred("start", YEARMONTH, "1", "YYYY-MM or YYYY", claim=True),
         Pred("end", YEARMONTH, "?", "omitted while ongoing", claim=True),
         Pred("state", Enum("state"), "1", "ended, ongoing or unknown")),
        (Pred("seniority", Enum("seniority"), "1", "one of the closed eight", claim=True),
         Pred("change", Enum("change"), "?", "how they came into it"),
         Pred("engagementKind", Enum("engagementKind"), "?", "employment unless stated")),
    ), "a job title held", claims=True),
    Class("Project", "prj", ("kb",), "Projects", (
        (Pred("name", STR, "1", "the project's name", claim=True),),
        (Pred("position", Ref(("Position",)), "?", "the role it was done in"),),
        (Pred("strength", Lit(("integer",), lo=1, hi=5), "1", "evidence quality, 5 flagship"),
         Pred("recency", Lit(("integer",), lo=1950, hi=2100), "1", "the last year worked on"),
         Pred("seniority", Enum("seniority"), "?", "the level it shows", claim=True)),
        (Pred("domain", Concept(("Domain",)), "*", "the domains it was in"),),
        (Pred("uses", Concept(), "*", "tags: what it involved; not evidence"),),
        (Pred("headlineMetric", Ref(("Metric",)), "?", "the number it leads with"),
         Pred("noneQuantified", BOOL, "?", "true when no number exists")),
        (Pred("problem", TEXT, "?", "the problem, in prose"),),
        (Pred("decision", TEXT, "?", "what they decided, in prose"),),
        (Pred("outcome", TEXT, "?", "what changed, in prose"),),
    ), "an engagement or product: the evidence", claims=True),
    Class("Achievement", "ach", ("kb",), "Projects", (
        (Pred("project", Ref(("Project",)), "1", "the project it belongs to"),
         Pred("rank", Lit(("integer",), lo=1), "1", "its order under the project")),
        (Pred("text", TEXT, "1", "the bullet, written once and reused", claim=True),),
        (Pred("cites", Ref(("Metric",)), "*", "the metrics whose numbers it states"),
         Pred("shows", Concept(), "*", "what it is evidence of", claim=True)),
    ), "a bullet", claims=True),
    Class("Metric", "met", ("kb",), "Metrics", (
        (Pred("subject", STR, "1", "what is measured"),
         Pred("unit", STR, "?", "its unit"),
         Pred("direction", Enum("direction"), "?", "which way is better")),
    ), "a measured quantity; its numbers live on its versions"),
    Class("MetricVersion", "met.v", ("kb",), "Metrics", (
        (Pred("of", Ref(("Metric",)), "1", "the metric it is a version of"),),
        (Pred("baseline", NUM, "?", "the value before", claim=True),
         Pred("value", NUM, "1", "the value", claim=True),
         Pred("kind", Enum("metricKind"), "?", "absolute, delta, ratio and so on", claim=True)),
        (Pred("confidence", Enum("confidence"), "1", "measured, estimated or reported"),
         Pred("source", STR, "?", "where the number comes from")),
        (Pred("validFrom", DATE, "?", "when it became true"),
         Pred("validUntil", DATE, "?", "when a later version replaced it")),
    ), "one value of a metric over a period", claims=True),
    Class("Skill", "skill", ("kb",), "Skills", (
        (Pred("name", STR, "1", "the display name"),
         Pred("category", STR, "1", "the group it is shown under"),
         Pred("rank", Lit(("integer",), lo=1), "?", "display order in its category")),
        (Pred("alias", STR, "*", "other names an ATS may look for"),),
    ), "a display skill"),
    Class("Education", "edu", ("kb",), "Education", (
        (Pred("institution", STR, "1", "where", claim=True),),
        (Pred("qualification", STR, "1", "the award", claim=True),
         Pred("field", STR, "?", "the field of study"),
         Pred("level", Enum("educationLevel"), "?", "ISCED level")),
        (Pred("start", YEARMONTH, "?", "YYYY-MM or YYYY"),
         Pred("end", YEARMONTH, "?", "YYYY-MM or YYYY")),
        (Pred("gradeScheme", STR, "?", "the grading scheme"),
         Pred("gradeValue", Lit(("integer", "decimal", "string")), "?", "the grade")),
    ), "a qualification", claims=True),
    Class("Credential", "cred", ("kb",), "Certifications", (
        (Pred("name", STR, "1", "the credential", claim=True),),
        (Pred("issuer", STR, "1", "who issued it", claim=True),
         Pred("issued", YEARMONTH, "?", "YYYY-MM or YYYY", claim=True),
         Pred("expires", YEARMONTH, "?", "YYYY-MM or YYYY"),
         Pred("credentialState", Enum("credentialState"), "1", "active, expired or lapsed")),
        (Pred("url", URL, "?", "where it can be verified"),),
    ), "a certification actually earned", claims=True),
    Class("OpenSource", "os", ("kb",), "Open source", (
        (Pred("name", STR, "1", "the project"),),
        (Pred("url", URL, "1", "where the code is"),
         Pred("role", Enum("openSourceRole"), "1", "their part in it", claim=True)),
    ), "public code", claims=True),
    Class("Question", "q", ("kb",), "Open questions", (
        (Pred("about", Ref(ANY), "1", "the entry it is about"),),
        (Pred("question", STR, "1", "the question, ready to ask aloud"),),
        (Pred("asked", DATE, "1", "when it was raised"),
         Pred("answered", DATE, "?", "when it was answered")),
    ), "the gap queue"),
    # --- posting.ttl -------------------------------------------------------------------
    Class("Posting", "post", ("posting",), "Posting", (
        (Pred("company", STR, "1", "the employer advertising"),
         Pred("title", STR, "1", "the advertised title")),
        (Pred("url", URL, "?", "where it was advertised"),),
        (Pred("seniority", Enum("seniority"), "?", "the level it asks for"),
         Pred("domain", Concept(("Domain",)), "*", "its domains")),
        (Pred("captured", DATE, "1", "the day it was saved"),
         Pred("advert", Lit(("string",), r"posting\.md"), "1", "the verbatim advert beside it")),
    ), "a job advertisement"),
    Class("Requirement", "req", ("posting",), "Requirements", (
        (Pred("posting", Ref(("Posting",)), "1", "the posting asking"),),
        (Pred("asked", STR, "1", "the term as the advert wrote it"),
         Pred("necessity", Enum("necessity"), "1", "required, preferred or implicit"),
         Pred("concept", Concept(), "?", "the concept meant, when the label is ambiguous")),
        (Pred("quote", TEXT, "1", "the advert's own words"),),
    ), "one thing a posting asks for"),
    # --- application.ttl ---------------------------------------------------------------
    Class("Application", "app", ("application",), "Application", (
        (Pred("posting", Ref(("Posting",)), "1", "what it answered"),
         Pred("view", STR, "?", "the URS view it rendered")),
        (Pred("submitted", Lit(("date", "boolean"), r"\d{4}-\d{2}-\d{2}|false"), "1",
              "the day it was sent, or false when held back"),
         Pred("channel", STR, "?", "how it was sent")),
        (Pred("document", STR, "*", "a file that was sent"),),
        (Pred("recordSha256", SHA256, "?", "the frozen resume.json's hash"),),
        (Pred("carried", Ref(("Achievement",)), "*", "bullets it sent"),),
        (Pred("carriedVersion", Ref(("MetricVersion",)), "*", "metric versions it sent"),),
    ), "a submission"),
    Class("Event", "evt", ("application",), "Timeline", (
        (Pred("application", Ref(("Application",)), "1", "the application"),),
        (Pred("date", Lit(("date", "string"), r"\d{4}-\d{2}-\d{2}|unknown"), "1",
              "the day it happened, or unknown"),
         Pred("kind", Enum("eventKind"), "1", "the pipeline vocabulary"),
         Pred("channel", STR, "?", "how"),
         Pred("due", DATE, "?", "a date somebody committed to")),
    ), "something that happened to an application"),
    # --- log.ttl -----------------------------------------------------------------------
    Class("LogEntry", "rev", ("log",), "Log", (
        (Pred("revision", Lit(("integer",), lo=1), "1", "counts up from 1"),
         Pred("date", DATE, "1", "the day"),
         Pred("by", Enum("logBy"), "1", "the command that wrote it")),
        (Pred("summary", TEXT, "1", "what changed"),),
        (Pred("touched", Ref(ANY, may_dangle=True), "*", "ids changed"),),
        (Pred("minted", Ref(ANY, may_dangle=True), "*", "ids created"),),
        (Pred("answer", TEXT, "?", "the person's answer, for a confirm"),),
        (Pred("kbSha256", SHA256, "1", "kb.ttl's hash after the change"),),
    ), "one change to the career"),
)

BY_NAME = {c.name: c for c in CLASSES}
BY_PREFIX = {c.prefix: c for c in CLASSES if c.prefix}

# The sections of each file kind, in the order they are written.
SECTIONS = {
    "kb": ("Identity", "Positioning", "Work authorization and languages", "Vocabulary",
           "Organisations", "Roles", "Projects", "Metrics", "Skills", "Education",
           "Certifications", "Open source", "Open questions"),
    "vocabulary": ("Vocabulary",),
    "posting": ("Posting", "Requirements"),
    "application": ("Application", "Timeline"),
    "log": ("Log",),
}
# kb.ttl prints every banner, empty or not: the structure is the contract.
ALL_BANNERS = {"kb"}

# The class each file kind holds exactly one of: what makes the file that kind of file.
HEADS = {"kb": "KB", "posting": "Posting", "application": "Application"}

FILE_KINDS = {"kb.ttl": "kb", "log.ttl": "log", "posting.ttl": "posting",
              "application.ttl": "application", "vocabulary.ttl": "vocabulary"}

SLUG = r"[a-z0-9]+(?:_[a-z0-9]+)*"
ID = re.compile(rf"(?P<prefix>[a-z]+)_(?P<slug>{SLUG})(?:\.v(?P<version>[1-9][0-9]*))?")
CONCEPT_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
POSITIONAL = re.compile(r"_\d+$")


# What places a claim without being one: which project a bullet is under, which employer
# a role was at, which metric a bullet cites, the dates and grades of a qualification.
# The claims gate does not read them, but "led a team of 6" under another role is not
# what the person confirmed - so changing one resets provenance like a claim does.
PLACES = {"organisation", "position", "project", "of", "cites", "start", "end", "field",
          "level", "gradeScheme", "gradeValue", "expires"}


def resets(cls):
    """The predicates of `cls` whose change makes a confirmed entry unconfirmed."""
    return {p.name for p in cls.preds.values() if p.claim or p.name in PLACES}


def kind_of(path):
    """The file kind a path holds, from its name; None when it is not a record file."""
    name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith(".trig"):
        return "changeset"
    return FILE_KINDS.get(name)


def class_of(iri):
    """The class a k: id names by its shape, or "Concept" for a c: iri; None when the
    iri is neither. A concept's own class (Capability, ...) is stated in the file."""
    if iri.startswith(C):
        return "Concept"
    if not iri.startswith(K):
        return None
    local = iri[len(K):]
    if local in ("kb", "person"):
        return BY_PREFIX["=" + local].name
    m = ID.fullmatch(local)
    if not m:
        return None
    if m["version"]:
        return "MetricVersion" if m["prefix"] == "met" else None
    cls = BY_PREFIX.get(m["prefix"])
    return cls.name if cls and cls.prefix != "met.v" else None


def norm(label):
    """A label as it is matched: lowercased, whitespace runs turned into `-`."""
    return re.sub(r"\s+", "-", label.strip().lower())
