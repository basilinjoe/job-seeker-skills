"""The number check's old path, and its binding: the career read through the engine's queries."""
from ..application.gates import numbers as _numbers
from ..domain.gates.numbers import (ACRONYM, NUMBER, SCALE, Fault, covered, numerals, quoted,
                                    trace)
from ..infra.oxigraph.queries import OxigraphQueries

__all__ = ["ACRONYM", "NUMBER", "SCALE", "Fault", "covered", "facts", "numerals", "quoted",
           "trace", "untraced"]


def untraced(store, bullets, today=None):
    """[Fault] for the `bullets` whose words state a number the career's metrics do not hold.

    Args:
        store: a loaded workspace (store.load).
        bullets: achievement iris, in order.
        today: accepted so every caller passes one clock.

    Returns:
        application.gates.numbers.untraced over the store's queries. Runs two SELECTs.
    """
    return _numbers.untraced(OxigraphQueries(store), bullets, today)


def facts(store):
    """(text, cites, versions) of a loaded workspace, as application.gates.numbers.facts reads them.

    Args:
        store: a loaded workspace (store.load).

    Returns:
        Each bullet's words, the metrics it cites, and each metric's versions as
        (version, {numbers}, closed day or None). Runs two SELECTs.
    """
    return _numbers.facts(OxigraphQueries(store))
