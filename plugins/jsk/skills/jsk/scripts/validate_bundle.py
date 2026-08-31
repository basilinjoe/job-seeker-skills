#!/usr/bin/env python3
"""Validate an OKF career bundle.

Usage:
  python3 validate_bundle.py [bundle_root]
  python3 validate_bundle.py <bundle> --scope projects        only that subtree
  python3 validate_bundle.py <bundle> --exclude-archive       skip the frozen archive
  python3 validate_bundle.py <bundle> --max-findings 50       print at most N of each

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = valid. Exit 1 = errors. Exit 2 = called wrong.

Checks OKF v0.1 hard rules plus this bundle's own conventions.
Requires: pyyaml  (pip install pyyaml)
"""
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pipeline_model  # noqa: E402
from authoring import schema  # noqa: E402

try:
    import yaml
except ImportError:
    # A traceback here reads as a broken install rather than a missing package,
    # and this is often the first script anyone runs against their own bundle.
    print("validate_bundle.py needs pyyaml:  pip install pyyaml")
    sys.exit(2)

ARCHIVE = "tailoring/applications"

ap = argparse.ArgumentParser(add_help=True)
ap.add_argument("bundle", nargs="?", default=os.getcwd())
ap.add_argument("--scope", metavar="SUBDIR",
                help="validate only this subtree, bundle-relative (e.g. --scope projects)")
ap.add_argument("--exclude-archive", action="store_true",
                help=f"do not read {ARCHIVE}/")
ap.add_argument("--max-findings", type=int, default=25, metavar="N",
                help="print at most N errors and N warnings; 0 prints every one")
args = ap.parse_args()

ROOT = args.bundle
EXCLUDE_ARCHIVE = args.exclude_archive
MAX_FINDINGS = args.max_findings if args.max_findings > 0 else None

# A run that reads part of a bundle has to say which part, or a green result means
# nothing. Every check below that a narrowed run cannot cover in full adds a line here.
notes = []

SCOPE = None
if args.scope is not None:
    SCOPE = args.scope.replace("\\", "/").strip("/")
    if not SCOPE or SCOPE == "." or SCOPE.startswith("..") or os.path.isabs(args.scope):
        print(f"not a subdirectory of the bundle: {args.scope}")
        print("fix:  --scope projects   - a path inside the bundle, not an absolute one")
        sys.exit(2)
    if not os.path.isdir(os.path.join(ROOT, *SCOPE.split("/"))):
        print(f"no such directory in the bundle: {SCOPE}")
        print(f"fix:  --scope <a subdirectory of {ROOT}>")
        sys.exit(2)


def scoped(rel_dir):
    """Whether a bundle-relative directory is inside --scope, or holds it."""
    if not SCOPE:
        return True
    return (rel_dir == SCOPE or rel_dir.startswith(SCOPE + "/")
            or SCOPE.startswith(rel_dir + "/"))


# The vocabularies live in authoring/schema.py, which is the single machine-readable
# statement of the format. They used to be spelt out again here, so there were three
# copies - these, the schema's, and bundle-spec.md's prose - and a vocabulary that has
# drifted does not fail loudly: a synonym silently stops matching. Same objects, so a
# test can prove it. schema.py is standard-library only, so this adds nothing to what
# validate_bundle.py already needs.
STATUS = schema.STATUS_VALUES
SENIORITY = schema.SENIORITY_VALUES
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
LIST_ITEM = re.compile(r"^\s*[-*]\s+")

# The copies archived beside an application. bundle-spec.md is explicit that the files in
# tailoring/targets/ stay editable and "the copies beside the application are the archive
# and do not" - so an error inside one is a red nobody is permitted to clear, and a gate
# that cannot go green is a gate people stop running. Those findings warn instead. The
# application file itself still errors: its timeline is appended to for as long as the
# process is live, which makes anything wrong in it fixable.
FROZEN_COPY = (".posting.md", ".gaps.md", ".view.md", ".target.md")

