#!/usr/bin/env python3
"""The parse gate's old module path, kept until P6 for its names.

The command is adapters/cli/gates/ats.py and the gate application/gates/ats.py; this
module keeps the path, the names callers and tests reach through it, and the .txt reader
(Ruling 4 of the onion design).
"""
import re
import sys

from ..domain.gates.ats_rules import HEADING_MAX as HEADING_MAX
from ..domain.gates.ats_rules import LIGATURES as LIGATURES
from ..domain.gates.ats_rules import MIN_EXTRACTED_CHARS as MIN_EXTRACTED_CHARS
from ..domain.gates.ats_rules import RISKY_BULLETS as RISKY_BULLETS
from ..domain.gates.ats_rules import ROLE_WORDS as ROLE_WORDS
from ..domain.gates.ats_rules import SAFE_BULLETS as SAFE_BULLETS
from ..domain.gates.ats_rules import SPLIT_WORD as SPLIT_WORD
from ..domain.gates.ats_rules import codepoint as codepoint
from ..domain.gates.ats_rules import has_phone as has_phone
from ..domain.gates.ats_rules import is_heading as is_heading
from ..domain.gates.ats_rules import judge as judge
from ..infra.pdf import read_pdf as read_pdf

# The keyword emit_latex.py writes into the PDF's metadata to name the variant.
VARIANT_KEYWORD = re.compile(r"jsk-variant:([A-Za-z0-9_-]+)")


def variant_of(pdf_path):
    """The render variant the PDF was built as - "ats-maximal", "presentation" -
    or None when its metadata carries no marker.

    Read from the metadata rather than the file name, because the name is the
    person's to change: "_ATS" in the stem was the only marker, and a renamed
    file silently lost its strict check. None for a file that cannot be opened
    as a PDF - the gate itself reports that. Raises ImportError without
    pymupdf, as read_pdf() does: a variant nobody could read is not the same
    answer as a variant that is not there.
    """
    from ..infra.pdf import keywords as keywords_of

    try:
        keywords = keywords_of(pdf_path)
    except ImportError:
        raise
    except Exception:  # noqa: BLE001 - pymupdf raises its own types on a damaged PDF; no keyword then
        return None
    m = VARIANT_KEYWORD.search(keywords)
    return m.group(1) if m else None


def read_txt(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read(), []


def main(argv=None):
    """The gate, as an exit code (adapters.cli.gates.ats.main).

    Args:
        argv: the arguments alone, as check_prose.py takes them; by default sys.argv's.

    Returns:
        The exit code. Prints the verdict.
    """
    from ..adapters.cli.gates.ats import main as ats

    return ats(sys.argv[1:] if argv is None else list(argv))


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.gates.check_ats", "jsk resume check RESUME.pdf --only parse"))
