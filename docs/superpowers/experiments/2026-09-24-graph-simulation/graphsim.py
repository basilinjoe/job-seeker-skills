"""Graph simulation: does one workspace graph answer what a model cannot hold by itself?

A throwaway prototype, not product code. It loads a synthetic career - knowledge base,
vocabulary, four postings, three sent applications, a revised metric, an audit log and
a draft resume - into an in-memory Oxigraph store, and runs twelve scenarios. Every
expected answer below was worked out by hand from the data before the queries were
written; a scenario passes only when the graph's answer equals it.

Run:  python graphsim.py            (needs `pip install pyoxigraph`)
"""
import json
import re
import sys
import time
from itertools import combinations

import pyoxigraph as ox

# The repo's own numeral detector, which knows p95, K8s and EC2 are designators rather
# than claims. A real honesty gate would reuse it; so does this prototype.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[4] / "src"))
from jsk.gates.validate_urs import numerals  # noqa: E402

J = "https://jsk.dev/ns#"
C = "https://jsk.dev/concept/"
I = "https://jsk.dev/id/"
XSD_INT = ox.NamedNode("http://www.w3.org/2001/XMLSchema#integer")
XSD_BOOL = ox.NamedNode("http://www.w3.org/2001/XMLSchema#boolean")
PREFIX = f"PREFIX j: <{J}>\nPREFIX c: <{C}>\nPREFIX i: <{I}>\n"
COUNTS_AS = ("isA", "partOf", "implies")
HOP_LIMIT = 2


def month(text):
    y, m = text.split("-")
    return int(y) * 12 + int(m) - 1


def norm(label):
    return re.sub(r"\s+", "-", label.strip().lower())


# --- the data -------------------------------------------------------------------------

VOCAB = {
    # shipped: technologies only, no implies
    "kubernetes": {"kind": "technology", "labels": ["Kubernetes", "K8s"]},
    "aks": {"kind": "technology", "labels": ["AKS", "Azure Kubernetes Service"],
            "isA": ["kubernetes"], "partOf": ["azure"]},
    "eks": {"kind": "technology", "labels": ["EKS", "Amazon EKS"], "isA": ["kubernetes"],
            "partOf": ["aws"]},
    "azure": {"kind": "technology", "labels": ["Azure", "Microsoft Azure"], "isA": ["cloud-platform"]},
    "aws": {"kind": "technology", "labels": ["AWS"], "isA": ["cloud-platform"]},
    "cloud-platform": {"kind": "technology", "labels": ["Cloud platform"], "isA": ["computing"]},
    "computing": {"kind": "technology", "labels": ["Computing"]},
    "entra-id": {"kind": "technology", "labels": ["Entra ID"], "former": [("Azure AD", 2023)],
                 "partOf": ["azure"]},
    "bicep": {"kind": "technology", "labels": ["Bicep"], "partOf": ["azure"]},
    "dotnet": {"kind": "technology", "labels": [".NET", "Dot Net"], "distinct": ["dotnet-framework"]},
    "dotnet-framework": {"kind": "technology", "labels": [".NET Framework"]},
    "csharp": {"kind": "technology", "labels": ["C#"], "partOf": ["dotnet"]},
    "java": {"kind": "technology", "labels": ["Java"], "distinct": ["javascript"]},
    "javascript": {"kind": "technology", "labels": ["JavaScript", "JS"]},
    "angular": {"kind": "technology", "labels": ["Angular"], "distinct": ["angularjs"]},
    "angularjs": {"kind": "technology", "labels": ["AngularJS"]},
    "python": {"kind": "technology", "labels": ["Python"]},
    "fastapi": {"kind": "technology", "labels": ["FastAPI"], "partOf": ["python"]},
    "kafka": {"kind": "technology", "labels": ["Kafka", "Apache Kafka"]},
    "terraform": {"kind": "technology", "labels": ["Terraform"]},
    "sql-server": {"kind": "technology", "labels": ["SQL Server", "MSSQL"]},
    "golang": {"kind": "technology", "labels": ["Go", "Golang"]},
    # the knowledge base's own: capabilities, a domain, and the implies edges
    "infrastructure-as-code": {"kind": "capability", "labels": ["Infrastructure as Code", "IaC"]},
    "event-driven-architecture": {"kind": "capability", "labels": ["Event-driven architecture"]},
    "team-leadership": {"kind": "capability", "labels": ["Team leadership"]},
    "mentoring": {"kind": "capability", "labels": ["Mentoring"], "partOf": ["team-leadership"]},
    "go-game": {"kind": "domain", "labels": ["Go", "Go (board game)"]},
    "__kb_implies": {},
}
KB_IMPLIES = [("terraform", "infrastructure-as-code"), ("bicep", "infrastructure-as-code"),
              ("kafka", "event-driven-architecture")]

