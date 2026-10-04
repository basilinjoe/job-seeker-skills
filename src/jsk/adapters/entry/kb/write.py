"""The refusal printer `jsk kb load` shares: a record use case's refusal said as lines.

It held `jsk kb apply` and the logged write's printer until 2026-10-04, when the career_apply
tool (adapters/mcp, over compose/career.py) took over writing the career
(docs/superpowers/plans/2026-10-04-retire-duplicated-cli.md, Ruling 4).
"""
from ..presenters import refuse, show_findings, unclean


def refused(err):
    """Print a refusal raised by a record use case (application/record/refusals.py).

    Args:
        err: Refused, Problems, Failing or Unclean.

    Returns:
        1, the exit code of a refusal.
    """
    from ....application.record.refusals import Failing, Problems, Unclean
    from ..presenters import refuse_each

    if isinstance(err, Failing):
        show_findings(err.findings, err.title)
        if err.written:
            print("nothing was written")
        return 1
    if isinstance(err, Unclean):
        return unclean(err.state)
    if isinstance(err, Problems):
        return refuse_each(err.problems)
    return refuse(err.lines, err.fix)
