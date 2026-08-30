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

Nothing is deleted. A key may be renamed when the new key carries the same value and
r7 moves the application archive into year directories, but no value is dropped, no
file is removed, and nothing is ever written over a file that is already there. Where
the bundle does not record something - the year an application was sent, which
application a loose resume belongs to - it is reported and left alone.
"""
import argparse
import datetime
import json
import os
import posixpath
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pipeline_model  # noqa: E402

CURRENT_REVISION = 7

REVISIONS = {
    1: "applications point at a mutable target file (`target:`) and carry `outcome:`",
    2: "the posting is frozen beside each application as `<stem>.target.md`",
    3: "an application's outcome is derived from an append-only timeline",
    4: "the posting is a UJD document - superseded by 5, which puts it back "
       "into Markdown",
    5: "roles and projects declare their relations in frontmatter so the record "
       "compiles, and the posting is `<stem>.posting.md` again",
    6: "the working posting r5 replaced is marked `superseded_by:`, and every live "
       "reference points at the posting",
    7: "the application archive is partitioned by submission year",
}

# A frontmatter line carrying a single scalar. Lists and nested maps are skipped, which
# is correct here: no path-valued key in the layout is ever a list.
FM_SCALAR = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):[ \t]+(\S.*)$")
LINK_TARGET = re.compile(r"\]\(([^)]+)\)")
MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

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


def plan_application(root, rel, today, changes, blocked):
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


def plan_r1_to_r2(root, today, changes, blocked):
    apps = os.path.join(root, "tailoring", "applications")
    if not os.path.isdir(apps):
        return
    for name in sorted(os.listdir(apps)):
        if not name.endswith(".md") or name == "index.md" or name.endswith(".target.md"):
            continue
        plan_application(root, f"tailoring/applications/{name}", today, changes,
                         blocked)


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
# required-versus-preferred modifier, so promoting all of them to `required` is the
# only reading that does not silently discard a distinction.
NECESSITY_NOTE = ("necessity is not recoverable from a Job Target file: it held one "
                  "list with no required-versus-preferred modifier. Every requirement "
                  "here is `required` and needs review.")


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
    own earlier output, and carrying them into the new posting would leave a person
    re-reading this framework's guesses as though the employer had written them.
    """
    capture, out = False, []
    for line in body.split("\n"):
        if line.startswith("# "):
            capture = line.strip().lower().startswith("# posting")
            continue
        if capture:
            out.append(line)
    return "\n".join(out).strip()


def quote(value):
    """A frontmatter scalar, quoted only when leaving it bare would change it."""
    value = value or ""
    if value and not re.search(r"""[:#\[\]{}'"\n]|^[-?&*!|>%@`]|^\s|\s$""", value):
        return value
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def target_to_posting(text, stem):
    """A revision 3 Job Target file as a revision 5 posting.

    The advertisement moves into the body verbatim and the two flat requirement
    lists become one `requirements:` block. Nothing is invented: `label` is left off
    entirely rather than filled with the vocabulary term, because a term someone
    typed while decomposing a posting is not the posting's own wording.
    """
    parts = split_frontmatter(text)
    if not parts:
        return None, 0
    fm_lines, body = parts

    pairs = []
    for key, kind in (("required_capabilities", "capability"),
                      ("required_technologies", "technology")):
        pairs += [(value, kind) for value in fm_list(fm_lines, key)]

    out = ["type: Job Posting"]
    out.append("title: " + quote(fm_get(fm_lines, "role")
                                 or fm_get(fm_lines, "title") or stem))
    for source_key, key in (("company", "company"), ("source", "url"),
                            ("seniority_sought", "seniority")):
        value = fm_get(fm_lines, source_key)
        if value:
            out.append("%s: %s" % (key, quote(value)))
    domains = fm_list(fm_lines, "domains")
    if domains:
        out.append("domains: [%s]" % ", ".join(domains))
    out.append("status: needs-verification")
    for index, (value, kind) in enumerate(pairs):
        if not index:
            out.append("requirements:")
        out.append("  - value: " + quote(value))
        out.append("    kind: " + kind)
        out.append("    necessity: required")

    advertisement = posting_body(body) or (
        "<!-- The Job Target file carried no `# Posting` section, so the "
        "advertisement itself is gone. Paste it back here. -->")
    return join_frontmatter(out, "\n# Posting\n\n" + advertisement + "\n"), len(pairs)


