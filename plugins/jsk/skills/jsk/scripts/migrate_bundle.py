#!/usr/bin/env python3
"""Migrate an OKF career bundle to the current layout revision.

Usage:
  python3 migrate_bundle.py <bundle>            report what would change
  python3 migrate_bundle.py <bundle> --apply    make the changes

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = already current, or --apply finished with nothing left for a person.
Exit 1 = changes are pending (report mode), or something needs a person.
Exit 2 = called wrong.

Report mode exiting 1 is deliberate: it makes `migrate_bundle.py <bundle>` usable
as a check, so an out-of-date bundle is detectable without writing to it.

Standard library only. Frontmatter is edited line by line rather than round-tripped
through a YAML parser, because a dump-and-rewrite erases comments, key order and
quoting style across the whole file - a lot of collateral damage for renaming one
key. A migration should be legible in a diff.

Nothing is deleted. A key may be renamed when the new key carries the same value,
but no value is dropped, and no file is removed.
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pipeline_model  # noqa: E402

CURRENT_REVISION = 5

REVISIONS = {
    1: "applications point at a mutable target file (`target:`) and carry `outcome:`",
    2: "the posting is frozen beside each application as `<stem>.target.md`",
    3: "an application's outcome is derived from an append-only timeline",
    4: "the posting is a UJD document, `<stem>.posting.json`, not Markdown frontmatter",
    5: "roles and projects declare their relations in frontmatter, so the record compiles",
}

# `outcome:` values seen in the wild, mapped onto timeline events. `offer` maps to an
# advancing event rather than a terminal one, because an old record saying "offer" does
# not say whether it was accepted - and guessing which would be inventing the ending.
OUTCOME_TO_EVENT = {
    "offer": "offer",
    "accepted": "accepted",
    "declined": "declined",
    "rejected": "rejected",
    "rejected-at-screen": "rejected",
    "rejected-after-interview": "rejected",
    "withdrawn": "withdrawn",
    "no-response": "no-response",
    "ghosted": "no-response",
}


# ---------------------------------------------------------------- frontmatter

def split_frontmatter(text):
    """Return (fm_lines, body) or None when there is no usable frontmatter."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    return text[4:end].split("\n"), text[end + 5:]


def join_frontmatter(fm_lines, body):
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def scalar(raw):
    """The value of a frontmatter line, minus quotes and any trailing comment."""
    raw = raw.strip()
    if raw[:1] in ('"', "'"):
        quote = raw[0]
        end = raw.find(quote, 1)
        return raw[1:end] if end != -1 else raw[1:]
    return raw.split("#")[0].strip()


def fm_get(fm_lines, key):
    for line in fm_lines:
        if line.startswith(key + ":"):
            return scalar(line[len(key) + 1:])
    return None


def fm_index(fm_lines, key):
    for i, line in enumerate(fm_lines):
        if line.startswith(key + ":"):
            return i
    return -1


# --------------------------------------------------------------------- change

class Change:
    """One edit, described before it is made and applied only on request."""

    def __init__(self, verb, subject, detail, action):
        self.verb = verb          # create | update | stamp
        self.subject = subject    # bundle-relative path
        self.detail = detail
        self.action = action

    def apply(self):
        self.action()


# ------------------------------------------------------------------ detection

def detect_revision(root):
    """Read the stamp from index.md. Absent means r1 - every bundle predates it."""
    index = os.path.join(root, "index.md")
    if not os.path.exists(index):
        return None
    parts = split_frontmatter(open(index, encoding="utf-8").read())
    if not parts:
        return None
    stamped = fm_get(parts[0], "okf_bundle")
    if stamped is None:
        return 1
    try:
        return int(stamped)
    except ValueError:
        return None


# --------------------------------------------------------------- r1 -> r2

