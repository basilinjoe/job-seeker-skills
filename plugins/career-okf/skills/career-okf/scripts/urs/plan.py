"""The render plan: `build(doc, view_id, region, fmt)`.

The work lives in two modules either side of one seam:

    resolve.py      decides *what* the document says - selection, ordering,
                    provenance filtering, region gating
    formatting.py   decides *how* a single value reads - dates, grades,
                    quantities, the fold to ASCII

This module is their public face. `from urs import plan` and `plan.build(...)`
have always been the way in, and they still are; the split is behind it.
"""

from .formatting import (ASCII_FOLD, MONTHS, fold_ascii, fmt_grade, fmt_instant,
                         fmt_period, fmt_quantity, period_key)
from .resolve import (CATEGORY_ORDER, DEMONYM, PROVENANCE_RANK, Resolver, build)

__all__ = [
    "build", "Resolver",
    "fold_ascii", "fmt_instant", "fmt_period", "fmt_grade", "fmt_quantity",
    "period_key", "MONTHS", "ASCII_FOLD",
    "PROVENANCE_RANK", "CATEGORY_ORDER", "DEMONYM",
]
