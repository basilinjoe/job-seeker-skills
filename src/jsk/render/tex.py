"""The old path of jsk.infra.tex, kept until every importer names the new one.

The module object is jsk.infra.tex itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..infra import tex as _moved

sys.modules[__name__] = _moved
