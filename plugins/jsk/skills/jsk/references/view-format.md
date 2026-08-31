# URS Views — the tailoring model

**The URS specification is in two files, and this is the half about selection.**
`references/urs-spec.md` is the other half: the record's own shape — periods, provenance, metrics,
achievements, names, the three levels of employment, grades, skills, region profiles, privacy,
conformance and interoperability. Everything a view points *at* is defined there. Every key a view
may *carry* is defined here.

The split exists for one reader. `jsk-resume-author` is told to read the view format before it
writes anything, and the view format was a sixth of the file it had to read to get it; the rest is
record shape it never authors, because it reads the compiled record itself rather than the schema
the record is compiled to. The read went from 4,127 tokens to 968.

**A split, never a copy.** No view key is defined in `urs-spec.md`, and no record key is defined
here. Neither file restates the other, and that is a structural rule rather than a courtesy: a
specification in two halves that paraphrase each other stops agreeing the moment one is edited, and
nobody finds out until a validator rejects a document the other half called legal. If you are adding
a view key, it belongs here even if you found the gap while editing `urs-spec.md`; if you are adding
a record key, it belongs there even if you found the gap while editing this file.

A view is a rendering instruction. It selects, orders, redacts and sets a budget.

```json
{ "id": "view_acme",
  "label": "Principal Engineer @ Acme",
  "format_profile": "ats-maximal",
  "region_profile": "urs:profile:au/1",
  "locale": "en-AU",
  "target": { "title": "Principal Engineer", "ref": "tailoring/targets/acme.md" },
  "narrative": "nar_acme",
  "include": [ { "ref": "eng_1", "order": 1, "achievements": ["ach_latency", "ach_scale"] } ],
  "redact": ["person.phone"],
  "provenance_floor": "confirmed",
  "budget": { "pages": 2 } }
```

**`order` orders achievements, never employers.** Within an `include` entry, the `achievements`
list is rendered in the order written — that is how a bullet earns the top of a role. The entry's
own `order` is read and then overridden: engagements always render by date, because a resume that
reorders employers by relevance reads as concealment and breaks the date parsing every ATS does
first. `render.order` in the region profile chooses which direction that date sort runs.

**Normative: a view MUST NOT contain content text.** It may carry only references, ordering,
redaction and presentation settings. `label` and `target` are metadata about the application, not
resume content, and are never rendered into the document body.

This is the rule that earns the format its existence. Tailoring becomes auditable by construction,
and "the model embellished my resume" becomes structurally impossible rather than something you hope
did not happen. A validator enforces it by rejecting any unknown free-text field inside a view.

**A `.view.md` on disk is not this document.** It is an OKF concept whose frontmatter happens to be a
view, so it also carries the bundle's own bookkeeping — `type`, `title`, `description`, `timestamp`,
`status`, and `frozen`/`frozen_date` once an application has archived it. `okf_compile.py` strips
those before a view reaches URS, which is why none of them appear above: what sits on disk is a
concept, and what is validated here is a view. The two were once read as the same thing, and the
result was that `frozen: true` — which `mode-ship.md` instructs on every shipped application —
failed the record gate as an unknown view key, permanently.

`provenance_floor` makes a view refuse content below a given status. `confirmed` is the default for
anything a person will actually send.

`format_profile` is `presentation`, `ats-maximal`, `plaintext` or `web`, matching the variants in
`ats-rules.md`.
