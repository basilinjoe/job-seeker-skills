"""The old module path of `jsk app event` (adapters/cli/event): run, it names the command it became."""
import sys

if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.graph.timeline", "jsk app event"))
