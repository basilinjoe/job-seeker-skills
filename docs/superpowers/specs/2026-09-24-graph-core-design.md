# Graph core (P1): the ontology, reader, canonical writer, validation and loader

**Status:** approved design, 2026-09-24. Phase P1 of `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md`.
**Depends on:** the P0 spike (`docs/superpowers/experiments/2026-09-24-p0-spike/README.md`), whose numbers
are restated where they decide something. **Changes no command.** `kbindex.py` and every Markdown path
stay as they are until P4/P7.

## What P1 delivers

A package, `src/jsk/graph/`, that can take any file of the graph record - hand-written or written by
jsk - and:

1. **parse** it, naming `file:line:column` on a syntax error;
2. **validate** it alone and together with the rest of the workspace, every finding naming
   `file:line id`, the rule and a fix;
3. **write** it back canonically - the same triples always give the same bytes, and the writer's
   output parses back to exactly the triples it was given;
4. **load** a whole workspace into one in-memory Oxigraph store, with types derived and the
   counts-as closure materialised, ready for P2's queries.

The ontology covers **every file kind the rewrite will have** (the person chose "everything up front"),
so P2-P5 add behaviour, not format. Rules that need behaviour from a later phase are named here and
owned there (see "Deferred rules").

Success is: the fixture workspace loads, validates clean and round-trips byte for byte; every rule is
proven to fire by a mutation; the suite passes on four CI jobs; `jsk doctor` shows pyoxigraph `ok`.

## Decisions carried in from P0 and the roadmap

| Decision | Source |
|---|---|
| pyoxigraph `>=0.5.11,<0.6`, the first hard dependency; abi3 wheels for every platform jsk supports | P0 |
| Python floor 3.10 (3.8 and 3.9 are end-of-life and never tested) | roadmap |
| jsk writes its own Turtle; pyoxigraph only parses and queries (its serializer is not canonical) | P0 |
| short `# == Section` banners; no `a j:Class` on `k:` ids - the id prefix names the class | P0, 1.17x tokens vs Markdown; layout approved by the person |
| one named graph per file; derived triples in `j:derived`; queries over the union graph | P0 |
| findings through `validate_urs.Report` / `show()`, errors carrying a fix like `KBError` | roadmap |

## Where the ontology lives: Python data

`src/jsk/graph/ontology.py` holds the format as declarative tables - one row per class, one per
predicate - and every other module reads them: the writer's ordering, tier-1 validation, and the
tests. Rejected: SHACL run by pyshacl (a second, heavy dependency; the writer's ordering would still
need a home, so two definitions) and a self-describing `ontology.ttl` (every consumer parses before
it can act; buys nothing until someone outside jsk wants the ontology, which P8 can export).

```python
Class(name, prefix, file_kind, section, key, doc)            # key: the natural sort key
Pred(name, classes, obj, card, claim, group, doc, section=None)
#   obj:  Lit(datatype | pattern) | Enum(name) | Ref(prefixes...) | ConceptRef(classes...)
#   card: "1" | "?" | "*" | "+"
#   claim: True for predicates whose change resets provenance and that the claims gate reads
#   group: predicates with the same group share a line when the writer lays a subject out
ENUMS = {name: (values...)}                                  # values are j: individuals
```

## Files, namespaces and ids

**File kinds:** `kb` (`career/kb.ttl`), `log` (`career/log.ttl`), `posting`
(`applications/<dir>/posting.ttl`), `application` (`applications/<dir>/application.ttl`),
`vocabulary` (`src/jsk/data/vocabulary.ttl`, shipped), and `changeset` (TriG, P3). Every class
belongs to exactly one file kind; concepts belong to `kb` and `vocabulary`.

