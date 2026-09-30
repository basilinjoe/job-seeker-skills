"""The workspace on disk: where it is, found from any path inside it."""
import os


def find_root(start):
    """The nearest folder at or above `start` holding career/store/ - or career/kb.ttl, a
    career from before the store, found so that it can be refused with the import as the
    fix - or None."""
    here = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(here, "career", "store")) or \
                os.path.isfile(os.path.join(here, "career", "kb.ttl")):
            return here
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up