def ujd_to_posting(doc):
    """A revision 4 UJD document as a revision 5 posting.

    Every key the ranking reads has a home in frontmatter. The rest of that document
    - provenance spans, requirement groups, a self-scored aggregate - is dropped,
    which is the whole point of the revision: nothing but its own validator read it.
    """
    posting = doc.get("posting") or {}
    role = doc.get("role") or {}
    out = ["type: Job Posting", "title: " + quote(posting.get("title"))]
    company = (doc.get("organization") or {}).get("name")
    if company:
        out.append("company: " + quote(company))
    if posting.get("url"):
        out.append("url: " + quote(posting["url"]))
    if role.get("seniority"):
        out.append("seniority: " + quote(role["seniority"]))
    if role.get("domains"):
        out.append("domains: [%s]" % ", ".join(role["domains"]))
    out.append("status: needs-verification")

    requirements = doc.get("requirements") or []
    for index, req in enumerate(requirements):
        if not index:
            out.append("requirements:")
        out.append("  - value: " + quote(req.get("value")))
        out.append("    kind: " + (req.get("kind") or "capability"))
        necessity = req.get("necessity") or "required"
        out.append("    necessity: " + {"must-have": "required",
                                        "nice-to-have": "preferred"}.get(
                                            necessity, necessity))
        label = ((req.get("provenance") or {}).get("source") or {}).get("text")
        if label:
            out.append("    label: " + quote(label))

    advertisement = ((doc.get("source") or {}).get("raw_text") or "").strip() or (
        "<!-- The UJD document carried no source.raw_text, so the advertisement "
        "itself is gone. Paste it back here. -->")
    return (join_frontmatter(out, "\n# Posting\n\n" + advertisement + "\n"),
            len(requirements))


def plan_posting(root, rel, changes, blocked):
    """One working posting - a Job Target or a UJD document - to `<stem>.posting.md`.

    The source is left where it is. Nothing reads it any more, but deleting somebody's
    only copy of an advertisement to save a few kilobytes is not a trade a migration
    gets to make on their behalf.
    """
    stem = os.path.basename(rel)
    for suffix in (".posting.json", ".target.md", ".md"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    out_rel = "%s/%s.posting.md" % (os.path.dirname(rel), stem)
    if os.path.exists(os.path.join(root, out_rel)):
        return

    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        text = fh.read()

    note = None
    if rel.endswith(".json"):
        try:
            written, count = ujd_to_posting(json.loads(text))
        except ValueError as exc:
            blocked.append("%s is not readable JSON (%s), so nothing could be read "
                           "from it. Convert it by hand." % (rel, exc))
            return
        detail = "%d requirement(s) carried over; the JSON is left in place" % count
    else:
        written, count = target_to_posting(text, stem)
        if written is None:
            blocked.append("%s has no readable frontmatter, so nothing could be read "
                           "from it. Convert it by hand, or re-capture the posting."
                           % rel)
            return
        detail = ("%d requirement(s) from frontmatter, all required and unverified; "
                  "the Markdown is left in place" % count)
        if count:
            note = "%s: %d requirement(s) - %s" % (out_rel, count, NECESSITY_NOTE)

    def write(dest=os.path.join(root, out_rel), payload=written):
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)

    changes.append(Change("create", out_rel, detail, write))
    if note:
        blocked.append(note)


def plan_postings(root, changes, blocked):
    """Every working posting to Markdown, one per stem.

    A bundle that stopped at revision 4 holds both sources for the same posting: the
    Job Target file r3 left in place and the UJD document r4 wrote beside it. They
    describe one job and land on one filename, so only one can be the source - and it
    is the JSON, which is the later document and the only one that ever recorded a
    required-versus-preferred distinction.

    `tailoring/targets/` only. The copy beside an application was frozen when that
    application was sent, and it is already Markdown - `<stem>.target.md`, written by
    r1 -> r2. Rewriting it would edit an archive to match a convention that postdates
    it, which is the one thing an archive exists to prevent.
    """
    directory = os.path.join(root, "tailoring", "targets")
    if not os.path.isdir(directory):
        return
    sources = {}
    for name in sorted(os.listdir(directory)):
        if name == "index.md" or name.endswith(".posting.md"):
            continue
        if name.endswith(".posting.json"):
            sources[name[: -len(".posting.json")]] = name
        elif name.endswith(".md"):
            sources.setdefault(name[:-3], name)
    for _, name in sorted(sources.items()):
        plan_posting(root, "tailoring/targets/" + name, changes, blocked)


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


