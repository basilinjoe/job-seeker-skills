"""What `jsk match` says of a match beyond its buckets: the Verdict each bucket supports, the
question a number no metric backs is asked as, and which FAIL stops a match."""

SOURCES = "dashboards, retros, release notes"


def quoted(numbers):
    """`'a'`, `'a' and 'b'`, `'a', 'b' and 'c'`.

    Args:
        numbers: the numbers, as their text.

    Returns:
        Each quoted, the last joined with "and".
    """
    shown = [f"'{n}'" for n in numbers]
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def fault_question(q):
    """The question, ready to be asked aloud. It asks for the figure and its source and
    offers only the words as the alternative - never another metric's number, which is
    how the ElevenLabs author turned a 300-400 into a 300-800 nobody had said.

    Args:
        q: one of record_faults' entries: its bullet, numbers, superseded and cites.

    Returns:
        The question as one line.
    """
    parts = []
    if q["numbers"]:
        many = len(q["numbers"]) > 1
        parts.append(f"{quoted(q['numbers'])} in {q['bullet']} {'are' if many else 'is'} in "
                     + ("no metric it cites" if q["cites"] else "no metric (it cites none)"))
    for s in q["superseded"]:
        parts.append(f"'{s['number']}'" + ("" if q["numbers"] else f" in {q['bullet']}")
                     + f" is {s['version']}'s number, replaced on {s['until']}")
    many = len(q["numbers"]) + len(q["superseded"]) > 1
    return ("; ".join(parts) + " - " + ("what are the figures, and where do they come from"
                                         if many else "what is the figure, and where does it "
                                         "come from")
            + f" ({SOURCES})? Or should the words change?")


def verdict(state, carriers):
    """The Verdict the record supports, from the bucket and the evidence: the most gaps.md
    may say. A tag or an unconfirmed bullet is a claim, so matching on one is `unevidenced`.

    Args:
        state: the requirement's bucket (matched, near, missing, ambiguous, candidate,
            implicit).
        carriers: the match's carriers, each with its `evidence`.

    Returns:
        The verdict's name, or None for `implicit`: the match does not assess it.
    """
    if state == "matched":
        return ("satisfied" if any(c["evidence"] == "confirmed" for c in carriers)
                else "unevidenced")
    return {"near": "partial", "missing": "unsatisfied", "ambiguous": "indeterminate",
            "candidate": "indeterminate"}.get(state)


def blocks(finding, here):
    """Does this FAIL stop matching the posting in `here` (its directory, with a slash)?

    The career, the vocabulary and the posting's own directory: a fault there changes what
    matches. A fault in another application does not - an old advert that no longer quotes
    cleanly must not block every new one - except a syntax error anywhere, which hides that
    file's ids and so switches off the dangling check for the whole workspace.

    Args:
        finding: a Finding, with its rule and the file it names.
        here: the application's folder relative to the workspace, ending in a slash.

    Returns:
        True when the finding stops the match.
    """
    return (finding.rule == "syntax" or not finding.file.startswith("applications/")
            or finding.file.startswith(here))
