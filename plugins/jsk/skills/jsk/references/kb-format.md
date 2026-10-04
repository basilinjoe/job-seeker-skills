# The record: one store, read as Turtle

For reading the career and drafting a changeset. The record is named graphs in one store,
`career/store/`, that only `jsk` opens: you change it with the `career_apply` tool, and read it with
`career_show` (entries as Turtle, and the `op:base`), `career_view`, `career_query` and `career_log`.

```
<workspace>/
  career/store/              the record: graphs kb (the career), log (every change),
                             applications/<stem>/posting, review, gaps, resume, application;
                             resumes/<name>/resume
  .jsk/backup.trig           the whole record as TriG, after every write
  applications/<stem>/       the .pdf and .tex a render left (one frozen from files before
                             6.0 also holds posting.md, read to check its quotes)
```

## Sections

The career's header is `k:kb j:format 3 ; j:name … ; j:updated … ; j:revision N .` (`format`,
`updated` and `revision` are jsk's to write). `career_view` prints it in these sections, in this
order; its `section` argument takes one name:

```
Identity
Positioning
Work authorization and languages
Vocabulary
Organisations
Roles
Projects
Metrics
Skills
Education
Certifications
Open source
Open questions
```

Bullets sit under their project, versions under their metric. `career_show` prints prose in `"""…"""`.

## Ids

`k:<prefix>_<words>`, lowercase, underscores, never positional (`_2` is refused), never reused.
Concepts are `c:<words-with-dashes>`. A bullet's id is minted by apply.

| Prefix | Class | Section | Predicates (`?` optional, `*` many, rest required) |
|---|---|---|---|
| `k:person` | Person | Identity | `fullName` `givenName`? `familyName`? `headline`? `city`? `region`? `country`? `workMode`? `email`* `phone`* `linkedin`* `github`* `website`* `primary`? `positioning`? |
| `auth_` | WorkAuthorization | Work authorization | `jurisdiction` `kind` `authorization` `validUntil`? |
| `lang_` | Language | Work authorization | `language` `native`? `scheme`? `level`? |
| `c:` | Capability · Domain · Technology | Vocabulary | `label`* `former`* `isA`* `partOf`* `implies`* `distinct`* `unlabel`* `unlink`* |
| `org_` | Organisation | Organisations | `name` `relationship` `industry`* `size`? |
| `pos_` | Position | Roles | `organisation` `title` `functionalTitle`? `start` `end`? `state` `seniority` `change`? `engagementKind`? |
| `prj_` | Project | Projects | `name` `position`? `strength` `recency` `seniority`? `domain`* `uses`* `headlineMetric`? `noneQuantified`? `problem`? `decision`? `outcome`? |
| `ach_` | Achievement (a bullet) | Projects | `project` `rank` `text` `cites`* `shows`* |
| `met_` | Metric | Metrics | `subject` `unit`? `direction`? |
| `met_x.v1` | MetricVersion | Metrics | `of` `baseline`? `value` `upper`? `qualifier`? `kind`? `confidence` `source`? `validFrom`? `validUntil`? |
| `skill_` | Skill | Skills | `name` `category` `rank`? `alias`* |
| `edu_` | Education | Education | `institution` `qualification` `field`? `level`? `start`? `end`? `gradeScheme`? `gradeValue`? |
| `cred_` | Credential | Certifications | `name` `issuer` `issued`? `expires`? `credentialState` `url`? |
| `os_` | OpenSource | Open source | `name` `url` `role` |
| `q_` | Question | Open questions | `about`+ (`k:kb`: the whole career) `question` `asked` `answered`? |
| `abs_` | Absence (a "no") | Open questions | `concept` `said` `answer` (their words) |

