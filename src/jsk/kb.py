#!/usr/bin/env python3
"""Scaffold a career knowledge base: one Markdown file, and a place to file applications.

Usage: python3 -m jsk.kb <path> --name "Their Name" [--force]
       <path>     the directory to create the knowledge base in
       --name     the person's full name; it seeds the identity block
       --force    overwrite an existing user-knowledgebase.md

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = written. Exit 1 = refused, because something was already there. Exit 2 =
called wrongly.

The template is here rather than in the skill's Markdown so that every knowledge base
starts from the same headings in the same order. The skill edits this file directly
afterwards with ordinary file tools - there is no write layer and no command per noun,
because there is no longer a several-file transaction for one of them to make atomic.
A knowledge base is one file, so a write to it either happened or did not.

What the headings are for is written into the file itself, as HTML comments beneath
each one. Guidance in a template a person is looking at gets read; guidance in a
specification they have to go and find does not.
"""
import os
import sys

from .cliutil import docstring_usage, wants_help

FILENAME = "user-knowledgebase.md"

TEMPLATE = """---
kb: 1
name: __NAME__
updated: __DATE__
---

# Career knowledge base - __NAME__

<!-- This one file is the source of truth for every resume rendered from it. A resume
     is a selection out of this file, never a document edited on its own: two hand-kept
     documents stop agreeing the moment one is edited, silently, usually in the copy
     that gets sent.

     Every claim carries `status`: `confirmed` (they said it, or it is in a source
     document), `inferred` (drafted but unverified) or `needs-verification` (a known
     gap). Nothing marked `inferred` reaches a resume until the person has confirmed
     it. -->

## Identity

<!-- The parse gate fails a resume with no email and no phone, so this block is what
     makes the file able to render anything sendable at all. -->

```yaml
full_name: __NAME__
given_name:
family_name:
headline:                 # the title they present as, not necessarily their job title
location:
  city:
  region:
  country:                # ISO 3166-1 alpha-2, e.g. AU
  mode:                   # onsite | hybrid | remote
contacts:
  - kind: email
    value:
    primary: true
  - kind: phone
    value:
  - kind: linkedin
    value:
  - kind: github
    value:
status: needs-verification
```

## Positioning

<!-- Two or three sentences in their own words: what they are for, who they are useful
     to, and the through-line the evidence below actually proves. A summary on a resume
     is retuned from this per posting; it is never this text pasted in. -->

_Not captured yet._

## Work authorization and languages

```yaml
work_authorization:
  - jurisdiction:         # ISO 3166-1 alpha-2
    kind:                 # citizen | permanent | work-visa | student | none
    status: held
    label:
languages:
  - language:
    native: true
```

## Vocabulary

<!-- The matching axis. Capabilities compare as EXACT STRINGS when a posting is scored
     against this file, so a synonym silently breaks matching. Add a term here in the
     same edit that first uses it. Only backticked list items count as vocabulary. -->

### Capabilities

_None recorded yet._

### Domains

_None recorded yet._

### Seniority (fixed vocabulary - do not extend)

`architecture-ownership` - `product-ownership` - `platform-design` -
`team-leadership` - `technical-ownership` - `hands-on-senior` - `hands-on` - `junior`

## Organisations

<!-- One `###` per employer or client. The id is what roles and projects point at. -->

_None recorded yet._

## Roles

<!-- One `###` per job title. Roles sharing an `organisation` render as progression
     within one employer rather than as unrelated jobs, ordered by `start`, and
     `change` is what names the step. -->

_None recorded yet._

## Projects

<!-- The evidence. One `###` per engagement or product, each with its selection
     metadata, the story in prose, and the resume lines its prose earned.

### Client or product - what it is `proj_slug`

```yaml
id: proj_slug
role: role_slug             # the Role id it was done under
strength: 5                 # 1-5. Evidence quality. 5 = flagship, 1 = filler
recency: 2026
seniority: architecture-ownership
domains: [healthcare]
capabilities: [ai-platform-architecture]
technologies: [azure, bicep]
headline_metric: metric_slug    # or: none-quantified
status: confirmed
```

**The problem.** What was wrong, and for whom.

**What I decided.** The judgement calls that were actually theirs.

**What changed.** The outcome, with the number if there is one.

**Bullets**

- Cut p95 clinical event latency from 5 minutes to under 1 second across 40,000
  daily ingestion jobs.
  - metric: metric_latency
  - status: confirmed
-->

_None recorded yet._

## Metrics

<!-- Every verified number, recorded once. A bullet names a row here rather than
     restating the figure, which is what stops a rewritten clause inflating it -
     "cut latency 62%" becoming "by over 60%" becoming "by two thirds".
     `confidence` is `measured`, `estimated` or `self-reported`. -->

| id | subject | baseline | value | unit | direction | confidence | source | status |
|---|---|---|---|---|---|---|---|---|

## Skills

<!-- Display names, grouped and aliased - deliberately not the same thing as a
     project's `capabilities`. Those are matching vocabulary; these are how the block
     should read. An ATS-maximal render expands each one with its aliases. -->

_None recorded yet._

## Education

<!-- One `###` per qualification, most recent first.

### Master of Engineering, Computer Science `edu_meng`

```yaml
id: edu_meng
institution: Anna University
qualification: Master of Engineering
field: Computer Science
level: isced-7              # isced-5 diploma - 6 bachelor - 7 master - 8 doctorate
start: 2010
end: 2012
grade:                      # only where the market expects it - India and the Gulf do
  scheme: in-cgpa-10
  value: 8.4
status: confirmed
```
-->

_None recorded yet._

## Certifications

<!-- Only what was actually earned. Never write a credential, or call one "in
     progress", unless they said so. "None held" is a legitimate state. -->

_None held._

## Open source

<!-- Public code, and what their part in it actually was. A maintainer, a regular
     contributor and somebody with one merged typo fix are three different claims, and
     only the first two belong on a resume.

- carbon-aware-scheduler `os_carbon_scheduler`
  - url: https://github.com/example/carbon-aware-scheduler
  - role: maintainer          # maintainer | contributor | author
  - status: confirmed
-->

_None recorded yet._

## Open questions

<!-- The gap queue. One row per thing somebody still has to answer, newest last.
     Anything `inferred` above should have a row here until it is confirmed. -->

| id | question | about | asked | answered |
|---|---|---|---|---|

## Log

<!-- Dated, appended to, never edited. When an earlier mistake is found, record the
     correction rather than quietly fixing it: a knowledge base that hides its errors
     cannot be trusted. -->

| date | what changed |
|---|---|
| __DATE__ | Knowledge base created. |
"""

