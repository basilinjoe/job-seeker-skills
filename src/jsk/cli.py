#!/usr/bin/env python3
"""`jsk.cli`: where the `jsk` console script points (`jsk.cli:main_console`), for good.

An install made before the CLI became `jsk <noun> <verb>` keeps a launcher that imports this
module, so it stays (Ruling 4 of the onion design) and hands every call over to
adapters/cli/main.py, where the nouns, their verbs and the retired names are. It once also
re-exported about thirty names "callers and tests reach through it"; those went on 2026-10-04
(Ruling 7 of docs/superpowers/plans/2026-10-04-mcp-first.md) and callers import the real module.
"""
import sys

from .adapters.cli.main import main as main


def main_console():
    """The `jsk` console script.

    Separate from main() because main() takes the whole argv the way a script's does -
    that is the documented shape every in-process caller here already uses, and the
    generated console wrapper passes no arguments at all.

    Returns:
        The exit code.
    """
    return main(sys.argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
