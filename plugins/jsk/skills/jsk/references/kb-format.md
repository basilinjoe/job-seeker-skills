# The record: Turtle files in git

For reading `career/kb.ttl` and drafting a changeset. Nobody writes `career/` but `jsk`; you
change the career with `jsk kb apply`, and read it with `jsk kb show`, `view` and `query`.

```
<workspace>/
  .gitattributes             *.ttl text eol=lf
  career/kb.ttl              the whole career, one readable file
  career/log.ttl             every change: revision, day, command, summary, kb.ttl's hash
  applications/<yyyy-mm-dd>-<company>-<role>/
    posting.md               the advertisement, verbatim - nothing else
    posting.ttl              what it asks for (the analyst writes it)
    gaps.md                  the assessment and the question queue
    resume.json              the bullets and settings this submission rendered from
    application.ttl          what was sent, and its timeline - jsk freeze, jsk event
```

## Layout

A fixed prefix block (`j:` the ontology, `k:` ids, `c:` concepts, `xsd:`), the header
`k:kb j:format 3 ; j:name … ; j:updated … ; j:revision N .` (`format`, `updated` and `revision`
are jsk's to write), then one banner per section, always all of them, in this order:

```
# == Identity
# == Positioning
# == Work authorization and languages
# == Vocabulary
# == Organisations
# == Roles
# == Projects
# == Metrics
# == Skills
# == Education
# == Certifications
# == Open source
# == Open questions
```

Bullets sit under their project, versions under their metric, prose in `"""…"""`. Values are
never reflowed. No blank nodes on disk. `jsk kb fmt` restores the layout.

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

Every entry may carry `retired` (with a `reason`) and `note`* - free text for anything the
ontology has no field for. Enums are `j:` words (`j:ongoing`, `j:measured`); dates are
`"2026-09-08"^^xsd:date`; `start`/`end` are `"YYYY-MM"` strings. Seniority is closed:
`architecture-ownership` `product-ownership` `platform-design` `team-leadership`
`technical-ownership` `hands-on-senior` `hands-on` `junior`. A number stated loosely keeps how:
"15-20" is `j:value 15 ; j:upper 20`, "50+" `j:qualifier j:at-least` (`j:about` ~, `j:under` <,
`j:over` >); several numbers in one are several metrics.

**Tag versus evidence.** A project's `uses` is a tag; a bullet's `shows` is evidence. A concept a
project names must exist - in the shipped vocabulary or under `# == Vocabulary`
(`c:x a j:Capability ; j:label "X" .`).

## Provenance

Every entry except concepts, metrics, skills and questions carries `j:provenance`: `j:confirmed`,
`j:inferred`, `j:needs-verification` or `j:disputed`. Changing a claim - text, a title, a date, a
value, where it sits - drops the entry to `j:inferred` and opens a `q_` question. Only
`jsk kb confirm <id> --answer "…"` raises it.

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
- `op:base` is the revision `jsk kb show` printed; a later change to what you touch is refused.
- A new bullet is `[]` with `j:project` and `j:rank`. A new `j:value` on a metric version an
  application sent becomes the next version; the sent one never changes. Never write `j:confirmed`, `j:revision` or `j:updated`.
- `--dry-run` first. Every refusal says what fixes it.

Without pyoxigraph, draft the changeset into a file and say it waits for `jsk kb apply`.

## Hand edits

Legal. The next load says `kb.ttl changed outside jsk kb apply`; `jsk kb adopt` logs the edit and
lists every provenance it raised, to check with the person.

## posting.ttl

```turtle
# == Posting

k:post_acme_platform j:company "Acme Health" ; j:title "Platform Engineer" ;
    j:url "https://…" ;
    j:seniority j:platform-design ;
    j:captured "2026-09-08"^^xsd:date ; j:advert "posting.md" .

# == Requirements

k:req_acme_platform_k8s j:posting k:post_acme_platform ;
    j:asked "K8s" ; j:necessity j:required ; j:concept c:kubernetes ;
    j:quote "Deep, hands-on K8s experience in production" .
```

A posting holds `company` `title` `url`? `seniority`? `domain`* `captured` `advert`; a requirement
`posting` `asked` `necessity` `concept`? `quote`. `asked` is the advert's term; `quote` its words,
verbatim from `posting.md`; `necessity` is `required`, `preferred` or `implicit`; `concept` only
when `jsk match` calls the term ambiguous.
