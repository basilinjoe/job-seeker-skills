"""The match's old path, and its binding: each question asked of a loaded Store.

The rules live in domain/matching (resolve, rank, cover, nearest, questions) and ask a
RecordQueries; the SPARQL is infra/oxigraph/queries.py's. Each function here keeps the
signature its callers use - a Store first - and asks the engine's queries over it.
"""
from ..domain.matching import nearest as _nearest
from ..domain.matching import questions as _questions
from ..domain.matching import rank as _rank
from ..domain.matching import resolve as _resolve
from ..domain.matching.cover import cover as cover
from ..domain.matching.cover import unresolved as unresolved
from ..domain.matching.model import Match as Match
from ..domain.matching.model import Question as Question
from ..domain.matching.model import Requirement as Requirement
from ..domain.matching.model import Resolution as Resolution
from ..domain.matching.model import Row as Row
from ..domain.matching.model import local as local
from ..domain.matching.nearest import COVER as COVER
from ..domain.matching.nearest import FILLER as FILLER
from ..domain.matching.nearest import words as words
from ..domain.matching.resolve import resolve as resolve
from ..infra.oxigraph.queries import PRE as PRE
from ..infra.oxigraph.queries import OxigraphQueries


def requirements(store, post):
    """A posting's [Requirement] in iri order (OxigraphQueries.requirements)."""
    return OxigraphQueries(store).requirements(post)


def labels(store):
    """{normalised label: {concept iris}} (domain.matching.resolve.labels)."""
    return _resolve.labels(OxigraphQueries(store))


def concepts(store):
    """Every concept iri the workspace states something about."""
    return OxigraphQueries(store).concepts()


def paths_to(store, concept):
    """(project, held, hops, implied) for every live project holding what counts as `concept`."""
    return OxigraphQueries(store).paths_to(concept)


def broader_held(store, concept):
    """(project, held) where the project holds only something `concept` counts as."""
    return OxigraphQueries(store).broader_held(concept)


def match(store, post):
    """{requirement iri: Match} for one posting (domain.matching.resolve.match)."""
    return _resolve.match(OxigraphQueries(store), post)


def evidence(store, project, concepts):
    """confirmed, unconfirmed or tag for a project (domain.matching.resolve.evidence)."""
    return _resolve.evidence(OxigraphQueries(store), project, concepts)


def confirmed_texts(store, project, concepts):
    """The sorted words of the live, confirmed bullets showing one of the concepts."""
    return OxigraphQueries(store).confirmed_texts(project, concepts)


def projects(store):
    """{project: (strength, recency, seniority)} for every live project."""
    return OxigraphQueries(store).projects()


def posting_seniority(store, post):
    """The seniority a posting asks for, or None."""
    return OxigraphQueries(store).posting_seniority(post)


def rank(store, post, matches, today):
    """[Row] for every live project, best first (domain.matching.rank.rank)."""
    return _rank.rank(OxigraphQueries(store), post, matches, today)


def posting(store, req):
    """The posting a requirement belongs to, or None."""
    return OxigraphQueries(store).posting_of(req)


def answered(store, post=None):
    """{(asked, concept): postings} the analysts named on the postings other than `post`."""
    return OxigraphQueries(store).answered(post)


def nearest(store, limit=3, post=None):
    """near(label) -> the concepts closest to it (domain.matching.nearest.nearest)."""
    return _nearest.nearest(OxigraphQueries(store), limit, post)


def labels_in(store):
    """named(line) -> the concepts whose whole label it holds (domain.matching.nearest.labels_in)."""
    return _nearest.labels_in(OxigraphQueries(store))


def questions(store, matches):
    """[Question] a tailoring round should ask (domain.matching.questions.questions)."""
    return _questions.questions(OxigraphQueries(store), matches)
