"""The old path of jsk.domain.record.edit, kept until every importer names the new one.

The module object is jsk.domain.record.edit itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain.record import edit as _moved

sys.modules[__name__] = _moved