# ------------------------------------------- r5 -> r6: retiring the working posting


def superseded_targets(root, pending=()):
    """`tailoring/targets/<stem>.md` that `<stem>.posting.md` has replaced.

    r5 converted every working posting to `<stem>.posting.md` and deliberately left the
    source where it was - deleting somebody's only copy of an advertisement is not a
    trade a migration gets to make on their behalf. What it could not do was say so on
    the file. So a migrated bundle holds two documents per job, nothing on either one
    names the live copy, and the indexes still link to the retired one. This step
    writes the relationship down; the file still is not deleted.

    `pending` names the postings r4 -> r5 is about to write in this same run. Reading
    only the filesystem was the regression: a bundle coming from r1 has no
    `<stem>.posting.md` on disk when this step is planned, so nothing looked superseded,
    nothing was marked, and `--apply` finished by producing a bundle that
    validate_bundle.py rejects on the rule this very step exists to satisfy.
    """
    directory = os.path.join(root, "tailoring", "targets")
    if not os.path.isdir(directory):
        return {}
    names = set(os.listdir(directory))
    names |= {posixpath.basename(p) for p in pending
              if posixpath.dirname(p) == "tailoring/targets"}
    found = {}
    for name in sorted(names):
        if not name.endswith(".md") or name == "index.md":
            continue
        if name.endswith((".posting.md", ".gaps.md", ".view.md")):
            continue
        stem = name[: -len(".md")]
        if stem + ".posting.md" in names:
            found[stem] = "tailoring/targets/" + name
    return found


def repointed(rel, candidate, retired):
    """`candidate` with `.posting.md` on it, when it names a retired working posting.

    Resolved against the referring file rather than matched as a string: `../targets/x.md`
    and `x.md` are the same document seen from two directories, and only one of them
    looks like the path being retired.
    """
    if "://" in candidate or candidate.startswith(("mailto:", "#")):
        return None
    bare, _, anchor = candidate.partition("#")
    if not bare.endswith(".md"):
        return None
    resolved = os.path.normpath(os.path.join(os.path.dirname(rel), bare))
    if resolved.replace(os.sep, "/") not in retired:
        return None
    moved = bare[: -len(".md")] + ".posting.md"
    return moved + ("#" + anchor if anchor else "")


ARCHIVED_COMPANION = (".target.md", ".posting.md", ".gaps.md", ".view.md")


def is_archive(rel, fm_lines):
    """Whether this file was frozen when an application was sent."""
    if fm_get(fm_lines, "frozen") == "true":
        return True
    directory, _, name = rel.rpartition("/")
    return (directory.endswith("tailoring/applications")
            and name.endswith(ARCHIVED_COMPANION))


