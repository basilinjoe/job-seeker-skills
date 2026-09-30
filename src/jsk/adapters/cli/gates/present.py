"""The lines every gate prints the same way: its counts, its findings and its verdict."""
from ....cliutil import show

FAILED = "DO NOT SEND - fix the failures above"


def findings(result, limit=None):
    """Print a gate's count line and then its findings, failures first.

    Args:
        result: the gate's GateResult.
        limit: how many of each to print; None prints them all (cliutil.show).

    Returns:
        None. Writes to stdout.
    """
    print(f"\nFAIL {len(result.fails)}   WARN {len(result.warns)}")
    show(list(result.fails), "FAIL", limit)
    show(list(result.warns), "warn", limit)


def verdict(result, passed, failed=FAILED):
    """Print the gate's last line and return its exit code.

    Args:
        result: the gate's GateResult.
        passed: the line for a result with no failures.
        failed: the line for one with any.

    Returns:
        The result's exit code. Writes to stdout.
    """
    print("\n" + (failed if result.fails else passed))
    return result.code


def unreadable(result):
    """Print the verdict on a document that would not open (application.gates.result).

    Returns:
        1. Writes to stdout.
    """
    print(f"checking: {result.name}")
    findings(result)
    return verdict(result, "")
