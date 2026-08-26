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
import os
import sys

CURRENT_REVISION = 2

REVISIONS = {
    1: "applications point at a mutable target file (`target:`) and carry `outcome:`",
    2: "the posting is frozen beside each application as `<stem>.target.md`",
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
        plan_application(root, f"tailoring/applications/{name}", today, changes, blocked)


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
    today = datetime.date.today().isoformat()

    if revision < 2:
        print(f"\nr1 -> r2  {REVISIONS[2]}")
        plan_r1_to_r2(root, today, changes, blocked)
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
