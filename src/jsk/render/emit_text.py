"""The old path of jsk.domain.render.emit_text, kept until every importer names the new one.

The module object is jsk.domain.render.emit_text itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain.render import emit_text as _moved

sys.modules[__name__] = _moved