PROJECTS = {
    "events": {"strength": 5, "start": "2023-01", "end": "2026-06",
               "uses": ["aks", "kafka", "csharp", "terraform", "team-leadership"]},
    "identity": {"strength": 4, "start": "2021-09", "end": "2022-12",
                 "uses": ["entra-id", "dotnet", "bicep", "kafka"]},
    "portal": {"strength": 3, "start": "2018-01", "end": "2021-05",
               "uses": ["angularjs", "java", "sql-server"]},
    "data": {"strength": 2, "start": "2019-06", "end": "2020-12",
             "uses": ["python", "fastapi", "kubernetes", "terraform"]},
    "game": {"strength": 2, "start": "2014-03", "end": "2016-10", "uses": ["javascript", "go-game"]},
}

BULLETS = {   # bullet: project, concepts its text shows, metric, status
    "b1": ("events", ["aks", "kafka"], "metric_latency", "confirmed"),
    "b2": ("events", ["team-leadership"], "metric_team", "confirmed"),
    "b7": ("events", ["terraform"], None, "confirmed"),
    "b3": ("identity", ["entra-id"], "metric_apps", "confirmed"),
    "b8": ("identity", ["kafka"], None, "confirmed"),
    "b4": ("portal", ["angularjs"], None, "confirmed"),
    "b5": ("data", ["fastapi"], None, "inferred"),
    "b6": ("game", ["go-game"], "metric_players", "confirmed"),
}

METRICS = {   # metric: [(version, baseline, value, unit, valid_from, valid_until)]
    "metric_latency": [("v1", 5, 1, "s", "2024-01", "2026-03"), ("v2", 5, 400, "ms", "2026-03", None)],
    "metric_team": [("v1", None, 6, "engineers", "2023-01", None)],
    "metric_apps": [("v1", None, 40, "applications", "2022-12", None)],
    "metric_players": [("v1", None, 100000, "players", "2016-10", None)],
}

LOG = [("log1", "2026-03", "metric_latency", "p95 latency re-measured after the partition fix")]

POSTINGS = {   # posting: [(label as written, necessity)]
    "contoso": [("K8s", "required"), ("Terraform", "required"), ("Infrastructure as Code", "required"),
                ("Azure AD", "preferred"), ("Go", "preferred"), (".NET", "required"),
                ("EKS", "preferred"), ("K3s", "preferred"), ("Team leadership", "required"),
                ("Mentoring", "implicit")],
    "fabrikam": [(".NET Framework", "required"), ("SQL Server", "required"), ("Angular", "preferred"),
                 ("Terraform", "required")],
    "northwind": [("Python", "required"), ("Kafka", "required"), ("Terraform", "required"),
                  ("Event-driven architecture", "preferred"), ("Computing", "preferred"),
                  ("JavaScript", "preferred")],
    "tailspin": [("Terraform", "required"), ("Kubernetes", "required"), ("AWS", "preferred"),
                 ("Azure Kubernetes", "preferred")],
}

APPLICATIONS = {   # application: posting, sent, [(bullet, metric version it carried)]
    "app1": ("contoso", "2026-02", [("b1", "v1"), ("b2", "v1"), ("b3", "v1")]),
    "app2": ("northwind", "2026-04", [("b1", "v2"), ("b5", None)]),
    "app3": ("tailspin", "2026-01", [("b1", "v1")]),
}

