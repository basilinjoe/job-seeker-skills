"""Put this checkout's src/ first on the path before any test module is imported.

fixtures.py does the same, but only for a test module that imports it before it imports
jsk. One that does not - `from jsk.graph import ontology` on its first line - got
whichever jsk the interpreter found first, and on a machine with another checkout
installed in editable mode that is the other checkout's code: under pytest-xdist every
later test in that worker then ran against it. pytest imports this file first.
"""
import fixtures  # noqa: F401 - imported for its sys.path side effect
