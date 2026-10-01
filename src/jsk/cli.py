#!/usr/bin/env python3
"""`jsk.cli`: where the `jsk` console script points (`jsk.cli:main_console`), for good.

An install made before the CLI became `jsk <noun> <verb>` keeps a launcher that imports this
module, so it stays (Ruling 4 of the onion design) and hands every call over to
adapters/cli/main.py, where the nouns, their verbs and the retired names are. The names
callers and tests reach through it are kept here too.
"""
import sys

from .adapters.cli.dispatch import NO_RECORD as NO_RECORD
from .adapters.cli.dispatch import SUBPACKAGE as SUBPACKAGE
from .adapters.cli.dispatch import WHOLE_ARGV as WHOLE_ARGV
from .adapters.cli.dispatch import call_gate as call_gate
from .adapters.cli.dispatch import module_for as module_for
from .adapters.cli.dispatch import run_in_process as run_in_process
from .adapters.cli.dispatch import workspace_refusal as workspace_refusal
from .adapters.cli.doctor import cmd_doctor as cmd_doctor
from .adapters.cli.doctor import store_report as store_report
from .adapters.cli.gates.check import CHECK_GATES as CHECK_GATES
from .adapters.cli.gates.check import DEFAULT_RECORD as DEFAULT_RECORD
from .adapters.cli.gates.check import DOC_GATES as DOC_GATES
from .adapters.cli.gates.check import cmd_check as cmd_check
from .adapters.cli.gates.check import cmd_gates as cmd_gates
from .adapters.cli.gates.check import cmd_validate as cmd_validate
from .adapters.cli.gates.check import gate_result as gate_result
from .adapters.cli.gates.check import gate_results as gate_results
from .adapters.cli.gates.check import parse_pages as parse_pages
from .adapters.cli.gates.check import print_results as print_results
from .adapters.cli.gates.check import rendered_documents as rendered_documents
from .adapters.cli.gates.check import worst_exit as worst_exit
from .adapters.cli.main import HELP_ENDS_BEFORE as HELP_ENDS_BEFORE
from .adapters.cli.main import NOUNS as NOUNS
from .adapters.cli.main import RETIRED as RETIRED
from .adapters.cli.main import main as main
from .adapters.cli.main import usage as usage
from .application.guards import VIEW_GONE as VIEW_GONE
from .application.guards import frozen_refusal as frozen_refusal
from .application.guards import record_refusal as record_refusal
from .application.guards import unloaded_refusal as unloaded_refusal
from .application.guards import view_refusal as view_refusal


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
