"""Which files a render writes, and what they are called."""

# The stem follows the VARIANT. It used to follow the format, so
# `--format latex --profile ats-maximal` wrote `{name}_Resume.tex` and silently
# overwrote the presentation render with a different document.
#
# The ATS-maximal PDF shares the presentation stem. It was `{name}_Resume_ATS.pdf`, and
# that is the name a recruiter reads on the file they were sent. --ats-max switches
# which variant the one PDF holds and never adds a second, so the two cannot collide;
# the gates tell them apart by the jsk-variant keyword in the PDF's own metadata
# (check_ats.variant_of), not by the name. The .txt keeps its suffix: it is pasted into
# a box, never attached.
STEMS = {
    "presentation": "{name}_Resume",
    "ats-maximal": "{name}_Resume",
    "plaintext": "{name}_Resume_ATS",
}


def select_targets(fmt, profile):
    """(variant, kind, stem) rows to render.

    --profile names the variant the document is rendered IN; --format names a
    file kind. They compose. --profile used to be discarded entirely whenever
    --format was left at its default of `all`, so asking for an ATS-maximal
    render quietly gave you a presentation one.

    --ats-max switches the variant the PDF holds; it never adds a second PDF.
    The plain text rides along either way - it is the paste-in-box artefact and
    it is ASCII-folded whatever the PDF holds.

    Args:
        fmt: latex | txt | all; any other kind is passed through for the caller to refuse.
        profile: the variant, or None for presentation.

    Returns:
        The rows, in the order they are rendered.
    """
    variant = profile or "presentation"
    if fmt != "all":
        return [(variant, fmt, STEMS.get(variant, "{name}_Resume"))]
    return [
        (variant, "latex", STEMS.get(variant, "{name}_Resume")),
        ("plaintext", "txt", STEMS["plaintext"]),
    ]


def safe_name(text):
    """`text` as a file name: every character but a letter or digit an underscore.

    Args:
        text: a name, or None.

    Returns:
        The name, never empty - "Resume" when nothing is left.
    """
    keep = [c if c.isalnum() else "_" for c in (text or "Resume")]
    return "".join(keep).strip("_").replace("__", "_") or "Resume"
