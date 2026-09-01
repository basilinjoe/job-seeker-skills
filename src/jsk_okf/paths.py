"""Where the packaged data lives - stated once.

`preflight.py`, `validate_urs.py` and `urs/profiles.py` each computed this with their
own `..` arithmetic against `__file__`, from three different depths in the tree. So
the schema directory's location was asserted in three places and correct in whichever
of them had last been updated - and moving the directory needed all three found.

Plain path arithmetic rather than `importlib.resources`. The callers read these files
with `open()` and test for them with `os.path.exists`, neither of which works out of a
zipimport anyway, so a Traversable would buy zip-safety this package does not have and
cannot use. What it would cost is real: every one of those call sites would have to
change shape to consume it.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# profile.schema.json, example.resume.json, and profiles/<region>.json.
SCHEMA_DIR = os.path.join(HERE, "data", "schema")

PROFILES_DIR = os.path.join(SCHEMA_DIR, "profiles")
EXAMPLE_RECORD = os.path.join(SCHEMA_DIR, "example.resume.json")
