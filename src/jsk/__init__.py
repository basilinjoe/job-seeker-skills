r"""jsk: the career record, and the rendering and verification toolchain behind it.

The career lives in one validated graph file, `career/kb.ttl`, with its log beside it.
It is changed only through `jsk kb apply` - a changeset merged, validated and logged -
and read with `jsk kb show`, `jsk kb view` and `jsk kb query`. Each application's
resume is built from it and a short resume.json - the bullets chosen for the posting,
as ids, and a summary - and carried to a document somebody can send:

    career/kb.ttl  +  resume.json (short)      ->  .tex -> .pdf   (the deliverable)
      jsk kb apply      jsk kb export,               \-> .txt       (paste-in boxes)
                        then ordered

    jsk doctor                  what works on this machine
    jsk new PATH --name NAME    scaffold career/kb.ttl, its log at r1, and applications/
    jsk kb VERB [...]           the career record: apply, confirm, show, view, query,
                                export, check
    jsk match POSTING.ttl       a posting against the career, through the vocabulary
    jsk migrate KB.md           an old user-knowledgebase.md to career/kb.ttl, once
    jsk validate RESUME         the record gate: is the resume.json sound?
    jsk render RESUME --out D   one resume.json to a PDF and plain text
    jsk preview RESUME --out D  the same resume in every template, to pick a look
    jsk check FILE              the parse gate and the prose gate
    jsk gates DIR --record R    the record, parse and prose gates over one render
    jsk fit TEX --target-pages  fit a render to a page budget
    jsk ship RESUME --out D     validate, render and gate, in one pass
    jsk freeze APP ...          archive a sent application as application.ttl
    jsk event APP KIND          add a screen, an offer, a rejection to one

`jsk validate` checks a resume.json before anything renders - every id it names is live
in kb.ttl, and every number in a bullet it selects traces to a current version of a metric
the bullet cites, so a number the career has since replaced is caught before it is sent -
and the render withholds a claim below the file's provenance floor.

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

__version__ = "4.3.0"

__all__ = ["__version__"]