DRAFT = {   # the draft resume for contoso, as the model wrote it
    "bullets": {
        "d1": ("b1", "Cut p95 event latency from 5 minutes to under 1 s on EKS", ["eks", "kafka"]),
        "d2": ("b3", "Migrated 40 applications to Azure AD single sign-on", ["entra-id"]),
        "d3": ("b5", "Built a FastAPI ingestion service", ["fastapi"]),
        "d4": ("b2", "Led 8 engineers across two squads", ["team-leadership"]),
    },
    "skills": {"skill_k8s": ("kubernetes", ["K8s", "AKS", "EKS"]),
               "skill_dotnet": ("dotnet", ["C#", ".NET Framework"])},
    "claims": [("kubernetes", 8)],        # "8 years of Kubernetes" in the summary
}

TODAY = month("2026-09")


# --- building the graph -----------------------------------------------------------------

def build(extra_projects=0):
    s = ox.Store()
    q = []

    def n(ns, x):
        return ox.NamedNode(ns + x)

    def add(sub, pred, obj):
        q.append(ox.Quad(sub, n(J, pred), obj))

    def lit(v):
        if isinstance(v, bool):
            return ox.Literal("true" if v else "false", datatype=XSD_BOOL)
        if isinstance(v, int):
            return ox.Literal(str(v), datatype=XSD_INT)
        return ox.Literal(v)

    for cid, e in VOCAB.items():
        if cid.startswith("__"):
            continue
        cn = n(C, cid)
        add(cn, "kind", lit(e["kind"]))
        add(cn, "label", lit(cid))
        for label in e.get("labels", []):
            add(cn, "label", lit(norm(label)))
            add(cn, "display", lit(label))
        for label, until in e.get("former", []):
            add(cn, "label", lit(norm(label)))
            add(cn, "former", lit(label))
        for kind in COUNTS_AS + ("distinct",):
            for t in e.get(kind, []):
                add(cn, kind, n(C, t))
    for a, b in KB_IMPLIES:
        add(n(C, a), "implies", n(C, b))

    projects = dict(PROJECTS)
    for k in range(extra_projects):           # filler, to measure how results scale
        projects[f"filler{k}"] = {"strength": 1, "start": "2010-01", "end": "2011-01",
                                  "uses": [f"filler-tech-{k}"]}
    for pid, p in projects.items():
        pn = n(I, pid)
        add(pn, "type", lit("Project"))
        add(pn, "strength", lit(p["strength"]))
        add(pn, "start", lit(month(p["start"])))
        add(pn, "end", lit(month(p["end"])))
        for cid in p["uses"]:
            if cid not in VOCAB:
                add(n(C, cid), "kind", lit("tag"))
                add(n(C, cid), "label", lit(cid))
            add(pn, "uses", n(C, cid))
    for bid, (pid, shows, metric, status) in BULLETS.items():
        bn = n(I, bid)
        add(n(I, pid), "bullet", bn)
        add(bn, "status", lit(status))
        for cid in shows:
            add(bn, "shows", n(C, cid))
        if metric:
            add(bn, "cites", n(I, metric))
    for mid, versions in METRICS.items():
        for vid, base, value, unit, start, until in versions:
            vn = n(I, f"{mid}.{vid}")
            add(n(I, mid), "version", vn)
            add(vn, "value", lit(value))
            if base is not None:
                add(vn, "baseline", lit(base))
            add(vn, "unit", lit(unit))
            add(vn, "validFrom", lit(month(start)))
            if until:
                add(vn, "validUntil", lit(month(until)))
    for lid, when, mid, note in LOG:
        ln = n(I, lid)
        add(ln, "date", lit(month(when)))
        add(ln, "changed", n(I, mid))
        add(ln, "note", lit(note))
    for post, reqs in POSTINGS.items():
        pn = n(I, post)
        for k, (text, necessity) in enumerate(reqs):
            rn = n(I, f"{post}.r{k}")
            add(pn, "requires", rn)
            add(rn, "text", lit(text))
            add(rn, "asked", lit(norm(text)))    # not j:label: a requirement is not a concept
            add(rn, "necessity", lit(necessity))
    for aid, (post, sent, uses) in APPLICATIONS.items():
        an = n(I, aid)
        add(an, "posting", n(I, post))
        add(an, "sent", lit(month(sent)))
        for k, (bid, vid) in enumerate(uses):
            un = n(I, f"{aid}.u{k}")
            add(an, "carried", un)
            add(un, "bullet", n(I, bid))
            if vid:
                add(un, "metricVersion", n(I, f"{BULLETS[bid][2]}.{vid}"))
    s.extend(q)
    materialise_paths(s)
    return s