APPLICATIONS_README = """# Applications

One directory per submission, named `<yyyy-mm-dd>-<company>-<role>` - the date being
the day it was sent. Each holds the whole of that application:

| File | Is |
|---|---|
| `posting.md` | the advertisement verbatim, with its requirements in frontmatter |
| `gaps.md` | the assessment of the knowledge base against it, and the question queue |
| `resume.json` | the URS record this submission rendered from |
| `<Name>_<Company>_Resume.{tex,pdf,txt}` | the files actually sent |
| `application.md` | the log: what was sent, through what channel, and what came back |

**Everything in here is frozen at submission.** The knowledge base keeps moving; an
application that pointed at a moving record could not answer what it was answering.

An application worked through and then held back is still a real application. Write
`submitted: false` in its `application.md` frontmatter rather than inventing a date.
"""


def scaffold(root, name, force=False):
    """(exit code, lines to print). Writes the file, or refuses and says why."""
    import datetime

    lines = []
    target = os.path.join(root, FILENAME)
    if os.path.exists(target) and not force:
        return 1, [f"FAIL  already exists: {target}",
                   "fix:  edit it, or pass --force to start over from the template"]

    os.makedirs(root, exist_ok=True)
    today = datetime.date.today().isoformat()
    body = TEMPLATE.replace("__NAME__", name).replace("__DATE__", today)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    lines.append(f"wrote  {target}")

    apps = os.path.join(root, "applications")
    readme = os.path.join(apps, "README.md")
    if not os.path.exists(readme):
        os.makedirs(apps, exist_ok=True)
        with open(readme, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(APPLICATIONS_README)
        lines.append(f"wrote  {readme}")

    lines.append("")
    lines.append("The Identity block is the one to fill in first: without an email and")
    lines.append("a phone number the parse gate fails, so nothing sendable renders.")
    return 0, lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2

    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]

    name = None
    if "--name" in argv:
        at = argv.index("--name")
        if at + 1 >= len(argv):
            print("--name needs a value")
            print('fix:  --name "Their Name"')
            return 2
        name = argv[at + 1]
        del argv[at:at + 2]

    if len(argv) != 1:
        print("usage: jsk new <path> --name \"Their Name\"")
        return 2
    if not name:
        print("--name is required")
        print("fix:  the identity block is seeded from it, and a knowledge base that")
        print("      cannot say whose it is renders nothing sendable")
        return 2

    code, lines = scaffold(argv[0], name, force=force)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
