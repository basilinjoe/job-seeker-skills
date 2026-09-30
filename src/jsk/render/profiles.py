"""The old path of jsk.infra.profiles, kept until every importer names the new one.

The module object is jsk.infra.profiles itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..infra import profiles as _moved

sys.modules[__name__] = _moved
