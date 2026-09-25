r"""jsk: the career record, and the rendering and verification toolchain behind it.

The career lives in one validated graph file, `career/kb.ttl`, with its log beside it.
It is changed only through `jsk kb apply` - a changeset merged, validated and logged -
and read with `jsk kb show`, `jsk kb view` and `jsk kb query`. Each application's
resume is a URS record drafted from it, retuned for the posting, and carried to a
document somebody can send:

    career/kb.ttl  ->  resume.json (URS)        ->  .tex -> .pdf   (the deliverable)
      jsk kb apply       jsk kb export --urs,         \-> .txt       (paste-in boxes)
                         then retuned

    jsk doctor                  what works on this machine
    jsk new PATH --name NAME    scaffold career/kb.ttl, its log at r1, and applications/
    jsk kb VERB [...]           the career record: apply, confirm, show, view, query,
                                export --urs, check
    jsk match POSTING.ttl       a posting against the career, through the vocabulary
    jsk migrate KB.md           an old user-knowledgebase.md to career/kb.ttl, once
    jsk validate RECORD         the record gate: is the source coherent?
    jsk render RECORD --out D   one record to a PDF and plain text
    jsk preview RECORD --out D  the same record in every template, to pick a look
    jsk check FILE              the parse gate and the prose gate
    jsk gates DIR --record R    the record, claims, parse and prose gates over one render
    jsk fit TEX --target-pages  fit a render to a page budget
    jsk ship RECORD --out D     validate, render and gate, in one pass
    jsk freeze APP ...          archive a sent application as application.ttl
    jsk event APP KIND          add a screen, an offer, a rejection to one

`jsk validate` checks a record before anything renders - every number in a bullet has to
trace to a recorded metric, and a view's `provenance_floor` refuses to render a claim
nobody confirmed - and the claims gate joins the record with kb.ttl, so a number or a
provenance the career has since replaced is caught before it is sent.

The modules are the documented API and are importable individually; each one that has
a CLI also runs as `python -m jsk.<module>` - `python -m jsk.gates.check_ats`,
`python -m jsk.urs.render_resume`. `cli.py` is a convenience layer over them and never
the only way in.

One dependency is required: `pyoxigraph`, the engine that reads, validates and queries
kb.ttl. Everything else is optional and imported at the point of use rather than here:
`pymupdf` to read a PDF, and `markdown-it-py` with `pyyaml` for `jsk migrate` alone. A
bare Python runs the record gate, the prose gate and the `.txt` parse gate, and
`jsk doctor` is standard-library only, so it can report on a machine before anything is
installed on it.
"""

__version__ = "4.0.0"

__all__ = ["__version__"]