def plan_repoint(root, retired, changes):
    """Every live reference to a retired working posting, moved onto the posting.

    Both shapes matter. `target_working_copy:` is by definition the pointer to the
    editable copy, so an application holding it on a retired file names a document
    nobody maintains. Index links are how a person finds any of this at all.

    **Archives are skipped**, and identified structurally rather than by `frozen: true`:
    the snapshots the r1 -> r2 step wrote predate that key, so trusting it would rewrite
    exactly the oldest archives. Everything beside an application except the Application
    concept itself is frozen by the layout, whatever its frontmatter says.

    **Prose is left alone outside an `index.md`.** A link in a project or in `log.md` is
    a record of what somebody wrote at the time; the retired file still exists and now
    names its successor in frontmatter, so the reader gets there in one hop. An index is
    navigation and is meant to be current, which is the whole reason a stale one is worth
    fixing.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if rel in retired:
                continue
            parts = split_frontmatter(open(path, encoding="utf-8").read())
            if not parts:
                continue
            fm_lines, body = parts
            if is_archive(rel, fm_lines):
                continue

            moves = []
            for line in fm_lines:
                match = FM_SCALAR.match(line)
                if not match:
                    continue
                value = scalar(match.group(2))
                moved = repointed(rel, value, retired)
                if moved:
                    moves.append(("%s:" % match.group(1), value, moved))
            links = []
            for target in (LINK_TARGET.findall(body) if name == "index.md" else ()):
                moved = repointed(rel, target, retired)
                if moved:
                    links.append((target, moved))
            if not moves and not links:
                continue

            def write(p=path, keys=tuple(moves), body_links=tuple(links)):
                fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
                # Matched on the value, not on the key the value was found under: an
                # earlier step in the same run renames `target:` to
                # `target_working_copy:`, and a key-anchored rewrite silently did
                # nothing once it had.
                for _key, was, now in keys:
                    for i, line in enumerate(fm_lines):
                        match = FM_SCALAR.match(line)
                        if match and scalar(match.group(2)) == was:
                            fm_lines[i] = line.replace(was, now, 1)
                            break
                for was, now in body_links:
                    body = body.replace("](%s)" % was, "](%s)" % now)
                open(p, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

            detail = ", ".join(
                ["%s %s -> %s" % (k, w, n) for k, w, n in moves]
                + ["link %s -> %s" % (w, n) for w, n in links])
            changes.append(Change("update", rel, detail, write))


def plan_r5_to_r6(root, changes, blocked, pending=()):
    retired = superseded_targets(root, pending)
    for stem, rel in sorted(retired.items()):
        path = os.path.join(root, rel)
        parts = split_frontmatter(open(path, encoding="utf-8").read())
        if not parts:
            blocked.append("%s has no readable frontmatter, so it cannot be marked "
                           "superseded. Compare it with %s.posting.md by hand and "
                           "delete it if nothing in it is worth keeping." % (rel, stem))
            continue
        fm_lines, _ = parts
        if fm_index(fm_lines, "superseded_by") != -1:
            continue
        target = stem + ".posting.md"

        def write(p=path, value=target):
            fm_lines, body = split_frontmatter(open(p, encoding="utf-8").read())
            at = fm_index(fm_lines, "status")
            if at == -1:
                at = len(fm_lines) - 1
            fm_lines.insert(at + 1, "superseded_by: " + value)
            open(p, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

        changes.append(Change("update", rel, "superseded_by: " + target, write))

    if retired:
        plan_repoint(root, set(retired.values()), changes)


# ------------------------------------------- r6 -> r7: the archive, by year

# The stem already carries the submission date, so for anything written since r2 the
# year is in the filename. Only an older stem needs the frontmatter read.
STEM_YEAR = re.compile(r"^(\d{4})-\d{2}-\d{2}-")
SUBMITTED_YEAR = re.compile(r"^(\d{4})-\d{2}-\d{2}")
YEAR_DIR = re.compile(r"^(?:\d{4}|undated)$")
APPLICATION_COMPANIONS = (".target.md", ".posting.md", ".gaps.md", ".view.md")
UNDATED = "undated"


def application_stem(name):
    """The stem a Markdown file in tailoring/applications/ belongs to.

    None for anything that is not Markdown. A sent resume is named after the person and
    the company rather than after the application - `Priya_Raman_Acme_Resume.pdf` - so it
    cannot be grouped by its own name and is attributed separately.
    """
    for suffix in APPLICATION_COMPANIONS:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name[:-3] if name.endswith(".md") else None


def links_to(root, apps_rel, stem, name):
    path = os.path.join(root, apps_rel, stem + ".md")
    if not os.path.exists(path):
        return False
    text = open(path, encoding="utf-8").read()
    return any(t.split("#")[0] == name for t in LINK_TARGET.findall(text))


def attribute(root, apps_rel, name, groups):
    """The application a loose file - a sent resume, an attachment - belongs to.

    Three signals, strongest first: the filename carries the stem, the application log
    links to the file, or there is only one application it could belong to. Anything
    else returns None and is reported. A resume filed under the wrong application is a
    worse record than one nobody moved, and company names in a filename are exactly
    close enough to make that mistake plausible.
    """
    named = sorted((s for s in groups if name.startswith(s)), key=len, reverse=True)
    if named:
        return named[0]
    linked = [s for s in sorted(groups) if links_to(root, apps_rel, s, name)]
    if len(linked) == 1:
        return linked[0]
    if not linked and len(groups) == 1:
        return next(iter(groups))
    return None


def group_year(root, apps_rel, stem):
    """The submission year, or None where the bundle does not record one."""
    match = STEM_YEAR.match(stem)
    if match:
        return match.group(1)
    leader = os.path.join(root, apps_rel, stem + ".md")
    if os.path.exists(leader):
        parts = split_frontmatter(open(leader, encoding="utf-8").read())
        if parts:
            match = SUBMITTED_YEAR.match(fm_get(parts[0], "submitted") or "")
            if match:
                return match.group(1)
    return None


def archive_resolver(root, moves):
    """Where a bundle-relative path ends up, given the moves this migration makes.

    None for anything the bundle does not hold. A migration rebases the references it
    can prove; rewriting one that already dangles would only move the dangle somewhere
    harder to spot.
    """
    def resolve(rel):
        if rel in moves:
            return moves[rel]
        if rel == ".." or rel.startswith("../"):
            return None
        return rel if os.path.exists(os.path.join(root, rel)) else None
    return resolve


def rebase_target(target, old_rel, new_rel, resolve):
    """One relative reference, seen from the file's new home.

    Resolved against where the file was and recomputed from where it lands, rather than
    counting `../` segments. That is the same arithmetic for a companion in the same
    directory, a posting two levels up and an application in another year, so it cannot
    drift out of step with the layout the way a hand-counted prefix does.
    """
    if not target or "://" in target or target.startswith(("mailto:", "#", "/")):
        return None
    bare, sep, anchor = target.partition("#")
    if not bare or os.path.isabs(bare):
        return None
    was_at = posixpath.normpath(posixpath.join(posixpath.dirname(old_rel), bare))
    landed = resolve(was_at)
    if landed is None:
        return None
    if landed == was_at and posixpath.dirname(old_rel) == posixpath.dirname(new_rel):
        # Neither end of the reference moved. Recomputing it anyway would rewrite
        # `./x.md` to `x.md` across the bundle - a diff that says nothing.
        return None
    now = posixpath.relpath(landed, posixpath.dirname(new_rel) or ".")
    return None if now == bare else now + (sep + anchor if sep else "")


def rebase_text(text, old_rel, new_rel, resolve):
    """`text` with every relative reference recomputed for `new_rel`.

    Frontmatter scalars and body links both: `target_working_copy:` and a link in the
    prose are the same promise and break the same way.
    """
    parts = split_frontmatter(text)
    fm_lines, body = parts if parts else (None, text)
    if fm_lines is not None:
        for i, line in enumerate(fm_lines):
            match = FM_SCALAR.match(line)
            if not match:
                continue
            was = scalar(match.group(2))
            now = rebase_target(was, old_rel, new_rel, resolve)
            if now:
                fm_lines[i] = line.replace(was, now, 1)

    def one(match):
        label, target = match.group(1), match.group(2)
        now = rebase_target(target, old_rel, new_rel, resolve)
        if not now:
            return match.group(0)
        # A link whose text is its own path - the freeze banner writes one - is showing
        # the reader a path, so the shown path has to be the one that resolves.
        return "[%s](%s)" % (now if label == target else label, now)

    body = MARKDOWN_LINK.sub(one, body)
    return join_frontmatter(fm_lines, body) if fm_lines is not None else body


def year_index(root, apps_rel, year, stems):
    """The index a year directory needs, listing what is in it."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    when = ("Applications with no recorded submission date." if year == UNDATED
            else f"Applications submitted in {year}.")
    lines = [f'---\ntype: Index\ntitle: "Applications {year}"\n'
             f'description: "{when}"\ntimestamp: {ts}\n---\n']
    for stem in stems:
        leader = os.path.join(root, apps_rel, year, stem + ".md")
        title = stem
        if os.path.exists(leader):
            parts = split_frontmatter(open(leader, encoding="utf-8").read())
            if parts:
                title = fm_get(parts[0], "title") or stem
        lines.append(f"- [{title}]({stem}.md)")
    return "\n".join(lines) + "\n"


