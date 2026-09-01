#!/usr/bin/env python3
"""What a job search needs from you this week.

Usage:
  python3 pipeline.py <bundle>                   what needs attention, most urgent first
  python3 pipeline.py <bundle> --top 30          how many rows per block (default 15)
  python3 pipeline.py <bundle> --all             the full board, closed applications included
  python3 pipeline.py <bundle> --company NAME    everything for one company
  python3 pipeline.py <bundle> --as-of DATE      compute against a date rather than today
  python3 pipeline.py <bundle> --markdown        emit as a table, to paste into a file
  python3 pipeline.py <bundle> --json            emit the whole board as JSON

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = nothing needs attention. Exit 1 = something does. Exit 2 = called wrong.

The 1 is deliberate and matches migrate_bundle.py's dry run: it makes this usable as
a scheduled check without writing anything.

This script decides nothing. Stage, staleness and next action all come from
pipeline_model.py, so the board and the application files cannot disagree - the board
did not choose what they say.

Requires: pyyaml  (pip install pyyaml)
"""
import argparse
import datetime
import json
import os
import sys


from . import markup
from . import pipeline_model as model

try:
    import yaml
except ImportError:
    print("pipeline.py needs pyyaml:  pip install pyyaml")
    sys.exit(2)

# The frozen copies archived beside an application. They carry a `type` of their own, so
# reading them and discarding them on the type check was correct - and at 100 applications
# it was 300 needless YAML parses a run, most of them over a verbatim advertisement body.
COMPANIONS = (".posting.md", ".gaps.md", ".view.md", ".target.md")

DEFAULT_TOP = 15


class Application:
    __slots__ = ("rel", "company", "role", "submitted", "state")

    def __init__(self, rel, meta, state):
        self.rel = rel
        self.company = meta.get("company") or meta.get("title") or rel
        self.role = meta.get("role") or ""
        self.submitted = str(meta.get("submitted") or "")
        self.state = state


def read_frontmatter(text):
    """okf_compile's parser, so a concept reads the same way in the board and the record.

    This was a second copy, and a weaker one - it had no CRLF arm - sitting under a
    docstring in okf_compile.py that claimed this module used *that* one. It does now.
    """
    return markup.read_frontmatter(text, yaml)


def collect(root, as_of, rules):
    """Every Application concept in the bundle, with its derived state.

    Walks rather than lists: revision 7 partitions the archive into applications/<yyyy>/,
    and both shapes have to keep working - a bundle is never obliged to migrate, and a
    board that silently went empty after a layout change would be worse than one that
    was slow.
    """
    apps_dir = os.path.join(root, "tailoring", "applications")
    if not os.path.isdir(apps_dir):
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(apps_dir):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".md") or name == "index.md" or name.endswith(COMPANIONS):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            meta, body = read_frontmatter(open(path, encoding="utf-8").read())
            if not meta or meta.get("type") != "Application":
                continue
            out.append(Application(rel, meta,
                                   model.derive(model.parse_timeline(body), as_of, rules)))
    return out


def sort_key(app):
    """Most urgent first. Overdue by the most days leads; a stale-but-not-overdue
    item sorts on how long it has been quiet."""
    u = app.state.urgency
    if u.startswith("overdue"):
        return (0, -int(u.split()[1].rstrip("d")))
    if u == "due today":
        return (1, 0)
    return (2, -(app.state.days_quiet or 0))


def groups(apps):
    """needs / waiting / closed, each in the order they should be read."""
    needs = sorted([a for a in apps if a.state.needs_action and not a.state.terminal],
                   key=sort_key)
    waiting = sorted([a for a in apps if not a.state.needs_action and not a.state.terminal],
                     key=sort_key)
    closed = [a for a in apps if a.state.terminal]
    return needs, waiting, closed


def line(app, width):
    s = app.state
    flag = ("  [" + "; ".join(s.flags) + "]") if s.flags else ""
    return (f"  {s.urgency:<13} {app.company[:width]:<{width}} "
            f"{app.role[:34]:<34} {s.stage or '-':<20} {s.action}{flag}")


