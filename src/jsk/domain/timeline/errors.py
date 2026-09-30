"""How a write to an application refuses: with its reason and the fix."""


class Unwritable(Exception):
    """A write to an application directory that did not happen. Carries the fix."""

    def __init__(self, message, fix):
        """Hold the refusal.

        Args:
            message: what was not written, and why.
            fix: what the person does about it.
        """
        super().__init__(message)
        self.fix = fix


class Frozen(Unwritable):
    """Refused because the application is sent."""