def plan_r6_to_r7(root, changes, blocked, pending=()):
    """Every application in the flat archive into `applications/<year>/`.

    The archive is the one part of a bundle that only grows. At a hundred applications a
    flat directory is four hundred files nobody can read, and the frozen `.view.md`
    copies in it collide in the compiler with the live views they were taken from. The
    year is immutable and already recorded, which is why it - and not the outcome, which
    changes - is what the layout partitions on.
    """
    apps_rel = "tailoring/applications"
    apps = os.path.join(root, apps_rel)
    if not os.path.isdir(apps):
        return

    entries = sorted(os.listdir(apps))
    for name in entries:
        if os.path.isdir(os.path.join(apps, name)) and not YEAR_DIR.match(name):
            blocked.append(
                f"{apps_rel}/{name}/: not a year directory, so revision 7 has no place "
                "for it and this migration will not guess one. Move what is in it into "
                "the year each application was submitted.")

    flat = {n for n in entries if os.path.isfile(os.path.join(apps, n))}
    # An r1 bundle reaches r7 in one run, so the archive it is asked to partition
    # includes the snapshots the r1 -> r2 step is about to write beside each
    # application. Planning against the filesystem alone would move the application out
    # from under its own frozen posting.
    flat |= {posixpath.basename(p) for p in pending
             if posixpath.dirname(p) == apps_rel}
    flat.discard("index.md")

    groups = {}
    for name in sorted(flat):
        stem = application_stem(name)
        if stem:
            groups.setdefault(stem, []).append(name)
    for name in sorted(n for n in flat if application_stem(n) is None):
        owner = attribute(root, apps_rel, name, groups)
        if owner:
            groups[owner].append(name)
        else:
            blocked.append(
                f"{apps_rel}/{name}: belongs to no application this migration can name, "
                "so it stays where it is. Move it into the year directory of the "
                "application that sent it.")

    moves, per_year, undated = {}, {}, []
    for stem in sorted(groups):
        year = group_year(root, apps_rel, stem)
        if year is None:
            year = UNDATED
            undated.append(stem)
        placed = []
        for name in sorted(groups[stem]):
            new_rel = f"{apps_rel}/{year}/{name}"
            if os.path.exists(os.path.join(root, new_rel)):
                blocked.append(
                    f"{new_rel} already exists, so {apps_rel}/{name} was left where it "
                    "is rather than written over. Compare the two and keep the one that "
                    "belongs there.")
                continue
            moves[f"{apps_rel}/{name}"] = new_rel
            placed.append(name)
        if placed:
            per_year.setdefault(year, []).append(stem)
            changes.append(Change(
                "move", f"{apps_rel}/{stem}.*",
                "%d file(s) -> %s/, relative links rebased one level deeper"
                % (len(placed), year),
                _mover(root, [(f"{apps_rel}/{n}", f"{apps_rel}/{year}/{n}")
                              for n in placed], moves)))

    for stem in undated:
        blocked.append(
            f"{apps_rel}/{stem}.md: neither the stem nor `submitted:` gives a submission "
            f"date, so it went to {apps_rel}/{UNDATED}/ rather than into a guessed year. "
            "Add `submitted:` and move it.")

    plan_archive_indexes(root, apps_rel, per_year, moves, changes)
    plan_archive_relinks(root, moves, changes)


