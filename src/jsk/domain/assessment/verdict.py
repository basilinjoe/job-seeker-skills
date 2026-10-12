"""A requirement's verdict: the order the verdicts rank in, and why none is ever raised."""
from ..ontology import ENUMS

# Raising a verdict is never the analyst's call. When the match under-reads the record, the
# fix is in the career - the tag, or the confirmed bullet - made in the conversation with the
# person present; then the match reads it. A verdict typed higher is a claim nobody made.
VERDICTS = ENUMS["verdict"]
# satisfied 3 … unsatisfied 0; `indeterminate`, last, ranks nowhere.
RANK = {v: len(VERDICTS) - 2 - n for n, v in enumerate(VERDICTS[:-1])}
RAISE_FIX = ("lower it, or - if the record really shows it - the career needs the tag or the "
             "confirmation, which the conversation makes; then derive the assessment again "
             "(`assessment_derive`)")
