#!/usr/bin/env python3
"""`python -m jsk.kb` and `jsk new`: the documented entry point, handed over to
adapters/cli/kb/new.py until P5 makes it `jsk kb new` (Ruling 4).

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
    sys.exit(main())
