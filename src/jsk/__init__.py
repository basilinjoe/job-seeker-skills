r"""jsk: the career record, and the rendering and verification toolchain behind it.

The career lives in one validated graph store, `career/store/`, with its log beside it
in the same store. It is changed only through `jsk kb apply` - a changeset merged,
validated and logged - and read with `jsk kb show`, `jsk kb view` and `jsk kb query`.
Each resume is built from it and a selection - the bullets chosen for a posting, as ids,
and a summary, kept in the store as an application's or a general resume's graph - and
carried to a document somebody can send:

    career/store/  +  a target's selection     ->  .tex -> .pdf   (the deliverable)
      jsk kb apply      resume_select (jsk mcp),     \-> plain text (in memory: the
                        then ordered                     parse and terms gates read it)

    jsk doctor                       what works on this machine
    jsk kb new PATH --name NAME      scaffold career/store/ - the career and its log at
                                     r1 - and applications/
    jsk kb VERB [...]                the career record: apply, confirm, show, view, query,
                                     export, check
    jsk resume check TARGET          the record gate: is the selection sound? TARGET is an
                                     application's <stem>, or resumes/<name>
    jsk resume render TARGET         its selection to a .tex (a PDF too with --pdf)
    jsk resume preview TARGET --out D  the same resume in every template, to pick a look
    jsk resume check FILE            the parse gate and the prose gate
    jsk resume check DIR             the record, parse and prose gates over one render
    jsk resume fit TEX --target-pages  fit a render to a page budget
    jsk resume ship TARGET           validate, render and gate, in one pass
    jsk app freeze APP ...           archive a sent application: its record, in the store
    jsk app event APP KIND           add a screen, an offer, a rejection to one
    jsk mcp                          the career and graph-native applications as MCP tools,
                                     the plugin's agents' only way in (the `mcp` extra)

`jsk resume check` checks a selection before anything renders - every id it names is live
in the career, and every number in a bullet it selects traces to a current version of a metric
the bullet cites, so a number the career has since replaced is caught before it is sent -
and the render withholds a claim below the selection's provenance floor. A resume.json was
read as the selection until 6.0, which reads none.

The modules are importable individually. Every command runs through `jsk` (or
`python -m jsk`, where the console script is not on PATH): `jsk <noun> <verb>`, the noun
what you work on, the verb what you do to it.

One dependency is required: `pyoxigraph`, the engine that stores, validates and queries
the career. Everything else is optional and imported at the point of use rather than here:
`pymupdf` to read a PDF, `mcp` to serve `jsk mcp`. A bare Python runs the record gate, the prose gate and the plain-text
parse gate, and
`jsk doctor` is standard-library only, so it can report on a machine before anything is
installed on it.
"""

__version__ = "6.0.0"

__all__ = ["__version__"]