def materialise_paths(s):
    """The counts-as closure within the hop limit, written back into the graph as Path
    nodes - the one piece of inference every later query joins on."""
    kinds = ", ".join(f"j:{k}" for k in COUNTS_AS)
    s.update(PREFIX + """
        INSERT { ?p j:from ?a ; j:to ?a ; j:hops 0 ; j:implied false ; j:via ?a }
        WHERE { ?a j:kind ?k . BIND(IRI(CONCAT(STR(?a), "/path0")) AS ?p) }""")
    s.update(PREFIX + f"""
        INSERT {{ ?p j:from ?a ; j:to ?b ; j:hops 1 ; j:implied ?imp ; j:via ?a }}
        WHERE {{ ?a ?k ?b . FILTER(?k IN ({kinds}))
                 BIND(?k = j:implies AS ?imp)
                 BIND(IRI(CONCAT(STR(?a), "/p1/", STRAFTER(STR(?b), "concept/"))) AS ?p) }}""")
    s.update(PREFIX + f"""
        INSERT {{ ?p j:from ?a ; j:to ?b ; j:hops 2 ; j:implied ?imp ; j:via ?m }}
        WHERE {{ ?a ?k1 ?m . ?m ?k2 ?b . FILTER(?k1 IN ({kinds}) && ?k2 IN ({kinds}))
                 BIND(?k1 = j:implies || ?k2 = j:implies AS ?imp)
                 BIND(IRI(CONCAT(STR(?a), "/p2/", STRAFTER(STR(?m), "concept/"), "/",
                                 STRAFTER(STR(?b), "concept/"))) AS ?p) }}""")


def rows(s, sparql):
    out = []
    for sol in s.query(PREFIX + sparql):
        row = []
        for v in sol:
            if v is None:
                row.append(None)
            elif isinstance(v, ox.NamedNode):
                row.append(v.value.rsplit("/", 1)[-1])
            elif isinstance(v, ox.Literal) and v.datatype == XSD_INT:
                row.append(int(v.value))
            elif isinstance(v, ox.Literal) and v.datatype == XSD_BOOL:
                row.append(v.value == "true")
            else:
                row.append(v.value)
        out.append(tuple(row))
    return out


def ask(s, sparql):
    return bool(s.query(PREFIX + sparql))


# --- the queries --------------------------------------------------------------------------

def resolve(s, post):
    """Each requirement's concepts: one, several (ambiguous) or none (candidate)."""
    got = {}
    for text, c in rows(s, f"""
        SELECT ?text ?c WHERE {{ i:{post} j:requires ?r . ?r j:text ?text ; j:asked ?l .
                                 OPTIONAL {{ ?c j:label ?l }} }}"""):
        got.setdefault(text, set())
        if c:
            got[text].add(c)
    return got


def match(s, post):
    """The posting joined with the knowledge base through the counts-as paths.

    -> {requirement text: {"matched": {project: via}, "near": {project: why}, "state": ...}}
    """
    reqs = {t: n for t, n in POSTINGS[post]}
    concepts = resolve(s, post)
    out = {}
    for text, necessity in reqs.items():
        found = concepts[text]
        entry = {"necessity": necessity, "matched": {}, "near": {}}
        out[text] = entry
        if necessity == "implicit":
            entry["state"] = "implicit"
            continue
        if len(found) != 1:
            entry["state"] = "ambiguous" if found else "candidate"
            entry["concepts"] = sorted(found)
            continue
        want = next(iter(found))
        entry["concept"] = want
        for proj, have, hops, implied in rows(s, f"""
            SELECT ?proj ?have ?hops ?implied WHERE {{
              ?proj j:uses ?have . ?p j:from ?have ; j:to c:{want} ; j:hops ?hops ; j:implied ?implied }}"""):
            if implied and necessity == "required":
                entry["near"].setdefault(proj, f"implied by {have}; confirm")
                continue
            best = entry["matched"].get(proj)
            if best is None or (hops, implied) < (best[1], best[2]):
                entry["matched"][proj] = (have, hops, implied)
        for proj, have in rows(s, f"""
            SELECT ?proj ?have WHERE {{
              ?proj j:uses ?have . ?p j:from c:{want} ; j:to ?have ; j:hops ?h ; j:implied false .
              FILTER(?h > 0) }}"""):
            if proj not in entry["matched"]:
                entry["near"].setdefault(proj, f"holds broader {have}")
        entry["state"] = "matched" if entry["matched"] else "missing"
    return out