# Two banners, because the caveat is only true when the dates differ. Telling someone
# a same-day snapshot "may have moved on since" is a warning about drift that could not
# have happened, and a caveat that is obviously wrong is one nobody reads twice.
FREEZE_BANNER_LATE = """
**FROZEN SNAPSHOT - reconstructed at migration on {today}, not captured at submission.**

This is what [{working}]({working}) said on {today}. The application was submitted {when}, and the
working copy is editable, so this is not necessarily the posting that was applied against. Marked
`needs-verification` for that reason. If you still have the original advertisement, check it against
this, then set `status: confirmed` and drop `snapshot_late`.
"""

FREEZE_BANNER_SAME_DAY = """
**FROZEN SNAPSHOT - reconstructed at migration on {today}, not captured at submission.**

Taken from [{working}]({working}) on the same day the application was submitted, so it is very
likely the posting that was applied against - but a migration cannot prove the working copy was
untouched earlier that day. Marked `needs-verification` for that reason alone; confirming it is
usually a glance.
"""


def freeze_text(target_text, stem, today, submitted):
    """Build the archived copy of a Job Target, stamped for what it actually is."""
    parts = split_frontmatter(target_text)
    if not parts:
        return None
    fm_lines, body = parts

    out = []
    for line in fm_lines:
        if line.startswith("type:"):
            out.append("type: Source Document")
        elif line.startswith("status:"):
            out.append("status: needs-verification")
        else:
            out.append(line)
    if fm_index(out, "type") == -1:
        out.insert(0, "type: Source Document")
    if fm_index(out, "status") == -1:
        out.append("status: needs-verification")

    working = f"../targets/{stem}.md"
    out += [
        f'snapshot_of: "{working}"',
        f"snapshot_taken: {today}",
        "snapshot_late: true",
    ]

    if submitted and str(submitted) == today:
        banner = FREEZE_BANNER_SAME_DAY.format(today=today, working=working)
    else:
        when = f"on {submitted}" if submitted else "at some earlier date"
        banner = FREEZE_BANNER_LATE.format(today=today, working=working, when=when)
    return join_frontmatter(out, banner + body)


