"""A gate's findings: the failures and the warnings, in the order they were found.

These lived in validate_urs.py, the URS record gate, and every other gate and `jsk kb`
verb borrowed them from there - so deleting that gate with the URS record would have
taken `jsk kb check`'s output with it. They moved when the record gate became one check
over the short resume.json (2026-09-25); nothing about them changed.
"""


class Report:
    """The FAIL and WARN lines a gate has found, each list in the order they were added."""

    def __init__(self):
        self.fails = []
        self.warns = []

    def fail(self, msg):
        """Record one failure line."""
        self.fails.append(msg)

    def warn(self, msg):
        """Record one warning line."""
        self.warns.append(msg)