def evidence(s, proj, concept):
    """confirmed: a confirmed bullet shows the concept or a narrower one.
    unconfirmed: only an inferred bullet does. tag: only the project's tag does."""
    got = rows(s, f"""
        SELECT ?status WHERE {{ i:{proj} j:bullet ?b . ?b j:status ?status ; j:shows ?m .
                                ?p j:from ?m ; j:to c:{concept} ; j:implied false }}""")
    statuses = {g[0] for g in got}
    return "confirmed" if "confirmed" in statuses else "unconfirmed" if statuses else "tag"


def score(s, post, proj, result):
    weights = {"required": 3, "preferred": 1, "implicit": 0}
    total = sum(weights[e["necessity"]] for e in result.values() if proj in e["matched"])
    strength, end = rows(s, f"SELECT ?s ?e WHERE {{ i:{proj} j:strength ?s ; j:end ?e }}")[0]
    age = TODAY // 12 - end // 12
    return total + 2 * strength + (1 if age <= 3 else 0.5 if age <= 6 else 0)


def cover(s, post, result, budget):
    """The smallest set of projects, within the budget, carrying every required concept."""
    required = {t for t, e in result.items() if e["necessity"] == "required" and e.get("concept")}
    carries = {}
    for text in required:
        for proj in result[text]["matched"]:
            carries.setdefault(proj, set()).add(text)
    reachable = set().union(*carries.values()) if carries else set()
    for size in range(1, budget + 1):
        for combo in combinations(sorted(carries), size):
            if set().union(*(carries[p] for p in combo)) >= reachable:
                return list(combo), sorted(required - reachable)
    return None, sorted(required - reachable)


def honesty(s):
    """Every draft claim against the graph: concepts the evidence holds, the metric's
    current version, the claim's status, aliases the person holds, stated years."""
    flags = []
    for did, (bid, text, shows) in DRAFT["bullets"].items():
        proj, _, metric, status = BULLETS[bid]
        for cid in shows:
            held = ask(s, f"""ASK {{ i:{proj} j:uses|j:bullet/j:shows ?h .
                                     ?p j:from ?h ; j:to c:{cid} ; j:implied false }}""")
            if not held:
                flags.append((did, "names-unheld", cid))
        if status != "confirmed":
            flags.append((did, "unconfirmed-source", bid))
        numbers = {int(v) for v, _, _ in numerals(text)}
        if metric:
            current = rows(s, f"""SELECT ?base ?value WHERE {{ i:{metric} j:version ?v .
                                   OPTIONAL {{ ?v j:baseline ?base }} ?v j:value ?value .
                                   FILTER NOT EXISTS {{ ?v j:validUntil ?u }} }}""")
            allowed = {x for r in current for x in r if x is not None}
            for num in sorted(numbers - allowed):
                old = rows(s, f"""SELECT ?v WHERE {{ i:{metric} j:version ?v . ?v j:value {num} ;
                                                    j:validUntil ?u }}""")
                flags.append((did, "superseded-number" if old else "untraced-number", num))
    for sid, (cid, aliases) in DRAFT["skills"].items():
        for alias in aliases:
            named = {c for (c,) in rows(s, f'SELECT ?c WHERE {{ ?c j:label "{norm(alias)}" }}')}
            held = any(ask(s, f"""ASK {{ ?proj j:uses|j:bullet/j:shows ?h .
                                         ?p j:from ?h ; j:to c:{c} ; j:implied false }}""")
                       for c in named)
            if not held:
                flags.append((sid, "alias-unheld", alias))
    for cid, years in DRAFT["claims"]:
        months = experience(s, cid)
        if years * 12 > months:
            flags.append(("summary", "overstated-years", f"{cid}: claims {years}y, evidence {months // 12}y{months % 12}m"))
    return sorted(flags, key=str)


