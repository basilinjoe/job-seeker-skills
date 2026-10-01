#!/usr/bin/env python3
"""`jsk kb new`'s old module path, kept until P6 (Ruling 4) for the names
adapters/cli/kb/new.py and the tests reach through it.

The scaffold itself is application/record/scaffold.py; the names callers and tests use
stay importable here.
"""
import sys

from .adapters.cli.kb.new import INSTALL as INSTALL
from .adapters.cli.kb.new import main as main
from .adapters.cli.kb.new import scaffold as scaffold
from .application.record.scaffold import APPLICATIONS_README as APPLICATIONS_README
from .application.record.scaffold import GITATTRIBUTES as GITATTRIBUTES
from .application.record.scaffold import STORE as STORE
from .application.record.scaffold import first_write as first_write
from .application.record.scaffold import header as header
from .application.record.scaffold import kept_name as kept_name

if __name__ == "__main__":
    from .cliutil import retired_path

    sys.exit(retired_path("jsk.kb", "jsk kb new"))
