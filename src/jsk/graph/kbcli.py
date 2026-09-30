"""The old path of jsk.adapters.cli.kb, kept until every importer names the new one.

The module object is jsk.adapters.cli.kb itself, so an attribute patched through this
path is patched where the code looks it up.
"""
import sys

from ..adapters.cli import kb as _moved

if __name__ == "__main__":
    sys.exit(_moved.main())

sys.modules[__name__] = _moved