def plan_application(root, rel, today, changes, blocked, planned=None):
    """Plan the r1 -> r2 edits for one Application concept."""
    path = os.path.join(root, rel)
    parts = split_frontmatter(open(path, encoding="utf-8").read())
    if not parts:
        blocked.append(f"{rel}: no usable frontmatter - migrate this one by hand")
        return
    fm_lines, _ = parts
    if fm_get(fm_lines, "type") != "Application":
        return

    stem = os.path.basename(rel)[:-3]
    app_dir = os.path.dirname(rel)
    frozen_rel = os.path.join(app_dir, stem + ".target.md").replace("\\", "/")
    working_rel = fm_get(fm_lines, "target") or f"../targets/{stem}.md"
    working_abs = os.path.normpath(os.path.join(root, app_dir, working_rel))

    # 1. the posting itself
    frozen_ok = os.path.exists(os.path.join(root, frozen_rel))
    if not frozen_ok:
        if not os.path.exists(working_abs):
            blocked.append(
                f"{rel}: no working target at {working_rel} - the posting was never captured, "
                "and a migration cannot invent one. Paste it in by hand, or record that it is lost."
            )
        else:
            submitted = fm_get(fm_lines, "submitted")
            frozen = freeze_text(open(working_abs, encoding="utf-8").read(), stem, today, submitted)
            if frozen is None:
                blocked.append(f"{working_rel}: no usable frontmatter - cannot freeze it safely")
            else:
                def write(dest=os.path.join(root, frozen_rel), text=frozen):
                    open(dest, "w", encoding="utf-8").write(text)
                changes.append(Change(
                    "create", frozen_rel,
                    f"frozen from {working_rel}, marked needs-verification (a late snapshot)",
                    write))
                frozen_ok = True
                # r3 -> r4 converts frozen postings, and in a single r1 -> r4 run this
                # file does not exist on disk yet - every change is planned before any
                # is applied. Recording the text here is what stops the last bundle in
                # the chain from being the only one whose archive keeps its Markdown.
                if planned is not None:
                    planned[frozen_rel] = frozen

    # 2. the pointers, which must say which copy they mean.
    # `posting:` is only written when there is - or will be - something for it to point
    # at. Naming a file the migration just reported it could not create would turn one
    # honest blocker into a dangling pointer that reads as if it resolved.
    had_target = fm_index(fm_lines, "target") != -1
    wants_posting = frozen_ok and fm_index(fm_lines, "posting") == -1
    wants_working = had_target or (fm_index(fm_lines, "target_working_copy") == -1
                                   and os.path.exists(working_abs))
    if wants_posting or wants_working:
        def repoint(p=path, stem=stem, working_rel=working_rel,
                    wants_posting=wants_posting, wants_working=wants_working):
            fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
            replacement = []
            if wants_posting:
                replacement.append(f'posting: "{stem}.target.md"')
            if wants_working:
                replacement.append(f'target_working_copy: "{working_rel}"')
            i = fm_index(fm_lines, "target")
            if i != -1:
                fm_lines[i:i + 1] = replacement
            else:
                anchor = fm_index(fm_lines, "record")
                at = anchor if anchor != -1 else len(fm_lines)
                fm_lines[at:at] = replacement
            open(p, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

        if wants_posting and had_target:
            detail = "target: -> target_working_copy:, and posting: added for the frozen copy"
        elif wants_posting:
            detail = "posting: and target_working_copy: added"
        else:
            detail = "target: -> target_working_copy: (no posting: - nothing to freeze)"
        changes.append(Change("update", rel, detail, repoint))


def plan_r1_to_r2(root, today, changes, blocked, planned=None):
    apps = os.path.join(root, "tailoring", "applications")
    if not os.path.isdir(apps):
        return
    for name in sorted(os.listdir(apps)):
        if not name.endswith(".md") or name == "index.md" or name.endswith(".target.md"):
            continue
        plan_application(root, f"tailoring/applications/{name}", today, changes,
                         blocked, planned)


# --------------------------------------------------------------- r2 -> r3

# A date sitting in the `# Outcome` prose, which is where it usually is:
# "Rejected after first interview, 2026-07-02."
PROSE_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def timeline_rows(fm_lines, body):
    """Reconstruct what the frontmatter and prose can support, and no more.

    `outcome: rejected-after-interview` records *what* happened, never *when*. Where
    the date cannot be established this writes `unknown` rather than a plausible
    guess: a fabricated date would be indistinguishable from a recorded one, which is
    exactly the confusion the provenance rules exist to prevent.
    """
    rows = []
    submitted = fm_get(fm_lines, "submitted")
    channel = fm_get(fm_lines, "channel") or ""
    rows.append((submitted or "unknown", "submitted", channel,
                 "" if submitted else "[reconstructed at migration - date not recorded]", ""))

    outcome = fm_get(fm_lines, "outcome")
    event = OUTCOME_TO_EVENT.get((outcome or "").strip())
    if event:
        # Only look after the outcome heading; a date earlier in the file belongs to
        # something else, and borrowing it would be the guess this avoids.
        tail = body.split("# Outcome", 1)[1] if "# Outcome" in body else ""
        found = PROSE_DATE.search(tail)
        date = found.group(1) if found else "unknown"
        note = f"was `outcome: {outcome}`"
        if date == "unknown":
            note += " [reconstructed at migration - date not recorded]"
        rows.append((date, event, "", note, ""))
    return rows


def render_timeline(rows):
    out = ["", "# Timeline", "",
           "| Date | Event | Channel | Note | Due |",
           "|---|---|---|---|---|"]
    for date, event, channel, note, due in rows:
        out.append(f"| {date} | {event} | {channel} | {note} | {due} |")
    return "\n".join(out) + "\n"


def plan_timeline(root, rel, changes):
    path = os.path.join(root, rel)
    parts = split_frontmatter(open(path, encoding="utf-8").read())
    if not parts:
        return
    fm_lines, body = parts
    if fm_get(fm_lines, "type") != "Application":
        return
    if "# Timeline" in body:
        return

    rows = timeline_rows(fm_lines, body)
    # An `offer` row leaves the application live: the record never said how it ended.
    live = len(rows) == 1 or rows[-1][1] not in pipeline_model.TERMINAL

    def write(p=path, rows=rows):
        fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
        i = fm_index(fm_lines, "outcome")
        if i != -1:
            # Kept for one revision, not deleted. Marked, so nobody edits it expecting
            # it to mean anything - the timeline decides the outcome now.
            fm_lines[i] = fm_lines[i] + "   # DEPRECATED at r3 - the timeline is the outcome"
        open(p, "w", encoding="utf-8").write(
            join_frontmatter(fm_lines, body.rstrip("\n") + "\n" + render_timeline(rows)))

    detail = f"{len(rows)} row(s) from submitted:" + (" and outcome:" if not live else "")
    if live:
        detail += " - live, so the history between then and now needs a person"
    changes.append(Change("update", rel, detail, write))
    return live


def plan_organisation(root, rel, changes):
    path = os.path.join(root, rel)
    parts = split_frontmatter(open(path, encoding="utf-8").read())
    if not parts:
        return
    fm_lines, _ = parts
    if fm_get(fm_lines, "type") != "Organisation":
        return
    if fm_index(fm_lines, "relationship") != -1:
        return

    def write(p=path):
        fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
        at = fm_index(fm_lines, "type")
        fm_lines.insert(at + 1 if at != -1 else 0, "relationship: employer")
        open(p, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

    changes.append(Change("update", rel, "relationship: employer - what it already was", write))


def plan_r2_to_r3(root, changes, blocked):
    vocab = os.path.join(root, "framework", "pipeline-vocabulary.md")
    if not os.path.exists(vocab):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        def write(dest=vocab, ts=stamp):
            open(dest, "w", encoding="utf-8").write(pipeline_model.vocabulary_markdown(ts))
        changes.append(Change("create", "framework/pipeline-vocabulary.md",
                              "the event vocabulary the timeline is checked against", write))

    orgs = os.path.join(root, "organisations")
    if os.path.isdir(orgs):
        for name in sorted(os.listdir(orgs)):
            if name.endswith(".md") and name != "index.md":
                plan_organisation(root, f"organisations/{name}", changes)

    apps = os.path.join(root, "tailoring", "applications")
    if not os.path.isdir(apps):
        return
    live = 0
    for name in sorted(os.listdir(apps)):
        if not name.endswith(".md") or name == "index.md" or name.endswith(".target.md"):
            continue
        if plan_timeline(root, f"tailoring/applications/{name}", changes):
            live += 1
    if live:
        blocked.append(
            f"{live} live application(s) have no history beyond submission. Everything between "
            "then and now is in somebody's inbox, not the bundle - run /jsk:pipeline and "
            "fill them in one at a time."
        )


# --------------------------------------------------------------- r3 -> r4

# The single fact this migration cannot recover, stated on every requirement it
# writes. A Job Target file held one list of requirements with no
# required-versus-preferred modifier, so promoting all of them to must-have is the
# only reading that does not silently discard a distinction - and it is exactly the
# loss the UJD spec's own schema.org mapping table predicts.
NECESSITY_NOTE = ("necessity is not recoverable from a Job Target file: it held one "
                  "list with no required-versus-preferred modifier. Every requirement "
                  "here is must-have and needs review.")


def fm_list(fm_lines, key):
    """A frontmatter list, from either the inline or the block form."""
    index = fm_index(fm_lines, key)
    if index == -1:
        return []
    raw = fm_lines[index][len(key) + 1:].strip()
    if raw.startswith("["):
        inner = raw[1:raw.rfind("]")] if "]" in raw else raw[1:]
        return [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
    values = []
    for line in fm_lines[index + 1:]:
        stripped = line.strip()
        if not stripped.startswith("- "):
            break
        values.append(stripped[2:].strip().strip("\"'"))
    return [v for v in values if v]


def posting_body(body):
    """The advertisement, taken from the target file's own `# Posting` section.

    Only that section. The ranking and gap headings beneath it are this toolchain's
    own earlier output, and carrying them into source.raw_text would let a later
    span check pass against text that was never in the advertisement.
    """
    capture, out = False, []
    for line in body.split("\n"):
        if line.startswith("# "):
            capture = line.strip().lower().startswith("# posting")
            continue
        if capture:
            out.append(line)
    return "\n".join(out).strip()


def target_to_ujd(text, stem, today):
    """A Job Target file as a conformance Level 0 UJD document."""
    parts = split_frontmatter(text)
    if not parts:
        return None
    fm_lines, body = parts
    raw_text = posting_body(body)

    requirements = []
    for key, kind in (("required_capabilities", "capability"),
                      ("required_technologies", "technology")):
        for value in fm_list(fm_lines, key):
            requirements.append({
                "id": "req_r4_%d" % (len(requirements) + 1),
                "kind": kind,
                "necessity": "must-have",
                "value": value,
                "provenance": {
                    "status": "needs-verification",
                    "asserted": today,
                    # The caveat rides on source.label, where the schema puts a note
                    # about how a claim was read. Provenance itself takes no free text.
                    "source": {"kind": "posting-text", "label": NECESSITY_NOTE},
                },
            })

    doc = {
        "$schema": "https://openresume.dev/ujd/v1/posting.schema.json",
        "ujd": "1.0.0",
        "meta": {
            "id": "ujd:migrated:" + stem,
            "updated": today,
            "generator": "migrate_bundle.py r3->r4",
            # No self-declared conformance. The validator computes the level this
            # document actually reaches, and a migrated file claiming its own grade
            # is the sort of assertion the whole format is built to avoid.
        },
        "posting": {
            "id": "pst_" + (re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "migrated"),
            "title": fm_get(fm_lines, "role") or fm_get(fm_lines, "title") or stem,
            "retrieved": today,
            "status": "unknown",
        },
    }
    company = fm_get(fm_lines, "company")
    if company:
        doc["organization"] = {"id": "org_migrated", "name": company}
    url = fm_get(fm_lines, "source")
    if url and url.startswith("http"):
        doc["posting"]["url"] = url

    role = {}
    domains = fm_list(fm_lines, "domains")
    if domains:
        role["domains"] = domains
    seniority = fm_get(fm_lines, "seniority_sought")
    if seniority:
        role["seniority"] = seniority
    if role:
        doc["role"] = role
    if requirements:
        doc["requirements"] = requirements

    doc["source"] = {
        "raw_format": "markdown",
        "ingested_from": "manual",
        "ingest_notes": [
            NECESSITY_NOTE,
            "Migrated from a Job Target Markdown file. Requirement values are the "
            "vocabulary terms a person typed while decomposing the posting, so no "
            "source.span can be recovered and this stays at conformance Level 0.",
        ],
    }
    if raw_text:
        doc["source"]["raw_text"] = raw_text
    else:
        doc["source"]["ingest_notes"].append(
            "The target file carried no `# Posting` section, so the advertisement "
            "itself is gone. Nothing downstream can check an extraction against it.")
    return doc


def plan_target(root, rel, today, changes, blocked, text=None):
    """One Job Target file to one UJD document, written beside it.

    `text` is supplied when the source is a file an earlier step is only planning to
    write, which is the r1 -> r4 case: nothing is on disk until every step has been
    planned.
    """
    stem = os.path.basename(rel)
    for suffix in (".target.md", ".md"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    out_rel = "%s/%s.posting.json" % (os.path.dirname(rel), stem)
    if os.path.exists(os.path.join(root, out_rel)):
        return

    if text is None:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            text = fh.read()
    doc = target_to_ujd(text, stem, today)
    if doc is None:
        blocked.append("%s has no readable frontmatter, so nothing could be read from "
                       "it. Convert it by hand, or re-capture the posting." % rel)
        return
    count = len(doc.get("requirements") or [])

    def write(dest=os.path.join(root, out_rel), payload=doc):
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    changes.append(Change(
        "create", out_rel,
        "%d requirement(s) from frontmatter, all must-have and needs-verification; "
        "the Markdown is left in place" % count, write))
    if count:
        blocked.append(
            "%s: %d requirement(s) are must-have because a Job Target file could not "
            "say otherwise. Some of them were preferred, and nothing here can tell "
            "which - read the posting and set `necessity`." % (out_rel, count))


def plan_r3_to_r4(root, today, changes, blocked, planned=None):
    for folder in ("targets", "applications"):
        directory = os.path.join(root, "tailoring", folder)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".md") or name == "index.md":
                continue
            # In targets/ every Markdown file is a posting. In applications/ only the
            # frozen `.target.md` is - the bare `<stem>.md` is the application log.
            if folder == "applications" and not name.endswith(".target.md"):
                continue
            plan_target(root, "tailoring/%s/%s" % (folder, name), today, changes, blocked)

    # Postings an earlier step is about to write. Without this an r1 -> r4 run leaves
    # every archived posting as Markdown, because nothing had been applied yet when
    # this step listed the directory.
    for rel, text in sorted((planned or {}).items()):
        plan_target(root, rel, today, changes, blocked, text=text)

    if not os.path.exists(os.path.join(root, "resume-generation", "record.json")):
        blocked.append(
            "resume-generation/record.json does not exist yet. It is the standing URS "
            "transcription of this bundle, and everything downstream now reads it - the "
            "scorer, the gap analysis and the author. jsk-record-builder writes it on "
            "the first /jsk:tailor run. A migration cannot: transcribing prose into "
            "evidence is not a text substitution.")


# ------------------------------------------- r4 -> r5: the relational keys

MONTHS = {m: "%02d" % i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def ladder_date(cell):
    """Aug 2015 -> 2015-08. Present -> None, which is what ongoing means."""
    text = cell.strip().strip("*").strip()
    if not text or text.lower() in ("present", "now", "current", "-", "ongoing"):
        return None
    m = re.match(r"^([A-Za-z]{3})[a-z]*\.?\s+(\d{4})$", text)
    if m and m.group(1).lower() in MONTHS:
        return "%s-%s" % (m.group(2), MONTHS[m.group(1).lower()])
    m = re.match(r"^(\d{4})-(\d{2})", text)
    if m:
        return "%s-%s" % (m.group(1), m.group(2))
    m = re.match(r"^(\d{4})$", text)
    return m.group(1) if m else None


def read_ladder(root):
    """The Career Progression concept's ladder, one row per role, in its own order.

    The relational spine was already written down here - which employer, from when to
    when, in what order. It was just never in a place a compile could read.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            parts = split_frontmatter(open(path, encoding="utf-8").read())
            if not parts or fm_get(parts[0], "type") != "Career Progression":
                continue
            rows = []
            for line in parts[1].splitlines():
                if not line.startswith("|") or set(line.strip()) <= set("|- "):
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) < 4 or cells[0].lower().strip("*") == "role":
                    continue
                rows.append(cells)
            if rows:
                return rows
    return []


def org_stem(cell, org_stems):
    """The organisations/ file a ladder cell names, by link or by name."""
    link = re.search(r"\(([^)]+)\)", cell)
    if link:
        stem = os.path.basename(link.group(1)).replace(".md", "")
        if stem in org_stems:
            return stem
    plain = re.sub(r"[\[\]]", "", re.sub(r"\([^)]*\)", "", cell)).strip().lower()
    if not plain:
        return None
    head = plain.split()[0]
    for stem in sorted(org_stems):
        if stem.startswith(head) or head in stem:
            return stem
    return None


def plan_r4_to_r5(root, changes, blocked):
    roles_dir = os.path.join(root, "roles")
    if not os.path.isdir(roles_dir):
        return
    org_stems = set()
    orgs_dir = os.path.join(root, "organisations")
    if os.path.isdir(orgs_dir):
        org_stems = {n[:-3] for n in os.listdir(orgs_dir)
                     if n.endswith(".md") and n != "index.md"}

    ladder = read_ladder(root)
    if not ladder:
        blocked.append(
            "no Career Progression concept with a ladder table, so the roles' employers "
            "and dates cannot be read from anywhere. Add organisation, start, end, state "
            "and change to each roles/*.md by hand - bundle-spec.md, 'The relational keys'.")
        return

    seen_org, by_title = set(), {}
    for cells in ladder:
        title = re.sub(r"[*`]", "", cells[0]).strip()
        stem = org_stem(cells[1], org_stems)
        entry = {"organisation": stem,
                 "start": ladder_date(cells[2]),
                 "end": ladder_date(cells[3]),
                 "org_cell": cells[1],
                 "change": "hire" if stem not in seen_org else "promotion"}
        seen_org.add(stem)
        by_title[title.lower()] = entry

    for name in sorted(os.listdir(roles_dir)):
        if not name.endswith(".md") or name == "index.md":
            continue
        rel = "roles/" + name
        path = os.path.join(roles_dir, name)
        parts = split_frontmatter(open(path, encoding="utf-8").read())
        if not parts:
            continue
        fm_lines, _ = parts
        if fm_get(fm_lines, "type") != "Role":
            continue
        if fm_index(fm_lines, "organisation") != -1:
            continue
        title = (fm_get(fm_lines, "title") or "").strip().strip('"')
        row = by_title.get(title.lower()) or by_title.get(title.split(" - ")[0].strip().lower())
        if not row:
            blocked.append(
                "%s: %r is not a row in the career-progression ladder, so its employer and "
                "dates cannot be established. Add them by hand." % (rel, title))
            continue
        if not row["organisation"]:
            blocked.append(
                "%s: the ladder names %s, which has no concept in organisations/. A role "
                "cannot be for a company the bundle does not know - write that concept "
                "first." % (rel, row["org_cell"]))
            continue
        if not row["start"]:
            blocked.append("%s: the ladder gives no readable start date." % rel)
            continue

        lines = ["organisation: " + row["organisation"], "start: " + row["start"]]
        if row["end"]:
            lines += ["end: " + row["end"], "state: ended"]
        else:
            lines += ["state: ongoing"]
        lines.append("change: " + row["change"])

        def write(p=path, add=tuple(lines)):
            fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
            at = fm_index(fm_lines, "status")
            if at == -1:
                at = len(fm_lines) - 1
            for offset, line in enumerate(add):
                fm_lines.insert(at + 1 + offset, line)
            open(p, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

        changes.append(Change("update", rel, ", ".join(lines), write))

    # A project points at the role it was done under. The body already carries the link
    # a reader follows; this is the key a compile reads.
    projects_dir = os.path.join(root, "projects")
    if not os.path.isdir(projects_dir):
        return
    role_stems = {n[:-3] for n in os.listdir(roles_dir)
                  if n.endswith(".md") and n != "index.md"}
    for name in sorted(os.listdir(projects_dir)):
        if not name.endswith(".md") or name == "index.md":
            continue
        rel = "projects/" + name
        path = os.path.join(projects_dir, name)
        parts = split_frontmatter(open(path, encoding="utf-8").read())
        if not parts:
            continue
        fm_lines, body = parts
        if fm_get(fm_lines, "type") != "Project" or fm_index(fm_lines, "role") != -1:
            continue
        found = None
        for _label, target in re.findall(r"\*\*Role:\*\*\s*\[([^\]]+)\]\(([^)]+)\)", body):
            stem = os.path.basename(target).replace(".md", "")
            if stem in role_stems:
                found = stem
                break
        if not found:
            blocked.append(
                "%s: no **Role:** link in the body, so the role it was done under is "
                "recorded nowhere. Add `role: <stem>` to its frontmatter." % rel)
            continue

        def write_project(p=path, stem=found):
            fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
            at = fm_index(fm_lines, "status")
            if at == -1:
                at = len(fm_lines) - 1
            fm_lines.insert(at + 1, "role: " + stem)
            open(p, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

        changes.append(Change("update", rel, "role: " + found, write_project))


# ------------------------------------------------------------------ the stamp

def plan_stamp(root, revision, changes):
    index = os.path.join(root, "index.md")

    def stamp(p=index, rev=revision):
        fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
        i = fm_index(fm_lines, "okf_bundle")
        line = f"okf_bundle: {rev}"
        if i == -1:
            at = fm_index(fm_lines, "type")
            fm_lines.insert(at + 1 if at != -1 else 0, line)
        else:
            fm_lines[i] = line
        open(p, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

    changes.append(Change("stamp", "index.md", f"okf_bundle: {revision}", stamp))


# ------------------------------------------------------------------------ cli

def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("bundle")
    ap.add_argument("--apply", action="store_true", help="make the changes (default: report only)")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    root = args.bundle
    if not os.path.isdir(root):
        print(f"not a directory: {root}")
        print("fix:  pass the bundle root - the folder holding index.md and projects/")
        return 2

    print(f"migrate_bundle.py   bundle: {root}")

    revision = detect_revision(root)
    if revision is None:
        print("cannot read index.md frontmatter - is this a bundle?")
        print("fix:  run validate_bundle.py first; a bundle without a readable index.md")
        print("      cannot be migrated safely, because nothing identifies its shape.")
        return 2

    print(f"bundle revision: {revision}   current: {CURRENT_REVISION}")
    if revision >= CURRENT_REVISION:
        print(f"\nalready at revision {CURRENT_REVISION} - nothing to do")
        return 0

    changes, blocked = [], []
    # Files a step plans to create, for the steps that come after it. Every change is
    # planned before any is applied, so a later step cannot see an earlier one's work
    # on disk.
    planned = {}
    today = datetime.date.today().isoformat()

    # Each step runs only when the bundle is below it AND the target reaches it. Guarding
    # on `revision < N` alone would run a step the target excludes and then stamp a lower
    # number over it - a bundle that lies about its own shape, which is worse than one
    # carrying no stamp at all.
    if revision < 2 <= CURRENT_REVISION:
        print(f"\nr1 -> r2  {REVISIONS[2]}")
        plan_r1_to_r2(root, today, changes, blocked, planned)
    if revision < 3 <= CURRENT_REVISION:
        print(f"\nr2 -> r3  {REVISIONS[3]}")
        plan_r2_to_r3(root, changes, blocked)
    if revision < 4 <= CURRENT_REVISION:
        print(f"\nr3 -> r4  {REVISIONS[4]}")
        plan_r3_to_r4(root, today, changes, blocked, planned)
    if revision < 5 <= CURRENT_REVISION:
        print(f"\nr4 -> r5  {REVISIONS[5]}")
        plan_r4_to_r5(root, changes, blocked)
    plan_stamp(root, CURRENT_REVISION, changes)

    done = {"create": "created", "update": "updated", "stamp": "stamped"}
    for c in changes:
        prefix = ("would " + c.verb) if not args.apply else done[c.verb]
        print(f"  {prefix:<14} {c.subject}")
        print(f"  {'':<14}   {c.detail}")

    print(f"\nCHANGES {len(changes)} | NEEDS A PERSON {len(blocked)}")
    for b in blocked:
        print(f"  ! {b}")

    if not args.apply:
        print("\nDRY RUN - nothing written. Re-run with --apply")
        return 1

    for c in changes:
        c.apply()

    print(f"\nMIGRATED to revision {CURRENT_REVISION}")
    if blocked:
        print("Some things could not be migrated - see above. They are listed, not guessed.")
        return 1
    print("Run validate_bundle.py to confirm the result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
