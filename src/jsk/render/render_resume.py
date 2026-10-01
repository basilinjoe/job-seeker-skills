#!/usr/bin/env python3
"""`jsk resume render`'s old module path: where its ports are bound until P6.

The command is adapters/cli/render.py and the render application/render/render_resume.py;
this module keeps the path, the names callers and tests reach through it, and the TeX
engine as `compile_pdf`, which a test patches here (Ruling 4 of the onion design).
"""
import os
import sys

from ..domain.render.page_report import LAST_PAGE_FLOOR as LAST_PAGE_FLOOR
from ..domain.render.page_report import page_report as page_report
from ..domain.render.targets import STEMS as STEMS
from ..domain.render.targets import safe_name as safe_name
from ..domain.render.targets import select_targets as select_targets
from ..infra.tex import compile_pdf


class Tex:
    """The TeX engine as this module names it, looked up at each call.

    A test patches render_resume.compile_pdf, so the render is handed this rather than
    infra.tex itself: the patch is then what the render compiles with.
    """

    def compile_pdf(self, tex_path, out_dir):
        """(the PDF's path or None, a note), from this module's compile_pdf (infra.tex)."""
        return compile_pdf(tex_path, out_dir)


def company_of(record_path, store=None):
    """The employer of the posting of the application the record sits in, or None.

    mode-tailor.md has always laid an application out as
    `<Name>_<Company>_Resume.{tex,pdf,txt}`, and the renderer wrote `<Name>_Resume`:
    a recruiter holding five candidates' files could not tell whose was for them.

    `store` is the workspace the render already loaded, so this costs one SELECT over
    the posting graph and no second load. A naming nicety, so a record outside an
    application, or one with no posting, names the file with no company rather than
    stopping the render."""
    from ..graph import store as S
    from ..graph.queries import PRE
    from ..infra.files import workspace_of_app

    root, rel = workspace_of_app(os.path.dirname(os.path.abspath(record_path)))
    if root is None:
        return None
    if store is None:
        store = S.load(root)
    graph = S.graph_iri(S.app_graph(rel, "posting"))
    found = store.select(PRE + f"SELECT ?c WHERE {{ GRAPH <{graph}> {{ ?p j:company ?c }} }}")
    return found[0]["c"].value if found else None


def page_count(pdf):
    """Pages in the PDF just written, or None if it cannot be measured
    (application.render.render_resume.page_count over infra.pdf)."""
    from ..application.render.render_resume import page_count as count
    from ..infra import pdf as reader

    return count(reader, pdf)


def last_page_fill(pdf):
    """How far down the last page the text reaches, in percent, or None
    (application.render.render_resume.last_page_fill over infra.pdf)."""
    from ..application.render.render_resume import last_page_fill as fill
    from ..infra import pdf as reader

    return fill(reader, pdf)


def main(argv):
    """`jsk resume render` (adapters.cli.render.main), with this module's TeX engine."""
    from ..adapters.cli.render import main as render

    return render(argv, tex=Tex(), company_of=company_of)


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.render.render_resume", "jsk resume render"))
