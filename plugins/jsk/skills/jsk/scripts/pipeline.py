#!/usr/bin/env python3
"""What a job search needs from you this week.

Usage:
  python3 pipeline.py <bundle>                   what needs attention, most urgent first
  python3 pipeline.py <bundle> --all             the full board, closed applications included
  python3 pipeline.py <bundle> --company NAME    everything for one company
  python3 pipeline.py <bundle> --as-of DATE      compute against a date rather than today
  python3 pipeline.py <bundle> --markdown        emit as a table, to paste into a file

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
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pipeline_model as model  # noqa: E402

try:
    import yaml
except ImportError:
    print("pipeline.py needs pyyaml:  pip install pyyaml")
    sys.exit(2)


class Application:
    __slots__ = ("rel", "company", "role", "submitted", "state")

    def __init__(self, rel, meta, state):
        self.rel = rel
        self.company = meta.get("company") or meta.get("title") or rel
        self.role = meta.get("role") or ""
        self.submitted = str(meta.get("submitted") or "")
        self.state = state


def read_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 3)
    if end == -1:
        return None, text
    try:
        meta = yaml.safe_load(text[4:end])
    except Exception:
        return None, text[end + 5:]
    return (meta if isinstance(meta, dict) else None), text[end + 5:]


def collect(root, as_of, rules):
    """Every Application concept in the bundle, with its derived state."""
    apps_dir = os.path.join(root, "tailoring", "applications")
    if not os.path.isdir(apps_dir):
        return []
    out = []
    for name in sorted(os.listdir(apps_dir)):
        if not name.endswith(".md") or name == "index.md" or name.endswith(".target.md"):
            continue
        rel = f"tailoring/applications/{name}"
        meta, body = read_frontmatter(open(os.path.join(apps_dir, name), encoding="utf-8").read())
        if not meta or meta.get("type") != "Application":
            continue
        out.append(Application(rel, meta, model.derive(model.parse_timeline(body), as_of, rules)))
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


def line(app, width):
    s = app.state
    flag = ("  [" + "; ".join(s.flags) + "]") if s.flags else ""
    return (f"  {s.urgency:<13} {app.company[:width]:<{width}} "
            f"{app.role[:34]:<34} {s.stage or '-':<20} {s.action}{flag}")


def render(apps, args, as_of):
    needs = sorted([a for a in apps if a.state.needs_action and not a.state.terminal], key=sort_key)
    waiting = sorted([a for a in apps if not a.state.needs_action and not a.state.terminal],
                     key=sort_key)
    closed = [a for a in apps if a.state.terminal]
    width = min(28, max([len(a.company) for a in apps] + [7]))

    if args.markdown:
        print("| Urgency | Company | Role | Stage | Next |")
        print("|---|---|---|---|---|")
        for a in needs + (waiting if args.all else []):
            s = a.state
            print(f"| {s.urgency} | {a.company} | {a.role} | {s.stage or '-'} | {s.action} |")
    else:
        print(f"\nNEEDS YOU ({len(needs)})")
        for a in needs:
            print(line(a, width))
        if not needs:
            print("  nothing - every live application is inside its window")

        if args.all or waiting:
            print(f"\nWAITING ({len(waiting)})")
            for a in waiting:
                print(line(a, width))

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


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("bundle")
    ap.add_argument("--all", action="store_true", help="include waiting and closed applications")
    ap.add_argument("--company", help="everything for one company")
    ap.add_argument("--as-of", dest="as_of", help="compute against this date (YYYY-MM-DD)")
    ap.add_argument("--markdown", action="store_true", help="emit a table to paste into a file")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

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

    print(f"pipeline.py   bundle: {args.bundle}   as of {as_of.isoformat()}")
    if not apps:
        print("\nno applications yet - tailor mode creates the first one")
        return 0

    if args.company:
        return render_company(apps, args.company)
    return render(apps, args, as_of)


if __name__ == "__main__":
    sys.exit(main())
