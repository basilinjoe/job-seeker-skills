"""The old path of jsk.domain.ontology, kept until every importer names the new one.

The module object is jsk.domain.ontology itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..domain import ontology as _moved

sys.modules[__name__] = _moved