errors, warnings = [], []
files, types, caps = [], {}, {}
metas = {}   # bundle-relative path (forward slashes) -> frontmatter, for the layout checks
missing_index = []


def frozen(rel):
    return rel.startswith(ARCHIVE + "/") and rel.endswith(FROZEN_COPY)


def problem(rel, msg):
    """Record a finding against a file, demoting it if that file may not be edited."""
    (warnings if frozen(rel) else errors).append(msg)


WALK_ROOT = os.path.join(ROOT, *SCOPE.split("/")) if SCOPE else ROOT

for dp, dns, fn in os.walk(WALK_ROOT):
    dns[:] = [d for d in dns if not d.startswith(".")]   # prune hidden dirs, not whole paths
    rel_dir = os.path.relpath(dp, ROOT).replace(os.sep, "/")
    rel_dir = "" if rel_dir == "." else rel_dir
    if EXCLUDE_ARCHIVE and (rel_dir == ARCHIVE or rel_dir.startswith(ARCHIVE + "/")):
        dns[:] = []
        continue
    # bundle-spec.md gives every directory an index.md and SKILL.md has every session read
    # it first to orient itself, but only init_bundle.py has ever written one. At 100
    # applications the archive index was a stub beside 400 files nobody had listed. A
    # warning, not an error: a stale index has never made a record wrong, and nothing in
    # the tree can regenerate it on the reader's behalf.
    if any(f.endswith(".md") for f in fn) and "index.md" not in fn:
        missing_index.append(f"{rel_dir}/index.md" if rel_dir else "index.md")
    for f in fn:
        if f.endswith(".md"):
            files.append(os.path.relpath(os.path.join(dp, f), ROOT))

if not files:
    errors.append(f"no markdown files found under {WALK_ROOT} - is this a bundle?")

# The layout revision, so an out-of-date bundle is told rather than silently misread.
# A WARNING and never an ERROR: failing a bundle built on an earlier revision would break
# every bundle already in existence, which the frozen surfaces rule out. Absent means r1,
# because every bundle predating the stamp has no way to say so.
CURRENT_BUNDLE_REVISION = 7

