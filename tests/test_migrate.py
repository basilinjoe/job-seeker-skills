"""jsk migrate: a Markdown knowledge base moved to the graph record, once, provably whole.

Every refusal has a test, and so does the promise the command exists for: what was
read from the Markdown is what the graph holds, and nothing it read from is deleted.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import CLI, REPO_ROOT, kb_text, run, scaffold_markdown_kb

from jsk import migrate
from jsk.graph import ontology as O
from jsk.graph import record as R
from jsk.graph import store as S

FENCE = "```"

# Every section kb-spec.md defines, each holding the shapes it allows - and a few things
# it does not: a key no field holds, a section nobody defined, a country written out.
EVERY_SECTION = f"""---
kb: 2
name: Priya Raman
updated: 2026-09-08
---

# Career knowledge base - Priya Raman

<!-- The template's guidance, which is not the career. -->

## Identity

{FENCE}yaml
full_name: Priya Raman
given_name: Priya
family_name: Raman
headline: Principal Solution Architect
location:
  city: Melbourne
  region: VIC
  country: Australia
  mode: hybrid
contacts:
  - kind: email
    value: priya.raman@example.com
    primary: true
  - kind: phone
    value: "+61 400 000 000"
  - kind: linkedin
    value: linkedin.com/in/priyaraman
  - kind: github
    value: github.com/priyaraman
  - kind: mastodon
    value: "@priya@example.social"
pronouns: she/her
status: confirmed
{FENCE}

## Positioning

Architect who turns regulated estates into event-driven platforms.

Strongest in healthcare and aged care.

## Work authorization and languages

{FENCE}yaml
work_authorization:
  - jurisdiction: AU
    kind: citizen
    status: held
  - jurisdiction: AE
    kind: work-visa
    status: requires-sponsorship
    label: UAE employment visa
languages:
  - language: English
    native: true
  - language: ta
    native: true
    status: confirmed
{FENCE}

## Vocabulary

### Capabilities

- `ai-platform-architecture`
- `data-sovereignty` - keeping data in the jurisdiction it belongs to
- `team-leadership`

### Domains

- `healthcare`
- `aged-care`

### Seniority (fixed vocabulary - do not extend)

`architecture-ownership` - `product-ownership` - `platform-design` -
`team-leadership` - `technical-ownership` - `hands-on-senior` - `hands-on` - `junior`

## Organisations

### Meridian Health `org_meridian`

{FENCE}yaml
id: org_meridian
relationship: employer
industry: [healthcare]
size: 1001-5000
status: confirmed
{FENCE}

### Northbridge Digital `org_northbridge`

{FENCE}yaml
id: org_northbridge
industry: [healthcare]
status: confirmed
{FENCE}

## Roles

### Principal Solution Architect - Meridian Health `role_meridian_principal`

{FENCE}yaml
id: role_meridian_principal
organisation: org_meridian
title: Principal Solution Architect
functional_title:
start: 2023-07
end:
state: ongoing
seniority: architecture-ownership
change: promotion
status: confirmed
{FENCE}

### Solution Architect - Northbridge `role_northbridge_architect`

{FENCE}yaml
id: role_northbridge_architect
organisation: org_northbridge
title: Solution Architect
start: 2016-08
end: 2023-06
state: ended
seniority: platform-design
change: hire
status: confirmed
{FENCE}

## Projects

### Clinical event pipeline `proj_clinical_events`

{FENCE}yaml
id: proj_clinical_events
role: role_meridian_principal
strength: 5
recency: 2026
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture, data-sovereignty]
technologies: [azure-ai-foundry, bicep, kafka, "Node.js"]
headline_metric: metric_event_latency
status: confirmed
{FENCE}

**The problem.** The legacy scheduler could not express care-plan constraints, so every site
maintained its own spreadsheet beside it.

**What I decided.** Event-sourced the schedule rather than versioning the table.

**What changed.** Propagation fell from five minutes to under a second.

**Bullets**

- Cut p95 clinical event latency from 5 minutes to under 1 second across 40,000 daily
  ingestion jobs.
  - metric: metric_event_latency
  - status: confirmed
- Led a team of 6 engineers through the migration with no unplanned downtime.
  - metric: metric_team
  - status: confirmed
- Wrote the audit trail design that the regulator accepted first time.

### Intranet refresh `proj_intranet`