def _mover(root, pairs, moves):
    """Move one application's files, rewriting each one's references on the way.

    Rewritten before the move rather than after, and re-read at apply time rather than
    planned as a string edit: earlier revision steps in the same run have been writing
    into these files, and this step has to rebase what is in them then, not what was in
    them when the run was planned.
    """
    def action():
        resolve = archive_resolver(root, moves)
        for old_rel, new_rel in pairs:
            src, dst = os.path.join(root, old_rel), os.path.join(root, new_rel)
            if not os.path.exists(src) or os.path.exists(dst):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if old_rel.endswith(".md"):
                text = open(src, encoding="utf-8").read()
                rebased = rebase_text(text, old_rel, new_rel, resolve)
                if rebased != text:
                    open(src, "w", encoding="utf-8").write(rebased)
            os.replace(src, dst)
    return action


def plan_archive_indexes(root, apps_rel, per_year, moves, changes):
    """The index every directory in the layout is required to have.

    A year directory with no index is a folder of filenames: the archive is the part of
    a bundle a person comes back to months later, and the title of what was sent is the
    only thing that makes it findable.
    """
    for year in sorted(per_year):
        rel = f"{apps_rel}/{year}/index.md"
        if os.path.exists(os.path.join(root, rel)):
            continue

        def write(dest=os.path.join(root, rel), y=year, stems=tuple(sorted(per_year[year]))):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(year_index(root, apps_rel, y, stems))

        count = len(per_year[year])
        changes.append(Change(
            "create", rel,
            "%d application(s) with no recorded submission date" % count
            if year == UNDATED else "%d application(s) submitted in %s" % (count, year),
            write))

    rel = f"{apps_rel}/index.md"
    path = os.path.join(root, rel)
    existed = os.path.exists(path)
    body_now = ""
    if existed:
        parts = split_frontmatter(open(path, encoding="utf-8").read())
        body_now = parts[1] if parts else ""
    listed = {t.split("/")[0] for t in LINK_TARGET.findall(body_now)}
    missing = [y for y in sorted(per_year) if y not in listed]
    if existed and not missing:
        return

    def write_root(dest=path, years=tuple(missing), had=existed):
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if had:
            fm_lines, body = split_frontmatter(open(dest, encoding="utf-8").read())
        else:
            fm_lines, body = ["type: Index", 'title: "Applications"',
                              'description: "Submissions, evidence selected, and outcomes."',
                              f"timestamp: {ts}"], ""
        # Appended, never rewritten: whatever else is in this index is somebody's own
        # notes about their own applications.
        if "# Years" in body:
            body = body.rstrip("\n") + "\n\n"
        else:
            body = (body.rstrip("\n")
                    + "\n\n# Years\n\nOne directory per submission year.\n\n")
        body += "\n".join(f"- [{y}/]({y}/index.md)" for y in years) + "\n"
        open(dest, "w", encoding="utf-8").write(join_frontmatter(fm_lines, body))

    changes.append(Change("update" if existed else "create", rel,
                          "lists the year directories: %s" % ", ".join(missing),
                          write_root))