def render(apps, args, as_of):
    needs, waiting, closed = groups(apps)
    width = min(28, max([len(a.company) for a in apps] + [7]))
    # A hundred live applications is a real search and an unreadable board. Bounded, with
    # the count and the remainder both printed, so the cut is visible rather than silent.
    top = None if args.all or args.top <= 0 else args.top

    def bounded(rows):
        return rows[:top] if top else rows

    def remainder(rows):
        return len(rows) - top if top and len(rows) > top else 0

    if args.markdown:
        rows = needs + (waiting if args.all else [])
        print("| Urgency | Company | Role | Stage | Next |")
        print("|---|---|---|---|---|")
        for a in bounded(rows):
            s = a.state
            print(f"| {s.urgency} | {a.company} | {a.role} | {s.stage or '-'} | {s.action} |")
        if remainder(rows):
            print(f"\n... and {remainder(rows)} more - --all for the whole board")
    else:
        print(f"\nNEEDS YOU ({len(needs)})")
        for a in bounded(needs):
            print(line(a, width))
        if remainder(needs):
            print(f"  ... and {remainder(needs)} more - --top {len(needs)} or --all "
                  "for the rest")
        if not needs:
            print("  nothing - every live application is inside its window")

        if args.all or waiting:
            print(f"\nWAITING ({len(waiting)})")
            for a in bounded(waiting):
                print(line(a, width))
            if remainder(waiting):
                print(f"  ... and {remainder(waiting)} more - --top {len(waiting)} or "
                      "--all for the rest")

        if closed:
            counts = {}
            for a in closed:
                counts[a.state.terminal] = counts.get(a.state.terminal, 0) + 1
            summary = " | ".join(f"{k} {v}" for k, v in sorted(counts.items()))
            print(f"\nCLOSED ({len(closed)})   {summary}")
            if args.all:
                for a in closed:
                    print(f"  {a.state.terminal:<13} {a.company[:width]:<{width}} {a.role[:34]}")

    print(f"\nACTION {len(needs)} | LIVE {len(needs) + len(waiting)} | CLOSED {len(closed)}")
    return 1 if needs else 0


def render_company(apps, name):
    """Every application to one company - the 'have I burned this one already' query."""
    needle = name.lower()
    hits = [a for a in apps if needle in a.company.lower()]
    if not hits:
        print(f"\nno applications to a company matching {name!r}")
        return 0
    print(f"\n{len(hits)} application(s) matching {name!r}\n")
    for a in sorted(hits, key=lambda x: x.submitted):
        s = a.state
        verdict = s.terminal or (s.stage or "-")
        print(f"  {a.submitted:<12} {a.role[:38]:<38} {verdict:<18} {s.urgency}")
        print(f"  {'':<12} {a.rel}")
    live = [a for a in hits if not a.state.terminal]
    print(f"\nMATCHED {len(hits)} | LIVE {len(live)}")
    return 1 if any(a.state.needs_action for a in live) else 0


def as_dict(app, group):
    s = app.state
    return {
        "file": app.rel,
        "company": app.company,
        "role": app.role,
        "submitted": app.submitted or None,
        "group": group,
        "stage": s.stage,
        "terminal": s.terminal,
        "last_event": s.last_event,
        "days_quiet": s.days_quiet,
        "due": s.due.isoformat() if s.due else None,
        "needs_action": s.needs_action,
        "action": s.action,
        "urgency": s.urgency,
        "flags": list(s.flags),
    }


def render_json(apps, bundle, as_of):
    """The whole board, unbounded - --top is a reading aid and a parser does not read."""
    needs, waiting, closed = groups(apps)
    doc = {
        "bundle": bundle,
        "as_of": as_of.isoformat(),
        "counts": {"action": len(needs),
                   "live": len(needs) + len(waiting),
                   "closed": len(closed)},
        "applications": ([as_dict(a, "needs") for a in needs]
                         + [as_dict(a, "waiting") for a in waiting]
                         + [as_dict(a, "closed") for a in closed]),
    }
    # default=str so a stray date from a bundle's own frontmatter prints rather than
    # ending the run in a TypeError the caller cannot act on.
    print(json.dumps(doc, indent=2, default=str))
    return 1 if needs else 0


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("bundle")
    ap.add_argument("--all", action="store_true", help="include waiting and closed applications")
    ap.add_argument("--top", type=int, default=DEFAULT_TOP, metavar="N",
                    help=f"rows per block before the remainder is summarised "
                         f"(default {DEFAULT_TOP}; 0 for every row)")
    ap.add_argument("--company", help="everything for one company")
    ap.add_argument("--as-of", dest="as_of", help="compute against this date (YYYY-MM-DD)")
    ap.add_argument("--markdown", action="store_true", help="emit a table to paste into a file")
    ap.add_argument("--json", action="store_true", help="emit the whole board as JSON")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        # argparse raises SystemExit(0) for --help and (2) for a usage error.
        # Collapsing both to 2 reported "called wrong" for asking a question.
        return exc.code if isinstance(exc.code, int) else 2

    if not os.path.isdir(args.bundle):
        print(f"not a directory: {args.bundle}")
        print("fix:  pass the bundle root - the folder holding index.md and projects/")
        return 2

    as_of = datetime.date.today()
    if args.as_of:
        as_of = model.parse_date(args.as_of)
        if as_of is None:
            print(f"not an ISO date: {args.as_of}")
            print("fix:  --as-of YYYY-MM-DD")
            return 2

    rules = model.load_rules(args.bundle)
    apps = collect(args.bundle, as_of, rules)

    if args.json:
        if args.company:
            needle = args.company.lower()
            apps = [a for a in apps if needle in a.company.lower()]
        return render_json(apps, args.bundle, as_of)

    print(f"pipeline.py   bundle: {args.bundle}   as of {as_of.isoformat()}")
    if not apps:
        print("\nno applications yet - tailor mode creates the first one")
        return 0

    if args.company:
        return render_company(apps, args.company)
    return render(apps, args, as_of)


if __name__ == "__main__":
    sys.exit(main())
