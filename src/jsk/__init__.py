r"""jsk: the career record, and the rendering and verification toolchain behind it.

The career lives in one validated graph store, `career/store/`, with its log beside it
in the same store. It is changed only through the career_apply tool (jsk mcp) - a changeset
merged, validated and logged - and read with the career_show, career_view and career_query
tools.
Each resume is built from it and a selection - the bullets chosen for a posting, as ids,
and a summary, kept in the store as an application's or a general resume's graph - and
carried to a document somebody can send:

    career/store/  +  a target's selection     ->  .tex -> .pdf   (the deliverable)
      career_apply (jsk mcp)   resume_select (jsk mcp),     \-> plain text (in memory: the
                               then ordered                     parse and terms gates read it)

    jsk doctor                       what works on this machine
    jsk kb new PATH --name NAME      scaffold career/store/ - the career and its log at
                                     r1 - and applications/
    jsk kb load WORKSPACE|DUMP       fill an empty career/store/, once
    jsk kb dump [--out FILE]         the whole record as TriG: a backup, and what load reads
    jsk mcp                          the career and graph-native applications as MCP tools
                                     (career_*, app_*, resume_*, letter_check), the plugin's
                                     agents' only way in

Everything else is a tool of `jsk mcp`, not a command (2026-10-04): the resume_check tool checks
a selection before anything renders - every id it names is live
in the career, and every number in a bullet it selects traces to a current version of a metric
the bullet cites, so a number the career has since replaced is caught before it is sent -
and the render withholds a claim below the selection's provenance floor. A resume.json was
read as the selection until 6.0, which reads none.

The modules are importable individually. The three commands that remain run through `jsk` (or
`python -m jsk`, where the console script is not on PATH): `jsk <noun> <verb>`.

One dependency is required: `pyoxigraph`, the engine that stores, validates and queries
the career. Everything else is optional and imported at the point of use rather than here:
`pymupdf` to read a PDF, `mcp` to serve `jsk mcp`. A bare Python runs the record gate, the prose gate and the plain-text
parse gate, and
`jsk doctor` is standard-library only, so it can report on a machine before anything is
installed on it.
"""

__version__ = "6.0.0"

__all__ = ["__version__"]
