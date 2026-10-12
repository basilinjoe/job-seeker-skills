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

# What a SPARQL text over the record opens with: the prefixes the reads name.
SPARQL_PREFIX = (f"PREFIX j: <{J}>\nPREFIX k: <{K}>\nPREFIX c: <{C}>\n"
                 f"PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")

FORMAT = 3

# The reserved graphs of a changeset (TriG). P1 names them; P3 gives them meaning.
OPS = ("set", "add", "retire", "delete")


# --- object kinds ----------------------------------------------------------------------

@dataclass(frozen=True)
class Lit:
    """A literal. `types` are the xsd datatypes allowed; `pattern` must match the
    lexical form in full whatever the type; `lo`/`hi` bound a number."""
    types: tuple = ("string",)
    pattern: str | None = None
    lo: float | None = None
    hi: float | None = None


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
    # Only when the predicate is written in another section than its class.
    section: str | None = None


@dataclass(frozen=True)
class Class:
    name: str
    prefix: str | None   # "prj" for k:prj_x; "=kb" for the singleton k:kb; None for concepts
    kinds: tuple         # the file kinds it may be defined in
    section: str | None  # None: the file's header subject, written before the first banner
    lines: tuple         # tuples of Pred: each inner tuple is one line of the written subject
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
BOOL = Lit(("boolean",))
NUM = Lit(("integer", "decimal"))
YEARMONTH = Lit(("string",), r"\d{4}(-(0[1-9]|1[0-2]))?")
ISO2 = Lit(("string",), r"[A-Z]{2}")
SHA256 = Lit(("string",), r"[0-9a-f]{64}")
URL = Lit(("string",), r"\S+")

# URS values wherever URS defines the thing. Seniority runs most senior first, and
# the order is the ranking: scoring.SENIORITY is this tuple.
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
    # How a number was stated: "15+", "~12", "<1", ">5". Part of the claim - "50+ tenants"
    # is not "50 tenants" - so it is versioned with the value it qualifies.
    "qualifier": ("at-least", "about", "under", "over"),
    "educationLevel": ("isced-5", "isced-6", "isced-7", "isced-8"),
    "credentialState": ("active", "expired", "lapsed"),
    "openSourceRole": ("maintainer", "contributor", "author"),
    "necessity": ("required", "preferred", "implicit"),
    # the assessment. A verdict's order is not its rank: match.RANK ranks the first four, and
    # `indeterminate` is about the record, not the candidate, so it ranks nowhere.
    "verdict": ("satisfied", "partial", "unevidenced", "unsatisfied", "indeterminate"),
    "fit": ("strong", "partial", "poor"),
    "flag": ("listed-names",),
    "eventKind": ("submitted", "acknowledged", "screen-scheduled", "screen-done",
                  "interview-scheduled", "interview-done", "onsite-scheduled", "onsite-done",
                  "offer", "offer-accepted", "rejected", "withdrawn", "no-response",
                  "offer-declined", "follow-up-sent", "note", "referral", "recruiter-contact"),
    # `new` is `jsk kb new`'s r1 (and a --force start-over): neither adopted from a hand
    # edit nor migrated, so neither of those words would say what happened. `migrate` is
    # kept for the r1 entries `jsk migrate` wrote before it was removed. `load` is the
    # one-time import of a workspace laid out as files: its entry hashes what it imported.
    "logBy": ("apply", "confirm", "adopt", "migrate", "fmt", "new", "load"),
    # A graph-native posting or review is drafted a row at a time, and complete once its
    # checks hold (docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md,
    # Rulings 3 and 4). Not `state`: that is a role's, and its values mean something else.
    "progress": ("draft", "complete"),
    # advert.AdvertLine's sections, in advert_lines' words. `offered` is never stored: what a
    # benefits heading lists is not a line a requirement could quote.
    "advertSection": ("qualification", "responsibility", "other"),
    # gaps.txt's row verdicts as the review graph keeps them: `keep` answers a flag, and the
    # rest are `verdict`'s, in its order.
    "reviewVerdict": ("keep", "satisfied", "partial", "unevidenced", "unsatisfied",
                      "indeterminate"),
    # gaps.txt's repeated keyed lines, as the review graph's ordered items.
    "reviewItem": ("short", "surplus", "ask"),
}

ANY = ("*",)