Every entry may carry `retired` (with a `reason`) and `note`* - free text for anything the
ontology has no field for. Enums are `j:` words (`j:ongoing`, `j:measured`); dates are
`"2026-09-08"^^xsd:date`; `start`/`end` are `"YYYY-MM"` strings. Seniority is closed:
`architecture-ownership` `product-ownership` `platform-design` `team-leadership`
`technical-ownership` `hands-on-senior` `hands-on` `junior`. A number stated loosely keeps how:
"15-20" is `j:value 15 ; j:upper 20`, "50+" `j:qualifier j:at-least` (`j:about` ~, `j:under` <,
`j:over` >); several numbers in one are several metrics. The store keeps a number by value, so
write it as it keeps it - `8.4`, not `8.40`; `7`, not `007` - or apply refuses it; a grade whose
zeros matter (`3.80`) is a string.

**Tag versus evidence.** A project's `uses` is a tag; a bullet's `shows` is evidence. A concept a
project names must exist - in the shipped vocabulary or the career's own Vocabulary
(`c:x a j:Capability ; j:label "X" .`).

## Provenance

Every entry except concepts, metrics, skills and questions carries `j:provenance`: `j:confirmed`,
`j:inferred`, `j:needs-verification` or `j:disputed`. Changing a claim - text, a title, a date, a
value, where it sits - drops the entry to `j:inferred` and opens a `q_` question. Only
`career_confirm(ids=["<id>"], answer="…")` raises it.

## Changesets

TriG, with the prefix block written out (`op:` too):

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix op: <tag:jsk,2026:op#> .
op:changeset op:base 7 ; op:summary "The payments project, from the braindump." .
op:add {
  k:prj_payments j:name "Payments platform" ; j:position k:pos_acme_lead ;
      j:strength 4 ; j:recency 2025 ; j:uses c:kafka ; j:headlineMetric k:met_settlement .
  [] j:project k:prj_payments ; j:rank 1 ; j:text "Cut settlement latency from 800 ms to 200 ms." ;
      j:cites k:met_settlement ; j:shows c:kafka .
  k:met_settlement j:subject "settlement latency" ; j:unit "ms" ; j:direction j:decrease .
  k:met_settlement.v1 j:of k:met_settlement ; j:baseline 800 ; j:value 200 ; j:confidence j:reported .
}
op:set    { k:prj_legacy j:strength 2 . }
op:retire { k:prj_intranet j:reason "Too old to earn a line." . }
```

- `op:add` adds; `op:set` replaces every value of each (entry, predicate) it names; `op:retire`
  keeps the entry, dated, with its reason; `op:delete` removes triples, or `k:x a op:Entry` the
  whole entry - only one that was wrong, never one anything points at.
- `op:base` is the revision `career_show` returned. A later write that touched nothing you name
  does not stop it; a later change to what you touch is refused, naming the ids.
- A new bullet is `[]` with `j:project` and `j:rank`. A new `j:value` on a metric version an
  application sent becomes the next version; the sent one never changes. Never write `j:confirmed`, `j:revision` or `j:updated`.
- `career_preview` first. Every refusal says what fixes it.

With the jsk tools unavailable, draft the changeset into a file and say it waits for `career_apply`.

## The posting graph

`posting_decide` writes it; `career_show(ids=["k:post_<stem>"])` returns it:

```turtle
k:post_acme_platform j:company "Acme Health" ; j:title "Platform Engineer" ;
    j:url "https://…" ;
    j:seniority j:platform-design ;
    j:captured "2026-09-08"^^xsd:date ; j:state j:draft .

k:req_acme_platform_k8s j:posting k:post_acme_platform ;
    j:asked "K8s" ; j:necessity j:required ; j:concept c:kubernetes ;
    j:quote "Deep, hands-on K8s experience in production" .
```

A posting holds `company` `title` `url`? `seniority`? `domain`* `captured` `advert`? `state`?; a
requirement `posting` `asked` `necessity` `concept`* `quote` `line`?; an advert line (`line_`)
`posting` `n` `section` `text` `optional`? `eligibility`? `dropped`?. `asked` is the advert's
term; `quote` its words, verbatim from its advert line (`line`); a frozen file-made posting's from `posting.md`; `necessity` is `required`,
`preferred` or `implicit`; `concept` when the match calls the term ambiguous or unknown,
one per alternative ("AWS/GCP/Azure") - any one satisfies.
