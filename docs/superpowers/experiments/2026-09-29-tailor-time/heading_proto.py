"""Prototype: tailor-cost Rulings 1-2 (bare headings, section paragraphs) plus a new
Ruling: under a section heading, every line is its own item (no joining of unindented
lines). Compares section counts: today / old-plan prototype / this prototype.

Usage: python heading_proto.py <workspace> [<application-name-part>...]
  prints one row per applications/*/posting.md; each name part also lists that advert's lines."""
import glob, os, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from jsk.graph import rules as R
from jsk.graph.rules import (LIST_ITEM, BOLD_LINE, HEADING_ASKS, HEADING_NOT, HEADING_DOES,
                             HEADING_OFFERS, HEADING_OPTIONAL, squash)

TERMINAL = re.compile(r"[.!;,]\Z")
OFFERS_MORE = re.compile(r"(?i)what'?s in it for|\brewards?\b|why join|\bour (values|culture)\b|\babout us\b|\bperks\b")


def bare_heading(text):
    words = re.findall(r"[A-Za-z][\w'/-]*", text)
    if not words or len(words) > 6 or TERMINAL.search(text):
        return False
    letters = re.sub(r"[^A-Za-z]", "", text)
    if len(words) >= 2 and len(letters) >= 3 and letters.isupper():
        return True
    return bool(HEADING_ASKS.search(text) or HEADING_DOES.search(text)
                or HEADING_OFFERS.search(text) or HEADING_NOT.search(text) or OFFERS_MORE.search(text)
                or re.match(r"(?i)about\b", text)
                or re.fullmatch(r"(?i)(job description|(role |job )?overview|the role)\s*:?", text))


def heading(line, text, item):
    return not item and (text.startswith("#") or BOLD_LINE.fullmatch(text)
                         or (text.endswith(":") and len(text.split()) <= 8)
                         or bare_heading(text))


def lines(advert, per_line):
    advert = re.sub(r"\A---\n.*?\n---\n", "", advert, flags=re.S)
    found = []
    section, opt_heading, wrapping, prose = "other", False, None, False
    for line in advert.split("\n"):
        text = line.strip()
        item = LIST_ITEM.fullmatch(line) if not BOLD_LINE.fullmatch(text) else None
        if wrapping and text and not item and line[:1].isspace() and not (
                section != "qualification" and heading(line, text, item)):
            if wrapping == "join":
                found[-1][1] = f"{found[-1][1]} {squash(text)}"
            continue
        wrapping = None
        if not text:
            prose = False
        elif heading(line, text, item):
            words = squash(text)
            prose = False
            if HEADING_ASKS.search(words) and not HEADING_NOT.search(words):
                section, opt_heading = "qualification", bool(HEADING_OPTIONAL.search(words))
            elif HEADING_DOES.search(words):
                section, opt_heading = "responsibility", False
            elif HEADING_OFFERS.search(words) or HEADING_NOT.search(words) or OFFERS_MORE.search(words):
                section, opt_heading = "offered", False
            else:
                section, opt_heading = "other", False
        elif item:
            prose, wrapping = False, "skip"
            if section != "offered":
                found.append([section, squash(item.group(1)), opt_heading])
                wrapping = "join"
        elif not found and not prose and re.match(r"https?://\S+\Z", text):
            continue
        elif section == "offered":
            continue
        elif prose and not (per_line and section in ("qualification", "responsibility")):
            found[-1][1] = f"{found[-1][1]} {squash(text)}"
        elif section in ("qualification", "responsibility"):
            found.append([section, squash(text), opt_heading])
            prose = True
        else:
            found.append(["other", squash(text), False])
            prose = True
    return found


def today(advert):
    return [[x.section, x.text] for x in R.advert_lines(advert)]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    paths = sorted(glob.glob(os.path.join(sys.argv[1], "applications", "*", "posting.md")))
    verbose = set(sys.argv[2:])
    for p in paths:
        a = open(p, encoding="utf-8").read()
        t = Counter(s for s, *_ in today(a))
        o = Counter(s for s, *_ in lines(a, False))
        n = Counter(s for s, *_ in lines(a, True))
        name = Path(p).parent.name[:50]
        f = lambda c: f"q{c['qualification']:>2} r{c['responsibility']:>2} o{c['other']:>2}"
        print(f"{name:<50} today {f(t)} | old {f(o)} | new {f(n)}")
        if any(v in name for v in verbose):
            for s, txt, *_ in lines(a, True):
                print(f"   {s[:4]} {txt[:100]}")