**Namespaces.** `tag:` URIs (RFC 4151) - identifiers that need no domain ownership. Only the prefix
block shows them; every line below reads as CURIEs. This replaces the `https://jsk.dev/` namespace
the roadmap and the experiments used - a domain jsk does not own - while the format is still unfrozen.

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix op: <tag:jsk,2026:op#> .          # changesets only
```

**Ids.** A `k:` id is `<prefix>_<slug>`, slug `[a-z0-9]+(_[a-z0-9]+)*`; the prefix names the class.
Singletons: `k:kb`, `k:person`. Metric versions are `k:met_<slug>.v<N>`, N from 1. Achievement ids
ending `_<digits>` are refused as positional. A concept is `c:<slug>`, slug `[a-z0-9]+(-[a-z0-9]+)*`,
and is the one subject that states its class (`a j:Capability`), since its slug has no prefix.
Posting, requirement, application and event ids carry a stem minted at capture
(`post_acme_platform_engineer`) that never changes, including when `jsk freeze` renames the
directory. Ids match URS where URS has the thing (`org_ pos_ prj_ ach_ skill_ cred_ edu_`); URS's
`eng_` is derived from a position's organisation and never stored.

**On every class:** `j:note *` (free text; the relief valve for anything the ontology lacks),
`j:retired ?` (date) with `j:reason` required when retired. **On every claim-bearing class:**
`j:provenance 1` in `confirmed · inferred · needs-verification · disputed` (URS's
`PROVENANCE_RANK`).

**Format marker:** `k:kb j:format 3` (the Markdown was `kb: 2`).

## The classes

`1` required - `?` optional - `*` zero or more - `+` one or more. **Bold** = `claim=True`. Enum
values follow URS where URS defines them: the KB's `self-reported` becomes `reported`, and the
overloaded Markdown `status` splits into `j:provenance`, `j:authorization` and `j:credentialState`.
Dates are `xsd:date`; year-month and year values (`"2023-07"`, `2026`) are plain literals checked by
pattern, since URS keeps its own precision.

### kb.ttl, in section order

| Section | Class (id) | Predicates |
|---|---|---|
| (header) | KB `k:kb` | format 1 (= 3), name 1, updated 1 (date) |
| Identity | Person `k:person` | **fullName** 1, givenName ?, familyName ?, **headline** ?, city ?, region ?, country ? (ISO 3166-1 alpha-2), workMode ? (onsite·hybrid·remote), email *, phone *, linkedin *, github *, website *, primary ? (a literal equal to one of the contact values) |
| Positioning | Person `k:person` | positioning ? (prose) - the one predicate whose section differs from its class's |
| Work authorization and languages | WorkAuthorization `auth_` | jurisdiction 1, **kind** 1 (citizen·permanent·employment-visa·residence·student·working-holiday·none), **authorization** 1 (held·expired·eligible·requires-sponsorship), validUntil ? |
| | Language `lang_` | language 1 (BCP 47), native ? (boolean), scheme ? (cefr·ilr·jlpt·ielts·reported), level ? |
| Vocabulary | Concept `c:` | `a` 1 (Capability·Domain·Technology), label *, former *, isA *, partOf *, implies *, distinct * (symmetric: queries read it both ways, so it is written on whichever side the author chose) |
| Organisations | Organisation `org_` | **name** 1, relationship 1 (employer·prospect·both), industry * (-> Domain), size ? |
| Roles | Position `pos_` | organisation 1, **title** 1, functionalTitle ?, **start** 1, **end** ?, state 1 (ended·ongoing·unknown), **seniority** 1, change ? (hire·promotion·lateral·title-change), engagementKind ? (employment·contract·freelance·internship·volunteer·break) |
| Projects | Project `prj_` | **name** 1, position ?, strength 1 (1-5), recency 1 (year), **seniority** ?, domain * (-> Domain), uses * (-> Concept: a tag, not evidence), headlineMetric ? (-> Metric) or noneQuantified ? (true), problem ?, decision ?, outcome ? (prose, `claim=False`) |
| | Achievement `ach_` | project 1, rank 1, **text** 1, cites * (-> Metric), **shows** * (-> Concept: evidence) |
| Metrics | Metric `met_` | subject 1, unit ?, direction ? (increase·decrease) |
| | MetricVersion `met_x.vN` | of 1, **value** 1, **baseline** ?, **kind** ? (absolute·delta·ratio·duration·rank·count), confidence 1 (measured·estimated·reported), source ?, validFrom ?, validUntil ? |
| Skills | Skill `skill_` | name 1, category 1, rank ? (display order in its category), alias * |
| Education | Education `edu_` | **institution** 1, **qualification** 1, field ?, level ? (isced-5·isced-6·isced-7·isced-8), start ?, end ?, gradeScheme ?, gradeValue ? |
| Certifications | Credential `cred_` | **name** 1, **issuer** 1, **issued** ?, expires ?, credentialState 1 (active·expired·lapsed), url ? |
| Open source | OpenSource `os_` | name 1, url 1, **role** 1 (maintainer·contributor·author) |
| Open questions | Question `q_` | about 1 (-> any `k:` id), question 1, asked 1 (date), answered ? (date) |

`seniority` is the closed list of eight from `kbindex.SENIORITY`. A metric holds identity; its numbers
live on its versions, so a bullet cites `met_x` and the current version is resolved when it is read.

### The other file kinds

| File | Class (id) | Predicates |
|---|---|---|
| posting.ttl | Posting `post_` | company 1, title 1, url ?, seniority ?, domain *, captured 1 (date), advert 1 (literal `"posting.md"`: the verbatim advertisement beside it) |
| | Requirement `req_<stem>_<term>` | posting 1, asked 1 (the term as written), quote 1 (the advert's words), necessity 1 (required·preferred·implicit), concept ? (-> Concept: the analyst's choice when a label is ambiguous) |
| application.ttl | Application `app_` | posting 1, view ?, submitted 1 (date, or `false` when held back), channel ?, document *, recordSha256 ?, carried * (-> Achievement), carriedVersion * (-> MetricVersion) |
| | Event `evt_<stem>_<date>_<kind>` | application 1, date 1 (date, or `"unknown"`), kind 1 (the pipeline vocabulary: submitted·acknowledged·screen-scheduled·screen-done·interview-scheduled·interview-done·onsite-scheduled·onsite-done·offer·offer-accepted·rejected·withdrawn·no-response·offer-declined·follow-up-sent·note·referral·recruiter-contact), channel ?, note ?, due ? (date) |
| log.ttl | LogEntry `rev_<N>` | revision 1, date 1, by 1 (apply·confirm·adopt·migrate·fmt), summary 1, touched *, minted *, answer ? (only with `by confirm`), kbSha256 1 |
| vocabulary.ttl | Concept `c:` | as in kb.ttl, restricted to Technology with no `implies` (a P2 rule) |
| changeset.trig | reserved graphs | `op:set`, `op:add`, `op:retire`, `op:delete`, and the triple `op:base op:revision "rN"`. P1 names them; P3 gives them meaning |

**Across files:** a concept in kb.ttl may extend one the shipped vocabulary defines (more labels, more
edges) - the person's vocabulary layered over the shipped one. A `k:` subject defined in two files
is a FAIL.

**Left out on purpose:** eligibility (prose in gaps.md), URS referees and narratives (the KB never held
them). Adding a class later is additive and does not bump the format.

## The canonical writer (`writer.py`)

`write(graph, kind) -> str` is a pure function of the triple set, so the same content always gives
the same bytes: parse(write(g)) == g, and write(parse(write(g))) == write(g).

**File, top to bottom:** the fixed, complete prefix block (`op` in changesets only); the header
subject; sections in ontology order, each opened by `# == <Section>` and one blank line. kb.ttl prints
every banner even when the section is empty, so the structure stays visible - the contract the
Markdown headings had; other kinds omit empty sections.