{FENCE}yaml
id: proj_intranet
role: role_northbridge_architect
strength: 1
recency: 2017
seniority: hands-on
capabilities: []
technologies: [dotnet]
headline_metric: none-quantified
status: confirmed
retired: true
{FENCE}

## Metrics

| id | subject | baseline | value | unit | direction | confidence | source | status |
|---|---|---|---|---|---|---|---|---|
| metric_event_latency | p95 clinical event latency | 5 | 1 | min→s | decrease | measured | Grafana dashboard | confirmed |
| metric_team | engineers led | | 6 | engineers | | self-reported | org chart | confirmed |
| metric_jobs | daily ingestion jobs | | 40,000 | jobs | | estimated | | inferred |

## Skills

### cloud-platform

- Azure `skill_azure` — aliases: Microsoft Azure, Azure AI Foundry, Bicep

### language

- C# / .NET `skill_dotnet` — aliases: C#, .NET, ASP.NET Core
- Python

## Education

### Master of Engineering, Computer Science `edu_meng`

{FENCE}yaml
id: edu_meng
institution: Anna University
qualification: Master of Engineering
field: Computer Science
level: isced-7
start: 2010
end: 2012
grade:
  scheme: in-cgpa-10
  value: 8.40
status: confirmed
{FENCE}

## Certifications

- Azure Solutions Architect Expert `cred_azarch`
  - issuer: Microsoft
  - issued: 2024-05
  - status: active
- Certified Kubernetes Administrator `cred_cka`
  - issuer: CNCF
  - issued: 2021-02
  - expires: 2024-02
  - status: confirmed

## Open source

- carbon-aware-scheduler `os_carbon_scheduler`
  - url: https://github.com/example/carbon-aware-scheduler
  - role: maintainer
  - status: confirmed

## Talks

A conference talk on event sourcing in aged care, 2025.

## Open questions

| id | question | about | asked | answered |
|---|---|---|---|---|
| q_latency_source | Where did the 5-minute baseline come from? | metric_event_latency | 2026-09-08 | |
| q_team_size | Was the team 6 throughout, or at peak? | proj_clinical_events | 2026-08-12 | 2026-08-14 |
"""

LOG_MD = """# Log - Priya Raman

| date | what changed |
|---|---|
| 2026-09-01 | Knowledge base created. |
| 2026-09-08 | Added the clinical event pipeline. |
"""

POSTING_MD = """---
company: Acme Health
title: "Platform Engineer: Core"
url: https://acme.example/jobs/42
seniority: platform-design
domains: [healthcare]
captured: 2026-09-08
requirements:
  - value: kafka
    kind: technology
    necessity: required
    label: "Kafka in production"
  - value: team-leadership
    kind: capability
    necessity: preferred
    label: grows the people around them
  - value: quantum-annealing
    kind: capability
    necessity: preferred
    label: something the advert never said
---

# Platform Engineer at Acme Health

- Kafka in production, at scale.
- Team leadership a plus.
"""

APPLICATION_MD = """---
company: Acme Health
title: "Platform Engineer: Core"
view: view_default
submitted: 2026-09-10
channel: company site
documents:
  - Priya_Raman_Resume.pdf
---

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-09-10 | submitted | company site | | |
| 2026-09-15 | screen-scheduled | email | Phone screen, 30 min | 2026-09-18 |
| unknown | phone-screen | | recruiter called | |
"""

BULLET = ("Cut p95 clinical event latency from 5 minutes to under 1 second across 40,000 daily "
          "ingestion jobs.")

RESUME = {"urs": "1.0.0", "engagements": [{"id": "eng_meridian", "achievements": [
    {"id": "ach_latency", "text": BULLET, "provenance": {"status": "confirmed"}},
    {"id": "ach_retuned", "text": "Something the knowledge base never said."}]}]}

IN_PROGRESS = """---
company: Globex
title: Staff Engineer
captured: 2026-09-20
---

