"""A gate's findings, and how many of them it prints.

These lived in validate_urs.py, the URS record gate, and every other gate and `jsk kb`
verb borrowed them from there - so deleting that gate with the URS record would have
taken `jsk kb check`'s output with it. They moved here when the record gate became one
check over the short resume.json (2026-09-25); nothing about them changed.
"""


class Report:
    def __init__(self):
        self.fails = []
        self.warns = []

    def fail(self, msg):
        self.fails.append(msg)

    def warn(self, msg):
        self.warns.append(msg)


def show(items, mark, limit):
    """At most `limit` findings, then the count of what was not listed.

    Truncating a gate's output is only safe while the total is still visible, so
    the caller prints the real counts in the header and this says how many it left
    out. The header keeps printing the true totals, so nothing is hidden by the cap.
    """
    for item in items[:limit or len(items)]:
        print(f"  {mark}  {item}")
    if limit and len(items) > limit:
        print(f"  {mark}  ... and {len(items) - limit} more")
