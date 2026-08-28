"""Region profiles: market conventions as data.

A profile answers three questions about a field path, and nothing else:

    forbidden  -> never emit it, whatever the record holds
    required   -> warn loudly when it is absent
    expected   -> conventional here, so a `private` field may be emitted

The gate is deliberately dumb. Anything that needs judgement belongs in the
profile's `notes`, addressed to whoever is reading, not encoded here.
"""
import json
import os

PRIVATE_BY_DEFAULT = (
    "person.demographics",
    "person.photo",
    "person.name.related_names",
    "identity_documents",
    "referees",
    "compensation",
    "availability",
)


def schema_dir(start=None):
    """The skill's own schema/ directory, found relative to this file."""
    here = os.path.dirname(os.path.abspath(start or __file__))
    return os.path.normpath(os.path.join(here, "..", "..", "schema"))


def load(ref, base=None):
    """Load a profile by id (`urs:profile:au/1`), region code (`AU`) or path."""
    base = base or schema_dir()
    if ref is None:
        ref = "default"
    if os.path.exists(ref):
        path = ref
    else:
        token = ref
        if token.startswith("urs:profile:"):
            token = token[len("urs:profile:"):].split("/")[0]
        token = token.lower()
        if token in ("xx", "", "none"):
            token = "default"
        path = os.path.join(base, "profiles", f"{token}.json")
        if not os.path.exists(path):
            path = os.path.join(base, "profiles", "default.json")
    with open(path, encoding="utf8") as fh:
        return json.load(fh)


class Gate:
    """Decides whether one field path may be rendered under a profile."""

    def __init__(self, profile, extra_redactions=()):
        self.profile = profile
        self.render = profile.get("render", {})
        self.forbidden = list(profile.get("forbidden", []))
        self.required = list(profile.get("required", []))
        self.expected = list(profile.get("expected", []))
        self.redacted = list(extra_redactions)

    @staticmethod
    def _covers(rule, path):
        """A rule covers a path if it is the path or a prefix segment of it."""
        return path == rule or path.startswith(rule + ".")

    def permits(self, path):
        for rule in self.redacted:
            if self._covers(rule, path):
                return False
        for rule in self.forbidden:
            if self._covers(rule, path):
                return False
        if self._is_private(path):
            return any(
                self._covers(rule, path) or self._covers(path, rule)
                for rule in self.required + self.expected
            )
        return True

    @staticmethod
    def _is_private(path):
        return any(
            path == p or path.startswith(p + ".") or p.startswith(path + ".")
            for p in PRIVATE_BY_DEFAULT
        )

    def missing_required(self, present):
        """Required paths with nothing behind them. `present` is a set of paths."""
        return [
            r for r in self.required
            if not any(p == r or p.startswith(r + ".") for p in present)
        ]

    def setting(self, key, fallback=None):
        return self.render.get(key, fallback)
