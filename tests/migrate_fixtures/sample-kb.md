---
kb: 2
name: Priya Raman
updated: 2026-09-20
---

# Career knowledge base - Priya Raman

## Identity

```yaml
full_name: Priya Raman
headline: Principal Solution Architect
location:
  city: Sydney
  country: AU
  mode: hybrid
contacts:
  - kind: linkedin
    value: linkedin.com/in/priyaraman
    primary: true
status: confirmed
```

## Positioning

Architect who turns regulated, legacy-heavy estates into event-driven platforms without a big-bang
rewrite. Strongest in healthcare and aged care.

## Work authorization and languages

```yaml
work_authorization:
  - jurisdiction: AU
    kind: citizen
    status: held
languages:
  - language: en
    native: true
```

## Vocabulary

### Capabilities

- `ai-platform-architecture`
- `data-sovereignty`
- `team-leadership`

### Domains

- `healthcare`
- `aged-care`

## Organisations

### Meridian Health `org_meridian`

```yaml
id: org_meridian
relationship: employer
industry: [healthcare]
size: 1001-5000
status: confirmed
```

## Roles

### Principal Solution Architect - Meridian Health `role_meridian_principal`

```yaml
id: role_meridian_principal
organisation: org_meridian
title: Principal Solution Architect
start: 2023-07
state: ongoing
seniority: architecture-ownership
change: promotion
status: confirmed
```

### Senior Engineer - Meridian Health `role_meridian_senior`

```yaml
id: role_meridian_senior
organisation: org_meridian
title: Senior Engineer
start: 2020-02
end: 2023-06
state: ended
seniority: hands-on-senior
change: hire
status: confirmed
```

## Projects

### Clinical event pipeline `proj_clinical_events`

```yaml
id: proj_clinical_events
role: role_meridian_principal
strength: 5
recency: 2026
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture, data-sovereignty]
technologies: [azure-ai-foundry, bicep, kafka]
headline_metric: metric_event_latency
status: confirmed
```

**The problem.** The legacy scheduler could not express care-plan constraints, so every site
maintained its own spreadsheet beside it.

**What I decided.** Event-sourced the schedule rather than versioning the table, on the argument
that the audit requirement was the real constraint.

**What changed.** Propagation fell from five minutes to under a second across 15 integrated
applications.

**Bullets**

- Cut p95 clinical event latency from 5 minutes to under 1 second across 40,000 daily
  ingestion jobs.
  - metric: metric_event_latency
  - status: confirmed
- Led a team of 6 engineers through the migration with no unplanned downtime.
  - metric: metric_team
  - status: confirmed

### Care-site onboarding `proj_site_onboarding`

```yaml
id: proj_site_onboarding
role: role_meridian_senior
strength: 3
recency: 2022
seniority: hands-on-senior
domains: [aged-care]
capabilities: [team-leadership]
technologies: [dotnet, sql-server]
headline_metric: metric_sites
status: inferred
```

**The problem.** Each new residential care site took a quarter to onboard by hand.

**What I decided.** Templated the site configuration and moved the checks into the pipeline.

**What changed.** Onboarding fell to two weeks; 42 sites now run on it.

**Bullets**

- Brought 42 residential care sites onto one platform, cutting onboarding from a quarter to two
  weeks.
  - metric: metric_sites
  - status: inferred

## Metrics

| id | subject | baseline | value | unit | direction | confidence | source | status |
|---|---|---|---|---|---|---|---|---|
| metric_event_latency | p95 clinical event latency | 5 | 1 | min→s | decrease | measured | Grafana dashboard | confirmed |
| metric_team | engineers led | | 6 | engineers | | measured | org chart | confirmed |
| metric_sites | residential care sites served | | 42 | sites | | measured | platform admin console | confirmed |

## Skills

### cloud-platform

- Azure `skill_azure` — aliases: Microsoft Azure, Azure AI Foundry, Bicep

### language

- C# / .NET `skill_dotnet` — aliases: C#, .NET, ASP.NET Core

## Education

_None recorded yet._

## Certifications

- Azure Solutions Architect Expert `cred_az305`
  - issuer: Microsoft
  - issued: 2024-03
  - status: active

## Open source

_None recorded yet._

## Open questions

| id | question | about | asked | answered |
|---|---|---|---|---|
| q_sites_confirm | Is 42 the current site count, or the count at hand-over? | proj_site_onboarding | 2026-09-01 | |
| q_team_size | Was the team 6 throughout, or at peak? | proj_clinical_events | 2026-08-12 | 2026-08-14 |
