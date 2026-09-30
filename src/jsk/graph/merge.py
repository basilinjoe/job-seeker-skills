"""The old path of jsk.domain.record.merge, kept until every importer names the new one.

The module object is jsk.domain.record.merge itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain.record import merge as _moved

sys.modules[__name__] = _moved