def experience(s, cid):
    """Months covered by projects holding the concept or a narrower one - overlaps once."""
    spans = sorted(set(rows(s, f"""SELECT ?start ?end WHERE {{ ?proj j:uses ?h ; j:start ?start ; j:end ?end .
                                    ?p j:from ?h ; j:to c:{cid} ; j:implied false }}""")))
    total, cursor = 0, None
    for a, b in spans:
        if cursor is not None and a <= cursor:
            if b > cursor:
                total += b - cursor
                cursor = b
            continue
        total += b - a + 1
        cursor = b
    return total


def stale(s):
    """Applications that carried a metric version since superseded, with the log's reason."""
    return sorted(rows(s, """SELECT ?app ?metric ?why WHERE {
        ?app j:carried ?u . ?u j:metricVersion ?v . ?metric j:version ?v . ?v j:validUntil ?until .
        ?log j:changed ?metric ; j:note ?why ; j:date ?d . FILTER(?d >= ?until) }"""))


def inconsistent(s):
    """Metrics sent with different values in different applications."""
    sent = {}
    for metric, value in rows(s, """SELECT DISTINCT ?metric ?value WHERE {
            ?app j:carried ?u . ?u j:metricVersion ?v . ?metric j:version ?v . ?v j:value ?value }"""):
        sent.setdefault(metric, set()).add(value)
    return sorted((m, sorted(v)) for m, v in sent.items() if len(v) > 1)


def demand(s):
    """Per concept required anywhere: how many postings, and the best evidence held."""
    table = {}
    for post in POSTINGS:
        result = match(s, post)
        for text, e in result.items():
            if e["necessity"] != "required" or not e.get("concept"):
                continue
            row = table.setdefault(e["concept"], {"postings": set(), "evidence": "none"})
            row["postings"].add(post)
            levels = [evidence(s, p, e["concept"]) for p in e["matched"]]
            if not levels and e["near"]:
                levels = ["implied" if any("implied" in w for w in e["near"].values()) else "none"]
            rank = ["none", "implied", "tag", "unconfirmed", "confirmed"]
            best = max(levels, key=rank.index) if levels else "none"
            row["evidence"] = max([row["evidence"], best], key=rank.index)
    return {c: (len(r["postings"]), r["evidence"]) for c, r in table.items()}


def questions(s, post):
    """The questions a tailoring round should ask, derived from the match - not invented."""
    out = []
    for text, e in match(s, post).items():
        if e["state"] == "ambiguous":
            out.append((text, "ambiguous", "|".join(e["concepts"])))
        elif e["state"] == "candidate":
            out.append((text, "unknown-term", ""))
        elif e["state"] == "missing" and e["near"]:
            kinds = {"implied" if "implied" in w else "broader" for w in e["near"].values()}
            out.append((text, "implied" if "implied" in kinds else "broader-held",
                        ",".join(sorted(e["near"]))))
        elif e["state"] == "matched":
            levels = {p: evidence(s, p, e["concept"]) for p in e["matched"]}
            if "confirmed" not in levels.values():
                out.append((text, "tag-only", ",".join(sorted(levels))))
    return sorted(out)


def validate(s):
    kinds = "|".join(f"j:{k}" for k in COUNTS_AS)
    return {"cycle": ask(s, f"ASK {{ ?a ({kinds})+ ?a }}"),
            "distinct-crossed": ask(s, f"ASK {{ ?a j:distinct ?b . {{ ?a ({kinds})+ ?b }} UNION {{ ?b ({kinds})+ ?a }} }}")}


# --- baselines: what matching looks like without the graph --------------------------------

def baseline_pairs(kind):
    """exact: the requirement's text equals a project tag. fuzzy: either contains the other,
    over tags and their display labels - roughly what "similar words" matching does."""
    pairs = set()
    for post, reqs in POSTINGS.items():
        for text, necessity in reqs:
            if necessity == "implicit":
                continue
            r = norm(text)
            for proj, p in PROJECTS.items():
                names = set()
                for cid in p["uses"]:
                    names.add(cid)
                    names |= {norm(x) for x in VOCAB.get(cid, {}).get("labels", [])}
                hit = (r in p["uses"]) if kind == "exact" else any(r in x or x in r for x in names)
                if hit:
                    pairs.add((post, text, proj))
    return pairs


