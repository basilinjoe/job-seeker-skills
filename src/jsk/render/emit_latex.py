"""The old path of jsk.domain.render.emit_latex, kept until every importer names the new one.

The module object is jsk.domain.render.emit_latex itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain.render import emit_latex as _moved

sys.modules[__name__] = _moved
