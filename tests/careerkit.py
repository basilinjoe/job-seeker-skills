"""A workspace to test against: tests/claims_fixtures, copied, edited, with a short
resume.json in its application.

The record went from a 41KB copy of the career to a short file naming what was chosen,
so a test builds a career the way a person has one - kb.ttl - and says what it picks,
rather than hand-writing the copy the renderer used to read.
"""
import json
import shutil
from pathlib import Path

from jsk.graph import store as S

FIXTURES = Path(__file__).parent / "claims_fixtures"
APP = Path("applications") / "contoso-platform"

# ach_events_terraform, retired - an edit for workspace(edits=[RETIRE]).
RETIRE = ('    j:text "Wrote the platform\'s Terraform." ;\n    j:shows c:terraform ;\n',
          '    j:text "Wrote the platform\'s Terraform." ;\n    j:shows c:terraform ;\n'
          '    j:retired "2026-09-01"^^xsd:date ; j:reason "not true any more" ;\n')


def workspace(root, edits=(), short=None):
    """(root, short_path): the fixture copied to `root`, each (old, new) replaced once in
    career/kb.ttl, and `short` (a dict) written as the application's resume.json - the
    legacy record that was there is removed either way."""
    root = Path(root)
    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
    kb = root / "career" / "kb.ttl"
    text = kb.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    kb.write_text(text, encoding="utf-8", newline="\n")
    path = root / APP / "resume.json"
    path.unlink(missing_ok=True)
    if short is not None:
        path.write_text(json.dumps(short, indent=2) + "\n", encoding="utf-8", newline="\n")
    return str(root), str(path)


def store(root):
    return S.load(root)