TRUTH = {   # worked by hand: which projects honestly carry each requirement
    ("contoso", "K8s"): {"events", "data"}, ("contoso", "Terraform"): {"events", "data"},
    ("contoso", "Infrastructure as Code"): set(), ("contoso", "Azure AD"): {"identity"},
    ("contoso", "Go"): set(), ("contoso", ".NET"): {"events", "identity"}, ("contoso", "EKS"): set(),
    ("contoso", "K3s"): set(), ("contoso", "Team leadership"): {"events"},
    ("fabrikam", ".NET Framework"): set(), ("fabrikam", "SQL Server"): {"portal"},
    ("fabrikam", "Angular"): set(), ("fabrikam", "Terraform"): {"events", "data"},
    ("northwind", "Python"): {"data"}, ("northwind", "Kafka"): {"events", "identity"},
    ("northwind", "Terraform"): {"events", "data"},
    ("northwind", "Event-driven architecture"): {"events", "identity"},
    ("northwind", "Computing"): set(), ("northwind", "JavaScript"): {"game"},
    ("tailspin", "Terraform"): {"events", "data"}, ("tailspin", "Kubernetes"): {"events", "data"},
    ("tailspin", "AWS"): set(),
    ("tailspin", "Azure Kubernetes"): {"events"},   # a true synonym nobody declared
}


def precision_recall(pairs):
    truth = {(p, t, proj) for (p, t), projs in TRUTH.items() for proj in projs}
    tp = len(pairs & truth)
    return (round(tp / len(pairs), 3) if pairs else 1.0, round(tp / len(truth), 3),
            sorted(pairs - truth), sorted(truth - pairs))


# --- the scenarios ------------------------------------------------------------------------

