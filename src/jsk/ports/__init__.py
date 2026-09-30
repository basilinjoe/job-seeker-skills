"""What the application and the domain need from outside, as Protocols.

An implementation satisfies a port by shape, not by inheritance, so nothing imports this
package at run time: a use case names a port in its annotations under TYPE_CHECKING, and the
command handler passes in whatever infra implements it. Startup is budgeted
(tests/test_budget.py), and `typing` alone would cost every command a few milliseconds.
"""
