"""The old path of jsk.infra.oxigraph.db, kept until every importer names the new one.

The module object is jsk.infra.oxigraph.db itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..infra.oxigraph import db as _moved

sys.modules[__name__] = _moved