CLASSES = (
    # --- kb: the career ------------------------------------------------------------
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
         Pred("value", NUM, "1", "the value; the bottom of a range", claim=True),
         Pred("upper", NUM, "?", "the top of a range, above value", claim=True),
         Pred("qualifier", Enum("qualifier"), "?",
              "at-least (15+), about (~12), under (<1) or over (>5); on a range, it "
              "qualifies the top", claim=True),
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
        (Pred("about", Ref(ANY), "+", "the entries it is about; k:kb for the career as a whole"),),
        (Pred("question", STR, "1", "the question, ready to ask aloud"),),
        (Pred("asked", DATE, "1", "when it was raised"),
         Pred("answered", DATE, "?", "when it was answered")),
    ), "the gap queue"),
    # Ruling 8: a "no" is a claim like any other - inferred until the person confirms it, and
    # lapsed 365 days after it was said (domain/record/absence.py). Under Open questions, a
    # section every career already prints: a new banner would change every career's hash,
    # and the career_check tool would call every store written outside jsk.
    Class("Absence", "abs", ("kb",), "Open questions", (
        (Pred("concept", Concept(), "1", "what the person said they have not done",
              claim=True),
         Pred("said", DATE, "1", "the day they said it", claim=True)),
        (Pred("answer", TEXT, "1", "their words", claim=True),),
    ), "a person's no: a concept they say they do not hold", claims=True),
    # --- applications/<dir>/posting ---------------------------------------------------
    Class("Posting", "post", ("posting",), "Posting", (
        (Pred("company", STR, "1", "the employer advertising"),
         Pred("title", STR, "1", "the advertised title")),
        (Pred("url", URL, "?", "where it was advertised"),),
        (Pred("seniority", Enum("seniority"), "?", "the level it asks for"),
         Pred("domain", Concept(("Domain",)), "*", "its domains")),
        (Pred("captured", DATE, "1", "the day it was saved"),
         Pred("advert", Lit(("string",), r"posting\.md"), "?",
              "the verbatim advert beside it; absent when its lines are in the graph"),
         Pred("state", Enum("progress"), "?", "draft or complete; absent on a posting built "
                                                "from files, which is complete")),
    ), "a job advertisement"),
    # Ruling 1: the advert as lines, as advert_lines numbers them. No concepts: they follow
    # the vocabulary, which changes, so they are found when the lines are read.
    Class("AdvertLine", "line", ("posting",), "Advert lines", (
        (Pred("posting", Ref(("Posting",)), "1", "the posting it is a line of"),
         Pred("n", Lit(("integer",), lo=1), "1", "its number, from 1, in the advert's order"),
         Pred("section", Enum("advertSection"), "1", "qualification, responsibility or other")),
        (Pred("text", TEXT, "1", "the line, squashed: what a requirement quotes"),),
        (Pred("optional", BOOL, "?", "under an optional heading, or worded optionally"),
         Pred("eligibility", BOOL, "?", "eligibility's words: never a requirement")),
        (Pred("dropped", STR, "?", "the analyst's reason for leaving it out"),),
    ), "one line of an advert"),
    Class("Requirement", "req", ("posting",), "Requirements", (
        (Pred("posting", Ref(("Posting",)), "1", "the posting asking"),),
        (Pred("asked", STR, "1", "the term as the advert wrote it"),
         Pred("necessity", Enum("necessity"), "1", "required, preferred or implicit"),
         Pred("concept", Concept(), "*", "the concepts meant, any one satisfying: one when "
                                          "the label is ambiguous, several when the advert "
                                          "lists alternatives")),
        (Pred("quote", TEXT, "1", "the advert's own words"),),
        (Pred("line", Ref(("AdvertLine",)), "?", "the advert line it quotes"),),
        # Optional, so no format revision: a posting without it reads as before. 60 is far
        # past any career; it stops a typo such as 2018 from reading as a requirement.
        (Pred("years", Lit(("integer",), lo=1, hi=60), "?",
              "the minimum years of experience the advert states, measured against the "
              "record's dates"),),
    ), "one thing a posting asks for"),
    # --- applications/<dir>/application -----------------------------------------------
    Class("Application", "app", ("application",), "Application", (
        (Pred("posting", Ref(("Posting",)), "1", "what it answered"),
         Pred("view", STR, "?", "\"resume\" for a short resume.json; a legacy record's "
                                "URS view")),
        (Pred("submitted", Lit(("date", "boolean"), r"\d{4}-\d{2}-\d{2}|false"), "1",
              "the day it was sent, or false when held back"),
         Pred("channel", STR, "?", "how it was sent")),
        (Pred("document", STR, "*", "a file that was sent"),),
        (Pred("recordSha256", SHA256, "?", "the frozen resume.json's hash - the short "
                                                   "file's own; the words are the documents. "
                                                   "For a graph-native application, which "
                                                   "keeps none, SHA-256 of its stored "
                                                   "selection's selection.canonical text, "
                                                   "UTF-8 (Ruling 7)"),),
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
    # --- applications/<dir>/gaps: the assessment ----------------------------------------
    # Written by code: the match, derived, with the analyst's gaps.txt folded in.
    Class("Assessment", "gap", ("gaps",), "Assessment", (
        (Pred("posting", Ref(("Posting",)), "1", "the posting assessed"),
         Pred("assessed", DATE, "1", "the day it was derived"),
         Pred("fit", Enum("fit"), "1", "strong, partial or poor")),
        (Pred("eligibility", STR, "?", "the analyst's eligibility judgement"),),
        (Pred("fallsShort", TEXT, "?", "where it falls short, most load-bearing first; one "
                                       "item a line"),),
        (Pred("surplus", TEXT, "?", "surplus worth knowing about; one item a line"),),
        (Pred("questions", TEXT, "?", "the questions to ask, in order; one a line"),),
    ), "a posting's gap assessment"),
    Class("Verdict", "vrd", ("gaps",), "Verdicts", (
        (Pred("assessment", Ref(("Assessment",)), "1", "the assessment"),
         Pred("requirement", Ref(("Requirement",)), "1", "the requirement judged")),
        (Pred("matched", Enum("verdict"), "?", "the match's verdict; absent when implicit"),
         Pred("verdict", Enum("verdict"), "1", "the verdict that stands"),
         Pred("flag", Enum("flag"), "*", "a review the derived verdict asks of the analyst")),
        (Pred("evidence", Ref(("Project",)), "*", "the projects behind the verdict"),),
        (Pred("basis", STR, "1", "why the match says what it says"),),
        (Pred("shortfall", STR, "?", "the analyst's reason for lowering it"),),
    ), "one requirement's verdict"),
    # Ruling 5: the questions as nodes, each with the concepts it is about copied from its
    # requirement, so "what have I been asked about Kafka" needs no join. Replaces
    # j:questions for a graph-native application only.
    Class("Ask", "ask", ("gaps",), "Questions", (
        (Pred("assessment", Ref(("Assessment",)), "1", "the assessment asking"),
         Pred("position", Lit(("integer",), lo=1), "1", "its place in the order, from 1")),
        (Pred("question", TEXT, "1", "the question, ready to ask aloud"),),
        (Pred("requirement", Ref(("Requirement",)), "?", "the requirement it is about"),
         Pred("concept", Concept(), "*", "that requirement's concepts")),
    ), "one question the assessment asks"),
    # --- applications/<dir>/review: the analyst's overlay, kept between runs -------------
    # Ruling 4: what gaps.txt held, as triples. It outlives the gaps graph, which a
    # re-derivation rewrites.
    Class("Review", "rvw", ("review",), "Review", (
        (Pred("posting", Ref(("Posting",)), "1", "the posting reviewed"),
         Pred("fit", Enum("fit"), "?", "the analyst's fit, when it is not the match's"),
         Pred("state", Enum("progress"), "?", "draft or complete")),
        (Pred("eligibility", STR, "?", "the analyst's eligibility judgement"),),
    ), "the analyst's review of a posting's assessment"),
    Class("ReviewRow", "rvr", ("review",), "Rows", (
        (Pred("review", Ref(("Review",)), "1", "the review"),
         Pred("requirement", Ref(("Requirement",)), "1", "the requirement it answers")),
        (Pred("verdict", Enum("reviewVerdict"), "1", "keep, or the verdict it lowers to"),
         # Not j:reason, which every class has for a retirement. It becomes the verdict's
         # j:shortfall, so it is named the same.
         Pred("shortfall", STR, "?", "why it was lowered")),
    ), "one gaps.txt row"),
    Class("ReviewItem", "rvi", ("review",), "Items", (
        (Pred("review", Ref(("Review",)), "1", "the review"),
         Pred("kind", Enum("reviewItem"), "1", "short, surplus or ask"),
         Pred("position", Lit(("integer",), lo=1), "1", "its place among its kind, from 1")),
        (Pred("text", TEXT, "1", "what it says"),),
        (Pred("about", Ref(("Requirement",)), "?", "the requirement it is about"),),
    ), "one short, surplus or ask line"),
    # --- applications/<dir>/resume and resumes/<name>/resume: a selection --------------
    # Ruling 6: resume.json as triples. Its keys stay the interchange format: doc_of gives
    # the same dict back (domain/resume/selection.py).
    Class("Selection", "sel", ("resume",), "Selection", (
        (Pred("format", Lit(("string",), r"presentation|ats-maximal"), "?", "the format"),
         Pred("region", Lit(("string",), r"[A-Za-z]{2}"), "?", "the region's profile"),
         Pred("pages", Lit(("integer",), lo=1), "?", "the page budget"),
         Pred("atsPages", Lit(("integer",), lo=1), "?", "the ats-maximal page budget"),
         Pred("floor", Lit(("string",), r"confirmed|inferred|needs-verification|disputed"), "?",
              "the lowest provenance that renders")),
        (Pred("summaryText", TEXT, "?", "the summary"),),
        (Pred("summaryStatus", Lit(("string",), r"confirmed|inferred"), "?",
              "confirmed or inferred"),
         Pred("summaryAnswer", TEXT, "?", "the person's words confirming it"),
         Pred("summarySha", Lit(("string",), r"[0-9a-f]{12}"), "?",
              "the confirmed text's hash, as short.digest gives it")),
        (Pred("headlineText", TEXT, "?", "the headline"),),
        (Pred("headlineStatus", Lit(("string",), r"confirmed|inferred"), "?",
              "confirmed or inferred"),
         Pred("headlineAnswer", TEXT, "?", "the person's words confirming it"),
         Pred("headlineSha", Lit(("string",), r"[0-9a-f]{12}"), "?",
              "the confirmed text's hash, as short.digest gives it")),
    ), "a resume's selection and settings"),
    Class("Pick", "pck", ("resume",), "Picks", (
        (Pred("selection", Ref(("Selection",)), "1", "the selection"),
         Pred("item", Ref(("Achievement", "Position", "Skill")), "1", "the entry picked"),
         Pred("position", Lit(("integer",), lo=1), "1", "its place in its list, from 1")),
        (Pred("alias", STR, "?", "the name a skill renders under: resume.json's names"),),
    ), "one entry a selection lists"),
    # --- log: the career's history -----------------------------------------------------
    Class("LogEntry", "rev", ("log",), "Log", (
        (Pred("revision", Lit(("integer",), lo=1), "1", "counts up from 1"),
         Pred("date", DATE, "1", "the day"),
         Pred("by", Enum("logBy"), "1", "the command that wrote it")),
        (Pred("summary", TEXT, "1", "what changed"),),
        (Pred("touched", Ref(ANY, may_dangle=True), "*", "ids changed"),),
        (Pred("minted", Ref(ANY, may_dangle=True), "*", "ids created"),),
        (Pred("answer", TEXT, "?", "the person's answer, for a confirm"),),
        (Pred("kbSha256", SHA256, "1", "the career's hash after the change, as the writer lays it out"),),
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
    "posting": ("Posting", "Requirements", "Advert lines"),
    "application": ("Application", "Timeline"),
    "gaps": ("Assessment", "Verdicts", "Questions"),
    "review": ("Review", "Rows", "Items"),
    "resume": ("Selection", "Picks"),
    "log": ("Log",),
}
# The career prints every banner, empty or not: the structure is the contract.
ALL_BANNERS = {"kb"}

# The class each file kind holds exactly one of: what makes the file that kind of file.
HEADS = {"kb": "KB", "posting": "Posting", "application": "Application", "gaps": "Assessment",
         "review": "Review", "resume": "Selection"}

# The file names are the import's: a workspace from before the store (infra/legacy_import.py).
FILE_KINDS = {"kb.ttl": "kb", "log.ttl": "log", "posting.ttl": "posting",
              "application.ttl": "application", "gaps.ttl": "gaps",
              "vocabulary.ttl": "vocabulary",
              # a general resume's selection, which the shipped example carries as a file
              # since 6.0 (infra/legacy_import.py reads resumes/<name>/resume.ttl)
              "resume.ttl": "resume",
              # ... and as the store names the graph each file became
              "kb": "kb", "log": "log", "posting": "posting", "application": "application",
              "gaps": "gaps", "vocabulary": "vocabulary",
              # ... and the two kinds that were never files (Ruling 10)
              "review": "review", "resume": "resume"}

SLUG = r"[a-z0-9]+(?:_[a-z0-9]+)*"
ID = re.compile(rf"(?P<prefix>[a-z]+)_(?P<slug>{SLUG})(?:\.v(?P<version>[1-9][0-9]*))?")
CONCEPT_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
POSITIONAL = re.compile(r"_\d+$")


# What places a claim without being one: which project a bullet is under, which employer
# a role was at, which metric a bullet cites, the dates and grades of a qualification.
# The record gate does not read them, but "led a team of 6" under another role is not
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


def class_named(iri):
    """The Class an iri's shape names - for an iri a check has already passed as a jsk
    id. Raises ValueError naming the iri when it is not one: a KeyError(None) said nothing
    of which subject broke the assumption."""
    name = class_of(iri)
    if name is None:
        raise ValueError(f"{iri} is not a jsk id, so it has no class")
    return BY_NAME[name]


def norm(label):
    """A label as it is matched: lowercased, whitespace runs turned into `-`."""
    return re.sub(r"\s+", "-", label.strip().lower())


def stated(value, upper=None, qualifier=None):
    """A metric version's number as a person writes it: "15+", "~12", "<1", ">5",
    "15-20", "~20-30", "300-800+". `value`, `upper` as lexical forms, `qualifier` a
    qualifier's name or None."""
    text = f"{value}-{upper}" if upper is not None else str(value)
    if qualifier == "at-least":
        return text + "+"
    marks = {"about": "~", "under": "<", "over": ">"}
    return (marks.get(qualifier, "") if qualifier else "") + text
