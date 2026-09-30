"""The old path of jsk.infra.oxigraph.record, kept until every importer names the new one.

The module object is jsk.infra.oxigraph.record itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..infra.oxigraph import record as _moved

sys.modules[__name__] = _moved
