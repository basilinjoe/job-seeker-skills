"""Reading Turtle and TriG, where each half lives now: the parsed text in the domain, the
parse through the engine in infra.oxigraph.codec, the file read in infra.files."""
from ..domain.record.parsed import (BANNER, NUMERIC, SUBJECT, TOKENS, GraphError, Parsed, comments,
                                    normalise, sha256, subject_lines)
from ..infra.files import Missing, NotUtf8, Unreadable, parse, read_text
from ..infra.oxigraph.codec import canonical_numbers, parse_text

__all__ = ["BANNER", "NUMERIC", "SUBJECT", "TOKENS", "GraphError", "Missing", "NotUtf8", "Parsed",
           "Unreadable", "canonical_numbers", "comments", "normalise", "parse", "parse_text",
           "read_text", "sha256", "subject_lines"]