Staff Engineer at Globex. Terraform everywhere.
"""


def workspace(root, kb=EVERY_SECTION, apps=True):
    root = Path(root)
    (root / "user-knowledgebase.md").write_text(kb, encoding="utf-8", newline="\n")
    (root / "log.md").write_text(LOG_MD, encoding="utf-8", newline="\n")
    if apps:
        sent = root / "applications" / "2026-09-10-acme-platform-engineer"
        sent.mkdir(parents=True)
        (sent / "posting.md").write_text(POSTING_MD, encoding="utf-8", newline="\n")
        (sent / "application.md").write_text(APPLICATION_MD, encoding="utf-8", newline="\n")
        (sent / "resume.json").write_text(json.dumps(RESUME, indent=2), encoding="utf-8")
        (sent / "gaps.md").write_text("# Gaps\n", encoding="utf-8")
        draft = root / "applications" / "globex-staff-engineer"
        draft.mkdir(parents=True)
        (draft / "posting.md").write_text(IN_PROGRESS, encoding="utf-8", newline="\n")
    return root


def migrated(root, *args):
    """(exit code, output) of `jsk migrate`, in process."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = migrate.main([str(Path(root) / "user-knowledgebase.md"), *args])
    return code, out.getvalue()


def snapshot(root):
    """{relative path: sha256} of every file under root."""
    out = {}
    for dirpath, _, files in os.walk(root):
        for f in files:
            p = Path(dirpath) / f
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def triples(root, file=R.KB):
    """{(subject curie, predicate name): {object values}} of one written file."""
    from jsk.graph.writer import curie
    store = S.load(root)
    out = {}
    for q in store.graph(file):
        p = "a" if q.predicate.value == O.RDF_TYPE else q.predicate.value[len(O.J):]
        o = curie(q.object.value) if q.object.__class__.__name__ == "NamedNode" else q.object.value
        out.setdefault((curie(q.subject.value), p), set()).add(o)
    return out


