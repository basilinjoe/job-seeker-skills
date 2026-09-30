"""The old path of jsk.domain.record.view, kept until every importer names the new one.

The module object is jsk.domain.record.view itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain.record import view as _moved

sys.modules[__name__] = _moved
