"""A posting's decisions checked one row at a time against the advert's lines.

`jsk posting build` checked decisions.txt's rows in one loop (application/posting/build.py,
until 2026-10-02); a graph-native posting is decided a row at a time, each row checked
against the lines the graph holds and the rows already decided (Ruling 18's
`posting_decide`). Both go through `Rows`, so there is one set of checks: the line exists,
`asked` is in it, the slug and the normalised `asked` are unique, the quote is the line's
text and the necessity is one. Then `uncovered`: every qualification line that is not
eligibility used or dropped.

Each check returns (severity, message, fix) findings and refuses nothing itself; the
caller decides what a FAIL stops. Which concepts a row may name needs the workspace, so
that check stays with the caller. Nothing here reads a file or the store.
"""
from .. import ontology as O
from .advert import REQUIRED_WORDS, squash


class Rows:
    """The rows one posting decides, checked as they arrive.

    A row or drop is labelled by whatever its caller locates it by - decisions.txt's line,
    or a row's place in a batch - and `at(label)` is how a message names that place.
    """

    def __init__(self, lines, at=str, listed="extract printed", refetch=""):
        """Hold what the rows are checked against.

        Args:
            lines: {n: advert.AdvertLine}.
            at: label -> where a message says the row is (`decisions.txt:12`).
            listed: how a message names the numbered lines: "extract printed".
            refetch: the fix for a line number that is none of them.
        """
        self.lines, self.at, self.listed, self.refetch = lines, at, listed, refetch
        self.used = set()           # line numbers answered: by a row, or by a drop
        self.slugs = {}             # slug -> the label of the row that took it
        self.terms = {}             # normalised asked -> the label of the row that asked it

    def unknown(self, label, n):
        """The finding for a line number that is not one of the advert's."""
        return ("FAIL", f"{self.at(label)}: line {n} is not one {self.listed} "
                        f"(1-{len(self.lines)})", self.refetch)

    def row(self, label, n, slug, asked, quote=None, need=None):
        """The findings for one requirement row, which is then counted as decided.

        Args:
            label: where the row is, for `at`.
            n: the advert line it quotes.
            slug: the requirement's slug.
            asked: its term, as the advert writes it.
            quote: its quote, when the caller states one; it must be the line's text.
            need: its necessity, when the caller states one.

        Returns:
            [(severity, message, fix)], in the order build always reported them.
        """
        line = self.lines.get(n)
        if line is None:
            return [self.unknown(label, n)]
        self.used.add(n)            # answered, even when wrongly: not also "neither used"
        out = []
        if squash(asked).casefold() not in line.text.casefold():
            out.append(("FAIL", f"{self.at(label)}: {asked!r} is not in line {n}: "
                                f"{line.text!r}",
                        "fix:  write `asked` as the line writes it, or use the line that says it"))
        if slug in self.slugs:
            out.append(("FAIL", f"{self.at(label)}: slug {slug!r} is used on line "
                                f"{self.slugs[slug]} too", "fix:  one slug per requirement"))
        self.slugs.setdefault(slug, label)
        # `jsk tailor match --gaps` pairs gaps.md's rows to requirements by this, so two with
        # one `asked` could never pair and would warn on even a perfect draft.
        term = O.norm(asked)
        if term in self.terms:
            out.append(("FAIL", f"{self.at(self.terms[term])} and line {label}: two "
                                f"requirements ask {asked!r}",
                        "fix:  merge them into one requirement, or name each as the advert "
                        "writes it"))
        self.terms.setdefault(term, label)
        if quote is not None and quote != line.text:
            # Ruling 2: the quote is the line, so quote-verbatim cannot fail on a row.
            out.append(("FAIL", f"{self.at(label)}: the quote is not line {n}'s text: "
                                f"{line.text!r}", "fix:  leave the quote out; it is the line"))
        if need is not None and need not in O.ENUMS["necessity"]:
            out.append(("FAIL", f"{self.at(label)}: need {need!r} is not one of "
                                f"{', '.join(O.ENUMS['necessity'])}",
                        "fix:  name one, or leave it out for the line's default"))
        return out

    def necessity(self, label, n, slug, need):
        """The WARN for a responsibility made required when its words do not say so, or [].

        Args:
            label: where the row is.
            n: its line, which exists.
            slug: the requirement's slug.
            need: the necessity it takes.
        """
        line = self.lines[n]
        if need == "required" and line.section == "responsibility" \
                and not REQUIRED_WORDS.search(line.text):
            return [("WARN", f"{self.at(label)}: {slug} makes responsibility line {n} "
                             "required, and the line does not say so", None)]
        return []

    def drop(self, label, n):
        """The findings for one drop, which then counts its line as answered."""
        out = [] if n in self.lines else [self.unknown(label, n)]
        self.used.add(n)
        return out

    def uncovered(self):
        """The qualification lines, eligibility aside, neither used nor dropped, by number."""
        return uncovered(self.lines, self.used)


def uncovered(lines, used):
    """The qualification lines that are not eligibility and that no row or drop answered.

    A responsibility may go unmentioned: its requirement would be implicit, which the match
    does not assess (tailor-cost Ruling 3).

    Args:
        lines: {n: advert.AdvertLine}.
        used: the line numbers answered.

    Returns:
        [n], in the advert's order.
    """
    return [x.n for x in lines.values()
            if x.section == "qualification" and not x.elig and x.n not in used]


def coverage(missing, where, fix="fix:  a row for what it asks, or `n | - | <reason>`"):
    """The FAIL for qualification lines left neither used nor dropped.

    Args:
        missing: uncovered's line numbers; not empty.
        where: what the message names (the decisions file).
        fix: what resolves it.

    Returns:
        (severity, message, fix).
    """
    return ("FAIL", f"{where}: advert line{'s' if len(missing) > 1 else ''} "
                    f"{', '.join(map(str, missing))} neither used nor dropped", fix)
