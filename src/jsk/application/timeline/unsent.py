"""The applications made from files that were never sent: what the 6.0 release strands.

docs/superpowers/plans/2026-10-03-retire-file-pipeline.md (Ruling 5): the file verbs retired
in 6.0, and an application made from files that is still open has no command left in this
CLI to finish it. Such an application is named - by `app_list`, `jsk doctor` and the
career_check tool - with the release that still finishes one and the command that sets it aside, and
this is the one place that decides which ones they are and says so, so the three never
disagree. It was found before the upgrade in 5.1 (P1); this says it after.

An application is file-made and unsent when its folder under applications/ holds a file only
the file pipeline writes (FILE_MADE), its posting graph - if it has one - holds no
`j:AdvertLine` (Ruling 11 of the graph-native plan: lines are the graph-native mark), and
nothing says it was frozen: no application graph in the store, and no application.md from
before the career was a graph. It reads nothing itself: the caller passes the store's graphs
and the folder listing (infra.files.application_listing), and words what it finds.
"""
from ...domain.naming import app_graph
from ...domain.timeline.events import LEGACY
from ..posting.native import has_lines

# What only the file pipeline leaves in an application's folder: the resume_select tool (jsk mcp)'s
# resume.json, `jsk posting build`'s decisions.txt and `jsk posting fetch`'s posting.md. A
# graph-native application keeps its record in the store, and a resume.json beside one is
# never read (Ruling 11), so the posting graph's lines settle a folder holding both.
FILE_MADE = ("resume.json", "decisions.txt", "posting.md")

# The last release whose CLI finishes an application made from files: 5.1 kept every file
# verb working beside its WARN (Ruling 1), and 6.0 retired them. Named in the fix, since the
# person reading it already runs a CLI that cannot.
LAST_FILE_RELEASE = "5.1.0"


def file_made_unsent(graphs, listing):
    """The stems of the applications made from files that are not frozen, sorted.

    Args:
        graphs: {graph name: triples} the store holds - a Store's parsed graphs' quads, or
            what db.read returns.
        listing: {stem: the names in applications/<stem>/} (infra.files.application_listing).

    Returns:
        A tuple of stems, each `applications/<stem>` on disk.
    """
    out = []
    for stem, names in listing.items():
        names = set(names)
        if not names & set(FILE_MADE) or LEGACY in names:
            continue
        rel = f"applications/{stem}"
        if app_graph(rel, "application") in graphs:
            continue
        if has_lines(graphs.get(app_graph(rel, "posting")) or ()):
            continue
        out.append(stem)
    return tuple(sorted(out))


# The fix named "the career_apply tool (jsk mcp) a changeset retiring its posting" until 2026-10-03, which a
# changeset cannot do: it writes the career graph alone, and many such applications have no
# posting graph. The app_drop tool is the way (application/timeline/drop.py).
def note(stem):
    """(what is wrong with `applications/<stem>`, the fix) - an unsent file-made application."""
    return (f"applications/{stem} was made from files and is not sent; jsk 6.0 no longer "
            "finishes such an application",
            f"send it with jsk {LAST_FILE_RELEASE}, the last CLI that does "
            f"(`pip install 'jsk-resume=={LAST_FILE_RELEASE}'`), or drop it: "
            f'the app_drop tool (jsk mcp), app_drop(app="{stem}")')


def warning(stem):
    """The career_check tool's WARN line for an unsent file-made application, id first as every
    finding there starts."""
    text, fix = note(stem)
    return f"file-made-unsent {text}\n        fix: {fix}"
