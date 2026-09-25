# URS Views — the tailoring model

The URS specification is in two files; this half defines every key a **view** may carry.
`urs-spec.md` defines the record — everything a view points *at*. Neither restates the other: a new
view key belongs here, a new record key there.

A view is a rendering instruction. It selects, orders, redacts and sets a budget.

```json
{ "id": "view_acme",
  "label": "Principal Engineer @ Acme",
  "format_profile": "ats-maximal",
  "region_profile": "urs:profile:au/1",
  "locale": "en-AU",
  "target": { "title": "Principal Engineer", "ref": "applications/<stem>/posting.md" },
  "narrative": "nar_acme",
  "include": [ { "ref": "eng_1", "order": 1, "achievements": ["ach_latency", "ach_scale"] } ],
  "redact": ["person.phone"],
  "provenance_floor": "confirmed",
  "budget": { "pages": 2 } }
```

**`order` orders achievements, never employers.** Within an `include` entry, `achievements` render
in the order written. The entry's own `order` is read and then overridden: engagements always render
by date (reordering employers reads as concealment and breaks ATS date parsing). `render.order` in
the region profile sets the sort direction.

**Normative: a view MUST NOT contain content text.** It carries only references, ordering, redaction
and presentation settings. `label` and `target` are application metadata, never rendered into the
body. A validator enforces this by rejecting any unknown free-text field inside a view.

**The view lives inside `resume.json` and carries only the keys above** — `jsk validate` fails an
unrecognised one. Application bookkeeping (when sent, frozen, which posting) belongs in the
application's `application.ttl`, never in the view; a `frozen: true` key fails the record gate.

`provenance_floor` makes a view withhold content below a given status (a `withheld` warning, not a
failure). `confirmed` is the default for
anything a person will send.

`format_profile` is `presentation`, `ats-maximal`, `plaintext` or `web`, matching the variants in
`ats-rules.md`.
