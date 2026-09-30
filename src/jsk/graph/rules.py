"""Tier 2 bound to the disk. The rules are domain/record/rules.py's; this module
supplies the real posting.md and decisions.txt reader and the files' record state,
and keeps every name its callers use."""
from ..domain.posting.advert import TYPOGRAPHY as TYPOGRAPHY
from ..domain.posting.advert import EMPHASIS as EMPHASIS
from ..domain.posting.advert import squash as squash
from ..domain.posting.advert import OPTIONAL_WORDS as OPTIONAL_WORDS
from ..domain.posting.advert import REQUIRED_WORDS as REQUIRED_WORDS
from ..domain.posting.advert import HEADING_ASKS as HEADING_ASKS
from ..domain.posting.advert import HEADING_NOT as HEADING_NOT
from ..domain.posting.advert import ELIGIBILITY as ELIGIBILITY
from ..domain.posting.advert import LIST_ITEM as LIST_ITEM
from ..domain.posting.advert import BOLD_LINE as BOLD_LINE
from ..domain.posting.advert import HEADING_DOES as HEADING_DOES
from ..domain.posting.advert import HEADING_OFFERS as HEADING_OFFERS
from ..domain.posting.advert import HEADING_OPTIONAL as HEADING_OPTIONAL
from ..domain.posting.advert import OFFERS_MORE as OFFERS_MORE
from ..domain.posting.advert import TERMINAL as TERMINAL
from ..domain.posting.advert import ABOUT as ABOUT
from ..domain.posting.advert import FIRST_LINE as FIRST_LINE
from ..domain.posting.advert import bare_heading as bare_heading
from ..domain.posting.advert import sub_heading as sub_heading
from ..domain.posting.advert import AdvertLine as AdvertLine
from ..domain.posting.advert import _heading as _heading
from ..domain.posting.advert import advert_lines as advert_lines
from ..domain.posting.advert import asked_lines as asked_lines
from ..domain.record.rules import PREFIX as PREFIX
from ..domain.record.rules import COUNTS_AS as COUNTS_AS
from ..domain.record.rules import Rule as Rule
from ..domain.record.rules import Reads as Reads
from ..domain.record.rules import v as v
from ..domain.record.rules import dangling_fix as dangling_fix
from ..domain.record.rules import version_gaps as version_gaps
from ..domain.record.rules import label_clashes as label_clashes
from ..domain.record.rules import misplaced_postings as misplaced_postings
from ..domain.record.rules import node as node
from ..domain.record.rules import duplicates as duplicates
from ..domain.record.rules import untyped as untyped
from ..domain.record.rules import unmatched_narrowing as unmatched_narrowing
from ..domain.record.rules import reclassed as reclassed
from ..domain.record.rules import bare_capabilities as bare_capabilities
from ..domain.record.rules import bare as bare
from ..domain.record.rules import folder_of as folder_of
from ..domain.record.rules import unquoted as unquoted
from ..domain.record.rules import worded_otherwise as worded_otherwise
from ..domain.record.rules import dropped_lines as dropped_lines
from ..domain.record.rules import uncovered as uncovered
from ..domain.record.rules import out_of_step as out_of_step
from ..domain.record.rules import log_sync_fix as log_sync_fix
from ..domain.record.rules import PLACEHOLDER as PLACEHOLDER
from ..domain.record.rules import DENIAL as DENIAL
from ..domain.record.rules import placeholder_answers as placeholder_answers
from ..domain.record.rules import bad_periods as bad_periods
from ..domain.record.rules import concept_class_rules as concept_class_rules
from ..domain.record.rules import RULES as RULES
from ..domain.record.rules import term_text as term_text


def tier2(store):
    """Findings for the whole loaded workspace, its files read from disk.

    Args:
        store: the loaded workspace, tier 1 already run.

    Returns:
        [Finding], as domain.record.rules.tier2 finds them. Reads each application's
        posting.md and decisions.txt, and for a career still laid out as files, whether
        they exist.
    """
    from ..domain.record.rules import tier2 as run
    from ..infra.adverts import Adverts
    from ..infra.oxigraph.record import state

    return run(store, Adverts(), state)
