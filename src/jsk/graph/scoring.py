"""The old path of jsk.domain.matching.scoring, kept until every importer names the new one.

The module object is jsk.domain.matching.scoring itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain.matching import scoring as _moved

sys.modules[__name__] = _moved
