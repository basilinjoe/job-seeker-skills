r"""jsk: the rendering and verification toolchain behind the Job Seeker Skill.

The career lives in **one Markdown file** — `user-knowledgebase.md` — which a person
and the skill edit directly with ordinary file tools. Nothing here reads it. This
package starts one step later, at the URS record the skill writes out for a particular
application, and carries it to a document somebody can send:

    user-knowledgebase.md  ->  resume.json (URS)  ->  .tex -> .pdf   (the deliverable)
      the skill writes it       the skill writes it   \-> .txt       (paste-in boxes)

    jsk doctor                  what works on this machine
    jsk new PATH --name NAME    scaffold an empty knowledge base
    jsk validate RECORD         the record gate: is the source coherent?
    jsk render RECORD --out D   one record to a PDF and plain text
    jsk preview RECORD --out D  the same record in every template, to pick a look
    jsk check FILE              the parse gate and the prose gate
    jsk gates DIR --record R    the record, parse and prose gates over one render
    jsk fit TEX --target-pages  fit a render to a page budget

There is no compile step and no bundle format, because there is no longer a folder of
concepts to compile: the knowledge base is one file a model can hold in its head, and
the record is written from it the way a resume is. What the old toolchain enforced by
construction, `jsk validate` now enforces by checking — every number in a bullet has
to trace to a recorded metric, and a view's `provenance_floor` still refuses to render
a claim nobody confirmed.

The modules are the documented API and are importable individually; each one that has
a CLI also runs as `python -m jsk.<module>`. `cli.py` is a convenience layer over them
and never the only way in.

Dependencies are deliberately close to zero and every one is optional, imported at the
point of use rather than here: `pymupdf` to read a PDF, `jsonschema` for full record
validation. A bare Python runs the record gate's structural rules, the prose gate and
the `.txt` parse gate — which is what makes `jsk doctor` able to report on a machine
before anything is installed on it.
"""

__version__ = "4.0.0"

__all__ = ["__version__"]
