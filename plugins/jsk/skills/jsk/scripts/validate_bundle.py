#!/usr/bin/env python3
"""Validate an OKF career bundle.

Usage: python3 validate_bundle.py [bundle_root]

On Windows use `python` or `py -3` in place of `python3`.

Checks OKF v0.1 hard rules plus this bundle's own conventions.
Requires: pyyaml  (pip install pyyaml)
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pipeline_model  # noqa: E402

try:
    import yaml
except ImportError:
    # A traceback here reads as a broken install rather than a missing package,
    # and this is often the first script anyone runs against their own bundle.
    print("validate_bundle.py needs pyyaml:  pip install pyyaml")
    sys.exit(2)

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
STATUS = {"confirmed", "inferred", "needs-verification"}
SENIORITY = {"architecture-ownership","product-ownership","platform-design","team-leadership",
             "technical-ownership","hands-on-senior","hands-on","junior"}
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
LIST_ITEM = re.compile(r"^\s*[-*]\s+")

errors, warnings = [], []
files, types, caps = [], {}, {}
metas = {}   # bundle-relative path (forward slashes) -> frontmatter, for the layout checks

for dp, dns, fn in os.walk(ROOT):
    dns[:] = [d for d in dns if not d.startswith(".")]   # prune hidden dirs, not whole paths
    for f in fn:
        if f.endswith(".md"):
            files.append(os.path.relpath(os.path.join(dp, f), ROOT))

if not files:
    errors.append(f"no markdown files found under {ROOT} - is this a bundle?")

# The layout revision, so an out-of-date bundle is told rather than silently misread.
# A WARNING and never an ERROR: failing a bundle built on an earlier revision would break
# every bundle already in existence, which the frozen surfaces rule out. Absent means r1,
# because every bundle predating the stamp has no way to say so.
CURRENT_BUNDLE_REVISION = 6
revision = None
index_path = os.path.join(ROOT, "index.md")
if os.path.exists(index_path):
    itxt = open(index_path, encoding="utf-8").read()
    iend = itxt.find("\n---\n", 3) if itxt.startswith("---\n") else -1
    if iend != -1:
        try:
            imeta = yaml.safe_load(itxt[4:iend])
            if isinstance(imeta, dict):
                revision = imeta.get("okf_bundle", 1)
        except Exception:
            revision = None

# The timeline vocabulary. Absent, events go unchecked rather than all being rejected -
# the same fallback capabilities use, and the same reason: a bundle that predates the file
# is not a broken bundle.
pipeline_vocab = set()
pv_path = os.path.join(ROOT, "framework", "pipeline-vocabulary.md")
if os.path.exists(pv_path):
    fenced = False
    with open(pv_path, encoding="utf-8") as f:
        for line in f:
            if line.lstrip().startswith("```"):
                fenced = not fenced; continue
            if not fenced and LIST_ITEM.match(line):
                pipeline_vocab.update(re.findall(r"`([a-z0-9-]+)`", line))

for rel in sorted(files):
    txt = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    if not txt.startswith("---\n"):
        errors.append(f"{rel}: no YAML frontmatter"); continue
    end = txt.find("\n---\n", 3)
    if end == -1:
        errors.append(f"{rel}: unterminated frontmatter"); continue
    try:
        meta = yaml.safe_load(txt[4:end])
    except Exception as e:
        errors.append(f"{rel}: YAML parse error - {e}"); continue
    if not isinstance(meta, dict):
        errors.append(f"{rel}: frontmatter is not a mapping"); continue
    metas[rel.replace(os.sep, "/")] = meta

    if not meta.get("type"):
        errors.append(f"{rel}: MISSING REQUIRED KEY 'type'")
    else:
        types[meta["type"]] = types.get(meta["type"], 0) + 1
    for k in ("title", "description", "timestamp"):
        if k not in meta: warnings.append(f"{rel}: recommended key '{k}' absent")

    st = meta.get("status")
    if st and st not in STATUS:
        errors.append(f"{rel}: status '{st}' not in {sorted(STATUS)}")

    if meta.get("type") == "Project":
        for k in ("strength", "recency", "seniority", "capabilities", "domains"):
            if k not in meta: errors.append(f"{rel}: Project missing selection key '{k}'")
        s = meta.get("strength")
        if s is not None and (not isinstance(s, int) or not 1 <= s <= 5):
            errors.append(f"{rel}: strength must be int 1-5, got {s!r}")
        sn = meta.get("seniority")
        if sn and sn not in SENIORITY:
            errors.append(f"{rel}: seniority '{sn}' not in vocabulary")
        cv = meta.get("capabilities")
        if cv is not None and not isinstance(cv, list):
            errors.append(f"{rel}: 'capabilities' must be a list, got {type(cv).__name__}")
        else:
            for c in cv or []:
                caps[c] = caps.get(c, 0) + 1

    body = txt[end + 5:]

    # Timelines are checked at revision 3 and above only. An older bundle has no
    # timelines and must not start failing because the current shape gained them.
    if meta.get("type") == "Application" and isinstance(revision, int) and revision >= 3:
        rows = pipeline_model.parse_timeline(body)
        if not rows:
            errors.append(f"{rel}: Application has no '# Timeline' - "
                          "its stage and outcome cannot be derived")
        elif not any(r.event == "submitted" for r in rows):
            errors.append(f"{rel}: timeline has no 'submitted' row - "
                          "every application starts by being sent")
        seen_terminal = None
        previous = None
        for r in rows:
            if pipeline_vocab and r.event not in pipeline_vocab:
                errors.append(f"{rel}:{r.line}: event '{r.event}' is not in "
                              "framework/pipeline-vocabulary.md - a synonym stops counting")
            if r.date is None and r.raw_date.strip().lower() != "unknown":
                errors.append(f"{rel}:{r.line}: date '{r.raw_date}' is neither "
                              "YYYY-MM-DD nor 'unknown'")
            if r.date and previous and r.date < previous:
                warnings.append(f"{rel}:{r.line}: dated before the row above it - "
                                "expected when backfilling, worth a look otherwise")
            if seen_terminal and r.event in pipeline_model.ADVANCING:
                warnings.append(f"{rel}:{r.line}: '{r.event}' follows "
                                f"'{seen_terminal}' - a reopened process, or a mistake")
            if r.event in pipeline_model.TERMINAL:
                seen_terminal = r.event
            elif r.event in pipeline_model.ADVANCING:
                seen_terminal = None
            previous = r.date or previous

    # strip fenced blocks and inline code - example links in templates are not real links
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    body = re.sub(r"`[^`\n]*`", "", body)
    for _, target in LINK.findall(body):
        if target.startswith(("http://", "https://", "mailto:", "#")) or "://" in target: continue
        t = target.split("#")[0]
        if not t: continue
        p = os.path.normpath(os.path.join(os.path.dirname(rel), t))
        if not os.path.exists(os.path.join(ROOT, p)):
            errors.append(f"{rel}: BROKEN LINK -> {target}")

# ------------------------------------------------------------- tailoring layout
#
# The link checker above catches a reference to a file that is not there. It cannot
# catch the opposite - a file that is there and should not be, or a companion the
# layout requires and nobody wrote. Those are what make a tailoring folder unreadable,
# and neither shows up as a broken link.

APPLICATION_STEM = re.compile(r"^\d{4}-\d{2}-\d{2}-.+$")
TARGET_COMPANIONS = (".posting.md", ".gaps.md", ".view.md")


def target_stem(name):
    for suffix in TARGET_COMPANIONS:
        if name.endswith(suffix):
            return name[: -len(suffix)], suffix
    return name[:-3] if name.endswith(".md") else None, ".md"


targets_dir = os.path.join(ROOT, "tailoring", "targets")
if os.path.isdir(targets_dir):
    tnames = set(os.listdir(targets_dir))
    for name in sorted(n for n in tnames if n.endswith(".md") and n != "index.md"):
        stem, suffix = target_stem(name)
        rel = f"tailoring/targets/{name}"
        if suffix == ".md":
            # A working posting r5 replaced. Marked, it is a retired copy somebody kept
            # on purpose; unmarked, it is a second document for the same job with
            # nothing to say which one the scorer should have read.
            if stem + ".posting.md" not in tnames:
                continue
            if (metas.get(rel) or {}).get("superseded_by"):
                continue
            msg = (f"{rel}: superseded by {stem}.posting.md and not marked - two "
                   "documents describe one job and neither says which is live")
            if isinstance(revision, int) and revision >= 6:
                errors.append(msg)
            else:
                warnings.append(msg)
        elif suffix in (".gaps.md", ".view.md") and stem + ".posting.md" not in tnames:
            errors.append(f"{rel}: no {stem}.posting.md beside it - an assessment or a "
                          "view with no posting cannot say what it was answering")

apps_dir = os.path.join(ROOT, "tailoring", "applications")
if os.path.isdir(apps_dir):
    anames = set(os.listdir(apps_dir))
    for name in sorted(anames):
        rel = f"tailoring/applications/{name}"
        meta = metas.get(rel)
        if not name.endswith(".md") or name == "index.md" or not meta:
            continue
        if meta.get("type") != "Application":
            continue
        stem = name[: -len(".md")]

        if not APPLICATION_STEM.match(stem):
            warnings.append(f"{rel}: stem is not <yyyy-mm-dd>-<company>-<role> - the "
                            "date is what makes a second round at the same posting "
                            "addressable")

        # Declared and missing is the serious one: the application names the thing it
        # was answering and the thing is not there.
        for key, is_a in (("posting", "the posting it answered"),
                          ("assessment", "the assessment it answered"),
                          ("view_file", "the view it rendered from")):
            named = meta.get(key)
            if not named:
                continue
            if not os.path.exists(os.path.normpath(os.path.join(apps_dir, str(named)))):
                errors.append(f"{rel}: {key}: {named} does not exist - {is_a} is "
                              "named and not archived")

        # Undeclared is the quieter one, and a warning for the same reason the revision
        # check is: an application frozen before these keys existed is not broken, it is
        # just less answerable than one frozen today. A file sitting beside the
        # application counts even when frontmatter never names it, and `<stem>.target.md`
        # is the r2 spelling of the frozen posting.
        missing = []
        for key, suffixes in (("posting", (".posting.md", ".target.md")),
                              ("assessment", (".gaps.md",)),
                              ("view_file", (".view.md",))):
            if meta.get(key) or any(stem + s in anames for s in suffixes):
                continue
            missing.append("%s: (%s%s)" % (key, stem, suffixes[0]))
        if missing:
            warnings.append(f"{rel}: no {', no '.join(missing)} - the archive cannot say "
                            "what this answered or what it rendered from")

        if stem + ".resume.json" in anames:
            warnings.append(f"{rel}: {stem}.resume.json sits beside it - the record is "
                            "not copied into an application (bundle-spec.md); it "
                            "compiles from concepts in git at the commit it was sent at")


# capabilities must exist in the canonical vocabulary.
# Only real list items count: the file's own prose and its fenced format example are
# not vocabulary, and treating them as such would reject every genuine value.
vocab_path = os.path.join(ROOT, "framework", "capability-vocabulary.md")
if not os.path.exists(vocab_path):
    vocab_path = os.path.join(ROOT, "framework", "capability_vocabulary.md")
vocab = set()
if os.path.exists(vocab_path):
    fenced = False
    with open(vocab_path, encoding="utf-8") as f:
        for line in f:
            if line.lstrip().startswith("```"):
                fenced = not fenced; continue
            if not fenced and LIST_ITEM.match(line):
                vocab.update(re.findall(r"`([a-z0-9-]+)`", line))
unknown = sorted(c for c in caps if vocab and c not in vocab)
for c in unknown:
    errors.append(f"capability '{c}' is not in framework/capability-vocabulary.md - add it there or reuse an existing value")

print(f"files {len(files)} | concept types {len(types)} | capabilities {len(caps)}")
print(f"ERRORS {len(errors)} | WARNINGS {len(warnings)}")
for e in errors: print("  x", e)
for w in warnings[:15]: print("  !", w)
if len(warnings) > 15: print(f"  ! ... and {len(warnings) - 15} more")
strong = sorted(c for c, n in caps.items() if n >= 3)
if strong:
    print(f"\n  through-lines (3+ projects, safe to claim in a summary): {', '.join(strong)}")
if isinstance(revision, int) and revision < CURRENT_BUNDLE_REVISION:
    print(f"\n  bundle revision {revision}, current is {CURRENT_BUNDLE_REVISION}"
          " - run migrate_bundle.py <bundle> to bring it up to date")

print("\nVALID" if not errors else "\nFAILED")
sys.exit(1 if errors else 0)
