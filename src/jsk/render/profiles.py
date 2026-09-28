"""Region profiles: a market's conventions as data.

A profile says what jsk.resume.build needs to know about a market and nothing else: its
paper size (`region`), the default page budget, which sections render in what order,
whether the Indian declaration closes the page, and whether the right to work goes on
the header line. The forbidden/expected/private-field gate that sat here went with the
URS record (2026-09-25): every field it governed - a photo, a date of birth, referees,
compensation - is one kb.ttl has no home for, so the gate had nothing left to refuse.
"""
import json
import os


def schema_dir(start=None):
    """The packaged schema/ directory. `start` overrides it, for a caller with its own.

    The `..` arithmetic this did against `__file__` is now one constant in paths.py -
    three modules were computing the same directory from three different depths.
    """
    if start is not None:
        here = os.path.dirname(os.path.abspath(start))
        return os.path.normpath(os.path.join(here, "..", "..", "data", "schema"))
    from ..paths import SCHEMA_DIR      # noqa: PLC0415 - avoids a package-level cycle
    return SCHEMA_DIR


def load(ref, base=None):
    """Load a profile by id (`urs:profile:au/1`), region code (`AU`) or path; the
    default profile for anything that names none that ships."""
    base = base or schema_dir()
    if ref is None:
        ref = "default"
    if os.path.exists(ref):
        path = ref
    else:
        token = ref
        if token.startswith("urs:profile:"):
            token = token[len("urs:profile:"):].split("/")[0]
        token = token.lower()
        if token in ("xx", "", "none"):
            token = "default"
        path = os.path.join(base, "profiles", f"{token}.json")
        if not os.path.exists(path):
            path = os.path.join(base, "profiles", "default.json")
    with open(path, encoding="utf8") as fh:
        return json.load(fh)