# r7 partitions the archive by submission year. An application file sitting directly in
# tailoring/applications/ is the r6 shape: correct there, and at r7 the sign that a
# migration was never run. An ERROR only at r7, for the same reason every other layout
# rule here is - a bundle built on an earlier revision must not start failing.
APPLICATION_YEAR_DIR = re.compile(r"^(?:\d{4}|undated)$")

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
    key = rel.replace(os.sep, "/")
    txt = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    if not txt.startswith("---\n"):
        problem(key, f"{rel}: no YAML frontmatter"); continue
    end = txt.find("\n---\n", 3)
    if end == -1:
        problem(key, f"{rel}: unterminated frontmatter"); continue
    try:
        meta = yaml.safe_load(txt[4:end])
    except Exception as e:
        problem(key, f"{rel}: YAML parse error - {e}"); continue
    if not isinstance(meta, dict):
        problem(key, f"{rel}: frontmatter is not a mapping"); continue
    metas[key] = meta

    if not meta.get("type"):
        problem(key, f"{rel}: MISSING REQUIRED KEY 'type'")
    else:
        types[meta["type"]] = types.get(meta["type"], 0) + 1
    for k in ("title", "description", "timestamp"):
        if k not in meta: warnings.append(f"{rel}: recommended key '{k}' absent")

    st = meta.get("status")
    if st and st not in STATUS:
        problem(key, f"{rel}: status '{st}' not in {sorted(STATUS)}")

    if meta.get("type") == "Project":
        for k in ("strength", "recency", "seniority", "capabilities", "domains"):
            if k not in meta: problem(key, f"{rel}: Project missing selection key '{k}'")
        s = meta.get("strength")
        if s is not None and (not isinstance(s, int) or not 1 <= s <= 5):
            problem(key, f"{rel}: strength must be int 1-5, got {s!r}")
        sn = meta.get("seniority")
        if sn and sn not in SENIORITY:
            problem(key, f"{rel}: seniority '{sn}' not in vocabulary")
        cv = meta.get("capabilities")
        if cv is not None and not isinstance(cv, list):
            problem(key, f"{rel}: 'capabilities' must be a list, got {type(cv).__name__}")
        else:
            for c in cv or []:
                caps[c] = caps.get(c, 0) + 1

    body = txt[end + 5:]

    # Timelines are checked at revision 3 and above only. An older bundle has no
    # timelines and must not start failing because the current shape gained them.
    if meta.get("type") == "Application" and isinstance(revision, int) and revision >= 3:
        rows = pipeline_model.parse_timeline(body)
        if not rows:
            problem(key, f"{rel}: Application has no '# Timeline' - "
                         "its stage and outcome cannot be derived")
        elif not any(r.event == "submitted" for r in rows):
            # Not every application was sent. One prepared, rendered and then held
            # back is a real application concept with a real timeline, and its
            # frontmatter already says so - so ask it rather than assuming. Writing
            # a `submitted` row to clear this error would trade an accurate red for
            # a false green, and the stage derived from it would be a lie.
            #
            # Only an explicit `submitted: false` exempts it. A file that never
            # says either way is the case this check was written for: a timeline
            # nobody finished, where the absence means nothing was recorded.
            if meta.get("submitted") is not False:
                problem(key, f"{rel}: timeline has no 'submitted' row and "
                             "frontmatter does not say `submitted: false` - "
                             "an application was either sent or explicitly held")
        seen_terminal = None
        previous = None
        for r in rows:
            if pipeline_vocab and r.event not in pipeline_vocab:
                problem(key, f"{rel}:{r.line}: event '{r.event}' is not in "
                             "framework/pipeline-vocabulary.md - a synonym stops counting")
            if r.date is None and r.raw_date.strip().lower() != "unknown":
                problem(key, f"{rel}:{r.line}: date '{r.raw_date}' is neither "
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
            problem(key, f"{rel}: BROKEN LINK -> {target}")

for path in missing_index:
    warnings.append(f"{path}: absent - bundle-spec.md gives every directory an index.md, "
                    "and it is the first thing a session reads to find its way around")

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
if os.path.isdir(targets_dir) and scoped("tailoring/targets"):
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
if os.path.isdir(apps_dir) and not EXCLUDE_ARCHIVE and scoped(ARCHIVE):
    # Recursive since r7, which moved every application into applications/<yyyy>/. A flat
    # listdir here saw an empty directory and reported nothing at all - the worst way for
    # a layout check to fail. The companion lookups stay directory-local, because a
    # companion is a file beside the application, not one anywhere in the archive.
    beside = {}
    for dp, dns, fn in os.walk(apps_dir):
        dns[:] = [d for d in dns if not d.startswith(".")]
        rel_dir = os.path.relpath(dp, ROOT).replace(os.sep, "/")
        beside[rel_dir] = set(fn)

    # The literal 7, not CURRENT_BUNDLE_REVISION: this pair of rules is about the
    # revision that introduced the year directories, and it must keep firing at r7
    # after the next revision moves the constant on.
    if isinstance(revision, int) and revision >= 7:
        for name in sorted(beside.get(ARCHIVE, ())):
            if name.endswith(".md") and name != "index.md":
                rel = f"{ARCHIVE}/{name}"
                errors.append(f"{rel}: sits directly in tailoring/applications/ - revision"
                              " 7 partitions the archive by year (run migrate_bundle.py)")
        for name in sorted(os.listdir(apps_dir)):
            if name.startswith(".") or not os.path.isdir(os.path.join(apps_dir, name)):
                continue
            if not APPLICATION_YEAR_DIR.match(name):
                rel = f"{ARCHIVE}/{name}"
                errors.append(f"{rel}: not a year directory - revision 7 partitions the "
                              "archive as applications/<yyyy>/")

    for rel_dir in sorted(beside):
        anames = beside[rel_dir]
        for name in sorted(anames):
            rel = f"{rel_dir}/{name}"
            meta = metas.get(rel)
            if not name.endswith(".md") or name == "index.md" or not meta:
                continue
            if meta.get("type") != "Application":
                continue
            stem = name[: -len(".md")]
            here = os.path.join(ROOT, *rel_dir.split("/"))

            if not APPLICATION_STEM.match(stem):
                warnings.append(f"{rel}: stem is not <yyyy-mm-dd>-<company>-<role> - the "
                                "date is what makes a second round at the same posting "
                                "addressable")

            # Declared and missing is the serious one: the application names the thing it
            # was answering and the thing is not there.
            for k, is_a in (("posting", "the posting it answered"),
                            ("assessment", "the assessment it answered"),
                            ("view_file", "the view it rendered from")):
                named = meta.get(k)
                if not named:
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(here, str(named)))):
                    errors.append(f"{rel}: {k}: {named} does not exist - {is_a} is "
                                  "named and not archived")

            # Undeclared is the quieter one, and a warning for the same reason the revision
            # check is: an application frozen before these keys existed is not broken, it is
            # just less answerable than one frozen today. A file sitting beside the
            # application counts even when frontmatter never names it, and `<stem>.target.md`
            # is the r2 spelling of the frozen posting.
            missing = []
            for k, suffixes in (("posting", (".posting.md", ".target.md")),
                                ("assessment", (".gaps.md",)),
                                ("view_file", (".view.md",))):
                if meta.get(k) or any(stem + s in anames for s in suffixes):
                    continue
                missing.append("%s: (%s%s)" % (k, stem, suffixes[0]))
            if missing:
                warnings.append(f"{rel}: no {', no '.join(missing)} - the archive cannot "
                                "say what this answered or what it rendered from")

            if stem + ".resume.json" in anames:
                warnings.append(f"{rel}: {stem}.resume.json sits beside it - the record is "
                                "not copied into an application (bundle-spec.md); it "
                                "compiles from concepts in git at the commit it was sent at")
