"""The old path of jsk.domain.render.themes, kept until every importer names the new one.

The module object is jsk.domain.render.themes itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain.render import themes as _moved

sys.modules[__name__] = _moved