class Tmp(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class ARealKnowledgeBaseMigrates(Tmp):
    """The exit criterion: every section, applications beside it, round trip passing."""

    def setUp(self):
        super().setUp()
        workspace(self.root)
        self.before = snapshot(self.root)
        self.code, self.out = migrated(self.root)
        self.t = triples(self.root)

    def test_it_exits_zero_and_says_the_round_trip_held(self):
        self.assertEqual(self.code, 0, self.out)
        self.assertIn("round trip  ok", self.out)

    def test_the_workspace_loads_clean_with_no_failure(self):
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.fails()], [])
        self.assertEqual(R.state(store).kind, "clean")
        st = R.state(store)
        self.assertEqual((st.kb_revision, st.log_revision), (1, 1))

    def test_jsk_kb_check_passes_on_it(self):
        code, out = run(CLI, "kb", "check", "--root", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("record   clean at r1", out)
        self.assertNotIn("canonical layout", out)

    def test_the_log_entry_is_by_migrate_and_keeps_log_md_whole(self):
        log = triples(self.root, R.LOG)
        self.assertEqual(log[("k:rev_1", "by")], {"j:migrate"})
        self.assertIn("Added the clinical event pipeline.", next(iter(log[("k:rev_1", "note")])))
        self.assertIn("k:prj_clinical_events", log[("k:rev_1", "minted")])

    def test_ids_take_the_ontology_s_prefixes(self):
        self.assertEqual(self.t[("k:prj_clinical_events", "position")], {"k:pos_meridian_principal"})
        self.assertEqual(self.t[("k:pos_meridian_principal", "organisation")], {"k:org_meridian"})
        self.assertEqual(self.t[("k:prj_clinical_events", "headlineMetric")], {"k:met_event_latency"})
        self.assertEqual(self.t[("k:q_latency_source", "about")], {"k:met_event_latency"})
        self.assertFalse([s for s, _ in self.t if s.startswith(("k:proj_", "k:role_", "k:metric_"))])

    def test_enums_take_urs_values_and_status_splits(self):
        self.assertEqual(self.t[("k:met_team.v1", "confidence")], {"j:reported"})
        self.assertEqual(self.t[("k:auth_ae", "kind")], {"j:employment-visa"})
        self.assertEqual(self.t[("k:auth_ae", "authorization")], {"j:requires-sponsorship"})
        self.assertEqual(self.t[("k:auth_ae", "provenance")], {"j:inferred"})
        self.assertEqual(self.t[("k:cred_azarch", "credentialState")], {"j:active"})
        self.assertEqual(self.t[("k:cred_cka", "provenance")], {"j:confirmed"})
        self.assertEqual(self.t[("k:cred_cka", "credentialState")], {"j:expired"})

    def test_metrics_become_a_metric_and_its_first_version(self):
        self.assertEqual(self.t[("k:met_jobs", "subject")], {"daily ingestion jobs"})
        self.assertEqual(self.t[("k:met_jobs.v1", "value")], {"40000"})
        self.assertEqual(self.t[("k:met_event_latency.v1", "baseline")], {"5"})
        self.assertEqual(self.t[("k:met_jobs.v1", "provenance")], {"j:inferred"})

    def test_bullets_are_minted_from_project_and_words_or_reused(self):
        self.assertEqual(self.t[("k:ach_latency", "text")], {BULLET})
        self.assertEqual(self.t[("k:ach_latency", "rank")], {"1"})
        self.assertIn(("k:ach_clinical_events_led_team_engineers", "text"), self.t)
        third = [s for (s, p), o in self.t.items() if p == "rank" and o == {"3"}]
        self.assertEqual(third, ["k:ach_clinical_events_wrote_audit_trail"])
        # A bullet the Markdown gave no status is inferred: a migration never raises one.
        self.assertEqual(self.t[("k:ach_clinical_events_wrote_audit_trail", "provenance")],
                         {"j:inferred"})

    def test_prose_is_kept_with_its_line_breaks(self):
        problem = next(iter(self.t[("k:prj_clinical_events", "problem")]))
        self.assertEqual(problem, "The legacy scheduler could not express care-plan constraints, "
                                  "so every site\nmaintained its own spreadsheet beside it.")
        self.assertEqual(self.t[("k:person", "positioning")],
                         {"Architect who turns regulated estates into event-driven platforms.\n\n"
                          "Strongest in healthcare and aged care."})

    def test_a_retired_project_is_retired_with_a_reason(self):
        self.assertEqual(self.t[("k:prj_intranet", "retired")], {"2026-09-08"})
        self.assertIn(("k:prj_intranet", "reason"), self.t)
        self.assertEqual(self.t[("k:prj_intranet", "noneQuantified")], {"true"})

    def test_concepts_are_the_shipped_ones_or_the_person_s_own(self):
        self.assertEqual(self.t[("c:team-leadership", "a")], {"j:Capability"})
        self.assertEqual(self.t[("c:aged-care", "a")], {"j:Domain"})
        # kafka is shipped: used, never redefined.
        self.assertIn("c:kafka", self.t[("k:prj_clinical_events", "uses")])
        self.assertNotIn(("c:kafka", "a"), self.t)
        # "Node.js" is a shipped label: the term becomes the concept it names.
        self.assertIn("c:nodejs", self.t[("k:prj_clinical_events", "uses")])
        self.assertNotIn(("c:node-js", "a"), self.t)

    def test_a_term_the_vocabulary_lacks_is_slugged_and_keeps_its_spelling(self):
        # "Tekton CD" normalises to its slug, so matching finds it with no label; "Tekton/CD"
        # does not, so its spelling is kept as one.
        kb = EVERY_SECTION.replace('"Node.js"]', '"Tekton CD", "Tekton/CD"]')
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        workspace(root, kb=kb, apps=False)
        self.assertEqual(migrated(root)[0], 0)
        t = triples(root)
        self.assertEqual(t[("c:tekton-cd", "a")], {"j:Technology"})
        self.assertEqual(t[("c:tekton-cd", "label")], {"Tekton/CD"})

    def test_what_no_field_holds_is_a_note_never_dropped(self):
        notes = self.t[("k:person", "note")]
        self.assertIn("pronouns: she/her", notes)
        self.assertIn("location.country: Australia", notes)
        self.assertIn("contact mastodon: @priya@example.social", notes)
        self.assertIn("label: UAE employment visa", self.t[("k:auth_ae", "note")])
        self.assertTrue(any(n.startswith("## Talks") and "event sourcing" in n
                            for n in self.t[("k:kb", "note")]))
        self.assertIn("vocabulary: keeping data in the jurisdiction it belongs to",
                      self.t[("c:data-sovereignty", "note")])
        self.assertIn("location.country 'Australia' kept as a j:note", self.out)

    def test_skills_education_open_source_and_languages(self):
        self.assertEqual(self.t[("k:skill_dotnet", "alias")], {"C#", ".NET", "ASP.NET Core"})
        self.assertEqual(self.t[("k:skill_python", "category")], {"language"})
        self.assertEqual(self.t[("k:skill_python", "rank")], {"2"})
        # The value as written: YAML's float would have made it 8.4.
        self.assertEqual(self.t[("k:edu_meng", "gradeValue")], {"8.40"})
        self.assertEqual(self.t[("k:os_carbon_scheduler", "role")], {"j:maintainer"})
        self.assertEqual(self.t[("k:lang_en", "language")], {"en"})
        self.assertEqual(self.t[("k:lang_ta", "provenance")], {"j:confirmed"})

    def test_nothing_it_read_from_is_deleted_or_changed(self):
        after = snapshot(self.root)
        for name in ("user-knowledgebase.md", "log.md",
                     "applications/2026-09-10-acme-platform-engineer/application.md",
                     "applications/2026-09-10-acme-platform-engineer/resume.json",
                     "applications/2026-09-10-acme-platform-engineer/gaps.md"):
            self.assertEqual(after[name], self.before[name], name)
        sent = "applications/2026-09-10-acme-platform-engineer/"
        self.assertEqual(after[sent + "posting.orig.md"], self.before[sent + "posting.md"])
        self.assertIn("nothing was deleted", self.out)

    def test_the_posting_becomes_requirements_and_the_advert_alone(self):
        sent = self.root / "applications" / "2026-09-10-acme-platform-engineer"
        advert = (sent / "posting.md").read_text(encoding="utf-8")
        self.assertTrue(advert.startswith("# Platform Engineer at Acme Health"), advert)
        self.assertNotIn("requirements:", advert)
        post = triples(self.root, "applications/2026-09-10-acme-platform-engineer/posting.ttl")
        self.assertEqual(post[("k:post_acme_platform_engineer", "title")],
                         {"Platform Engineer: Core"})
        self.assertEqual(post[("k:req_acme_platform_engineer_kafka", "quote")],
                         {"Kafka in production"})
        self.assertEqual(post[("k:req_acme_platform_engineer_kafka", "concept")], {"c:kafka"})
        # The label is not in the advert; the line that names the term is quoted instead.
        self.assertEqual(post[("k:req_acme_platform_engineer_team_leadership", "quote")],
                         {"Team leadership a plus."})
        # A requirement the advert never states is not invented: it is kept as a note.
        self.assertNotIn(("k:req_acme_platform_engineer_quantum_annealing", "quote"), post)
        self.assertTrue(any("quantum-annealing" in n
                            for n in post[("k:post_acme_platform_engineer", "note")]))

    def test_the_application_carries_the_links_its_resume_sent(self):
        app = triples(self.root, "applications/2026-09-10-acme-platform-engineer/application.ttl")
        a = "k:app_acme_platform_engineer"
        self.assertEqual(app[(a, "carried")], {"k:ach_latency"})
        self.assertEqual(app[(a, "carriedVersion")], {"k:met_event_latency.v1"})
        self.assertEqual(app[(a, "submitted")], {"2026-09-10"})
        record = self.root / "applications/2026-09-10-acme-platform-engineer/resume.json"
        self.assertEqual(app[(a, "recordSha256")], {hashlib.sha256(record.read_bytes()).hexdigest()})
        self.assertIn("resume.json's ach_retuned is not a bullet", self.out)

    def test_the_timeline_becomes_events(self):
        app = triples(self.root, "applications/2026-09-10-acme-platform-engineer/application.ttl")
        e = "k:evt_acme_platform_engineer_2026_09_15_screen_scheduled"
        self.assertEqual(app[(e, "due")], {"2026-09-18"})
        self.assertEqual(app[(e, "note")], {"Phone screen, 30 min"})
        odd = "k:evt_acme_platform_engineer_unknown_note"
        self.assertEqual(app[(odd, "date")], {"unknown"})
        self.assertIn("event: phone-screen", app[(odd, "note")])

    def test_an_application_still_being_tailored_gets_its_posting_only(self):
        draft = self.root / "applications" / "globex-staff-engineer"
        self.assertTrue((draft / "posting.ttl").is_file())
        self.assertFalse((draft / "application.ttl").exists())

    def test_the_claims_gate_runs_over_every_resume_it_found(self):
        # A gate that did not run is not a gate that passed: "did not run" is a failure here.
        self.assertTrue(importlib.util.find_spec("jsk.gates.claims"))
        self.assertNotIn("did not run", self.out)
        self.assertRegex(self.out, r"claims   applications/2026-09-10-acme-platform-engineer/"
                                   r"resume\.json: \d+ FAIL")

    def test_a_second_fmt_changes_nothing(self):
        code, out = run(CLI, "kb", "fmt", "--root", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("already canonical", out)


class Refusals(Tmp):
    def test_it_refuses_when_kb_ttl_exists(self):
        workspace(self.root, apps=False)
        (self.root / "career").mkdir()
        (self.root / "career" / "kb.ttl").write_text("# not mine\n", encoding="utf-8")
        before = snapshot(self.root)
        code, out = migrated(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED  career/kb.ttl already exists", out)
        self.assertEqual(snapshot(self.root), before)

    def test_a_round_trip_that_loses_an_entry_is_refused(self):
        workspace(self.root)
        before = snapshot(self.root)
        real = migrate.project

        def lossy(quads):
            nodes = real(quads)
            nodes.pop(O.K + "prj_intranet")
            return nodes
        migrate.project = lossy
        try:
            code, out = migrated(self.root)
        finally:
            migrate.project = real
        self.assertEqual(code, 1, out)
        self.assertIn("does not read back as the Markdown: k:prj_intranet", out)
        self.assertEqual(snapshot(self.root), before)

    def test_a_round_trip_that_changes_a_value_is_refused(self):
        workspace(self.root, apps=False)
        before = snapshot(self.root)
        real = migrate.to_quads

        def drift(nodes):
            import pyoxigraph as ox
            quads = real(nodes)
            return [ox.Quad(q.subject, q.predicate, ox.Literal("4", datatype=q.object.datatype))
                    if q.predicate.value == O.J + "strength" and q.subject.value.endswith("intranet")
                    else q for q in quads]
        migrate.to_quads = drift
        try:
            code, out = migrated(self.root)
        finally:
            migrate.to_quads = real
        self.assertEqual(code, 1, out)
        self.assertIn("k:prj_intranet", out)
        self.assertIn("jsk index reads projects", out)
        self.assertEqual(snapshot(self.root), before)

    def test_a_dry_run_writes_nothing_and_prints_the_files(self):
        workspace(self.root)
        before = snapshot(self.root)
        code, out = migrated(self.root, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("--- would write career/kb.ttl", out)
        self.assertIn("k:prj_clinical_events j:name", out)
        self.assertIn("would copy applications/2026-09-10-acme-platform-engineer/posting.md", out)
        self.assertIn("dry run: nothing was written", out)
        self.assertEqual(snapshot(self.root), before)

    def test_a_required_value_missing_names_the_entry(self):
        # jsk index's own test KB: roles with no organisation and no seniority.
        from test_kbindex import KB
        workspace(self.root, kb=KB, apps=False)
        before = snapshot(self.root)
        code, out = migrated(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("k:pos_one has no organisation", out)
        self.assertIn("k:pos_one has no seniority", out)
        self.assertEqual(snapshot(self.root), before)

    def test_a_metric_value_that_is_not_a_number_is_refused(self):
        kb = EVERY_SECTION.replace("| 40,000 | jobs |", "| about forty thousand | jobs |")
        workspace(self.root, kb=kb, apps=False)
        code, out = migrated(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("metric metric_jobs: value 'about forty thousand' is not a number", out)
        self.assertFalse((self.root / "career").exists())

    def test_a_file_not_in_the_spec_s_shape_is_refused_as_jsk_index_would(self):
        kb = EVERY_SECTION.replace("strength: 1\n", "strength: 9\n")
        workspace(self.root, kb=kb, apps=False)
        code, out = migrated(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("`strength: 9` is outside 1-5", out)

    def test_a_dangling_reference_fails_validation_and_is_refused(self):
        kb = EVERY_SECTION.replace("| metric_event_latency | 2026-09-08 |",
                                   "| metric_nowhere | 2026-09-08 |")
        workspace(self.root, kb=kb, apps=False)
        code, out = migrated(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("the migrated record would not validate", out)
        self.assertIn("j:about k:met_nowhere: nothing defines it", out)
        self.assertFalse((self.root / "career").exists())


def line_of(text, fragment):
    """The 1-based line of `text` holding `fragment`."""
    return next(n for n, line in enumerate(text.split("\n"), 1) if fragment in line)


class NothingReadIsLostOrChanged(Tmp):
    """Each value the reader used to drop or alter without a word - found by review, each
    exiting 0 with "round trip ok". YAML 1.1 read them as numbers, octals and booleans;
    the reader skipped what it had no branch for."""

    def migrate(self, kb):
        workspace(self.root, kb=kb, apps=False)
        code, out = migrated(self.root)
        self.assertEqual(code, 0, out)
        return triples(self.root)

    def test_a_phone_number_with_a_leading_zero_is_kept_as_written(self):
        t = self.migrate(EVERY_SECTION.replace('value: "+61 400 000 000"', "value: 0400123456"))
        self.assertEqual(t[("k:person", "phone")], {"0400123456"})

    def test_a_phone_number_with_a_plus_keeps_it(self):
        t = self.migrate(EVERY_SECTION.replace('value: "+61 400 000 000"', "value: +61400000000"))
        self.assertEqual(t[("k:person", "phone")], {"+61400000000"})

    def test_a_contact_that_is_a_bare_string_is_a_note(self):
        t = self.migrate(EVERY_SECTION.replace("pronouns: she/her",
                                               "  - someone@example.org\npronouns: she/her"))
        self.assertIn("contact: someone@example.org", t[("k:person", "note")])

    def test_frontmatter_keys_no_field_holds_are_notes_and_the_old_updated_is_kept(self):
        t = self.migrate(EVERY_SECTION.replace(
            "updated: 2026-09-08\n",
            "updated: 2026-09-08\ntarget_roles: [Staff Engineer, Principal]\n"
            "notice_period: 4 weeks\n"))
        notes = t[("k:kb", "note")]
        self.assertIn("notice_period: 4 weeks", notes)
        self.assertIn('target_roles: ["Staff Engineer", "Principal"]', notes)
        self.assertIn("updated: 2026-09-08", notes)

    def test_a_language_with_no_language_key_is_a_note(self):
        t = self.migrate(EVERY_SECTION.replace(
            "    status: confirmed\n```\n\n## Vocabulary",
            "    status: confirmed\n  - level: C1\n    scheme: cefr\n```\n\n## Vocabulary"))
        self.assertTrue(any("C1" in n and "cefr" in n for n in t[("k:person", "note")]),
                        t[("k:person", "note")])

    def test_a_country_code_yaml_reads_as_false_stays_the_code(self):
        t = self.migrate(EVERY_SECTION.replace("country: Australia", "country: NO"))
        self.assertEqual(t[("k:person", "country")], {"NO"})

    def test_two_ids_that_normalise_to_one_are_refused_naming_both(self):
        kb = EVERY_SECTION.replace("## Roles\n", (
            f"### Meridian again `org_Meridian`\n\n{FENCE}yaml\nid: org_Meridian\n"
            f"relationship: employer\nstatus: confirmed\n{FENCE}\n\n## Roles\n"))
        workspace(self.root, kb=kb, apps=False)
        code, out = migrated(self.root)
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"REFUSED  .*org_meridian.*org_Meridian")
        self.assertFalse((self.root / "career").exists())

    def test_a_key_written_twice_in_one_block_is_refused(self):
        kb = EVERY_SECTION.replace("given_name: Priya\n", "given_name: Priya\ngiven_name: X\n")
        workspace(self.root, kb=kb, apps=False)
        code, out = migrated(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn(f"line {line_of(kb, 'given_name: X')}", out)
        self.assertIn("duplicate key", out)

    def test_a_body_line_the_reader_lost_is_refused_naming_the_line(self):
        workspace(self.root, apps=False)
        real = migrate.Reader.sec_positioning
        migrate.Reader.sec_positioning = lambda self, s: None
        try:
            code, out = migrated(self.root)
        finally:
            migrate.Reader.sec_positioning = real
        self.assertEqual(code, 1, out)
        n = line_of(EVERY_SECTION, "Architect who turns")
        self.assertIn(f"REFUSED  line {n}: 'Architect who turns regulated estates", out)
        self.assertFalse((self.root / "career").exists())

    def test_a_yaml_value_the_reader_lost_is_refused_naming_the_line(self):
        workspace(self.root, apps=False)
        real = migrate.Reader.sec_identity

        def forgetful(self, s):
            real(self, s)
            # Handed to the graph, then lost: the check reads the graph, not the reader.
            self.plan.nodes[O.K + "person"].props["region"].clear()
        migrate.Reader.sec_identity = forgetful
        try:
            code, out = migrated(self.root)
        finally:
            migrate.Reader.sec_identity = real
        self.assertEqual(code, 1, out)
        self.assertIn(f"REFUSED  line {line_of(EVERY_SECTION, 'region: VIC')}: 'VIC'", out)

    def test_a_yaml_value_the_reader_never_handed_on_is_refused(self):
        workspace(self.root, apps=False)
        real = migrate.Reader.status
        # The person's status dropped: "confirmed" is still all over the graph, so only
        # the record of what the reader handed on can see it went missing.

        def forgetful(self, iri, value, other=None):
            if iri != O.K + "person":
                real(self, iri, value, other)
        migrate.Reader.status = forgetful
        try:
            code, out = migrated(self.root)
        finally:
            migrate.Reader.status = real
        self.assertEqual(code, 1, out)
        n = line_of(EVERY_SECTION, "pronouns: she/her") + 1
        self.assertIn(f"REFUSED  line {n}: 'confirmed'", out)


class OlderShapes(Tmp):
    def test_a_bullet_may_name_its_own_id_and_cite_two_metrics(self):
        kb = EVERY_SECTION.replace(
            "  - metric: metric_team\n",
            "  - id: ach_led_migration\n  - metric: metric_team, metric_jobs\n")
        workspace(self.root, kb=kb, apps=False)
        self.assertEqual(migrated(self.root)[0], 0)
        t = triples(self.root)
        self.assertEqual(t[("k:ach_led_migration", "cites")], {"k:met_team", "k:met_jobs"})

    def test_a_kb_1_file_s_log_section_joins_the_history(self):
        kb = EVERY_SECTION.replace("kb: 2", "kb: 1") + (
            "\n## Log\n\n| date | what changed |\n|---|---|\n| 2026-01-01 | Began. |\n")
        workspace(self.root, kb=kb, apps=False)
        code, out = migrated(self.root)
        self.assertEqual(code, 0, out)
        note = next(iter(triples(self.root, R.LOG)[("k:rev_1", "note")]))
        self.assertIn("| 2026-01-01 | Began. |", note)
        self.assertIn("Added the clinical event pipeline.", note)


class TheOldFormatIsStillDocumented(unittest.TestCase):
    """A Markdown file migrate or kbindex refuses has to be fixed against a description of
    the old format - which left the plugin when kb-spec.md became kb-format.md."""

    def test_every_pointer_names_a_file_that_exists(self):
        spec = REPO_ROOT / "docs" / "legacy-kb-spec.md"
        self.assertTrue(spec.is_file())
        for module in ("migrate.py", "kbindex.py"):
            text = (REPO_ROOT / "src" / "jsk" / module).read_text(encoding="utf-8")
            with self.subTest(module=module):
                self.assertNotRegex(text, r"(?<!legacy-)kb-spec\.md")
                self.assertIn("docs/legacy-kb-spec.md", text)


class TheCommand(Tmp):
    def test_help_exits_zero(self):
        code, out = run(CLI, "migrate", "--help")
        self.assertEqual(code, 0, out)
        self.assertIn("--dry-run", out)

    def test_called_wrong_exits_two(self):
        self.assertEqual(run(CLI, "migrate")[0], 2)
        self.assertEqual(run(CLI, "migrate", self.root / "nothing.md")[0], 2)

    def test_the_template_jsk_new_used_to_write_migrates(self):
        scaffold_markdown_kb(self.root, "Test Person")
        self.assertIn("## Projects", kb_text(self.root))
        code, out = run(CLI, "migrate", self.root / "user-knowledgebase.md")
        self.assertEqual(code, 0, out)
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.fails()], [])
        self.assertEqual(R.state(store).kind, "clean")
        t = triples(self.root)
        self.assertEqual(t[("k:person", "fullName")], {"Test Person"})
        self.assertEqual(t[("k:person", "provenance")], {"j:needs-verification"})

    def test_the_p0_sample_knowledge_base_migrates(self):
        """The P0 spike's sample, copied into tests/ so the suite runs from an unpacked
        sdist, which ships no docs/superpowers. The copy drops the email contact."""
        sample = Path(__file__).resolve().parent / "migrate_fixtures" / "sample-kb.md"
        shutil.copy(sample, self.root / "user-knowledgebase.md")
        code, out = migrated(self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual(R.state(S.load(self.root)).kind, "clean")
        t = triples(self.root)
        self.assertEqual(t[("k:met_event_latency.v1", "value")], {"1"})
        self.assertIn("c:kafka", t[("k:prj_clinical_events", "uses")])


if __name__ == "__main__":
    unittest.main()
