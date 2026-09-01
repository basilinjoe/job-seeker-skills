"""One function per noun-verb: where user input meets the schema, the emitter and
the transaction.

This module assembles the others and decides nothing itself. Whether a value is
allowed is schema.py's question; how it is written is concept.py's and body.py's;
when a file lands is stage.py's; what every command needs before it can decide
anything is common.py's. If a validation rule appears here it belongs in
schema.py, and if a quoting decision appears here it belongs in concept.py.

**What is only in this layer is the class of rule that needs the bundle in hand.**
schema.py takes values and nothing else - no path, no filesystem - so a rule
about whether some other file exists or says something cannot live in it. Its
docstring names exactly three, and common.py is where they are enforced:

  - a `capabilities` value must appear in `framework/capability-vocabulary.md`, and
    only when that file lists any values at all;
  - a Project's `role` must name a concept in `roles/`;
  - a Role's `organisation` must name a concept in `organisations/`.

The referential pair is the expensive one to miss. `validate_bundle.py` checks
neither, so the first thing that notices is `okf_compile.load()` - which `okf score`
calls on the tailor-analyst's hot path. A dangling `role` written today surfaces as a
crash in the middle of a tailoring run, not as a red line at ship time.

Referential checks are local by construction: `--role X` is a stat on one file and
`--capability c` parses one vocabulary. Nothing here walks the tree except the two
verbs that must - `rm`, which has to know whether anything still points at what it
is about to delete, and `reindex`, whose whole subject is the tree. So an ordinary
write costs about the interpreter floor rather than the ~1,024 ms a full compile
costs, and a whole `okf validate` still runs once at the end of a mode as the mode
files already say.

## Where the verbs live

    career.py     project · role · org · education    add|set|retire|rm
                  including `set --section`, which restates one heading's prose
    claims.py     bullet · skill · credential         add|set|rm|mv
                  metric add|set
    upkeep.py     capability add · question add|resolve · log · reindex
    tailoring.py  posting add · posting requirement add · gaps write
                  view create|set|include
    archive.py    application file · application event

One module per tranche of the design rather than one per noun, because the verbs
inside a tranche share their machinery and the tranches share almost none.
"""

import argparse
import json
import sys

from . import (archive, career, claims, common, concept, stage, tailoring,
               upkeep)

# Kept as this module's own names because tests/test_authoring.py and the
# scripts' own history reach for them here. They are common.py's now: one
# definition, two spellings of the way in.
slug = common.slug
bundle_root = common.bundle_root
first_appearance = common.first_appearance
vocabulary_terms = common.vocabulary_terms
vocabulary_path = common.vocabulary_path
vocabulary_with = common.vocabulary_with
resolve_capabilities = common.resolve_capabilities
extension_keys = common.extension_keys
line_convention = common.line_convention
read_body = common.read_body
REQUIRED_DIRECTORIES = common.REQUIRED_DIRECTORIES
VOCABULARY_NAMES = common.VOCABULARY_NAMES
VOCABULARY_ITEM = common.VOCABULARY_ITEM
TERM = common.TERM
HEADING = common.HEADING

# `project add`'s own map of key to flag, kept here because tests name it and
# because career.py builds one per type from the same shape.
FLAG_FOR = career.FLAG_FOR["Project"]

# Every module that contributes verbs. Each exposes `register(subparsers)`, which
# adds its own nouns and sets `build=` on each verb - so adding a verb touches one
# module and this list stays as it is.
MODULES = (career, claims, upkeep, tailoring, archive)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="okf",
        description="Write to a career bundle. Every change is one of these verbs.")
    nouns = parser.add_subparsers(dest="noun", metavar="<noun>")
    for module in MODULES:
        module.register(nouns)
    return parser


def project_add(args):
    """Kept as a name this module exports, for callers and tests that have it."""
    return career.concept_add(args)


def main(argv):
    """Parse, build the changeset, commit it, and say what happened."""
    try:
        # A Windows console is cp1252, and everything this command prints can carry a
        # character it has no byte for: a title, a path under a non-ASCII user name, a
        # refusal quoting either. `okf project add --title "項目再構築"` raised a
        # UnicodeEncodeError from inside the `FAIL` print - so the one run that had a
        # refusal worth reading printed a traceback instead of it. `okf gates` carries
        # the same two lines for the same reason.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # pragma: no cover
        pass
    parser = build_parser()
    args = parser.parse_args(list(argv))
    if not getattr(args, "build", None):
        # A noun with no verb, or no noun at all. argparse prints the usage for
        # whichever level was reached, which is the level the caller got wrong.
        (getattr(args, "parser", None) or parser).print_help()
        return 2
    try:
        payload = stage.commit(args.build(args), dry_run=args.dry_run)
    except (stage.Refused, concept.Unsplicable) as exc:
        # Both carry their own `fix:` line, so the message is the whole of what a
        # person gets and nothing here paraphrases it.
        print(f"FAIL  {exc}")
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    verb = "would write" if payload["dry_run"] else "wrote"
    for path in payload["changed"]:
        print(f"{verb}  {path}")
    for path in payload.get("removed", ()):
        print(f"{'would remove' if payload['dry_run'] else 'removed'}  {path}")
    for name, value in sorted(payload["ids"].items()):
        print(f"{name}: {value}")
    if payload["dry_run"]:
        print("dry run - nothing was written")
    return 0