elif EXCLUDE_ARCHIVE:
    notes.append(f"{ARCHIVE}/ not read (--exclude-archive) - nothing in it was checked")


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

if SCOPE:
    # Two checks read the whole bundle by nature. Say what a narrowed run did with them,
    # because a check that quietly did not run is worse than one that failed.
    notes.append(f"only {SCOPE}/ was read - nothing outside it was checked")
    notes.append(f"capability vocabulary cross-checked against {SCOPE}/ only - an "
                 "unlisted capability elsewhere in the bundle is not reported here")
    notes.append("bundle revision read from the bundle root as usual - still checked")


def show(items, mark):
    limit = MAX_FINDINGS or len(items)
    for item in items[:limit]:
        print(" ", mark, item)
    if len(items) > limit:
        print(f"  {mark} ... and {len(items) - limit} more")


print(f"files {len(files)} | concept types {len(types)} | capabilities {len(caps)}")
for note in notes:
    print(f"  scope: {note}")
print(f"ERRORS {len(errors)} | WARNINGS {len(warnings)}")
show(errors, "x")
show(warnings, "!")
strong = sorted(c for c, n in caps.items() if n >= 3)
if strong and not SCOPE:
    print(f"\n  through-lines (3+ projects, safe to claim in a summary): {', '.join(strong)}")
elif SCOPE:
    print("\n  through-line counts suppressed - they count projects across the whole bundle")
if isinstance(revision, int) and revision < CURRENT_BUNDLE_REVISION:
    print(f"\n  bundle revision {revision}, current is {CURRENT_BUNDLE_REVISION}"
          " - run migrate_bundle.py <bundle> to bring it up to date")

print("\nVALID" if not errors else "\nFAILED")
sys.exit(1 if errors else 0)
