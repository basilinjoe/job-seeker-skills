"""The names the record's graphs go by: the short name a finding prints and the IRI a query
uses, the same in memory as in career/store/, so a query means the same thing over either."""
from urllib.parse import quote, unquote

GRAPH = "tag:jsk,2026:graph/"


def graph_iri(name):
    """The IRI of the graph named `name`. Percent-encoded: an application folder can hold a
    space, and an IRI cannot."""
    return GRAPH + quote(name, safe="/-._~")


def name_of(iri):
    """A graph IRI's short name, or None when it is not a record graph."""
    value = getattr(iri, "value", iri)
    if isinstance(value, str) and value.startswith(GRAPH):
        return unquote(value[len(GRAPH):])
    return None


def short_name(name):
    """graph_name for a name already relative to the workspace (`career/kb.ttl`). A graph
    name comes back as it is, so a caller may pass either."""
    if name in ("career/kb.ttl", "career/log.ttl"):
        return name[len("career/"):-len(".ttl")]
    if name == "vocabulary.ttl" or name.endswith(("/vocabulary.ttl", "\\vocabulary.ttl")):
        return "vocabulary"
    head, _, tail = name.rpartition("/")
    if head.startswith("applications/") and head.count("/") == 1 and \
            tail in ("posting.ttl", "application.ttl", "gaps.ttl"):
        return name[:-len(".ttl")]
    return name


def app_graph(app, kind):
    """The graph name of an application's `kind` (posting, application, gaps, review,
    resume). `app` is its name relative to the workspace (`applications/<stem>`)."""
    return f"{app.rstrip('/')}/{kind}"


# The folders whose graphs are one application's or one general resume's, never the
# career's: a fault in one of them is that one's, and blocks no write to the career. A
# general resume's selection is `resumes/<name>/resume` (Ruling 10 of
# docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md).
OWN = ("applications/", "resumes/")


def resume_graph(name):
    """The graph name of the general resume `name`'s selection: `resumes/<name>/resume`."""
    return f"resumes/{name.strip('/')}/resume"


def is_own(name):
    """Whether the graph `name` is one application's or one general resume's."""
    return name.startswith(OWN)
