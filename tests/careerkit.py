"""A workspace to test against: tests/claims_fixtures, copied, edited, with a general
resume's selection in its store.

The record went from a 41KB copy of the career to a short file naming what was chosen,
so a test builds a career the way a person has one - Turtle a test can read, put in
career/store/ - and says what it picks, rather than hand-writing the copy the renderer
used to read.
"""
import shutil
from pathlib import Path

import fixtures  # noqa: F401 - puts this checkout's src/ first on sys.path
from jsk.adapters.compose import record

FIXTURES = Path(__file__).parent / "claims_fixtures"
APP = Path("applications") / "contoso-platform"

# The fixture's Meridian bullets, the selection most tests render.
MERIDIAN = ["ach_events_latency", "ach_events_team", "ach_identity_sso"]


def short(bullets=MERIDIAN, **keys):
    """A selection as resume.json's dict: `bullets` in order, and any other keys as given."""
    return {"resume": 2, "bullets": list(bullets), **keys}

# ach_events_terraform, retired - an edit for workspace(edits=[RETIRE]).
RETIRE = ('    j:text "Wrote the platform\'s Terraform." ;\n    j:shows c:terraform ;\n',
          '    j:text "Wrote the platform\'s Terraform." ;\n    j:shows c:terraform ;\n'
          '    j:retired "2026-09-01"^^xsd:date ; j:reason "not true any more" ;\n')


def workspace(root, edits=(), short=None, logged=True, stored=True):
    """(root, ref): the fixture copied to `root`, each (old, new) replaced once in
    career/kb.ttl, and `short` (a dict) stored as the general resume `resumes/test`'s
    selection, its ref returned where a resume.json path was until 6.0 read none
    (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2). The fixture's own
    resume.json in its file-made application is removed either way.

    The edits stand for ones made with `jsk kb apply`. Then the record goes into
    career/store/ and the .ttl files go (`stored`, storekit.seed) - a workspace as jsk
    keeps one, where every write lands with its log entry and no hash is checked. Left as
    files (`stored=False`), log.ttl is made to agree with the edits (`logged`), as the
    file loader checks it, and no selection can be stored."""
    root = Path(root)
    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
    kb = root / "career" / "kb.ttl"
    text = kb.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    kb.write_text(text, encoding="utf-8", newline="\n")
    if edits and logged and not stored:
        relog(root)
    (root / APP / "resume.json").unlink(missing_ok=True)
    ref = str(root / "resumes" / "test" / "resume")
    if stored:
        from storekit import seed
        seed(root)
        if short is not None:
            ref = select(root, short)
    else:
        assert short is None, "a selection lives in the store: workspace(stored=True)"
    return str(root), ref


def select(root, doc, name="test"):
    """The general resume `resumes/<name>` holding `doc` as its selection graph, written
    straight to the store as `resume_select` would leave it; returns its ref - the path the
    render, the record gate and the gates take where a resume.json path went until 6.0
    (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2). `doc` is written as
    given, so a test of a bad selection can plant one the tool would refuse."""
    import os

    from jsk.domain.resume.selection import triples_of
    from jsk.infra.oxigraph import record as R

    R.write_graphs(str(root), {f"resumes/{name}/resume":
                               triples_of(doc, "sel_cv_" + name.replace("-", "_"))})
    return os.path.join(str(root), "resumes", name, "resume")


def relog(root):
    """log.ttl made to agree with kb.ttl as edited, as if jsk had written it."""
    from jsk.infra.oxigraph import record as R
    from jsk.domain.record.parsed import sha256

    before = sha256((FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8"))
    after = sha256((Path(root) / "career" / "kb.ttl").read_text(encoding="utf-8"))
    log = Path(root) / R.LOG_FILE
    log.write_text(log.read_text(encoding="utf-8").replace(before, after),
                   encoding="utf-8", newline="\n")


def store(root):
    return record.load(root)
