# resume.json

One resume: what was chosen for one posting, and nothing the career holds. Names, dates,
employers, bullet text and metrics come from `career/kb.ttl` every time the resume is built, so
a confirm or a corrected bullet is on the next render with nothing to update here.

```json
{
  "resume": 2,
  "format": "presentation",
  "region": "in",
  "pages": 2,
  "summary": { "text": "Full-stack engineer who builds AI agents ...", "status": "inferred" },
  "bullets": ["ach_chloe_care_plan_directed_claude_code", "ach_mindbody_dahua_solo_designed_built"],
  "roles": ["pos_contract_backend"],
  "skills": ["skill_python", "skill_typescript", "skill_react"]
}
```

| key | required | what it holds |
|---|---|---|
| `resume` | yes | `2` |
| `bullets` | yes | `ach_` ids in render order within each role. Roles, employers and their order follow from the career, by date. |
| `format` | no | `presentation` (default) or `ats-maximal` |
| `region` | no | a two-letter code: `au`, `ae`, `in` pick their profile, any other (`us`, `xx`) the default one; it also sets the paper. Default the person's country |
| `pages`, `ats_pages` | no | page budgets; `ats_pages` for the ATS-maximal variant |
| `floor` | no | provenance floor, default `confirmed`: a bullet or summary below it is withheld, with a warning |
| `summary` | no | `{text, status}`, `status` `inferred` or `confirmed`; absent, the career's positioning |
| `roles` | no | `pos_` ids to show with no bullet, for chronology |
| `skills` | no | `skill_` ids in row order; absent, every skill |

`jsk ship --ats-max` overrides `format`, and `jsk render --region` overrides `region`, for one render.

**The summary is the only prose in it.** A reworded bullet goes into the career first
(`jsk kb apply`) and is named here by its id; an unknown key fails. Once the person confirms the
summary, set its `"status": "confirmed"` — the one edit a confirm ever needs here.

```bash
jsk kb export --from-match applications/<stem>/posting.ttl --out applications/<stem>/resume.json
jsk kb export --select <ach_/prj_/pos_ ids> --out resume.json      # a general resume
jsk validate applications/<stem>/resume.json
```

Export never writes over an existing file: edit it. `jsk validate` is the record gate. It fails
the shape, an id the career does not hold or has retired, a bullet whose project has no role, a
number in a bullet that no current version of a metric it cites holds, and a career that does not
validate or that `log.ttl` does not vouch for (`jsk kb adopt`); it warns of labels, "N years of X"
and brackets. A full URS record (`"urs"` key) from before is converted once: `jsk migrate <workspace>` for
every application's, `jsk migrate <resume.json>` for one anywhere else.
