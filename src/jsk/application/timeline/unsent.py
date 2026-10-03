"""The applications made from files that were never sent: what the 6.0 release would strand.

docs/superpowers/plans/2026-10-03-retire-file-pipeline.md (Ruling 5, P1): the file verbs
retire in 6.0, and an application made from files that is still open then has no command
left to finish it. Such an application is named before that happens - by `app_list`, `jsk
doctor` and `jsk kb check` - and this is the one place that decides which ones they are, so
the three never disagree.

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

# What only the file pipeline leaves in an application's folder: `jsk kb export --out`'s
# resume.json, `jsk posting build`'s decisions.txt and `jsk posting fetch`'s posting.md. A
# graph-native application keeps its record in the store, and a resume.json beside one is
# never read (Ruling 11), so the posting graph's lines settle a folder holding both.
FILE_MADE = ("resume.json", "decisions.txt", "posting.md")


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
