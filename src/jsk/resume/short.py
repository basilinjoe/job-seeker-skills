"""The short resume.json: one application's choices, and nothing the career holds.

It replaced a 30-47KB URS record copied out of career/kb.ttl, of which the parts anyone
authored - the view and the summary - were 3KB (ElevenLabs, 2026-09-25). The copy is
what needed a spec, a refresh command and a gate for drift; a file that holds only ids
and settings can go stale in one way only, an id the career no longer holds, and that
is what `ids` checks.

The file's own checks are domain/resume/short.py and the loading
application/render/load_resume.py; this module binds them to the disk and the store, and
keeps `python -m jsk.resume.short`.
"""
from ..application.render.load_resume import career_of, read_short, workspace_of
from ..cliutil import utf8_stdout
from ..domain.resume.short import CONFIRM as CONFIRM
from ..domain.resume.short import FLOORS as FLOORS
from ..domain.resume.short import FORMATS as FORMATS
from ..domain.resume.short import KEYS as KEYS
from ..domain.resume.short import LISTS as LISTS
from ..domain.resume.short import STATUSES as STATUSES
from ..domain.resume.short import SUMMARY_KEYS as SUMMARY_KEYS
from ..domain.resume.short import VERSION as VERSION
from ..domain.resume.short import ShortError as ShortError
from ..domain.resume.short import confirmed as confirmed
from ..domain.resume.short import digest as digest
from ..domain.resume.short import ids as ids
from ..domain.resume.short import shape as shape
from ..domain.resume.short import summary_status as summary_status
from ..domain.resume.short import unearned as unearned


def read(path):
    """The file as a dict, or ShortError naming what to do."""
    from ..infra import files

    return read_short(path, files)


def workspace(path):
    """The workspace root above the file. Walked up, never worked out: the real one is
    the folder holding career/store/."""
    from ..infra.files import find_root

    return workspace_of(path, find_root)


def career(root):
    """The workspace at `root`, loaded. A store that will not open is a ShortError with
    its fix, as a file that cannot be read is - never a traceback."""
    from ..graph import store as S

    return career_of(root, S.load)


def main(argv):
    """`python -m jsk.resume.short <resume.json>`: shape and ids, PASS or FAIL.

    doctor spawns it over the example workspace: the record gate (jsk.gates.record)
    replaces it there once it lands, and this stays the check with no gate behind it."""
    args = argv[1:]
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: python -m jsk.resume.short <resume.json>")
        return 2
    path = args[0]
    utf8_stdout()
    print(f"checking: {path}")
    try:
        doc = read(path)
        root = workspace(path)
        fails = shape(doc) or ids(doc, career(root))
    except ShortError as e:
        print(f"FAIL  {e}\n      fix: {e.fix}")
        return 1
    for line in fails:
        print(f"FAIL  {line}")
    if fails:
        print(f"FAIL {len(fails)}")
        return 1
    print("PASS - safe to render")
    return 0


if __name__ == "__main__":
    import sys

    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.resume.short", "jsk resume check RESUME.json"))
