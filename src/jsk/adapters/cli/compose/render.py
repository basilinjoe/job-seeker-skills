"""`jsk resume render`'s ports, bound: the TeX engine, the PDF reader, and the posting's
employer read from the workspace the render loaded.

The render is application/render/render_resume.py and the command adapters/cli/render.py.
A test patches `compile_pdf` here, so the render is handed this module's Tex, which looks
the name up at each call (Ruling 4 of the onion design).
"""
import os

from ....infra.tex import compile_pdf


class Tex:
    """The TeX engine as this module names it, looked up at each call.

    A test patches compose.render.compile_pdf, so the render is handed this rather than
    infra.tex itself: the patch is then what the render compiles with.
    """

    def compile_pdf(self, tex_path, out_dir):
        """Compile a .tex with this module's compile_pdf (infra.tex).

        Args:
            tex_path: the .tex.
            out_dir: where the PDF goes.

        Returns:
            (the PDF's path or None, a note). Runs the TeX engine.
        """
        return compile_pdf(tex_path, out_dir)


def company_of(record_path, store=None):
    """The employer of the posting of the application the record sits in, or None.

    mode-tailor.md has always laid an application out as
    `<Name>_<Company>_Resume.{tex,pdf,txt}`, and the renderer wrote `<Name>_Resume`:
    a recruiter holding five candidates' files could not tell whose was for them.

    A naming nicety, so a record outside an application, or one with no posting, names
    the file with no company rather than stopping the render.

    Args:
        record_path: the resume.json.
        store: the workspace the render already loaded, so this costs one SELECT over the
            posting graph and no second load; None loads it.

    Returns:
        The company's name, or None.
    """
    from ....domain import naming
    from ....infra.files import workspace_of_app
    from ....infra.oxigraph.queries import PRE
    from .record import load

    root, rel = workspace_of_app(os.path.dirname(os.path.abspath(record_path)))
    if root is None:
        return None
    if store is None:
        store = load(root)
    graph = naming.graph_iri(naming.app_graph(rel, "posting"))
    found = store.select(PRE + f"SELECT ?c WHERE {{ GRAPH <{graph}> {{ ?p j:company ?c }} }}")
    return found[0]["c"].value if found else None


def page_count(pdf):
    """Pages in the PDF just written (application.render.render_resume.page_count over
    infra.pdf).

    Args:
        pdf: the PDF's path.

    Returns:
        The page count, or None if it cannot be measured.
    """
    from ....application.render.render_resume import page_count as count
    from ....infra import pdf as reader

    return count(reader, pdf)


def last_page_fill(pdf):
    """How far down the last page the text reaches (application.render.render_resume.
    last_page_fill over infra.pdf).

    Args:
        pdf: the PDF's path.

    Returns:
        The fill in percent, or None if it cannot be measured.
    """
    from ....application.render.render_resume import last_page_fill as fill
    from ....infra import pdf as reader

    return fill(reader, pdf)
