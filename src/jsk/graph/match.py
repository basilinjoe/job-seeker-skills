"""`jsk match` and `python -m jsk.graph.match`: the documented entry point.

The command is adapters/cli/match.py and the match application/tailor/match_posting.py;
this module keeps the path and every name callers and tests reach through it, each with
today's signature - a loaded Store first - and the engine's queries and the selection
bound in (Ruling 4 of the onion design).
"""
import sys

from ..application.tailor.match_posting import COVER as COVER
from ..application.tailor.match_posting import TOP as TOP
from ..application.tailor.match_posting import application as application
from ..application.tailor.match_text import markdown as markdown
from ..domain.assessment.verdict import RAISE_FIX as RAISE_FIX
from ..domain.assessment.verdict import RANK as RANK
from ..domain.matching.report import SOURCES as SOURCES
from ..domain.matching.report import blocks as blocks
from ..domain.matching.report import fault_question as fault_question
from ..domain.matching.report import quoted as quoted
from ..domain.matching.report import verdict as verdict


def posting_in(store, app):
    """The one Posting the application `app` (its directory) holds, or None
    (application.tailor.match_posting.posting_in)."""
    from ..application.tailor.match_posting import posting_in as posting_of
    from ..infra.files import file_name

    return posting_of(store, file_name(app, store.root))


def record_faults(store, post, today, budget, ranked=None):
    """The bullets this posting's draft would carry whose numbers the record cannot back,
    as questions for round 1 (application.tailor.match_posting.record_faults over the
    engine's queries and graph.select)."""
    from ..application.tailor.match_posting import record_faults as faults
    from ..infra.oxigraph.queries import OxigraphQueries
    from . import select as SEL

    return faults(store, OxigraphQueries(store), post, today, budget, ranked, SEL.select)


def faults_in(store, bullets, today):
    """record_faults' entries for `bullets` (iris), in their order
    (application.tailor.match_posting.faults_in over the engine's queries)."""
    from ..application.tailor.match_posting import faults_in as faults
    from ..infra.oxigraph.queries import OxigraphQueries

    return faults(OxigraphQueries(store), bullets, today)


def result(store, post, today, budget, elsewhere=0):
    """Everything `jsk match` reports, as plain data (application.tailor.match_posting.result
    over the engine's queries and graph.select)."""
    from ..application.tailor.match_posting import result as matched
    from ..infra.oxigraph.queries import OxigraphQueries
    from . import select as SEL

    return matched(store, OxigraphQueries(store), post, today, budget, elsewhere, SEL.select)


def main(argv=None):
    """`jsk match` (adapters.cli.match.main), over sys.argv when no argv is given."""
    from ..adapters.cli.match import main as match

    return match(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