def plan_archive_relinks(root, moves, changes):
    """Every reference from outside the archive, moved with the file it names.

    r5 -> r6 deliberately left prose links alone, and was right to: the file they named
    was still there. Here it is not - the whole step is that these files move - so a
    link nobody rebases is a broken link, and validate_bundle.py is right to fail it.
    """
    if not moves:
        return
    resolve = archive_resolver(root, moves)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if rel in moves:
                continue
            text = open(path, encoding="utf-8").read()
            if rebase_text(text, rel, rel, resolve) == text:
                continue

            def write(p=path, r=rel):
                current = open(p, encoding="utf-8").read()
                open(p, "w", encoding="utf-8").write(
                    rebase_text(current, r, r, archive_resolver(root, moves)))

            changes.append(Change("update", rel,
                                  "links into the archive rebased on the year directories",
                                  write))


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

def pending_creations(changes):
    """Bundle-relative paths an earlier step will write during this same run.

    Each step plans against the filesystem, so a later step cannot see what an earlier
    one has not written yet - and a bundle at r1 crosses every revision in one command.
    """
    return {c.subject for c in changes if c.verb == "create"}


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
    today = datetime.date.today().isoformat()

    # Each step runs only when the bundle is below it AND the target reaches it. Guarding
    # on `revision < N` alone would run a step the target excludes and then stamp a lower
    # number over it - a bundle that lies about its own shape, which is worse than one
    # carrying no stamp at all.
    if revision < 2 <= CURRENT_REVISION:
        print(f"\nr1 -> r2  {REVISIONS[2]}")
        plan_r1_to_r2(root, today, changes, blocked)
    if revision < 3 <= CURRENT_REVISION:
        print(f"\nr2 -> r3  {REVISIONS[3]}")
        plan_r2_to_r3(root, changes, blocked)
    # r3 -> r4 turned every posting into JSON and r5 turns it back, so a bundle
    # below either one converts straight to Markdown. Running r4's step first would
    # write a document whose only reader was deleted with the format.
    if revision < 5 <= CURRENT_REVISION:
        print(f"\nr4 -> r5  {REVISIONS[5]}")
        plan_postings(root, changes, blocked)
        plan_r4_to_r5(root, changes, blocked)
    if revision < 6 <= CURRENT_REVISION:
        print(f"\nr5 -> r6  {REVISIONS[6]}")
        plan_r5_to_r6(root, changes, blocked, pending_creations(changes))
    if revision < 7 <= CURRENT_REVISION:
        print(f"\nr6 -> r7  {REVISIONS[7]}")
        plan_r6_to_r7(root, changes, blocked, pending_creations(changes))
    plan_stamp(root, CURRENT_REVISION, changes)

    done = {"create": "created", "update": "updated",
            "move": "moved", "stamp": "stamped"}
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
