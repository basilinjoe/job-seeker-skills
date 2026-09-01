"""`python -m jsk_okf` - the same entry point as the `okf` console script.

Worth keeping even though `okf` exists: a `pip install --user` puts the package where
the interpreter can import it without necessarily putting its scripts on PATH, and this
is the spelling that works either way.
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(["okf"] + sys.argv[1:]))