**Subjects within a section,** by the class's natural key, id breaking ties:

| Section | Order |
|---|---|
| Roles | start descending |
| Organisations | by their newest role's start, descending; organisations with no role last, by id |
| Projects | position order, then recency descending, then id - each project followed by its achievements by rank |
| Metrics | each metric followed by its versions, v1 upward |
| Skills | category, rank, name |
| Education · Certifications | end · issued descending |
| Open questions | asked, then id |
| Vocabulary | Capability, Domain, Technology, then id |
| Events · Log | date (`"unknown"` last) · revision |

**Within a subject:** predicates in ontology order. Predicates sharing a `group` go on one line
joined by ` ; `; the first line starts with the subject; continuation lines are indented four spaces;
the subject ends ` .` then a blank line. **One-line rule:** a subject whose whole text fits in 100
columns and holds no multi-line literal is written on one line. Several objects of one predicate are
sorted - references by id, literals by value - since RDF gives them no order (which is why skills
carry `rank`).

**Literals:** integers, decimals and booleans bare; `xsd:date` typed (`"2026-09-20"^^xsd:date`); a
string without a newline as `"…"`, escaping `\` `"` and the controls `\t` `\r`; a string with a
newline as `"""…"""`, escaping `\` and `"""`, and a final `"` (P0's escaping, `spike.py`). Values are
never reflowed or wrapped. Files are UTF-8, no BOM, LF only, ending in one newline.

**Hand comments.** RDF drops comments, so a rewrite would silently delete a note typed into the file.
The reader reports every `#` line that is not a banner (`io.parse` returns them); validation reports
each as a WARN - "comment on line N will be lost on the next write; move it into `j:note`" - and P3's
`apply` and `fmt` refuse while any exist. Nothing is dropped silently. Preserving comments by
attaching them to the next subject was rejected: they drift when a person reorganises the file.

## Validation (`shapes.py` tier 1, `rules.py` tier 2)

Findings go into a `validate_urs.Report`, one line each, printed with `show()`:

```
FAIL  career/kb.ttl:76 ach_clinical_events_led_migration - j:cites k:met_teem: no such metric
      fix: did you mean k:met_team?
```

Each finding has a rule id, severity, file, line, focus id, detail and fix. The line is the first
`^(k|c):<id>\b` subject line in that file (`io` builds the index while reading). A syntax error is
reported with pyoxigraph's line and column and stops that file before any rule runs; the other files
are still checked.

### Tier 1: generated from the ontology, per file

| Rule | Checks | Severity |
|---|---|---|
| `id-form` | the id's prefix is known and it matches its pattern; `ach_…_<digits>` refused as positional; concept slug pattern | FAIL |
| `id-home` | the class belongs to this file kind | FAIL |
| `closed` | the predicate is defined for the class; the fix names the nearest (difflib) | FAIL |
| `cardinality` | required present; single-valued at most once | FAIL |
| `object` | literal vs reference; datatype or pattern; enum member; a reference's prefix is one the predicate allows | FAIL |
| `no-blank-nodes` | no blank node anywhere | FAIL |
| `no-derived` | no `j:derived` graph and no `rdf:type` on a `k:` id | FAIL |
| `retired-reason` | `retired` without `reason` | FAIL |
| `comment` | a hand comment the next write would drop | WARN |

### Tier 2: SPARQL over the union graph

Each rule is a row `(rule_id, severity, SELECT ?focus ?detail, fix)`.

| Rule | Checks | Severity |
|---|---|---|
| `dangling` | a reference to an id no loaded file defines (the log's `touched`/`minted` excepted: they may name deleted ids) | FAIL |
| `concept-typed` | a `c:` that no loaded file gives a class | FAIL |
| `primary-contact` | `primary` is not one of the person's contact values | FAIL |
| `headline-xor` | a project with both `headlineMetric` and `noneQuantified` | FAIL |
| `duplicate-id` | a `k:` subject defined in two files - reported at each later definition, where the edit was | FAIL |
| `metric-open` | a metric with no version, or more than one without `validUntil` | FAIL |
| `version-orphan` | `met_x.vN` whose `of` is not `met_x` | FAIL |
| `version-gap` | versions not v1..vN contiguous | WARN |
| `rank-unique` | two achievements of one project sharing a rank | FAIL |
| `headline-cited` | a headline metric no achievement of the project cites | WARN |
| `counts-as-cycle` | a cycle through isA, partOf, implies | FAIL |
| `wall-crossed` | an isA/partOf/implies path joining two concepts declared `distinct` | FAIL |
| `label-clash` | one normalised label (lowercase, whitespace to `-`) on two concepts | WARN |
| `inferred-unasked` | an `inferred` or `needs-verification` node with no unanswered question `about` it | WARN |
| `retired-referenced` | a live node referencing a retired one | WARN |
| `answered-before-asked` | `answered` earlier than `asked` | FAIL |
| `application-posting` | an application whose posting is not in its own directory's posting.ttl | FAIL |
| `event-before-submit` | an event dated before its application's submitted date | WARN |
| `concept-class` | a predicate restricted to a concept class (industry, domain -> Domain) points at a concept of another class | FAIL |

`label-clash` stays a WARN: an ambiguous label is legitimate, and P2 turns it into a question.

### Deferred rules

Named so nothing is forgotten; each phase owns its rule.

| Rule | Why not in P1 | Phase |
|---|---|---|
| requirement `quote` appears verbatim in posting.md | reads a Markdown file, not the graph | P2 |
| shipped vocabulary: Technology only, no `implies` | a property of the shipped data P2 writes | P2 |
| kb.ttl changed outside `jsk kb apply` (hash in log.ttl) | needs apply to write the hash | P3 |
| a carried metric version was changed | needs history - the log's hashes | P5 |

**Mutation sweep.** For every rule: the valid fixture plus one edit must produce exactly that rule's
finding at the expected `file:line`. A rule with no registered mutation fails the suite - no rule
exists without a test proving it fires.

## Reading and loading (`io.py`, `store.py`)

**`io.parse(path, kind) -> Parsed(graph, lines, comments)`** normalises CRLF, parses into the named
graph `<file:<path relative to the workspace root>>`, and returns the subject-line index and the
non-banner comments. A `SyntaxError` becomes `GraphError(message, fix, file, line, col)` - the
`KBError(message, fix)` pattern. **pyoxigraph is imported here, lazily, and nowhere at module top**,
so `jsk --help` and every command that never reads the graph do not pay its 11-12 ms import.

**`store.load(root) -> Store`**:

1. find `career/kb.ttl`, `career/log.ttl`, `applications/*/posting.ttl`,
   `applications/*/application.ttl`, and the shipped `src/jsk/data/vocabulary.ttl` - a missing file
   is simply absent;
2. parse each into its own graph;
3. derive `rdf:type` from each `k:` id's prefix into `j:derived`;
4. validate: tier 1 per file, then tier 2 over the union;
5. materialise the counts-as closure into `j:derived` - Path nodes with `from`, `to`, `hops`,
   `implied`, `via`, hop limit 2, one-way from narrower to broader (graphsim's
   `materialise_paths`).

`Store` exposes `.report`, `.select(sparql)` (union graph), `.file_of(id)` and `.graph(file)` (for
the writer). `j:derived` is never written. `load` never raises on invalid content - it reports, and
the caller decides; it raises only for an unreadable path.

The shipped `vocabulary.ttl` in P1 is a seed of about ten Technology concepts, enough for the loader
and closure tests; P2 fills it out.

**Budget:** load and validate a workspace of 300 projects and 100 applications (about 15,700 quads
with the derived ones) in under 400 ms. Drafting P1 measured 250-390 ms (parse 80, tier 1 70, tier 2
50, the rest inserts and the closure); P0's 70 ms timed a load and two queries, not about twenty rules.
The test asserts 3x, so a slow CI runner cannot make it flaky.

## Packaging, preflight, CI

- **`pyproject.toml`:** `dependencies = ["pyoxigraph>=0.5.11,<0.6"]`, `requires-python = ">=3.10"`,
  and the "deliberately empty" comment rewritten to say why this one is the exception (abi3 wheels
  on every platform, no transitive dependencies, P0) and that the rest stay optional.
- **`src/jsk/preflight.py`:** `MIN_PYTHON = (3, 10)`; a `GRAPH_MODULES` list and a required "graph
  record package" check, the pattern `gates` and `urs` already follow, each module added by the task
  that creates it (adding one early turns doctor BLOCKED); a pyoxigraph `Check` via `find_spec`, so preflight stays
  standard-library only. Missing, it reports "cannot read or validate the graph record (kb.ttl) -
  matching and career writes unavailable" with an `INSTALL["pyoxigraph"]` hint. It is not in
  `REQUIRED` while the render path does not use it.
- **`.gitattributes`:** `*.ttl text eol=lf` and `*.trig text eol=lf`. Without it a Windows checkout with
  `core.autocrlf` turns the golden fixtures into CRLF and the byte-for-byte tests fail there only.
  (P7's `jsk new` writes the same line into a person's workspace.)
- **`.github/workflows/test.yml`:** keep the two ubuntu / 3.13 jobs; add **Python 3.10, no TeX** (the
  floor) and **Windows, Python 3.13, no TeX** (paths, file locks, CRLF). The no-engine assertion step
  runs with `shell: bash` so it works on both. The Preflight step is fixed at the same time: without a
  TeX engine `jsk doctor` is BLOCKED by design, which has failed the no-engine job on every run since
  2026-09-01; a no-engine job now asserts that the TeX engine is the only FAIL instead.

## Tests

| File | Covers |
|---|---|
| `tests/test_graph_ontology.py` | every predicate has a doc, a group and an object kind; every enum non-empty; prefixes unique; every class has one file kind and a section; every section is in its file kind's order |
| `tests/test_graph_io.py` | round-trip and byte idempotence over one fixture per file kind; a seeded generator of random valid graphs from the ontology (write, parse, same triples; write again, same bytes); escaping (`"""` inside, runs of quotes, trailing `"`, `\`, tab, non-ASCII, `→`); CRLF in, LF out; syntax error names file:line:col; comments reported |
| `tests/test_graph_shapes.py` | tier 1: one mutation per rule, each naming file:line, focus and fix |
| `tests/test_graph_rules.py` | tier 2: the same, plus a wall declared from either side |
| `tests/test_graph_budget.py` | the load budget |
| `tests/test_graph_store.py` | the fixture workspace loads with an empty report; derived types; closure paths, the hop limit, implies marking; a missing file is absent, not an error |

**Fixture workspace, `tests/graph_fixtures/`:** `career/kb.ttl` (the approved sample, extended with
education, open source, a retired entry and a second metric version), `career/log.ttl`, and one
application directory with `posting.ttl`, `posting.md` and `application.ttl`. The kb.ttl golden is
the writer's output for the sample's triples, reviewed against `sample-kb.tight.ttl`; where it
differs (the `tag:` prefixes, sorted multi-values, the one-line rule), the difference is listed in
the commit that adds it.

## Exit criteria

1. The fixture workspace loads with no findings, and each of its files round-trips byte for byte.
2. Every tier-1 and tier-2 rule has a mutation that fires it at the right `file:line`.
3. `python -m pytest tests -q -n auto` and `python -m ruff check src tests` pass on all four CI jobs.
4. `jsk doctor` shows the pyoxigraph check `ok` and still passes with no graph file anywhere.
5. No command's output changes: the existing suite passes unmodified apart from the Python floor.
