"""The one line a render says about its pages: what was produced, against the budget.

the resume_render tool prints it under each PDF and the resume_check tool reprints it over a render it did not
make, so the two cannot describe one measurement in different words.
"""

LAST_PAGE_FLOOR = 50      # percent of the last page's height its text reaches


def page_report(name, count, budget, fill=None):
    """One line about what was actually produced, against what was asked for.

    This printed the budget alone, which is a number nobody measured - the resume
    that prompted the fix rendered on one page against a budget of two and said so
    nowhere. Over budget is reported rather than failed: fit_pages.py owns that
    verdict, and it is the script that can do something about it. So is a last page
    under half full: it is room the budget paid for, or a page too many.

    Args:
        name: the PDF's file name.
        count: its pages, or None when they could not be counted.
        budget: the plan's page budget.
        fill: how far down its last page the text reaches, in percent, or None.

    Returns:
        The line, indented as the render prints it.
    """
    if count is None:
        return (f"  pages  {name}: budget {budget}, not measured - "
                f"pip install pymupdf to have this checked")
    measured = f"{count} page{'' if count == 1 else 's'} against a budget of {budget}"
    if count > budget:
        return f"  pages  {name}: {measured} - OVER BUDGET, call the resume_fit tool"
    if count > 1 and fill is not None and fill < LAST_PAGE_FLOOR:
        return (f"  pages  {name}: {measured} - page {count} is {fill:.0f}% full: add the "
                f"evidence the budget allows, or fit it to {count - 1} "
                f"page{'' if count == 2 else 's'}")
    return f"  pages  {name}: {measured}"
