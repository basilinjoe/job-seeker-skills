"""Shared help-text and flag handling for the hand-rolled entry points.

These entry points hand-write their usage, and they used to print one paragraph
of the module docstring and return 2 - so `jsk resume render --help` named none of the
flags SKILL.md tells a reader to look up there, and a caller checking exit codes
saw "called wrong" for asking a question.

Both halves are fixed here, so every command answers a question with an answer
and an exit code of 0.
"""
from __future__ import annotations

import sys

HELP_FLAGS = frozenset({"-h", "--help", "help"})


def utf8_stdout() -> None:
    """Print UTF-8, replacing what cannot be encoded. A cp1252 Windows console raises
    UnicodeEncodeError from inside a print of a finding's non-ASCII text, and the whole
    verdict is lost with it. A stream that cannot be reconfigured - a test's StringIO,
    an already-detached one - is left as it is."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError, TypeError, AttributeError):
        pass                    # a wrapper stream's reconfigure may take other arguments


def refused(refusal) -> int:
    """Print a refusal as every command prints it.

    Args:
        refusal: [what is wrong, the fix], as application.guards returns it.

    Returns:
        1, the exit code of a refused command. Writes both lines to stdout.
    """
    print("REFUSED - " + refusal[0])
    print(refusal[1])
    return 1


def retired_path(module: str, command: str) -> int:
    """Say that `python -m <module>` no longer runs its command, and what does.

    `jsk` is the only door (Ruling 10 of the onion design). A module left importable but
    silent would exit 0, which a script reads as success, so it says what replaced it.

    Args:
        module: the dotted path that was run.
        command: the `jsk <noun> <verb>` that replaced it.

    Returns:
        2, the exit code of a call made wrongly. Prints one line.
    """
    print(f"python -m {module} was retired: it is {command} now")
    return 2


def wants_help(argv) -> bool:
    """Did the caller actually ask for help, rather than call the thing wrongly?"""
    return any(a in HELP_FLAGS for a in argv)


class Problem(str):
    """What was wrong with a call, as the message printed - and, for a caller that adds
    its own fix, `kind` ("unknown", "missing" or "repeated") and the `flag`."""

    def __new__(cls, text, kind, flag):
        self = super().__new__(cls, text)
        self.kind, self.flag = kind, flag
        return self


def parse_flags(args, values, switches=("--json",), repeats=(), lists=(), dash=False):
    """((positional, flags), None) or (None, a Problem).

    `values` take one argument, `switches` none, and `repeats` one argument each time
    they appear, collected into a list. `lists` take every argument up to the next one
    starting with "-", as a list that may be empty. A value may start with "-" - it is
    whatever follows its flag. A value flag given twice is refused: which one was meant
    is the caller's to say, and keeping the last dropped the first without a word.
    After `--` every argument is positional, so a query can say "-40%". With `dash`, a
    lone "-" is positional too - for a command that answers it - else an unknown flag.
    """
    positional, flags, pending, listing, rest = [], {}, None, None, False
    for token in args:
        if rest:
            positional.append(token)
            continue
        if listing and not token.startswith("-"):
            flags[listing].append(token)
            continue
        listing = None
        if pending:
            if pending in repeats:
                flags.setdefault(pending, []).append(token)
            elif pending in flags:
                return None, Problem(f"{pending} given twice - pass it once", "repeated",
                                     pending)
            else:
                flags[pending] = token
            pending = None
        elif token == "--":
            rest = True
        elif token in values or token in repeats:
            pending = token
        elif token in lists:
            listing = token
            flags.setdefault(token, [])
        elif token in switches:
            flags[token] = True
        elif token.startswith("-") and not (dash and token == "-"):
            return None, Problem(f"unknown flag: {token}", "unknown", token)
        else:
            positional.append(token)
    if pending:
        return None, Problem(f"{pending} needs a value", "missing", pending)
    return (positional, flags), None


def docstring_usage(doc: str | None) -> str:
    """The operator-facing half of a module docstring: usage, flags, exit codes.

    Splitting on blank lines and taking `[1]` - what these entry points used to do -
    yields the two-line invocation and drops the flag list that follows it, which is
    the part anyone reading `--help` came for.

    These docstrings all run operator-facing first and design commentary second,
    with the exit-code paragraph as the seam. Cutting there keeps the flags and
    leaves out the essay about why the emitters are split - which belongs to
    whoever opens the file, not to whoever typed `--help`.
    """
    if not doc:
        return ""
    paragraphs = doc.strip().split("\n\n")
    if len(paragraphs) < 2:
        return doc.strip()

    kept = []
    for para in paragraphs[1:]:
        kept.append(para)
        if para.lstrip().startswith("Exit "):
            break
    return "\n\n".join(kept).rstrip()


def show(items, mark, limit):
    """Print at most `limit` findings, then the count of what was not listed.

    Truncating a gate's output is only safe while the total is still visible, so
    the caller prints the real counts in the header and this says how many it left
    out. The header keeps printing the true totals, so nothing is hidden by the cap.

    Args:
        items: the finding lines, in order.
        mark: FAIL or WARN, printed before each.
        limit: how many to print; 0 or None prints them all.

    Returns:
        None. Writes to stdout.
    """
    for item in items[:limit or len(items)]:
        print(f"  {mark}  {item}")
    if limit and len(items) > limit:
        print(f"  {mark}  ... and {len(items) - limit} more")
