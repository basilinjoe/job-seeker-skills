"""Which files a render writes, and what they are called."""

# The stem follows the VARIANT. It used to follow the format, so
# `--format latex --profile ats-maximal` wrote `{name}_Resume.tex` and silently
# overwrote the presentation render with a different document.
#
# The ATS-maximal PDF shares the presentation stem. It was `{name}_Resume_ATS.pdf`, and
# that is the name a recruiter reads on the file they were sent. --ats-max switches
# which variant the one PDF holds and never adds a second, so the two cannot collide;
# the gates tell them apart by the jsk-variant keyword in the PDF's own metadata
# (check_ats.variant_of), not by the name.
#
# There is no plain-text file any more (Ruling 23 of the graph-native plan): the gates read
# emit_text.emit over the plaintext variant's plan in memory, the same plan as the .tex.
STEMS = {
    "presentation": "{name}_Resume",
    "ats-maximal": "{name}_Resume",
}

# The variant whose emitted text the gates read: ASCII-folded whatever the PDF holds.
TEXT_VARIANT = "plaintext"


def select_targets(fmt, profile):
    """(variant, kind, stem) rows to render.

    --profile names the variant the document is rendered IN; --format names a
    file kind. They compose. --profile used to be discarded entirely whenever
    --format was left at its default of `all`, so asking for an ATS-maximal
    render quietly gave you a presentation one.

    --ats-max switches the variant the PDF holds; it never adds a second PDF.

    Args:
        fmt: latex | all; any other kind is passed through for the caller to refuse.
        profile: the variant, or None for presentation.

    Returns:
        The rows, in the order they are rendered.
    """
    variant = profile or "presentation"
    kind = "latex" if fmt == "all" else fmt
    return [(variant, kind, STEMS.get(variant, "{name}_Resume"))]


def safe_name(text):
    """`text` as a file name: every character but a letter or digit an underscore.

    Args:
        text: a name, or None.

    Returns:
        The name, never empty - "Resume" when nothing is left.
    """
    keep = [c if c.isalnum() else "_" for c in (text or "Resume")]
    return "".join(keep).strip("_").replace("__", "_") or "Resume"