def scenarios():
    s = build()
    results = []

    def check(name, got, want, why):
        results.append((name, got == want, got, want, why))

    check("S0 the graph validates", validate(s), {"cycle": False, "distinct-crossed": False},
          "no cycle, no counts-as path across a distinct wall")

    r = resolve(s, "contoso")
    check("S1 labels resolve; ambiguity and unknowns are named",
          {t: sorted(c) for t, c in r.items() if t in ("K8s", ".NET", "Azure AD", "Go", "K3s")},
          {"K8s": ["kubernetes"], ".NET": ["dotnet"], "Azure AD": ["entra-id"],
           "Go": ["go-game", "golang"], "K3s": []},
          "K8s, .NET and the former label Azure AD resolve; Go names two concepts; K3s none")

    m = match(s, "contoso")
    check("S2 narrower counts as broader, one way only",
          (m["K8s"]["matched"].get("events"), m["EKS"]["state"], m["EKS"]["near"]),
          (("aks", 1, False), "missing", {"data": "holds broader kubernetes"}),
          "AKS work is Kubernetes work; Kubernetes work is not EKS work - a near miss")

    n = match(s, "northwind")
    check("S3 the hop limit", (n["Computing"]["state"], n["Computing"]["matched"]),
          ("missing", {}), "aks -> azure -> cloud-platform -> computing is three hops")

    f = match(s, "fabrikam")
    check("S4 distinct walls", (f[".NET Framework"]["matched"], f["Angular"]["matched"]),
          ({}, {}), "dotnet is not dotnet-framework; angularjs is not angular")

    check("S5 implies never carries a required requirement",
          (m["Infrastructure as Code"]["state"], sorted(m["Infrastructure as Code"]["near"]),
           sorted(n["Event-driven architecture"]["matched"])),
          ("missing", ["data", "events", "identity"], ["events", "identity"]),
          "IaC is required: terraform/bicep only imply it. EDA is preferred: kafka carries it")

    graph_pairs = {(p, t, proj) for p in POSTINGS for t, e in match(s, p).items()
                   for proj in e["matched"]}
    stats = {k: precision_recall(v)[:2] for k, v in
             (("graph", graph_pairs), ("exact", baseline_pairs("exact")), ("fuzzy", baseline_pairs("fuzzy")))}
    check("S6 precision and recall against hand-worked truth", stats["graph"], (1.0, 0.958),
          "no false match; one miss - 'Azure Kubernetes', a synonym nobody declared")

    budget_top = sorted(PROJECTS, key=lambda p: -score(s, "northwind", p, n))[:2]
    chosen, uncovered = cover(s, "northwind", n, budget=2)
    check("S7 cover the posting, not just the top scores",
          (budget_top, chosen, uncovered), (["events", "identity"], ["data", "events"], []),
          "top-2 by score leave Python uncovered; the smallest cover is events + data")

    check("S8 honesty gate on the draft resume", honesty(s), sorted([
        ("d1", "names-unheld", "eks"),
        ("d1", "superseded-number", 1),
        ("d3", "unconfirmed-source", "b5"),
        ("d4", "untraced-number", 8),
        ("skill_dotnet", "alias-unheld", ".NET Framework"),
        ("skill_k8s", "alias-unheld", "EKS"),
        ("summary", "overstated-years", "kubernetes: claims 8y, evidence 5y1m"),
    ], key=str), "EKS never held; '1 s' is the superseded figure; b5 is inferred; 8 is not 6; "
                 "AKS alias is fine (held), EKS and .NET Framework are not; 8 years vs 61 months")

    check("S9 what went out with the old number, and why",
          (stale(s), inconsistent(s)),
          ([("app1", "metric_latency", "p95 latency re-measured after the partition fix"),
            ("app3", "metric_latency", "p95 latency re-measured after the partition fix")],
           [("metric_latency", [1, 400])]),
          "app1 and app3 sent 1 s before the March revision; app2 sent 400 ms")

    check("S10 demand across every posting", demand(s), {
        "kubernetes": (2, "confirmed"), "terraform": (4, "confirmed"),
        "infrastructure-as-code": (1, "implied"), "dotnet": (1, "tag"),
        "team-leadership": (1, "confirmed"), "dotnet-framework": (1, "none"),
        "sql-server": (1, "tag"), "python": (1, "unconfirmed"), "kafka": (1, "confirmed")},
          "terraform is asked for by all four and evidenced; .NET, SQL Server and Python are "
          "required but only tagged or inferred - what to capture next")

    check("S11 the questions a tailoring round should ask", questions(s, "contoso"), sorted([
        ("Go", "ambiguous", "go-game|golang"), ("K3s", "unknown-term", ""),
        ("EKS", "broader-held", "data"), ("Infrastructure as Code", "implied", "data,events,identity"),
        (".NET", "tag-only", "events,identity")]),
          "every question comes from a named gap in the join, none from the model's imagination")

    # S12: what an agent reads. Whole knowledge base vs the match result, as the KB grows.
    sizes = []
    for extra in (0, 50, 200):
        big = build(extra)
        kb_bytes = len(json.dumps({"projects": {**PROJECTS, **{f"filler{k}": {} for k in range(extra)}},
                                   "bullets": BULLETS, "metrics": METRICS, "vocab": VOCAB}))
        kb_bytes += extra * 1200     # a filler project's prose, at the fixture's average
        start = time.perf_counter()
        res = match(big, "contoso")
        ms = (time.perf_counter() - start) * 1000
        sizes.append((extra + len(PROJECTS), kb_bytes // 4,
                      len(json.dumps(res, default=str)) // 4, round(ms)))
    flat = len({x[2] for x in sizes}) == 1
    check("S12 the agent's read stays flat as the career grows", flat, True,
          "tokens: " + "; ".join(f"{p} projects: KB ~{k}, match ~{r} ({ms} ms)" for p, k, r, ms in sizes))

    return results, stats


def main():
    results, stats = scenarios()
    width = max(len(r[0]) for r in results)
    for name, ok, got, want, why in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {why}")
        if not ok:
            print(f"      got:  {got}\n      want: {want}")
    print()
    for k, (p, r) in stats.items():
        print(f"{k:6} precision {p:.3f}  recall {r:.3f}")
    fuzzy = precision_recall(baseline_pairs("fuzzy"))
    exact = precision_recall(baseline_pairs("exact"))
    print(f"\nfuzzy false matches: {fuzzy[2]}")
    print(f"exact misses: {exact[3]}")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
