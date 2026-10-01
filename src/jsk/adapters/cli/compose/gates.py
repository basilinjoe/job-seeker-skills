"""The gates' ports, bound: the career's feature reads (infra.oxigraph.queries), its standing
with its log (infra.oxigraph.record.state, looked up there at each call, where a test
patches it), the clock for a caller that has not read it, and a resume.json's plan.

The checks are application/gates/'s; each function here keeps the signature its callers
use, with a loaded Store in place of the ports. Nothing is imported until a call.
"""
import datetime


def untraced(store, bullets, today=None):
    """[Fault] for the `bullets` whose words state a number the career's metrics do not hold.

    Args:
        store: a loaded workspace (compose.record.load).
        bullets: achievement iris, in order.
        today: accepted so every caller passes one clock.

    Returns:
        application.gates.numbers.untraced over the store's queries. Runs two SELECTs.
    """
    from ....application.gates.numbers import untraced as traced
    from ....infra.oxigraph.queries import OxigraphQueries

    return traced(OxigraphQueries(store), bullets, today)


def facts(store):
    """(text, cites, versions) of a loaded workspace, as application.gates.numbers.facts
    reads them.

    Args:
        store: a loaded workspace (compose.record.load).

    Returns:
        Each bullet's words, the metrics it cites, and each metric's versions as
        (version, {numbers}, closed day or None). Runs two SELECTs.
    """
    from ....application.gates.numbers import facts as read
    from ....infra.oxigraph.queries import OxigraphQueries

    return read(OxigraphQueries(store))


def findings(doc, store, today=None):
    """(fails, warns): every finding for a short file - a dict, or a path to one - over a
    loaded workspace (application.gates.record.findings).

    Args:
        doc: the resume.json, as a dict or its path.
        store: a loaded workspace.
        today: the date the years claims are measured to; by default today.

    Returns:
        The FAIL and WARN lines. Reads the file when given its path.

    Raises:
        ShortError: a path that will not read as a resume.json.
    """
    from ....application.gates.record import findings as found
    from ....infra.oxigraph import record as R
    from ....infra.oxigraph.queries import OxigraphQueries
    from .resume import read

    today = today or datetime.date.today()
    if not isinstance(doc, dict):
        doc = read(doc)
    return found(doc, store, today, queries=OxigraphQueries(store), state=R.state)


def number_lines(text, doc, store, posting=None, today=None):
    """FAIL lines for each numeral in a letter the application cannot stand on
    (application.gates.letter.number_lines).

    Args:
        text: the letter's body.
        doc: the resume.json, as a dict.
        store: the loaded workspace.
        posting: posting.md's text, or None.
        today: the date the years claims are measured to; by default today.

    Returns:
        The FAIL lines. Runs the store's SELECTs.
    """
    from ....application.gates.letter import number_lines as lines
    from ....infra.oxigraph import record as R
    from ....infra.oxigraph.queries import OxigraphQueries

    return lines(text, doc, store, posting, today or datetime.date.today(),
                 queries=OxigraphQueries(store), state=R.state)


def from_record(record, pdf):
    """The region and page budget the render of `pdf` was built with, from its resume.json.

    Args:
        record: the resume.json.
        pdf: the rendered PDF, whose metadata names its variant.

    Returns:
        (region, page budget, None) from the plan, or (None, None, why) when the record
        would not build - reported, never fatal.
    """
    from ....infra.pdf import variant_of
    from .resume import from_path

    try:
        plan, _ = from_path(record, fmt=variant_of(pdf))
    except Exception as exc:                       # noqa: BLE001 - reported, never fatal
        return None, None, f"{type(exc).__name__}: {exc}"
    return plan.get("region"), plan.get("pages"), None
